"""
号码筛选核心模块 - 支持多账号和智能速率控制
"""
import asyncio
from datetime import datetime
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from telethon.errors import (
    PhoneNumberInvalidError,
    FloodWaitError
)
from phone_utils import PhoneUtils


class EmptyQueryResultError(Exception):
    """Telegram 查询成功但未返回用户，用于上层做谨慎重试。"""


class TelegramFilter:
    def __init__(self, manager=None, limiter=None):
        self.manager = manager
        self.limiter = limiter

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

        except FloodWaitError as e:
            if account:
                self.manager.mark_account_error(account, e)
            result['query_state'] = 'rate_limited'
            result['error'] = f'触发速率限制，需等待{e.seconds}秒'
        except PhoneNumberInvalidError:
            result['query_state'] = 'invalid'
            result['error'] = '手机号格式无效'
        except EmptyQueryResultError:
            result['query_state'] = 'empty_result'
            result['error'] = '查询未返回用户'
        except Exception as e:
            if account:
                self.manager.mark_account_error(account)
            result['query_state'] = 'query_failed'
            result['error'] = str(e)

        return result

    async def _import_contact_and_get_user(self, client, phone):
        contact = InputPhoneContact(
            client_id=0,
            phone=phone,
            first_name='User',
            last_name=''
        )
        result = await client(ImportContactsRequest(contacts=[contact]))
        if not result.users:
            raise EmptyQueryResultError('查询未返回用户')

        user = result.users[0]
        try:
            await client(DeleteContactsRequest(id=[user]))
        except Exception:
            pass
        return user

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
