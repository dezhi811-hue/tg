"""代理凭据仓库。

- 凭据单独存 proxies.json（不塞 config.json，防泄露到备份/截图）
- 支持"1 行根凭据 → N 号自动 sticky sub-session"批量分发
- 启动时对每号做一次 SOCKS CONNECT ping 保活
- 失败号通知 pool 自动 cooling
"""
import asyncio
import json
import os
import socket
import struct
import time

from account_pool import build_sticky_proxy_for


def _atomic_write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class ProxyRegistry:
    """proxies.json schema:
    {
        "base": {"host": ..., "port": ..., "username": ..., "password": ...},
        "overrides": {"account1": {...}, ...}   # 可选，单号覆盖
    }
    """

    def __init__(self, path):
        self.path = path
        self.data = {'base': None, 'overrides': {}}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            self.data.setdefault('base', None)
            self.data.setdefault('overrides', {})
        except Exception:
            pass

    def save(self):
        _atomic_write_json(self.path, self.data)

    def set_base(self, proxy_dict):
        """粘贴 1 行根凭据。N 个号会各自拿到 -session-<crc32(name)> 的 sticky 代理。"""
        self.data['base'] = proxy_dict
        self.save()

    def set_override(self, account_name, proxy_dict):
        self.data['overrides'][account_name] = proxy_dict
        self.save()

    def clear_override(self, account_name):
        self.data['overrides'].pop(account_name, None)
        self.save()

    def resolve_for(self, account):
        """返回该账号的实际代理 dict（已注入 sticky session）。"""
        name = account.get('name') if isinstance(account, dict) else account
        override = self.data.get('overrides', {}).get(name)
        base = override or self.data.get('base')
        if not base:
            return None
        return build_sticky_proxy_for({'name': name}, base)


def _socks5_handshake(host, port, username, password, timeout=8):
    """对 SOCKS5 代理做一次握手（不连 TG），用于保活 ping。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        # 协商方法：0x02 用户名密码 / 0x00 无认证
        sock.sendall(b'\x05\x02\x00\x02')
        resp = sock.recv(2)
        if len(resp) < 2 or resp[0] != 0x05:
            return False, 'bad greeting'
        method = resp[1]
        if method == 0x02:
            if not username:
                return False, 'auth required but no creds'
            u = username.encode('utf-8')
            p = (password or '').encode('utf-8')
            req = b'\x01' + bytes([len(u)]) + u + bytes([len(p)]) + p
            sock.sendall(req)
            auth_resp = sock.recv(2)
            if len(auth_resp) < 2 or auth_resp[1] != 0x00:
                return False, 'auth rejected'
        elif method != 0x00:
            return False, f'unsupported method 0x{method:02x}'
        return True, 'ok'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'
    finally:
        try:
            sock.close()
        except Exception:
            pass


async def proxy_ping(proxy_dict, timeout=8):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _socks5_handshake,
        proxy_dict['host'], proxy_dict['port'],
        proxy_dict.get('username'), proxy_dict.get('password'),
        timeout,
    )


async def keepalive_pass(registry, pool, log_fn=None):
    """对 active 号跑一轮 SOCKS 握手；失败 2 次进 cooling。"""
    for name in pool.get_by_state('active'):
        proxy = registry.resolve_for({'name': name})
        if not proxy:
            continue
        ok, reason = await proxy_ping(proxy, timeout=6)
        if log_fn:
            log_fn(f'🛰️ keepalive {name}: {"OK" if ok else "FAIL "+reason}')
        if not ok:
            # 一次失败立即 10 分钟 cooling（代理商掉线常见）
            pool.mark_cooling(name, duration_sec=600, reason='proxy_ping_failed')
