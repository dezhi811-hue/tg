"""批量导入号包 + 代理分配 + 首登健康检测。

- parse_proxy_block: 'host:port:user:pass' 格式的多行代理批量解析
- scan_account_folder: 扫描文件夹，找 session+json 配对
- parse_info_json: 模糊匹配各家卖号包 json 字段（api_id/app_id/device/sdk 等）
- health_check_account: 用 Telethon 做首登检测，区分活号/死号/代理问题
"""
import asyncio
import json
import os
from telethon import TelegramClient
from telethon.errors import (
    AuthKeyUnregisteredError,
    SessionRevokedError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    PhoneNumberBannedError,
)

SESSION_EXT = '.session'


def parse_proxy_line(line):
    """解析单行 'host:port:user:pass'，空行/注释返回 None，错误抛 ValueError。"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    parts = line.split(':')
    if len(parts) < 2:
        raise ValueError(f"至少需要 host:port，当前：{line!r}")
    host = parts[0].strip()
    if not host:
        raise ValueError(f"host 不能为空：{line!r}")
    try:
        port = int(parts[1].strip())
    except ValueError:
        raise ValueError(f"端口必须为数字：{line!r}")
    user = parts[2].strip() if len(parts) >= 3 else ''
    pw = ':'.join(parts[3:]).strip() if len(parts) >= 4 else ''
    return {"host": host, "port": port, "username": user, "password": pw}


def parse_proxy_block(text):
    """返回 (proxies, errors)。errors 为人类可读的错误行号列表。"""
    proxies, errors = [], []
    for i, line in enumerate(text.splitlines(), 1):
        try:
            p = parse_proxy_line(line)
            if p:
                proxies.append(p)
        except ValueError as e:
            errors.append(f"第 {i} 行 {e}")
    return proxies, errors


def scan_account_folder(folder):
    """扫描目录返回 [(name, session_path, json_path_or_None), ...]。

    支持两种布局：
    1. 扁平：folder/{name}.session + folder/{name}.json (或 info.json)
    2. 子目录：folder/{name}/*.session + folder/{name}/info.json
    """
    found = []
    if not folder or not os.path.isdir(folder):
        return found

    def _pair_in_dir(dir_path, base_name=None):
        try:
            entries = os.listdir(dir_path)
        except OSError:
            return
        sessions = [f for f in entries if f.lower().endswith(SESSION_EXT)]
        for s in sessions:
            sp = os.path.join(dir_path, s)
            stem = os.path.splitext(s)[0]
            json_candidates = [
                os.path.join(dir_path, stem + '.json'),
                os.path.join(dir_path, 'info.json'),
                os.path.join(dir_path, stem + '_info.json'),
                os.path.join(dir_path, 'json', stem + '.json'),
            ]
            jp = next((j for j in json_candidates if os.path.exists(j)), None)
            name = base_name if base_name else stem
            found.append((name, sp, jp))

    _pair_in_dir(folder)
    for sub in os.listdir(folder):
        sp = os.path.join(folder, sub)
        if os.path.isdir(sp):
            _pair_in_dir(sp, base_name=sub)

    # 去重（扁平+子目录可能重复），以 session 绝对路径为键
    seen, uniq = set(), []
    for entry in found:
        key = os.path.abspath(entry[1])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(entry)
    return uniq


def parse_info_json(path):
    """模糊匹配常见卖号包 json 字段。读失败或文件不存在返回 {}。"""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    def first(*keys):
        for k in keys:
            if k in data and data[k] not in (None, ''):
                return data[k]
        return None

    return {
        'api_id': first('app_id', 'api_id', 'APP_ID'),
        'api_hash': first('app_hash', 'api_hash', 'APP_HASH'),
        'phone': first('phone', 'phone_number', 'number'),
        'device_model': first('device', 'device_model', 'device_name'),
        'system_version': first('sdk', 'system_version', 'os_version', 'os'),
        'app_version': first('app_version', 'version'),
        'lang_code': first('lang_code', 'lang_pack', 'language'),
        'system_lang_code': first('system_lang_code', 'system_lang_pack'),
        'twoFA': first('twoFA', 'two_fa', '2fa', 'password'),
    }


async def health_check_account(account, proxy_dict, session_path, timeout=20):
    """对单个号做首登检测。返回 dict:
    {status, error, phone, username, user_id}

    status ∈ {alive, dead_session, dead_banned, dead_deactivated,
              proxy_failed, unknown_error}
    """
    from account_manager import resolve_device_profile, build_proxy_config

    fp = resolve_device_profile(account)
    proxy = build_proxy_config(proxy_dict)

    result = {
        'status': 'unknown_error', 'error': '',
        'phone': '', 'username': '', 'user_id': 0,
    }

    try:
        api_id = int(account['api_id'])
    except (KeyError, TypeError, ValueError):
        result['status'] = 'unknown_error'
        result['error'] = 'api_id 缺失或非数字'
        return result

    client = TelegramClient(
        session_path,
        api_id,
        account.get('api_hash', ''),
        proxy=proxy,
        timeout=timeout,
        **fp,
    )

    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=timeout)
        except Exception as e:
            result['status'] = 'proxy_failed'
            result['error'] = f"连接失败: {type(e).__name__}: {e}"
            return result

        try:
            authorized = await asyncio.wait_for(
                client.is_user_authorized(), timeout=timeout
            )
        except (AuthKeyUnregisteredError, SessionRevokedError) as e:
            result['status'] = 'dead_session'
            result['error'] = f'会话已失效: {type(e).__name__}'
            return result
        except UserDeactivatedBanError:
            result['status'] = 'dead_banned'
            result['error'] = '账号已被 Telegram 封禁'
            return result
        except UserDeactivatedError:
            result['status'] = 'dead_deactivated'
            result['error'] = '账号已被停用'
            return result
        except PhoneNumberBannedError:
            result['status'] = 'dead_banned'
            result['error'] = '手机号已被封禁'
            return result
        except Exception as e:
            result['status'] = 'unknown_error'
            result['error'] = f'授权检查失败: {type(e).__name__}: {e}'
            return result

        if not authorized:
            result['status'] = 'dead_session'
            result['error'] = '会话未授权（session 已失效或未登录）'
            return result

        try:
            me = await asyncio.wait_for(client.get_me(), timeout=timeout)
            result['phone'] = getattr(me, 'phone', '') or ''
            result['username'] = getattr(me, 'username', '') or ''
            result['user_id'] = getattr(me, 'id', 0) or 0
            result['status'] = 'alive'
        except (AuthKeyUnregisteredError, SessionRevokedError):
            result['status'] = 'dead_session'
            result['error'] = 'get_me 返回 AUTH_KEY 失效'
        except UserDeactivatedBanError:
            result['status'] = 'dead_banned'
            result['error'] = 'get_me 返回账号已封禁'
        except UserDeactivatedError:
            result['status'] = 'dead_deactivated'
            result['error'] = 'get_me 返回账号已停用'
        except Exception as e:
            result['status'] = 'unknown_error'
            result['error'] = f'get_me 失败: {type(e).__name__}: {e}'
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    return result


STATUS_LABEL = {
    'alive': '✅ 活号',
    'dead_session': '❌ 死号-会话失效',
    'dead_banned': '❌ 死号-已封禁',
    'dead_deactivated': '❌ 死号-已停用',
    'proxy_failed': '⚠️ 代理/网络不通',
    'unknown_error': '⚠️ 未知错误',
}


def is_refundable(status):
    """按卖家售后规则：死号可退，代理问题不可退，活号不退。"""
    return status in ('dead_session', 'dead_banned', 'dead_deactivated')
