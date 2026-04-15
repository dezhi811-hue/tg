#!/bin/bash

# Telegram筛号工具 - 快速启动脚本

echo "=================================="
echo "Telegram 筛号工具 - 快速启动"
echo "=================================="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装Python"
    exit 1
fi

# 检查依赖
if [ ! -d "venv" ]; then
    echo "📦 首次运行，正在创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 检查配置文件
if [ ! -f "config.json" ]; then
    echo "⚠️  未找到config.json，请先配置："
    echo "   cp config.example.json config.json"
    echo "   然后编辑config.json填入你的API凭证"
    exit 1
fi

# 运行
echo ""
echo "🚀 启动筛号工具..."
echo ""

if [ -z "$1" ]; then
    echo "用法："
    echo "  ./run.sh us_phones.txt          # 筛选美国号码"
    echo "  ./run.sh cn_phones.txt CN       # 筛选中国号码"
    exit 1
fi

PHONE_FILE=$1
COUNTRY=${2:-US}

python3 main_multi.py --file "$PHONE_FILE" --country "$COUNTRY" --output "result_${COUNTRY}_$(date +%Y%m%d_%H%M%S).csv"
