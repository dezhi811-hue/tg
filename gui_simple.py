#!/usr/bin/env python3
"""
Telegram筛号工具 - GUI界面（简化版）
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import json
import os


class TelegramFilterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram 筛号工具 - 多账号版")
        self.root.geometry("1000x700")

        # 配置文件路径
        self.config_path = "config.json"
        self.config = self.load_config()

        # 立即创建界面
        self.create_widgets()

        # 强制刷新
        self.root.update_idletasks()
        self.root.update()

        # 加载账号
        self.load_accounts_to_list()

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        return {
            "accounts": [],
            "rate_limit": {
                "requests_per_account": 30,
                "min_delay": 3,
                "max_delay": 8
            },
            "target_country": "US"
        }

    def save_config(self):
        """保存配置文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        self.log("✅ 配置已保存")

    def create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)

        # 标题
        title = ttk.Label(main_frame, text="🚀 Telegram 筛号工具", font=('Arial', 16, 'bold'))
        title.pack(pady=10)

        # 创建Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=10)

        # 标签页1: 筛选
        self.filter_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.filter_frame, text='📱 筛选')
        self.create_filter_tab()

        # 标签页2: 账号管理
        self.account_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.account_frame, text='👤 账号管理')
        self.create_account_tab()

        # 标签页3: 设置
        self.settings_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.settings_frame, text='⚙️ 设置')
        self.create_settings_tab()

    def create_filter_tab(self):
        """创建筛选标签页"""
        # 使用PanedWindow分割左右
        paned = ttk.PanedWindow(self.filter_frame, orient='horizontal')
        paned.pack(fill='both', expand=True)

        # 左侧框架
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="📞 手机号列表（每行一个）:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)

        self.phone_text = scrolledtext.ScrolledText(left_frame, height=20, width=40)
        self.phone_text.pack(fill='both', expand=True, pady=5)

        # 按钮框架
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(btn_frame, text="📂 导入文件", command=self.import_phones).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="🗑️ 清空", command=lambda: self.phone_text.delete('1.0', 'end')).pack(side='left', padx=2)

        # 国家选择
        country_frame = ttk.Frame(left_frame)
        country_frame.pack(fill='x', pady=10)

        ttk.Label(country_frame, text="🌍 目标国家:").pack(side='left', padx=5)
        self.country_var = tk.StringVar(value="US")
        ttk.Radiobutton(country_frame, text="美国 🇺🇸", variable=self.country_var, value="US").pack(side='left', padx=5)
        ttk.Radiobutton(country_frame, text="中国 🇨🇳", variable=self.country_var, value="CN").pack(side='left', padx=5)

        # 开始按钮
        ttk.Button(left_frame, text="🚀 开始筛选", command=self.start_filtering).pack(fill='x', pady=5)

        # 右侧框架
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="📝 运行日志:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)

        self.log_text = scrolledtext.ScrolledText(right_frame, height=25, width=60)
        self.log_text.pack(fill='both', expand=True, pady=5)

        ttk.Button(right_frame, text="💾 导出结果", command=self.export_results).pack(fill='x', pady=5)

        # 初始日志
        self.log("✅ GUI已启动")
        self.log("💡 请先在'账号管理'中添加账号")

    def create_account_tab(self):
        """创建账号管理标签页"""
        # 左右分割
        paned = ttk.PanedWindow(self.account_frame, orient='horizontal')
        paned.pack(fill='both', expand=True)

        # 左侧
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="👥 已配置账号:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)

        self.account_listbox = tk.Listbox(left_frame, height=15)
        self.account_listbox.pack(fill='both', expand=True, pady=5)
        self.account_listbox.bind('<<ListboxSelect>>', self.on_account_select)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(btn_frame, text="➕ 添加", command=self.add_account).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="✏️ 编辑", command=self.edit_account).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="🗑️ 删除", command=self.delete_account).pack(side='left', padx=2)

        # 右侧
        right_frame = ttk.LabelFrame(paned, text="📋 账号详情", padding=10)
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="账号名称:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        self.acc_name_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.acc_name_var, width=30).grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text="API ID:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        self.acc_api_id_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.acc_api_id_var, width=30).grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text="API Hash:").grid(row=2, column=0, sticky='w', pady=5, padx=5)
        self.acc_api_hash_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.acc_api_hash_var, width=30).grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text="手机号:").grid(row=3, column=0, sticky='w', pady=5, padx=5)
        self.acc_phone_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.acc_phone_var, width=30).grid(row=3, column=1, pady=5, padx=5)

        ttk.Button(right_frame, text="💾 保存账号", command=self.save_account).grid(row=4, column=0, columnspan=2, pady=20)

        help_text = """
💡 如何获取API凭证：
1. 访问 https://my.telegram.org
2. 登录你的Telegram账号
3. 点击 "API development tools"
4. 创建应用，获取 api_id 和 api_hash
        """
        ttk.Label(right_frame, text=help_text, justify='left', foreground='gray').grid(row=5, column=0, columnspan=2, sticky='w')

    def create_settings_tab(self):
        """创建设置标签页"""
        frame = ttk.LabelFrame(self.settings_frame, text="⚙️ 速率控制设置", padding=20)
        frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(frame, text="单账号连续请求上限:").grid(row=0, column=0, sticky='w', pady=10)
        self.req_per_acc_var = tk.IntVar(value=self.config['rate_limit']['requests_per_account'])
        ttk.Spinbox(frame, from_=10, to=100, textvariable=self.req_per_acc_var, width=10).grid(row=0, column=1, sticky='w', pady=10)
        ttk.Label(frame, text="次（建议20-50）").grid(row=0, column=2, sticky='w', pady=10)

        ttk.Label(frame, text="最小延迟:").grid(row=1, column=0, sticky='w', pady=10)
        self.min_delay_var = tk.IntVar(value=self.config['rate_limit']['min_delay'])
        ttk.Spinbox(frame, from_=1, to=10, textvariable=self.min_delay_var, width=10).grid(row=1, column=1, sticky='w', pady=10)
        ttk.Label(frame, text="秒（建议3-5）").grid(row=1, column=2, sticky='w', pady=10)

        ttk.Label(frame, text="最大延迟:").grid(row=2, column=0, sticky='w', pady=10)
        self.max_delay_var = tk.IntVar(value=self.config['rate_limit']['max_delay'])
        ttk.Spinbox(frame, from_=5, to=30, textvariable=self.max_delay_var, width=10).grid(row=2, column=1, sticky='w', pady=10)
        ttk.Label(frame, text="秒（建议8-15）").grid(row=2, column=2, sticky='w', pady=10)

        ttk.Button(frame, text="💾 保存设置", command=self.save_settings).grid(row=3, column=0, columnspan=3, pady=20)

    def load_accounts_to_list(self):
        """加载账号到列表"""
        self.account_listbox.delete(0, 'end')
        for acc in self.config.get('accounts', []):
            self.account_listbox.insert('end', f"{acc['name']} ({acc['phone']})")

    def on_account_select(self, event):
        """选择账号"""
        selection = self.account_listbox.curselection()
        if selection:
            idx = selection[0]
            acc = self.config['accounts'][idx]
            self.acc_name_var.set(acc['name'])
            self.acc_api_id_var.set(acc['api_id'])
            self.acc_api_hash_var.set(acc['api_hash'])
            self.acc_phone_var.set(acc['phone'])

    def add_account(self):
        """添加账号"""
        self.acc_name_var.set("")
        self.acc_api_id_var.set("")
        self.acc_api_hash_var.set("")
        self.acc_phone_var.set("")
        self.log("➕ 准备添加新账号")

    def edit_account(self):
        """编辑账号"""
        selection = self.account_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要编辑的账号")

    def delete_account(self):
        """删除账号"""
        selection = self.account_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的账号")
            return

        if messagebox.askyesno("确认", "确定要删除这个账号吗？"):
            idx = selection[0]
            del self.config['accounts'][idx]
            self.save_config()
            self.load_accounts_to_list()

    def save_account(self):
        """保存账号"""
        name = self.acc_name_var.get().strip()
        api_id = self.acc_api_id_var.get().strip()
        api_hash = self.acc_api_hash_var.get().strip()
        phone = self.acc_phone_var.get().strip()

        if not all([name, api_id, api_hash, phone]):
            messagebox.showerror("错误", "请填写所有字段")
            return

        account = {
            "name": name,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone
        }

        selection = self.account_listbox.curselection()
        if selection:
            idx = selection[0]
            self.config['accounts'][idx] = account
        else:
            self.config['accounts'].append(account)

        self.save_config()
        self.load_accounts_to_list()
        messagebox.showinfo("成功", "账号已保存")

    def save_settings(self):
        """保存设置"""
        self.config['rate_limit']['requests_per_account'] = self.req_per_acc_var.get()
        self.config['rate_limit']['min_delay'] = self.min_delay_var.get()
        self.config['rate_limit']['max_delay'] = self.max_delay_var.get()
        self.save_config()
        messagebox.showinfo("成功", "设置已保存")

    def import_phones(self):
        """导入号码"""
        filename = filedialog.askopenfilename(
            title="选择号码文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filename:
            with open(filename, 'r', encoding='utf-8') as f:
                phones = f.read()
            self.phone_text.delete('1.0', 'end')
            self.phone_text.insert('1.0', phones)
            self.log(f"✅ 已导入 {filename}")

    def log(self, message):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{timestamp}] {message}\n")
        self.log_text.see('end')
        self.root.update()

    def start_filtering(self):
        """开始筛选"""
        if not self.config.get('accounts'):
            messagebox.showerror("错误", "请先添加至少一个账号")
            return

        phones_text = self.phone_text.get('1.0', 'end').strip()
        if not phones_text:
            messagebox.showerror("错误", "请输入要筛选的手机号")
            return

        phones = [p.strip() for p in phones_text.split('\n') if p.strip()]
        self.log(f"🚀 准备筛选 {len(phones)} 个号码...")
        self.log("💡 实际筛选功能请使用命令行版本：")
        self.log("   python main_multi.py --file phones.txt --country US")

    def export_results(self):
        """导出结果"""
        filename = filedialog.asksaveasfilename(
            title="保存结果",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")]
        )
        if filename:
            self.log(f"💾 结果将导出到 {filename}")


def main():
    root = tk.Tk()
    app = TelegramFilterGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
