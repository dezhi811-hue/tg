#!/usr/bin/env python3
"""
测试日志功能
"""
import os
import sys

# 测试本地日志
print("=" * 60)
print("测试本地日志模块")
print("=" * 60)

try:
    from local_logger import get_local_logger
    local_logger = get_local_logger()

    local_logger.info("测试 INFO 日志")
    local_logger.warning("测试 WARNING 日志")
    local_logger.error("测试 ERROR 日志", Exception("测试异常"))
    local_logger.critical("测试 CRITICAL 日志")

    print("✅ 本地日志测试成功")

    # 检查日志文件
    if os.path.exists("telegram_filter.log"):
        print(f"✅ 日志文件已创建: telegram_filter.log")
        with open("telegram_filter.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"✅ 日志文件包含 {len(lines)} 行")
            print("\n最后 5 行日志:")
            for line in lines[-5:]:
                print(f"  {line.rstrip()}")
    else:
        print("❌ 日志文件未创建")

except Exception as e:
    print(f"❌ 本地日志测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试远程日志模块")
print("=" * 60)

try:
    from remote_logger import init_remote_logger

    # 使用测试配置（不会真正发送）
    bot_token = "test_token"
    chat_id = "test_chat_id"

    remote_logger = init_remote_logger(bot_token, chat_id, enabled=False)
    print("✅ 远程日志模块导入成功（未启用）")

except Exception as e:
    print(f"⚠️  远程日志模块测试: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
