#!/usr/bin/env python3
"""
Telegram筛号工具 - 完全可用版本
"""
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import json
import os

config_path = "config.json"

def load_config():
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"accounts": [], "rate_limit": {"requests_per_account": 30, "min_delay": 3, "max_delay": 8}}

config = load_config()

def save_config():
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

# 创建主窗口
root = tk.Tk()
root.title("Telegram 筛号工具")
root.geometry("1200x700")
root.configure(bg='#f5f5f5')

# ========== 顶部标题 ==========
header = tk.Frame(root, bg='#2196F3', height=70)
header.pack(fill='x')
header.pack_propagate(False)

tk.Label(header, text="🚀 Telegram 筛号工具",
         font=('Arial', 20, 'bold'),
         bg='#2196F3', fg='white').pack(pady=20)

# ========== 导航栏 ==========
nav_bar = tk.Frame(root, bg='#1976D2', height=50)
nav_bar.pack(fill='x')
nav_bar.pack_propagate(False)

# ========== 内容区 ==========
content = tk.Frame(root, bg='white')
content.pack(fill='both', expand=True)

# 创建三个页面
page_filter = tk.Frame(content, bg='white')
page_account = tk.Frame(content, bg='white')
page_settings = tk.Frame(content, bg='white')

current_page = [None]
active_btn = [None]

def show_page(page, btn):
    if current_page[0]:
        current_page[0].pack_forget()

    page.pack(fill='both', expand=True, padx=20, pady=20)
    current_page[0] = page

    if active_btn[0]:
        active_btn[0].config(bg='#1976D2', relief='flat')
    btn.config(bg='#0D47A1', relief='sunken')
    active_btn[0] = btn

# 导航按钮
def create_nav_btn(text, page):
    btn = tk.Button(nav_bar, text=text,
                    font=('Arial', 12, 'bold'),
                    bg='#1976D2', fg='white',
                    relief='flat', bd=0,
                    padx=25, pady=10,
                    command=lambda: show_page(page, btn))
    btn.pack(side='left', padx=2)
    return btn

btn_filter = create_nav_btn('📱 筛选', page_filter)
btn_account = create_nav_btn('👤 账号管理', page_account)
btn_settings = create_nav_btn('⚙️ 设置', page_settings)

# ==================== 筛选页面 ====================
filter_left = tk.Frame(page_filter, bg='white', width=450)
filter_left.pack(side='left', fill='both', padx=10, pady=10)
filter_left.pack_propagate(False)

tk.Label(filter_left, text="📞 手机号列表",
         font=('Arial', 13, 'bold'),
         bg='white').pack(anchor='w', pady=(0,10))

phone_text = scrolledtext.ScrolledText(filter_left, height=18,
                                       font=('Consolas', 11))
phone_text.pack(fill='both', expand=True, pady=(0,10))

btn_group = tk.Frame(filter_left, bg='white')
btn_group.pack(fill='x', pady=10)

def import_phones():
    filename = filedialog.askopenfilename(filetypes=[("文本文件", "*.txt")])
    if filename:
        with open(filename, 'r') as f:
            phone_text.delete('1.0', 'end')
            phone_text.insert('1.0', f.read())
        log_text.insert('end', f"✅ 已导入 {filename}\n")
        log_text.see('end')

tk.Button(btn_group, text="📂 导入文件",
          command=import_phones,
          font=('Arial', 10),
          bg='#2196F3', fg='white',
          padx=15, pady=8).pack(side='left', padx=5)

tk.Button(btn_group, text="🗑️ 清空",
          command=lambda: phone_text.delete('1.0', 'end'),
          font=('Arial', 10),
          bg='#f44336', fg='white',
          padx=15, pady=8).pack(side='left', padx=5)

country_group = tk.Frame(filter_left, bg='white')
country_group.pack(fill='x', pady=10)

tk.Label(country_group, text="🌍 目标国家:",
         font=('Arial', 11),
         bg='white').pack(side='left', padx=(0,10))

country_var = tk.StringVar(value="US")
tk.Radiobutton(country_group, text="🇺🇸 美国",
               variable=country_var, value="US",
               font=('Arial', 11),
               bg='white').pack(side='left', padx=5)

tk.Radiobutton(country_group, text="🇨🇳 中国",
               variable=country_var, value="CN",
               font=('Arial', 11),
               bg='white').pack(side='left', padx=5)

def start_filtering():
    if not config.get('accounts'):
        messagebox.showerror("错误", "请先在'账号管理'中添加账号")
        return
    phones = [p.strip() for p in phone_text.get('1.0', 'end').split('\n') if p.strip()]
    if not phones:
        messagebox.showerror("错误", "请输入手机号")
        return
    log_text.insert('end', f"🚀 准备筛选 {len(phones)} 个号码\n")
    log_text.insert('end', "💡 实际筛选请使用: python3 main_multi.py --file phones.txt\n")
    log_text.see('end')

tk.Button(filter_left, text="🚀 开始筛选",
          command=start_filtering,
          font=('Arial', 14, 'bold'),
          bg='#4CAF50', fg='white',
          height=2).pack(fill='x', pady=10)

filter_right = tk.Frame(page_filter, bg='white')
filter_right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

tk.Label(filter_right, text="📝 运行日志",
         font=('Arial', 13, 'bold'),
         bg='white').pack(anchor='w', pady=(0,10))

log_text = scrolledtext.ScrolledText(filter_right, height=25,
                                     font=('Consolas', 10))
log_text.pack(fill='both', expand=True)

# ==================== 账号管理页面 ====================
acc_left = tk.Frame(page_account, bg='white', width=400)
acc_left.pack(side='left', fill='both', padx=10, pady=10)
acc_left.pack_propagate(False)

tk.Label(acc_left, text="👥 已配置账号",
         font=('Arial', 13, 'bold'),
         bg='white').pack(anchor='w', pady=(0,10))

account_listbox = tk.Listbox(acc_left, height=20, font=('Arial', 11))
account_listbox.pack(fill='both', expand=True, pady=(0,10))

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

acc_btn_group = tk.Frame(acc_left, bg='white')
acc_btn_group.pack(fill='x')

def add_account():
    name_var.set("")
    api_id_var.set("")
    api_hash_var.set("")
    phone_var.set("")

def delete_account():
    sel = account_listbox.curselection()
    if sel and messagebox.askyesno("确认", "确定删除该账号？"):
        del config['accounts'][sel[0]]
        save_config()
        load_accounts()

tk.Button(acc_btn_group, text="➕ 新建",
          command=add_account,
          font=('Arial', 10),
          bg='#4CAF50', fg='white',
          padx=15, pady=8).pack(side='left', padx=5)

tk.Button(acc_btn_group, text="🗑️ 删除",
          command=delete_account,
          font=('Arial', 10),
          bg='#f44336', fg='white',
          padx=15, pady=8).pack(side='left', padx=5)

acc_right = tk.Frame(page_account, bg='white')
acc_right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

tk.Label(acc_right, text="📋 账号详情",
         font=('Arial', 13, 'bold'),
         bg='white').pack(anchor='w', pady=(0,20))

detail_form = tk.Frame(acc_right, bg='white')
detail_form.pack(fill='x', padx=20)

name_var = tk.StringVar()
api_id_var = tk.StringVar()
api_hash_var = tk.StringVar()
phone_var = tk.StringVar()

fields = [
    ("账号名称:", name_var),
    ("API ID:", api_id_var),
    ("API Hash:", api_hash_var),
    ("手机号:", phone_var)
]

for i, (label_text, var) in enumerate(fields):
    tk.Label(detail_form, text=label_text,
             font=('Arial', 11),
             bg='white').grid(row=i, column=0, sticky='w', pady=15, padx=(0,10))

    tk.Entry(detail_form, textvariable=var,
             width=35,
             font=('Arial', 11)).grid(row=i, column=1, sticky='ew', pady=15)

detail_form.columnconfigure(1, weight=1)

def save_account():
    if not all([name_var.get(), api_id_var.get(), api_hash_var.get(), phone_var.get()]):
        messagebox.showerror("错误", "请填写所有字段")
        return

    acc = {
        "name": name_var.get(),
        "api_id": api_id_var.get(),
        "api_hash": api_hash_var.get(),
        "phone": phone_var.get()
    }

    sel = account_listbox.curselection()
    if sel:
        config['accounts'][sel[0]] = acc
    else:
        config['accounts'].append(acc)

    save_config()
    load_accounts()
    messagebox.showinfo("成功", "账号已保存")

tk.Button(detail_form, text="💾 保存账号",
          command=save_account,
          font=('Arial', 12, 'bold'),
          bg='#2196F3', fg='white',
          height=2).grid(row=len(fields), column=0, columnspan=2,
                        pady=30, sticky='ew')

tk.Label(detail_form, text="💡 获取API凭证: https://my.telegram.org",
         font=('Arial', 9),
         fg='#666', bg='white').grid(row=len(fields)+1, column=0, columnspan=2, sticky='w')

# ==================== 设置页面 ====================
settings_form = tk.Frame(page_settings, bg='white')
settings_form.pack(padx=50, pady=50)

tk.Label(settings_form, text="⚙️ 速率控制设置",
         font=('Arial', 15, 'bold'),
         bg='white').pack(pady=(0,30))

req_var = tk.IntVar(value=config['rate_limit']['requests_per_account'])
min_var = tk.IntVar(value=config['rate_limit']['min_delay'])
max_var = tk.IntVar(value=config['rate_limit']['max_delay'])

settings_items = [
    ("单账号请求上限:", req_var, 10, 100),
    ("最小延迟(秒):", min_var, 1, 10),
    ("最大延迟(秒):", max_var, 5, 30)
]

for label_text, var, from_, to in settings_items:
    frame = tk.Frame(settings_form, bg='white')
    frame.pack(fill='x', pady=15)

    tk.Label(frame, text=label_text,
             font=('Arial', 11),
             bg='white', width=20, anchor='w').pack(side='left', padx=(0,10))

    tk.Spinbox(frame, from_=from_, to=to,
               textvariable=var,
               width=15,
               font=('Arial', 11)).pack(side='left')

def save_settings():
    config['rate_limit']['requests_per_account'] = req_var.get()
    config['rate_limit']['min_delay'] = min_var.get()
    config['rate_limit']['max_delay'] = max_var.get()
    save_config()
    messagebox.showinfo("成功", "设置已保存")

tk.Button(settings_form, text="💾 保存设置",
          command=save_settings,
          font=('Arial', 12, 'bold'),
          bg='#FF9800', fg='white',
          height=2, width=25).pack(pady=40)

# 初始化
load_accounts()
show_page(page_filter, btn_filter)
log_text.insert('end', "✅ GUI已启动\n")
log_text.insert('end', "💡 点击顶部按钮切换页面\n")

root.mainloop()
