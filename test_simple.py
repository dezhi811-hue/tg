#!/usr/bin/env python3
"""
超级简化版GUI - 测试显示
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import os

root = tk.Tk()
root.title("Telegram 筛号工具")
root.geometry("800x600")

# 强制显示
root.lift()
root.attributes('-topmost', True)
root.after_idle(root.attributes, '-topmost', False)

# 创建一个大标签测试
label = tk.Label(root, text="如果你能看到这行大字，说明显示正常！",
                 font=('Arial', 20, 'bold'), fg='red', bg='yellow')
label.pack(pady=20, fill='x')

# 创建按钮
button = tk.Button(root, text="点击测试", font=('Arial', 14),
                   command=lambda: messagebox.showinfo("测试", "按钮工作正常！"))
button.pack(pady=10)

# 创建文本框
text = tk.Text(root, height=10, width=60, font=('Arial', 12))
text.pack(pady=10, padx=20, fill='both', expand=True)
text.insert('1.0', "这是测试文本框\n\n如果你能看到这些文字，说明GUI可以正常工作！\n\n请告诉我你能看到什么。")

# 强制更新
root.update_idletasks()
root.update()

print("GUI已启动，窗口应该显示内容了")

root.mainloop()
