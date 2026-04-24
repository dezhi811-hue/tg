# 号池架构设计方案 v1

> 目标：从当前"固定 5 号硬并发"过渡到"**任意规模 N 的号池，动态并发 K = f(N)**"。兼容现有 config.json 和 session 文件，老用户零迁移成本。支持 N = 5 到 200+，同一套代码、同一套配置。

---

## 0. 规模伸缩原则（Scale-Aware）

所有后续章节里出现的"50 号"只是**示例**。真实实现必须按 N 自适应，不写任何硬编码的池子大小：

### K（并发数）与 N（池子大小）的关系

```python
def default_concurrency(N):
    # 默认公式：池子越大，并发占比越小（分散风险）
    if N <= 5:   return max(1, N)           # 小号池全开也安全
    if N <= 20:  return max(4, N // 4)      # 中号池 25%
    if N <= 100: return max(6, N // 8)      # 大号池 12.5%
    return max(10, N // 12)                 # 超大号池 8%
```

| N | 建议 K | 备注 |
|---|--------|------|
| 5  | 5  | 全开（现有场景） |
| 20 | 5  | |
| 50 | 6-8 | 你的目标 |
| 100 | 10-12 | |
| 200 | 16-20 | |

K 默认按上式算，UI 上**允许用户覆盖**（`pool_config.max_concurrency`）。UI 检测手动 K > 推荐值的 1.5 倍时弹黄字警告"并发过高易被 IP 聚簇识别"。

### 日产量与 N 的关系

按 §5.11 的日配额分层 × 典型号龄分布（warmup 10%、3-30d 70%、30d+ 20%）：

```
日产量 ≈ N × 平均单号日配额(约 85) × 工作日活跃率(约 0.9)
      ≈ N × 76
```

| N | 稳态日产量 | 备注 |
|---|----------|------|
| 20 | ~1500 | |
| 50 | ~3800 | 你的目标区间 |
| 100 | ~7600 | |
| 200 | ~15000 | 需 SQLite，见 §8 |

### 动态扩缩

用户任何时候可以：
- **批量导入新号** → 池子 N 变大，下次 `get_active_batch` 自动算新 K
- **手动 retire 老号 / 号被 FW 熔断** → N 变小，K 自动下调
- **设置页调 `max_concurrency`** → 立刻生效，下一轮挑号按新值
- **代理数 < 号数** → K 自动封顶到"有代理的号数量"，无代理号不会被调度

**实现要点**：`AccountPool.get_active_batch()` 每次调用前重新计算 K，**不缓存**；`max_concurrency` 读取用 getter 每次问 config，不在 `__init__` 固定。

---

## 1. 核心概念

### 1.1 三层状态机

```
              首登成功             预热期满            FloodWait ≥ 3 /
  [NEW]  --->  [WARMUP]  --->  [ACTIVE]  ---->  [RETIRED]
                  |               ^                  |
                  |               |                  | 管理员手动
                  +-----> [COOLING] <----------+ 解除
                          (临时冷却 10-60 min 随机)
```

| 状态 | 含义 | 可否被筛号调度 |
|------|------|-----------------|
| `warmup` | 首登 < 72h，只允许心跳行为 | ❌ |
| `active` | 正常参与筛号 | ✅ |
| `cooling` | 单轮配额用尽 / 空返探针失败 | ❌（到时自动转 active） |
| `retired` | 死号 / FloodWait 累计超限 / 手动封存 | ❌（永久） |

### 1.2 选号策略

`AccountPool.get_active_batch(k)` 返回 k 个号，优先级：

1. `state == active` 的号
2. 健康分降序
3. 上次使用时间升序（避免猛薅同一个号）
4. 同一代理/同一 /24 子网的号不同时出现在同一批

> 筛号并发 K 按 §0 公式：`K = min(max_concurrency_override or default_concurrency(N), len(active_pool))`。默认跟随 N 动态算，用户可在 UI 覆盖。

### 1.3 健康分公式

每号一个 0-100 分：

```
score = 100
      - floodwait_count_24h * 15      # 24h 内 FloodWait 次数，每次扣 15
      - empty_return_ratio * 40       # 空返率（0-1），满权重 40
      - (time_since_first_login < 72h) * 20  # 还在预热期
      + min(success_count_24h, 50) / 5       # 24h 成功数加分，封顶 +10

# 分数 < 30 自动进入 cooling；< 10 进入 retired
```

---

## 2. 数据模型

### 2.1 config.json（保持兼容）

只加一个顶层字段 `pool_config`：

```json
{
  "accounts": [ ... 老格式，不变 ... ],
  "rate_limit": { ... 老格式 ... },
  "pool_config": {
    "max_concurrency": null,
    "max_concurrency_comment": "null 表示按 §0 公式 default_concurrency(N) 动态算；填数字则强制覆盖",
    "warmup_hours": 72,
    "floodwait_retire_threshold": 3,
    "floodwait_window_hours": 24,
    "cooling_min_minutes": 20,
    "cooling_max_minutes": 60,
    "per_account_daily_quota": 50
  }
}
```

### 2.2 account_state.json（新增，持久化）

与 config 分离，避免每次保存 config 时把运行时状态也写掉。

```json
{
  "account1": {
    "first_login_ts": 1714000000,
    "state": "active",
    "health_score": 87,
    "total_requests": 1823,
    "total_success": 1402,
    "floodwait_events": [1713999000, 1713998000],
    "last_used_ts": 1714012345,
    "last_check_ts": 1714000000,
    "retired_reason": null,
    "bound_proxy_fingerprint": "sha1(host:port:user)"
  }
}
```

- **`bound_proxy_fingerprint`**：代理绑定指纹。如果用户手动改了代理，启动时对比不一致 → 弹窗警告"代理变更 = 换设备"。
- **`last_check_ts`**：AccountCheckThread 用来决定是否跳过（< 24h 直接 OK）。
- **`floodwait_events`**：时间戳列表，超出 `floodwait_window_hours` 的自动清理。

---

## 3. 关键类设计

### 3.1 `account_pool.py`（新文件，~250 行）

```python
class AccountPool:
    """号池的唯一真相来源。所有号的状态读写都走这里。"""

    def __init__(self, config_path, state_path):
        self.accounts_cfg = load_config(config_path)['accounts']
        self.state = load_state(state_path)  # 缺失字段自动补默认值
        self._migrate_legacy()  # 老用户第一次用：所有号初始 state=active

    # --- 查询接口 ---
    def get_active_batch(self, k, exclude_subnets=True): ...
    def get_by_state(self, state) -> list: ...
    def get_health_snapshot(self) -> dict: ...  # 供 GUI 展示

    # --- 状态更新（线程安全）---
    def record_request(self, name, success: bool): ...
    def record_floodwait(self, name, seconds): ...
    def record_empty_return(self, name): ...
    def mark_cooling(self, name, duration_sec, reason): ...
    def mark_retired(self, name, reason): ...
    def mark_warmup_done(self, name): ...

    # --- 定时任务 ---
    def tick(self):
        """每 30s 调一次：检查 cooling 到期、warmup 到期、health 重算。"""

    # --- 持久化 ---
    def save(self): ...  # 写 state.json（原子写）
```

### 3.2 FilterThread 改造

现在是：`AccountManager(config).connect_all() → active_primary → workers`。

改成：

```python
pool = AccountPool(config_path, state_path)
k = pool.compute_concurrency()  # 内部按 §0 公式 + max_concurrency 覆盖逻辑
active = pool.get_active_batch(k)  # 只拿 K 个，不是全部
# ... 原 worker 逻辑不变，结束后统一 pool.record_* 落盘
```

### 3.3 GUI 号池页

在"账号管理" tab 旁新增 "🏊 号池" tab：

```
┌────────────────────────────────────────────────────────┐
│ 活跃 12 / 预热 4 / 冷却 2 / 退役 3   平均健康分 78     │
├────────────────────────────────────────────────────────┤
│ 名称      状态    分数  代理        首登    24h FW    │
│ acc001    🟢active 92   1.2.3.4     7d     0         │
│ acc002    🟡warmup 60   1.2.3.5     2h     0         │
│ acc003    🔴retire 5    1.2.3.6     30d    8  手动激活│
└────────────────────────────────────────────────────────┘
```

---

## 4. 迁移策略

老用户第一次升级到号池版本：

1. 检测 `account_state.json` 不存在 → 自动创建
2. config.accounts 里每个号自动进 `state=active`，`health_score=80`（给个初始中位数）
3. `first_login_ts` 设为 `os.path.getmtime(session_{name}.session)`（用 session 文件 mtime 近似）
4. `pool_config` 不存在 → 写入默认值

**零感迁移**：老用户打开软件完全不需要改 config 就能用，只是从此多了一套状态文件。

---

## 5. 反封控集成（Anti-Ban Layer）

号池不是"换汤不换药的调度器"，而是**反封控策略的载体**。以下 8 项全部随号池架构一起落地。

### 5.1 预热心跳（Warmup Heartbeat）

`warmup` 态账号由独立 `WarmupThread` 低频驱动，**不**参与筛号但模拟真人：

```python
# 每号 warmup 期（默认 72h）内，每 30-120 分钟随机跑一次：
actions = [
    ('GetDialogsRequest', 0.40),          # 看对话列表，最常见
    ('UpdateStatus(online=True)', 0.20),  # 上线状态
    ('GetFullUserRequest(self)', 0.15),   # 看自己资料
    ('GetContactsRequest', 0.15),         # 看联系人
    ('GetNotifySettingsRequest', 0.10),   # 看通知设置
]
# 按权重随机选一个，隔机随机睡 30-120 分钟
```

> **收益**：首登 → 暴力筛是最容易死的。模拟一天 10-30 次真人操作，72h 后才放出池子，风控打分完全不一样。

### 5.2 突发-静默节奏（Burst-Silent Pacing）—— **保守版**

`RateLimiter` 状态机。节奏对标"真人卖家号"而非"真人日常用户"，但仍然克制：

```
BURST 段：连 2-4 次，间隔 8-18s       (模拟真人一段集中操作)
  ↓ 完成
QUIET 段：一次，间隔 180-600s (3-10min) (模拟放下手机)
  ↓ 完成
BURST ...
```

**节奏实算**（取中位数）：

```
BURST: 3 次 × 13s = 39s
QUIET: 390s
周期 = 429s / 3 次请求
→ 每号每小时 ~25 次
```

配合 §5.11 日配额硬截断，单号一天实际只"上班"3-4 小时。

每个 worker 独立维护 burst 计数，参数从 `pool_config.pacing` 读取：

```json
"pacing": {
  "burst_min": 2, "burst_max": 4,
  "burst_interval_min": 8, "burst_interval_max": 18,
  "quiet_interval_min": 180, "quiet_interval_max": 600
}
```

> **收益**：均匀 25-45s 延迟仍然是机器节奏。真人 = 爆发 + 长静默。之前设计的 BURST 3-6 次 + QUIET 90-240s 是**激进版，单小时 90 次/号明显超标**，已下调到保守值。

### 5.3 API 多样化（API Diversity）

当前 99% 是 `ImportContactsRequest`。号池层强制每 10-15 次筛号穿插一次"伪装调用"：

```python
DECOY_CALLS = [
    lambda c: c(GetFullUserRequest('@telegram')),     # 公开频道作者
    lambda c: c(GetHistoryRequest(CHANNEL, limit=1)), # 公开频道历史
    lambda c: c(GetDialogsRequest(limit=5)),
    lambda c: c(UpdateStatusRequest(offline=False)),
]
```

伪装调用的结果丢弃，只为改变 API 分布。

> **收益**：TG 按单账号 API 比例打标，单一 API >95% = 机器人。

### 5.4 时区降频（Time-Zone Throttling）

按账号手机号首位检测国家时区，本地 **02:00-07:00** 期间：

- `delay_multiplier = 3.0`（min_delay/max_delay 都 × 3）
- `per_account_hourly_quota` 降到平时 1/4

美国号（+1）+ 美国代理，UTC 07:00-12:00 对应美东深夜。

> **收益**：24 小时同一节奏 = 机器人；真人晚上睡觉。

### 5.5 FloodWait 累计熔断

已列 M2。具体规则：

- `floodwait_window_hours = 24`
- 24h 内 FW 次数 ≥ `floodwait_retire_threshold`（默认 3）→ 直接 `retired`
- 单次 FW seconds > 300 → 立即 `retired`（这种 FW 通常伴随永久标记）
- `retired` 需用户在 GUI 手动激活才会复用

### 5.6 代理 Provider 绑定（Proxy Provider Binding）

> **动态代理场景下，IP 必然每天变，不能按 IP 绑定。绑定的是"代理身份"——同一 provider、同一 region、同一 sub-user 视为同一背景。**

**代理 provider 指纹**（存 `account_state.json`）：

```python
provider_fingerprint = sha1(
    host_domain          # 如 us-eu.fluxisp.com （忽略 IP 数字、忽略端口）
    + region_tag         # 从 user 字段解析，如 region-US / region-EU
    + sub_user_prefix    # 如 gdggxfzrk51113（忽略 session-xxx 后缀）
).hexdigest()[:16]
```

启动或代理更新时对比：

| 情况 | 动作 |
|------|------|
| Provider 一致（只是 IP / session ID 变了） | 静默替换，无警告 |
| Region 变化（US → EU） | 🔴 红色警告"美国号接到欧洲 IP，TG 会瞬间标异常" |
| Host domain / 账户前缀完全换了 | 🟡 黄色警告"更换了代理服务商，风控会重新观察一段时间" |
| 多账号共享完全相同 provider+session | 红色警告（动态代理若不带 session 后缀就是这种） |

**解析约定**（批量代理粘贴时自动抽取）：

```
us-eu.fluxisp.com:5000:gdggxfzrk51113-region-US-sid-FNVUBKrn-t-5:uhh5m5eu
         ↓
host_domain       = us-eu.fluxisp.com
region_tag        = US
sub_user_prefix   = gdggxfzrk51113
session_id        = FNVUBKrn         (动态部分，不参与指纹)
```

支持的 user 字段语法（常见动态代理商通用）：
- `-region-XX` / `-country-XX` / `-zone-XX`
- `-session-XXX` / `-sid-XXX` / `-sess-XXX`
- `-sticky-XX` 粘性时长（分钟）

### 5.7 Sticky Session 强制（关键 §）

> **动态代理最大的坑：如果不配 session 后缀，每次请求都是新 IP，TG 会把你当作一秒换一次设备。必须强制 sticky。**

号池层对每号自动注入 sticky session 标识：

```python
def build_sticky_proxy_user(account_name, base_user):
    # 约定：config 里的 user 字段末尾若没有 -session-XXX，自动追加
    if '-session-' in base_user or '-sid-' in base_user:
        return base_user
    # 用 account name 的 crc32 作为稳定 session id，同一号每次拿同 IP
    sid = f"{zlib.crc32(account_name.encode()):08x}"
    return f"{base_user}-session-{sid}"
```

**用户配置简化**：用户在"代理更新"粘贴框里只需要填**基础凭据**：

```
# 粘贴 1 行（provider 根用户）→ 自动为池中所有 N 个号生成 N 个 sticky sub-session
host=us-eu.fluxisp.com port=5000 user=gdggxfzrk51113-region-US pass=uhh5m5eu
```

每个号拿到的实际代理 user 是 `gdggxfzrk51113-region-US-session-<crc32(name)>`。

> **收益**：配代理从"粘贴 N 行逐一校对"变成"粘贴 1 行根凭据"。N = 5 还是 200，都是一行搞定。同一号每天/每次启动永远拿同一 sub-session → TG 看到的 IP 漂移最小化。

### 5.8 代理每日热更新（Daily Rotation）

用户每天从代理商拿新凭据（pass 改了 / sub-user 改了 / 整个 provider 换了）。工作流：

```
[📡 代理更新] 按钮
    ↓
粘贴新的代理凭据（支持单行根凭据 或 50 行逐号明细）
    ↓
解析 + 提取 provider_fingerprint
    ↓
与现有绑定对比：
    ├─ provider 一致 → 静默替换 pass / sub-user
    ├─ region 变了 → 红字弹窗确认
    └─ 整个 provider 换了 → 黄字弹窗 + 建议先跑一小时预热
    ↓
原子写入 proxies.json + 触发所有号一次 SOCKS CONNECT 健康检测
    ↓
失败的号进 cooling 10 分钟，成功的号立即可用
    ↓
写一条更新记录到 proxy_history.log（审计用）
```

**文件落盘**：代理独立存 `proxies.json`，**不**塞进 config.json，避免代理凭据泄露到备份/截图里。同时 `.gitignore` 默认加一条。

**自动保活**：独立 QTimer 每 30 分钟对所有 active 号跑 SOCKS CONNECT ping（不登录 TG，只 TCP 握手），失败 ≥ 2 次进 cooling。代理商的 IP 池掉线很常见，提前发现比等筛号报错强。

### 5.9 子网多样性（Subnet Diversity）

`get_active_batch(k)` 选号时：

- 不让同一 /24 子网的 2 个号同时出现在同一批
- 不让同一 `api_id` 的超过 2 个号同时出现（号包常常共享 api_id）
- **动态代理下**：按 `provider_fingerprint + session_id` 区分，同一 session id 不会在 k 个号里重复（sticky session 保证了每号不同 session id，本规则兜底）

> **收益**：批量筛号时并发请求不会集中打同一个 /24，降低"IP 聚簇"风控。

### 5.10 联系人簿周期清理

现有 `reset_contacts_interval = 50` 已启用，号池下扩展为：

- **按号独立计数**（当前已是）
- 每号每天硬性 `ResetSavedRequest` 至少 1 次（即便没到 50 次）
- `retired` 号在归档前自动 reset 一次，把联系人簿清干净

> **收益**：联系人簿膨胀是卖家号最常见的次生风险。

### 5.11 按号龄的日配额硬截断（Daily Quota by Age）

> **最关键的一条防封线**。前面所有延迟/节奏只控制"短时速率"，日配额控制"累计体量"。两者缺一不可。

```python
def daily_quota(age_days):
    if age_days < 3:   return 25    # 新号极度克制
    if age_days < 7:   return 50
    if age_days < 14:  return 80
    if age_days < 30:  return 120
    return 150                       # 30 天以上"成熟号"
```

**硬约束**：

- 每号维护 `today_requests` 计数器，存 `account_state.json`
- 达到 `daily_quota(age)` → 该号**立即进入 `cooling`** 到本地时区**次日 00:00**
- 跨日自动归零，不需手工重置
- `get_active_batch(k)` 永不返回已达配额的号

**日产量估算**（任意池子大小 N，假设号龄分布均衡）：

按 §0 公式：日产量 ≈ N × 单号日均配额 × 活跃率 ≈ **N × 76**。

示例（号龄均衡分布，每层占比：warmup 10% / 3-7d 20% / 7-14d 30% / 14-30d 30% / 30d+ 10%）：

| N | 日配额加权和 | 预计日产量 |
|---|------------|-----------|
| 20  | 20 × 76  | ~1500 |
| 50  | 50 × 76  | ~3800 |
| 100 | 100 × 76 | ~7600 |
| 200 | 200 × 76 | ~15000 |

> 实际产量取决于号龄分布：新号多 → 配额低 → 产量偏下；成熟号多 → 产量偏上。GUI 号池页显示"按当前号龄分布预测今日产量"帮你决策要不要加号。

**状态机交互**：

```
normal → 达配额 → cooling_quota_done (到次日 00:00)
         ↓
         次日 00:00 → normal（配额重置，健康分也小幅 +5，奖励自律）
```

> **收益**：杜绝"跑 24h 单号超 2000 次"这类结构性红线。即便延迟和 burst 配置被误调激进，日配额依然兜底。

### 5.12 PEER_FLOOD 专项识别与熔断（借鉴社区共识）

TG 针对"滥用 ImportContacts 联系陌生人"的专门封控代码，**比 FLOOD_WAIT 严重得多**：

| 错误码 | 含义 | 影响 | 我们的处理 |
|--------|------|------|-----------|
| `FLOOD_WAIT_X` | 临时限速 X 秒 | 秒级-分钟级 | 已处理（退避） |
| `SLOW_MODE_WAIT` | 频道慢速模式 | 几秒 | 基本不触发 |
| `PEER_FLOOD` | ⚠️ 账号被限联系陌生人 | **几天到永久** | **当前无识别，当 generic Exception** |
| `SPAM_WAIT` | 严重垃圾号警告 | 几小时-几天 | 同上 |
| `USER_DEACTIVATED(_BAN)` | 封号 | 永久 | 已处理 |

**现状危险点**：`filter.py._check_with_manager` 的 `except Exception` 分支对 `PEER_FLOOD` 等于只打个日志继续轮询该号 → 该号每次筛号都报错 → 24h 内 FW 计数却没涨（因为不是 FloodWaitError）→ 熔断不触发 → **永远在池子里死转**。

**新规则**：

```python
PERMANENT_LIMIT_CODES = ('PEER_FLOOD', 'SPAM_WAIT', 'USER_PRIVACY_RESTRICTED')

except Exception as e:
    msg = str(e).upper()
    if any(code in msg for code in PERMANENT_LIMIT_CODES):
        pool.mark_retired(account, reason=f'permanent_limit:{code}')
        return  # 该号立刻下架，不再被 get_active_batch 选中
```

`PEER_FLOOD` 触发 = **立即 retired，不走 3 次累计**。这种错误一旦出现号基本废了，继续跑只会把代理 IP 也带坏。

> **收益**：堵掉 2026 最常见的"号还活着但 ImportContacts 全错"的阴性死亡路径。

### 5.13 tdata 导入支持（你的场景必做）

> **你拿到的协议号带 tdata 文件夹**。这是官方 Telegram Desktop 的登录态目录，可信度比 session 文件高 30-50%（社区共识）。

**tdata 优势**：

- 携带完整的 device_id / install_id / lang_pack / mtproxy 历史等 30+ 字段，TG 看起来就是"真官方客户端"
- session 文件只有 auth_key + dc_id + server_addr，"轻量登录态"，TG 看起来像"第三方库连的"
- 号商卖 tdata 号通常贵 2-3 倍，封控率显著低

**实现**：引入 `opentele` 库（MIT 协议）做转换：

```python
# batch_import.py 扩展
from opentele.td import TDesktop
from opentele.api import UseCurrentSession

def convert_tdata_to_telethon(tdata_dir, out_session_path):
    """把 tdata/ 文件夹转成 Telethon .session 文件，保留所有指纹字段。"""
    tdesk = TDesktop(tdata_dir)
    client = await tdesk.ToTelethon(
        session=out_session_path,
        flag=UseCurrentSession,  # 关键：不触发新设备事件
    )
    return client
```

**scan_account_folder 扩展**：

```python
# 除了 .session + .json 外，再识别 tdata/ 子目录
def _find_tdata(dir_path):
    tdata_subdir = os.path.join(dir_path, 'tdata')
    if os.path.isdir(tdata_subdir):
        # tdata 目录必有 key_datas 或 D877F783D5D3EF8C_1 之类文件
        return tdata_subdir
    return None
```

**BatchImportDialog UI**：扫描结果表格新增 "类型" 列：

```
名称        类型     json    会话源
acc001     tdata    ✓       tdata/
acc002     session  ✓       acc002.session
acc003     tdata    ✓       tdata/
```

**优先级规则**：同一个号既有 tdata 又有 session，**默认选 tdata**（可信度高）。UI 提示"检测到 X 个 tdata 号，将优先使用 tdata 登录态"。

**健康分加成**：tdata 导入的号初始 health_score **+10**（起始 90 而不是 80），`get_active_batch` 自然优先用。

> **收益**：直接吃到号商卖你的"高质量"那部分，不白浪费 tdata 的可信度。

### 5.14 DC 预绑定（你全是美国号 → 简化版）

> **你确认池子全是 +1 美国号。**不需要多 DC 查表，**所有号启动时强制锁 DC1**。

Telethon 默认连 DC2（荷兰），然后 redirect 到正确 DC。对美国号这是多 1 次握手 + 代理 IP 暴露给 DC2 一次。

**实现（简化版，2 行）**：

```python
# account_manager.connect_all 里，创建 TelegramClient 之前：
DC1_MIA = (1, '149.154.175.50', 443)
client.session.set_dc(*DC1_MIA)  # 所有号一律直连 DC1
await client.connect()
```

配合 §5.6 的 region 检查：代理 `user` 字段里只允许 `-region-US`，任何非 US region 启动时红字拦截。**美国号 + 美国代理 + DC1 = TG 看到的是"一个始终在美国使用的账号"，风控信号最干净。**

**将来扩展**：如果池子加入其他国家号，把 DC 查表复活即可（保留代码注释版）。

### 5.15 US 专属时区锁（简化 §5.4）

§5.4 原方案是"按号手机号首位推时区"。**你全是美国号**，直接锁美东时区：

```python
US_EASTERN = pytz.timezone('America/New_York')
def is_quiet_hour():
    """美东 02:00-07:00 降频 3×。"""
    hour = datetime.now(US_EASTERN).hour
    return 2 <= hour < 7
```

**收益**：代码从"查国家时区 + 夏令时处理"简化到 3 行常量。

如果后续混入其他国家号，再还原 §5.4 的完整版。

---

## 6. 实施里程碑（含反封控 + 动态代理 + 社区共识补齐）

| Milestone | 内容 | 工作量 | 验收 |
|-----------|------|--------|------|
| **M1** | `account_pool.py` 基础类 + 持久化 + 迁移 + 单元测试 | 1 天 | 老 config 自动生成合法 state.json |
| **M2** | FloodWait 熔断（§5.5）+ **PEER_FLOOD 识别（§5.12）** + 24h check 缓存 + 代理 provider 绑定（§5.6） | 2 天 | FW 3 次自动 retired；PEER_FLOOD 立即 retired；provider 变更弹窗分级 |
| **M2b** | Sticky Session 强制（§5.7）+ 代理热更新 UI 与文件（§5.8） | 2 天 | 粘贴 1 行根凭据自动生成 N 号 sticky；`proxies.json` 原子写 |
| **M2c** | **tdata 导入（§5.13）** + opentele 依赖 + 识别 tdata/ 子目录 + 健康分 +10 | 1.5 天 | 扫描能识别 tdata；导入后 TG 看到"官方客户端"指纹；tdata 号起始分 90 |
| **M3** | FilterThread 接 `get_active_batch(k)` + 子网多样性（§5.9）+ warmup 跳过 + **DC1 锁（§5.14）** | 2 天 | 任意 N 号池跑通，K 自动算；日志打印 "DC1 direct" |
| **M3b** | 代理每日健康保活（§5.8 ping）+ 失败号自动 cooling | 1 天 | 代理商掉线 2 分钟内发现，对应号进冷却 |
| **M4** | `WarmupThread` 心跳（§5.1）+ 72h 自动升 active | 1.5 天 | 新导入号静置观察，GUI 能看到升级 |
| **M5** | `RateLimiter` 重写为保守版突发-静默（§5.2）+ 日配额硬截断（§5.11）+ **美东时区降频（§5.15）** | 2 天 | 24h 模拟跑，单号请求数必须 ≤ `daily_quota(age)`；02-07 AM EST 自动降频 3× |
| **M6** | API 多样化（§5.3）+ 联系人簿强制日清（§5.10） | 1 天 | 单账号 API 分布 ImportContacts 占比 < 85% |
| **M7** | GUI 号池页 + 健康分 + 手动激活/退役 + 代理池可视化 + **tdata 标记** | 2.5 天 | 可视化完整，能看到每号来源（tdata/session）、session id、出口 IP |

**总计：16.5 工作日**。建议节奏：

- M1+M2+M2b+M2c+M3+M3b 一起发 **v3.3.0**（号池底层 + 动态代理 + tdata + DC1 锁 + PEER_FLOOD）
- M4+M5+M6 一起发 **v3.4.0**（反封控行为层 + 日配额 + 美东降频）
- M7 发 **v3.5.0**（可视化）

每个版本都兼容老 config，可独立回滚。

---

## 7. 回退方案

每个 Milestone 都兼容老 config，不删除任何既有字段。任何时候回滚 v3.2.x 都能读回现有 session 和 config.json 继续工作。

`account_state.json` 是纯附加，回滚时被老版忽略；再次升级自动重建。

---

## 8. 开放问题（等你决定）

1. **池大小上限**：设计层面不设上限（N 可任意大）。存储层：
   - N ≤ 300：JSON 足够（单文件 < 500KB）
   - N > 300：建议切换 SQLite（状态读写更频繁、历史数据累积快）
   - 软件启动时检测 N 自动选后端，用户无感切换。
2. **代理池是否同步管理**：号池+代理池双池 vs 只管号池手工绑代理。前者工作量 +3 天（已纳入 M2b+M3b）。
3. **定时任务载体**：`pool.tick()` 用独立 QThread 还是复用现有 QTimer（1s 粒度够）。建议 QTimer。
4. **健康分公式**：上面是起手值，实际跑一周后根据数据再调权重。
5. **失败号的 session 文件**：retired 后是否自动移到 `session_archive/` 子目录？避免跟活号混。
