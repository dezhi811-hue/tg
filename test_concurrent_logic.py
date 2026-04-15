#!/usr/bin/env python3
"""
并发筛号逻辑模拟测试
"""
import asyncio
import random
from datetime import datetime


class MockAccount:
    def __init__(self, name):
        self.name = name
        self.role = 'primary'
        self.runtime_state = 'active'
        self.request_count = 0
        self.is_blocked = False


class MockManager:
    def __init__(self):
        self.accounts = [
            MockAccount('account1'),
            MockAccount('account2'),
            MockAccount('account3'),
        ]

    def get_active_primary_accounts(self):
        return [acc for acc in self.accounts if acc.runtime_state == 'active']


class MockRateLimiter:
    def __init__(self):
        self.config = {'min_delay': 1, 'max_delay': 4}

    async def wait_before_request(self):
        delay = random.uniform(self.config['min_delay'], self.config['max_delay'])
        jitter = random.uniform(0, 0.5)
        await asyncio.sleep(delay + jitter)


class MockFilter:
    def __init__(self):
        pass

    async def check_phone(self, phone, country):
        # 模拟查询
        await asyncio.sleep(0.1)
        # 70%概率已注册，30%未注册
        registered = random.random() < 0.7
        return {
            'phone': phone,
            'registered': registered,
            'query_state': 'registered' if registered else 'empty_result',
            'status': 'online' if registered else None,
            'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S') if registered else None
        }


async def process_single_phone(phone_idx, phone, worker, manager):
    """模拟处理单个号码"""
    # 随机延迟
    random_delay = random.uniform(0.1, 0.5)
    await asyncio.sleep(random_delay)

    print(f"[{phone_idx+1}/100] 检查 {phone} (账号: {worker['account'].name})")

    # 速率限制
    await worker['limiter'].wait_before_request()

    # 查询
    result = await worker['filter'].check_phone(phone, 'US')

    if result['registered']:
        print(f"  ✅ 已注册 | {phone} | {result['status']}")
    else:
        print(f"  ❌ 未注册 | {phone}")

    return result


async def test_concurrent_filtering():
    """测试并发筛号逻辑"""
    print("=" * 60)
    print("🧪 并发筛号逻辑模拟测试")
    print("=" * 60)

    # 初始化
    manager = MockManager()
    active_primary = manager.get_active_primary_accounts()
    concurrent_workers = len(active_primary)

    print(f"✅ 初始化完成，{concurrent_workers} 个账号并发")

    # 创建workers
    workers = []
    for account in active_primary:
        limiter = MockRateLimiter()
        filter_obj = MockFilter()
        workers.append({
            'account': account,
            'limiter': limiter,
            'filter': filter_obj
        })

    # 模拟100个号码
    phones = [f"+1234567{i:04d}" for i in range(100)]

    print(f"\n🚀 开始筛选 {len(phones)} 个号码")
    print(f"🔥 启用 {concurrent_workers} 个账号并发查询\n")

    start_time = datetime.now()
    registered_count = 0
    unregistered_count = 0

    # 批量并发处理
    batch_size = concurrent_workers
    for batch_start in range(0, len(phones), batch_size):
        batch_end = min(batch_start + batch_size, len(phones))
        batch_phones = [(i, phones[i]) for i in range(batch_start, batch_end)]

        # 为每个号码分配worker
        tasks = []
        for idx, (phone_idx, phone) in enumerate(batch_phones):
            worker = workers[idx % concurrent_workers]
            task = process_single_phone(phone_idx, phone, worker, manager)
            tasks.append(task)

        # 并发执行
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        for result in batch_results:
            if isinstance(result, Exception):
                print(f"  ⚠️ 异常: {result}")
                continue
            if result and result.get('registered'):
                registered_count += 1
            else:
                unregistered_count += 1

        # 显示进度
        progress = (batch_end / len(phones)) * 100
        print(f"\n📊 进度: {batch_end}/{len(phones)} ({progress:.1f}%) | 已注册: {registered_count} | 未注册: {unregistered_count}\n")

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
    print(f"总号码数: {len(phones)}")
    print(f"已注册: {registered_count}")
    print(f"未注册: {unregistered_count}")
    print(f"总耗时: {elapsed:.1f}秒")
    print(f"平均速度: {len(phones)/elapsed:.2f} 个/秒")
    print(f"并发倍数: {concurrent_workers}x")
    print("=" * 60)


async def test_rate_limiter_randomness():
    """测试速率限制器的随机性"""
    print("\n" + "=" * 60)
    print("🧪 测试速率限制器随机性")
    print("=" * 60)

    limiter = MockRateLimiter()
    delays = []

    for i in range(10):
        start = datetime.now()
        await limiter.wait_before_request()
        end = datetime.now()
        delay = (end - start).total_seconds()
        delays.append(delay)
        print(f"请求 {i+1}: 延迟 {delay:.2f}秒")

    avg_delay = sum(delays) / len(delays)
    min_delay = min(delays)
    max_delay = max(delays)

    print(f"\n统计:")
    print(f"  平均延迟: {avg_delay:.2f}秒")
    print(f"  最小延迟: {min_delay:.2f}秒")
    print(f"  最大延迟: {max_delay:.2f}秒")
    print(f"  延迟范围: {max_delay - min_delay:.2f}秒")
    print("=" * 60)


async def test_concurrent_safety():
    """测试并发安全性"""
    print("\n" + "=" * 60)
    print("🧪 测试并发安全性（共享变量）")
    print("=" * 60)

    # 模拟共享变量
    shared_counter = {'value': 0}
    lock = asyncio.Lock()

    async def increment_counter(worker_id):
        for i in range(100):
            async with lock:
                old_value = shared_counter['value']
                await asyncio.sleep(0.001)  # 模拟处理时间
                shared_counter['value'] = old_value + 1

    # 3个worker并发增加计数器
    tasks = [increment_counter(i) for i in range(3)]
    await asyncio.gather(*tasks)

    expected = 300
    actual = shared_counter['value']

    print(f"预期值: {expected}")
    print(f"实际值: {actual}")

    if expected == actual:
        print("✅ 并发安全测试通过")
    else:
        print(f"❌ 并发安全测试失败，差值: {expected - actual}")

    print("=" * 60)


if __name__ == '__main__':
    print("\n🔬 开始全面测试...\n")

    # 运行所有测试
    asyncio.run(test_rate_limiter_randomness())
    asyncio.run(test_concurrent_safety())
    asyncio.run(test_concurrent_filtering())

    print("\n✅ 所有测试完成！")
