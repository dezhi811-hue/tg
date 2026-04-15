# Windows 崩溃问题修复说明

## 问题描述
在 Windows 上点击"开始筛选"按钮后，程序立即崩溃闪退。

## 根本原因
Windows 平台上 `asyncio.run()` 在多线程环境（PyQt5 QThread）中存在兼容性问题，会导致程序崩溃。

## 修复内容

### 1. 设置 Windows 事件循环策略
在程序启动时检测操作系统，如果是 Windows 则设置兼容的事件循环策略：

```python
import platform
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

### 2. 修改所有线程中的 asyncio.run() 调用
将所有 QThread 中的 `asyncio.run()` 替换为线程安全的方式：

**修改前：**
```python
def run(self):
    asyncio.run(self.some_task())
```

**修改后：**
```python
def run(self):
    # 创建新的事件循环（线程安全）
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(self.some_task())
    finally:
        loop.close()
```

### 3. 涉及的线程类
- `LoginThread` - 账号登录线程
- `AccountCheckThread` - 账号检测线程
- `FilterThread` - 筛选任务线程（主要崩溃点）

### 4. 添加详细日志
在关键位置添加本地日志记录，便于追踪问题：
- 线程启动/完成
- 账号管理器初始化
- 连接建立
- 筛选进度（每 10 个号码记录一次）

## 日志文件位置
程序运行时会在当前目录生成 `telegram_filter.log` 文件，记录所有操作和错误信息。

## 测试建议
1. 在 Windows 上运行程序
2. 添加账号并登录
3. 输入测试号码
4. 点击"开始筛选"
5. 观察是否还会崩溃
6. 如果崩溃，查看 `telegram_filter.log` 文件中的错误信息

## 其他改进
- 修复了远程日志的异常处理（移除 `except Exception: pass`）
- 所有远程日志发送失败时会记录到本地日志
- 添加了用户操作日志（开始/停止筛选）

## 兼容性
此修复对 macOS 和 Linux 平台无影响，保持向后兼容。
