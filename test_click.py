#!/usr/bin/env python3
"""
测试按钮点击是否工作
"""
import tkinter as tk

root = tk.Tk()
root.title('按钮点击测试')
root.geometry('500x400')

click_count = [0]

def on_button_click():
    click_count[0] += 1
    result_label.config(text=f'✅ 按钮已点击 {click_count[0]} 次')
    print(f'按钮被点击了 {click_count[0]} 次')

# 标题
tk.Label(root, text='测试按钮是否可以点击',
         font=('Arial', 16, 'bold')).pack(pady=20)

# 测试按钮
test_btn = tk.Button(root, text='点击这个按钮',
                     font=('Arial', 14, 'bold'),
                     bg='#4CAF50', fg='white',
                     padx=30, pady=15,
                     command=on_button_click)
test_btn.pack(pady=20)

# 结果显示
result_label = tk.Label(root, text='还没有点击',
                        font=('Arial', 12), fg='blue')
result_label.pack(pady=20)

# 说明
tk.Label(root, text='如果点击后上面的数字增加，说明按钮工作正常',
         font=('Arial', 10), fg='gray').pack(pady=10)

print('测试窗口已打开，请点击按钮测试')
root.mainloop()
