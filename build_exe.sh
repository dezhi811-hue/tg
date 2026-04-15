#!/bin/bash
# =============================================
# TelegramFilter EXE 打包脚本
# 支持 macOS (交叉编译 Windows EXE) 和 Windows 本机打包
# =============================================

set -e

echo "========================================"
echo "TelegramFilter EXE 打包工具"
echo "========================================"

# 检测操作系统
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || -n "$WINDIR" ]]; then
    OS_TYPE="windows"
else
    OS_TYPE="linux"
fi

echo "检测到系统: $OS_TYPE"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

echo "Python 版本:"
python3 --version

# 检查 pip
if ! python3 -m pip --version &> /dev/null; then
    echo "❌ 未找到 pip，请先安装 pip"
    exit 1
fi

# 检查依赖
echo ""
echo "检查依赖..."
check_pkg() {
    python3 -c "import $1" 2>/dev/null && echo "  ✅ $1" || echo "  ❌ $1 (未安装)"
}

check_pkg PyQt5
check_pkg telethon
check_pkg phonenumbers
check_pkg pysocks

# 检查 pyinstaller
if ! python3 -m PyInstaller --version &> /dev/null; then
    echo ""
    echo "⚠️  PyInstaller 未安装，正在安装..."
    python3 -m pip install pyinstaller
fi

echo ""
echo "PyInstaller 版本:"
python3 -m PyInstaller --version

# 清理旧构建
echo ""
echo "清理旧构建文件..."
rm -rf build/ dist/ *.spec.bak 2>/dev/null || true

# 执行打包
echo ""
echo "开始打包 (这可能需要几分钟)..."
echo "========================================"

python3 -m PyInstaller TelegramFilter.spec --clean

echo ""
echo "========================================"
echo "✅ 打包完成！"
echo ""
echo "输出文件:"
ls -lh dist/

echo ""
echo "📦 EXE 文件位置: dist/TelegramFilter.exe"
echo ""
echo "使用方法:"
echo "  1. 将 EXE 复制到包含以下文件的文件夹:"
echo "     - config.json (账号配置)"
echo "     - phones.txt  (待检测号码)"
echo "  2. 双击运行 TelegramFilter.exe"
echo ""
echo "注意: 首次运行会创建 session 文件，"
echo "      之后会自动登录，无需重新扫码。"
echo "========================================"
