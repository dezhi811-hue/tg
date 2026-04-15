#!/usr/bin/env python3
"""
Telegram筛号工具 - GUI界面（修复版）
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
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    log_message("✅ 配置已保存")

def log_message(msg):
    from datetime import datetime
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_text.insert('end', f"[{timestamp}] {msg}\n")
    log_text.see('end')

config = load_config()

# 创建顶部标题
title_frame = tk.Frame(root, bg='#2196F3', height=60)
title_frame.pack(fill='x', side='top')
title_frame.pack_propagate(False)

title_label = tk.Label(title_frame, text="🚀 Telegram 筛号工具",
                       font=('Arial', 20, 'bold'), bg='#2196F3', fg='white')
title_label.pack(expand=True)

# 创建Notebook（标签页） - 使用更大的字体
style = ttk.Style()
style.configure('TNotebook.Tab', font=('Arial', 12, 'bold'), padding=[20, 10])

notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True, padx=5, pady=5)

# ==================== 标签页1: 筛选 ====================
filter_tab = tk.Frame(notebook, bg='#f5f5f5')
notebook.add(filter_tab, text='  📱 筛选  ')

# 使用PanedWindow分割
paned = tk.PanedWindow(filter_tab, orient='horizontal', sashwidth=5, bg='#ddd')
paned.pack(fill='both', expand=True, padx=5, pady=5)

# 左侧框架
filter_left = tk.Frame(paned, bg='white', relief='raised', bd=2)
paned.add(filter_left, width=400)

tk.Label(filter_left, text="📞 手机号列表（每行一个）",
         font=('Arial', 12, 'bold'), bg='white', fg='#333').pack(anchor='w', padx=10, pady=10)

phone_text = scrolledtext.ScrolledText(filter_left, height=18, width=35, font=('Arial', 11))
phone_text.pack(fill='both', expand=True, padx=10, pady=5)

# 按钮区域
btn_frame = tk.Frame(filter_left, bg='white')
btn_frame.pack(fill='x', padx=10, pady=10)

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
          font=('Arial', 10), bg='#2196F3', fg='white', relief='flat',
          padx=10, pady=5).pack(side='left', padx=3)
tk.Button(btn_frame, text="🗑️ 清空", command=lambda: phone_text.delete('1.0', 'end'),
          font=('Arial', 10), bg='#f44336', fg='white', relief='flat',
          padx=10, pady=5).pack(side='left', padx=3)

# 国家选择
country_frame = tk.Frame(filter_left, bg='white')
country_frame.pack(fill='x', padx=10, pady=10)

tk.Label(country_frame, text="🌍 目标国家:", font=('Arial', 11, 'bold'),
         bg='white').pack(side='left', padx=5)
country_var = tk.StringVar(value="US")
tk.Radiobutton(country_frame, text="美国 🇺🇸", variable=country_var, value="US",
               font=('Arial', 11), bg='white').pack(side='left', padx=10)
tk.Radiobutton(country_frame, text="中国 🇨🇳", variable=country_var, value="CN",
               font=('Arial', 11), bg='white').pack(side='left', padx=10)

# 开始按钮
def start_filtering():
    if not config.get('accounts'):
        messagebox.showerror("错误", "请先在'账号管理'标签中添加至少一个账号")
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
          font=('Arial', 14, 'bold'), bg='#4CAF50', fg='white',
          relief='flat', height=2).pack(fill='x', padx=10, pady=10)

# 右侧框架
filter_right = tk.Frame(paned, bg='white', relief='raised', bd=2)
paned.add(filter_right, width=550)

tk.Label(filter_right, text="📝 运行日志",
         font=('Arial', 12, 'bold'), bg='white', fg='#333').pack(anchor='w', padx=10, pady=10)

log_text = scrolledtext.ScrolledText(filter_right, height=25, width=55, font=('Arial', 10))
log_text.pack(fill='both', expand=True, padx=10, pady=5)

def export_results():
    filename = filedialog.asksaveasfilename(
        title="保存结果",
        defaultextension=".csv",
        filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")]
    )
    if filename:
        log_message(f"💾 结果将导出到 {filename}")

tk.Button(filter_right, text="💾 导出结果", command=export_results,
          font=('Arial', 11), bg='#FF9800', fg='white', relief='flat',
          padx=20, pady=8).pack(fill='x', padx=10, pady=10)

# ==================== 标签页2: 账号管理 ====================
account_tab = tk.Frame(notebook, bg='#f5f5f5')
notebook.add(account_tab, text='  👤 账号管理  ')

# 使用PanedWindow分割
acc_paned = tk.PanedWindow(account_tab, orient='horizontal', sashwidth=5, bg='#ddd')
acc_paned.pack(fill='both', expand=True, padx=5, pady=5)

# 左侧
account_left = tk.Frame(acc_paned, bg='white', relief='raised', bd=2)
acc_paned.add(account_left, width=350)

tk.Label(account_left, text="👥 已配置账号",
         font=('Arial', 12, 'bold'), bg='white', fg='#333').pack(anchor='w', padx=10, pady=10)

account_listbox = tk.Listbox(account_left, height=18, font=('Arial', 10))
account_listbox.pack(fill='both', expand=True, padx=10, pady=5)

def load_accounts():
    account_listbox.delete(0, 'end')
    for acc in config.get('accounts', []):
        account_listbox.insert('end', f"{acc['name']} ({acc['phone']})")

def on_account_select(event):
    selection = account_listbox.curselection()
    if selection:
        idx = selection[0]
        acc = config['accounts'][idx]
        acc_name_var.set(acc['name'])
        acc_api_id_var.set(acc['api_id'])
        acc_api_hash_var.set(acc['api_hash'])
        acc_phone_var.set(acc['phone'])

account_listbox.bind('<<ListboxSelect>>', on_account_select)

acc_btn_frame = tk.Frame(account_left, bg='white')
acc_btn_frame.pack(fill='x', padx=10, pady=10)

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

tk.Button(acc_btn_frame, text="➕ 添加", command=add_account,
          font=('Arial', 10), bg='#4CAF50', fg='white', relief='flat',
          padx=15, pady=5).pack(side='left', padx=3)
tk.Button(acc_btn_frame, text="🗑️ 删除", command=delete_account,
          font=('Arial', 10), bg='#f44336', fg='white', relief='flat',
          padx=15, pady=5).pack(side='left', padx=3)

# 右侧
account_right = tk.Frame(acc_paned, bg='white', relief='raised', bd=2)
acc_paned.add(account_right, width=600)

tk.Label(account_right, text="📋 账号详情",
         font=('Arial', 12, 'bold'), bg='white', fg='#333').pack(anchor='w', padx=10, pady=10)

detail_frame = tk.Frame(account_right, bg='white')
detail_frame.pack(fill='both', expand=True, padx=20, pady=10)

tk.Label(detail_frame, text="账号名称:", font=('Arial', 11), bg='white').grid(row=0, column=0, sticky='w', pady=12, padx=5)
acc_name_var = tk.StringVar()
tk.Entry(detail_frame, textvariable=acc_name_var, width=35, font=('Arial', 11)).grid(row=0, column=1, pady=12, padx=5)

tk.Label(detail_frame, text="API ID:", font=('Arial', 11), bg='white').grid(row=1, column=0, sticky='w', pady=12, padx=5)
acc_api_id_var = tk.StringVar()
tk.Entry(detail_frame, textvariable=acc_api_id_var, width=35, font=('Arial', 11)).grid(row=1, column=1, pady=12, padx=5)

tk.Label(detail_frame, text="API Hash:", font=('Arial', 11), bg='white').grid(row=2, column=0, sticky='w', pady=12, padx=5)
acc_api_hash_var = tk.StringVar()
tk.Entry(detail_frame, textvariable=acc_api_hash_var, width=35, font=('Arial', 11)).grid(row=2, column=1, pady=12, padx=5)

tk.Label(detail_frame, text="手机号:", font=('Arial', 11), bg='white').grid(row=3, column=0, sticky='w', pady=12, padx=5)
acc_phone_var = tk.StringVar()
tk.Entry(detail_frame, textvariable=acc_phone_var, width=35, font=('Arial', 11)).grid(row=3, column=1, pady=12, padx=5)

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
          font=('Arial', 12, 'bold'), bg='#2196F3', fg='white',
          relief='flat', height=2).grid(row=4, column=0, columnspan=2, pady=20, sticky='ew')

help_text = """💡 如何获取API凭证：
1. 访问 https://my.telegram.org
2. 登录你的Telegram账号
3. 点击 "API development tools"
4. 创建应用，获取 api_id 和 api_hash"""

tk.Label(detail_frame, text=help_text, justify='left',
         font=('Arial', 9), fg='#666', bg='white').grid(row=5, column=0, columnspan=2, sticky='w', pady=10)

# ==================== 标签页3: 设置 ====================
settings_tab = tk.Frame(notebook, bg='#f5f5f5')
notebook.add(settings_tab, text='  ⚙️ 设置  ')

settings_frame = tk.LabelFrame(settings_tab, text=" ⚙️ 速率控制设置 ",
                               font=('Arial', 12, 'bold'), bg='white',
                               relief='raised', bd=2)
settings_frame.pack(fill='both', expand=True, padx=20, pady=20)

settings_inner = tk.Frame(settings_frame, bg='white')
settings_inner.pack(padx=30, pady=30)

tk.Label(settings_inner, text="单账号连续请求上限:", font=('Arial', 11), bg='white').grid(row=0, column=0, sticky='w', pady=15)
req_per_acc_var = tk.IntVar(value=config['rate_limit']['requests_per_account'])
tk.Spinbox(settings_inner, from_=10, to=100, textvariable=req_per_acc_var,
           width=12, font=('Arial', 11)).grid(row=0, column=1, sticky='w', pady=15, padx=10)
tk.Label(settings_inner, text="次（建议20-50）", font=('Arial', 10), bg='white', fg='#666').grid(row=0, column=2, sticky='w', pady=15)

tk.Label(settings_inner, text="最小延迟:", font=('Arial', 11), bg='white').grid(row=1, column=0, sticky='w', pady=15)
min_delay_var = tk.IntVar(value=config['rate_limit']['min_delay'])
tk.Spinbox(settings_inner, from_=1, to=10, textvariable=min_delay_var,
           width=12, font=('Arial', 11)).grid(row=1, column=1, sticky='w', pady=15, padx=10)
tk.Label(settings_inner, text="秒（建议3-5）", font=('Arial', 10), bg='white', fg='#666').grid(row=1, column=2, sticky='w', pady=15)

tk.Label(settings_inner, text="最大延迟:", font=('Arial', 11), bg='white').grid(row=2, column=0, sticky='w', pady=15)
max_delay_var = tk.IntVar(value=config['rate_limit']['max_delay'])
tk.Spinbox(settings_inner, from_=5, to=30, textvariable=max_delay_var,
           width=12, font=('Arial', 11)).grid(row=2, column=1, sticky='w', pady=15, padx=10)
tk.Label(settings_inner, text="秒（建议8-15）", font=('Arial', 10), bg='white', fg='#666').grid(row=2, column=2, sticky='w', pady=15)

def save_settings():
    config['rate_limit']['requests_per_account'] = req_per_acc_var.get()
    config['rate_limit']['min_delay'] = min_delay_var.get()
    config['rate_limit']['max_delay'] = max_delay_var.get()
    save_config()
    messagebox.showinfo("成功", "设置已保存")

tk.Button(settings_inner, text="💾 保存设置", command=save_settings,
          font=('Arial', 12, 'bold'), bg='#FF9800', fg='white',
          relief='flat', height=2, width=20).grid(row=3, column=0, columnspan=3, pady=30)

# 初始化
load_accounts()
log_message("✅ GUI已启动")
log_message("💡 请先切换到'账号管理'标签添加账号")
log_message("💡 然后回到'筛选'标签开始使用")

# 运行
root.mainloop()
