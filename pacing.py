"""速率控制状态机（§5.2 突发-静默 + §5.15 美东降频）。

对外只暴露一个接口：`await pacing.wait(account_name)`。
内部每号独立维护 burst 计数，兼顾单号节奏保守 + 多号之间相互错峰。
"""
import asyncio
import random
import threading
from collections import defaultdict

from account_pool import is_us_quiet_hour


class BurstSilentPacer:
    def __init__(self, pool):
        self.pool = pool
        self._lock = threading.Lock()
        # 每号 state: {'burst_left': int, 'mode': 'burst'|'quiet'}
        self._state = defaultdict(lambda: {'burst_left': 0, 'mode': 'burst'})

    def _cfg(self):
        return self.pool.pool_config.get('pacing', {})

    def _next_burst_size(self, cfg):
        return random.randint(cfg.get('burst_min', 2), cfg.get('burst_max', 4))

    async def wait(self, account_name):
        """等到可以发下一次请求；每号独立 BURST/QUIET 状态机。"""
        cfg = self._cfg()
        with self._lock:
            st = self._state[account_name]
            if st['burst_left'] <= 0:
                # 进入新一轮 burst（开头先静默一次模拟真人"放下手机"）
                st['burst_left'] = self._next_burst_size(cfg)
                delay = random.uniform(
                    cfg.get('quiet_interval_min', 180),
                    cfg.get('quiet_interval_max', 600),
                )
                st['mode'] = 'quiet'
            else:
                delay = random.uniform(
                    cfg.get('burst_interval_min', 8),
                    cfg.get('burst_interval_max', 18),
                )
                st['mode'] = 'burst'
            st['burst_left'] -= 1
        # 美东 02-07 降频
        if is_us_quiet_hour():
            delay *= float(cfg.get('quiet_hour_multiplier', 3.0))
        await asyncio.sleep(delay)
