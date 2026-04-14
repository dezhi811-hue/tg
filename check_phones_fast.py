#!/usr/bin/env python3
"""
快速批量检测手机号是否注册Telegram
使用 Telegram contacts.importContacts API，速度极快
"""
import sys
import os

# 查找已有的 session 文件
for f in os.listdir('.'):
    if f.startswith('session_') and f.endswith('.session'):
        session_name = f.replace('.session', '')
        break
    else:
        session_name = None

if not session_name:
    print("❌ 未找到 session 文件，请先通过 gui_monitor.py 登录账号")
    sys.exit(1)

print(f"🔗 使用 session: {session_name}")

import asyncio
from telethon import TelegramClient


def get_config_path():
    """获取 config.json 路径，支持 EXE 打包"""
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'config.json')


async def main():
    client = TelegramClient(session_name, timeout=60)
    await client.start()

    # 读取号码文件
    if len(sys.argv) < 2:
        print("用法: python3 check_phones_fast.py phones.txt")
        return

    phone_file = sys.argv[1]
    if not os.path.exists(phone_file):
        print(f"❌ 文件不存在: {phone_file}")
        return

    with open(phone_file, 'r') as f:
        raw_phones = [line.strip() for line in f if line.strip()]

    print(f"📋 共 {len(raw_phones)} 个号码，开始检测...")

    # 格式化号码（统一加 +）
    def format_phone(p):
        p = p.strip()
        if not p.startswith('+'):
            p = '+' + p
        return p

    phones_to_check = [format_phone(p) for p in raw_phones]

    # 批量导入通讯录来检测（Telegram 官方方式，最快）
    from telethon.tl.functions.contacts import ImportContactsRequest
    from telethon.tl.types import InputPhoneContact

    contacts = []
    for i, phone in enumerate(phones_to_check):
        contacts.append(InputPhoneContact(
            client_id=i,
            phone=phone,
            first_name="User",
            last_name=""
        ))

    # 分批处理，每批1000个
    batch_size = 1000
    registered = []
    not_registered = []
    total = len(contacts)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = contacts[batch_start:batch_end]

        print(f"  检测第 {batch_start+1}-{batch_end}/{total} 个...")

        try:
            result = await client(ImportContactsRequest(contacts=batch))
            if result.users:
                for user in result.users:
                    registered.append(user.phone)
            registered_phones = set(u.phone for u in result.users)
            for c in batch:
                if c.phone not in registered_phones:
                    not_registered.append(c.phone)
        except Exception as e:
            print(f"  ⚠️ 批次 {batch_start//batch_size+1} 出错: {e}")

    print(f"\n{'='*50}")
    print(f"✅ 已注册: {len(registered)} 个")
    print(f"❌ 未注册: {len(not_registered)} 个")
    print(f"{'='*50}")

    # 保存结果
    with open('registered.txt', 'w') as f:
        for p in registered:
            f.write(p + '\n')

    with open('not_registered.txt', 'w') as f:
        for p in not_registered:
            f.write(p + '\n')

    print(f"\n💾 结果已保存:")
    print(f"   registered.txt     - 已注册号码")
    print(f"   not_registered.txt - 未注册号码")

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
