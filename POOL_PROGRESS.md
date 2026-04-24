# 号池改造进度档案

> M1–M6 已全部落地。下次启动读这份 + `POOL_DESIGN.md` 即可对齐。

---

## 现状（本次会话完成）

### 代码

- 分支：`main`（有大量未提交改动，统一待发 **v3.3.0 + v3.4.0**）
- 未提交新文件：
  - `account_pool.py` —— 号池核心（四态机 + 健康分 + 日配额 + 代理指纹 + API 计数）
  - `pacing.py` —— BurstSilentPacer（§5.2 + §5.15 降频）
  - `proxy_registry.py` —— proxies.json + sticky session 生成 + SOCKS ping 保活
  - `warmup_thread.py` —— §5.1 预热心跳（按 warmup 号随机 API 调用）
  - `test_account_pool.py` —— 25 条单测全绿
- 未提交修改：
  - `filter.py` —— 接 pool + pacer；PEER_FLOOD 立即退役；§5.3 decoy call；§5.10 日清联系人
  - `account_manager.py` —— §5.14 DC1 锁（`pool_config.dc1_lock=true` 时生效）
  - `batch_import.py` —— §5.13 tdata 识别 + `convert_tdata_to_telethon`；scan 返回 4 元组含 `source_type`
  - `gui_monitor.py` —— FilterThread 启动时构建 pool/pacer、打印"🏊 从池中挑 K"；批量导入兼容 4 元组、tdata 优先转换
  - `config.json` —— 加 `pool_config` 完整默认值
  - `requirements.txt` —— `pytz + opentele`
  - `build_config.spec` —— 新文件进 hiddenimports
  - `.gitignore` —— 忽略 `account_state.json` / `proxies.json`

### 文档

- `POOL_DESIGN.md` / `POOL_PROGRESS.md`（本文件）保持最新

---

## Milestone 状态

| M | 名称 | 状态 |
|---|------|------|
| M1 | 号池基础类 + 持久化 + 迁移 | ✅ 含 25 条单测 |
| M2 | FloodWait 熔断 + PEER_FLOOD + 代理 provider 指纹 | ✅ |
| M2b | Sticky Session + proxy_registry + SOCKS ping | ✅ 后端；UI 未接（暂不做） |
| M2c | tdata 识别 + opentele 转换 | ✅ |
| M3 | FilterThread 接 pool.get_active_batch + DC1 锁 + 子网去重 | ✅ |
| M3b | 代理保活 ping | ✅ 函数就绪（QTimer 触发暂未接 GUI） |
| M4 | WarmupThread 心跳（§5.1） | ✅ 模块就绪（QTimer 触发暂未接 GUI） |
| M5 | 突发-静默 pacing + 日配额 + 美东降频 | ✅ |
| M6 | API 多样化 + 联系簿强制日清 | ✅ |
| M7 | GUI 可视化 | ⏸️ 按用户意愿延后 |

> **未接 GUI 的 4 个 QTimer 入口**（M3b keepalive_pass / M4 warmup_once / pool.tick / 代理更新 UI）
> 可以在下次开工按需接，核心防封功能已全部生效。

---

## 验收关键日志

筛选跑起来应该同时出现以下 5 条之一：

```
🏊 号池 active=X warmup=Y cooling=Z retired=W 推荐并发 K=K
🏊 从池中挑 K 个（原 N，过滤掉 cooling/retired/warmup/达配额）
🗽 accXXX DC1 direct (MIA)
```

触发真实 TG 时：
- 单号连续 30 次空返 → 自动 cooling
- 24h 内 3 次 FloodWait → 自动 retired
- 单次 FloodWait ≥ 300s → 立即 retired
- 遇 PEER_FLOOD / SPAM_WAIT / AUTH_KEY_UNREGISTERED → 立即 retired

---

## 兼容性

- `config.json` 只加 `pool_config` 顶层字段，老字段不改
- `account_state.json` 纯附加，回滚 v3.2.x 直接忽略
- `proxies.json` 独立存，不塞进 config；默认 `.gitignore`
- 老用户不设 `pool_config` 也能跑（用 `DEFAULT_POOL_CONFIG`）

---

## 下次开工的候选任务

1. **发版 v3.3.0**：提交未提交改动 + 打 tag（包含 M1~M3b + v3.2.x 修复）
2. **发版 v3.4.0**：实测 1-2 轮后再打（M4~M6 都要跑满一天观察）
3. **M3b/M4 QTimer 接入 GUI**（30min 一次 keepalive_pass，60min 一次 warmup_once）
4. **M7 号池可视化 tab**：显示 `pool.get_health_snapshot()` + 手动激活/退役按钮
5. **代理热更新 UI**：`ProxyUpdateDialog`（粘贴根凭据 → 生成 N sticky → 触发保活）

---

## 常用文件速查

```
account_pool.py           号池核心
pacing.py                 BurstSilentPacer（M5）
proxy_registry.py         proxies.json + sticky + SOCKS ping
warmup_thread.py          warmup_once（M4）
filter.py                 _check_with_manager 已接 pool/pacer，PEER_FLOOD ready
account_manager.py        connect_all DC1 锁可配
batch_import.py           scan 返回 4 元组，tdata 优先
gui_monitor.py            FilterThread 启动时挂 pool/pacer
test_account_pool.py      25 条单测 ✅
config.json               已含 pool_config
account_state.json        【运行时自动生成】号池状态持久化
proxies.json              【M2b 新增】代理凭据独立存
```
