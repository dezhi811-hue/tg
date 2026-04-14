#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram 登录工具
用于生成 session 文件
"""

import sys
import json
import asyncio
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError


class LoginThread(QThread):
    """登录线程"""
    log_signal = pyqtSignal(str)
    success_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    code_needed_signal = pyqtSignal()
    password_needed_signal = pyqtSignal()

    def __init__(self, phone, api_id, api_hash, session_name, proxy=None):
        super().__init__()
        self.phone = phone
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.proxy = proxy
        self.client = None
        self.code = None
        self.password = None
        self.waiting_for_code = False
        self.waiting_for_password = False

    def run(self):
        asyncio.run(self.login())

    async def login(self):
        try:
            self.log_signal.emit(f"正在连接 Telegram...")

            # 创建客户端
            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash,
                proxy=self.proxy
            )

            await self.client.connect()

            if not await self.client.is_user_authorized():
                self.log_signal.emit(f"发送验证码到 {self.phone}...")
                await self.client.send_code_request(self.phone)

                # 等待验证码
                self.log_signal.emit("等待输入验证码...")
                self.code_needed_signal.emit()
                self.waiting_for_code = True

                while self.waiting_for_code:
                    await asyncio.sleep(0.1)

                if not self.code:
                    self.error_signal.emit("未输入验证码")
                    return

                try:
                    self.log_signal.emit("验证中...")
                    await self.client.sign_in(self.phone, self.code)
                except SessionPasswordNeededError:
                    # 需要两步验证密码
                    self.log_signal.emit("需要两步验证密码...")
                    self.password_needed_signal.emit()
                    self.waiting_for_password = True

                    while self.waiting_for_password:
                        await asyncio.sleep(0.1)

                    if not self.password:
                        self.error_signal.emit("未输入密码")
                        return

                    await self.client.sign_in(password=self.password)
                except PhoneCodeInvalidError:
                    self.error_signal.emit("验证码错误")
                    return

            # 获取用户信息
            me = await self.client.get_me()
            self.log_signal.emit(f"登录成功！用户: {me.first_name}")

            session_file = f"{self.session_name}.session"
            self.success_signal.emit(f"Session 文件已生成: {session_file}")

        except Exception as e:
            self.error_signal.emit(f"登录失败: {str(e)}")
        finally:
            if self.client:
                await self.client.disconnect()

    def set_code(self, code):
        self.code = code
        self.waiting_for_code = False

    def set_password(self, password):
        self.password = password
        self.waiting_for_password = False


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.login_thread = None
        self.init_ui()
        self.load_config()

    def init_ui(self):
        self.setWindowTitle('Telegram 登录工具')
        self.setMinimumSize(500, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 标题
        title = QLabel('Telegram 账号登录')
        title.setStyleSheet('font-size: 18px; font-weight: bold; margin: 10px;')
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # API ID
        layout.addWidget(QLabel('API ID:'))
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText('从 my.telegram.org 获取')
        layout.addWidget(self.api_id_input)

        # API Hash
        layout.addWidget(QLabel('API Hash:'))
        self.api_hash_input = QLineEdit()
        self.api_hash_input.setPlaceholderText('从 my.telegram.org 获取')
        layout.addWidget(self.api_hash_input)

        # 手机号
        layout.addWidget(QLabel('手机号 (带国际区号):'))
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText('例如: +8613800138000')
        layout.addWidget(self.phone_input)

        # Session 名称
        layout.addWidget(QLabel('Session 名称:'))
        self.session_input = QLineEdit()
        self.session_input.setText('session_1')
        self.session_input.setPlaceholderText('例如: session_1')
        layout.addWidget(self.session_input)

        # 代理设置（可选）
        layout.addWidget(QLabel('代理 (可选):'))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText('例如: socks5://127.0.0.1:1080')
        layout.addWidget(self.proxy_input)

        # 登录按钮
        self.login_btn = QPushButton('开始登录')
        self.login_btn.setStyleSheet('padding: 10px; font-size: 14px;')
        self.login_btn.clicked.connect(self.start_login)
        layout.addWidget(self.login_btn)

        # 日志输出
        layout.addWidget(QLabel('日志:'))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

    def load_config(self):
        """加载配置文件"""
        config_file = Path('config.json')
        if not config_file.exists():
            config_file = Path('config.example.json')

        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.api_id_input.setText(str(config.get('api_id', '')))
                    self.api_hash_input.setText(config.get('api_hash', ''))

                    proxy = config.get('proxy')
                    if proxy:
                        proxy_str = f"{proxy['proxy_type']}://{proxy['addr']}:{proxy['port']}"
                        self.proxy_input.setText(proxy_str)
            except Exception as e:
                self.log(f"加载配置文件失败: {e}")

    def start_login(self):
        # 验证输入
        api_id = self.api_id_input.text().strip()
        api_hash = self.api_hash_input.text().strip()
        phone = self.phone_input.text().strip()
        session_name = self.session_input.text().strip()

        if not all([api_id, api_hash, phone, session_name]):
            QMessageBox.warning(self, '错误', '请填写所有必填项')
            return

        try:
            api_id = int(api_id)
        except ValueError:
            QMessageBox.warning(self, '错误', 'API ID 必须是数字')
            return

        # 解析代理
        proxy = None
        proxy_str = self.proxy_input.text().strip()
        if proxy_str:
            try:
                # 简单解析 socks5://host:port
                if '://' in proxy_str:
                    proxy_type, addr_port = proxy_str.split('://')
                    addr, port = addr_port.split(':')
                    proxy = (proxy_type, addr, int(port))
            except Exception as e:
                QMessageBox.warning(self, '错误', f'代理格式错误: {e}')
                return

        # 禁用按钮
        self.login_btn.setEnabled(False)
        self.log_text.clear()

        # 启动登录线程
        self.login_thread = LoginThread(phone, api_id, api_hash, session_name, proxy)
        self.login_thread.log_signal.connect(self.log)
        self.login_thread.success_signal.connect(self.on_success)
        self.login_thread.error_signal.connect(self.on_error)
        self.login_thread.code_needed_signal.connect(self.ask_code)
        self.login_thread.password_needed_signal.connect(self.ask_password)
        self.login_thread.start()

    def log(self, message):
        self.log_text.append(message)

    def ask_code(self):
        code, ok = QMessageBox.getText(self, '输入验证码',
                                       '请输入 Telegram 发送的验证码:',
                                       QLineEdit.Normal)
        if ok and code:
            self.login_thread.set_code(code.strip())
        else:
            self.login_thread.set_code(None)

    def ask_password(self):
        password, ok = QMessageBox.getText(self, '输入密码',
                                          '请输入两步验证密码:',
                                          QLineEdit.Password)
        if ok and password:
            self.login_thread.set_password(password)
        else:
            self.login_thread.set_password(None)

    def on_success(self, message):
        self.log(message)
        self.login_btn.setEnabled(True)
        QMessageBox.information(self, '成功', message)

    def on_error(self, message):
        self.log(f"错误: {message}")
        self.login_btn.setEnabled(True)
        QMessageBox.critical(self, '错误', message)


def main():
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
