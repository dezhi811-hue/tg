@echo off
REM Windows 打包脚本

echo 🔨 开始打包 Telegram 筛号工具...

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，请先安装
    exit /b 1
)

REM 检查依赖
echo 📦 检查依赖...
pip install -r requirements_build.txt

REM 清理旧文件
echo 🧹 清理旧文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 打包
echo 🚀 开始打包...
pyinstaller build_config.spec

REM 检查结果
if exist "dist\TelegramFilter.exe" (
    echo ✅ 打包成功！
    echo 📍 文件位置: dist\TelegramFilter.exe
    echo.
    echo ⚠️  使用前请确保：
    echo    1. config.json 在同目录
    echo    2. 已运行 login.py 生成 session 文件
    echo    3. session 文件复制到同目录
) else (
    echo ❌ 打包失败，请查看错误信息
    exit /b 1
)
