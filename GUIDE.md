## 项目结构

```
telegram_filter/
├── main_multi.py           # 主程序（多账号版，推荐）
├── main.py                 # 主程序（单账号版）
├── account_manager.py      # 多账号管理模块
├── rate_limiter.py         # 智能速率控制模块
├── filter.py               # 筛选核心功能
├── phone_utils.py          # 号码格式化工具
├── auth.py                 # 认证模块（单账号）
├── exporter.py             # 结果导出
├── example_multi.py        # 多账号使用示例
├── example.py              # 单账号使用示例
├── config.example.json     # 配置模板
├── us_phones.example.txt   # 美国号码示例
├── phones.example.txt      # 号码示例
├── requirements.txt        # 依赖包
└── README.md              # 使用说明

## 快速开始指南

### 第一步：安装依赖
```bash
cd /Volumes/waijie/tg/telegram_filter
pip install -r requirements.txt
```

### 第二步：准备多个Telegram账号
- 至少准备3-5个Telegram账号
- 每个账号访问 https://my.telegram.org/apps 获取API凭证

### 第三步：配置
```bash
cp config.example.json config.json
# 编辑config.json，填入所有账号信息
```

### 第四步：准备号码文件
创建 `us_phones.txt`，每行一个号码：
```
+12025551234
2025551235
(202) 555-1236
```

### 第五步：运行
```bash
python main_multi.py --file us_phones.txt --country US --output result.csv
```

首次运行会要求输入每个账号的验证码。

## 防封建议

1. **账号数量**：至少3个，推荐5个以上
2. **请求速率**：每个账号每次请求间隔3-8秒
3. **单账号限制**：连续请求不超过30次就切换
4. **运行时间**：避免24小时连续运行，分批次执行
5. **错误处理**：遇到FloodWait立即切换账号
6. **账号质量**：使用真实手机号注册的老账号更安全

## 性能估算

- 单账号：约10-15个号码/分钟
- 3个账号轮换：约25-35个号码/分钟
- 5个账号轮换：约40-50个号码/分钟

## 技术架构

```
用户输入
    ↓
号码格式化 (phone_utils.py)
    ↓
智能调度器 (rate_limiter.py)
    ↓
账号管理器 (account_manager.py) → 账号1、账号2、账号3...
    ↓
Telegram API
    ↓
结果收集 & 导出 (exporter.py)
```
