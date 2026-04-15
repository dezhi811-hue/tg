#!/usr/bin/env python3
"""
测试账号管理页面显示
"""
import tkinter as tk

root = tk.Tk()
root.title("测试账号管理")
root.geometry("800x600")

# 左侧
left = tk.Frame(root, bg='lightblue', width=300)
left.pack(side='left', fill='both', padx=10, pady=10)
left.pack_propagate(False)

tk.Label(left, text="左侧区域", font=('Arial', 16, 'bold'), bg='lightblue').pack(pady=20)

# 右侧
right = tk.Frame(root, bg='lightgreen')
right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

tk.Label(right, text="右侧区域 - 账号详情", font=('Arial', 16, 'bold'), bg='lightgreen').pack(pady=20)

# 表单
form = tk.Frame(right, bg='lightyellow')
form.pack(fill='both', expand=True, padx=20, pady=20)

tk.Label(form, text="账号名称:", font=('Arial', 12), bg='lightyellow').grid(row=0, column=0, sticky='w', pady=10)
tk.Entry(form, width=30, font=('Arial', 12)).grid(row=0, column=1, pady=10)

tk.Label(form, text="API ID:", font=('Arial', 12), bg='lightyellow').grid(row=1, column=0, sticky='w', pady=10)
tk.Entry(form, width=30, font=('Arial', 12)).grid(row=1, column=1, pady=10)

tk.Label(form, text="API Hash:", font=('Arial', 12), bg='lightyellow').grid(row=2, column=0, sticky='w', pady=10)
tk.Entry(form, width=30, font=('Arial', 12)).grid(row=2, column=1, pady=10)

tk.Label(form, text="手机号:", font=('Arial', 12), bg='lightyellow').grid(row=3, column=0, sticky='w', pady=10)
tk.Entry(form, width=30, font=('Arial', 12)).grid(row=3, column=1, pady=10)

tk.Button(form, text="保存账号", font=('Arial', 12, 'bold'), bg='blue', fg='white', height=2).grid(row=4, column=0, columnspan=2, pady=20, sticky='ew')

print("测试窗口已打开")
print("你应该能看到：")
print("- 左侧蓝色区域")
print("- 右侧绿色区域")
print("- 黄色表单区域，里面有4个输入框和1个按钮")

root.mainloop()
