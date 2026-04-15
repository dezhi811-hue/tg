#!/usr/bin/env python3
"""检查账号 2 的登录状态"""
import asyncio
import json
from telethon import TelegramClient

async def check_account2():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    account = config['accounts'][1]  # 账号 2

    client = TelegramClient(
        f"session_{account['name']}",
        int(account['api_id']),
        account['api_hash']
    )

    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✅ 账号 2 已登录")
            print(f"   手机号: {account['phone']}")
            print(f"   用户: {me.first_name} {me.last_name or ''}")
        else:
            print(f"❌ 账号 2 未登录")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
    finally:
        await client.disconnect()

asyncio.run(check_account2())
