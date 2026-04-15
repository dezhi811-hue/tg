#!/usr/bin/env python3
"""
本地日志模块 - 记录到本地文件
"""
import os
import datetime
import traceback


class LocalLogger:
    """本地文件日志记录器"""

    def __init__(self, log_file="telegram_filter.log"):
        """初始化本地日志"""
        self.log_file = log_file
        self._write_log("=" * 60)
        self._write_log(f"程序启动 - {datetime.datetime.now()}")
        self._write_log("=" * 60)

    def _write_log(self, message):
        """写入日志到文件"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"{message}\n")
                f.flush()
        except Exception:
            pass

    def log(self, level, message, exception=None):
        """记录日志"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level}] {message}"
        self._write_log(log_line)

        if exception:
            self._write_log(f"异常: {str(exception)}")
            self._write_log(traceback.format_exc())

    def info(self, message):
        """记录 INFO 日志"""
        self.log('INFO', message)

    def warning(self, message, exception=None):
        """记录 WARNING 日志"""
        self.log('WARNING', message, exception)

    def error(self, message, exception=None):
        """记录 ERROR 日志"""
        self.log('ERROR', message, exception)

    def critical(self, message, exception=None):
        """记录 CRITICAL 日志"""
        self.log('CRITICAL', message, exception)


# 全局日志实例
_local_logger = None


def get_local_logger():
    """获取全局本地日志实例"""
    global _local_logger
    if _local_logger is None:
        _local_logger = LocalLogger()
    return _local_logger
