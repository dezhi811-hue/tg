#!/usr/bin/env python3
"""
远程日志模块 - 将日志发送到 Telegram Bot
"""
import requests
import json
import datetime
import platform
import traceback
from threading import Thread
from queue import Queue


class RemoteLogger:
    """远程日志记录器 - 发送到 Telegram Bot"""

    def __init__(self, bot_token=None, chat_id=None, enabled=True):
        """
        初始化远程日志
        :param bot_token: Telegram Bot Token
        :param chat_id: 接收日志的 Chat ID
        :param enabled: 是否启用远程日志
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled and bot_token and chat_id
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
                self._send_to_telegram(log_data)
            except Exception:
                pass

    def _send_to_telegram(self, log_data):
        """发送日志到 Telegram"""
        try:
            # 格式化消息
            level_emoji = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'error': '❌',
                'critical': '🔥'
            }
            emoji = level_emoji.get(log_data['level'], '📝')

            message = f"{emoji} *{log_data['level'].upper()}*\n\n"
            message += f"*消息:* {log_data['message']}\n"
            message += f"*时间:* {log_data['timestamp']}\n"
            message += f"*平台:* {log_data['platform']} {log_data['platform_version']}\n"

            # 添加额外信息
            if 'exception' in log_data:
                message += f"\n*异常:* `{log_data['exception']}`\n"

            if 'traceback' in log_data:
                # Telegram 消息长度限制 4096，截断 traceback
                tb = log_data['traceback']
                if len(tb) > 1000:
                    tb = tb[:500] + "\n...\n" + tb[-500:]
                message += f"\n*堆栈:*\n```\n{tb}\n```"

            # 其他额外字段
            for key, value in log_data.items():
                if key not in ['level', 'message', 'timestamp', 'platform',
                              'platform_version', 'python_version', 'exception', 'traceback']:
                    message += f"\n*{key}:* {value}"

            # 发送到 Telegram
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            requests.post(
                url,
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                },
                timeout=10
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
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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


def init_remote_logger(bot_token=None, chat_id=None, enabled=True):
    """初始化全局远程日志"""
    global _remote_logger
    _remote_logger = RemoteLogger(bot_token, chat_id, enabled)
    return _remote_logger


def get_remote_logger():
    """获取全局远程日志实例"""
    global _remote_logger
    if _remote_logger is None:
        _remote_logger = RemoteLogger(enabled=False)
    return _remote_logger
