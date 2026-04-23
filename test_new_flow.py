"""模拟：连续空返回 → 定向探针 → 冷却 10min → 复验的新链路。
复用 test_sim_v3 的 Fake 基础设施，把冷却时长 patch 成 1 秒以便测试。"""
import asyncio
import importlib
import json
import os
import random
import sys
import tempfile
import types

sys.path.insert(0, '/Volumes/waijie/tg')
import test_sim_v3 as sim


async def run(name, phones, probe_phones, scenario_map, consecutive_trigger=5, cooldown_sec=1):
    # scenario_map: {(phone, account): kind}
    sim.SCENARIO = sim.Scenario()
    sim.call_log = []
    for (p, a), k in scenario_map.items():
        sim.SCENARIO.set(p, a, k)

    rate_limit = {'min_delay': 0, 'max_delay': 0,
                  'requests_per_account': 1000, 'error_cooldown': cooldown_sec}

    with tempfile.TemporaryDirectory() as tmpdir:
        cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            with open('config.json', 'w') as f:
                json.dump({'accounts': [], 'rate_limit': rate_limit}, f)
            sim.install_fakes()
            import gui_monitor
            importlib.reload(gui_monitor)
            gui_monitor.config_path = os.path.join(tmpdir, 'config.json')
            # Patch 常量，加速测试
            gui_monitor.FilterThread.CONSECUTIVE_EMPTY_TRIGGER = consecutive_trigger
            gui_monitor.FilterThread.EMPTY_PROBE_COOLDOWN_SEC = cooldown_sec

            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.instance() or QCoreApplication(sys.argv)

            ft = gui_monitor.FilterThread(phones, 'US',
                                          {'rate_limit': rate_limit},
                                          probe_interval=0,  # 关掉周期探针，只测空返探针
                                          probe_phones=probe_phones)
            logs = []
            snaps = []
            ft.log_signal = types.SimpleNamespace(emit=lambda s: logs.append(s))
            ft.status_signal = types.SimpleNamespace(emit=lambda s: snaps.append(s))
            ft.probe_anomaly_signal = types.SimpleNamespace(emit=lambda *a: logs.append(f'ANOMALY:{a}'))
            ft.conflict_signal = types.SimpleNamespace(emit=lambda s: None)
            ft.emergency_pause_signal = types.SimpleNamespace(emit=lambda s: None)

            await ft.filter_task()
            print(f"\n==== [{name}] ====")
            return logs, snaps[-1] if snaps else {}
        finally:
            os.chdir(cwd)


async def main():
    random.seed(7)

    # ===== Case A: 全未注册但账号健康 =====
    # 5 worker，每个至少处理 5 个未注册 → 触发空返探针
    # 探针号对所有账号 registered → 命中，不冷却
    phones = [f'+700000{i:04d}' for i in range(50)]  # 50 个全 unreg（号尾 0-9 奇偶决定，改成全 unreg）
    scenario = {}
    # 让所有业务号返回 unregistered
    for p in phones:
        for acc in ['A', 'B', 'C', 'D', 'E']:
            scenario[(p, acc)] = 'unregistered'
    # 探针号对所有账号 registered
    for acc in ['A', 'B', 'C', 'D', 'E']:
        scenario[('+probe_ok', acc)] = 'registered'

    logs, snap = await run('健康账号空返命中', phones, ['+probe_ok'], scenario,
                           consecutive_trigger=5, cooldown_sec=1)
    trig = [l for l in logs if '触发定向探针' in l]
    hit = [l for l in logs if '定向探针命中' in l]
    miss_cooldown = [l for l in logs if '确认异常，停' in l]
    print(f"  空返触发探针: {len(trig)} 次")
    print(f"  探针命中（账号正常）: {len(hit)} 次")
    print(f"  探针未命中冷却: {len(miss_cooldown)} 次")
    block_counts = {n: s.get('block_count', 0) for n, s in snap.items()}
    print(f"  各号封禁数: {block_counts}")
    assert len(trig) >= 3, f"5 worker × 10 未注册 / 阈值 5 应至少触发 3 次探针，实际 {len(trig)}"
    assert len(hit) == len(trig), f"健康账号应全部探针命中（{len(hit)}/{len(trig)}）"
    assert len(miss_cooldown) == 0, "健康账号不应被冷却"
    assert sum(block_counts.values()) == 0, "封禁数应为 0"

    # ===== Case B: 账号 D 持续异常（号 + 探针都 unregistered）=====
    # 空返触发 → 探针失败 → 冷却 → 复验仍失败 → 再冷却
    phones = [f'+800000{i:04d}' for i in range(100)]
    scenario = {}
    for p in phones:
        for acc in ['A', 'B', 'C', 'D', 'E']:
            # D 号什么都查不到；其他号按号尾奇偶
            if acc == 'D':
                scenario[(p, acc)] = 'unregistered'
            else:
                last = int(p[-1])
                scenario[(p, acc)] = 'registered' if last % 2 == 0 else 'unregistered'
    # 探针号：D 查不到（已确诊异常），其他健康
    for acc in ['A', 'B', 'C', 'E']:
        scenario[('+probe_bad', acc)] = 'registered'
    scenario[('+probe_bad', 'D')] = 'unregistered'

    logs, snap = await run('异常账号 D 冷却+复验', phones, ['+probe_bad'], scenario,
                           consecutive_trigger=5, cooldown_sec=1)
    d_trig = [l for l in logs if 'D 连续' in l and '触发定向探针' in l]
    d_miss = [l for l in logs if 'D 确认异常，停' in l]
    d_recheck = [l for l in logs if 'D 冷却结束，复验探针' in l]
    d_recheck_miss = [l for l in logs if 'D 仍异常' in l]
    d_recheck_hit = [l for l in logs if 'D 恢复筛号' in l]
    print(f"  D 触发空返探针: {len(d_trig)}")
    print(f"  D 探针未命中 → 冷却: {len(d_miss)}")
    print(f"  D 冷却结束复验: {len(d_recheck)}")
    print(f"  D 复验仍异常 → 再冷却: {len(d_recheck_miss)}")
    print(f"  D 复验命中 → 恢复: {len(d_recheck_hit)}")
    d_block = snap.get('D', {}).get('block_count', 0)
    print(f"  D 封禁数: {d_block}")
    other_blocks = {k: snap.get(k, {}).get('block_count', 0) for k in ['A','B','C','E']}
    print(f"  其他号封禁数: {other_blocks}")

    assert len(d_trig) >= 1, "D 应至少触发 1 次空返探针"
    assert len(d_miss) >= 1, "D 第一次探针应未命中进入冷却"
    assert len(d_recheck) >= 1, "冷却结束必须复验一次"
    assert len(d_recheck_miss) >= 1, "复验仍应失败进入再冷却"
    assert len(d_recheck_hit) == 0, "D 场景下复验不会命中"
    assert d_block >= 2, f"D 应至少冷却 2 次（初次 + 复验）实际 {d_block}"
    for k, v in other_blocks.items():
        assert v == 0, f"其他号不应被冷却：{k}={v}"

    print("\n✅ 新流程模拟全部通过")


if __name__ == '__main__':
    asyncio.run(main())
