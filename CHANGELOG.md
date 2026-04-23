# Telegram筛号工具 - 更新日志

## v3.1.0 - 防封控大修 + 关键 bug 修复 (2026-04-24)

### 🔴 关键 bug 修复（批次一）
- **`get_config_path` EXE 模式路径错误**：之前用 `sys._MEIPASS`（PyInstaller 临时解压目录），导致用户在 exe 旁边修改的 `config.json` 永远不生效，跑的是打包时嵌进去的老默认值。这就是为什么实际筛号间隔是 7–8 秒而不是设置的 20–30 秒。现已改用 `sys.executable` 目录。
- **空返不计数导致单号被猛薅**：账号被风控开始全空返后，`request_count` 永远 = 0 → 单号冷却永远不触发 → 死循环。现在空返也 `mark_account_used`。
- **探针/单号上限冷却时长不一致**：定时探针失败冷却 15 分钟，空返探针冷却 10 分钟。统一为 **10 分钟**（`EMPTY_PROBE_COOLDOWN_SEC = 600`）。
- **`load_config` fallback 值过激进**：读不到 config.json 时 fallback `min_delay=3, max_delay=8`，与预期差太远。修正为 20/30。

### 🛡️ 防封控大修（批次二）

- **每账号设备指纹差异化**：引入 6 套内置指纹池（iPhone 14 Pro / iPhone 15 / Samsung / Pixel / MacBook / Windows 桌面），按账号 name 稳定 hash 分配。同一账号每次启动固定指纹，不同账号差异化。用户也可在 `config.json` 每账号显式配置 `device_model / system_version / app_version / lang_code / system_lang_code` 覆盖。
- **`InputPhoneContact` 字段随机化**：`client_id` 从固定 0 改为随机整数，`first_name` 从固定 'User' 改为从常见英文名池随机挑。消除 Telegram 风控最容易识别的静态特征。
- **代理配置修正**：
  - 6 元组（socks5, host, port, **rdns=True**, user, pass）确保 DNS 也走代理，不再泄露真实 IP
  - port 强制转 int（JSON 字符串 port 也兼容）
  - 空字符串 username/password 改成 None，修复"以空密码认证"失败
- **连接后 `get_me()` 校验**：代理或网络问题立即暴露，不再等到筛号时才失败
- **FloodWait 指数退避**：触发一次冷却 `wait × 1`，第 N 次触发 `wait × 2^(N-1)`，封顶 2 小时。避免反复踩同一账号。
- **`ResolvePhoneRequest` 开关**：`rate_limit.use_resolve_phone = true` 时走 Resolve（不入联系人簿，配额比 Import 松）。默认关闭，保持原 Import 语义（"能加为联系人"）。
- **静默读**：`rate_limit.silent_read_interval` 控制每 N 次查询穿插一次 `GetDialogsRequest`（默认 10），让风控看到"真人在用客户端"的行为。
- **周期清联系人簿**：`rate_limit.reset_contacts_interval` 控制每 N 次查询调一次 `ResetSavedRequest`（默认 50），兜底 `DeleteContactsRequest` 未及时清理的遗留。
- **单号请求上限冷却也统一 10 分钟**

### 新增配置字段（全部可选）

```json
"rate_limit": {
  "use_resolve_phone": false,
  "silent_read_interval": 10,
  "reset_contacts_interval": 50
}
```

每账号还可加 `device_model / system_version / app_version / lang_code / system_lang_code`。

### 注意事项
- 现有 session 是 Telethon 默认指纹登录的，升级后重连时指纹会变，Telegram 会把这次当"设备更新"。这是**一次性事件**，之后每次都稳定。
- 打包时**不要把 config.json 嵌进 exe**，让它必须是 exe 旁的那份（已修复路径解析，可以直接读到）。
- 新增 `test_batch12_sim.py` 覆盖本批次全部改动。

### 修改的文件
- `filter.py`：核心查询逻辑，新增 4 个 helper 函数
- `account_manager.py`：新增 `resolve_device_profile` / `build_proxy_config` 两个公共 helper
- `gui_monitor.py`：`get_config_path`、LoginThread、AccountCheckThread、cooldown 统一
- `login.py`：同步用公共 helper
- `config.example.json`：展示新增字段

## v3.0.4 - 两态结果 + 空返探针 + 慢速筛号 (2026-04-23)

### 改动
- 🎯 **结果简化为两态**：`已注册 / 未注册`，取消"未确认"和"号码无效"分类
  - 旧版把 B（号没注册）、C（号开了隐私"仅联系人可找"）、D（账号被限）混成同一个"空返回"反复同账号复查，日志刷屏且无意义
  - API 层 B 和 C 本就无法区分，故归并为"未注册"；D 改由独立机制识别
- 🔍 **连续空返回触发定向探针（固定 15 次）**：
  - 单账号连续 15 个号查成未注册 → 立即用该账号查一次已知注册的探针号
  - 探针命中 → 说明那 15 个确实是 B/C，账号正常，清零继续筛
  - 探针未命中 → 确诊账号异常，停该号 10 分钟
- 🔁 **冷却期满强制复验**：10 分钟冷却结束后再查一次探针
  - 命中 → 恢复筛号
  - 未命中 → 再停 10 分钟，循环直到恢复
- 🐢 **放慢筛号速度**：默认每号间隔 **20–30 秒**（之前 1–4 秒）
  - 设置页"最小/最大延迟"输入范围扩到 1–60 / 5–120
- 🧹 **日志清爽化**：去掉"空返回复查 1/2"、"未确认"、"号码无效"等中间态输出
- ✅ **用户名保存确认**：已注册号导出到 `registered_XXX.txt` 会拼 `@username`（对方设了用户名时），筛号日志也同步显示

### 新增
- `CONSECUTIVE_EMPTY_TRIGGER = 15` 固定阈值
- `EMPTY_PROBE_COOLDOWN_SEC = 600`（10 分钟）固定冷却时长
- `_probe_after_cooldown` 复验机制
- `test_new_flow.py` 覆盖健康账号空返命中 / 异常账号冷却+复验两个新场景

### 动机
旧逻辑一个账号被 Telegram 静默限制后，工具会继续用它查号，导致连续几十个号被误判为"未确认"。周期探针每 20 个号才验一次，发现太慢。新机制以"连续空返回"为可疑信号、以"定向探针"为确诊手段，既不误杀正常账号，也能在 15 个号内发现被限账号。

## v3.0.3 - 并发真实化 + 探针/冷却/计数全面修复 (2026-04-22)

### 修复
- 🔧 **worker 真绑账号**：每个工作号的 filter 固定到自己账号，修复旧版"三/五个 worker 挤到同一个号"的问题，并发数真实生效
- 🔧 **探针按"总完成数"判定**：改用 `finished_total` 替代连续前缀水位线，头号卡住时探针也能正常触发，不会漏检
- 🔧 **探针退出条件修正**：`phone_queue.empty()` 不再作为退出信号，改为"全部号已跑完"，避免号少时探针提前返回
- 🔧 **单账号请求上限真生效**：worker 每次取号前检查 `request_count`，到点自动冷却 `error_cooldown` 秒后恢复
- 🔧 **探针公平轮询**：按 `last_probe_id` 挑最久未抽的号，冷却恢复后第一时间被探针验证

### 新增
- ✅ **账号管理表格真实化**：
  - 列改为：账号名称 / 手机号 / **探针次数** / 登录状态 / 代理状态 / 角色 / 运行状态 / **封禁数** / 统计
  - 运行状态冷却期间显示 `🧊 冷却至 HH:MM:SS`
  - 角色 / 运行状态 随替补、冷却动态更新
- ✅ **实时并发显示**：窗口标题显示 `实时并发 4/5`，冷却时自动降、恢复后自动升
- ✅ **严格并发数**：未连接成功的号不占 worker 名额，日志明示 `设定 5，实际 3`
- ✅ **FloodWait / 请求上限 / 探针失败** 三条路径都计入 `block_count`

### 内部改动
- `AccountManager` 新增 `probe_count` / `block_count` 字段并暴露在 runtime snapshot
- 筛号收尾 emit 一次最终状态快照，用户能看到最终的探针和封禁统计
- 新增 `test_sim_v3.py` 覆盖 pin / 冷却 / 水位线 / 探针公平性等 6 个场景

## v3.0.2 - 探针失败改为冷却恢复 (2026-04-22)

### 改动
- 🧊 **探针连续失败不再永久暂停账号**：改为冷却 `error_cooldown` 秒后自动恢复继续筛号
- 🧊 默认冷却时长调整为 **900 秒（15 分钟）**
- ⏸️ 备用号顶替逻辑在探针失败路径上停用（代码保留，暂未触发）
- ▶️ 冷却结束自动清除封禁标记，日志提示"冷却结束，恢复筛号"

### 动机
旧逻辑一旦探针失败就把账号永久踢出当次任务并让备用号顶替，少数偶发抖动会让好账号被白白闲置。改为冷却等待更贴合 Telegram 限速实际：只要等风控窗口过去，账号就能继续跑。

## v3.0.1 - username 输出 + GUI 自动更新 (2026-04-22)

### 新增功能
- ✅ **`registered_XXX.txt` 追加 username** - 每行手机号后拼接 `@username`（仅当对方设置了公开用户名），方便事后直接联系；没设置的用户保持原格式
- ✅ **GUI 检查更新按键** - 顶栏右上角"🔄 检查更新"一键检测 GitHub 最新 Release，新版本下载并自动替换 `.exe`，完成后自动重启（仅 Windows 打包版）
- ✅ **版本常量** - 新增 `version.py`，今后每次发版改一行即可

### 内部改动
- 新增 `updater.py`：GitHub API 查询 + 下载 + Windows `.bat` 自替换脚本
- `build_config.spec` 纳入 `updater` / `version` 模块
- 仓库改为 Public 以支持匿名 API 访问（无需在 exe 里嵌入 token）

## v3.0 - 队列并发 + 备用号自动替补 (2026-04-21)

### 新增功能
- ✅ **并发工作号数量可配置** - 设置页新增"并发工作号数量"选项，可自由决定几个号同时跑、几个号留作备用
- ✅ **备用号自动替补** - 工作号被探针判定异常并暂停时，系统自动从备用号中升级一个顶上，无需手动干预
- ✅ **队列 + worker 并发筛号** - 每个工作号独立从队列拉号处理，消除木桶效应，筛选速度随并发数线性提升
- ✅ **进度水位线** - 乱序完成时只推进"连续已完成前缀"，中断恢复不会跳过任何未处理号

### 优化改进
- 🔧 探针改为按账号独立计数 - 单账号连续失败只暂停它自己，其他账号继续跑，不再因偶发抖动导致整体停摆
- 🔧 启动时账号检测并行化 - 多账号连通性检查由串行改为并行，启动更快
- 🔧 运行态 worker 池动态扩展 - `asyncio.wait` 轮询替换旧的一次性 `gather`，替补 worker 能被正确等待
- 🔧 账号管理器支持 `config['primary_count']` 字段 - 默认等于账号总数，兼容旧配置

### 兼容性
- ⚠️ 旧版 `config.json` 无需改动即可用，`primary_count` 不填默认全部账号作为工作号
- ⚠️ 进度文件 `filter_progress.json` 格式兼容 v2.0

## v2.0 - 多账号版本 (2026-04-07)

### 新增功能
- ✅ 多账号管理系统 - 支持3-10个账号轮换
- ✅ 智能速率控制 - 随机延迟、错误重试、自动暂停
- ✅ 美国号码支持 - 自动格式化多种美国号码格式
- ✅ 防封策略 - FloodWait处理、账号切换、请求限制
- ✅ 账号统计 - 实时显示每个账号的使用情况
- ✅ 智能调度器 - 自动选择最优账号执行任务

### 优化改进
- 🔧 重构筛选核心模块，支持调度器模式
- 🔧 增强错误处理和重试机制
- 🔧 优化输出格式，增加emoji状态指示
- 🔧 添加国家代码检测和格式化

### 文件结构
- `main_multi.py` - 多账号主程序
- `account_manager.py` - 账号管理
- `rate_limiter.py` - 速率控制
- `phone_utils.py` - 号码工具
- `GUIDE.md` - 详细使用指南
- `run.sh` - 快速启动脚本

## v1.0 - 初始版本

### 基础功能
- ✅ 单账号筛选
- ✅ 验证号码是否注册
- ✅ 获取用户活跃状态
- ✅ CSV/JSON导出
