#!/usr/bin/env python3
"""
Telegram筛号工具 - PyQt5版本（带实时监控）
"""
import sys
import json
import os
import asyncio
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QTabWidget,
    QGroupBox, QFormLayout, QRadioButton, QButtonGroup,
    QFileDialog, QMessageBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QMenu
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import QFont, QColor
from telethon.errors import PhoneNumberInvalidError

def get_config_path():
    """获取 config.json 路径，支持 EXE 打包和相对路径"""
    # EXE 打包时：资源文件在 sys._MEIPASS 目录
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'config.json')

config_path = get_config_path()


def translate_error_message(message):
    text = str(message)
    mappings = [
        ("The phone number is invalid", "手机号无效，请检查国家区号和号码位数"),
        ("Connection to Telegram failed 5 time(s)", "连接 Telegram 失败，请检查网络或代理设置"),
        ("Connection to Telegram failed", "连接 Telegram 失败，请检查网络或代理设置"),
        ("No module named 'socks'", "缺少代理模块 pysocks，请先安装"),
        ("All offered SOCKS5 authentication methods were rejected", "代理认证失败，请检查代理账号或密码"),
        ("timed out", "连接超时，请检查网络或代理"),
        ("TimeoutError", "连接超时，请检查网络或代理"),
        ("SendCodeRequest", "发送验证码失败"),
        ("OSError", "网络连接错误，请检查防火墙或网络设置"),
        ("Cannot find any entity", "无法找到该用户"),
    ]

    for src, dst in mappings:
        text = text.replace(src, dst)
    return text

def load_config():
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"accounts": [], "rate_limit": {"requests_per_account": 30, "min_delay": 3, "max_delay": 8}}

def save_config(config):
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


class LoginThread(QThread):
    status_signal = pyqtSignal(dict)
    code_requested = pyqtSignal(str)
    password_requested = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, account):
        super().__init__()
        self.account = account
        self.code = None
        self.password = None
        self._loop = None
        self._future = None

    def set_code(self, code):
        self.code = code
        if self._loop and self._future and not self._future.done():
            self._loop.call_soon_threadsafe(self._future.set_result, code)

    def set_password(self, password):
        self.password = password
        if self._loop and self._future and not self._future.done():
            self._loop.call_soon_threadsafe(self._future.set_result, password)

    def run(self):
        try:
            asyncio.run(self.login_task())
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    async def wait_for_input(self):
        self._loop = asyncio.get_running_loop()
        self._future = self._loop.create_future()
        return await self._future

    async def login_task(self):
        from telethon import TelegramClient
        from telethon.errors import SessionPasswordNeededError

        proxy = self.account.get('proxy', {})
        proxy_config = None
        if proxy and proxy.get('host'):
            proxy_config = ('socks5', proxy['host'], proxy['port'],
                          proxy.get('username') or None, proxy.get('password') or None)

        client = TelegramClient(
            f"session_{self.account['name']}",
            int(self.account['api_id']),
            self.account['api_hash'],
            proxy=proxy_config
        )

        fallback_client = None

        try:
            try:
                await client.connect()
            except Exception:
                if proxy_config:
                    fallback_client = TelegramClient(
                        f"session_{self.account['name']}",
                        int(self.account['api_id']),
                        self.account['api_hash']
                    )
                    await fallback_client.connect()
                    client = fallback_client
                else:
                    raise

            if not client.is_connected():
                raise RuntimeError('连接到 Telegram 失败')

            if await client.is_user_authorized():
                self.status_signal.emit({self.account['name']: {'login_state': 'logged_in'}})
                self.finished_signal.emit(True, '已登录')
                return

            self.status_signal.emit({self.account['name']: {'login_state': 'logging_in'}})
            await client.send_code_request(self.account['phone'])
            self.code_requested.emit(self.account['phone'])
            code = await self.wait_for_input()

            try:
                await client.sign_in(self.account['phone'], code)
            except SessionPasswordNeededError:
                self.password_requested.emit(self.account['phone'])
                password = await self.wait_for_input()
                await client.sign_in(password=password)

            self.status_signal.emit({self.account['name']: {'login_state': 'logged_in'}})
            self.finished_signal.emit(True, '登录成功')
        except PhoneNumberInvalidError:
            self.status_signal.emit({self.account['name']: {'login_state': 'failed', 'error': '手机号无效，请检查国家区号和号码位数'}})
            self.finished_signal.emit(False, '手机号无效，请检查国家区号和号码位数')
        except Exception as e:
            error_msg = translate_error_message(str(e))
            self.status_signal.emit({self.account['name']: {'login_state': 'failed', 'error': error_msg}})
            self.finished_signal.emit(False, error_msg)
        finally:
            await client.disconnect()
            if fallback_client and fallback_client is not client:
                await fallback_client.disconnect()


class AccountCheckThread(QThread):
    status_signal = pyqtSignal(dict)
    log_signal = pyqtSignal(str)

    def __init__(self, accounts):
        super().__init__()
        self.accounts = accounts

    def run(self):
        try:
            asyncio.run(self.check_accounts())
        except Exception as e:
            self.log_signal.emit(f"❌ 账号检测失败: {translate_error_message(str(e))}")

    async def check_accounts(self):
        from telethon import TelegramClient

        for account in self.accounts:
            name = account['name']
            status = {
                'login_state': 'not_logged_in',
                'proxy_state': 'not_configured'
            }

            proxy = account.get('proxy', {})
            proxy_config = None
            if proxy and proxy.get('host'):
                proxy_config = ('socks5', proxy['host'], proxy['port'],
                              proxy.get('username') or None, proxy.get('password') or None)
                proxy_client = None
                try:
                    proxy_client = TelegramClient(
                        f"session_{name}_proxy_check",
                        int(account['api_id']),
                        account['api_hash'],
                        proxy=proxy_config
                    )
                    await proxy_client.connect()
                    if proxy_client.is_connected():
                        status['proxy_state'] = 'proxy_ok'
                        self.log_signal.emit(f"🟢 账号 {name} 代理连接成功")
                    else:
                        status['proxy_state'] = 'proxy_failed'
                        status['proxy_error'] = '代理连接失败'
                        self.log_signal.emit(f"🔴 账号 {name} 代理连接失败")
                except Exception as e:
                    status['proxy_state'] = 'proxy_failed'
                    status['proxy_error'] = translate_error_message(str(e))
                    self.log_signal.emit(f"🔴 账号 {name} 代理失败: {status['proxy_error']}")
                finally:
                    if proxy_client:
                        await proxy_client.disconnect()
            else:
                self.log_signal.emit(f"⚪ 账号 {name} 未配置代理")

            client = TelegramClient(
                f"session_{name}",
                int(account['api_id']),
                account['api_hash'],
                proxy=proxy_config
            )
            try:
                await client.connect()
                if not client.is_connected():
                    status['login_state'] = 'failed'
                    status['login_error'] = '连接 Telegram 失败'
                    self.log_signal.emit(f"🔴 账号 {name} 登录检测失败: 连接 Telegram 失败")
                elif await client.is_user_authorized():
                    status['login_state'] = 'logged_in'
                    self.log_signal.emit(f"🟢 账号 {name} 已登录")
                else:
                    status['login_state'] = 'not_logged_in'
                    self.log_signal.emit(f"⚪ 账号 {name} 未登录")
            except Exception as e:
                status['login_state'] = 'failed'
                status['login_error'] = translate_error_message(str(e))
                self.log_signal.emit(f"🔴 账号 {name} 登录状态异常: {status['login_error']}")
            finally:
                await client.disconnect()

            self.status_signal.emit({name: status})


class FilterThread(QThread):
    """后台筛选线程"""
    REGISTERED_CHUNK_SIZE = 200
    PROGRESS_FILE = 'filter_progress.json'
    MAX_RETRIES = 3
    EMPTY_RESULT_RETRIES = 2
    PROBE_FAILURE_THRESHOLD = 2
    RECENT_SECTION_TITLE = '近期在线'
    MID_SECTION_TITLE = '一个月到半年在线'
    OLD_SECTION_TITLE = '长期未在线'

    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(dict)  # 账号状态更新
    finished_signal = pyqtSignal()
    probe_signal = pyqtSignal(str, str, int, int)  # (phone, status, current_idx, total)
    conflict_signal = pyqtSignal(dict)
    emergency_pause_signal = pyqtSignal(dict)

    def __init__(self, phones, country, config, probe_interval=0, probe_phones=None):
        super().__init__()
        self.phones = phones
        self.country = country
        self.config = config
        self.running = True
        self.probe_interval = probe_interval  # 每隔多少个号查一次探针
        self.probe_phones = probe_phones or []  # 探针号码列表

    def run(self):
        """在后台运行筛选任务"""
        try:
            asyncio.run(self.filter_task())
        except Exception as e:
            self.log_signal.emit(f"❌ 错误: {str(e)}")
        finally:
            self.finished_signal.emit()

    def get_display_phone(self, result, fallback_phone):
        original_phone = result.get('original_phone') or fallback_phone
        formatted_phone = result.get('phone') or fallback_phone
        return formatted_phone if formatted_phone == original_phone else f"{original_phone} -> {formatted_phone}"

    async def query_with_account(self, filter_obj, account, phone, country):
        original_manager = filter_obj.manager
        proxy_manager = type('SingleAccountManager', (), {'get_next_account': lambda self: account})()
        filter_obj.manager = proxy_manager
        try:
            return await self.resolve_phone_result(filter_obj, phone, country)
        finally:
            filter_obj.manager = original_manager

    async def handle_account_conflict(self, manager, filter_obj, failed_account, successful_account, phone, base_result, index, total):
        manager.mark_account_suspected(failed_account, f"conflict_with:{successful_account['name']}")
        failed_name = failed_account['name']
        success_name = successful_account['name']
        display_phone = self.get_display_phone(base_result, phone)
        self.log_signal.emit(f"  ⚠️ 账号冲突 | {failed_name} 未命中，{success_name} 命中 | {display_phone}")

        backups = manager.get_available_backup_accounts()
        verification_log = []

        for backup in backups[:2]:
            verify_result = await self.query_with_account(filter_obj, backup, phone, self.country)
            verify_display = self.get_display_phone(verify_result, phone)
            verification_log.append({
                'account': backup['name'],
                'registered': verify_result.get('registered', False),
                'display_phone': verify_display,
                'query_state': verify_result.get('query_state'),
                'error': verify_result.get('error')
            })

            if verify_result.get('registered'):
                manager.replace_primary_account(failed_account, backup, f"verified_by:{backup['name']}")
                self.log_signal.emit(f"  🔁 替换账号 | {failed_name} 下线，{backup['name']} 接替 | {verify_display}")
                return {'action': 'replaced', 'replacement': backup['name'], 'verification_log': verification_log}

            self.log_signal.emit(f"  ⚠️ 备用复核失败 | {backup['name']} 未命中 | {verify_display}")

        all_results = []
        for account in manager.get_active_primary_accounts():
            verify_result = await self.query_with_account(filter_obj, account, phone, self.country)
            all_results.append({
                'account': account['name'],
                'registered': verify_result.get('registered', False),
                'display_phone': self.get_display_phone(verify_result, phone),
                'query_state': verify_result.get('query_state'),
                'error': verify_result.get('error')
            })

        any_registered = any(item['registered'] for item in all_results)
        payload = {
            'phone': phone,
            'display_phone': display_phone,
            'failed_account': failed_name,
            'successful_account': success_name,
            'backup_results': verification_log,
            'all_results': all_results,
            'index': index,
            'total': total
        }

        if not any_registered:
            self.running = False
            self.emergency_pause_signal.emit(payload)
            self.log_signal.emit(f"  ⛔ 紧急暂停 | 所有工作号都未命中 | {display_phone}")
            return {'action': 'paused', 'verification_log': verification_log, 'all_results': all_results}

        self.conflict_signal.emit(payload)
        self.log_signal.emit(f"  ⚠️ 冲突保留 | 部分账号命中，已弹窗提示 | {display_phone}")
        return {'action': 'conflict', 'verification_log': verification_log, 'all_results': all_results}

    def build_registered_entry(self, result):
        return {
            'phone': result.get('phone'),
            'status': result.get('status'),
            'last_seen': result.get('last_seen')
        }

    def classify_activity_group(self, entry):
        status = entry.get('status')
        last_seen = entry.get('last_seen')

        if status in {'online', 'recently', 'within_week', 'within_month'}:
            return self.RECENT_SECTION_TITLE

        if status == 'offline' and last_seen:
            try:
                last_seen_dt = datetime.strptime(last_seen, '%Y-%m-%d %H:%M:%S')
                days = (datetime.now() - last_seen_dt).days
                if days <= 31:
                    return self.RECENT_SECTION_TITLE
                if days <= 183:
                    return self.MID_SECTION_TITLE
            except ValueError:
                pass

        return self.OLD_SECTION_TITLE

    def format_registered_line(self, entry):
        phone = entry.get('phone') or ''
        status = entry.get('status') or 'unknown'
        last_seen = entry.get('last_seen')

        if last_seen:
            return f"{phone} | {status} | {last_seen}"
        return f"{phone} | {status}"

    def format_registered_chunk(self, entries):
        grouped = {
            self.RECENT_SECTION_TITLE: [],
            self.MID_SECTION_TITLE: [],
            self.OLD_SECTION_TITLE: []
        }

        for entry in entries:
            group = self.classify_activity_group(entry)
            phone = entry.get('phone')
            if phone:
                grouped[group].append(self.format_registered_line(entry))

        sections = []
        for title in [self.RECENT_SECTION_TITLE, self.MID_SECTION_TITLE, self.OLD_SECTION_TITLE]:
            sections.append(title)
            sections.extend(grouped[title])
            sections.append('')

        return '\n'.join(sections).rstrip() + '\n'

    def save_registered_chunk(self, entries, file_index):
        filename = f"registered_{file_index:03d}.txt"
        content = self.format_registered_chunk(entries)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        self.log_signal.emit(f"💾 已保存 {filename}（{len(entries)} 个已注册号码）")

    def load_progress(self):
        if not os.path.exists(self.PROGRESS_FILE):
            return None
        try:
            with open(self.PROGRESS_FILE, 'r', encoding='utf-8') as f:
                progress = json.load(f)
            if progress.get('phones') != self.phones:
                return None
            return progress
        except Exception:
            return None

    def save_progress(self, next_index, registered_count, unregistered_count, registered_batch, registered_file_index, uncertain_count=0, environment_unstable=False, probe_failure_count=0):
        progress = {
            'phones': self.phones,
            'next_index': next_index,
            'registered_count': registered_count,
            'unregistered_count': unregistered_count,
            'uncertain_count': uncertain_count,
            'registered_batch': registered_batch,
            'registered_file_index': registered_file_index,
            'environment_unstable': environment_unstable,
            'probe_failure_count': probe_failure_count,
            'country': self.country,
            'probe_interval': self.probe_interval,
            'probe_phones': self.probe_phones,
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(self.PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def clear_progress(self):
        if os.path.exists(self.PROGRESS_FILE):
            os.remove(self.PROGRESS_FILE)

    async def reconnect_manager(self, manager):
        self.log_signal.emit('🔄 连接中断，正在自动重连...')
        await manager.disconnect_all()
        await manager.connect_all()
        if not any(acc.get('client') for acc in manager.accounts):
            raise RuntimeError('自动重连失败，当前没有可用账号')
        self.log_signal.emit('✅ 自动重连成功，继续筛选')

    async def resolve_phone_result(self, filter_obj, phone, country):
        attempts = []
        max_attempts = self.EMPTY_RESULT_RETRIES + 1

        for attempt in range(1, max_attempts + 1):
            result = await filter_obj.check_phone(phone, country)
            attempts.append(result)
            if result.get('registered'):
                if attempt > 1:
                    result['recovered_after_retry'] = True
                    result['retry_attempts'] = attempt
                return result

            if result.get('query_state') != 'empty_result':
                result['retry_attempts'] = attempt
                return result

            if attempt < max_attempts:
                self.log_signal.emit(f"  🔄 空返回复查 {attempt}/{self.EMPTY_RESULT_RETRIES}")

        final_result = attempts[-1]
        final_result['retry_attempts'] = max_attempts
        final_result['query_state'] = 'uncertain'
        final_result['error'] = '连续空返回，结果未确认'
        return final_result

    def describe_non_registered_result(self, result, environment_unstable):
        query_state = result.get('query_state')
        if query_state == 'invalid':
            return 'invalid', '号码无效'
        if query_state == 'rate_limited':
            return 'uncertain', result.get('error') or '触发速率限制'
        if query_state == 'query_failed':
            return 'uncertain', result.get('error') or '查询失败'
        if query_state in {'empty_result', 'uncertain'}:
            if environment_unstable:
                return 'uncertain', '查询环境不稳定，结果未确认'
            return 'uncertain', result.get('error') or '查询未返回用户'
        if query_state == 'unregistered':
            return 'unregistered', result.get('error') or '未注册Telegram'
        return 'uncertain', result.get('error') or '结果未确认'

    async def filter_task(self):
        """异步筛选任务"""
        from account_manager import AccountManager
        from filter import TelegramFilter
        from rate_limiter import RateLimiter

        self.log_signal.emit(f"🚀 开始筛选 {len(self.phones)} 个号码")

        # 初始化管理器
        manager = AccountManager(config_path)
        await manager.connect_all()

        limiter = RateLimiter(self.config['rate_limit'])
        filter_obj = TelegramFilter(manager, limiter)

        results = []
        progress = self.load_progress()
        start_index = 0
        registered_count = 0
        unregistered_count = 0
        uncertain_count = 0
        registered_batch = []
        registered_file_index = 1
        environment_unstable = False
        probe_failure_count = 0

        if progress:
            start_index = progress.get('next_index', 0)
            registered_count = progress.get('registered_count', 0)
            unregistered_count = progress.get('unregistered_count', 0)
            uncertain_count = progress.get('uncertain_count', 0)
            registered_batch = progress.get('registered_batch', [])
            registered_file_index = progress.get('registered_file_index', 1)
            environment_unstable = progress.get('environment_unstable', False)
            probe_failure_count = progress.get('probe_failure_count', 0)
            if start_index > 0:
                self.log_signal.emit(f"📂 检测到上次进度，从第 {start_index + 1} 条继续")

        for i in range(start_index, len(self.phones)):
            phone = self.phones[i]
            if not self.running:
                break

            self.log_signal.emit(f"[{i+1}/{len(self.phones)}] 检查 {phone}")

            for attempt in range(1, self.MAX_RETRIES + 1):
                try:
                    result = await self.resolve_phone_result(filter_obj, phone, self.country)
                    results.append(result)

                    status = self.get_account_status(manager)
                    self.status_signal.emit(status)

                    display_phone = self.get_display_phone(result, phone)

                    if result['registered']:
                        registered_count += 1
                        registered_batch.append(self.build_registered_entry(result))
                        if len(registered_batch) >= self.REGISTERED_CHUNK_SIZE:
                            self.save_registered_chunk(registered_batch, registered_file_index)
                            registered_batch = []
                            registered_file_index += 1

                        status_text = result.get('status') or 'unknown'
                        last_seen = result.get('last_seen')
                        retry_suffix = ''
                        if result.get('recovered_after_retry'):
                            retry_suffix = f" | 复查后成功({result.get('retry_attempts')})"
                        if last_seen:
                            self.log_signal.emit(f"  ✅ 已注册 | {display_phone} | {status_text} | {last_seen}{retry_suffix}")
                        else:
                            self.log_signal.emit(f"  ✅ 已注册 | {display_phone} | {status_text}{retry_suffix}")
                    else:
                        active_primary = manager.get_active_primary_accounts()
                        conflict_handled = False
                        if len(active_primary) >= 2:
                            first_primary = active_primary[0]
                            second_primary = active_primary[1]
                            second_result = await self.query_with_account(filter_obj, second_primary, phone, self.country)
                            if second_result.get('registered'):
                                conflict_handled = True
                                registered_count += 1
                                registered_batch.append(self.build_registered_entry(second_result))
                                if len(registered_batch) >= self.REGISTERED_CHUNK_SIZE:
                                    self.save_registered_chunk(registered_batch, registered_file_index)
                                    registered_batch = []
                                    registered_file_index += 1

                                second_display_phone = self.get_display_phone(second_result, phone)
                                second_status = second_result.get('status') or 'unknown'
                                second_last_seen = second_result.get('last_seen')
                                if second_last_seen:
                                    self.log_signal.emit(f"  ✅ 复核命中 | {second_primary['name']} | {second_display_phone} | {second_status} | {second_last_seen}")
                                else:
                                    self.log_signal.emit(f"  ✅ 复核命中 | {second_primary['name']} | {second_display_phone} | {second_status}")

                                await self.handle_account_conflict(
                                    manager,
                                    filter_obj,
                                    first_primary,
                                    second_primary,
                                    phone,
                                    second_result,
                                    i + 1,
                                    len(self.phones)
                                )
                            elif len(active_primary) >= 3:
                                third_primary = active_primary[2]
                                third_result = await self.query_with_account(filter_obj, third_primary, phone, self.country)
                                if third_result.get('registered'):
                                    conflict_handled = True
                                    manager.mark_account_suspected(second_primary, f"miss_before:{third_primary['name']}")
                                    registered_count += 1
                                    registered_batch.append(self.build_registered_entry(third_result))
                                    if len(registered_batch) >= self.REGISTERED_CHUNK_SIZE:
                                        self.save_registered_chunk(registered_batch, registered_file_index)
                                        registered_batch = []
                                        registered_file_index += 1

                                    third_display_phone = self.get_display_phone(third_result, phone)
                                    third_status = third_result.get('status') or 'unknown'
                                    third_last_seen = third_result.get('last_seen')
                                    if third_last_seen:
                                        self.log_signal.emit(f"  ✅ 三级复核命中 | {first_primary['name']} 未命中 -> {second_primary['name']} 未命中 -> {third_primary['name']} 命中 | {third_display_phone} | {third_status} | {third_last_seen}")
                                    else:
                                        self.log_signal.emit(f"  ✅ 三级复核命中 | {first_primary['name']} 未命中 -> {second_primary['name']} 未命中 -> {third_primary['name']} 命中 | {third_display_phone} | {third_status}")

                                    await self.handle_account_conflict(
                                        manager,
                                        filter_obj,
                                        first_primary,
                                        third_primary,
                                        phone,
                                        third_result,
                                        i + 1,
                                        len(self.phones)
                                    )
                                else:
                                    classification, message = self.describe_non_registered_result(result, environment_unstable)
                                    if classification == 'unregistered':
                                        unregistered_count += 1
                                        self.log_signal.emit(f"  ❌ 未注册 | {display_phone} | {message}")
                                    elif classification == 'invalid':
                                        self.log_signal.emit(f"  ⚠️ 号码无效 | {display_phone}")
                                    else:
                                        uncertain_count += 1
                                        self.log_signal.emit(f"  ❓ 未确认 | {display_phone} | {message}")
                            else:
                                classification, message = self.describe_non_registered_result(result, environment_unstable)
                                if classification == 'unregistered':
                                    unregistered_count += 1
                                    self.log_signal.emit(f"  ❌ 未注册 | {display_phone} | {message}")
                                elif classification == 'invalid':
                                    self.log_signal.emit(f"  ⚠️ 号码无效 | {display_phone}")
                                else:
                                    uncertain_count += 1
                                    self.log_signal.emit(f"  ❓ 未确认 | {display_phone} | {message}")
                        if not active_primary or (len(active_primary) < 2 and not conflict_handled):
                            classification, message = self.describe_non_registered_result(result, environment_unstable)
                            if classification == 'unregistered':
                                unregistered_count += 1
                                self.log_signal.emit(f"  ❌ 未注册 | {display_phone} | {message}")
                            elif classification == 'invalid':
                                self.log_signal.emit(f"  ⚠️ 号码无效 | {display_phone}")
                            elif not conflict_handled:
                                uncertain_count += 1
                                self.log_signal.emit(f"  ❓ 未确认 | {display_phone} | {message}")

                    self.save_progress(
                        i + 1,
                        registered_count,
                        unregistered_count,
                        registered_batch,
                        registered_file_index,
                        uncertain_count,
                        environment_unstable,
                        probe_failure_count
                    )
                    break
                except Exception as e:
                    error_text = str(e)
                    if attempt < self.MAX_RETRIES and any(key in error_text.lower() for key in ['reset by peer', 'server closed', 'timed out', 'connection', 'timeout']):
                        self.log_signal.emit(f"  ⚠️ 网络异常，第 {attempt} 次重试")
                        await self.reconnect_manager(manager)
                        continue
                    self.log_signal.emit(f"  ⚠️ 错误: {error_text}")
                    self.save_progress(
                        i,
                        registered_count,
                        unregistered_count,
                        registered_batch,
                        registered_file_index,
                        uncertain_count,
                        environment_unstable,
                        probe_failure_count
                    )
                    await manager.disconnect_all()
                    return

            # ── 探针验证：每隔 N 个号静默检查一次 ──
            if self.running and self.probe_interval > 0 and self.probe_phones:
                probe_idx = (i + 1) // self.probe_interval
                if (i + 1) % self.probe_interval == 0 and probe_idx > 0:
                    probe_phone = self.probe_phones[(probe_idx - 1) % len(self.probe_phones)]
                    self.log_signal.emit(f"[探针{probe_idx}] 验证 {probe_phone}...")
                    try:
                        probe_result = await self.resolve_phone_result(filter_obj, probe_phone, self.country)
                        probe_original = probe_result.get('original_phone') or probe_phone
                        probe_formatted = probe_result.get('phone') or probe_phone
                        probe_display = probe_formatted if probe_formatted == probe_original else f"{probe_original} -> {probe_formatted}"
                        if probe_result['registered']:
                            probe_failure_count = 0
                            if environment_unstable:
                                self.log_signal.emit(f"  [探针{probe_idx}] ✅ {probe_display} 已恢复正常")
                            else:
                                self.log_signal.emit(f"  [探针{probe_idx}] ✅ {probe_display} 已注册（正常）")
                            environment_unstable = False
                        else:
                            probe_failure_count += 1
                            environment_unstable = probe_failure_count >= self.PROBE_FAILURE_THRESHOLD
                            _, probe_message = self.describe_non_registered_result(probe_result, environment_unstable)
                            self.log_signal.emit(f"  [探针{probe_idx}] ❓ {probe_display} 未确认 | {probe_message}")
                            if environment_unstable:
                                self.log_signal.emit(f"  [探针{probe_idx}] ⚠️ 当前查询环境已标记为不稳定")
                    except Exception as e:
                        probe_failure_count += 1
                        environment_unstable = probe_failure_count >= self.PROBE_FAILURE_THRESHOLD
                        self.log_signal.emit(f"  [探针{probe_idx}] ⚠️ {probe_phone} 网络异常: {e}")

        if registered_batch:
            self.save_registered_chunk(registered_batch, registered_file_index)

        await manager.disconnect_all()
        self.clear_progress()
        self.log_signal.emit(
            f"✅ 筛选完成！共 {len(self.phones)} 个号码，已注册 {registered_count} 个，未确认 {uncertain_count} 个，未注册 {unregistered_count} 个"
        )

    def get_account_status(self, manager):
        """获取所有账号的状态"""
        return manager.get_account_runtime_snapshot()

    def stop(self):
        self.running = False


class TelegramFilterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.filter_thread = None
        self.login_thread = None
        self.account_check_thread = None
        self.account_status = {}
        self.editing_account_name = None
        self.load_account_login_status()
        self.init_ui()

        # 定时器：每秒更新账号状态
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_account_display)
        self.timer.start(1000)

        # 启动时检查登录状态
        QTimer.singleShot(500, self.check_initial_login)

    def load_account_login_status(self):
        for acc in self.config.get('accounts', []):
            session_file = f"session_{acc['name']}.session"
            self.account_status[acc['name']] = {
                'login_state': 'logged_in' if os.path.exists(session_file) else 'not_logged_in',
                'proxy_state': 'not_configured'
            }

    def init_ui(self):
        self.setWindowTitle("Telegram 筛号工具")
        self.setGeometry(100, 100, 1200, 700)

        # 主容器
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 顶部标题
        header = QLabel("🚀 Telegram 筛号工具")
        header.setFont(QFont('Arial', 18, QFont.Bold))
        header.setStyleSheet("background: #2196F3; color: white; padding: 15px;")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # 标签页
        tabs = QTabWidget()
        tabs.addTab(self.create_filter_tab(), "📱 筛选")
        tabs.addTab(self.create_account_tab(), "👤 账号管理")
        tabs.addTab(self.create_settings_tab(), "⚙️ 设置")
        main_layout.addWidget(tabs)

    def create_filter_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 左侧
        left = QWidget()
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("📞 手机号列表（每行一个）"))
        self.phone_text = QTextEdit()
        self.phone_text.setFont(QFont('Consolas', 10))
        left_layout.addWidget(self.phone_text)

        # 按钮
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("📂 从文件导入")
        import_btn.clicked.connect(self.import_phones)
        btn_layout.addWidget(import_btn)

        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.clicked.connect(lambda: self.phone_text.clear())
        btn_layout.addWidget(clear_btn)
        left_layout.addLayout(btn_layout)

        # 国家选择
        country_group = QGroupBox("🌍 目标国家")
        country_layout = QHBoxLayout()
        self.country_group = QButtonGroup()
        us_radio = QRadioButton("🇺🇸 美国")
        us_radio.setChecked(True)
        cn_radio = QRadioButton("🇨🇳 中国")
        self.country_group.addButton(us_radio, 0)
        self.country_group.addButton(cn_radio, 1)
        country_layout.addWidget(us_radio)
        country_layout.addWidget(cn_radio)
        country_group.setLayout(country_layout)
        left_layout.addWidget(country_group)

        # 探针验证设置
        probe_group = QGroupBox("🔍 探针验证（防止批量误判）")
        probe_layout = QVBoxLayout()

        probe_top = QHBoxLayout()
        probe_top.addWidget(QLabel("每隔"))
        self.probe_interval_spin = QSpinBox()
        self.probe_interval_spin.setRange(0, 500)
        self.probe_interval_spin.setValue(20)
        self.probe_interval_spin.setToolTip("填 0 表示关闭探针验证")
        probe_top.addWidget(self.probe_interval_spin)
        probe_top.addWidget(QLabel(" 个号验证一次探针"))
        probe_top.addStretch()
        probe_layout.addLayout(probe_top)

        probe_tip = QLabel("探针号码（已知已注册的号，每行一个，不出现在日志和结果中）:")
        probe_tip.setStyleSheet("color: #666; font-size: 11px;")
        probe_layout.addWidget(probe_tip)
        self.probe_phones_text = QTextEdit()
        self.probe_phones_text.setPlaceholderText("+12025551234\n+8613800138000")
        self.probe_phones_text.setMaximumHeight(70)
        self.probe_phones_text.setFont(QFont('Consolas', 9))
        probe_layout.addWidget(self.probe_phones_text)

        probe_group.setLayout(probe_layout)
        left_layout.addWidget(probe_group)

        # 开始/停止按钮 + 继续筛选按钮
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("🚀 开始筛选")
        self.start_btn.setFont(QFont('Arial', 13, QFont.Bold))
        self.start_btn.setStyleSheet("background: #4CAF50; color: white; padding: 10px;")
        self.start_btn.clicked.connect(self.start_filtering)
        btn_row.addWidget(self.start_btn)

        self.resume_btn = QPushButton("📂 继续筛选")
        self.resume_btn.setFont(QFont('Arial', 11, QFont.Bold))
        self.resume_btn.setStyleSheet("background: #2196F3; color: white; padding: 10px;")
        self.resume_btn.clicked.connect(self.resume_filtering)
        self.resume_btn.hide()  # 默认隐藏
        btn_row.addWidget(self.resume_btn)

        left_layout.addLayout(btn_row)

        # 检查是否有可恢复的进度
        self._update_resume_button()

        # 右侧日志
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("📝 运行日志"))
        self.log_text = QTextEdit()
        self.log_text.setFont(QFont('Consolas', 9))
        self.log_text.setReadOnly(True)
        right_layout.addWidget(self.log_text)

        layout.addWidget(left, 1)
        layout.addWidget(right, 1)

        self.log("✅ GUI已启动")
        self.start_account_check()
        return widget

    def create_account_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 顶部：账号状态表格
        layout.addWidget(QLabel("📊 账号状态监控"))

        self.account_table = QTableWidget()
        self.account_table.setColumnCount(9)
        self.account_table.setHorizontalHeaderLabels([
            "账号名称", "手机号", "请求次数", "登录状态", "代理状态", "角色", "运行状态", "封禁至", "统计"
        ])
        self.account_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.account_table.setFont(QFont('Arial', 10))
        self.account_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.account_table.customContextMenuRequested.connect(self.show_account_context_menu)
        layout.addWidget(self.account_table)

        # 删除按钮
        btn_row = QHBoxLayout()
        self.login_btn = QPushButton("🔐 登录选中账号")
        self.login_btn.setStyleSheet("background: #4CAF50; color: white; padding: 6px;")
        self.login_btn.clicked.connect(self.login_selected_account)
        btn_row.addWidget(self.login_btn)

        self.delete_btn = QPushButton("🗑️ 删除选中账号")
        self.delete_btn.setStyleSheet("background: #f44336; color: white; padding: 6px;")
        self.delete_btn.clicked.connect(self.delete_selected_account)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        # 底部：添加账号表单
        form_group = QGroupBox("➕ 添加新账号")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.name_input = QLineEdit()
        form_layout.addRow("账号名称:", self.name_input)

        self.api_id_input = QLineEdit()
        form_layout.addRow("API ID:", self.api_id_input)

        self.api_hash_input = QLineEdit()
        form_layout.addRow("API Hash:", self.api_hash_input)

        self.phone_input = QLineEdit()
        form_layout.addRow("手机号:", self.phone_input)

        # 代理设置
        proxy_label = QLabel("━━━ 代理设置（可选）━━━")
        proxy_label.setStyleSheet("color: #888; font-size: 10px;")
        form_layout.addRow("", proxy_label)

        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("如: 12.34.56.78")
        form_layout.addRow("代理IP:", self.proxy_host_input)

        self.proxy_port_input = QSpinBox()
        self.proxy_port_input.setRange(1, 65535)
        self.proxy_port_input.setValue(1080)
        form_layout.addRow("端口:", self.proxy_port_input)

        self.proxy_user_input = QLineEdit()
        self.proxy_user_input.setPlaceholderText("代理账号（可选）")
        form_layout.addRow("代理账号:", self.proxy_user_input)

        self.proxy_pass_input = QLineEdit()
        self.proxy_pass_input.setPlaceholderText("代理密码（可选）")
        self.proxy_pass_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("代理密码:", self.proxy_pass_input)

        save_btn = QPushButton("💾 保存账号")
        save_btn.setStyleSheet("background: #2196F3; color: white; padding: 8px;")
        save_btn.clicked.connect(self.save_account)
        self.save_account_btn = save_btn
        form_layout.addRow("", save_btn)

        tip = QLabel("💡 获取API: https://my.telegram.org")
        tip.setStyleSheet("color: blue;")
        form_layout.addRow("", tip)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # 初始化表格
        self.refresh_account_table()

        return widget

    def start_account_check(self):
        if self.account_check_thread and self.account_check_thread.isRunning():
            return
        self.account_check_thread = AccountCheckThread(self.config.get('accounts', []))
        self.account_check_thread.status_signal.connect(self.handle_account_check_status)
        self.account_check_thread.log_signal.connect(self.log)
        self.account_check_thread.start()

    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(50, 50, 50, 50)

        title = QLabel("⚙️ 速率控制设置")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 表单
        form = QFormLayout()
        form.setSpacing(15)

        self.req_spin = QSpinBox()
        self.req_spin.setRange(10, 100)
        self.req_spin.setValue(self.config['rate_limit']['requests_per_account'])
        self.req_spin.setFont(QFont('Arial', 11))
        form.addRow("单账号请求上限:", self.req_spin)

        self.min_spin = QSpinBox()
        self.min_spin.setRange(1, 10)
        self.min_spin.setValue(self.config['rate_limit']['min_delay'])
        self.min_spin.setFont(QFont('Arial', 11))
        form.addRow("最小延迟(秒):", self.min_spin)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(5, 30)
        self.max_spin.setValue(self.config['rate_limit']['max_delay'])
        self.max_spin.setFont(QFont('Arial', 11))
        form.addRow("最大延迟(秒):", self.max_spin)

        layout.addLayout(form)

        save_btn = QPushButton("💾 保存设置")
        save_btn.setFont(QFont('Arial', 12, QFont.Bold))
        save_btn.setStyleSheet("background: #FF9800; color: white; padding: 10px;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()
        return widget

    def import_phones(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "文本文件 (*.txt)")
        if filename:
            with open(filename, 'r') as f:
                self.phone_text.setPlainText(f.read())
            self.log(f"✅ 已导入 {filename}")

    def start_filtering(self):
        if self.filter_thread and self.filter_thread.isRunning():
            # 停止筛选
            self.filter_thread.stop()
            self.start_btn.setText("🚀 开始筛选")
            self.start_btn.setStyleSheet("background: #4CAF50; color: white; padding: 10px;")
            return

        if not self.config.get('accounts'):
            QMessageBox.critical(self, "错误", "请先在'账号管理'中添加账号")
            return

        if not any(
            self.account_status.get(name, {}).get('login_state') == 'logged_in'
            for name in self.account_status
        ):
            QMessageBox.critical(self, "错误", "请先在'账号管理'中选中账号并点击“登录选中账号”")
            return

        phones = [p.strip() for p in self.phone_text.toPlainText().split('\n') if p.strip()]
        if not phones:
            QMessageBox.critical(self, "错误", "请输入手机号")
            return

        country = "US" if self.country_group.checkedId() == 0 else "CN"

        # 读取探针配置
        probe_interval = getattr(self, 'probe_interval_spin', None) and self.probe_interval_spin.value() or 0
        probe_phones_raw = getattr(self, 'probe_phones_text', None) and self.probe_phones_text.toPlainText() or ''
        probe_phones = [p.strip() for p in probe_phones_raw.split('\n') if p.strip()]

        # 启动后台线程
        self.filter_thread = FilterThread(phones, country, self.config, probe_interval, probe_phones)
        self.filter_thread.log_signal.connect(self.log)
        self.filter_thread.status_signal.connect(self.update_account_status)
        self.filter_thread.finished_signal.connect(self.on_filter_finished)
        self.filter_thread.probe_anomaly_signal.connect(self.on_probe_anomaly)
        self.filter_thread.conflict_signal.connect(self.on_account_conflict)
        self.filter_thread.emergency_pause_signal.connect(self.on_emergency_pause)
        self.filter_thread.start()

        self.start_btn.setText("⏹️ 停止筛选")
        self.start_btn.setStyleSheet("background: #f44336; color: white; padding: 10px;")

    def _read_progress_without_phone_check(self):
        """读取进度文件（不验证手机号列表是否一致）"""
        if not os.path.exists('filter_progress.json'):
            return None
        try:
            with open('filter_progress.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _update_resume_button(self):
        """检查是否有可恢复的进度，决定是否显示继续按钮"""
        progress = self._read_progress_without_phone_check()
        if progress and progress.get('next_index', 0) < len(progress.get('phones', [])):
            saved = progress.get('next_index', 0)
            total = len(progress.get('phones', []))
            self.resume_btn.setText(f"📂 继续筛选（从第{saved}/{total}继续）")
            self.resume_btn.show()
        else:
            self.resume_btn.hide()

    def resume_filtering(self):
        """从上次中断的位置继续筛选"""
        if self.filter_thread and self.filter_thread.isRunning():
            QMessageBox.information(self, "提示", "筛选正在进行中，请先停止")
            return

        progress = self._read_progress_without_phone_check()
        if not progress:
            QMessageBox.information(self, "提示", "没有找到可恢复的进度")
            self.resume_btn.hide()
            return

        saved_phones = progress.get('phones', [])
        saved_index = progress.get('next_index', 0)
        saved_country = progress.get('country', 'US')
        saved_probe_interval = progress.get('probe_interval', 0)
        saved_probe_phones = progress.get('probe_phones', [])

        if saved_index >= len(saved_phones):
            QMessageBox.information(self, "提示", f"已处理完所有 {len(saved_phones)} 个号码，无需继续")
            self.resume_btn.hide()
            return

        # 恢复手机号列表到文本框
        self.phone_text.setPlainText('\n'.join(saved_phones))
        # 恢复国家选择
        for btn in self.country_group.buttons():
            btn.setChecked(self.country_group.id(btn) == (0 if saved_country == 'US' else 1))
        # 恢复探针配置
        if hasattr(self, 'probe_interval_spin') and saved_probe_interval > 0:
            self.probe_interval_spin.setValue(saved_probe_interval)
        if hasattr(self, 'probe_phones_text') and saved_probe_phones:
            self.probe_phones_text.setPlainText('\n'.join(saved_probe_phones))

        # 提示用户确认
        reply = QMessageBox.question(
            self, "确认继续",
            f"将跳过前 {saved_index} 个号，从第 {saved_index + 1} 个继续（共 {len(saved_phones)} 个）\n\n"
            f"探针间隔: {saved_probe_interval}\n"
            f"探针号码: {', '.join(saved_probe_phones) or '无'}\n\n"
            f"手机号列表已恢复，确认继续吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.log(f"📂 继续筛选：从第 {saved_index + 1}/{len(saved_phones)} 个开始")
        self.start_filtering()

    def on_filter_finished(self):
        self.start_btn.setText("🚀 开始筛选")
        self.start_btn.setStyleSheet("background: #4CAF50; color: white; padding: 10px;")
        self.log("🏁 筛选任务已结束")
        self._update_resume_button()

    def on_account_conflict(self, payload):
        details = []
        for item in payload.get('all_results', []):
            state = '命中' if item.get('registered') else '未命中'
            details.append(f"- {item['account']}: {state}")
        detail_text = '\n'.join(details) if details else '无'
        msg = (
            f"号码: {payload.get('display_phone')}\n"
            f"失败账号: {payload.get('failed_account')}\n"
            f"复核账号: {payload.get('successful_account')}\n\n"
            f"全体验证结果:\n{detail_text}\n\n"
            f"请决定是否继续运行或手动调整账号。"
        )
        reply = QMessageBox.question(
            self,
            "账号冲突提示",
            msg,
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No and self.filter_thread:
            self.filter_thread.stop()
            self.log("⏸️ 用户选择在账号冲突后暂停筛选")

    def on_emergency_pause(self, payload):
        details = []
        for item in payload.get('all_results', []):
            state = '命中' if item.get('registered') else '未命中'
            details.append(f"- {item['account']}: {state}")
        detail_text = '\n'.join(details) if details else '无'
        msg = (
            f"号码: {payload.get('display_phone')}\n"
            f"所有工作号都未命中，系统已紧急暂停。\n\n"
            f"全体验证结果:\n{detail_text}"
        )
        QMessageBox.critical(self, "紧急暂停", msg)
        self.log("⛔ 已触发紧急暂停，请检查账号状态")

    def check_initial_login(self):
        """启动时检查是否需要登录"""
        accounts = self.config.get('accounts', [])
        if not accounts:
            QMessageBox.information(
                self,
                '欢迎使用',
                '请先在"账号管理"标签页添加 Telegram 账号。'
            )
            return

        # 检查是否有未登录的账号
        not_logged_in = []
        for acc in accounts:
            session_file = f"session_{acc['name']}.session"
            if not os.path.exists(session_file):
                not_logged_in.append(acc)

        if not_logged_in:
            reply = QMessageBox.question(
                self,
                '账号登录',
                f'检测到 {len(not_logged_in)} 个账号未登录。\n\n是否现在登录？',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.show_login_wizard(not_logged_in)

    def show_login_wizard(self, accounts):
        """显示登录向导"""
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox

        class LoginDialog(QDialog):
            def __init__(self, parent, account):
                super().__init__(parent)
                self.account = account
                self.login_thread = None
                self.init_ui()

            def init_ui(self):
                self.setWindowTitle(f"登录账号 - {self.account['name']}")
                self.setModal(True)
                self.setMinimumWidth(400)

                layout = QVBoxLayout(self)

                # 账号信息
                info_group = QGroupBox("账号信息")
                info_layout = QFormLayout()
                info_layout.addRow("账号名称:", QLabel(self.account['name']))
                info_layout.addRow("手机号:", QLabel(self.account['phone']))
                info_group.setLayout(info_layout)
                layout.addWidget(info_group)

                # 状态显示
                self.status_label = QLabel("准备登录...")
                self.status_label.setStyleSheet("padding: 10px; background: #f0f0f0; border-radius: 5px;")
                layout.addWidget(self.status_label)

                # 验证码输入
                self.code_group = QGroupBox("验证码")
                self.code_group.setVisible(False)
                code_layout = QVBoxLayout()
                code_layout.addWidget(QLabel("请输入收到的验证码:"))
                self.code_input = QLineEdit()
                self.code_input.setPlaceholderText("例如: 12345")
                code_layout.addWidget(self.code_input)
                self.code_submit_btn = QPushButton("提交验证码")
                self.code_submit_btn.clicked.connect(self.submit_code)
                code_layout.addWidget(self.code_submit_btn)
                self.code_group.setLayout(code_layout)
                layout.addWidget(self.code_group)

                # 密码输入
                self.password_group = QGroupBox("两步验证密码")
                self.password_group.setVisible(False)
                password_layout = QVBoxLayout()
                password_layout.addWidget(QLabel("请输入两步验证密码:"))
                self.password_input = QLineEdit()
                self.password_input.setEchoMode(QLineEdit.Password)
                self.password_input.setPlaceholderText("两步验证密码")
                password_layout.addWidget(self.password_input)
                self.password_submit_btn = QPushButton("提交密码")
                self.password_submit_btn.clicked.connect(self.submit_password)
                password_layout.addWidget(self.password_submit_btn)
                self.password_group.setLayout(password_layout)
                layout.addWidget(self.password_group)

                # 按钮
                self.button_box = QDialogButtonBox()
                self.start_btn = self.button_box.addButton("开始登录", QDialogButtonBox.ActionRole)
                self.start_btn.clicked.connect(self.start_login)
                self.cancel_btn = self.button_box.addButton("取消", QDialogButtonBox.RejectRole)
                self.cancel_btn.clicked.connect(self.reject)
                layout.addWidget(self.button_box)

            def start_login(self):
                self.start_btn.setEnabled(False)
                self.status_label.setText("正在连接 Telegram...")
                self.status_label.setStyleSheet("padding: 10px; background: #fff3cd; border-radius: 5px;")

                self.login_thread = LoginThread(self.account)
                self.login_thread.code_requested.connect(self.on_code_requested)
                self.login_thread.password_requested.connect(self.on_password_requested)
                self.login_thread.finished_signal.connect(self.on_login_finished)
                self.login_thread.start()

            def on_code_requested(self, phone):
                self.status_label.setText(f"验证码已发送到 {phone}")
                self.status_label.setStyleSheet("padding: 10px; background: #d1ecf1; border-radius: 5px;")
                self.code_group.setVisible(True)
                self.code_input.setFocus()

            def on_password_requested(self, phone):
                self.status_label.setText("需要两步验证密码")
                self.status_label.setStyleSheet("padding: 10px; background: #d1ecf1; border-radius: 5px;")
                self.code_group.setVisible(False)
                self.password_group.setVisible(True)
                self.password_input.setFocus()

            def submit_code(self):
                code = self.code_input.text().strip()
                if not code:
                    QMessageBox.warning(self, "错误", "请输入验证码")
                    return
                self.code_submit_btn.setEnabled(False)
                self.status_label.setText("正在验证...")
                self.login_thread.set_code(code)

            def submit_password(self):
                password = self.password_input.text().strip()
                if not password:
                    QMessageBox.warning(self, "错误", "请输入密码")
                    return
                self.password_submit_btn.setEnabled(False)
                self.status_label.setText("正在验证...")
                self.login_thread.set_password(password)

            def on_login_finished(self, success, message):
                if success:
                    self.status_label.setText(f"✅ {message}")
                    self.status_label.setStyleSheet("padding: 10px; background: #d4edda; border-radius: 5px;")
                    QTimer.singleShot(1000, self.accept)
                else:
                    self.status_label.setText(f"❌ {message}")
                    self.status_label.setStyleSheet("padding: 10px; background: #f8d7da; border-radius: 5px;")
                    self.start_btn.setEnabled(True)
                    self.code_submit_btn.setEnabled(True)
                    self.password_submit_btn.setEnabled(True)

        # 逐个登录
        for account in accounts:
            dialog = LoginDialog(self, account)
            result = dialog.exec_()
            if result == QDialog.Rejected:
                break

        # 刷新账号状态
        self.load_account_login_status()
        if hasattr(self, 'account_table'):
            self.refresh_account_table()


    def on_probe_anomaly(self, probe_phone, current_idx, total):
        """探针异常：已知注册号码被误判，立即停止"""
        self.start_btn.setText("🚀 开始筛选")
        self.start_btn.setStyleSheet("background: #4CAF50; color: white; padding: 10px;")
        msg = (
            f"🚨 探针检测到异常！\n\n"
            f"已知已注册的探针号码：{probe_phone}\n"
            f"在第 {current_idx}/{total} 个号码时被误判为「未注册」\n\n"
            f"工具可能存在 bug 或账号被限速。\n"
            f"请勿继续使用，立即检查！\n\n"
            f"已保存的数据不受影响。"
        )
        self.log(f"🚨 探针异常：{probe_phone} 被误判，筛选已停止（已处理到第 {current_idx}/{total} 个）")
        self._update_resume_button()
        QMessageBox.critical(self, "⚠️ 探针异常 - 已停止", msg)

    def save_account(self):
        name = self.name_input.text().strip()
        api_id = self.api_id_input.text().strip()
        api_hash = self.api_hash_input.text().strip()
        phone = self.phone_input.text().strip()

        if not all([name, api_id, api_hash, phone]):
            QMessageBox.critical(self, "错误", "请填写所有字段")
            return

        proxy_host = self.proxy_host_input.text().strip()
        proxy_port = self.proxy_port_input.value()
        proxy_user = self.proxy_user_input.text().strip()
        proxy_pass = self.proxy_pass_input.text().strip()

        account = {
            "name": name,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "proxy": {
                "host": proxy_host,
                "port": proxy_port,
                "username": proxy_user,
                "password": proxy_pass
            }
        }

        if self.editing_account_name:
            for i, existing in enumerate(self.config['accounts']):
                if existing['name'] == self.editing_account_name:
                    self.config['accounts'][i] = account
                    break
            QMessageBox.information(self, "成功", "账号已更新")
            self.log(f"✅ 账号 {name} 已更新")
        else:
            self.config['accounts'].append(account)
            QMessageBox.information(self, "成功", "账号已保存")
            self.log(f"✅ 账号 {name} 已保存")

        save_config(self.config)
        self.editing_account_name = None
        self.save_account_btn.setText('💾 保存账号')

        self.name_input.clear()
        self.api_id_input.clear()
        self.api_hash_input.clear()
        self.phone_input.clear()
        self.proxy_host_input.clear()
        self.proxy_port_input.setValue(1080)
        self.proxy_user_input.clear()
        self.proxy_pass_input.clear()

        self.load_account_login_status()
        self.refresh_account_table()
        self.start_account_check()

    def refresh_account_table(self):
        """刷新账号表格"""
        accounts = self.config.get('accounts', [])
        self.account_table.setRowCount(len(accounts))

        for i, acc in enumerate(accounts):
            self.account_table.setItem(i, 0, QTableWidgetItem(acc['name']))
            self.account_table.setItem(i, 1, QTableWidgetItem(acc['phone']))
            self.account_table.setItem(i, 2, QTableWidgetItem("0"))
            self.set_account_login_state(i, acc['name'])
            self.set_account_proxy_state(i, acc['name'])
            role = '工作号' if i < 3 else '备用号'
            runtime_state = '活跃' if i < 3 else '待命'
            self.account_table.setItem(i, 5, QTableWidgetItem(role))
            self.account_table.setItem(i, 6, QTableWidgetItem(runtime_state))
            self.account_table.setItem(i, 7, QTableWidgetItem("-"))
            self.account_table.setItem(i, 8, QTableWidgetItem("0/0"))

    def set_account_login_state(self, row, name):
        status = self.account_status.get(name, {})
        state = status.get('login_state', 'not_logged_in')
        if state == 'logged_in':
            item = QTableWidgetItem("🟢 已登录")
            item.setForeground(QColor('green'))
        elif state == 'failed':
            error = status.get('login_error', '')
            text = f"🔴 登录失败: {error}" if error else "🔴 登录失败"
            item = QTableWidgetItem(text)
            item.setForeground(QColor('red'))
        elif state == 'logging_in':
            item = QTableWidgetItem("🟡 登录中")
            item.setForeground(QColor('orange'))
        else:
            item = QTableWidgetItem("⚪ 未登录")
            item.setForeground(QColor('gray'))
        self.account_table.setItem(row, 3, item)

    def set_account_proxy_state(self, row, name):
        status = self.account_status.get(name, {})
        state = status.get('proxy_state', 'not_configured')
        if state == 'proxy_ok':
            item = QTableWidgetItem("🟢 代理成功")
            item.setForeground(QColor('green'))
        elif state == 'proxy_failed':
            error = status.get('proxy_error', '')
            text = f"🔴 代理失败: {error}" if error else "🔴 代理失败"
            item = QTableWidgetItem(text)
            item.setForeground(QColor('red'))
        else:
            item = QTableWidgetItem("⚪ 未配置代理")
            item.setForeground(QColor('gray'))
        self.account_table.setItem(row, 4, item)

    def show_account_context_menu(self, pos):
        row = self.account_table.rowAt(pos.y())
        if row < 0:
            return
        self.account_table.selectRow(row)
        menu = QMenu(self)
        edit_action = menu.addAction('编辑账号')
        delete_action = menu.addAction('删除账号')
        action = menu.exec_(self.account_table.viewport().mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_account()
        elif action == delete_action:
            self.delete_selected_account()

    def edit_selected_account(self):
        row = self.account_table.currentRow()
        if row < 0:
            return
        account = self.config['accounts'][row]
        self.editing_account_name = account['name']
        self.name_input.setText(account['name'])
        self.api_id_input.setText(str(account['api_id']))
        self.api_hash_input.setText(account['api_hash'])
        self.phone_input.setText(account['phone'])
        proxy = account.get('proxy', {})
        self.proxy_host_input.setText(proxy.get('host', ''))
        self.proxy_port_input.setValue(proxy.get('port', 1080))
        self.proxy_user_input.setText(proxy.get('username', ''))
        self.proxy_pass_input.setText(proxy.get('password', ''))
        self.save_account_btn.setText('💾 更新账号')
        self.log(f"✏️ 正在编辑账号 {account['name']}")

    def login_selected_account(self):
        row = self.account_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选中要登录的账号")
            return

        account = self.config['accounts'][row]
        self.account_status.setdefault(account['name'], {}).update({'login_state': 'logging_in'})
        self.refresh_account_table()
        self.log(f"🟡 账号 {account['name']} 开始登录")
        self.login_thread = LoginThread(account)
        self.login_thread.status_signal.connect(self.handle_login_status)
        self.login_thread.code_requested.connect(self.prompt_login_code)
        self.login_thread.password_requested.connect(self.prompt_login_password)
        self.login_thread.finished_signal.connect(self.on_login_finished)
        self.login_thread.start()

    def handle_login_status(self, status_dict):
        for name, status in status_dict.items():
            current = self.account_status.setdefault(name, {})
            current.update(status)
        self.refresh_account_table()

    def handle_account_check_status(self, status_dict):
        for name, status in status_dict.items():
            current = self.account_status.setdefault(name, {})
            current.update(status)
        self.refresh_account_table()

    def prompt_login_code(self, phone):
        code, ok = QInputDialog.getText(self, "输入验证码", f"请输入 {phone} 收到的验证码：")
        if ok and code.strip():
            self.login_thread.set_code(code.strip())
        else:
            self.login_thread.set_code("")

    def prompt_login_password(self, phone):
        password, ok = QInputDialog.getText(self, "两步验证密码", f"请输入 {phone} 的两步验证密码：", QLineEdit.Password)
        if ok:
            self.login_thread.set_password(password)
        else:
            self.login_thread.set_password("")

    def on_login_finished(self, success, message):
        if success:
            self.log(f"🟢 登录成功: {message}")
            QMessageBox.information(self, "成功", message)
        else:
            self.log(f"🔴 登录失败: {message}")
            QMessageBox.critical(self, "登录失败", message)
        self.start_account_check()

    def delete_selected_account(self):
        """删除选中的账号"""
        row = self.account_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选中要删除的账号")
            return

        name = self.account_table.item(row, 0).text()
        reply = QMessageBox.question(self, "确认", f"确定删除账号「{name}」？\n同时删除本地会话文件。",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        # 删除会话文件
        session_file = f"session_{name}.session"
        if os.path.exists(session_file):
            os.remove(session_file)

        # 从配置中删除
        self.config['accounts'] = [acc for acc in self.config['accounts'] if acc['name'] != name]
        self.account_status.pop(name, None)
        save_config(self.config)

        self.refresh_account_table()
        self.log(f"🗑️ 账号 {name} 已删除")
        QMessageBox.information(self, "成功", f"账号「{name}」已删除")

    def update_account_status(self, status_dict):
        """更新账号状态（从筛选线程接收）"""
        for i in range(self.account_table.rowCount()):
            name = self.account_table.item(i, 0).text()
            if name in status_dict:
                status = status_dict[name]

                self.account_table.setItem(i, 2, QTableWidgetItem(str(status['requests'])))

                if status['blocked']:
                    status_item = QTableWidgetItem("🚫 封禁中")
                    status_item.setForeground(QColor('red'))
                    self.account_table.setItem(i, 3, status_item)
                    self.account_table.setItem(i, 7, QTableWidgetItem(status['block_until'] or "-"))
                else:
                    self.set_account_login_state(i, name)
                    self.set_account_proxy_state(i, name)
                    self.account_table.setItem(i, 7, QTableWidgetItem("-"))

                role_text = {'primary': '工作号', 'backup': '备用号'}.get(status.get('role'), '工作号')
                runtime_text = {
                    'active': '活跃',
                    'standby': '待命',
                    'suspected': '疑似异常',
                    'paused': '已暂停'
                }.get(status.get('runtime_state'), '活跃')
                self.account_table.setItem(i, 5, QTableWidgetItem(role_text))
                self.account_table.setItem(i, 6, QTableWidgetItem(runtime_text))

    def update_account_display(self):
        """定时更新显示（用于倒计时等）"""
        pass

    def save_settings(self):
        self.config['rate_limit']['requests_per_account'] = self.req_spin.value()
        self.config['rate_limit']['min_delay'] = self.min_spin.value()
        self.config['rate_limit']['max_delay'] = self.max_spin.value()
        save_config(self.config)
        QMessageBox.information(self, "成功", "设置已保存")

    def log(self, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {msg}")

    def closeEvent(self, event):
        """关闭窗口时停止线程"""
        if self.filter_thread and self.filter_thread.isRunning():
            self.filter_thread.stop()
            self.filter_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TelegramFilter")
    gui = TelegramFilterGUI()
    gui.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
