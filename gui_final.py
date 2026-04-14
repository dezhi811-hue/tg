#!/usr/bin/env python3
"""
Telegram筛号工具 - 修复布局版本
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

# 强制禁用深色模式
try:
    from sys import platform
    if platform == "darwin":  # macOS
        root.tk.call('tk::unsupported::MacWindowStyle', 'style', root._w, 'document', 'closeBox horizontalZoom verticalZoom collapseBox resizable')
except:
    pass

root.configure(bg='#e0e0e0')

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

# ========== 内容容器 ==========
container = tk.Frame(root, bg='#e8e8e8')
container.pack(fill='both', expand=True)

# 创建三个独立的页面Frame
pages = {}
pages['filter'] = tk.Frame(container, bg='#e8e8e8')
pages['account'] = tk.Frame(container, bg='#e8e8e8')
pages['settings'] = tk.Frame(container, bg='#e8e8e8')

current_page = {'name': None}
active_btn = {'btn': None}

def switch_page(page_name, btn):
    # 隐藏所有页面
    for page in pages.values():
        page.place_forget()

    # 显示选中的页面
    pages[page_name].place(x=0, y=0, relwidth=1, relheight=1)
    current_page['name'] = page_name

    # 更新按钮样式
    if active_btn['btn']:
        active_btn['btn'].config(bg='#1976D2', relief='flat')
    btn.config(bg='#0D47A1', relief='sunken')
    active_btn['btn'] = btn

# 导航按钮
def create_nav_btn(text, page_name):
    btn = tk.Button(nav_bar, text=text,
                    font=('Arial', 12, 'bold'),
                    bg='#1976D2', fg='white',
                    relief='flat', bd=0,
                    padx=25, pady=10,
                    command=lambda: switch_page(page_name, btn))
    btn.pack(side='left', padx=2)
    return btn

btn_filter = create_nav_btn('📱 筛选', 'filter')
btn_account = create_nav_btn('👤 账号管理', 'account')
btn_settings = create_nav_btn('⚙️ 设置', 'settings')

# ==================== 筛选页面 ====================
page_filter = pages['filter']

filter_left = tk.Frame(page_filter, bg='#f5f5f5', relief='solid', bd=1)
filter_left.place(x=20, y=20, width=450, relheight=1, height=-40)

tk.Label(filter_left, text="📞 手机号列表",
         font=('Arial', 13, 'bold'),
         bg='#f5f5f5', fg='#000000').pack(anchor='w', pady=(0,10), padx=10)

phone_text = scrolledtext.ScrolledText(filter_left, height=18,
                                       font=('Consolas', 11),
                                       bg='#ffffff', fg='#000000',
                                       insertbackground='black')
phone_text.pack(fill='both', expand=True, pady=(0,10), padx=10)

btn_group = tk.Frame(filter_left, bg='#f5f5f5')
btn_group.pack(fill='x', pady=10, padx=10)

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

country_group = tk.Frame(filter_left, bg='#f5f5f5')
country_group.pack(fill='x', pady=10, padx=10)

tk.Label(country_group, text="🌍 目标国家:",
         font=('Arial', 11),
         bg='#f5f5f5', fg='#000000').pack(side='left', padx=(0,10))

country_var = tk.StringVar(value="US")
tk.Radiobutton(country_group, text="🇺🇸 美国",
               variable=country_var, value="US",
               font=('Arial', 11),
               bg='#f5f5f5', fg='#000000',
               selectcolor='#f5f5f5').pack(side='left', padx=5)

tk.Radiobutton(country_group, text="🇨🇳 中国",
               variable=country_var, value="CN",
               font=('Arial', 11),
               bg='#f5f5f5', fg='#000000',
               selectcolor='#f5f5f5').pack(side='left', padx=5)

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
          height=2).pack(fill='x', pady=10, padx=10)

filter_right = tk.Frame(page_filter, bg='#f5f5f5', relief='solid', bd=1)
filter_right.place(x=490, y=20, relwidth=1, width=-510, relheight=1, height=-40)

tk.Label(filter_right, text="📝 运行日志",
         font=('Arial', 13, 'bold'),
         bg='#f5f5f5', fg='#000000').pack(anchor='w', pady=(0,10), padx=10)

log_text = scrolledtext.ScrolledText(filter_right, height=25,
                                     font=('Consolas', 10),
                                     bg='#ffffff', fg='#000000',
                                     insertbackground='black')
log_text.pack(fill='both', expand=True, padx=10, pady=(0,10))

# ==================== 账号管理页面 ====================
page_account = pages['account']

# 居中表单容器
acc_center = tk.Frame(page_account, bg='#f5f5f5', relief='solid', bd=2)
acc_center.place(relx=0.5, rely=0.5, anchor='center', width=600)

tk.Label(acc_center, text="📋 添加账号",
         font=('Arial', 16, 'bold'),
         bg='#f5f5f5', fg='#000000').pack(pady=(20,30))

detail_form = tk.Frame(acc_center, bg='#f5f5f5')
detail_form.pack(fill='x', padx=40)

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
             font=('Arial', 12, 'bold'),
             bg='#f5f5f5', fg='#000000').grid(row=i, column=0, sticky='w', pady=20, padx=(0,15))

    entry = tk.Entry(detail_form, textvariable=var,
                     width=30,
                     font=('Arial', 12),
                     bg='#ffffff', fg='#000000',
                     insertbackground='black',
                     relief='solid', bd=2)
    entry.grid(row=i, column=1, sticky='ew', pady=20)

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

    config['accounts'].append(acc)
    save_config()
    messagebox.showinfo("成功", "账号已保存")

    # 清空表单
    name_var.set("")
    api_id_var.set("")
    api_hash_var.set("")
    phone_var.set("")

tk.Button(detail_form, text="💾 保存账号",
          command=save_account,
          font=('Arial', 12, 'bold'),
          bg='#2196F3', fg='white',
          height=2).grid(row=len(fields), column=0, columnspan=2,
                        pady=30, sticky='ew')

tk.Label(detail_form, text="💡 获取API凭证: https://my.telegram.org",
         font=('Arial', 10),
         fg='blue', bg='#f5f5f5').grid(row=len(fields)+1, column=0, columnspan=2, sticky='w', pady=(10,20))

# ==================== 设置页面 ====================
page_settings = pages['settings']

settings_center = tk.Frame(page_settings, bg='#f5f5f5', relief='solid', bd=2)
settings_center.place(relx=0.5, rely=0.5, anchor='center', width=500)

tk.Label(settings_center, text="⚙️ 速率控制设置",
         font=('Arial', 15, 'bold'),
         bg='#f5f5f5', fg='#000000').pack(pady=(20,30))

req_var = tk.IntVar(value=config['rate_limit']['requests_per_account'])
min_var = tk.IntVar(value=config['rate_limit']['min_delay'])
max_var = tk.IntVar(value=config['rate_limit']['max_delay'])

settings_items = [
    ("单账号请求上限:", req_var, 10, 100),
    ("最小延迟(秒):", min_var, 1, 10),
    ("最大延迟(秒):", max_var, 5, 30)
]

for label_text, var, from_, to in settings_items:
    frame = tk.Frame(settings_center, bg='#f5f5f5')
    frame.pack(fill='x', pady=15, padx=40)

    tk.Label(frame, text=label_text,
             font=('Arial', 11),
             bg='#f5f5f5', fg='#000000', width=20, anchor='w').pack(side='left', padx=(0,10))

    tk.Spinbox(frame, from_=from_, to=to,
               textvariable=var,
               width=15,
               font=('Arial', 11),
               bg='#ffffff', fg='#000000').pack(side='left')

def save_settings():
    config['rate_limit']['requests_per_account'] = req_var.get()
    config['rate_limit']['min_delay'] = min_var.get()
    config['rate_limit']['max_delay'] = max_var.get()
    save_config()
    messagebox.showinfo("成功", "设置已保存")

tk.Button(settings_center, text="💾 保存设置",
          command=save_settings,
          font=('Arial', 12, 'bold'),
          bg='#FF9800', fg='white',
          height=2, width=25).pack(pady=(40,20))

# 初始化
switch_page('filter', btn_filter)
log_text.insert('end', "✅ GUI已启动\n")
log_text.insert('end', "💡 点击顶部按钮切换页面\n")

root.mainloop()
