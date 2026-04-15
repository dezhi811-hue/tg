#!/usr/bin/env python3
"""
测试账号是否正常工作
用法: python3 test_accounts.py
"""
import asyncio
import json
from account_manager import AccountManager
from filter import TelegramFilter
from rate_limiter import RateLimiter


async def test_accounts():
    """测试所有账号是否能正常连接和查询"""
    print("=" * 60)
    print("🔍 测试账号连接和查询功能")
    print("=" * 60)

    # 1. 加载配置
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ 配置文件加载成功，共 {len(config['accounts'])} 个账号")
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        return

    # 2. 连接所有账号
    print("\n" + "=" * 60)
    print("📡 正在连接账号...")
    print("=" * 60)

    try:
        manager = AccountManager('config.json')
        await manager.connect_all()
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # 检查连接状态
    connected_count = sum(1 for acc in manager.accounts if acc.get('client'))
    print(f"\n✅ 成功连接 {connected_count}/{len(manager.accounts)} 个账号")

    if connected_count == 0:
        print("❌ 没有可用账号，请先运行 python3 login.py 登录")
        return

    # 3. 显示账号状态
    print("\n" + "=" * 60)
    print("📊 账号状态")
    print("=" * 60)
    for acc in manager.accounts:
        status = "✅ 已连接" if acc.get('client') else "❌ 未连接"
        role = acc.get('role', 'primary')
        state = acc.get('runtime_state', 'active')
        print(f"{acc['name']:15} | {status} | 角色: {role:8} | 状态: {state}")

    # 4. 测试查询功能
    print("\n" + "=" * 60)
    print("🧪 测试查询功能（使用已知的Telegram官方号码）")
    print("=" * 60)

    # 使用Telegram官方账号测试（这个号码肯定注册了）
    test_phone = "+42777"  # Telegram官方测试号

    try:
        limiter = RateLimiter(config['rate_limit'])
        filter_obj = TelegramFilter(manager, limiter)

        print(f"\n正在查询测试号码: {test_phone}")
        result = await filter_obj.check_phone(test_phone, 'US')

        if result.get('registered'):
            print(f"✅ 查询成功！")
            print(f"   号码: {result.get('phone')}")
            print(f"   用户名: {result.get('username') or 'N/A'}")
            print(f"   名字: {result.get('first_name') or 'N/A'}")
            print(f"   状态: {result.get('status') or 'unknown'}")
            print(f"   查询状态: {result.get('query_state')}")
        else:
            print(f"⚠️ 查询返回未注册（可能是网络问题）")
            print(f"   查询状态: {result.get('query_state')}")
            print(f"   错误信息: {result.get('error')}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()

    # 5. 显示速率配置
    print("\n" + "=" * 60)
    print("⚙️  当前速率配置")
    print("=" * 60)
    rate_config = config.get('rate_limit', {})
    print(f"每账号请求数: {rate_config.get('requests_per_account', 'N/A')}")
    print(f"最小延迟: {rate_config.get('min_delay', 'N/A')} 秒")
    print(f"最大延迟: {rate_config.get('max_delay', 'N/A')} 秒")
    print(f"错误冷却: {rate_config.get('error_cooldown', 'N/A')} 秒")

    avg_delay = (rate_config.get('min_delay', 0) + rate_config.get('max_delay', 0)) / 2
    queries_per_min = 60 / avg_delay if avg_delay > 0 else 0
    print(f"\n预计速度: 平均每分钟 {queries_per_min:.1f} 次查询")

    # 6. 断开连接
    print("\n" + "=" * 60)
    await manager.disconnect_all()
    print("✅ 测试完成，已断开所有连接")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(test_accounts())
