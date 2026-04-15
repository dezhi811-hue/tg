#!/bin/bash

# Telegram筛号工具 - GUI启动脚本

echo "🚀 启动 Telegram 筛号工具 GUI..."

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装Python"
    exit 1
fi

# 检查PyQt5
python3 -c "import PyQt5" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 未找到PyQt5，请先安装："
    echo "   pip3 install PyQt5"
    exit 1
fi

# 运行GUI
python3 gui_monitor.py
