# Telegram筛号工具 - 项目总结

## 📊 项目概览

**项目名称**: Telegram筛号工具（多账号防封版）  
**版本**: v2.0  
**开发日期**: 2026-04-07  
**代码行数**: ~950行Python代码  
**核心功能**: 验证美国/中国手机号是否注册Telegram，获取用户活跃度

## 🎯 核心特性

### 1. 多账号轮换系统
- 支持3-10个Telegram账号同时管理
- 智能账号切换，避免单账号过载
- 每个账号独立统计和监控
- 自动处理账号封禁和恢复

### 2. 智能防封策略
- **随机延迟**: 每次请求间隔3-8秒（可配置）
- **请求限制**: 单账号连续请求不超过30次
- **FloodWait处理**: 触发速率限制自动切换账号
- **错误重试**: 失败自动重试最多3次
- **冷却机制**: 错误后增加延迟时间
- **自动暂停**: 请求过于频繁时自动休息

### 3. 美国号码支持
- 自动识别和格式化多种美国号码格式
- 支持格式：+1xxx, xxx, (xxx) xxx-xxxx等
- 自动添加国家码+1
- 批量格式化和验证

### 4. 用户活跃度检测
- 🟢 online - 当前在线
- 🟡 recently - 最近在线（几分钟到几小时）
- 🟠 within_week - 一周内在线
- 🔴 within_month - 一个月内在线
- ⚫ offline - 离线（显示具体时间）
- ⚪ long_ago - 很久未上线

## 📁 文件说明

| 文件 | 大小 | 说明 |
|------|------|------|
| main_multi.py | 3.0K | 多账号主程序（推荐使用） |
| account_manager.py | 5.8K | 账号管理和轮换逻辑 |
| rate_limiter.py | 5.0K | 智能速率控制和调度 |
| filter.py | 5.9K | 核心筛选功能 |
| phone_utils.py | 2.7K | 号码格式化工具 |
| exporter.py | 1.6K | 结果导出（CSV/JSON） |
| auth.py | 1.4K | 单账号认证模块 |
| main.py | 2.1K | 单账号主程序 |

## 🚀 使用流程

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置多个账号
cp config.example.json config.json
# 编辑config.json，添加3-5个账号信息

# 3. 准备号码文件
echo "+12025551234" > us_phones.txt

# 4. 运行筛选
python main_multi.py --file us_phones.txt --country US --output result.csv

# 或使用快捷脚本
./run.sh us_phones.txt
```

## ⚙️ 配置参数

```json
{
  "rate_limit": {
    "requests_per_account": 30,    // 单账号连续请求上限
    "min_delay": 3,                // 最小延迟（秒）
    "max_delay": 8,                // 最大延迟（秒）
    "account_switch_delay": 60,    // 切换账号延迟
    "error_cooldown": 300          // 错误冷却时间
  }
}
```

## 📈 性能指标

- **单账号**: 10-15个号码/分钟
- **3账号轮换**: 25-35个号码/分钟
- **5账号轮换**: 40-50个号码/分钟

## 🛡️ 安全建议

1. ✅ 使用真实手机号注册的老账号
2. ✅ 至少准备3个账号，推荐5个以上
3. ✅ 不要设置过快的请求速率
4. ✅ 避免24小时连续运行
5. ✅ 分批次执行，每批次后休息
6. ✅ 遵守Telegram服务条款

## 📤 输出结果

CSV文件包含字段：
- phone（格式化号码）
- original_phone（原始输入）
- country（国家代码）
- registered（是否注册）
- user_id（用户ID）
- username（用户名）
- first_name / last_name（姓名）
- status（在线状态）
- last_seen（最后上线时间）
- is_bot（是否机器人）
- error（错误信息）

## 🔧 技术栈

- **Python 3.7+**
- **Telethon** - Telegram客户端库
- **asyncio** - 异步IO
- **pandas** - 数据处理（可选）

## 📝 使用场景

- ✅ 市场调研 - 验证目标用户是否使用Telegram
- ✅ 用户验证 - 检查号码有效性
- ✅ 活跃度分析 - 了解用户活跃情况
- ✅ 数据清洗 - 过滤无效号码

## ⚠️ 法律声明

本工具仅供学习和合法用途使用。使用者需：
- 遵守当地法律法规
- 遵守Telegram服务条款
- 尊重用户隐私
- 不得用于非法目的
- 自行承担使用风险

## 📚 文档

- `README.md` - 基础使用说明
- `GUIDE.md` - 详细使用指南
- `CHANGELOG.md` - 版本更新日志
- `example_multi.py` - 代码示例

## 🎉 项目完成

所有核心功能已实现，可以直接使用！
