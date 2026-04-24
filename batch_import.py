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


def _find_tdata(dir_path):
    """识别 tdata 子目录（Telegram Desktop 官方登录态目录）。"""
    tdata_subdir = os.path.join(dir_path, 'tdata')
    if not os.path.isdir(tdata_subdir):
        return None
    # tdata 目录必有 key_datas 或 D877F783D5D3EF8C_* 之类文件
    try:
        files = os.listdir(tdata_subdir)
    except OSError:
        return None
    for f in files:
        if f.startswith('key_datas') or 'D877F783D5D3EF8C' in f:
            return tdata_subdir
    return None


async def convert_tdata_to_telethon(tdata_dir, out_session_path, api_id=None, api_hash=None):
    """tdata → .session（§5.13）。保留 opentele 的官方指纹，可信度显著高于 session。

    要求：pip install opentele
    """
    from opentele.td import TDesktop
    from opentele.api import UseCurrentSession, API
    tdesk = TDesktop(tdata_dir)
    if not tdesk.isLoaded():
        raise RuntimeError('tdata 加载失败（key_datas 损坏或密码保护）')
    api = API.TelegramDesktop.Generate() if not api_id else None
    client = await tdesk.ToTelethon(
        session=out_session_path,
        flag=UseCurrentSession,
        api=api,
    )
    return client


def scan_account_folder(folder):
    """扫描目录返回 [(name, session_path_or_tdata, json_path_or_None, source_type), ...]。

    source_type ∈ {'session', 'tdata'}。同一号同时有 tdata 和 .session 时优先 tdata。
    支持两种布局：
    1. 扁平：folder/{name}.session + folder/{name}.json (或 info.json)
    2. 子目录：folder/{name}/*.session 或 folder/{name}/tdata/ + folder/{name}/info.json
    """
    found = []
    if not folder or not os.path.isdir(folder):
        return found

    def _pair_in_dir(dir_path, base_name=None):
        try:
            entries = os.listdir(dir_path)
        except OSError:
            return
        # 优先识别 tdata
        tdata_path = _find_tdata(dir_path)
        if tdata_path and base_name:
            jp = next(
                (p for p in (
                    os.path.join(dir_path, base_name + '.json'),
                    os.path.join(dir_path, 'info.json'),
                    os.path.join(dir_path, base_name + '_info.json'),
                ) if os.path.exists(p)),
                None,
            )
            found.append((base_name, tdata_path, jp, 'tdata'))
            return  # 同一号不再扫 session
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
            found.append((name, sp, jp, 'session'))

    _pair_in_dir(folder)
    for sub in os.listdir(folder):
        sp = os.path.join(folder, sub)
        if os.path.isdir(sp):
            _pair_in_dir(sp, base_name=sub)

    # 去重（扁平+子目录可能重复），以 name 为键，tdata 优先
    by_name = {}
    for entry in found:
        name = entry[0]
        existing = by_name.get(name)
        if existing is None or (existing[3] == 'session' and entry[3] == 'tdata'):
            by_name[name] = entry
    uniq = list(by_name.values())
    # 按账号名字典序固定顺序：保证 UI 第 N 行 = 粘贴代理的第 N 行，
    # 不被 os.listdir 的平台相关顺序坑（Win / macOS / Linux 各不同）。
    uniq.sort(key=lambda e: e[0])
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
    # 把首登实际使用的指纹回写到 account，上层会把它落盘到 config.json，
    # 确保后续筛号用完全相同的 device_model/system_version/... 再登 Telegram。
    # 没有这一步的话，没 json 的号会走 hash fallback 拿到指纹做首登，但保存时不带，
    # 下次启动只要账号列表变动导致 hash 命中的槽位变化，指纹就漂移。
    for k, v in fp.items():
        account.setdefault(k, v)
    # §5.7 首登也走 sticky，避免 "首登 IP-A / 筛号 IP-B" 的指纹错位
    sticky_proxy = proxy_dict
    if proxy_dict and proxy_dict.get('host'):
        try:
            from account_pool import build_sticky_proxy_for
            sticky_proxy = build_sticky_proxy_for(account, proxy_dict)
        except Exception:
            sticky_proxy = proxy_dict
    proxy = build_proxy_config(sticky_proxy)

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
