"""
使用示例
"""
import asyncio
from auth import TelegramAuth
from filter import TelegramFilter


async def example_single_check():
    """示例：检查单个手机号"""
    # 连接
    auth = TelegramAuth('config.json')
    client = await auth.connect()

    # 创建筛选器
    filter_tool = TelegramFilter(client, rate_limit=1)

    # 检查手机号
    result = await filter_tool.check_phone('+8613800138000')

    print(f"手机号: {result['phone']}")
    print(f"已注册: {result['registered']}")
    if result['registered']:
        print(f"用户名: {result['username']}")
        print(f"姓名: {result['first_name']} {result['last_name']}")
        print(f"状态: {result['status']}")
        print(f"最后上线: {result['last_seen']}")

    # 断开
    await auth.disconnect()


async def example_batch_check():
    """示例：批量检查"""
    auth = TelegramAuth('config.json')
    client = await auth.connect()

    filter_tool = TelegramFilter(client, rate_limit=1)

    phones = [
        '+8613800138000',
        '+8613800138001',
        '+8613800138002'
    ]

    # 批量检查，带回调
    def on_result(result):
        status = '✅' if result['registered'] else '❌'
        print(f"{status} {result['phone']} - {result.get('status', 'N/A')}")

    results = await filter_tool.batch_check(phones, callback=on_result)

    await auth.disconnect()

    return results


if __name__ == '__main__':
    # 运行示例
    asyncio.run(example_single_check())
