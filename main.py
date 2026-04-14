"""
Telegram筛号工具 - 主程序
"""
import asyncio
import argparse
from datetime import datetime
from auth import TelegramAuth
from filter import TelegramFilter
from exporter import ResultExporter


def load_phones_from_file(filename):
    """从文件加载手机号列表"""
    with open(filename, 'r', encoding='utf-8') as f:
        phones = [line.strip() for line in f if line.strip()]
    return phones


async def main():
    parser = argparse.ArgumentParser(description='Telegram筛号工具')
    parser.add_argument('--phone', help='单个手机号')
    parser.add_argument('--file', help='手机号文件路径（每行一个）')
    parser.add_argument('--output', help='输出文件路径（支持.csv/.json）')
    parser.add_argument('--config', default='config.json', help='配置文件路径')

    args = parser.parse_args()

    if not args.phone and not args.file:
        parser.error('请指定 --phone 或 --file 参数')

    # 初始化
    print("🚀 正在连接Telegram...")
    auth = TelegramAuth(args.config)
    client = await auth.connect()

    filter_tool = TelegramFilter(client, rate_limit=1)

    # 获取手机号列表
    if args.phone:
        phones = [args.phone]
    else:
        phones = load_phones_from_file(args.file)
        print(f"📋 已加载 {len(phones)} 个手机号")

    # 执行筛选
    print("\n开始筛选...\n")
    results = await filter_tool.batch_check(phones)

    # 显示统计
    ResultExporter.print_summary(results)

    # 导出结果
    if args.output:
        if args.output.endswith('.csv'):
            ResultExporter.to_csv(results, args.output)
        elif args.output.endswith('.json'):
            ResultExporter.to_json(results, args.output)
        else:
            print("⚠️  输出文件格式不支持，请使用 .csv 或 .json")
    else:
        # 默认导出CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_output = f'result_{timestamp}.csv'
        ResultExporter.to_csv(results, default_output)

    # 断开连接
    await auth.disconnect()
    print("✅ 完成！")


if __name__ == '__main__':
    asyncio.run(main())
