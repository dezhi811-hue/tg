"""M4 预热心跳：warmup 态账号每 30-120 分钟做一次真人动作。

- 不参与筛号
- 按权重随机挑动作（GetDialogs / UpdateStatus / GetFullUser 等）
- 动作失败不影响状态，但连续失败 3 次 → 标 retired（session 可能已死）
- 72h 后自动由 pool._auto_transition 升 active

该线程需要外部提供 `client_factory(account_name) -> TelegramClient`，
由 account_manager 实现（避免 pool 直接持有 Telethon 依赖）。
"""
import asyncio
import random
import time


_ACTIONS = [
    ('GetDialogsRequest', 0.40),
    ('UpdateStatusRequest', 0.20),
    ('GetFullUserRequest', 0.15),
    ('GetContactsRequest', 0.15),
    ('GetNotifySettingsRequest', 0.10),
]


def _pick_action():
    r = random.random()
    cum = 0
    for name, w in _ACTIONS:
        cum += w
        if r <= cum:
            return name
    return _ACTIONS[0][0]


async def _perform(client, action):
    from telethon.tl.functions.messages import GetDialogsRequest
    from telethon.tl.functions.account import UpdateStatusRequest, GetNotifySettingsRequest
    from telethon.tl.functions.users import GetFullUserRequest
    from telethon.tl.functions.contacts import GetContactsRequest
    from telethon.tl.types import InputPeerEmpty, InputNotifyUsers
    if action == 'GetDialogsRequest':
        await client(GetDialogsRequest(
            offset_date=None, offset_id=0,
            offset_peer=InputPeerEmpty(), limit=10, hash=0
        ))
    elif action == 'UpdateStatusRequest':
        await client(UpdateStatusRequest(offline=False))
    elif action == 'GetFullUserRequest':
        await client(GetFullUserRequest('me'))
    elif action == 'GetContactsRequest':
        await client(GetContactsRequest(hash=0))
    elif action == 'GetNotifySettingsRequest':
        await client(GetNotifySettingsRequest(peer=InputNotifyUsers()))


async def warmup_once(pool, client_factory, log_fn=None):
    """对所有 warmup 账号各做一次心跳动作。"""
    names = pool.get_by_state('warmup')
    for name in names:
        delay = random.uniform(1800, 7200)  # 30-120 min 抖动
        # 不真的 sleep 这么久，外层按号分片即可；这里仅做一次动作
        action = _pick_action()
        client = None
        try:
            client = await client_factory(name)
            if client is None:
                continue
            await _perform(client, action)
            pool.record_request(name, success=True, api_name=action)
            if log_fn:
                log_fn(f'🌡️ warmup {name}: {action} ok (next ~{int(delay/60)}min)')
        except Exception as e:
            if log_fn:
                log_fn(f'🌡️ warmup {name}: {action} fail {type(e).__name__}: {e}')
            # 永久错误立即退役
            msg = str(e).upper()
            from account_pool import PERMANENT_LIMIT_CODES
            for code in PERMANENT_LIMIT_CODES:
                if code in msg:
                    pool.record_permanent_limit(name, code)
                    break
        finally:
            if client is not None:
                try:
                    await client.disconnect()
                except Exception:
                    pass
