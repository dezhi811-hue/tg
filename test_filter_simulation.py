"""模拟运行 FilterThread.filter_task，验证队列 + 探针熔断 + 水位线逻辑。"""
import asyncio
import os
import sys
import types
import random
import json
import tempfile
from unittest.mock import MagicMock

# 切到项目目录
ROOT = '/Volumes/waijie/tg'
sys.path.insert(0, ROOT)

# ---- Stub 三个业务模块，避免真正连 Telegram ----

# Fake AccountManager
class FakeAccountManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.accounts = [
            {'name': 'A', 'runtime_state': 'active', 'role': 'primary', 'client': object()},
            {'name': 'B', 'runtime_state': 'active', 'role': 'primary', 'client': object()},
            {'name': 'C', 'runtime_state': 'active', 'role': 'primary', 'client': object()},
        ]
        self.paused = set()

    async def connect_all(self):
        return None

    def get_active_primary_accounts(self):
        return [a for a in self.accounts
                if a.get('role') == 'primary' and a.get('runtime_state') == 'active'
                and a['name'] not in self.paused]

    def get_next_account(self):
        active = self.get_active_primary_accounts()
        return active[0] if active else None

    def get_available_backup_accounts(self):
        return [a for a in self.accounts
                if a.get('role') == 'backup' and a.get('runtime_state') == 'standby'
                and a['name'] not in self.paused]

    def replace_primary_account(self, target, backup, reason=''):
        target['role'] = 'backup'
        target['runtime_state'] = 'paused'
        backup['role'] = 'primary'
        backup['runtime_state'] = 'active'
        return backup

    def get_account_runtime_snapshot(self):
        return {a['name']: {'role': a.get('role', 'primary'),
                             'runtime_state': a['runtime_state'],
                             'requests': 0, 'blocked': False, 'block_until': None,
                             'suspected_count': 0} for a in self.accounts}

    def pause_account(self, account, reason=''):
        self.paused.add(account['name'])
        account['runtime_state'] = 'paused'

    def mark_account_suspected(self, *a, **kw): pass
    def mark_account_used(self, *a, **kw): pass
    def mark_account_success(self, *a, **kw): pass
    def mark_account_error(self, *a, **kw): pass

    async def disconnect_all(self):
        return None


# Fake TelegramFilter —— 由 scenario 控制返回结果
class FakeTelegramFilter:
    def __init__(self, manager, limiter):
        self.manager = manager
        self.limiter = limiter

    async def check_phone(self, phone, country):
        # 根据 scenario 决定结果
        await asyncio.sleep(random.uniform(0.01, 0.05))  # 模拟查询耗时
        account = self.manager.get_next_account()
        return SCENARIO.resolve(phone, account['name'])


class FakeRateLimiter:
    def __init__(self, cfg): self.cfg = cfg


# 挂到 sys.modules
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


# ---- Scenario：控制每个 phone/account 的返回值 ----

class Scenario:
    def __init__(self):
        self.rules = {}  # (phone, account_name) -> result; '*' as wildcard

    def set(self, phone, account, result):
        self.rules[(phone, account)] = result

    def resolve(self, phone, account):
        key = (phone, account)
        if key in self.rules:
            return self._make(self.rules[key], phone)
        # default: 偶数号已注册，奇数未注册（按 phone 末尾）
        last = phone[-1] if phone else '0'
        if last.isdigit() and int(last) % 2 == 0:
            return self._make('registered', phone)
        return self._make('unregistered', phone)

    def _make(self, kind, phone):
        base = {'phone': phone, 'original_phone': phone, 'registered': False,
                'query_state': None, 'error': None, 'status': None, 'last_seen': None}
        if kind == 'registered':
            base.update(registered=True, query_state='registered', status='offline')
        elif kind == 'unregistered':
            base.update(query_state='unregistered', error='未注册Telegram')
        elif kind == 'empty':
            base.update(query_state='empty_result', error='查询未返回用户')
        elif kind == 'invalid':
            base.update(query_state='invalid', error='手机号格式无效')
        return base


SCENARIO = Scenario()


# ---- 测试运行 ----

async def run_case(name, phones, probe_interval=0, probe_phones=None, probe_scenario=None, expect_stop=False, backups=None):
    global SCENARIO
    SCENARIO = Scenario()
    if probe_scenario:
        for (p, acc), kind in probe_scenario.items():
            SCENARIO.set(p, acc, kind)

    # 临时工作目录（避免污染真项目的 filter_progress.json）
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            # 写个 config.json 给 FakeAccountManager
            with open('config.json', 'w') as f:
                json.dump({'accounts': [], 'rate_limit': {'min_delay': 0, 'max_delay': 0,
                                                           'requests_per_account': 100,
                                                           'error_cooldown': 1}}, f)

            install_fakes()
            # 必须在 install_fakes 之后 import，确保没被污染
            import importlib
            import gui_monitor
            importlib.reload(gui_monitor)

            # patch config_path 指向当前临时目录
            gui_monitor.config_path = os.path.join(tmpdir, 'config.json')

            # 构造 FilterThread（不 start，只直接跑 filter_task）
            from PyQt5.QtCore import QCoreApplication
            app = QCoreApplication.instance() or QCoreApplication(sys.argv)

            ft = gui_monitor.FilterThread(phones, 'US', {'rate_limit': {'min_delay': 0, 'max_delay': 0,
                                                                         'requests_per_account': 100,
                                                                         'error_cooldown': 1}},
                                           probe_interval, probe_phones or [])

            # 注入备用号（如果指定）
            if backups:
                # 替换掉 filter_task 里即将创建的 manager：
                # 改 install_fakes 后的 FakeAccountManager 默认账号
                original_init = gui_monitor.AccountManager.__init__ if hasattr(gui_monitor, 'AccountManager') else None
                def patched_init(self, config_path):
                    self.config_path = config_path
                    self.accounts = [
                        {'name': 'A', 'runtime_state': 'active', 'role': 'primary', 'client': object()},
                        {'name': 'B', 'runtime_state': 'active', 'role': 'primary', 'client': object()},
                        {'name': 'C', 'runtime_state': 'active', 'role': 'primary', 'client': object()},
                    ]
                    for bname in backups:
                        self.accounts.append({'name': bname, 'runtime_state': 'standby', 'role': 'backup', 'client': object()})
                    self.paused = set()
                import account_manager as am_mod
                am_mod.AccountManager.__init__ = patched_init
            # 收集日志（不连 Qt 槽，用 monkey-patch）
            logs = []
            ft.log_signal = types.SimpleNamespace(emit=lambda s: logs.append(s))
            ft.status_signal = types.SimpleNamespace(emit=lambda s: None)
            ft.probe_anomaly_signal = types.SimpleNamespace(emit=lambda *a: logs.append(f'PROBE_ANOMALY:{a}'))
            ft.conflict_signal = types.SimpleNamespace(emit=lambda s: None)
            ft.emergency_pause_signal = types.SimpleNamespace(emit=lambda s: None)

            await ft.filter_task()

            # 检查进度文件
            progress = None
            if os.path.exists('filter_progress.json'):
                with open('filter_progress.json') as f:
                    progress = json.load(f)

            print(f"\n==== [{name}] ====")
            for l in logs[-15:]:
                print('  ', l)
            print(f"最终日志条数: {len(logs)}")
            if progress:
                print(f"进度文件保留，processed={progress.get('next_index')}")
            else:
                print("进度文件已清除（正常结束）")
            return logs, progress
        finally:
            os.chdir(old_cwd)


async def main():
    random.seed(42)

    # Case 1: 正常 10 个号，无探针
    logs, prog = await run_case('正常 10 号', [f'+1{i:09d}' for i in range(10)])
    assert prog is None, "正常跑完后进度应清除"
    registered = sum(1 for l in logs if '✅ 已注册' in l)
    unregistered = sum(1 for l in logs if '❌ 未注册' in l)
    print(f"  registered={registered}, unregistered={unregistered}")
    assert registered + unregistered == 10, f"处理数不对: {registered}+{unregistered}"

    # Case 2: 单账号探针连续失败 → 暂停该账号，其他继续
    probe_scenario = {
        ('+probe1', 'A'): 'unregistered',  # A 探针每次都挂
        ('+probe1', 'B'): 'registered',
        ('+probe1', 'C'): 'registered',
    }
    logs, prog = await run_case(
        '单账号探针异常',
        [f'+2{i:09d}' for i in range(30)],
        probe_interval=5,
        probe_phones=['+probe1'],
        probe_scenario=probe_scenario,
    )
    paused_line = [l for l in logs if '已暂停该账号' in l]
    anomaly_line = [l for l in logs if 'PROBE_ANOMALY' in l]
    print(f"  暂停日志: {len(paused_line)} 条, 紧急停止: {len(anomaly_line)}")
    assert len(paused_line) >= 1, "应至少暂停一次"
    assert len(anomaly_line) == 0, "不应触发紧急停止"
    # 应该能跑完所有号
    assert prog is None, f"应当跑完，但 progress={prog}"

    # Case 3: 所有账号探针都挂 → 紧急停止
    probe_scenario = {
        ('+probe2', 'A'): 'unregistered',
        ('+probe2', 'B'): 'unregistered',
        ('+probe2', 'C'): 'unregistered',
    }
    logs, prog = await run_case(
        '全账号探针异常',
        [f'+3{i:09d}' for i in range(40)],
        probe_interval=3,
        probe_phones=['+probe2'],
        probe_scenario=probe_scenario,
    )
    anomaly_line = [l for l in logs if 'PROBE_ANOMALY' in l]
    print(f"  紧急停止信号: {len(anomaly_line)}")
    assert len(anomaly_line) >= 1, "应触发紧急停止"

    # Case 4: 备用号替补 —— 单 primary 探针挂，D 顶上继续跑
    probe_scenario = {
        ('+probe4', 'A'): 'unregistered',
        ('+probe4', 'B'): 'registered',
        ('+probe4', 'C'): 'registered',
        ('+probe4', 'D'): 'registered',  # 备用号探针正常
    }
    logs, prog = await run_case(
        '备用号替补',
        [f'+4{i:09d}' for i in range(30)],
        probe_interval=5,
        probe_phones=['+probe4'],
        probe_scenario=probe_scenario,
        backups=['D', 'E'],
    )
    promote_line = [l for l in logs if '已接替' in l]
    anomaly_line = [l for l in logs if 'PROBE_ANOMALY' in l]
    print(f"  替补日志: {len(promote_line)} 条, 紧急停止: {len(anomaly_line)}")
    assert len(promote_line) >= 1, "应至少替补一次"
    assert len(anomaly_line) == 0, "不应触发紧急停止"
    assert prog is None, f"应当跑完，但 progress={prog}"

    # Case 5: 全部 primary 挂 + 足够多备用 → 依次替补跑完
    probe_scenario = {
        ('+probe5', 'A'): 'unregistered',
        ('+probe5', 'B'): 'unregistered',
        ('+probe5', 'C'): 'unregistered',
        ('+probe5', 'D'): 'registered',
        ('+probe5', 'E'): 'registered',
        ('+probe5', 'F'): 'registered',
    }
    logs, prog = await run_case(
        '全primary挂+备用够用',
        [f'+5{i:09d}' for i in range(40)],
        probe_interval=4,
        probe_phones=['+probe5'],
        probe_scenario=probe_scenario,
        backups=['D', 'E', 'F'],
    )
    promote_line = [l for l in logs if '已接替' in l]
    anomaly_line = [l for l in logs if 'PROBE_ANOMALY' in l]
    print(f"  替补次数: {len(promote_line)}, 紧急停止: {len(anomaly_line)}")
    assert len(promote_line) >= 1, "应至少替补一次"

    # Case 6: 全部 primary 挂 + 备用也全挂 → 替补耗尽后紧急停止
    probe_scenario = {
        ('+probe6', 'A'): 'unregistered',
        ('+probe6', 'B'): 'unregistered',
        ('+probe6', 'C'): 'unregistered',
        ('+probe6', 'D'): 'unregistered',
    }
    logs, prog = await run_case(
        '全挂+备用不够',
        [f'+6{i:09d}' for i in range(50)],
        probe_interval=3,
        probe_phones=['+probe6'],
        probe_scenario=probe_scenario,
        backups=['D'],
    )
    promote_line = [l for l in logs if '已接替' in l]
    anomaly_line = [l for l in logs if 'PROBE_ANOMALY' in l]
    print(f"  替补次数: {len(promote_line)}, 紧急停止: {len(anomaly_line)}")
    assert len(promote_line) >= 1, "应先尝试替补"
    assert len(anomaly_line) >= 1, "替补也挂后应紧急停止"

    print("\n✅ 全部模拟通过")


if __name__ == '__main__':
    asyncio.run(main())
