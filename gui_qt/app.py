"""UI layer (PyQt6): main window. Holds the tab widget and shared
connection/log state. Tabs import controller only through this window,
never call VISA directly. Mirrors gui_tk/app.py's structure and behavior."""

import datetime

from PyQt6.QtGui import QColor, QTextCharFormat, QBrush
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QComboBox, QPushButton,
    QTabWidget, QTextEdit, QMessageBox,
)

from controller import ScopeError
from gui_qt.workspace_tab import WorkspaceTab
from gui_qt.tools_tab import ToolsTab

ERROR_HINTS = {
    "VI_ERROR_SYSTEM_ERROR": "ที่อยู่นี้ไม่ใช่ออสซิลโลสโคป (อาจเป็นพอร์ต COM ว่าง) ลองเลือกที่อยู่ที่ขึ้นต้นด้วย USB0::0x1AB1",
    "VI_ERROR_RSRC_NFOUND": "ไม่พบอุปกรณ์ที่ที่อยู่นี้ ตรวจสอบสาย USB แล้วกด Scan ใหม่",
    "VI_ERROR_TMO": "เครื่องไม่ตอบสนองภายในเวลาที่กำหนด ลองเพิ่ม timeout หรือรีสตาร์ทเครื่อง",
    "VI_ERROR_RSRC_BUSY": "อุปกรณ์ถูกใช้งานโดยโปรแกรมอื่นอยู่ ปิดโปรแกรมนั้นก่อน",
}

LOG_COLORS = {
    "info": "#dddddd",
    "ok": "#8ce99a",
    "error": "#ff6b6b",
}


class OscilloscopeApp(QMainWindow):
    """หน้าต่างหลักของโปรแกรม ติดต่อฮาร์ดแวร์ผ่าน ScopeController เท่านั้น"""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("Oscilloscope Controller (PyQt6)")
        self.resize(1100, 820)
        self.setMinimumSize(950, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._build_connection_panel(layout)
        self._build_tabs(layout)
        self._build_log_panel(layout)  

        self._set_tabs_enabled(False)

    # ---------- UI construction ----------

    def _build_connection_panel(self, parent_layout):
        group = QGroupBox("Connection")
        row = QHBoxLayout(group)

        row.addWidget(QLabel("VISA Address:"))

        self.address_box = QComboBox()
        self.address_box.setEditable(True)
        self.address_box.setMinimumWidth(320)
        row.addWidget(self.address_box)

        self.btn_scan = QPushButton("Scan")
        self.btn_scan.clicked.connect(self._on_scan)
        row.addWidget(self.btn_scan)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self._on_connect)
        row.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        row.addWidget(self.btn_disconnect)

        self.status_label = QLabel("● Not connected")
        self.status_label.setStyleSheet("color: #888888;")
        row.addWidget(self.status_label)

        row.addStretch()
        parent_layout.addWidget(group)

    def _build_tabs(self, parent_layout):
        self.tabs = QTabWidget()

        # 2 tab: Workspace (control+measure+trigger+console รวมกัน) และ Tools (screen capture)
        self.workspace_tab = WorkspaceTab(self.controller, self.log, self.run_safely)
        self.tools_tab = ToolsTab(self.controller, self.log, self.run_safely)

        self.tabs.addTab(self.workspace_tab, "Workspace")
        self.tabs.addTab(self.tools_tab, "Tools")

        parent_layout.addWidget(self.tabs, 1)

    def _build_log_panel(self, parent_layout):
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(70)  # ประมาณ 3 บรรทัด เท่ากับ Tkinter
        self.log_text.setStyleSheet(
            "background-color: #1e1e1e; color: #dddddd; "
            "font-family: Consolas, monospace; font-size: 9pt;"
        )
        layout.addWidget(self.log_text)

        parent_layout.addWidget(group)

        self.log("โปรแกรมเริ่มทำงาน", level="info")

    # ---------- Log ----------

    def log(self, message, level="info"):
        """เขียนข้อความลง log พร้อมเวลา level: 'info', 'ok', 'error'"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color = LOG_COLORS.get(level, LOG_COLORS["info"])

        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(QColor(color)))

        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.setCharFormat(fmt)
        cursor.insertText(f"[{timestamp}] {message}\n")

        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()

    # ---------- Connection status indicator ----------

    def _set_connection_indicator(self, connected):
        color = "#2ecc71" if connected else "#888888"
        text = "● Connected" if connected else "● Not connected"
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")

    # ---------- Helpers ----------

    def _friendly_error(self, exc):
        text = str(exc)
        for code, hint in ERROR_HINTS.items():
            if code in text:
                return hint
        return text

    def run_safely(self, action, success_message=None):
        """
        เรียก action ของ controller พร้อมดัก ScopeError มาแสดงผล
        ใช้ร่วมกันได้จากทุก tab ผ่าน self.controller และ logger ที่ tab ได้รับมา
        """
        try:
            result = action()
            if success_message:
                self.log(success_message, level="ok")
            return result
        except ScopeError as exc:
            message = self._friendly_error(exc)
            QMessageBox.critical(self, "เกิดข้อผิดพลาด", message)
            self.log(message, level="error")
            return None

    def _set_tabs_enabled(self, enabled):
        self.workspace_tab.set_enabled(enabled)
        self.tools_tab.set_enabled(enabled)

    # ---------- Event handlers ----------

    def _on_scan(self):
        resources = self.run_safely(self.controller.list_resources)
        if not resources:
            self.log("ไม่พบอุปกรณ์ VISA — ตรวจสอบสายและไดรเวอร์", level="error")
            return

        def priority(addr):
            if addr.startswith("USB"):
                return 0
            if addr.startswith("TCPIP"):
                return 1
            return 2

        resources = sorted(resources, key=priority)
        self.address_box.clear()
        self.address_box.addItems(resources)
        self.address_box.setCurrentIndex(0)

        instruments = [r for r in resources if not r.startswith("ASRL")]
        if instruments:
            self.log(f"พบเครื่องมือวัด {len(instruments)} เครื่อง", level="ok")
        else:
            self.log("พบแต่พอร์ตอนุกรม ยังไม่พบออสซิลโลสโคป", level="info")

    def _on_connect(self):
        address = self.address_box.currentText().strip()
        if not address:
            QMessageBox.warning(self, "Input Required", "Please enter a VISA address")
            return

        idn = self.run_safely(lambda: self.controller.connect(address))
        if idn:
            self.log(f"Connected: {idn}", level="ok")
            self._set_connection_indicator(True)
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self._set_tabs_enabled(True)

    def _on_disconnect(self):
        self.controller.disconnect()
        self.log("Disconnected", level="info")
        self._set_connection_indicator(False)
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self._set_tabs_enabled(False)

    def closeEvent(self, event):
        self.controller.disconnect()
        event.accept()
