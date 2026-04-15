"""
智能速率控制模块
"""
import asyncio
import random
from datetime import datetime, timedelta


class RateLimiter:
    def __init__(self, config):
        self.config = config
        self.request_history = []
        self.error_count = 0
        self.last_error_time = None

    async def wait_before_request(self):
        """请求前等待（智能延迟）"""
        # 基础随机延迟
        base_delay = random.uniform(
            self.config['min_delay'],
            self.config['max_delay']
        )

        # 如果最近有错误，增加延迟
        if self.last_error_time:
            time_since_error = (datetime.now() - self.last_error_time).total_seconds()
            if time_since_error < self.config['error_cooldown']:
                extra_delay = random.uniform(5, 15)
                base_delay += extra_delay
                print(f"⏳ 最近有错误，增加延迟 {extra_delay:.1f}秒")

        # 如果错误次数过多，进一步增加延迟
        if self.error_count > 3:
            penalty = self.error_count * random.uniform(2, 5)
            base_delay += penalty
            print(f"⚠️  错误次数较多，额外延迟 {penalty:.1f}秒")

        print(f"⏱️  等待 {base_delay:.1f}秒...")
        await asyncio.sleep(base_delay)

        # 记录请求时间
        self.request_history.append(datetime.now())

        # 清理旧记录（保留最近1小时）
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.request_history = [
            t for t in self.request_history if t > cutoff_time
        ]

    def record_error(self):
        """记录错误"""
        self.error_count += 1
        self.last_error_time = datetime.now()

    def record_success(self):
        """记录成功（逐渐降低错误计数）"""
        if self.error_count > 0:
            self.error_count = max(0, self.error_count - 0.5)

    def get_requests_per_hour(self):
        """获取每小时请求数"""
        return len(self.request_history)

    def should_pause(self):
        """判断是否应该暂停"""
        # 如果1小时内请求过多
        if self.get_requests_per_hour() > 100:
            return True

        # 如果错误率过高
        if self.error_count > 10:
            return True

        return False


class SmartScheduler:
    """智能任务调度器"""

    def __init__(self, account_manager, rate_limiter):
        self.account_manager = account_manager
        self.rate_limiter = rate_limiter
        self.current_account = None

    async def execute_task(self, task_func, *args, **kwargs):
        """执行单个任务（带重试和账号切换）"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 检查是否需要暂停
                if self.rate_limiter.should_pause():
                    pause_time = random.uniform(60, 180)
                    print(f"🛑 请求过于频繁，暂停 {pause_time:.0f}秒")
                    await asyncio.sleep(pause_time)

                # 获取可用账号
                if not self.current_account or self.account_manager.should_switch_account(self.current_account):
                    self.current_account = self.account_manager.get_next_account()
                    print(f"🔄 切换到账号: {self.current_account['name']}")

                    # 切换账号后额外等待
                    switch_delay = random.uniform(5, 15)
                    await asyncio.sleep(switch_delay)

                # 速率控制等待
                await self.rate_limiter.wait_before_request()

                # 执行任务
                result = await task_func(self.current_account['client'], *args, **kwargs)

                # 标记成功
                self.account_manager.mark_account_used(self.current_account)
                self.account_manager.mark_account_success(self.current_account)
                self.rate_limiter.record_success()

                return result

            except Exception as e:
                retry_count += 1
                error_msg = str(e)

                print(f"❌ 错误 (尝试 {retry_count}/{max_retries}): {error_msg}")

                # 标记错误
                self.account_manager.mark_account_error(self.current_account, e)
                self.rate_limiter.record_error()

                # 如果是速率限制错误，强制切换账号
                if 'FloodWait' in error_msg or 'FLOOD' in error_msg:
                    print("🚫 触发速率限制，强制切换账号")
                    self.current_account = None

                if retry_count < max_retries:
                    wait_time = retry_count * random.uniform(10, 30)
                    print(f"⏳ 等待 {wait_time:.1f}秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    return {
                        'error': error_msg,
                        'success': False
                    }

        return None
