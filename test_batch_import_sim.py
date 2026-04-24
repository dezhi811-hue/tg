"""batch_import 深度模拟测试。

mock Telethon 的 TelegramClient，覆盖 health_check_account 全部分支，
以及 BatchImportThread 端到端流水线（扫描→json 解析→复制 session→健康检测）。
"""
import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import patch, AsyncMock, MagicMock

ROOT = '/Volumes/waijie/tg'
sys.path.insert(0, ROOT)


def section(t):
    print(f"\n{'=' * 60}\n{t}\n{'=' * 60}")


# -------------------------------------------------------------
# health_check_account 分支覆盖
# -------------------------------------------------------------
def _make_client_factory(behavior, authorized=True):
    """behavior: 'ok' / 'connect_fail' / 'auth_invalid' / 'banned' /
                 'deactivated' / 'phone_banned' / 'unauthorized' /
                 'get_me_fail'"""

    def factory(*args, **kwargs):
        from telethon.errors import (
            AuthKeyUnregisteredError, UserDeactivatedError,
            UserDeactivatedBanError, PhoneNumberBannedError,
        )
        client = MagicMock()

        if behavior == 'connect_fail':
            client.connect = AsyncMock(side_effect=OSError("proxy timeout"))
        else:
            client.connect = AsyncMock(return_value=None)

        # is_user_authorized 分支
        if behavior == 'auth_invalid':
            client.is_user_authorized = AsyncMock(
                side_effect=AuthKeyUnregisteredError(request=None)
            )
        elif behavior == 'banned':
            client.is_user_authorized = AsyncMock(
                side_effect=UserDeactivatedBanError(request=None)
            )
        elif behavior == 'deactivated':
            client.is_user_authorized = AsyncMock(
                side_effect=UserDeactivatedError(request=None)
            )
        elif behavior == 'phone_banned':
            client.is_user_authorized = AsyncMock(
                side_effect=PhoneNumberBannedError(request=None)
            )
        elif behavior == 'unauthorized':
            client.is_user_authorized = AsyncMock(return_value=False)
        else:
            client.is_user_authorized = AsyncMock(return_value=authorized)

        # get_me 分支
        if behavior == 'get_me_fail':
            client.get_me = AsyncMock(
                side_effect=AuthKeyUnregisteredError(request=None)
            )
        else:
            me = MagicMock()
            me.phone = '14125551234'
            me.username = 'alice'
            me.id = 999
            client.get_me = AsyncMock(return_value=me)

        client.disconnect = AsyncMock(return_value=None)
        return client

    return factory


async def _run_hc(behavior, authorized=True):
    from batch_import import health_check_account
    with patch('batch_import.TelegramClient', side_effect=_make_client_factory(behavior, authorized)):
        acc = {'name': 'n', 'api_id': '1', 'api_hash': 'x', 'phone': '+1'}
        return await health_check_account(acc, None, '/tmp/foo', timeout=5)


def test_hc_alive():
    section("TEST A1: health_check alive")
    r = asyncio.run(_run_hc('ok'))
    assert r['status'] == 'alive', r
    assert r['phone'] == '14125551234'
    assert r['username'] == 'alice'
    assert r['user_id'] == 999
    print(f"✅ alive: phone={r['phone']}, @{r['username']}, id={r['user_id']}")


def test_hc_proxy_failed():
    section("TEST A2: health_check proxy_failed")
    r = asyncio.run(_run_hc('connect_fail'))
    assert r['status'] == 'proxy_failed', r
    assert 'proxy timeout' in r['error'] or 'connect' in r['error'].lower()
    print(f"✅ proxy_failed: {r['error']}")


def test_hc_dead_session_auth_invalid():
    section("TEST A3: AUTH_KEY_UNREGISTERED → dead_session")
    r = asyncio.run(_run_hc('auth_invalid'))
    assert r['status'] == 'dead_session', r
    print(f"✅ dead_session (auth_invalid): {r['error']}")


def test_hc_dead_banned():
    section("TEST A4: UserDeactivatedBanError → dead_banned")
    r = asyncio.run(_run_hc('banned'))
    assert r['status'] == 'dead_banned', r
    print(f"✅ dead_banned: {r['error']}")


def test_hc_dead_deactivated():
    section("TEST A5: UserDeactivatedError → dead_deactivated")
    r = asyncio.run(_run_hc('deactivated'))
    assert r['status'] == 'dead_deactivated', r
    print(f"✅ dead_deactivated: {r['error']}")


def test_hc_phone_banned():
    section("TEST A6: PhoneNumberBannedError → dead_banned")
    r = asyncio.run(_run_hc('phone_banned'))
    assert r['status'] == 'dead_banned', r
    print(f"✅ dead_banned (phone): {r['error']}")


def test_hc_unauthorized():
    section("TEST A7: is_user_authorized=False → dead_session")
    r = asyncio.run(_run_hc('unauthorized'))
    assert r['status'] == 'dead_session', r
    assert 'session' in r['error'].lower() or '未授权' in r['error']
    print(f"✅ dead_session (unauthorized): {r['error']}")


def test_hc_get_me_fail():
    section("TEST A8: authorized 但 get_me 抛 AUTH_KEY → dead_session")
    r = asyncio.run(_run_hc('get_me_fail'))
    assert r['status'] == 'dead_session', r
    print(f"✅ dead_session (get_me fail): {r['error']}")


def test_hc_missing_api_id():
    section("TEST A9: api_id 缺失")
    from batch_import import health_check_account
    r = asyncio.run(health_check_account({'name': 'n', 'api_hash': 'x'}, None, '/tmp/foo'))
    assert r['status'] == 'unknown_error'
    assert 'api_id' in r['error']
    print(f"✅ api_id 缺失正确报错: {r['error']}")


# -------------------------------------------------------------
# parse_info_json 边缘场景
# -------------------------------------------------------------
def test_partial_json():
    section("TEST B1: json 仅部分字段")
    from batch_import import parse_info_json
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({'api_id': 123, 'api_hash': 'h'}, f)
        p = f.name
    try:
        fp = parse_info_json(p)
        assert fp['api_id'] == 123
        assert fp['device_model'] is None
        assert fp['twoFA'] is None
        print("✅ 缺失字段返回 None，不报错")
    finally:
        os.unlink(p)


def test_json_not_dict():
    section("TEST B2: json 顶层是数组")
    from batch_import import parse_info_json
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([1, 2, 3], f)
        p = f.name
    try:
        assert parse_info_json(p) == {}
        print("✅ 非 dict 顶层返回 {}")
    finally:
        os.unlink(p)


def test_empty_string_fields():
    section("TEST B3: 字段为空字符串应被跳过")
    from batch_import import parse_info_json
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({'api_id': '', 'app_id': 42, 'device': '', 'device_model': 'X'}, f)
        p = f.name
    try:
        fp = parse_info_json(p)
        assert fp['api_id'] == 42, f"空串应跳过降级到 app_id: {fp}"
        assert fp['device_model'] == 'X', f"空串应跳过降级: {fp}"
        print("✅ 空串字段被跳过，降级到备选 key")
    finally:
        os.unlink(p)


# -------------------------------------------------------------
# BatchImportThread 端到端（mock 掉健康检测）
# -------------------------------------------------------------
def test_pipeline_end_to_end():
    section("TEST C1: BatchImportThread 端到端流水线")

    # 准备 3 个号包：
    # 1. 完整（应活号）
    # 2. 缺 json（应 unknown_error "缺少 api_id"）
    # 3. 完整但 mock 成 dead_banned
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as app_dir:
        # 号 1: 完整
        s1 = os.path.join(src_dir, 'acc1.session')
        open(s1, 'w').close()
        with open(os.path.join(src_dir, 'acc1.json'), 'w') as f:
            json.dump({
                'app_id': 10, 'app_hash': 'h1', 'phone': '+1111',
                'device': 'iPhone', 'sdk': 'iOS17',
            }, f)

        # 号 2: 无 json
        s2 = os.path.join(src_dir, 'acc2.session')
        open(s2, 'w').close()

        # 号 3: 完整
        s3 = os.path.join(src_dir, 'acc3.session')
        open(s3, 'w').close()
        with open(os.path.join(src_dir, 'acc3.json'), 'w') as f:
            json.dump({'app_id': 20, 'app_hash': 'h3', 'phone': '+3333'}, f)

        from batch_import import scan_account_folder
        entries = scan_account_folder(src_dir)
        assert len(entries) == 3
        entries.sort(key=lambda x: x[0])  # 稳定顺序 acc1, acc2, acc3
        print(f"  扫到: {[e[0] for e in entries]}")

        proxies = [
            {'host': 'p1', 'port': 1, 'username': 'u', 'password': 'p'},
            {'host': 'p2', 'port': 2, 'username': '', 'password': ''},
            # 第 3 个号故意无代理 → None
        ]

        # mock get_session_path → app_dir，避免写到真项目目录
        def fake_get_session_path(name):
            return os.path.join(app_dir, f'session_{name}')

        # mock health_check：acc1 alive，acc3 banned
        async def fake_hc(account, proxy, session_path, timeout=20):
            if account['name'] == 'acc1':
                return {
                    'status': 'alive', 'error': '',
                    'phone': '+1111', 'username': 'a1', 'user_id': 1,
                }
            if account['name'] == 'acc3':
                return {
                    'status': 'dead_banned', 'error': 'banned',
                    'phone': '', 'username': '', 'user_id': 0,
                }
            # acc2 本来不该走到这里（缺 api_id 应提前返回）
            raise AssertionError(f"acc2 不应调 hc: {account}")

        # 直接调用 _run_async（避免起 QThread）
        from PyQt5.QtWidgets import QApplication
        if QApplication.instance() is None:
            _ = QApplication([])

        with patch('gui_monitor.get_session_path', side_effect=fake_get_session_path), \
             patch('batch_import.health_check_account', side_effect=fake_hc):
            from gui_monitor import BatchImportThread
            thread = BatchImportThread(entries, proxies, copy_sessions=True)
            results = asyncio.run(thread._run_async())

        assert len(results) == 3, f"应 3 条结果: {len(results)}"
        by_name = {r['name']: r for r in results}

        # acc1 → alive，session 已复制
        assert by_name['acc1']['status'] == 'alive', by_name['acc1']
        assert by_name['acc1']['account']['api_id'] == 10
        assert by_name['acc1']['account']['device_model'] == 'iPhone'
        assert by_name['acc1']['account']['system_version'] == 'iOS17'
        assert by_name['acc1']['proxy']['host'] == 'p1'
        assert os.path.exists(os.path.join(app_dir, 'session_acc1.session')), \
            "acc1 session 应被复制"
        print(f"  ✅ acc1: alive + session 已复制 + 指纹正确")

        # acc2 → unknown_error（缺 api_id，未调 hc）
        assert by_name['acc2']['status'] == 'unknown_error', by_name['acc2']
        assert 'api_id' in by_name['acc2']['error']
        print(f"  ✅ acc2 缺 json：跳过 hc，标 unknown_error ({by_name['acc2']['error']})")

        # acc3 → dead_banned，代理为 None（代理数量不足）
        assert by_name['acc3']['status'] == 'dead_banned', by_name['acc3']
        assert by_name['acc3']['proxy'] is None
        print(f"  ✅ acc3: dead_banned + 代理=None（代理数 < 号数时溢出号直连）")


def test_pipeline_session_same_path():
    section("TEST C2: session 源路径 = 目标路径 不重复复制")
    with tempfile.TemporaryDirectory() as app_dir:
        name = 'acc_same'
        session_stem = os.path.join(app_dir, f'session_{name}')
        session_file = session_stem + '.session'
        open(session_file, 'w').close()
        json_file = os.path.join(app_dir, f'{name}.json')
        with open(json_file, 'w') as f:
            json.dump({'app_id': 1, 'app_hash': 'h', 'phone': '+1'}, f)

        entries = [(name, session_file, json_file)]

        def fake_get_session_path(n):
            return os.path.join(app_dir, f'session_{n}')

        async def fake_hc(account, proxy, session_path, timeout=20):
            return {'status': 'alive', 'error': '', 'phone': '+1',
                    'username': '', 'user_id': 1}

        from PyQt5.QtWidgets import QApplication
        if QApplication.instance() is None:
            _ = QApplication([])

        with patch('gui_monitor.get_session_path', side_effect=fake_get_session_path), \
             patch('batch_import.health_check_account', side_effect=fake_hc):
            from gui_monitor import BatchImportThread
            thread = BatchImportThread(entries, [], copy_sessions=True)
            results = asyncio.run(thread._run_async())

        assert results[0]['status'] == 'alive'
        print("✅ 源==目标时跳过复制，不抛 SameFileError")


# -------------------------------------------------------------
# BatchImportDialog._apply_to_config 合并逻辑
# -------------------------------------------------------------
def test_apply_to_config_merge():
    section("TEST D1: _apply_to_config 按 name 去重合并")
    # 只验证合并算法，不启 Qt
    existing_accounts = [
        {'name': 'old1', 'api_id': '1', 'api_hash': 'a', 'phone': '+1',
         'proxy': {'host': 'old', 'port': 1, 'username': '', 'password': ''}},
        {'name': 'conflict', 'api_id': '99', 'api_hash': 'z', 'phone': '+99',
         'proxy': {'host': 'old', 'port': 99, 'username': '', 'password': ''}},
    ]
    alive_results = [
        {
            'name': 'conflict',
            'account': {'name': 'conflict', 'api_id': '100', 'api_hash': 'new', 'phone': '+100'},
            'proxy': {'host': 'newp', 'port': 100, 'username': 'u', 'password': 'p'},
            'status': 'alive',
        },
        {
            'name': 'new1',
            'account': {'name': 'new1', 'api_id': '200', 'api_hash': 'n', 'phone': '+200'},
            'proxy': {'host': 'p2', 'port': 200, 'username': '', 'password': ''},
            'status': 'alive',
        },
    ]

    existing = {a['name']: a for a in existing_accounts}
    for r in alive_results:
        acc = dict(r['account'])
        proxy = r.get('proxy') or {}
        acc['proxy'] = {
            'host': proxy.get('host', ''),
            'port': proxy.get('port', 0),
            'username': proxy.get('username', ''),
            'password': proxy.get('password', ''),
        }
        existing[acc['name']] = acc

    final = list(existing.values())
    by_name = {a['name']: a for a in final}
    assert 'old1' in by_name and by_name['old1']['api_id'] == '1', "未冲突的旧号应保留"
    assert by_name['conflict']['api_id'] == '100', "同名冲突：新号覆盖旧号"
    assert by_name['conflict']['proxy']['host'] == 'newp', "同名冲突：代理也覆盖"
    assert 'new1' in by_name
    assert len(final) == 3
    print(f"✅ 合并结果: 保留 old1、覆盖 conflict、新增 new1（共 {len(final)} 个）")


# -------------------------------------------------------------
# 代理分配策略
# -------------------------------------------------------------
def test_proxy_assignment_edge_cases():
    section("TEST E1: 代理数 > 号数 / < 号数 / == 号数")
    # 代理数 > 号数：多余代理丢弃
    proxies = [{'host': f'h{i}', 'port': i} for i in range(5)]
    entries = [('a', 's', None), ('b', 's', None)]
    assigned = [proxies[i] if i < len(proxies) else None for i in range(len(entries))]
    assert [p['host'] for p in assigned] == ['h0', 'h1']
    print("✅ 代理多余：只取前 N 条")

    # 代理数 == 号数：一一对应
    proxies = [{'host': 'a'}, {'host': 'b'}]
    entries = [('x', 's', None), ('y', 's', None)]
    assigned = [proxies[i] if i < len(proxies) else None for i in range(len(entries))]
    assert assigned[0]['host'] == 'a' and assigned[1]['host'] == 'b'
    print("✅ 代理 == 号数：一一对应")

    # 代理数 < 号数：溢出号直连（None）
    proxies = [{'host': 'only'}]
    entries = [('x', 's', None), ('y', 's', None), ('z', 's', None)]
    assigned = [proxies[i] if i < len(proxies) else None for i in range(len(entries))]
    assert assigned[0]['host'] == 'only'
    assert assigned[1] is None and assigned[2] is None
    print("✅ 代理不足：溢出号直连（None）")


def test_session_overwrite_detection():
    section("TEST F1: P1 session 覆盖冲突检测")
    # 模拟 _start 里用来检测冲突的那段逻辑
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as app_dir:
        # 号 1：目标已有 session（冲突）
        s1 = os.path.join(src_dir, 'dup.session')
        open(s1, 'w').close()
        open(os.path.join(app_dir, 'session_dup.session'), 'w').close()
        # 号 2：目标没有 session（不冲突）
        s2 = os.path.join(src_dir, 'fresh.session')
        open(s2, 'w').close()
        # 号 3：源 == 目标（已在位，不应算冲突）
        s3 = os.path.join(app_dir, 'session_inplace.session')
        open(s3, 'w').close()

        entries = [('dup', s1, None), ('fresh', s2, None), ('inplace', s3, None)]

        def fake_get_session_path(name):
            return os.path.join(app_dir, f'session_{name}')

        # 复刻 _start 里的冲突检测
        conflicts = []
        for (name, src, _) in entries:
            dest = fake_get_session_path(name) + '.session'
            if os.path.abspath(src) == os.path.abspath(dest):
                continue
            if os.path.exists(dest):
                conflicts.append(name)

        assert conflicts == ['dup'], f"应仅 dup 冲突，实际 {conflicts}"
        print(f"✅ 冲突检测正确：仅 dup 冲突，fresh 和 inplace 不冲突")


if __name__ == '__main__':
    test_hc_alive()
    test_hc_proxy_failed()
    test_hc_dead_session_auth_invalid()
    test_hc_dead_banned()
    test_hc_dead_deactivated()
    test_hc_phone_banned()
    test_hc_unauthorized()
    test_hc_get_me_fail()
    test_hc_missing_api_id()

    test_partial_json()
    test_json_not_dict()
    test_empty_string_fields()

    test_pipeline_end_to_end()
    test_pipeline_session_same_path()

    test_apply_to_config_merge()
    test_proxy_assignment_edge_cases()

    test_session_overwrite_detection()

    print("\n" + "=" * 60)
    print("🎉 深度模拟测试全部通过")
    print("=" * 60)
