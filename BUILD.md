# Telegram筛号工具 - 打包说明

## 快速打包

### Windows 打包（在 Windows 上执行）

1. 安装依赖：
```bash
pip install -r requirements_build.txt
```

2. 运行打包脚本：
```bash
build.bat
```

3. 打包完成后，在 `dist` 文件夹找到 `TelegramFilter.exe`

### macOS 打包（在 macOS 上执行）

1. 安装依赖：
```bash
pip3 install -r requirements_build.txt
```

2. 运行打包脚本：
```bash
chmod +x build.sh
./build.sh
```

3. 打包完成后，在 `dist` 文件夹找到 `TelegramFilter.app`

## 分发给其他用户

打包完成后，将以下文件打包成压缩包发给用户：

### Windows 版本
```
TelegramFilter-Windows.zip
├── TelegramFilter.exe        （主程序）
├── config_example.json        （配置示例）
└── 使用说明.txt               （使用说明）
```

### macOS 版本
```
TelegramFilter-macOS.zip
├── TelegramFilter.app         （主程序）
├── config_example.json        （配置示例）
└── 使用说明.txt               （使用说明）
```

用户收到后：
1. 解压缩
2. 复制 config_example.json 为 config.json
3. 编辑 config.json 填入自己的 API 信息
4. 双击运行程序
5. 按提示登录账号

## 使用说明

### 首次运行前

1. 将 `config.json` 放在可执行文件同目录
2. 先运行登录脚本（需要 Python 环境）：
```bash
python3 login.py
```
这会生成 `session_*.session` 文件

3. 将生成的 session 文件复制到可执行文件同目录

### Windows 使用

双击 `TelegramFilter.exe` 启动

### macOS 使用

双击 `TelegramFilter.app` 启动

或命令行：
```bash
open TelegramFilter.app
```

## 注意事项

1. **Session 文件**：必须先用 Python 环境登录生成 session 文件，打包后的程序无法交互式登录
2. **配置文件**：`config.json` 必须和可执行文件在同一目录
3. **代理设置**：如果使用代理，确保代理服务在运行
4. **跨平台**：Windows 版本只能在 Windows 上打包，macOS 版本只能在 macOS 上打包
5. **文件权限**：macOS 首次运行可能需要在"系统偏好设置 > 安全性与隐私"中允许

## 高级选项

### 单文件模式（更慢但便携）

修改 `build_config.spec` 中的 `EXE` 部分：
```python
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TelegramFilter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 改为 True 可显示调试信息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,  # 添加这行
)
```

### 添加图标

1. 准备图标文件：
   - Windows: `icon.ico`
   - macOS: `icon.icns`

2. 修改 spec 文件：
```python
exe = EXE(
    ...
    icon='icon.ico',  # Windows
    ...
)

app = BUNDLE(
    ...
    icon='icon.icns',  # macOS
    ...
)
```

### 调试模式

如果打包后运行出错，改为控制台模式查看错误：
```python
console=True,  # 在 EXE 部分
```

## 常见问题

### Q: 打包后运行报错 "No module named 'telethon'"
A: 确保 `hiddenimports` 包含所有依赖，重新打包

### Q: macOS 提示"已损坏"
A: 运行：
```bash
xattr -cr TelegramFilter.app
```

### Q: Windows Defender 报毒
A: PyInstaller 打包的程序可能被误报，添加信任或使用代码签名

### Q: 打包文件太大
A: 
- 使用虚拟环境打包，避免打包不必要的库
- 启用 UPX 压缩（已默认启用）
- 考虑使用 `--exclude-module` 排除不需要的模块

### Q: 无法登录账号
A: 打包后的程序不支持交互式登录，必须先在 Python 环境中用 `login.py` 生成 session 文件
