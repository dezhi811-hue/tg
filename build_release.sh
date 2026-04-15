#!/bin/bash
# 打包并创建分发包

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
rm -rf build dist TelegramFilter-macOS.zip

# 打包
echo "🚀 开始打包..."
pyinstaller build_config.spec

# 检查结果
if [ -d "dist/TelegramFilter.app" ]; then
    echo "✅ 打包成功！"

    # 创建分发包
    echo "📦 创建分发包..."
    cd dist
    mkdir -p TelegramFilter-macOS
    cp -r TelegramFilter.app TelegramFilter-macOS/
    cp ../config_example.json TelegramFilter-macOS/
    cp ../使用说明.txt TelegramFilter-macOS/

    # 压缩
    zip -r TelegramFilter-macOS.zip TelegramFilter-macOS
    rm -rf TelegramFilter-macOS

    echo ""
    echo "✅ 分发包创建完成！"
    echo "📍 文件位置: dist/TelegramFilter-macOS.zip"
    echo ""
    echo "📤 发送给用户："
    echo "   1. 将 TelegramFilter-macOS.zip 发送给用户"
    echo "   2. 用户解压后按照"使用说明.txt"操作"
else
    echo "❌ 打包失败，请查看错误信息"
    exit 1
fi
