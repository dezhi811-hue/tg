#!/usr/bin/env python3
"""
Telegram筛号工具 - GUI界面（按钮切换版本）
"""
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import json
import os

root = tk.Tk()
root.title("Telegram 筛号工具")
root.geometry("1000x700")

config_path = "config.json"

def load_config():
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"accounts": [], "rate_limit": {"requests_per_account": 30, "min_delay": 3, "max_delay": 8}}

def save_config():
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    log_message("✅ 配置已保存")

def log_message(msg):
    from datetime import datetime
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_text.insert('end', f"[{timestamp}] {msg}\n")
    log_text.see('end')

config = load_config()

# 顶部导航栏
nav_frame = tk.Frame(root, bg='#2196F3', height=80)
nav_frame.pack(fill='x', side='top')
nav_frame.pack_propagate(False)

tk.Label(nav_frame, text="🚀 Telegram 筛号工具",
         font=('Arial', 18, 'bold'), bg='#2196F3', fg='white').pack(pady=10)

# 按钮导航
btn_nav_frame = tk.Frame(nav_frame, bg='#2196F3')
btn_nav_frame.pack()

# 内容区域
content_frame = tk.Frame(root, bg='white')
content_frame.pack(fill='both', expand=True)

# 创建3个页面
filter_page = tk.Frame(content_frame, bg='white')
account_page = tk.Frame(content_frame, bg='white')
settings_page = tk.Frame(content_frame, bg='white')

current_page = [None]

def show_page(page):
    if current_page[0]:
        current_page[0].pack_forget()
    page.pack(fill='both', expand=True)
    current_page[0] = page

# 导航按钮
def create_nav_button(text, page):
    btn = tk.Button(btn_nav_frame, text=text, font=('Arial', 12, 'bold'),
                    bg='#1976D2', fg='white', relief='flat',
                    padx=20, pady=8, command=lambda: show_page(page))
    btn.pack(side='left', padx=5)
    return btn

btn1 = create_nav_button('📱 筛选', filter_page)
btn2 = create_nav_button('👤 账号管理', account_page)
btn3 = create_nav_button('⚙️ 设置', settings_page)

# ========== 筛选页面 ==========
left_frame = tk.Frame(filter_page, bg='white')
left_frame.pack(side='left', fill='both', expand=True, padx=10, pady=10)

tk.Label(left_frame, text="📞 手机号列表（每行一个）",
         font=('Arial', 12, 'bold'), bg='white').pack(anchor='w', pady=5)

phone_text = scrolledtext.ScrolledText(left_frame, height=20, width=40, font=('Arial', 11))
phone_text.pack(fill='both', expand=True, pady=5)

btn_frame = tk.Frame(left_frame, bg='white')
btn_frame.pack(fill='x', pady=10)

def import_phones():
    filename = filedialog.askopenfilename(filetypes=[("文本文件", "*.txt")])
    if filename:
        with open(filename, 'r') as f:
            phone_text.delete('1.0', 'end')
            phone_text.insert('1.0', f.read())
        log_message(f"✅ 已导入 {filename}")

tk.Button(btn_frame, text="📂 从文件导入", command=import_phones,
          font=('Arial', 10), bg='#2196F3', fg='white').pack(side='left', padx=3)
tk.Button(btn_frame, text="🗑️ 清空", command=lambda: phone_text.delete('1.0', 'end'),
          font=('Arial', 10), bg='#f44336', fg='white').pack(side='left', padx=3)

country_frame = tk.Frame(left_frame, bg='white')
country_frame.pack(fill='x', pady=10)
tk.Label(country_frame, text="🌍 目标国家:", font=('Arial', 11), bg='white').pack(side='left', padx=5)
country_var = tk.StringVar(value="US")
tk.Radiobutton(country_frame, text="美国🇺🇸", variable=country_var, value="US",
               font=('Arial', 11), bg='white').pack(side='left', padx=5)
tk.Radiobutton(country_frame, text="中国🇨🇳", variable=country_var, value="CN",
               font=('Arial', 11), bg='white').pack(side='left', padx=5)

def start_filtering():
    if not config.get('accounts'):
        messagebox.showerror("错误", "请先在'账号管理'中添加账号")
        return
    phones = [p.strip() for p in phone_text.get('1.0', 'end').split('\n') if p.strip()]
    if not phones:
        messagebox.showerror("错误", "请输入手机号")
        return
    log_message(f"🚀 准备筛选 {len(phones)} 个号码")
    log_message("💡 实际筛选请使用: python3 main_multi.py --file phones.txt")

tk.Button(left_frame, text="🚀 开始筛选", command=start_filtering,
          font=('Arial', 14, 'bold'), bg='#4CAF50', fg='white', height=2).pack(fill='x', pady=10)

right_frame = tk.Frame(filter_page, bg='white')
right_frame.pack(side='right', fill='both', expand=True, padx=10, pady=10)

tk.Label(right_frame, text="📝 运行日志", font=('Arial', 12, 'bold'), bg='white').pack(anchor='w', pady=5)
log_text = scrolledtext.ScrolledText(right_frame, height=30, width=60, font=('Arial', 10))
log_text.pack(fill='both', expand=True, pady=5)

# ========== 账号管理页面 ==========
acc_left = tk.Frame(account_page, bg='white')
acc_left.pack(side='left', fill='both', expand=True, padx=10, pady=10)

tk.Label(acc_left, text="👥 已配置账号", font=('Arial', 12, 'bold'), bg='white').pack(anchor='w', pady=5)
account_listbox = tk.Listbox(acc_left, height=20, font=('Arial', 10))
account_listbox.pack(fill='both', expand=True, pady=5)

def load_accounts():
    account_listbox.delete(0, 'end')
    for acc in config.get('accounts', []):
        account_listbox.insert('end', f"{acc['name']} ({acc['phone']})")

def on_select(event):
    sel = account_listbox.curselection()
    if sel:
        acc = config['accounts'][sel[0]]
        name_var.set(acc['name'])
        api_id_var.set(acc['api_id'])
        api_hash_var.set(acc['api_hash'])
        phone_var.set(acc['phone'])

account_listbox.bind('<<ListboxSelect>>', on_select)

acc_btn = tk.Frame(acc_left, bg='white')
acc_btn.pack(fill='x', pady=5)

def add_account():
    name_var.set("")
    api_id_var.set("")
    api_hash_var.set("")
    phone_var.set("")

def delete_account():
    sel = account_listbox.curselection()
    if sel and messagebox.askyesno("确认", "确定删除？"):
        del config['accounts'][sel[0]]
        save_config()
        load_accounts()

tk.Button(acc_btn, text="➕ 添加", command=add_account, font=('Arial', 10),
          bg='#4CAF50', fg='white').pack(side='left', padx=3)
tk.Button(acc_btn, text="🗑️ 删除", command=delete_account, font=('Arial', 10),
          bg='#f44336', fg='white').pack(side='left', padx=3)

acc_right = tk.Frame(account_page, bg='white')
acc_right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

tk.Label(acc_right, text="📋 账号详情", font=('Arial', 12, 'bold'), bg='white').pack(anchor='w', pady=10)

detail = tk.Frame(acc_right, bg='white')
detail.pack(fill='both', expand=True)

tk.Label(detail, text="账号名称:", font=('Arial', 11), bg='white').grid(row=0, column=0, sticky='w', pady=10)
name_var = tk.StringVar()
tk.Entry(detail, textvariable=name_var, width=30, font=('Arial', 11)).grid(row=0, column=1, pady=10)

tk.Label(detail, text="API ID:", font=('Arial', 11), bg='white').grid(row=1, column=0, sticky='w', pady=10)
api_id_var = tk.StringVar()
tk.Entry(detail, textvariable=api_id_var, width=30, font=('Arial', 11)).grid(row=1, column=1, pady=10)

tk.Label(detail, text="API Hash:", font=('Arial', 11), bg='white').grid(row=2, column=0, sticky='w', pady=10)
api_hash_var = tk.StringVar()
tk.Entry(detail, textvariable=api_hash_var, width=30, font=('Arial', 11)).grid(row=2, column=1, pady=10)

tk.Label(detail, text="手机号:", font=('Arial', 11), bg='white').grid(row=3, column=0, sticky='w', pady=10)
phone_var = tk.StringVar()
tk.Entry(detail, textvariable=phone_var, width=30, font=('Arial', 11)).grid(row=3, column=1, pady=10)

def save_account():
    if not all([name_var.get(), api_id_var.get(), api_hash_var.get(), phone_var.get()]):
        messagebox.showerror("错误", "请填写所有字段")
        return
    acc = {"name": name_var.get(), "api_id": api_id_var.get(),
           "api_hash": api_hash_var.get(), "phone": phone_var.get()}
    sel = account_listbox.curselection()
    if sel:
        config['accounts'][sel[0]] = acc
    else:
        config['accounts'].append(acc)
    save_config()
    load_accounts()
    messagebox.showinfo("成功", "账号已保存")

tk.Button(detail, text="💾 保存账号", command=save_account,
          font=('Arial', 12, 'bold'), bg='#2196F3', fg='white', height=2).grid(row=4, column=0, columnspan=2, pady=20, sticky='ew')

tk.Label(detail, text="💡 获取API: https://my.telegram.org",
         font=('Arial', 9), fg='#666', bg='white').grid(row=5, column=0, columnspan=2, sticky='w')

# ========== 设置页面 ==========
settings_frame = tk.Frame(settings_page, bg='white')
settings_frame.pack(fill='both', expand=True, padx=50, pady=50)

tk.Label(settings_frame, text="⚙️ 速率控制设置", font=('Arial', 14, 'bold'), bg='white').pack(pady=20)

tk.Label(settings_frame, text="单账号请求上限:", font=('Arial', 11), bg='white').pack(anchor='w', pady=5)
req_var = tk.IntVar(value=config['rate_limit']['requests_per_account'])
tk.Spinbox(settings_frame, from_=10, to=100, textvariable=req_var, width=15, font=('Arial', 11)).pack(anchor='w', pady=5)

tk.Label(settings_frame, text="最小延迟(秒):", font=('Arial', 11), bg='white').pack(anchor='w', pady=5)
min_var = tk.IntVar(value=config['rate_limit']['min_delay'])
tk.Spinbox(settings_frame, from_=1, to=10, textvariable=min_var, width=15, font=('Arial', 11)).pack(anchor='w', pady=5)

tk.Label(settings_frame, text="最大延迟(秒):", font=('Arial', 11), bg='white').pack(anchor='w', pady=5)
max_var = tk.IntVar(value=config['rate_limit']['max_delay'])
tk.Spinbox(settings_frame, from_=5, to=30, textvariable=max_var, width=15, font=('Arial', 11)).pack(anchor='w', pady=5)

def save_settings():
    config['rate_limit']['requests_per_account'] = req_var.get()
    config['rate_limit']['min_delay'] = min_var.get()
    config['rate_limit']['max_delay'] = max_var.get()
    save_config()
    messagebox.showinfo("成功", "设置已保存")

tk.Button(settings_frame, text="💾 保存设置", command=save_settings,
          font=('Arial', 12, 'bold'), bg='#FF9800', fg='white', height=2, width=20).pack(pady=30)

# 初始化
load_accounts()
show_page(filter_page)
log_message("✅ GUI已启动")
log_message("💡 点击顶部按钮切换页面")

root.mainloop()
