"""
简单的GUI测试
"""
import tkinter as tk
from tkinter import ttk

def test_gui():
    root = tk.Tk()
    root.title("测试窗口")
    root.geometry("600x400")
    
    # 添加标签
    label = ttk.Label(root, text="如果你能看到这段文字，说明GUI正常工作！", font=('Arial', 14))
    label.pack(pady=20)
    
    # 添加按钮
    button = ttk.Button(root, text="点击测试", command=lambda: label.config(text="按钮工作正常！"))
    button.pack(pady=10)
    
    # 添加文本框
    text = tk.Text(root, height=10, width=50)
    text.pack(pady=10)
    text.insert('1.0', "这是一个测试文本框\n可以看到这些文字吗？")
    
    root.mainloop()

if __name__ == '__main__':
    test_gui()
