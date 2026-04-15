#!/usr/bin/env python3
"""
Telegram筛号工具 - Canvas版本（解决深色模式问题）
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

root = tk.Tk()
root.title("Telegram 筛号工具")
root.geometry("1000x650")
root.configure(bg='#e8e8e8')

# 顶部标题
header = tk.Frame(root, bg='#2196F3', height=60)
header.pack(fill='x')
header.pack_propagate(False)
tk.Label(header, text="🚀 Telegram 筛号工具", font=('Arial', 18, 'bold'),
         bg='#2196F3', fg='white').pack(pady=15)

# 导航栏
nav = tk.Frame(root, bg='#1976D2', height=45)
nav.pack(fill='x')
nav.pack_propagate(False)

# 内容区 - 使用Canvas
content = tk.Canvas(root, bg='#e8e8e8', highlightthickness=0)
content.pack(fill='both', expand=True)

# 三个页面容器
pages = {
    'filter': tk.Frame(content, bg='#e8e8e8'),
    'account': tk.Frame(content, bg='#e8e8e8'),
    'settings': tk.Frame(content, bg='#e8e8e8')
}

# 将Frame放到Canvas上
for page in pages.values():
    content.create_window(0, 0, window=page, anchor='nw', width=1000, height=600)

current = {'page': None, 'btn': None}

def show(page_name, btn):
    if current['page']:
        pages[current['page']].place_forget()

    pages[page_name].place(x=0, y=0, relwidth=1, relheight=1)
    current['page'] = page_name

    if current['btn']:
        current['btn'].config(bg='#1976D2')
    btn.config(bg='#0D47A1')
    current['btn'] = btn

def nav_btn(text, page):
    b = tk.Button(nav, text=text, font=('Arial', 11, 'bold'),
                  bg='#1976D2', fg='white', bd=0, padx=20, pady=10,
                  command=lambda: show(page, b))
    b.pack(side='left', padx=2)
    return b

b1 = nav_btn('📱 筛选', 'filter')
b2 = nav_btn('👤 账号管理', 'account')
b3 = nav_btn('⚙️ 设置', 'settings')

# ========== 筛选页面 ==========
pf = pages['filter']

left = tk.Frame(pf, bg='white', width=400)
left.pack(side='left', fill='both', padx=10, pady=10)
left.pack_propagate(False)

tk.Label(left, text="📞 手机号列表", font=('Arial', 12, 'bold'), bg='white').pack(anchor='w', pady=5)
phone_text = scrolledtext.ScrolledText(left, height=15, font=('Consolas', 10))
phone_text.pack(fill='both', expand=True, pady=5)

bf = tk.Frame(left, bg='white')
bf.pack(fill='x', pady=5)

def imp():
    f = filedialog.askopenfilename(filetypes=[("文本", "*.txt")])
    if f:
        with open(f) as file:
            phone_text.delete('1.0', 'end')
            phone_text.insert('1.0', file.read())
        log_text.insert('end', f"✅ 已导入 {f}\n")
        log_text.see('end')

tk.Button(bf, text="📂 导入", command=imp, bg='#2196F3', fg='white', padx=10).pack(side='left', padx=3)
tk.Button(bf, text="🗑️ 清空", command=lambda: phone_text.delete('1.0', 'end'),
          bg='#f44336', fg='white', padx=10).pack(side='left', padx=3)

cf = tk.Frame(left, bg='white')
cf.pack(fill='x', pady=5)
tk.Label(cf, text="🌍 国家:", bg='white').pack(side='left', padx=5)
country = tk.StringVar(value="US")
tk.Radiobutton(cf, text="🇺🇸 美国", variable=country, value="US", bg='white').pack(side='left')
tk.Radiobutton(cf, text="🇨🇳 中国", variable=country, value="CN", bg='white').pack(side='left')

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
    log_text.see('end')

tk.Button(left, text="🚀 开始筛选", command=start, font=('Arial', 13, 'bold'),
          bg='#4CAF50', fg='white', height=2).pack(fill='x', pady=10)

right = tk.Frame(pf, bg='white')
right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

tk.Label(right, text="📝 运行日志", font=('Arial', 12, 'bold'), bg='white').pack(anchor='w', pady=5)
log_text = scrolledtext.ScrolledText(right, height=20, font=('Consolas', 9))
log_text.pack(fill='both', expand=True)

# ========== 账号管理页面 ==========
pa = pages['account']

# 创建一个大的白色Canvas作为背景
acc_canvas = tk.Canvas(pa, bg='white', highlightthickness=0)
acc_canvas.pack(fill='both', expand=True, padx=50, pady=50)

# 在Canvas上绘制表单
acc_canvas.create_text(500, 50, text="📋 添加账号", font=('Arial', 16, 'bold'), fill='black')

# 创建输入框 - 直接放在Canvas上
name_var = tk.StringVar()
api_id_var = tk.StringVar()
api_hash_var = tk.StringVar()
phone_var = tk.StringVar()

y_start = 100
labels = ["账号名称:", "API ID:", "API Hash:", "手机号:"]
vars_list = [name_var, api_id_var, api_hash_var, phone_var]
entries = []

for i, (label, var) in enumerate(zip(labels, vars_list)):
    y = y_start + i * 60
    acc_canvas.create_text(300, y, text=label, font=('Arial', 12, 'bold'), fill='#000000', anchor='e')
    entry = tk.Entry(pa, textvariable=var, width=30, font=('Arial', 12),
                     bg='#ffffff', fg='#000000', insertbackground='black',
                     relief='solid', bd=2)
    acc_canvas.create_window(320, y, window=entry, anchor='w')
    entries.append(entry)

def save_acc():
    if not all([v.get() for v in vars_list]):
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

    for v in vars_list:
        v.set("")

save_btn = tk.Button(pa, text="💾 保存账号", command=save_acc,
                     font=('Arial', 12, 'bold'), bg='#2196F3', fg='white', height=2, width=20)
acc_canvas.create_window(500, y_start + 280, window=save_btn)

acc_canvas.create_text(500, y_start + 340, text="💡 获取API: https://my.telegram.org",
                       font=('Arial', 9), fill='blue')

# ========== 设置页面 ==========
ps = pages['settings']

set_canvas = tk.Canvas(ps, bg='white', highlightthickness=0)
set_canvas.pack(fill='both', expand=True, padx=50, pady=50)

set_canvas.create_text(500, 50, text="⚙️ 速率控制设置", font=('Arial', 16, 'bold'), fill='black')

req_var = tk.IntVar(value=config['rate_limit']['requests_per_account'])
min_var = tk.IntVar(value=config['rate_limit']['min_delay'])
max_var = tk.IntVar(value=config['rate_limit']['max_delay'])

items = [
    ("单账号请求上限:", req_var, 10, 100),
    ("最小延迟(秒):", min_var, 1, 10),
    ("最大延迟(秒):", max_var, 5, 30)
]

y_start = 120
for i, (label, var, from_, to) in enumerate(items):
    y = y_start + i * 60
    set_canvas.create_text(350, y, text=label, font=('Arial', 12), fill='#000000', anchor='e')
    spinbox = tk.Spinbox(ps, from_=from_, to=to, textvariable=var, width=12, font=('Arial', 12),
                         bg='#ffffff', fg='#000000', buttonbackground='#e0e0e0')
    set_canvas.create_window(370, y, window=spinbox, anchor='w')

def save_set():
    config['rate_limit']['requests_per_account'] = req_var.get()
    config['rate_limit']['min_delay'] = min_var.get()
    config['rate_limit']['max_delay'] = max_var.get()
    save_config()
    messagebox.showinfo("成功", "设置已保存")

set_save_btn = tk.Button(ps, text="💾 保存设置", command=save_set,
                         font=('Arial', 12, 'bold'), bg='#FF9800', fg='white', height=2, width=20)
set_canvas.create_window(500, y_start + 200, window=set_save_btn)

# 初始化
show('filter', b1)
log_text.insert('end', "✅ GUI已启动\n")

root.mainloop()
