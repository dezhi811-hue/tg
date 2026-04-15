#!/usr/bin/env python3
"""
远程日志模块 - 将日志发送到远程服务器
"""
import requests
import json
import datetime
import platform
import traceback
from threading import Thread
from queue import Queue


class RemoteLogger:
    """远程日志记录器"""

    def __init__(self, api_url=None, enabled=True):
        """
        初始化远程日志
        :param api_url: 远程日志接收 API 地址
        :param enabled: 是否启用远程日志
        """
        self.api_url = api_url or "https://your-log-server.com/api/logs"
        self.enabled = enabled
        self.queue = Queue()
        self.worker_thread = None

        if self.enabled:
            self.start_worker()

    def start_worker(self):
        """启动后台工作线程"""
        self.worker_thread = Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _worker(self):
        """后台工作线程，处理日志队列"""
        while True:
            try:
                log_data = self.queue.get()
                if log_data is None:
                    break
                self._send_log(log_data)
            except Exception:
                pass

    def _send_log(self, log_data):
        """发送日志到远程服务器"""
        try:
            requests.post(
                self.api_url,
                json=log_data,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
        except Exception:
            # 静默失败，不影响主程序
            pass

    def log(self, level, message, extra=None):
        """
        记录日志
        :param level: 日志级别 (info, warning, error, critical)
        :param message: 日志消息
        :param extra: 额外信息字典
        """
        if not self.enabled:
            return

        log_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'level': level,
            'message': message,
            'platform': platform.system(),
            'platform_version': platform.version(),
            'python_version': platform.python_version(),
        }

        if extra:
            log_data.update(extra)

        self.queue.put(log_data)

    def info(self, message, **kwargs):
        """记录 INFO 级别日志"""
        self.log('info', message, kwargs)

    def warning(self, message, **kwargs):
        """记录 WARNING 级别日志"""
        self.log('warning', message, kwargs)

    def error(self, message, **kwargs):
        """记录 ERROR 级别日志"""
        self.log('error', message, kwargs)

    def critical(self, message, exception=None, **kwargs):
        """记录 CRITICAL 级别日志"""
        extra = kwargs.copy()
        if exception:
            extra['exception'] = str(exception)
            extra['traceback'] = traceback.format_exc()
        self.log('critical', message, extra)

    def shutdown(self):
        """关闭远程日志"""
        if self.enabled:
            self.queue.put(None)
            if self.worker_thread:
                self.worker_thread.join(timeout=2)


# 全局日志实例
_remote_logger = None


def init_remote_logger(api_url=None, enabled=True):
    """初始化全局远程日志"""
    global _remote_logger
    _remote_logger = RemoteLogger(api_url, enabled)
    return _remote_logger


def get_remote_logger():
    """获取全局远程日志实例"""
    global _remote_logger
    if _remote_logger is None:
        _remote_logger = RemoteLogger(enabled=False)
    return _remote_logger
