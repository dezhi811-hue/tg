"""
结果导出模块
"""
import json
import csv
from datetime import datetime


class ResultExporter:
    @staticmethod
    def to_csv(results, filename):
        """导出为CSV格式"""
        if not results:
            print("没有数据可导出")
            return

        fieldnames = [
            'phone', 'original_phone', 'country', 'registered', 'user_id', 'username',
            'first_name', 'last_name', 'status', 'last_seen',
            'is_bot', 'error'
        ]

        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"✅ 已导出到 {filename}")

    @staticmethod
    def to_json(results, filename):
        """导出为JSON格式"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"✅ 已导出到 {filename}")

    @staticmethod
    def print_summary(results):
        """打印统计摘要"""
        total = len(results)
        registered = sum(1 for r in results if r['registered'])
        online = sum(1 for r in results if r['status'] == 'online')
        recently = sum(1 for r in results if r['status'] in ['online', 'recently'])

        print("\n" + "="*50)
        print("📊 筛选结果统计")
        print("="*50)
        print(f"总数: {total}")
        print(f"已注册: {registered} ({registered/total*100:.1f}%)")
        print(f"当前在线: {online}")
        print(f"最近活跃: {recently}")
        print("="*50 + "\n")
