"""UI layer: main window. Holds the notebook and shared connection/log state.
Tabs import controller only through this window, never call VISA directly."""

import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from controller import ScopeError
from gui_tk.workspace_tab import WorkspaceTab
from gui_tk.tools_tab import ToolsTab

ERROR_HINTS = {
    "VI_ERROR_SYSTEM_ERROR": "ที่อยู่นี้ไม่ใช่ออสซิลโลสโคป (อาจเป็นพอร์ต COM ว่าง) ลองเลือกที่อยู่ที่ขึ้นต้นด้วย USB0::0x1AB1",
    "VI_ERROR_RSRC_NFOUND": "ไม่พบอุปกรณ์ที่ที่อยู่นี้ ตรวจสอบสาย USB แล้วกด Scan ใหม่",
    "VI_ERROR_TMO": "เครื่องไม่ตอบสนองภายในเวลาที่กำหนด ลองเพิ่ม timeout หรือรีสตาร์ทเครื่อง",
    "VI_ERROR_RSRC_BUSY": "อุปกรณ์ถูกใช้งานโดยโปรแกรมอื่นอยู่ ปิดโปรแกรมนั้นก่อน",
}


class OscilloscopeApp:
    """หน้าต่างหลักของโปรแกรม ติดต่อฮาร์ดแวร์ผ่าน ScopeController เท่านั้น"""

    def __init__(self, root, controller):
        self.root = root
        self.controller = controller

        self.root.title("Oscilloscope Controller")
        self.root.geometry("1100x820")
        self.root.minsize(950, 700)

        self._build_connection_panel()
        self._build_log_panel()
        self._build_notebook()

        self._set_tabs_enabled(False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI construction ----------

    def _build_connection_panel(self):
        frame = ttk.LabelFrame(self.root, text="Connection", padding=10)
        frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(frame, text="VISA Address:").grid(row=0, column=0, sticky="w")

        self.address_var = tk.StringVar()
        self.address_box = ttk.Combobox(
            frame, textvariable=self.address_var, width=40
        )
        self.address_box.grid(row=0, column=1, padx=5)

        ttk.Button(frame, text="Scan", command=self._on_scan).grid(row=0, column=2, padx=2)
        self.btn_connect = ttk.Button(frame, text="Connect", command=self._on_connect)
        self.btn_connect.grid(row=0, column=3, padx=2)
        self.btn_disconnect = ttk.Button(
            frame, text="Disconnect", command=self._on_disconnect, state="disabled"
        )
        self.btn_disconnect.grid(row=0, column=4, padx=2)

        self.status_dot = tk.Canvas(frame, width=14, height=14, highlightthickness=0)
        self.status_dot.grid(row=0, column=5, padx=(15, 4))
        self._dot_id = self.status_dot.create_oval(2, 2, 12, 12, fill="#888888", outline="")

        self.status_label_var = tk.StringVar(value="Not connected")
        ttk.Label(frame, textvariable=self.status_label_var).grid(row=0, column=6, sticky="w")

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # 2 tab: Workspace (control+measure+trigger+console รวมกัน) และ Tools (screen capture)
        self.workspace_tab = WorkspaceTab(self.notebook, self.controller, self.log, self.run_safely)
        self.tools_tab = ToolsTab(self.notebook, self.controller, self.log, self.run_safely)

        self.notebook.add(self.workspace_tab, text="Workspace")
        self.notebook.add(self.tools_tab, text="Tools")

    def _build_log_panel(self):
        frame = ttk.LabelFrame(self.root, text="Log", padding=5)
        frame.pack(fill="x", side="bottom", padx=10, pady=(0, 10))

        self.log_text = tk.Text(
            frame, height=3, state="disabled",
            bg="#1e1e1e", fg="#dddddd", font=("Consolas", 9)
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.tag_config("error", foreground="#ff6b6b")
        self.log_text.tag_config("ok", foreground="#8ce99a")
        self.log_text.tag_config("info", foreground="#dddddd")

        self.log("โปรแกรมเริ่มทำงาน", level="info")

    # ---------- Log ----------

    def log(self, message, level="info"):
        """เขียนข้อความลง log พร้อมเวลา level: 'info', 'ok', 'error'"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ---------- Connection status indicator ----------

    def _set_connection_indicator(self, connected):
        color = "#2ecc71" if connected else "#888888"
        text = "Connected" if connected else "Not connected"
        self.status_dot.itemconfig(self._dot_id, fill=color)
        self.status_label_var.set(text)

    # ---------- Helpers ----------

    def _friendly_error(self, exc):
        text = str(exc)
        for code, hint in ERROR_HINTS.items():
            if code in text:
                return hint
        return text

    def run_safely(self, action, success_message=None):
        try:
            result = action()
            if success_message:
                self.log(success_message, level="ok")
            return result
        except ScopeError as exc:
            message = self._friendly_error(exc)
            messagebox.showerror("เกิดข้อผิดพลาด", message)
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
        self.address_box["values"] = resources
        self.address_var.set(resources[0])

        instruments = [r for r in resources if not r.startswith("ASRL")]
        if instruments:
            self.log(f"พบเครื่องมือวัด {len(instruments)} เครื่อง", level="ok")
        else:
            self.log("พบแต่พอร์ตอนุกรม ยังไม่พบออสซิลโลสโคป", level="info")

    def _on_connect(self):
        address = self.address_var.get().strip()
        if not address:
            messagebox.showwarning("Input Required", "Please enter a VISA address")
            return

        idn = self.run_safely(lambda: self.controller.connect(address))
        if idn:
            self.log(f"Connected: {idn}", level="ok")
            self._set_connection_indicator(True)
            self.btn_connect.configure(state="disabled")
            self.btn_disconnect.configure(state="normal")
            self._set_tabs_enabled(True)

    def _on_disconnect(self):
        self.controller.disconnect()
        self.log("Disconnected", level="info")
        self._set_connection_indicator(False)
        self.btn_connect.configure(state="normal")
        self.btn_disconnect.configure(state="disabled")
        self._set_tabs_enabled(False)

    def _on_close(self):
        self.controller.disconnect()
        self.root.destroy()