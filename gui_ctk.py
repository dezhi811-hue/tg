#!/usr/bin/env python3
"""
Telegram筛号工具 - CustomTkinter版本（完美支持深色模式）
"""
import customtkinter as ctk
from tkinter import filedialog, messagebox
import json
import os

ctk.set_appearance_mode("light")  # 强制浅色模式
ctk.set_default_color_theme("blue")

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

root = ctk.CTk()
root.title("Telegram 筛号工具")
root.geometry("1000x650")

# 顶部标题
header = ctk.CTkFrame(root, height=60, fg_color="#2196F3")
header.pack(fill='x')
header.pack_propagate(False)
ctk.CTkLabel(header, text="🚀 Telegram 筛号工具", font=('Arial', 18, 'bold'),
             text_color='white').pack(pady=15)

# 导航栏
nav = ctk.CTkFrame(root, height=45, fg_color="#1976D2")
nav.pack(fill='x')
nav.pack_propagate(False)

# 内容区
content = ctk.CTkFrame(root)
content.pack(fill='both', expand=True)

# 三个页面
pages = {
    'filter': ctk.CTkFrame(content),
    'account': ctk.CTkFrame(content),
    'settings': ctk.CTkFrame(content)
}

current = {'page': None, 'btn': None}

def show(page_name, btn):
    if current['page']:
        current['page'].pack_forget()
    pages[page_name].pack(fill='both', expand=True)
    current['page'] = pages[page_name]

    if current['btn']:
        current['btn'].configure(fg_color="#1976D2")
    btn.configure(fg_color="#0D47A1")
    current['btn'] = btn

def nav_btn(text, page):
    b = ctk.CTkButton(nav, text=text, font=('Arial', 11, 'bold'),
                      fg_color="#1976D2", hover_color="#0D47A1",
                      command=lambda: show(page, b))
    b.pack(side='left', padx=2, pady=5)
    return b

b1 = nav_btn('📱 筛选', 'filter')
b2 = nav_btn('👤 账号管理', 'account')
b3 = nav_btn('⚙️ 设置', 'settings')

# ========== 筛选页面 ==========
pf = pages['filter']

left = ctk.CTkFrame(pf, width=400)
left.pack(side='left', fill='both', padx=10, pady=10)
left.pack_propagate(False)

ctk.CTkLabel(left, text="📞 手机号列表", font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)
phone_text = ctk.CTkTextbox(left, height=300, font=('Consolas', 10))
phone_text.pack(fill='both', expand=True, pady=5)

bf = ctk.CTkFrame(left)
bf.pack(fill='x', pady=5)

def imp():
    f = filedialog.askopenfilename(filetypes=[("文本", "*.txt")])
    if f:
        with open(f) as file:
            phone_text.delete('1.0', 'end')
            phone_text.insert('1.0', file.read())
        log_text.insert('end', f"✅ 已导入 {f}\n")

ctk.CTkButton(bf, text="📂 导入", command=imp, width=80).pack(side='left', padx=3)
ctk.CTkButton(bf, text="🗑️ 清空", command=lambda: phone_text.delete('1.0', 'end'),
              width=80, fg_color="#f44336").pack(side='left', padx=3)

cf = ctk.CTkFrame(left)
cf.pack(fill='x', pady=5)
ctk.CTkLabel(cf, text="🌍 国家:").pack(side='left', padx=5)
country = ctk.StringVar(value="US")
ctk.CTkRadioButton(cf, text="🇺🇸 美国", variable=country, value="US").pack(side='left', padx=5)
ctk.CTkRadioButton(cf, text="🇨🇳 中国", variable=country, value="CN").pack(side='left', padx=5)

def start():
    if not config.get('accounts'):
        messagebox.showerror("错误", "请先添加账号")
        return
    phones = [p.strip() for p in phone_text.get('1.0', 'end').split('\n') if p.strip()]
    if not phones:
        messagebox.showerror("错误", "请输入手机号")
        return
    log_text.insert('end', f"🚀 准备筛选 {len(phones)} 个号码\n")
    log_text.insert('end', "💡 使用: python3 main_multi.py --file phones.txt\n")

ctk.CTkButton(left, text="🚀 开始筛选", command=start, font=('Arial', 13, 'bold'),
              fg_color="#4CAF50", height=40).pack(fill='x', pady=10)

right = ctk.CTkFrame(pf)
right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

ctk.CTkLabel(right, text="📝 运行日志", font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)
log_text = ctk.CTkTextbox(right, height=400, font=('Consolas', 9))
log_text.pack(fill='both', expand=True)

# ========== 账号管理页面 ==========
pa = pages['account']

form_frame = ctk.CTkFrame(pa)
form_frame.pack(expand=True, padx=50, pady=50)

ctk.CTkLabel(form_frame, text="📋 添加账号", font=('Arial', 16, 'bold')).pack(pady=20)

name_var = ctk.StringVar()
api_id_var = ctk.StringVar()
api_hash_var = ctk.StringVar()
phone_var = ctk.StringVar()

fields = [
    ("账号名称:", name_var),
    ("API ID:", api_id_var),
    ("API Hash:", api_hash_var),
    ("手机号:", phone_var)
]

for label, var in fields:
    f = ctk.CTkFrame(form_frame)
    f.pack(fill='x', pady=10)
    ctk.CTkLabel(f, text=label, font=('Arial', 11, 'bold'), width=100).pack(side='left', padx=10)
    ctk.CTkEntry(f, textvariable=var, width=300, font=('Arial', 11)).pack(side='left')

def save_acc():
    if not all([name_var.get(), api_id_var.get(), api_hash_var.get(), phone_var.get()]):
        messagebox.showerror("错误", "请填写所有字段")
        return

    config['accounts'].append({
        "name": name_var.get(),
        "api_id": api_id_var.get(),
        "api_hash": api_hash_var.get(),
        "phone": phone_var.get()
    })
    save_config()
    messagebox.showinfo("成功", "账号已保存")

    name_var.set("")
    api_id_var.set("")
    api_hash_var.set("")
    phone_var.set("")

ctk.CTkButton(form_frame, text="💾 保存账号", command=save_acc,
              font=('Arial', 12, 'bold'), height=40, width=200).pack(pady=25)

ctk.CTkLabel(form_frame, text="💡 获取API: https://my.telegram.org",
             font=('Arial', 9), text_color='blue').pack()

# ========== 设置页面 ==========
ps = pages['settings']

settings_frame = ctk.CTkFrame(ps)
settings_frame.pack(expand=True, padx=50, pady=50)

ctk.CTkLabel(settings_frame, text="⚙️ 速率控制设置", font=('Arial', 16, 'bold')).pack(pady=20)

req_var = ctk.IntVar(value=config['rate_limit']['requests_per_account'])
min_var = ctk.IntVar(value=config['rate_limit']['min_delay'])
max_var = ctk.IntVar(value=config['rate_limit']['max_delay'])

items = [
    ("单账号请求上限:", req_var, 10, 100),
    ("最小延迟(秒):", min_var, 1, 10),
    ("最大延迟(秒):", max_var, 5, 30)
]

for label, var, from_, to in items:
    f = ctk.CTkFrame(settings_frame)
    f.pack(pady=12)
    ctk.CTkLabel(f, text=label, font=('Arial', 11), width=150).pack(side='left', padx=10)
    ctk.CTkEntry(f, textvariable=var, width=100, font=('Arial', 11)).pack(side='left')

def save_set():
    config['rate_limit']['requests_per_account'] = req_var.get()
    config['rate_limit']['min_delay'] = min_var.get()
    config['rate_limit']['max_delay'] = max_var.get()
    save_config()
    messagebox.showinfo("成功", "设置已保存")

ctk.CTkButton(settings_frame, text="💾 保存设置", command=save_set,
              font=('Arial', 12, 'bold'), height=40, width=200,
              fg_color="#FF9800").pack(pady=30)

# 初始化
show('filter', b1)
log_text.insert('end', "✅ GUI已启动\n")

root.mainloop()
