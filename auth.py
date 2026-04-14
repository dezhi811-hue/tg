"""
Telegram认证模块
"""
import json
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


class TelegramAuth:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.api_id = self.config['api_id']
        self.api_hash = self.config['api_hash']
        self.phone = self.config.get('phone', '')
        self.client = None

    async def connect(self):
        """连接到Telegram"""
        self.client = TelegramClient('session', self.api_id, self.api_hash)
        await self.client.connect()

        if not await self.client.is_user_authorized():
            await self._login()

        return self.client

    async def _login(self):
        """登录流程"""
        print(f"正在发送验证码到 {self.phone}")
        await self.client.send_code_request(self.phone)

        code = input('请输入验证码: ')

        try:
            await self.client.sign_in(self.phone, code)
        except SessionPasswordNeededError:
            password = input('需要两步验证密码，请输入: ')
            await self.client.sign_in(password=password)

        print("登录成功！")

    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.disconnect()
