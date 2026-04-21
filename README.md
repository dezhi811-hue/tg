# Telegram 筛号工具（多账号版）

验证手机号是否注册Telegram，并获取用户活跃度信息。支持多账号轮换，智能防封控制。

## 功能特性

- ✅ 验证手机号是否注册Telegram
- ✅ 获取用户最后上线时间和活跃状态
- ✅ 支持美国号码（+1）和中国号码（+86）
- ✅ **多账号轮换** - 避免单账号频繁请求
- ✅ **智能速率控制** - 随机延迟、错误重试、自动暂停
- ✅ **防封策略** - 账号切换、请求限制、FloodWait处理
- ✅ 批量筛选支持
- ✅ 结果导出（CSV/JSON）
- ✅ **已注册号自动分组** - 按活跃度（近 1 个月 / 1-6 个月 / 更久）分段写入 `registered_XXX.txt`，行末追加 `@username`（若有）
- ✅ **GUI 一键检查更新** - 顶栏"🔄 检查更新"按键自动从 GitHub Release 下载最新 `.exe` 并重启（仅 Windows 打包版）

## 安装

### Windows 用户（推荐）

直接下载打包好的 exe，无需安装 Python：

👉 **[最新版本下载（v3.0.1）](https://github.com/dezhi811-hue/tg/releases/latest)**

下载 `TelegramFilter-Windows.zip` 解压后双击 `TelegramFilter.exe` 即可运行。
以后新版本直接在 GUI 顶栏点"🔄 检查更新"自动下载。

### 源码运行（开发者）

```bash
cd /Volumes/waijie/tg
pip install -r requirements.txt
python run_gui.py
```

## 配置

### 1. 获取API凭证

为每个账号获取API凭证：
1. 访问 https://my.telegram.org/apps
2. 登录你的Telegram账号
3. 创建应用，获取 `api_id` 和 `api_hash`
4. 重复以上步骤为其他账号获取凭证

### 2. 配置文件

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
  "accounts": [
    {
      "name": "account1",
      "api_id": "你的API_ID",
      "api_hash": "你的API_HASH",
      "phone": "+1234567890"
    },
    {
      "name": "account2",
      "api_id": "另一个API_ID",
      "api_hash": "另一个API_HASH",
      "phone": "+1234567891"
    }
  ],
  "rate_limit": {
    "requests_per_account": 30,
    "min_delay": 3,
    "max_delay": 8,
    "account_switch_delay": 60,
    "error_cooldown": 300
  },
  "target_country": "US"
}
```

**配置说明：**
- `requests_per_account`: 每个账号连续请求次数上限（建议20-50）
- `min_delay`: 最小延迟秒数（建议3-5秒）
- `max_delay`: 最大延迟秒数（建议8-15秒）
- `account_switch_delay`: 切换账号后的等待时间
- `error_cooldown`: 出错后的冷却时间

## 使用方法

### 🖥️ GUI版本（推荐，最简单）

```bash
# 启动图形界面
python gui.py

# 或使用启动脚本
./run_gui.sh
# Windows: python run_gui.py
```

**GUI功能：**
- ✅ 可视化账号管理（添加/编辑/删除）
- ✅ 直接输入或导入号码文件
- ✅ 实时查看筛选进度和日志
- ✅ 统计信息可视化
- ✅ 一键导出结果

### 💻 命令行版本（高级用户）

```bash
# 单个美国号码验证
python main_multi.py --phone +12025551234 --country US

# 批量验证美国号码
python main_multi.py --file us_phones.txt --country US --output result_us.csv

# 批量验证中国号码
python main_multi.py --file cn_phones.txt --country CN --output result_cn.csv
```

### 单账号版本（简单场景）

```bash
python main.py --phone +12025551234
```

## 号码格式

### 美国号码支持多种格式：
- `+12025551234`
- `12025551234`
- `2025551234`
- `(202) 555-1234`
- `202-555-1234`

程序会自动格式化为标准格式 `+12025551234`

## 输出结果

### CSV 导出
CSV文件包含以下字段：
- `phone`: 格式化后的号码
- `original_phone`: 原始输入号码
- `country`: 国家代码（US/CN等）
- `registered`: 是否注册（True/False）
- `user_id`: Telegram用户ID
- `username`: 用户名
- `first_name`: 名字
- `last_name`: 姓氏
- `status`: 在线状态
  - `online` 🟢 - 当前在线
  - `recently` 🟡 - 最近在线（几分钟到几小时）
  - `within_week` 🟠 - 一周内在线
  - `within_month` 🔴 - 一个月内在线
  - `offline` ⚫ - 离线（显示具体时间）
  - `long_ago` ⚪ - 很久未上线
- `last_seen`: 最后上线时间
- `is_bot`: 是否为机器人
- `error`: 错误信息

### 已注册号分组文件 `registered_XXX.txt`

筛选过程中 GUI 会按批次把**已注册**的号码写入 `registered_001.txt`、`registered_002.txt` ……按活跃度分成三段：

```
📅 近一个月内活跃
+12025551234 @john_doe | recently | 2026-04-20 18:30:00
+14085559876 @alice99 | online | 2026-04-21 09:15:00

📅 1-6 个月内活跃
+12025550000 | within_month | 2026-03-01 10:00:00

📅 半年以上未活跃
+12025557777 | long_ago
```

每行格式：`手机号 @用户名 | 活跃状态 | 最后上线时间`。用户没有公开 username 时省略 `@xxx`。

## 自动更新（仅 Windows .exe 版）

GUI 顶栏点击 **🔄 检查更新**：

1. 程序向 GitHub 查询最新 Release
2. 发现新版本弹窗显示更新说明
3. 点确认 → 自动下载 `TelegramFilter-Windows.zip` 并解压
4. 当前程序退出 → 后台脚本替换 exe → 自动启动新版本

**注意**：源码模式运行（`python run_gui.py`）不会触发自动更新，请用 `git pull`。

## 防封策略

程序内置多重防封机制：

1. **多账号轮换** - 自动在多个账号间切换
2. **智能延迟** - 每次请求随机延迟3-8秒
3. **请求限制** - 单账号连续请求不超过30次
4. **错误处理** - 遇到FloodWait自动切换账号
5. **自动重试** - 失败自动重试最多3次
6. **冷却机制** - 错误后增加延迟时间

## 注意事项

⚠️ **重要提醒**：
- 请遵守当地法律法规和Telegram服务条款
- 建议使用3-5个账号进行轮换
- 不要设置过快的请求速率
- 仅用于合法用途（市场调研、用户验证等）
- 尊重用户隐私，不要滥用数据
- 首次运行需要为每个账号输入验证码

## 常见问题

**Q: 账号被封了怎么办？**
A: 降低请求频率，增加延迟时间，添加更多账号轮换。

**Q: 需要多少个账号？**
A: 建议至少3个账号，5个以上更安全。

**Q: 可以24小时运行吗？**
A: 不建议。建议分批次运行，每批次后休息几小时。
