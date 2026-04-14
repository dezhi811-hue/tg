#!/usr/bin/env python3
"""
Telegram筛号工具 - GUI界面（直接版本）
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import json
import os

# 创建主窗口
root = tk.Tk()
root.title("Telegram 筛号工具 - 多账号版")
root.geometry("1000x700")

# 配置文件路径
config_path = "config.json"

def load_config():
    """加载配置"""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "accounts": [],
        "rate_limit": {
            "requests_per_account": 30,
            "min_delay": 3,
            "max_delay": 8
        }
    }

def save_config():
    """保存配置"""
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    log_message("✅ 配置已保存")

def log_message(msg):
    """添加日志"""
    from datetime import datetime
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_text.insert('end', f"[{timestamp}] {msg}\n")
    log_text.see('end')

config = load_config()

# 创建主框架
main_frame = tk.Frame(root, bg='white')
main_frame.pack(fill='both', expand=True, padx=10, pady=10)

# 标题
title_label = tk.Label(main_frame, text="🚀 Telegram 筛号工具",
                       font=('Arial', 18, 'bold'), bg='white')
title_label.pack(pady=10)

# 创建Notebook（标签页）
notebook = ttk.Notebook(main_frame)
notebook.pack(fill='both', expand=True, pady=10)

# ==================== 标签页1: 筛选 ====================
filter_tab = tk.Frame(notebook, bg='white')
notebook.add(filter_tab, text='📱 筛选')

# 左右分割
filter_left = tk.Frame(filter_tab, bg='white')
filter_left.pack(side='left', fill='both', expand=True, padx=10, pady=10)

filter_right = tk.Frame(filter_tab, bg='white')
filter_right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

# 左侧 - 输入区域
tk.Label(filter_left, text="📞 手机号列表（每行一个）:",
         font=('Arial', 11, 'bold'), bg='white').pack(anchor='w', pady=5)

phone_text = scrolledtext.ScrolledText(filter_left, height=20, width=40, font=('Arial', 11))
phone_text.pack(fill='both', expand=True, pady=5)

# 按钮区域
btn_frame = tk.Frame(filter_left, bg='white')
btn_frame.pack(fill='x', pady=10)

def import_phones():
    filename = filedialog.askopenfilename(
        title="选择号码文件",
        filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
    )
    if filename:
        with open(filename, 'r', encoding='utf-8') as f:
            phones = f.read()
        phone_text.delete('1.0', 'end')
        phone_text.insert('1.0', phones)
        log_message(f"✅ 已导入 {filename}")

tk.Button(btn_frame, text="📂 从文件导入", command=import_phones,
          font=('Arial', 10)).pack(side='left', padx=5)
tk.Button(btn_frame, text="🗑️ 清空", command=lambda: phone_text.delete('1.0', 'end'),
          font=('Arial', 10)).pack(side='left', padx=5)

# 国家选择
country_frame = tk.Frame(filter_left, bg='white')
country_frame.pack(fill='x', pady=10)

tk.Label(country_frame, text="🌍 目标国家:", font=('Arial', 10), bg='white').pack(side='left', padx=5)
country_var = tk.StringVar(value="US")
tk.Radiobutton(country_frame, text="美国 🇺🇸", variable=country_var, value="US",
               font=('Arial', 10), bg='white').pack(side='left', padx=5)
tk.Radiobutton(country_frame, text="中国 🇨🇳", variable=country_var, value="CN",
               font=('Arial', 10), bg='white').pack(side='left', padx=5)

# 开始按钮
def start_filtering():
    if not config.get('accounts'):
        messagebox.showerror("错误", "请先在'账号管理'中添加至少一个账号")
        return

    phones_text = phone_text.get('1.0', 'end').strip()
    if not phones_text:
        messagebox.showerror("错误", "请输入要筛选的手机号")
        return

    phones = [p.strip() for p in phones_text.split('\n') if p.strip()]
    log_message(f"🚀 准备筛选 {len(phones)} 个号码...")
    log_message("💡 实际筛选功能请使用命令行版本：")
    log_message("   python3 main_multi.py --file phones.txt --country US")

tk.Button(filter_left, text="🚀 开始筛选", command=start_filtering,
          font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white',
          height=2).pack(fill='x', pady=10)

# 右侧 - 日志区域
tk.Label(filter_right, text="📝 运行日志:",
         font=('Arial', 11, 'bold'), bg='white').pack(anchor='w', pady=5)

log_text = scrolledtext.ScrolledText(filter_right, height=30, width=60, font=('Arial', 10))
log_text.pack(fill='both', expand=True, pady=5)

def export_results():
    filename = filedialog.asksaveasfilename(
        title="保存结果",
        defaultextension=".csv",
        filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")]
    )
    if filename:
        log_message(f"💾 结果将导出到 {filename}")

tk.Button(filter_right, text="💾 导出结果", command=export_results,
          font=('Arial', 11)).pack(fill='x', pady=5)

# ==================== 标签页2: 账号管理 ====================
account_tab = tk.Frame(notebook, bg='white')
notebook.add(account_tab, text='👤 账号管理')

# 左右分割
account_left = tk.Frame(account_tab, bg='white')
account_left.pack(side='left', fill='both', expand=True, padx=10, pady=10)

account_right = tk.Frame(account_tab, bg='white')
account_right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

# 左侧 - 账号列表
tk.Label(account_left, text="👥 已配置账号:",
         font=('Arial', 11, 'bold'), bg='white').pack(anchor='w', pady=5)

account_listbox = tk.Listbox(account_left, height=20, font=('Arial', 10))
account_listbox.pack(fill='both', expand=True, pady=5)

def load_accounts():
    """加载账号列表"""
    account_listbox.delete(0, 'end')
    for acc in config.get('accounts', []):
        account_listbox.insert('end', f"{acc['name']} ({acc['phone']})")

def on_account_select(event):
    """选择账号"""
    selection = account_listbox.curselection()
    if selection:
        idx = selection[0]
        acc = config['accounts'][idx]
        acc_name_var.set(acc['name'])
        acc_api_id_var.set(acc['api_id'])
        acc_api_hash_var.set(acc['api_hash'])
        acc_phone_var.set(acc['phone'])

account_listbox.bind('<<ListboxSelect>>', on_account_select)

# 按钮
acc_btn_frame = tk.Frame(account_left, bg='white')
acc_btn_frame.pack(fill='x', pady=5)

def add_account():
    acc_name_var.set("")
    acc_api_id_var.set("")
    acc_api_hash_var.set("")
    acc_phone_var.set("")
    log_message("➕ 准备添加新账号")

def delete_account():
    selection = account_listbox.curselection()
    if not selection:
        messagebox.showwarning("提示", "请先选择要删除的账号")
        return

    if messagebox.askyesno("确认", "确定要删除这个账号吗？"):
        idx = selection[0]
        del config['accounts'][idx]
        save_config()
        load_accounts()

tk.Button(acc_btn_frame, text="➕ 添加", command=add_account, font=('Arial', 10)).pack(side='left', padx=2)
tk.Button(acc_btn_frame, text="🗑️ 删除", command=delete_account, font=('Arial', 10)).pack(side='left', padx=2)

# 右侧 - 账号详情
tk.Label(account_right, text="📋 账号详情",
         font=('Arial', 12, 'bold'), bg='white').pack(anchor='w', pady=10)

detail_frame = tk.Frame(account_right, bg='white')
detail_frame.pack(fill='both', expand=True)

tk.Label(detail_frame, text="账号名称:", font=('Arial', 10), bg='white').grid(row=0, column=0, sticky='w', pady=8, padx=5)
acc_name_var = tk.StringVar()
tk.Entry(detail_frame, textvariable=acc_name_var, width=30, font=('Arial', 10)).grid(row=0, column=1, pady=8, padx=5)

tk.Label(detail_frame, text="API ID:", font=('Arial', 10), bg='white').grid(row=1, column=0, sticky='w', pady=8, padx=5)
acc_api_id_var = tk.StringVar()
tk.Entry(detail_frame, textvariable=acc_api_id_var, width=30, font=('Arial', 10)).grid(row=1, column=1, pady=8, padx=5)

tk.Label(detail_frame, text="API Hash:", font=('Arial', 10), bg='white').grid(row=2, column=0, sticky='w', pady=8, padx=5)
acc_api_hash_var = tk.StringVar()
tk.Entry(detail_frame, textvariable=acc_api_hash_var, width=30, font=('Arial', 10)).grid(row=2, column=1, pady=8, padx=5)

tk.Label(detail_frame, text="手机号:", font=('Arial', 10), bg='white').grid(row=3, column=0, sticky='w', pady=8, padx=5)
acc_phone_var = tk.StringVar()
tk.Entry(detail_frame, textvariable=acc_phone_var, width=30, font=('Arial', 10)).grid(row=3, column=1, pady=8, padx=5)

def save_account():
    name = acc_name_var.get().strip()
    api_id = acc_api_id_var.get().strip()
    api_hash = acc_api_hash_var.get().strip()
    phone = acc_phone_var.get().strip()

    if not all([name, api_id, api_hash, phone]):
        messagebox.showerror("错误", "请填写所有字段")
        return

    account = {
        "name": name,
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": phone
    }

    selection = account_listbox.curselection()
    if selection:
        idx = selection[0]
        config['accounts'][idx] = account
    else:
        config['accounts'].append(account)

    save_config()
    load_accounts()
    messagebox.showinfo("成功", "账号已保存")

tk.Button(detail_frame, text="💾 保存账号", command=save_account,
          font=('Arial', 11, 'bold'), bg='#2196F3', fg='white',
          height=2).grid(row=4, column=0, columnspan=2, pady=20, sticky='ew')

help_text = """
💡 如何获取API凭证：
1. 访问 https://my.telegram.org
2. 登录你的Telegram账号
3. 点击 "API development tools"
4. 创建应用，获取 api_id 和 api_hash
"""
tk.Label(detail_frame, text=help_text, justify='left',
         font=('Arial', 9), fg='gray', bg='white').grid(row=5, column=0, columnspan=2, sticky='w')

# ==================== 标签页3: 设置 ====================
settings_tab = tk.Frame(notebook, bg='white')
notebook.add(settings_tab, text='⚙️ 设置')

settings_frame = tk.LabelFrame(settings_tab, text="⚙️ 速率控制设置",
                               font=('Arial', 11, 'bold'), bg='white', padx=20, pady=20)
settings_frame.pack(fill='both', expand=True, padx=20, pady=20)

tk.Label(settings_frame, text="单账号连续请求上限:", font=('Arial', 10), bg='white').grid(row=0, column=0, sticky='w', pady=10)
req_per_acc_var = tk.IntVar(value=config['rate_limit']['requests_per_account'])
tk.Spinbox(settings_frame, from_=10, to=100, textvariable=req_per_acc_var,
           width=10, font=('Arial', 10)).grid(row=0, column=1, sticky='w', pady=10)
tk.Label(settings_frame, text="次（建议20-50）", font=('Arial', 10), bg='white').grid(row=0, column=2, sticky='w', pady=10)

tk.Label(settings_frame, text="最小延迟:", font=('Arial', 10), bg='white').grid(row=1, column=0, sticky='w', pady=10)
min_delay_var = tk.IntVar(value=config['rate_limit']['min_delay'])
tk.Spinbox(settings_frame, from_=1, to=10, textvariable=min_delay_var,
           width=10, font=('Arial', 10)).grid(row=1, column=1, sticky='w', pady=10)
tk.Label(settings_frame, text="秒（建议3-5）", font=('Arial', 10), bg='white').grid(row=1, column=2, sticky='w', pady=10)

tk.Label(settings_frame, text="最大延迟:", font=('Arial', 10), bg='white').grid(row=2, column=0, sticky='w', pady=10)
max_delay_var = tk.IntVar(value=config['rate_limit']['max_delay'])
tk.Spinbox(settings_frame, from_=5, to=30, textvariable=max_delay_var,
           width=10, font=('Arial', 10)).grid(row=2, column=1, sticky='w', pady=10)
tk.Label(settings_frame, text="秒（建议8-15）", font=('Arial', 10), bg='white').grid(row=2, column=2, sticky='w', pady=10)

def save_settings():
    config['rate_limit']['requests_per_account'] = req_per_acc_var.get()
    config['rate_limit']['min_delay'] = min_delay_var.get()
    config['rate_limit']['max_delay'] = max_delay_var.get()
    save_config()
    messagebox.showinfo("成功", "设置已保存")

tk.Button(settings_frame, text="💾 保存设置", command=save_settings,
          font=('Arial', 11, 'bold'), bg='#FF9800', fg='white',
          height=2).grid(row=3, column=0, columnspan=3, pady=20, sticky='ew')

# 初始化
load_accounts()
log_message("✅ GUI已启动")
log_message("💡 请先在'账号管理'中添加账号")

# 运行主循环
root.mainloop()
