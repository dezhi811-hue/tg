"""批次一 + 批次二改动的模拟测试。

覆盖：
1. build_proxy_config 6 元组 + rdns + 空串→None
2. resolve_device_profile 账号间差异 + 同名稳定
3. AccountManager.mark_account_error FloodWait 指数退避
4. TelegramFilter:
   - 空返路径也 mark_account_used（bug A3）
   - InputPhoneContact client_id / first_name 随机化（B2）
   - ResolvePhoneRequest 开关（B8）
   - 静默读按间隔触发（B9）
   - 周期 ResetSavedRequest（B7+）
   - DeleteContactsRequest 命中后被调用（已有）
5. load_config fallback 值（gui_monitor）
"""
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

ROOT = '/Volumes/waijie/tg'
sys.path.insert(0, ROOT)


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# -------------------------------------------------------------------
# 1. build_proxy_config
# -------------------------------------------------------------------
def test_build_proxy_config():
    section("TEST 1: build_proxy_config")
    from account_manager import build_proxy_config

    # 空/未配置
    assert build_proxy_config(None) is None, "None 应该直连"
    assert build_proxy_config({}) is None, "空 dict 应该直连"
    assert build_proxy_config({"host": ""}) is None, "空 host 应该直连"
    print("✅ 无 host 返回 None")

    # 标准配置
    r = build_proxy_config({"host": "1.2.3.4", "port": 1080})
    assert r[0] == 'socks5', f"type 应为 socks5，实际 {r[0]}"
    assert r[1] == "1.2.3.4"
    assert r[2] == 1080 and isinstance(r[2], int), f"port 应为 int: {r[2]} ({type(r[2])})"
    assert r[3] is True, "rdns 必须为 True"
    assert r[4] is None and r[5] is None, "空串 username/password 应变为 None"
    print("✅ 6 元组结构正确：('socks5', host, port, rdns=True, None, None)")

    # 端口字符串也能处理
    r2 = build_proxy_config({"host": "1.2.3.4", "port": "1080"})
    assert r2[2] == 1080
    print("✅ 字符串 port 会转 int")

    # 有认证
    r3 = build_proxy_config({"host": "h", "port": 1, "username": "u", "password": "p"})
    assert r3[4] == "u" and r3[5] == "p"
    print("✅ 认证凭据正确传递")


# -------------------------------------------------------------------
# 2. resolve_device_profile
# -------------------------------------------------------------------
def test_resolve_device_profile():
    section("TEST 2: resolve_device_profile")
    from account_manager import resolve_device_profile

    # 同名两次 → 同一套指纹（稳定性）
    fp1 = resolve_device_profile({"name": "acct_1"})
    fp2 = resolve_device_profile({"name": "acct_1"})
    assert fp1 == fp2, "同名账号两次结果必须完全一致"
    print(f"✅ 稳定：acct_1 → {fp1['device_model']}")

    # 不同名大概率不同（池里 6 套，5 个账号里应出现多种）
    names = [f"acc_{i}" for i in range(10)]
    models = {resolve_device_profile({"name": n})['device_model'] for n in names}
    assert len(models) >= 2, f"10 个账号至少应分到 2 种指纹，实际 {models}"
    print(f"✅ 10 个账号散布在 {len(models)} 种指纹上：{models}")

    # 显式覆盖生效
    fp = resolve_device_profile({
        "name": "x",
        "device_model": "MyCustomDevice",
        "app_version": "99.9"
    })
    assert fp['device_model'] == "MyCustomDevice"
    assert fp['app_version'] == "99.9"
    assert fp['system_version']  # 其他字段仍由池填充
    print("✅ 显式字段优先，未填的从池填充")


# -------------------------------------------------------------------
# 3. AccountManager FloodWait 指数退避
# -------------------------------------------------------------------
def test_exponential_backoff():
    section("TEST 3: FloodWait 指数退避")

    # 构造最小 config 写入临时文件
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump({
        "accounts": [{"name": "a", "api_id": "1", "api_hash": "x", "phone": "+1"}],
        "rate_limit": {"requests_per_account": 50, "min_delay": 1, "max_delay": 2, "error_cooldown": 300}
    }, tmp)
    tmp.close()

    from account_manager import AccountManager
    from telethon.errors import FloodWaitError

    mgr = AccountManager(tmp.name)
    acc = mgr.accounts[0]

    # 构造一个模拟 FloodWaitError（seconds 属性）
    class FakeFlood(FloodWaitError):
        def __init__(self, seconds):
            self.seconds = seconds

    waits = []
    for i in range(5):
        before = datetime.now()
        mgr.mark_account_error(acc, FakeFlood(60))  # 每次原始 60s
        actual_cooldown = (acc['block_until'] - before).total_seconds()
        waits.append(round(actual_cooldown))
        print(f"  第 {i+1} 次 FloodWait(60s) → 实际冷却 {round(actual_cooldown)}s (block_count={acc['block_count']})")

    # 第 1 次 60×1=60, 第 2 次 60×2=120, 第 3 次 60×4=240, 第 4 次 60×8=480, 第 5 次 60×16=960
    assert waits[0] < waits[1] < waits[2] < waits[3] < waits[4], "冷却必须单调递增"
    assert waits[1] >= 2 * waits[0] - 2, "第 2 次应接近第 1 次的 2 倍"
    assert waits[2] >= 2 * waits[1] - 2
    print("✅ 指数退避生效，冷却随 block_count 单调增长")

    # 封顶 2 小时
    acc['block_count'] = 20  # 人为拉高
    mgr.mark_account_error(acc, FakeFlood(600))
    cooldown = (acc['block_until'] - datetime.now()).total_seconds()
    assert cooldown <= 2 * 3600 + 2, f"封顶应为 7200s，实际 {cooldown}"
    print(f"✅ 封顶 2 小时：block_count=20 时冷却 {int(cooldown)}s")

    os.unlink(tmp.name)


# -------------------------------------------------------------------
# 4. TelegramFilter 核心路径
# -------------------------------------------------------------------
class _FakeLimiter:
    async def wait_before_request(self): pass


class _FakeManager:
    def __init__(self, account):
        self._acc = account
        self.used = 0
        self.errored = 0
        self.succeeded = 0

    def get_next_account(self): return self._acc
    def mark_account_used(self, a): self.used += 1
    def mark_account_success(self, a): self.succeeded += 1
    def mark_account_error(self, a, e=None): self.errored += 1


def _make_fake_client(behavior):
    """behavior: 'hit' / 'empty' / 'flood' / 'hit_once_then_empty'"""
    client = AsyncMock()
    calls = {'n': 0, 'delete_contacts': 0, 'reset_saved': 0, 'get_dialogs': 0, 'resolve_phone': 0}
    last_contact = {}

    def make_user():
        u = MagicMock()
        u.id = 12345
        u.username = 'target'
        u.first_name = 'Target'
        u.last_name = ''
        u.bot = False
        u.status = None  # UserStatusEmpty-ish
        return u

    async def side_effect(req):
        from telethon.tl.functions.contacts import (
            ImportContactsRequest, DeleteContactsRequest, ResetSavedRequest, ResolvePhoneRequest
        )
        from telethon.tl.functions.messages import GetDialogsRequest

        if isinstance(req, ImportContactsRequest):
            calls['n'] += 1
            # 记录最后一次 InputPhoneContact 供断言
            last_contact['c'] = req.contacts[0]
            if behavior == 'hit':
                r = MagicMock(); r.users = [make_user()]; return r
            if behavior == 'empty':
                r = MagicMock(); r.users = []; return r
            if behavior == 'flood':
                from telethon.errors import FloodWaitError
                class FE(FloodWaitError):
                    def __init__(self):
                        self.seconds = 30
                raise FE()
            if behavior == 'hit_once_then_empty':
                if calls['n'] == 1:
                    r = MagicMock(); r.users = [make_user()]; return r
                r = MagicMock(); r.users = []; return r
        if isinstance(req, DeleteContactsRequest):
            calls['delete_contacts'] += 1
            return MagicMock()
        if isinstance(req, ResetSavedRequest):
            calls['reset_saved'] += 1
            return MagicMock()
        if isinstance(req, GetDialogsRequest):
            calls['get_dialogs'] += 1
            return MagicMock()
        if isinstance(req, ResolvePhoneRequest):
            calls['resolve_phone'] += 1
            if behavior == 'hit':
                r = MagicMock(); r.users = [make_user()]; return r
            r = MagicMock(); r.users = []; return r
        return MagicMock()

    client.side_effect = side_effect
    # 让 client(req) 同步调用 await
    async def call(req):
        return await side_effect(req)
    client.__call__ = call
    client.side_effect = side_effect
    # Telethon client 本身是 Callable 对象：await client(Request(...))
    # 用一个 wrapper 让它可调用且可 await
    return client, calls, last_contact


async def test_filter_hit_path():
    section("TEST 4a: Import 命中路径")
    from filter import TelegramFilter

    client, calls, last_contact = _make_fake_client('hit')
    account = {'client': client, 'name': 'a', 'request_count': 0}
    mgr = _FakeManager(account)

    f = TelegramFilter(mgr, _FakeLimiter(), {'rate_limit': {
        'silent_read_interval': 3,
        'reset_contacts_interval': 5,
    }})

    result = await f.check_phone('+12025551234', country='US')
    assert result['registered'] is True, f"命中应为 True: {result}"
    assert result['user_id'] == 12345
    assert mgr.used == 1 and mgr.succeeded == 1
    assert calls['n'] == 1, "ImportContactsRequest 应调用 1 次"
    assert calls['delete_contacts'] == 1, "命中后必须立即 DeleteContactsRequest"

    # 验证 client_id 和 first_name 随机化
    c = last_contact['c']
    assert c.client_id != 0, f"client_id 不应是静态 0: {c.client_id}"
    assert c.first_name != 'User', f"first_name 不应是静态 'User': {c.first_name}"
    print(f"✅ 命中路径：registered, 随机 client_id={c.client_id}, first_name={c.first_name}")
    print(f"✅ DeleteContactsRequest 被调用 {calls['delete_contacts']} 次")


async def test_filter_empty_path_marks_used():
    section("TEST 4b: 空返路径必须 mark_account_used (bug A3)")
    from filter import TelegramFilter

    client, calls, _ = _make_fake_client('empty')
    account = {'client': client, 'name': 'a', 'request_count': 0}
    mgr = _FakeManager(account)
    f = TelegramFilter(mgr, _FakeLimiter(), {'rate_limit': {}})

    result = await f.check_phone('+12025551234', country='US')
    assert result['registered'] is False
    assert result['query_state'] == 'empty_result'
    assert mgr.used == 1, f"⚠️ 空返也必须 mark_account_used，实际 used={mgr.used}"
    print(f"✅ 空返 → mark_account_used 调用 {mgr.used} 次（修复前 = 0，会死循环）")


async def test_filter_silent_read():
    section("TEST 4c: 静默读按间隔触发 (B9)")
    from filter import TelegramFilter

    client, calls, _ = _make_fake_client('hit')
    account = {'client': client, 'name': 'a', 'request_count': 0}
    mgr = _FakeManager(account)

    # 每 3 次触发一次静默读
    f = TelegramFilter(mgr, _FakeLimiter(), {'rate_limit': {
        'silent_read_interval': 3,
        'reset_contacts_interval': 1000,  # 避免 reset 干扰
    }})

    for i in range(6):
        # 手动模拟 request_count 递增（真正模拟全流程）
        account['request_count'] = i + 1  # 先给 mark_account_used 再运行
        # 但 _check_with_manager 里 mark_account_used 会再 +1... 这里简化：直接调查，让 FakeManager.used 控制
        # 实际 filter.py 里 _maybe_silent_read 用的是 account['request_count']
        # 由于 FakeManager.mark_account_used 不改 request_count，我们手动改
    # 重置，走完整流程
    calls['get_dialogs'] = 0
    account['request_count'] = 0
    orig_mark_used = mgr.mark_account_used
    def mark_and_inc(a):
        orig_mark_used(a)
        a['request_count'] += 1
    mgr.mark_account_used = mark_and_inc

    for i in range(7):
        await f.check_phone('+12025551234', country='US')

    # 在 request_count=3 和 6 时应各触发一次
    assert calls['get_dialogs'] == 2, f"静默读应触发 2 次 (count=3,6)，实际 {calls['get_dialogs']}"
    print(f"✅ 静默读：7 次查询中 request_count=3,6 时触发，共 {calls['get_dialogs']} 次")


async def test_filter_reset_saved():
    section("TEST 4d: 周期 ResetSavedRequest (B7+)")
    from filter import TelegramFilter

    client, calls, _ = _make_fake_client('hit')
    account = {'client': client, 'name': 'a', 'request_count': 0}
    mgr = _FakeManager(account)
    f = TelegramFilter(mgr, _FakeLimiter(), {'rate_limit': {
        'silent_read_interval': 1000,
        'reset_contacts_interval': 4,
    }})

    def mark_and_inc(a):
        a['request_count'] += 1
    mgr.mark_account_used = mark_and_inc

    for _ in range(9):
        await f.check_phone('+12025551234', country='US')
    # count=4,8 时应 reset
    assert calls['reset_saved'] == 2, f"应在 count=4,8 触发 2 次，实际 {calls['reset_saved']}"
    print(f"✅ 周期清联系人簿：9 次查询触发 {calls['reset_saved']} 次 ResetSavedRequest")


async def test_filter_resolve_phone_toggle():
    section("TEST 4e: use_resolve_phone 开关 (B8)")
    from filter import TelegramFilter

    client, calls, _ = _make_fake_client('hit')
    account = {'client': client, 'name': 'a', 'request_count': 0}
    mgr = _FakeManager(account)

    # 开启 resolve_phone
    f = TelegramFilter(mgr, _FakeLimiter(), {'rate_limit': {'use_resolve_phone': True}})
    await f.check_phone('+12025551234', country='US')
    assert calls['resolve_phone'] == 1, f"应走 ResolvePhoneRequest: {calls}"
    assert calls['n'] == 0, "开关开时不应调 ImportContactsRequest"
    assert calls['delete_contacts'] == 0, "Resolve 路径不入联系人簿，不需要 Delete"
    print(f"✅ use_resolve_phone=true：走 Resolve (1) 而非 Import (0)，无需 Delete")


async def test_filter_flood():
    section("TEST 4f: FloodWait 路径 mark_account_error 且不 mark_used")
    from filter import TelegramFilter

    client, calls, _ = _make_fake_client('flood')
    account = {'client': client, 'name': 'a', 'request_count': 0}
    mgr = _FakeManager(account)
    f = TelegramFilter(mgr, _FakeLimiter(), {'rate_limit': {}})

    result = await f.check_phone('+12025551234', country='US')
    assert result['query_state'] == 'rate_limited', f"state={result['query_state']}"
    assert mgr.errored == 1
    assert mgr.used == 0, "FloodWait 路径不应 mark_used"
    print(f"✅ FloodWait → mark_error=1, mark_used=0")


# -------------------------------------------------------------------
# 5. load_config fallback
# -------------------------------------------------------------------
def test_load_config_fallback():
    section("TEST 5: gui_monitor.load_config fallback 值")
    import gui_monitor
    # 临时指向不存在的 config 触发 fallback
    saved = gui_monitor.config_path
    gui_monitor.config_path = "/nonexistent_path_for_test.json"
    try:
        cfg = gui_monitor.load_config()
    finally:
        gui_monitor.config_path = saved

    rl = cfg['rate_limit']
    assert rl['min_delay'] == 20, f"min_delay fallback 应为 20，实际 {rl['min_delay']}"
    assert rl['max_delay'] == 30, f"max_delay fallback 应为 30，实际 {rl['max_delay']}"
    print(f"✅ fallback：min={rl['min_delay']}, max={rl['max_delay']}（之前是 3/8）")


# -------------------------------------------------------------------
# 6. 常量一致性：三处冷却都是 10 分钟
# -------------------------------------------------------------------
def test_cooldown_unified():
    section("TEST 6: 三处探针/上限冷却统一为 10 分钟")
    from gui_monitor import FilterThread
    assert FilterThread.EMPTY_PROBE_COOLDOWN_SEC == 600
    print(f"✅ EMPTY_PROBE_COOLDOWN_SEC = {FilterThread.EMPTY_PROBE_COOLDOWN_SEC}s")

    # 源码层面搜索 error_cooldown 是否已全部被替换
    with open(os.path.join(ROOT, 'gui_monitor.py')) as f:
        src = f.read()
    # 允许出现在 config 读取和默认声明里，但 worker_loop 单号上限 + probe_loop 两处必须是 EMPTY_PROBE_COOLDOWN_SEC
    import re
    # 找 "cooldown = " 后面立即跟的变量
    cooldown_assignments = re.findall(r'cooldown\s*=\s*(.+?)$', src, re.MULTILINE)
    bad = [c for c in cooldown_assignments if 'error_cooldown' in c]
    assert not bad, f"仍有 cooldown 用 error_cooldown 的赋值：{bad}"
    print(f"✅ 代码里所有 cooldown 赋值均未使用 error_cooldown 直取（共 {len(cooldown_assignments)} 处赋值）")


async def run_all():
    test_build_proxy_config()
    test_resolve_device_profile()
    test_exponential_backoff()
    await test_filter_hit_path()
    await test_filter_empty_path_marks_used()
    await test_filter_silent_read()
    await test_filter_reset_saved()
    await test_filter_resolve_phone_toggle()
    await test_filter_flood()
    test_load_config_fallback()
    test_cooldown_unified()
    print("\n" + "=" * 60)
    print("🎉 全部测试通过")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(run_all())
