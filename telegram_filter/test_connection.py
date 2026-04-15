#!/usr/bin/env python3
"""
测试 Telegram 连接
"""
import asyncio
import json
from telethon import TelegramClient


async def test_connection():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    account = config['accounts'][0]
    name = account['name']

    # 检查代理配置
    proxy = account.get('proxy', {})
    proxy_config = None
    if proxy and proxy.get('host'):
        proxy_config = ('socks5', proxy['host'], proxy['port'],
                       proxy.get('username') or None, proxy.get('password') or None)
        print(f"✓ 使用代理: {proxy['host']}:{proxy['port']}")
    else:
        print("✓ 不使用代理，直连")

    print(f"\n正在测试账号 {name} 的连接...")
    print(f"API ID: {account['api_id']}")
    print(f"手机号: {account['phone']}")

    client = TelegramClient(
        f"session_{name}",
        int(account['api_id']),
        account['api_hash'],
        proxy=proxy_config
    )

    try:
        print("\n[1/3] 正在连接 Telegram 服务器...")
        await client.connect()

        if client.is_connected():
            print("✅ 连接成功！")
        else:
            print("❌ 连接失败")
            return

        print("\n[2/3] 检查登录状态...")
        if await client.is_user_authorized():
            print("✅ 账号已登录")
            me = await client.get_me()
            print(f"   用户名: {me.first_name} {me.last_name or ''}")
            print(f"   用户ID: {me.id}")
        else:
            print("⚠️  账号未登录（需要先运行 login.py 登录）")

        print("\n[3/3] 测试完成")

    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
    finally:
        await client.disconnect()
        print("\n已断开连接")


if __name__ == '__main__':
    asyncio.run(test_connection())
