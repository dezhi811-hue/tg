#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Telegram 筛号工具")
root.geometry("900x600")

# 大标题
tk.Label(root, text="🚀 Telegram 筛号工具",
         font=('Arial', 18, 'bold'), bg='lightblue',
         pady=15).pack(fill='x')

# 创建标签页 - 使用最简单的方式
notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True, padx=10, pady=10)

# 标签页1
tab1 = tk.Frame(notebook, bg='white')
notebook.add(tab1, text='📱 筛选')
tk.Label(tab1, text="这是筛选页面", font=('Arial', 16)).pack(pady=50)

# 标签页2
tab2 = tk.Frame(notebook, bg='white')
notebook.add(tab2, text='👤 账号管理')
tk.Label(tab2, text="这是账号管理页面", font=('Arial', 16)).pack(pady=50)

# 标签页3
tab3 = tk.Frame(notebook, bg='white')
notebook.add(tab3, text='⚙️ 设置')
tk.Label(tab3, text="这是设置页面", font=('Arial', 16)).pack(pady=50)

print("GUI已创建，应该能看到3个标签页了")
root.mainloop()
