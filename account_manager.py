"""
多账号管理模块
"""
import json
import os
import sys
import asyncio
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError


# 设备指纹池：每个账号第一次连接时随机抽一套固定下来，避免所有账号共用一套默认指纹。
# 2025–2026 Telegram 风控重点之一：多账号同指纹直接扣分。
_DEVICE_PROFILES = [
    {"device_model": "iPhone 14 Pro",      "system_version": "17.4",   "app_version": "10.9.1",  "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "iPhone 15",          "system_version": "17.5.1", "app_version": "10.10.0", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "Samsung SM-G998B",   "system_version": "Android 14", "app_version": "10.9.1", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "Pixel 7",            "system_version": "Android 14", "app_version": "10.8.3", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "MacBook Pro",        "system_version": "macOS 14.4", "app_version": "4.16.8", "lang_code": "en", "system_lang_code": "en-US"},
    {"device_model": "Desktop",            "system_version": "Windows 11", "app_version": "4.16.8", "lang_code": "en", "system_lang_code": "en-US"},
]


def resolve_device_profile(account):
    """解析账号的设备指纹，返回 dict。

    优先读 account 中的显式字段；缺失则按账号 name 的稳定 hash 从指纹池挑一套，
    保证同一账号每次启动得到相同指纹，避免 Telegram 风控误判为"设备频繁切换"。
    """
    # 稳定 hash：name 相同永远得到同一套指纹
    name = account.get('name') or ''
    idx = abs(hash(name)) % len(_DEVICE_PROFILES)
    profile = _DEVICE_PROFILES[idx]
    return {
        'device_model': account.get('device_model') or profile['device_model'],
        'system_version': account.get('system_version') or profile['system_version'],
        'app_version': account.get('app_version') or profile['app_version'],
        'lang_code': account.get('lang_code') or profile['lang_code'],
        'system_lang_code': account.get('system_lang_code') or profile['system_lang_code'],
    }


def build_proxy_config(proxy):
    """把 config 里的 proxy dict 转换成 Telethon/PySocks 6 元组；没配返回 None。

    6 元组（而非 5 元组）确保 rdns=True，DNS 也走代理，防止本机 DNS 泄露真实 IP。
    空字符串的 username/password 改成 None，避免代理以"空密码认证"失败。
    """
    if not proxy or not proxy.get('host'):
        return None
    return (
        'socks5',
        proxy['host'],
        int(proxy['port']) if proxy.get('port') else 1080,
        True,
        (proxy.get('username') or None),
        (proxy.get('password') or None),
    )


def _get_app_dir():
    """session 文件所在目录：EXE 打包时为 EXE 所在目录，否则为脚本目录。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_session_path(name):
    return os.path.join(_get_app_dir(), f"session_{name}")


class AccountManager:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.accounts = []
        self.current_index = 0
        self.account_stats = {}  # 统计每个账号的使用情况

        # 初始化账号
        for acc_config in self.config['accounts']:
            account = {
                'name': acc_config['name'],
                'api_id': acc_config['api_id'],
                'api_hash': acc_config['api_hash'],
                'phone': acc_config['phone'],
                'proxy': acc_config.get('proxy', {}),
                'client': None,
                'request_count': 0,
                'probe_count': 0,
                'block_count': 0,
                'last_request_time': None,
                'is_blocked': False,
                'block_until': None
            }
            self.accounts.append(account)
            self.account_stats[acc_config['name']] = {
                'total_requests': 0,
                'errors': 0,
                'success': 0
            }

        self.rate_config = self.config['rate_limit']
        self.role_assignments = {
            'primary': [],
            'backup': []
        }

        self._initialize_account_roles()

    def _initialize_account_roles(self):
        raw = self.config.get('primary_count')
        try:
            primary_count = int(raw) if raw else len(self.accounts)
        except (TypeError, ValueError):
            primary_count = len(self.accounts)
        if self.accounts:
            primary_count = max(1, min(primary_count, len(self.accounts)))
        else:
            primary_count = 0
        for idx, account in enumerate(self.accounts):
            is_primary = idx < primary_count
            account['role'] = 'primary' if is_primary else 'backup'
            account['runtime_state'] = 'active' if is_primary else 'standby'
            account['suspected_count'] = 0
            account['replacement_history'] = []
            self.role_assignments[account['role']].append(account['name'])

    def get_accounts_by_role(self, role, include_paused=False):
        accounts = []
        for account in self.accounts:
            if account.get('role') != role:
                continue
            if include_paused:
                accounts.append(account)
                continue
            if account.get('runtime_state') in {'active', 'standby'} and not account.get('is_blocked'):
                accounts.append(account)
        return accounts

    def get_active_primary_accounts(self):
        return [acc for acc in self.get_accounts_by_role('primary') if acc.get('runtime_state') == 'active']

    def get_available_backup_accounts(self):
        return [acc for acc in self.get_accounts_by_role('backup') if acc.get('runtime_state') == 'standby']

    def mark_account_suspected(self, account, reason=''):
        account['runtime_state'] = 'suspected'
        account['suspected_count'] = account.get('suspected_count', 0) + 1
        if reason:
            account['replacement_history'].append(f"suspected:{reason}")

    def pause_account(self, account, reason=''):
        account['runtime_state'] = 'paused'
        if reason:
            account['replacement_history'].append(f"paused:{reason}")

    def activate_account(self, account, role=None, reason=''):
        if role and account.get('role') != role:
            old_role = account.get('role')
            if old_role in self.role_assignments and account['name'] in self.role_assignments[old_role]:
                self.role_assignments[old_role].remove(account['name'])
            account['role'] = role
            self.role_assignments.setdefault(role, []).append(account['name'])
        account['runtime_state'] = 'active' if account.get('role') == 'primary' else 'standby'
        if reason:
            account['replacement_history'].append(f"activated:{reason}")

    def replace_primary_account(self, target_account, backup_account, reason=''):
        target_account['runtime_state'] = 'paused'
        if reason:
            target_account['replacement_history'].append(f"replaced_out:{reason}")
            backup_account['replacement_history'].append(f"replaced_in:{reason}")

        target_name = target_account['name']
        backup_name = backup_account['name']

        if target_name in self.role_assignments['primary']:
            self.role_assignments['primary'].remove(target_name)
        if backup_name in self.role_assignments['backup']:
            self.role_assignments['backup'].remove(backup_name)

        self.role_assignments['primary'].append(backup_name)
        self.role_assignments['backup'].append(target_name)

        target_account['role'] = 'backup'
        backup_account['role'] = 'primary'
        backup_account['runtime_state'] = 'active'
        return backup_account

    def get_account_runtime_snapshot(self):
        snapshot = {}
        for account in self.accounts:
            snapshot[account['name']] = {
                'role': account.get('role', 'primary'),
                'runtime_state': account.get('runtime_state', 'active'),
                'requests': account['request_count'],
                'probe_count': account.get('probe_count', 0),
                'block_count': account.get('block_count', 0),
                'blocked': account['is_blocked'],
                'block_until': account['block_until'].strftime('%H:%M:%S') if account['block_until'] else None,
                'suspected_count': account.get('suspected_count', 0)
            }
        return snapshot

    async def connect_all(self):
        """连接所有账号"""
        print(f"🔗 正在连接 {len(self.accounts)} 个账号...")

        for account in self.accounts:
            try:
                proxy_config = build_proxy_config(account.get('proxy'))
                if proxy_config:
                    print(f"  {account['name']} 使用代理: {proxy_config[1]}:{proxy_config[2]}")
                else:
                    print(f"  ⚠️  {account['name']} 未配置代理，直连 Telegram")

                fp = resolve_device_profile(account)

                client = TelegramClient(
                    _get_session_path(account['name']),
                    account['api_id'],
                    account['api_hash'],
                    proxy=proxy_config,
                    **fp,
                )
                await client.connect()

                if not await client.is_user_authorized():
                    raise RuntimeError(
                        f"账号 {account['name']} ({account['phone']}) 需要先在终端登录。"
                        f"请运行: python3 login.py"
                    )

                # 真正验证代理+登录都 OK：调一次 get_me()，失败立即暴露代理/网络问题
                try:
                    me = await client.get_me()
                    if me is None:
                        raise RuntimeError("get_me() 返回空")
                except Exception as ge:
                    raise RuntimeError(f"账号验证失败（代理或网络问题）: {ge}")

                account['client'] = client
                print(f"✅ {account['name']} 已连接 | 指纹: {fp['device_model']} | @{getattr(me, 'username', None) or me.phone}")

            except Exception as e:
                print(f"❌ {account['name']} 连接失败: {e}")

    async def _login_account(self, client, phone):
        """登录单个账号"""
        await client.send_code_request(phone)
        code = input(f'请输入 {phone} 的验证码: ')

        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input(f'{phone} 需要两步验证密码: ')
            await client.sign_in(password=password)

    def get_next_account(self):
        """获取下一个可用账号（轮换策略）"""
        attempts = 0
        max_attempts = len(self.accounts) * 2

        while attempts < max_attempts:
            account = self.accounts[self.current_index]

            # 检查账号是否被封禁
            if account['is_blocked']:
                if datetime.now() > account['block_until']:
                    account['is_blocked'] = False
                    account['request_count'] = 0
                else:
                    self.current_index = (self.current_index + 1) % len(self.accounts)
                    attempts += 1
                    continue

            # 检查请求次数限制
            if account['request_count'] >= self.rate_config['requests_per_account']:
                print(f"⚠️  {account['name']} 达到请求限制，切换账号")
                self.current_index = (self.current_index + 1) % len(self.accounts)
                attempts += 1
                continue

            # 找到可用账号
            return account

        raise Exception("所有账号都不可用，请稍后再试")

    def mark_account_used(self, account):
        """标记账号已使用"""
        account['request_count'] += 1
        account['last_request_time'] = datetime.now()
        self.account_stats[account['name']]['total_requests'] += 1

    def mark_account_error(self, account, error_type='general'):
        """标记账号出错"""
        self.account_stats[account['name']]['errors'] += 1

        if isinstance(error_type, FloodWaitError):
            # 触发速率限制：指数退避，避免反复触发
            # block_count 越高冷却越久，封顶 2 小时
            wait_seconds = error_type.seconds
            block_count = account.get('block_count', 0)
            backoff_multiplier = 2 ** min(block_count, 6)  # 最多 64x
            cooldown = min(wait_seconds * backoff_multiplier, 2 * 3600)
            account['is_blocked'] = True
            account['block_until'] = datetime.now() + timedelta(seconds=cooldown)
            account['block_count'] = block_count + 1
            print(
                f"🚫 {account['name']} 触发速率限制（原始 {wait_seconds}s × {backoff_multiplier}），"
                f"实际冷却 {cooldown}s（累计 {account['block_count']} 次）"
            )

    def mark_account_success(self, account):
        """标记账号成功"""
        self.account_stats[account['name']]['success'] += 1

    def should_switch_account(self, account):
        """判断是否应该切换账号"""
        # 达到单账号请求限制
        if account['request_count'] >= self.rate_config['requests_per_account']:
            return True

        # 距离上次请求时间过短
        if account['last_request_time']:
            elapsed = (datetime.now() - account['last_request_time']).total_seconds()
            if elapsed < self.rate_config['min_delay']:
                return True

        return False

    async def disconnect_all(self):
        """断开所有账号"""
        for account in self.accounts:
            if account['client']:
                await account['client'].disconnect()

    def print_stats(self):
        """打印账号使用统计"""
        print("\n" + "="*60)
        print("📊 账号使用统计")
        print("="*60)
        for name, stats in self.account_stats.items():
            success_rate = (stats['success'] / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
            print(f"{name}:")
            print(f"  总请求: {stats['total_requests']}")
            print(f"  成功: {stats['success']}")
            print(f"  失败: {stats['errors']}")
            print(f"  成功率: {success_rate:.1f}%")
        print("="*60 + "\n")
