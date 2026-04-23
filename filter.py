"""
号码筛选核心模块 - 支持多账号和智能速率控制
"""
import asyncio
import random
from datetime import datetime
from telethon.tl.functions.contacts import (
    ImportContactsRequest,
    DeleteContactsRequest,
    ResetSavedRequest,
    ResolvePhoneRequest,
)
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPhoneContact, InputPeerEmpty
from telethon.errors import (
    PhoneNumberInvalidError,
    FloodWaitError,
)
from phone_utils import PhoneUtils


# 用于 InputPhoneContact.first_name 随机化的常见英文名池，避免所有请求都用 'User'
_RANDOM_FIRST_NAMES = [
    'John', 'Mike', 'David', 'Chris', 'Alex', 'James', 'Robert', 'Daniel',
    'Paul', 'Mark', 'Kevin', 'Brian', 'Steve', 'Tom', 'Sam', 'Jack',
    'Anna', 'Mary', 'Lisa', 'Emma', 'Sarah', 'Kate', 'Linda', 'Amy',
]


class EmptyQueryResultError(Exception):
    """Telegram 查询成功但未返回用户，用于上层做谨慎重试。"""


class TelegramFilter:
    def __init__(self, manager=None, limiter=None, config=None):
        self.manager = manager
        self.limiter = limiter
        # 从 config['rate_limit'] 读取防封控开关，默认保守值
        rl = (config or {}).get('rate_limit', {}) if isinstance(config, dict) else {}
        # use_resolve_phone: true 时走 ResolvePhoneRequest（不入联系人簿，配额松）
        # 默认 false，保留原 ImportContactsRequest 行为，老号触顶再手动切
        self.use_resolve_phone = bool(rl.get('use_resolve_phone', False))
        # 每账号每 N 次查询插一次静默读（GetDialogs），让风控看到真人行为
        # 0 或 None 表示关闭
        self.silent_read_interval = int(rl.get('silent_read_interval', 10) or 0)
        # 每账号每 N 次查询重置一次联系人簿，保险清理
        self.reset_contacts_interval = int(rl.get('reset_contacts_interval', 50) or 0)

    async def check_phone(self, phone, country='US'):
        """
        验证手机号是否注册Telegram（使用智能调度器）

        返回格式:
        {
            'phone': '+12025551234',
            'registered': True/False,
            'user_id': 123456,
            'username': 'example',
            'first_name': 'John',
            'last_name': 'Doe',
            'last_seen': '2026-04-07 10:30:00',
            'status': 'online/offline/recently/within_week/within_month/long_ago',
            'is_bot': False,
            'country': 'US'
        }
        """
        # 格式化号码
        if country == 'CN':
            formatted_phone = PhoneUtils.format_cn_phone(phone)
        else:
            formatted_phone = PhoneUtils.format_us_phone(phone)
        country_detected = PhoneUtils.detect_country(formatted_phone)

        result = {
            'phone': formatted_phone,
            'original_phone': phone,
            'country': country_detected,
            'registered': False,
            'user_id': None,
            'username': None,
            'first_name': None,
            'last_name': None,
            'last_seen': None,
            'status': None,
            'is_bot': False,
            'query_state': 'pending',
            'error': None
        }

        if self.manager and self.limiter:
            # 使用多账号管理器执行
            return await self._check_with_manager(phone, result)
        else:
            # 直接执行（兼容旧版）
            return result

    async def _check_with_manager(self, phone, result):
        """使用多账号管理器执行号码检查"""
        account = None
        try:
            account = self.manager.get_next_account()

            await self.limiter.wait_before_request()
            client = account['client']
            contact = await self._import_contact_and_get_user(client, result['phone'])

            result['registered'] = True
            result['query_state'] = 'registered'
            result['user_id'] = contact.id
            result['username'] = contact.username
            result['first_name'] = contact.first_name
            result['last_name'] = contact.last_name
            result['is_bot'] = contact.bot

            status_info = await self._get_user_status(contact)
            result.update(status_info)

            self.manager.mark_account_used(account)
            self.manager.mark_account_success(account)
            # 命中也穿插静默读与周期清理联系人簿
            await self._maybe_silent_read(client, account)
            await self._maybe_reset_contacts(client, account)

        except FloodWaitError as e:
            if account:
                self.manager.mark_account_error(account, e)
            result['query_state'] = 'rate_limited'
            result['error'] = f'触发速率限制，需等待{e.seconds}秒'
        except PhoneNumberInvalidError:
            result['query_state'] = 'invalid'
            result['error'] = '手机号格式无效'
        except EmptyQueryResultError:
            # 空返也要计数：否则单号被风控持续空返时，request_count 永远 = 0，
            # 调度器不会触发单号冷却，会变成死循环猛薅一个已经坏了的号。
            if account:
                self.manager.mark_account_used(account)
            result['query_state'] = 'empty_result'
            result['error'] = '查询未返回用户'
        except Exception as e:
            if account:
                self.manager.mark_account_error(account)
            result['query_state'] = 'query_failed'
            result['error'] = str(e)

        return result

    async def _import_contact_and_get_user(self, client, phone):
        """根据配置选择 ResolvePhone 或 ImportContacts。

        - ResolvePhone：不入联系人簿，配额松，但对"开启手机号隐私的用户"仍然能查到，
          语义可能与"能加联系人"略有差异。默认关闭，老号触顶再打开。
        - ImportContacts：经典语义，命中即表示"可通过手机号加为联系人"。命中后立即删除，
          避免联系人簿无限增长。
        """
        if self.use_resolve_phone:
            try:
                res = await client(ResolvePhoneRequest(phone=phone))
                if not res.users:
                    raise EmptyQueryResultError('ResolvePhone 未返回用户')
                return res.users[0]
            except EmptyQueryResultError:
                raise
            except Exception:
                # Resolve 失败（未注册 / 隐私保护）统一当空返，交由上层判定
                raise EmptyQueryResultError('ResolvePhone 查询未返回用户')

        # 默认路径：ImportContacts。随机化 client_id 与 first_name，去除静态特征。
        contact = InputPhoneContact(
            client_id=random.randint(1, 2**31 - 1),
            phone=phone,
            first_name=random.choice(_RANDOM_FIRST_NAMES),
            last_name='',
        )
        result = await client(ImportContactsRequest(contacts=[contact]))
        if not result.users:
            raise EmptyQueryResultError('查询未返回用户')

        user = result.users[0]
        # 命中后立即删除联系人，避免联系人簿无限增长（触发风控）
        try:
            await client(DeleteContactsRequest(id=[user]))
        except Exception as de:
            # 删失败不影响本次结果，但打日志便于排查
            print(f"⚠️  DeleteContactsRequest 失败: {de}")
        return user

    async def _maybe_silent_read(self, client, account):
        """周期性静默读：调 GetDialogs 模拟正常客户端行为，降低风控打分。

        每账号每 N 次查询触发一次，N 由 config.rate_limit.silent_read_interval 控制。
        """
        if self.silent_read_interval <= 0:
            return
        count = account.get('request_count', 0)
        if count <= 0 or count % self.silent_read_interval != 0:
            return
        try:
            await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=10,
                hash=0,
            ))
        except Exception:
            pass  # 静默读失败不影响筛号主流程

    async def _maybe_reset_contacts(self, client, account):
        """周期性清空联系人簿，兜底 DeleteContactsRequest 未及时清理的遗留。"""
        if self.reset_contacts_interval <= 0:
            return
        count = account.get('request_count', 0)
        if count <= 0 or count % self.reset_contacts_interval != 0:
            return
        try:
            await client(ResetSavedRequest())
        except Exception:
            pass

    async def _check_phone_impl(self, client, phone, result):
        """实际执行号码检查的内部方法"""
        try:
            # 通过导入联系人检测手机号
            contact = await self._import_contact_and_get_user(client, result['phone'])

            result['registered'] = True
            result['query_state'] = 'registered'
            result['user_id'] = contact.id
            result['username'] = contact.username
            result['first_name'] = contact.first_name
            result['last_name'] = contact.last_name
            result['is_bot'] = contact.bot

            # 获取在线状态
            status_info = await self._get_user_status(contact)
            result.update(status_info)

        except PhoneNumberInvalidError:
            result['query_state'] = 'invalid'
            result['error'] = '手机号格式无效'
        except EmptyQueryResultError:
            result['query_state'] = 'empty_result'
            result['error'] = '查询未返回用户'
        except FloodWaitError as e:
            result['query_state'] = 'rate_limited'
            result['error'] = f'触发速率限制，需等待{e.seconds}秒'
            raise  # 重新抛出让调度器处理
        except Exception as e:
            result['query_state'] = 'query_failed'
            result['error'] = str(e)

        return result

    async def _get_user_status(self, user):
        """获取用户在线状态和最后上线时间"""
        status_info = {
            'last_seen': None,
            'status': 'unknown'
        }

        if not hasattr(user, 'status'):
            return status_info

        status = user.status

        # 在线状态类型
        if hasattr(status, '__class__'):
            status_type = status.__class__.__name__

            if status_type == 'UserStatusOnline':
                status_info['status'] = 'online'
                if hasattr(status, 'expires'):
                    status_info['last_seen'] = status.expires.strftime('%Y-%m-%d %H:%M:%S')

            elif status_type == 'UserStatusOffline':
                status_info['status'] = 'offline'
                if hasattr(status, 'was_online'):
                    status_info['last_seen'] = status.was_online.strftime('%Y-%m-%d %H:%M:%S')

            elif status_type == 'UserStatusRecently':
                status_info['status'] = 'recently'  # 最近在线（几分钟到几小时内）

            elif status_type == 'UserStatusLastWeek':
                status_info['status'] = 'within_week'  # 一周内在线

            elif status_type == 'UserStatusLastMonth':
                status_info['status'] = 'within_month'  # 一个月内在线

            elif status_type == 'UserStatusEmpty':
                status_info['status'] = 'long_ago'  # 很久未上线

        return status_info

    async def batch_check(self, phones, callback=None, country='US'):
        """
        批量检查手机号

        phones: 手机号列表
        callback: 每个结果的回调函数
        country: 目标国家（US/CN等）
        """
        # 格式化号码
        print(f"📝 正在格式化 {len(phones)} 个号码...")
        formatted_phones, errors = PhoneUtils.batch_format(phones, country)

        if errors:
            print(f"⚠️  {len(errors)} 个号码格式错误:")
            for error in errors[:5]:  # 只显示前5个
                print(f"  - {error}")

        print(f"✅ 有效号码: {len(formatted_phones)}")

        results = []

        for i, phone in enumerate(formatted_phones, 1):
            print(f"\n[{i}/{len(formatted_phones)}] 正在检查: {phone}")

            result = await self.check_phone(phone)
            results.append(result)

            # 显示结果
            if result.get('registered'):
                status_emoji = {
                    'online': '🟢',
                    'recently': '🟡',
                    'within_week': '🟠',
                    'within_month': '🔴',
                    'offline': '⚫',
                    'long_ago': '⚪'
                }.get(result.get('status'), '❓')

                print(f"  ✅ 已注册 {status_emoji} {result.get('status')} - {result.get('username') or 'N/A'}")
            else:
                print(f"  ❌ {result.get('error', '未注册')}")

            if callback:
                callback(result)

        return results
