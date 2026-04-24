"""M1 号池基础类单元测试。

覆盖：
- 迁移：老 config 自动建 state.json
- 状态转换：active/cooling/retired/warmup
- 日配额：达标自动冷却到次日
- 健康分阈值：低于 threshold 自动降级
- FloodWait 24h 滑窗累计熔断 + 单次长 FW 立即退役
- 永久限制（PEER_FLOOD 等）立即退役
- compute_concurrency = default_concurrency(N_active)
- 代理 provider 指纹 + sticky session
- 空返探针阈值
"""
import json
import os
import tempfile
import time
import unittest

from account_pool import (
    AccountPool,
    STATE_ACTIVE, STATE_WARMUP, STATE_COOLING, STATE_RETIRED,
    default_concurrency, daily_quota,
    provider_fingerprint, build_sticky_proxy_user, build_sticky_proxy_for,
    _extract_region, _extract_sub_user_prefix,
)


def _write_config(dir_, accounts=None, pool_config=None):
    cfg = {
        'accounts': accounts or [
            {'name': 'acc001', 'api_id': '1', 'api_hash': 'h', 'phone': '+1'},
            {'name': 'acc002', 'api_id': '1', 'api_hash': 'h', 'phone': '+1'},
            {'name': 'acc003', 'api_id': '1', 'api_hash': 'h', 'phone': '+1'},
        ],
        'rate_limit': {'requests_per_account': 30, 'min_delay': 25, 'max_delay': 45,
                       'error_cooldown': 60},
    }
    if pool_config is not None:
        cfg['pool_config'] = pool_config
    p = os.path.join(dir_, 'config.json')
    with open(p, 'w') as f:
        json.dump(cfg, f)
    return p


class TestConcurrency(unittest.TestCase):
    def test_default_concurrency(self):
        self.assertEqual(default_concurrency(0), 0)
        self.assertEqual(default_concurrency(1), 1)
        self.assertEqual(default_concurrency(5), 5)
        self.assertEqual(default_concurrency(20), 5)
        self.assertEqual(default_concurrency(50), 6)
        self.assertEqual(default_concurrency(100), 12)
        self.assertEqual(default_concurrency(200), 16)

    def test_daily_quota(self):
        self.assertEqual(daily_quota(0), 25)
        self.assertEqual(daily_quota(2), 25)
        self.assertEqual(daily_quota(5), 50)
        self.assertEqual(daily_quota(10), 80)
        self.assertEqual(daily_quota(20), 120)
        self.assertEqual(daily_quota(60), 150)


class TestProxy(unittest.TestCase):
    def test_region_and_prefix_extract(self):
        u = 'gdggxfzrk51113-region-US-sid-FNVUBKrn-t-5'
        self.assertEqual(_extract_region(u), 'US')
        self.assertEqual(_extract_sub_user_prefix(u), 'gdggxfzrk51113')

    def test_provider_fingerprint_stable_on_session_change(self):
        p1 = {'host': 'us-eu.fluxisp.com', 'port': 5000,
              'username': 'gdggxfzrk-region-US-sid-AAA', 'password': 'x'}
        p2 = {'host': 'us-eu.fluxisp.com', 'port': 5000,
              'username': 'gdggxfzrk-region-US-sid-BBB', 'password': 'x'}
        self.assertEqual(provider_fingerprint(p1), provider_fingerprint(p2))

    def test_provider_fingerprint_differs_on_region_change(self):
        p1 = {'host': 'h', 'port': 1, 'username': 'u-region-US'}
        p2 = {'host': 'h', 'port': 1, 'username': 'u-region-EU'}
        self.assertNotEqual(provider_fingerprint(p1), provider_fingerprint(p2))

    def test_sticky_user_injected(self):
        self.assertIn('-session-', build_sticky_proxy_user('acc001', 'base-region-US'))

    def test_sticky_user_not_double_injected(self):
        u = 'base-region-US-session-XYZ'
        self.assertEqual(build_sticky_proxy_user('acc001', u), u)

    def test_build_sticky_proxy_for(self):
        base = {'host': 'h', 'port': 1, 'username': 'u-region-US', 'password': 'p'}
        out = build_sticky_proxy_for({'name': 'acc001'}, base)
        self.assertIn('-session-', out['username'])
        self.assertEqual(out['host'], 'h')
        self.assertEqual(out['password'], 'p')


class TestAccountPool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg_path = _write_config(self.tmp)
        self.state_path = os.path.join(self.tmp, 'state.json')
        self.pool = AccountPool(self.cfg_path, self.state_path)

    def test_migration_creates_state(self):
        self.assertTrue(os.path.exists(self.state_path))
        self.assertEqual(len(self.pool.state), 3)
        for name in ('acc001', 'acc002', 'acc003'):
            self.assertEqual(self.pool.state[name]['state'], STATE_ACTIVE)

    def test_get_active_batch(self):
        batch = self.pool.get_active_batch(3)
        self.assertEqual(set(batch), {'acc001', 'acc002', 'acc003'})

    def test_compute_concurrency(self):
        self.assertEqual(self.pool.compute_concurrency(), 3)

    def test_mark_cooling_removed_from_batch(self):
        self.pool.mark_cooling('acc001', duration_sec=3600, reason='test')
        batch = self.pool.get_active_batch(10)
        self.assertNotIn('acc001', batch)

    def test_mark_retired_removed_permanently(self):
        self.pool.mark_retired('acc001', reason='test')
        self.assertNotIn('acc001', self.pool.get_active_batch(10))
        self.pool.tick()
        self.assertNotIn('acc001', self.pool.get_active_batch(10))

    def test_record_request_increments(self):
        self.pool.record_request('acc001', success=True, api_name='ImportContactsRequest')
        e = self.pool.get_entry('acc001')
        self.assertEqual(e['total_requests'], 1)
        self.assertEqual(e['today_requests'], 1)
        self.assertEqual(e['today_api_calls'].get('ImportContactsRequest'), 1)

    def test_daily_quota_exhausted_cools(self):
        # 新号默认 age < 3 days → 配额 25
        for _ in range(25):
            self.pool.record_request('acc001', success=True)
        batch = self.pool.get_active_batch(10)
        self.assertNotIn('acc001', batch)
        self.assertEqual(self.pool.state['acc001']['state'], STATE_COOLING)

    def test_floodwait_accumulation_retires(self):
        for _ in range(3):
            self.pool.record_floodwait('acc001', 10)
        self.assertEqual(self.pool.state['acc001']['state'], STATE_RETIRED)

    def test_floodwait_long_single_retires(self):
        self.pool.record_floodwait('acc001', 400)
        self.assertEqual(self.pool.state['acc001']['state'], STATE_RETIRED)

    def test_permanent_limit_retires(self):
        self.pool.record_permanent_limit('acc001', 'PEER_FLOOD')
        self.assertEqual(self.pool.state['acc001']['state'], STATE_RETIRED)
        self.assertEqual(self.pool.state['acc001']['retired_reason'], 'peer_flood')

    def test_empty_probe_threshold(self):
        # 默认阈值 30
        for _ in range(29):
            self.pool.record_empty_return('acc001')
        self.assertEqual(self.pool.state['acc001']['state'], STATE_ACTIVE)
        self.pool.record_empty_return('acc001')
        self.assertEqual(self.pool.state['acc001']['state'], STATE_COOLING)

    def test_bind_proxy_first_time(self):
        p = {'host': 'h', 'port': 1, 'username': 'u-region-US'}
        changed, sev, _ = self.pool.bind_proxy('acc001', p)
        self.assertTrue(changed)
        self.assertEqual(sev, 'ok')

    def test_bind_proxy_session_change_silent(self):
        p1 = {'host': 'h', 'port': 1, 'username': 'u-region-US-sid-A'}
        p2 = {'host': 'h', 'port': 1, 'username': 'u-region-US-sid-B'}
        self.pool.bind_proxy('acc001', p1)
        changed, sev, _ = self.pool.bind_proxy('acc001', p2)
        self.assertFalse(changed)
        self.assertEqual(sev, 'ok')

    def test_register_new_account_in_warmup(self):
        self.pool.register_account('newbie', source_type='session')
        self.assertEqual(self.pool.state['newbie']['state'], STATE_WARMUP)

    def test_tdata_health_bonus(self):
        self.pool.register_account('tdata_acc', source_type='tdata')
        base = 80
        self.assertGreater(self.pool.state['tdata_acc']['health_score'], base)

    def test_decoy_call_interval(self):
        self.assertFalse(self.pool.needs_decoy_call('acc001'))
        for _ in range(12):
            self.pool.record_request('acc001', success=True)
        self.assertTrue(self.pool.needs_decoy_call('acc001'))

    def test_state_persists_across_instances(self):
        self.pool.mark_retired('acc001')
        self.pool.save()
        pool2 = AccountPool(self.cfg_path, self.state_path)
        self.assertEqual(pool2.state['acc001']['state'], STATE_RETIRED)


if __name__ == '__main__':
    unittest.main()
