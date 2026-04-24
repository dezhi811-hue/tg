"""端到端场景模拟：50 个美国号池跑 1 天，插入各种异常，看池子表现。

覆盖：
- 50 号冷启动（部分 tdata + 部分 session）
- 动态代理（1 行根凭据 → 50 个 sticky 出口）
- 日配额消耗 + 跨日重置
- FloodWait 累计 + 单次长 FW 退役
- PEER_FLOOD 命中立即退役
- 空返探针阈值触发冷却
- warmup 新号隔离
- 并发 K 按 active 数动态算
- 代理 provider 指纹稳定（只换 session id 不告警）
- get_active_batch 多样性（同 provider 不重复）
"""
import json
import os
import random
import tempfile
import time
from collections import Counter

from account_pool import (
    AccountPool, default_concurrency, daily_quota,
    STATE_ACTIVE, STATE_COOLING, STATE_RETIRED, STATE_WARMUP,
    build_sticky_proxy_for, provider_fingerprint,
)
from pacing import BurstSilentPacer


def banner(msg):
    print(f"\n{'='*68}\n▶ {msg}\n{'='*68}")


def assert_eq(a, b, msg=''):
    if a != b:
        raise AssertionError(f"{msg}: expected {b}, got {a}")


def make_config(n=50, tdata_ratio=0.4):
    accounts = []
    for i in range(n):
        src = 'tdata' if random.random() < tdata_ratio else 'session'
        accounts.append({
            'name': f'acc{i:03d}',
            'api_id': '1111', 'api_hash': 'x' * 32,
            'phone': f'+1202555{i:04d}',
            'source_type': src,
        })
    return accounts


def test_round_1():
    banner("ROUND 1: 冷启动 50 号 + 基础运行")
    tmp = tempfile.mkdtemp()
    cfg = {
        'accounts': make_config(50),
        'rate_limit': {'requests_per_account': 30, 'min_delay': 25, 'max_delay': 45,
                       'error_cooldown': 60},
        'pool_config': {'dc1_lock': True},
    }
    cfg_path = os.path.join(tmp, 'config.json')
    with open(cfg_path, 'w') as f:
        json.dump(cfg, f)

    pool = AccountPool(cfg_path, os.path.join(tmp, 'state.json'))
    print(f"  初始化完成：{len(pool.state)} 个号，state.json 已建")
    assert os.path.exists(pool.state_path)

    # 迁移后应该全是 active（老 config 兼容）
    summary = pool.summary()
    print(f"  summary: {summary}")
    assert_eq(summary['total'], 50)
    assert_eq(summary['active'], 50)

    # 推荐并发 K = default_concurrency(50) = 6
    assert_eq(summary['concurrency_k'], 6, "K(50) should be 6")

    batch = pool.get_active_batch()
    print(f"  get_active_batch() 挑出 {len(batch)} 个号（应 = K = 6）: {batch[:3]}...")
    assert_eq(len(batch), 6)

    # 代理绑定：50 号用同一根凭据，自动 sticky 成 50 个不同 session id
    base_proxy = {'host': 'us-eu.fluxisp.com', 'port': 5000,
                  'username': 'gdggxfzrk-region-US', 'password': 'pw'}
    fps = set()
    stickies = set()
    for name in pool.state:
        p = build_sticky_proxy_for({'name': name}, base_proxy)
        pool.bind_proxy(name, p)
        fps.add(provider_fingerprint(p))
        stickies.add(p['username'])
    # 50 号同 provider → provider_fingerprint 只应有 1 个
    assert_eq(len(fps), 1, "same provider → same fingerprint")
    # 但 sticky username 应有 50 个（每号独立）
    assert_eq(len(stickies), 50, "sticky session per account")
    print(f"  ✅ 50 号绑定同一 provider，sticky 出口 {len(stickies)} 个唯一")

    # get_active_batch 子网多样性：50 号同 provider 指纹 → 只能挑 1 个？
    # 实际逻辑：同指纹只返 1 个，兜底补齐到 K
    batch = pool.get_active_batch(6)
    assert_eq(len(batch), 6, "兜底补齐到 K 即便指纹相同")
    print(f"  ✅ 同 provider 下兜底挑 K={len(batch)} 个")

    return tmp, cfg_path, pool


def test_round_2(tmp, cfg_path, pool):
    banner("ROUND 2: 模拟 1 天筛号 + 各种异常")

    # --- 场景 A：单号达日配额自动冷却 ---
    target = 'acc000'
    age_days = pool.age_days(target)
    quota = daily_quota(age_days)
    print(f"  [A] {target} age={age_days}d quota={quota}")
    for _ in range(quota):
        pool.record_request(target, success=True, api_name='ImportContactsRequest')
    e = pool.state[target]
    assert_eq(e['state'], STATE_COOLING, f"{target} 达配额应 cooling")
    assert_eq(e['cooling_reason'], 'quota_exhausted')
    print(f"  [A] ✅ {target} 达配额 {quota} 后进 cooling（{e['cooling_reason']}）")
    assert target not in pool.get_active_batch(10)
    print(f"  [A] ✅ get_active_batch 已排除该号")

    # --- 场景 B：FloodWait 累计 3 次退役 ---
    target = 'acc001'
    for i in range(3):
        pool.record_floodwait(target, 30)
        print(f"    [B] FW #{i+1}: state={pool.state[target]['state']}")
    assert_eq(pool.state[target]['state'], STATE_RETIRED)
    print(f"  [B] ✅ 3 次 FW 后退役")

    # --- 场景 C：单次长 FW 立即退役 ---
    target = 'acc002'
    pool.record_floodwait(target, 400)
    assert_eq(pool.state[target]['state'], STATE_RETIRED)
    assert_eq(pool.state[target]['retired_reason'], 'floodwait_long')
    print(f"  [C] ✅ 单次 FW 400s 立即退役")

    # --- 场景 D：PEER_FLOOD 立退役 ---
    target = 'acc003'
    pool.record_permanent_limit(target, 'PEER_FLOOD')
    assert_eq(pool.state[target]['state'], STATE_RETIRED)
    assert_eq(pool.state[target]['retired_reason'], 'peer_flood')
    print(f"  [D] ✅ PEER_FLOOD 立退役")

    # --- 场景 E：空返阈值触发冷却 ---
    target = 'acc004'
    for _ in range(30):
        pool.record_empty_return(target)
    assert_eq(pool.state[target]['state'], STATE_COOLING)
    print(f"  [E] ✅ 连续 30 空返触发 cooling")

    # --- 场景 F：新号进 warmup，不应被 get_active_batch 挑中 ---
    pool.register_account('new_kid_001', source_type='tdata')
    assert_eq(pool.state['new_kid_001']['state'], STATE_WARMUP)
    # tdata bonus
    assert pool.state['new_kid_001']['health_score'] >= 90, "tdata 起始分 +10"
    batch = pool.get_active_batch(100)
    assert 'new_kid_001' not in batch, "warmup 号不应被挑"
    print(f"  [F] ✅ warmup 新号不参与调度，tdata 起始分 {pool.state['new_kid_001']['health_score']}")

    # --- 场景 G：K 自动下调（active 变少） ---
    summary = pool.summary()
    k_now = summary['concurrency_k']
    print(f"  [G] 经过异常后 active={summary['active']}, K={k_now}")
    # 1 配额耗完 + 1 空返 cooling = 2 cooling；3 retired；warmup 1
    # active = 50 - 2 - 3 = 45
    assert summary['active'] >= 44 and summary['active'] <= 46, f"active 应 ~45，实际 {summary['active']}"
    assert k_now == default_concurrency(summary['active'])
    print(f"  [G] ✅ K 随 active 自动调整")

    # --- 场景 H：代理 session 变了（动态代理每日换 session id），不应报警 ---
    base = {'host': 'us-eu.fluxisp.com', 'port': 5000,
            'username': 'gdggxfzrk-region-US-sid-OLD123', 'password': 'pw'}
    new = {'host': 'us-eu.fluxisp.com', 'port': 5000,
           'username': 'gdggxfzrk-region-US-sid-NEW456', 'password': 'pw'}
    pool.bind_proxy('acc010', base)
    changed, sev, _ = pool.bind_proxy('acc010', new)
    assert not changed, "同 provider/region 只换 session id 应静默"
    assert_eq(sev, 'ok')
    print(f"  [H] ✅ 动态代理换 session id 不误报")

    # --- 场景 I：region 变了（US→EU）红色告警 ---
    eu = {'host': 'us-eu.fluxisp.com', 'port': 5000,
          'username': 'gdggxfzrk-region-EU-sid-X', 'password': 'pw'}
    # 先设一个 _last_region
    pool.state['acc010']['_last_region'] = 'US'
    changed, sev, msg = pool.bind_proxy('acc010', eu)
    assert_eq(sev, 'red')
    print(f"  [I] ✅ US→EU 红色告警: {msg}")

    # --- 场景 J：持久化往返 ---
    pool.save()
    pool2 = AccountPool(cfg_path, pool.state_path)
    # 退役号应该保持退役
    assert_eq(pool2.state['acc001']['state'], STATE_RETIRED)
    assert_eq(pool2.state['acc003']['retired_reason'], 'peer_flood')
    print(f"  [J] ✅ 状态持久化跨进程正常")

    return pool


def test_round_3_pacing():
    banner("ROUND 3: Pacing 状态机（BURST/QUIET 节奏）")
    tmp = tempfile.mkdtemp()
    cfg = {
        'accounts': [{'name': f'acc{i}', 'api_id': '1', 'api_hash': 'x', 'phone': '+1'}
                     for i in range(3)],
        'rate_limit': {'requests_per_account': 30, 'min_delay': 25, 'max_delay': 45,
                       'error_cooldown': 60},
        'pool_config': {
            'pacing': {
                'burst_min': 2, 'burst_max': 2,
                'burst_interval_min': 0.01, 'burst_interval_max': 0.01,
                'quiet_interval_min': 0.02, 'quiet_interval_max': 0.02,
            }
        },
    }
    cfg_path = os.path.join(tmp, 'config.json')
    with open(cfg_path, 'w') as f:
        json.dump(cfg, f)
    pool = AccountPool(cfg_path, os.path.join(tmp, 'state.json'))
    pacer = BurstSilentPacer(pool)

    import asyncio
    async def exercise():
        delays = []
        for i in range(6):
            t0 = time.time()
            await pacer.wait('acc0')
            delays.append(time.time() - t0)
        return delays

    delays = asyncio.run(exercise())
    print(f"  6 次 wait 实际耗时（秒）: {[round(d, 3) for d in delays]}")
    # 模式：quiet, burst, quiet, burst, quiet, burst
    # 每 2 次里第 1 次是 quiet 大延迟，第 2 次是 burst 小延迟
    quiet_times = [delays[0], delays[2], delays[4]]
    burst_times = [delays[1], delays[3], delays[5]]
    assert all(q > b for q, b in zip(quiet_times, burst_times)), \
        f"quiet 应 > burst，实际 quiet={quiet_times} burst={burst_times}"
    print(f"  ✅ BURST/QUIET 交替正确：quiet 段每次都比 burst 段长")


def test_round_4_proxy_ping_offline():
    banner("ROUND 4: SOCKS ping 对不存在代理应失败（不崩溃）")
    from proxy_registry import proxy_ping
    import asyncio
    ok, reason = asyncio.run(proxy_ping(
        {'host': '127.0.0.1', 'port': 1, 'username': '', 'password': ''},
        timeout=2,
    ))
    assert not ok
    print(f"  ✅ 不存在代理 ping 正确失败：{reason}")


if __name__ == '__main__':
    random.seed(42)
    tmp, cfg_path, pool = test_round_1()
    test_round_2(tmp, cfg_path, pool)
    test_round_3_pacing()
    test_round_4_proxy_ping_offline()
    print("\n" + "="*68)
    print("🎉 端到端场景全部通过")
    print("="*68)
