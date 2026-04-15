#!/usr/bin/env python3
"""
Telegram筛号工具 - GUI启动脚本
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui_monitor import main

if __name__ == '__main__':
    main()
