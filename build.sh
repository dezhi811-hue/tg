#!/bin/bash
# macOS/Linux 打包脚本

echo "🔨 开始打包 Telegram 筛号工具..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
pip3 install -r requirements_build.txt

# 清理旧文件
echo "🧹 清理旧文件..."
rm -rf build dist

# 打包
echo "🚀 开始打包..."
pyinstaller build_config.spec

# 检查结果
if [ -d "dist/TelegramFilter.app" ]; then
    echo "✅ 打包成功！"
    echo "📍 文件位置: dist/TelegramFilter.app"
    echo ""
    echo "⚠️  使用前请确保："
    echo "   1. config.json 在同目录"
    echo "   2. 已运行 login.py 生成 session 文件"
    echo "   3. session 文件复制到同目录"
else
    echo "❌ 打包失败，请查看错误信息"
    exit 1
fi
