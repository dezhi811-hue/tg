"""batch_import 模块单元测试"""
import json
import os
import sys
import tempfile

ROOT = '/Volumes/waijie/tg'
sys.path.insert(0, ROOT)


def section(t):
    print(f"\n{'=' * 60}\n{t}\n{'=' * 60}")


def test_parse_proxy_line():
    section("TEST 1: parse_proxy_line")
    from batch_import import parse_proxy_line

    # 标准格式
    p = parse_proxy_line("us-eu.fluxisp.com:5000:gdggxfzrk51113-region-US-sid-FNVUBKrn-t-5:uhh5m5eu")
    assert p == {
        "host": "us-eu.fluxisp.com",
        "port": 5000,
        "username": "gdggxfzrk51113-region-US-sid-FNVUBKrn-t-5",
        "password": "uhh5m5eu",
    }, p
    print(f"✅ 标准格式解析: {p}")

    # 只 host:port
    p = parse_proxy_line("1.2.3.4:1080")
    assert p == {"host": "1.2.3.4", "port": 1080, "username": "", "password": ""}
    print(f"✅ host:port 格式: {p}")

    # 空行 / 注释
    assert parse_proxy_line("") is None
    assert parse_proxy_line("   ") is None
    assert parse_proxy_line("# 一条注释") is None
    print("✅ 空行/注释返回 None")

    # 密码里含冒号
    p = parse_proxy_line("h:1:u:pa:ss:word")
    assert p['password'] == "pa:ss:word", f"密码应保留冒号: {p['password']}"
    print(f"✅ 密码含冒号保留: {p['password']}")

    # 错误格式
    for bad in ["onlyhost", "host:notanumber"]:
        try:
            parse_proxy_line(bad)
            assert False, f"应该抛错: {bad}"
        except ValueError:
            pass
    print("✅ 无效格式抛 ValueError")


def test_parse_proxy_block():
    section("TEST 2: parse_proxy_block 批量")
    from batch_import import parse_proxy_block
    text = """
    # 这是注释
    h1.com:1080:u1:p1
    h2.com:2080:u2:p2
    bad_line_no_port
    h3.com:3080
    """
    proxies, errors = parse_proxy_block(text)
    assert len(proxies) == 3, f"应 3 条有效: {proxies}"
    assert len(errors) == 1, f"应 1 条错误: {errors}"
    assert proxies[0]['host'] == 'h1.com'
    assert proxies[2]['username'] == ''
    print(f"✅ 解析 3 条有效 + 1 条错误: {errors[0]}")


def test_scan_account_folder():
    section("TEST 3: scan_account_folder 扁平 + 子目录")
    from batch_import import scan_account_folder

    with tempfile.TemporaryDirectory() as tmp:
        # 扁平
        open(os.path.join(tmp, 'acc1.session'), 'w').close()
        with open(os.path.join(tmp, 'acc1.json'), 'w') as f:
            f.write('{}')
        # 子目录
        sub = os.path.join(tmp, 'acc2_folder')
        os.makedirs(sub)
        open(os.path.join(sub, 'x.session'), 'w').close()
        with open(os.path.join(sub, 'info.json'), 'w') as f:
            f.write('{}')
        # 子目录无 json
        sub2 = os.path.join(tmp, 'acc3_folder')
        os.makedirs(sub2)
        open(os.path.join(sub2, 'y.session'), 'w').close()

        entries = scan_account_folder(tmp)
        assert len(entries) == 3, f"应扫到 3 个: {entries}"
        by_name = {e[0]: e for e in entries}
        assert 'acc1' in by_name and by_name['acc1'][2] is not None
        assert 'acc2_folder' in by_name and by_name['acc2_folder'][2] is not None
        assert 'acc3_folder' in by_name and by_name['acc3_folder'][2] is None
        print(f"✅ 扫到 3 个号，其中 2 个有 json")


def test_parse_info_json():
    section("TEST 4: parse_info_json 模糊匹配")
    from batch_import import parse_info_json

    # 常见卖号格式（含 app_id / app_hash / device / sdk）
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "app_id": 2040,
            "app_hash": "abc123def456",
            "phone": "+14123456789",
            "device": "iPhone 15 Pro Max",
            "sdk": "iOS 17.3",
            "app_version": "10.5.0",
            "lang_code": "en",
            "system_lang_code": "en-US",
            "twoFA": "pwd123",
        }, f)
        path = f.name

    try:
        fp = parse_info_json(path)
        assert fp['api_id'] == 2040
        assert fp['api_hash'] == "abc123def456"
        assert fp['device_model'] == "iPhone 15 Pro Max"
        assert fp['system_version'] == "iOS 17.3"
        assert fp['app_version'] == "10.5.0"
        assert fp['twoFA'] == "pwd123"
        print(f"✅ 卖号包常见字段（app_id/app_hash/device/sdk）全部正确映射")
    finally:
        os.unlink(path)

    # 损坏 json
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("not a json")
        path2 = f.name
    try:
        assert parse_info_json(path2) == {}
        print("✅ 损坏 json 返回 {}")
    finally:
        os.unlink(path2)

    # None
    assert parse_info_json(None) == {}
    print("✅ path=None 返回 {}")


def test_status_label():
    section("TEST 5: STATUS_LABEL / is_refundable")
    from batch_import import STATUS_LABEL, is_refundable
    assert not is_refundable('alive')
    assert is_refundable('dead_session')
    assert is_refundable('dead_banned')
    assert is_refundable('dead_deactivated')
    assert not is_refundable('proxy_failed'), "代理挂了号本身可能没问题，不应标可退"
    assert 'alive' in STATUS_LABEL and 'proxy_failed' in STATUS_LABEL
    print(f"✅ 退款规则：死号可退，代理问题不可退")


if __name__ == '__main__':
    test_parse_proxy_line()
    test_parse_proxy_block()
    test_scan_account_folder()
    test_parse_info_json()
    test_status_label()
    print("\n" + "=" * 60)
    print("🎉 batch_import 全部测试通过")
    print("=" * 60)
