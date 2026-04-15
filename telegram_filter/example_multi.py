"""
使用示例 - 多账号版本
"""
import asyncio
from account_manager import AccountManager
from rate_limiter import RateLimiter, SmartScheduler
from filter import TelegramFilter


async def example_multi_account():
    """示例：使用多账号筛选"""
    # 初始化
    account_manager = AccountManager('config.json')
    await account_manager.connect_all()

    rate_limiter = RateLimiter(account_manager.config['rate_limit'])
    scheduler = SmartScheduler(account_manager, rate_limiter)
    filter_tool = TelegramFilter(scheduler)

    # 美国号码列表
    us_phones = [
        '+12025551234',
        '2025551235',
        '(202) 555-1236'
    ]

    # 批量检查
    results = await filter_tool.batch_check(us_phones, country='US')

    # 显示结果
    for result in results:
        if result['registered']:
            print(f"✅ {result['phone']} - {result['status']} - @{result['username']}")
        else:
            print(f"❌ {result['phone']} - {result['error']}")

    # 显示统计
    account_manager.print_stats()

    # 断开
    await account_manager.disconnect_all()


if __name__ == '__main__':
    asyncio.run(example_multi_account())
