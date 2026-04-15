"""
Telegram筛号工具 - 主程序（多账号版本）
"""
import asyncio
import argparse
from datetime import datetime
from account_manager import AccountManager
from rate_limiter import RateLimiter, SmartScheduler
from filter import TelegramFilter
from exporter import ResultExporter


def load_phones_from_file(filename):
    """从文件加载手机号列表"""
    with open(filename, 'r', encoding='utf-8') as f:
        phones = [line.strip() for line in f if line.strip()]
    return phones


async def main():
    parser = argparse.ArgumentParser(description='Telegram筛号工具（多账号版）')
    parser.add_argument('--phone', help='单个手机号')
    parser.add_argument('--file', help='手机号文件路径（每行一个）')
    parser.add_argument('--output', help='输出文件路径（支持.csv/.json）')
    parser.add_argument('--config', default='config.json', help='配置文件路径')
    parser.add_argument('--country', default='US', help='目标国家（US/CN等）')

    args = parser.parse_args()

    if not args.phone and not args.file:
        parser.error('请指定 --phone 或 --file 参数')

    print("="*60)
    print("🚀 Telegram 筛号工具 - 多账号版")
    print("="*60)

    # 初始化账号管理器
    print("\n📱 正在初始化账号...")
    account_manager = AccountManager(args.config)
    await account_manager.connect_all()

    # 初始化速率控制器
    rate_limiter = RateLimiter(account_manager.config['rate_limit'])

    # 初始化智能调度器
    scheduler = SmartScheduler(account_manager, rate_limiter)

    # 初始化筛选器
    filter_tool = TelegramFilter(scheduler)

    # 获取手机号列表
    if args.phone:
        phones = [args.phone]
    else:
        phones = load_phones_from_file(args.file)
        print(f"\n📋 已加载 {len(phones)} 个手机号")

    # 执行筛选
    print(f"\n🔍 开始筛选 {args.country} 号码...\n")
    print("="*60)

    results = await filter_tool.batch_check(phones, country=args.country)

    # 显示账号统计
    account_manager.print_stats()

    # 显示结果统计
    ResultExporter.print_summary(results)

    # 导出结果
    if args.output:
        if args.output.endswith('.csv'):
            ResultExporter.to_csv(results, args.output)
        elif args.output.endswith('.json'):
            ResultExporter.to_json(results, args.output)
        else:
            print("⚠️  输出文件格式不支持，请使用 .csv 或 .json")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_output = f'result_{timestamp}.csv'
            ResultExporter.to_csv(results, default_output)
    else:
        # 默认导出CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_output = f'result_{args.country}_{timestamp}.csv'
        ResultExporter.to_csv(results, default_output)

    # 断开所有连接
    await account_manager.disconnect_all()
    print("\n✅ 全部完成！")


if __name__ == '__main__':
    asyncio.run(main())
