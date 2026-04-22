"""模拟验证 v3 修复：pin / 冷却 / finished_total / 探针公平轮询 / 计数器。"""
import asyncio
import os
import sys
import types
import random
import json
import tempfile
from datetime import datetime, timedelta

ROOT = '/Volumes/waijie/tg'
sys.path.insert(0, ROOT)


# ---- Fake AccountManager：5 号全 primary ----
class FakeAccountManager:
    def __init__(self, config_path):
        with open(config_path) as f:
            cfg = json.load(f)
        self.rate_config = cfg['rate_limit']
        self.accounts = []
        for i, name in enumerate(['A', 'B', 'C', 'D', 'E']):
            self.accounts.append({
                'name': name,
                'role': 'primary',
                'runtime_state': 'active',
                'client': object(),
                'request_count': 0,
                'probe_count': 0,
                'block_count': 0,
                'is_blocked': False,
                'block_until': None,
            })

    async def connect_all(self): pass
    async def disconnect_all(self): pass

    def get_active_primary_accounts(self):
        return [a for a in self.accounts if a['role'] == 'primary' and a['runtime_state'] == 'active']

    def get_available_backup_accounts(self):
        return []

    def get_next_account(self):
        # 没有 pin 时，fallback（不应被使用）
        raise RuntimeError("get_next_account 被调用了，pin 没生效！")

    def activate_account(self, acc, role=None, reason=''):
        acc['runtime_state'] = 'active'

    def mark_account_suspected(self, *a, **kw): pass
    def mark_account_used(self, account):
        account['request_count'] += 1
    def mark_account_success(self, *a, **kw): pass
    def mark_account_error(self, *a, **kw): pass
    def replace_primary_account(self, *a, **kw): return None

    def get_account_runtime_snapshot(self):
        return {a['name']: {
            'role': a['role'], 'runtime_state': a['runtime_state'],
            'requests': a['request_count'],
            'probe_count': a.get('probe_count', 0),
            'block_count': a.get('block_count', 0),
            'blocked': a['is_blocked'],
            'block_until': a['block_until'].strftime('%H:%M:%S') if a['block_until'] else None,
            'suspected_count': 0,
        } for a in self.accounts}


# ---- Fake TelegramFilter：通过 pinned manager 拿账号 ----
call_log = []  # (phone, account_name)

class FakeTelegramFilter:
    def __init__(self, manager, limiter):
        self.manager = manager
        self.limiter = limiter

    async def check_phone(self, phone, country):
        await asyncio.sleep(random.uniform(0.001, 0.005))
        # 通过 pinned manager 拿绑定账号
        account = self.manager.get_next_account()
        account['request_count'] += 1
        call_log.append((phone, account['name']))
        # 根据 scenario 返回
        return SCENARIO.resolve(phone, account['name'])


class FakeRateLimiter:
    def __init__(self, cfg): self.cfg = cfg


def install_fakes():
    am = types.ModuleType('account_manager')
    am.AccountManager = FakeAccountManager
    sys.modules['account_manager'] = am

    fl = types.ModuleType('filter')
    fl.TelegramFilter = FakeTelegramFilter
    sys.modules['filter'] = fl

    rl = types.ModuleType('rate_limiter')
    rl.RateLimiter = FakeRateLimiter
    sys.modules['rate_limiter'] = rl


class Scenario:
    def __init__(self):
        self.rules = {}

    def set(self, phone, account, kind):
        self.rules[(phone, account)] = kind

    def resolve(self, phone, account):
        kind = self.rules.get((phone, account))
        if kind is None:
            # 默认：probe 号全部 registered，其他用号尾奇偶
            if 'probe' in phone:
                kind = 'registered'
            else:
                last = phone[-1] if phone else '0'
                kind = 'registered' if (last.isdigit() and int(last) % 2 == 0) else 'unregistered'
        return self._make(kind, phone)

    def _make(self, kind, phone):
        base = {'phone': phone, 'original_phone': phone, 'registered': False,
                'query_state': None, 'error': None, 'status': None, 'last_seen': None}
        if kind == 'registered':
            base.update(registered=True, query_state='registered', status='offline')
        elif kind == 'unregistered':
            base.update(query_state='unregistered', error='未注册')
        return base


SCENARIO = Scenario()


async def run_case(name, phones, probe_interval=0, probe_phones=None,
                   probe_scenario=None, rate_limit=None):
    global SCENARIO, call_log
    SCENARIO = Scenario()
    call_log = []
    if probe_scenario:
        for (p, acc), kind in probe_scenario.items():
            SCENARIO.set(p, acc, kind)

    rate_limit = rate_limit or {'min_delay': 0, 'max_delay': 0,
                                 'requests_per_account': 100,
                                 'error_cooldown': 2}

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            with open('config.json', 'w') as f:
                json.dump({'accounts': [], 'rate_limit': rate_limit}, f)

            install_fakes()
            import importlib, gui_monitor
            importlib.reload(gui_monitor)
            gui_monitor.config_path = os.path.join(tmpdir, 'config.json')

            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.instance() or QCoreApplication(sys.argv)

            ft = gui_monitor.FilterThread(phones, 'US',
                                           {'rate_limit': rate_limit},
                                           probe_interval, probe_phones or [])

            logs = []
            snapshots = []
            ft.log_signal = types.SimpleNamespace(emit=lambda s: logs.append(s))
            ft.status_signal = types.SimpleNamespace(emit=lambda s: snapshots.append(s))
            ft.probe_anomaly_signal = types.SimpleNamespace(
                emit=lambda *a: logs.append(f'PROBE_ANOMALY:{a}'))
            ft.conflict_signal = types.SimpleNamespace(emit=lambda s: None)
            ft.emergency_pause_signal = types.SimpleNamespace(emit=lambda s: None)

            await ft.filter_task()

            print(f"\n==== [{name}] ====")
            last_snap = snapshots[-1] if snapshots else {}
            return logs, last_snap, list(call_log)
        finally:
            os.chdir(old_cwd)


async def main():
    random.seed(42)

    # ==== Case 1: pin 生效 ====
    # 100 个号，5 worker，每号恰好应被打 20 次
    phones = [f'+100000{i:04d}' for i in range(100)]
    logs, snap, calls = await run_case('pin 生效', phones)
    counts = {}
    for _, acc in calls:
        counts[acc] = counts.get(acc, 0) + 1
    print(f"  各账号请求数: {counts}")
    assert len(counts) == 5, f"5 个账号都应被使用，实际 {len(counts)}"
    # 应该相对均衡（允许抢号随机性，每个号 10-40 之间都算正常）
    for name, c in counts.items():
        assert 5 <= c <= 50, f"{name} 请求数异常: {c}"
    assert sum(counts.values()) == 100, "总请求数应为 100"

    # ==== Case 2: 请求上限触发冷却 ====
    # 单号上限 5，50 个号 / 5 并发 = 每号 10 次，必然触发冷却
    phones = [f'+200000{i:04d}' for i in range(50)]
    logs, snap, calls = await run_case(
        '请求上限冷却',
        phones,
        rate_limit={'min_delay': 0, 'max_delay': 0,
                    'requests_per_account': 5, 'error_cooldown': 1}
    )
    cooldown_logs = [l for l in logs if '达到单号请求上限' in l]
    recovery_logs = [l for l in logs if '冷却结束' in l]
    print(f"  触发上限冷却: {len(cooldown_logs)} 次")
    print(f"  冷却结束恢复: {len(recovery_logs)} 次")
    block_counts = {n: s.get('block_count', 0) for n, s in snap.items()}
    print(f"  各号封禁数: {block_counts}")
    assert len(cooldown_logs) >= 1, "20 个号 / 5 并发 / 单号上限 8，应至少有 1 号触发冷却"
    assert sum(block_counts.values()) >= 1, "封禁数计数器应 >= 1"

    # ==== Case 3: finished_total 触发探针 ====
    # 15 个号，probe_interval=5，probe 号全 registered → 应触发 3 次探针
    phones = [f'+300000{i:04d}' for i in range(15)]
    logs, snap, calls = await run_case(
        '探针按 finished_total 触发',
        phones,
        probe_interval=5,
        probe_phones=['+probe_ok'],
    )
    probe_logs = [l for l in logs if l.startswith('[探针')]
    probe_ok_logs = [l for l in logs if '✅' in l and '探针' in l]
    probe_counts = {n: s.get('probe_count', 0) for n, s in snap.items()}
    print(f"  探针触发: {len(probe_logs)} 条日志, 成功: {len(probe_ok_logs)}")
    print(f"  各号 probe_count: {probe_counts}")
    assert len(probe_logs) >= 3, f"15/5=3 次探针，实际 {len(probe_logs)}"
    assert sum(probe_counts.values()) >= 3, "probe_count 应累计 >= 3"

    # ==== Case 4: 探针公平轮询 ====
    # 50 个号，probe_interval=5 → 10 次探针，5 号应各被抽 2 次
    phones = [f'+400000{i:04d}' for i in range(50)]
    logs, snap, calls = await run_case(
        '探针公平轮询',
        phones,
        probe_interval=5,
        probe_phones=['+probe_fair'],
    )
    probe_counts = {n: s.get('probe_count', 0) for n, s in snap.items()}
    print(f"  各号 probe_count: {probe_counts}")
    # 每号应该被抽到至少 1 次，最多 3 次（差距 <= 2）
    vals = list(probe_counts.values())
    assert max(vals) - min(vals) <= 2, f"探针分配不均: {probe_counts}"
    assert sum(vals) >= 8, f"总探针数应 >= 8, 实际 {sum(vals)}"

    # ==== Case 5: 探针连续失败 → 账号冷却 + block_count++ ====
    phones = [f'+500000{i:04d}' for i in range(40)]
    probe_scenario = {
        ('+probe_bad', 'A'): 'unregistered',
        ('+probe_bad', 'B'): 'registered',
        ('+probe_bad', 'C'): 'registered',
        ('+probe_bad', 'D'): 'registered',
        ('+probe_bad', 'E'): 'registered',
    }
    logs, snap, calls = await run_case(
        '探针失败冷却',
        phones,
        probe_interval=3,
        probe_phones=['+probe_bad'],
        probe_scenario=probe_scenario,
    )
    cooldown_logs = [l for l in logs if '探针连续失败，冷却' in l]
    print(f"  A 探针冷却次数: {len(cooldown_logs)}")
    a_block = snap.get('A', {}).get('block_count', 0)
    print(f"  A 封禁数: {a_block}")
    assert len(cooldown_logs) >= 1, "A 连续失败应至少冷却一次"
    assert a_block >= 1, "A 封禁数应 >= 1"
    # 进度应跑完
    anomaly = [l for l in logs if 'PROBE_ANOMALY' in l]
    assert len(anomaly) == 0, f"不应紧急停止：{anomaly}"

    # ==== Case 6: 水位线卡住时探针仍能触发 ====
    # 模拟第一个号查询慢一些，后续号快速完成，processed 会被卡在 0
    # 但 finished_total 会快速增长，探针仍应触发
    class SlowFirstFilter(FakeTelegramFilter):
        async def check_phone(self, phone, country):
            if phone == '+600000' + '0' * 4:  # 第一个号
                await asyncio.sleep(0.8)  # 让水位线卡住
            else:
                await asyncio.sleep(random.uniform(0.001, 0.005))
            account = self.manager.get_next_account()
            account['request_count'] += 1
            call_log.append((phone, account['name']))
            return SCENARIO.resolve(phone, account['name'])

    # 替换 filter 实现
    sys.modules['filter'] = types.ModuleType('filter')
    sys.modules['filter'].TelegramFilter = SlowFirstFilter

    phones = [f'+600000{i:04d}' for i in range(30)]
    logs, snap, calls = await run_case(
        '水位线卡住探针仍触发',
        phones,
        probe_interval=5,
        probe_phones=['+probe_watermark'],
    )
    probe_logs = [l for l in logs if l.startswith('[探针')]
    print(f"  水位线可能卡住，探针仍触发次数: {len(probe_logs)}")
    assert len(probe_logs) >= 2, f"finished_total 应让探针在水位线卡住时也能跑，实际 {len(probe_logs)}"

    print("\n✅ 全部 v3 模拟通过")


if __name__ == '__main__':
    asyncio.run(main())
