#!/usr/bin/env python3
"""
Telegram筛号工具 - PyQt5版本
"""
import sys
import json
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QTabWidget,
    QGroupBox, QFormLayout, QRadioButton, QButtonGroup,
    QFileDialog, QMessageBox, QSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

config_path = "config.json"

def load_config():
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"accounts": [], "rate_limit": {"requests_per_account": 30, "min_delay": 3, "max_delay": 8}}

def save_config(config):
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

class TelegramFilterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Telegram 筛号工具")
        self.setGeometry(100, 100, 1000, 650)

        # 主容器
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 顶部标题
        header = QLabel("🚀 Telegram 筛号工具")
        header.setFont(QFont('Arial', 18, QFont.Bold))
        header.setStyleSheet("background: #2196F3; color: white; padding: 15px;")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # 标签页
        tabs = QTabWidget()
        tabs.addTab(self.create_filter_tab(), "📱 筛选")
        tabs.addTab(self.create_account_tab(), "👤 账号管理")
        tabs.addTab(self.create_settings_tab(), "⚙️ 设置")
        main_layout.addWidget(tabs)

    def create_filter_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 左侧
        left = QWidget()
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("📞 手机号列表（每行一个）"))
        self.phone_text = QTextEdit()
        self.phone_text.setFont(QFont('Consolas', 10))
        left_layout.addWidget(self.phone_text)

        # 按钮
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("📂 从文件导入")
        import_btn.clicked.connect(self.import_phones)
        btn_layout.addWidget(import_btn)

        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.clicked.connect(lambda: self.phone_text.clear())
        btn_layout.addWidget(clear_btn)
        left_layout.addLayout(btn_layout)

        # 国家选择
        country_group = QGroupBox("🌍 目标国家")
        country_layout = QHBoxLayout()
        self.country_group = QButtonGroup()
        us_radio = QRadioButton("🇺🇸 美国")
        us_radio.setChecked(True)
        cn_radio = QRadioButton("🇨🇳 中国")
        self.country_group.addButton(us_radio, 0)
        self.country_group.addButton(cn_radio, 1)
        country_layout.addWidget(us_radio)
        country_layout.addWidget(cn_radio)
        country_group.setLayout(country_layout)
        left_layout.addWidget(country_group)

        # 开始按钮
        start_btn = QPushButton("🚀 开始筛选")
        start_btn.setFont(QFont('Arial', 13, QFont.Bold))
        start_btn.setStyleSheet("background: #4CAF50; color: white; padding: 10px;")
        start_btn.clicked.connect(self.start_filtering)
        left_layout.addWidget(start_btn)

        # 右侧日志
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("📝 运行日志"))
        self.log_text = QTextEdit()
        self.log_text.setFont(QFont('Consolas', 9))
        self.log_text.setReadOnly(True)
        right_layout.addWidget(self.log_text)

        layout.addWidget(left, 1)
        layout.addWidget(right, 1)

        self.log("✅ GUI已启动")
        return widget

    def create_account_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 左侧：账号列表
        left = QWidget()
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("📋 已添加的账号"))

        from PyQt5.QtWidgets import QListWidget
        self.account_list = QListWidget()
        self.account_list.setFont(QFont('Arial', 10))
        left_layout.addWidget(self.account_list)

        # 刷新账号列表
        self.refresh_account_list()

        layout.addWidget(left, 1)

        # 右侧：添加账号表单
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("➕ 添加新账号")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(title)

        # 表单
        form = QFormLayout()
        form.setSpacing(15)

        self.name_input = QLineEdit()
        self.name_input.setFont(QFont('Arial', 11))
        form.addRow("账号名称:", self.name_input)

        self.api_id_input = QLineEdit()
        self.api_id_input.setFont(QFont('Arial', 11))
        form.addRow("API ID:", self.api_id_input)

        self.api_hash_input = QLineEdit()
        self.api_hash_input.setFont(QFont('Arial', 11))
        form.addRow("API Hash:", self.api_hash_input)

        self.phone_input = QLineEdit()
        self.phone_input.setFont(QFont('Arial', 11))
        form.addRow("手机号:", self.phone_input)

        right_layout.addLayout(form)

        # 保存按钮
        save_btn = QPushButton("💾 保存账号")
        save_btn.setFont(QFont('Arial', 12, QFont.Bold))
        save_btn.setStyleSheet("background: #2196F3; color: white; padding: 10px;")
        save_btn.clicked.connect(self.save_account)
        right_layout.addWidget(save_btn)

        # 提示
        tip = QLabel("💡 获取API: https://my.telegram.org")
        tip.setStyleSheet("color: blue;")
        tip.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(tip)

        right_layout.addStretch()
        layout.addWidget(right, 1)
        return widget

    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(50, 50, 50, 50)

        title = QLabel("⚙️ 速率控制设置")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 表单
        form = QFormLayout()
        form.setSpacing(15)

        self.req_spin = QSpinBox()
        self.req_spin.setRange(10, 100)
        self.req_spin.setValue(self.config['rate_limit']['requests_per_account'])
        self.req_spin.setFont(QFont('Arial', 11))
        form.addRow("单账号请求上限:", self.req_spin)

        self.min_spin = QSpinBox()
        self.min_spin.setRange(1, 10)
        self.min_spin.setValue(self.config['rate_limit']['min_delay'])
        self.min_spin.setFont(QFont('Arial', 11))
        form.addRow("最小延迟(秒):", self.min_spin)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(5, 30)
        self.max_spin.setValue(self.config['rate_limit']['max_delay'])
        self.max_spin.setFont(QFont('Arial', 11))
        form.addRow("最大延迟(秒):", self.max_spin)

        layout.addLayout(form)

        # 保存按钮
        save_btn = QPushButton("💾 保存设置")
        save_btn.setFont(QFont('Arial', 12, QFont.Bold))
        save_btn.setStyleSheet("background: #FF9800; color: white; padding: 10px;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()
        return widget

    def import_phones(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "文本文件 (*.txt)")
        if filename:
            with open(filename, 'r') as f:
                self.phone_text.setPlainText(f.read())
            self.log(f"✅ 已导入 {filename}")

    def start_filtering(self):
        if not self.config.get('accounts'):
            QMessageBox.critical(self, "错误", "请先在'账号管理'中添加账号")
            return
        phones = [p.strip() for p in self.phone_text.toPlainText().split('\n') if p.strip()]
        if not phones:
            QMessageBox.critical(self, "错误", "请输入手机号")
            return
        self.log(f"🚀 准备筛选 {len(phones)} 个号码")
        self.log("💡 使用: python3 main_multi.py --file phones.txt")

    def save_account(self):
        name = self.name_input.text().strip()
        api_id = self.api_id_input.text().strip()
        api_hash = self.api_hash_input.text().strip()
        phone = self.phone_input.text().strip()

        if not all([name, api_id, api_hash, phone]):
            QMessageBox.critical(self, "错误", "请填写所有字段")
            return

        self.config['accounts'].append({
            "name": name,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone
        })
        save_config(self.config)
        QMessageBox.information(self, "成功", "账号已保存")

        self.name_input.clear()
        self.api_id_input.clear()
        self.api_hash_input.clear()
        self.phone_input.clear()

        # 刷新账号列表
        self.refresh_account_list()

    def refresh_account_list(self):
        """刷新账号列表显示"""
        self.account_list.clear()
        for i, acc in enumerate(self.config.get('accounts', [])):
            status = "✅ 正常"  # 默认状态
            item_text = f"{i+1}. {acc['name']} ({acc['phone']}) - {status}"
            self.account_list.addItem(item_text)

    def save_settings(self):
        self.config['rate_limit']['requests_per_account'] = self.req_spin.value()
        self.config['rate_limit']['min_delay'] = self.min_spin.value()
        self.config['rate_limit']['max_delay'] = self.max_spin.value()
        save_config(self.config)
        QMessageBox.information(self, "成功", "设置已保存")

    def log(self, msg):
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {msg}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = TelegramFilterGUI()
    gui.show()
    sys.exit(app.exec_())
