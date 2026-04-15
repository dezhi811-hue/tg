#!/usr/bin/env python3
"""
登录账号 2
"""
import asyncio
import json
import os
import sys
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


def get_config_path():
    """获取 config.json 路径"""
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'config.json')


async def main():
    config_path = get_config_path()

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    accounts = config.get('accounts', [])
    if len(accounts) < 2:
        print('❌ config.json 里没有账号 2')
        return

    acc = accounts[1]  # 账号 2
    session_name = f"session_{acc['name']}"

    # 支持代理
    proxy = acc.get('proxy', {})
    proxy_config = None
    if proxy and proxy.get('host'):
        proxy_config = ('socks5', proxy['host'], proxy['port'],
                       proxy.get('username') or None, proxy.get('password') or None)
        print(f"  使用代理: {proxy['host']}:{proxy['port']}")

    client = TelegramClient(
        session_name,
        int(acc['api_id']),
        acc['api_hash'],
        proxy=proxy_config
    )

    await client.connect()

    if await client.is_user_authorized():
        print(f"✅ 账号 {acc['name']} 已登录")
        await client.disconnect()
        return

    print(f"📱 正在给 {acc['phone']} 发送验证码...")
    await client.send_code_request(acc['phone'])
    code = input('请输入验证码: ').strip()

    try:
        await client.sign_in(acc['phone'], code)
    except SessionPasswordNeededError:
        password = input('请输入两步验证密码: ').strip()
        await client.sign_in(password=password)

    print(f"✅ 账号 {acc['name']} 登录成功")
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
