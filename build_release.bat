@echo off
REM 打包并创建分发包

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
if exist TelegramFilter-Windows.zip del TelegramFilter-Windows.zip

REM 打包
echo 🚀 开始打包...
pyinstaller build_config.spec

REM 检查结果
if exist "dist\TelegramFilter.exe" (
    echo ✅ 打包成功！

    REM 创建分发包
    echo 📦 创建分发包...
    cd dist
    mkdir TelegramFilter-Windows
    copy TelegramFilter.exe TelegramFilter-Windows\
    copy ..\config_example.json TelegramFilter-Windows\
    copy ..\使用说明.txt TelegramFilter-Windows\

    REM 压缩（需要安装 7-Zip 或使用 PowerShell）
    powershell Compress-Archive -Path TelegramFilter-Windows -DestinationPath TelegramFilter-Windows.zip -Force
    rmdir /s /q TelegramFilter-Windows

    echo.
    echo ✅ 分发包创建完成！
    echo 📍 文件位置: dist\TelegramFilter-Windows.zip
    echo.
    echo 📤 发送给用户：
    echo    1. 将 TelegramFilter-Windows.zip 发送给用户
    echo    2. 用户解压后按照"使用说明.txt"操作
) else (
    echo ❌ 打包失败，请查看错误信息
    exit /b 1
)
