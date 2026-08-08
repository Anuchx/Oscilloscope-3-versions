"""Tools tab (PyQt6): screen capture. Only calls controller.capture_screen()."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QFileDialog,
)


class ToolsTab(QWidget):
    """จับภาพหน้าจอจากเครื่องและบันทึกเป็นไฟล์"""

    def __init__(self, controller, logger, run_safely, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.log = logger
        self.run_safely = run_safely

        self._last_image_bytes = None

        layout = QVBoxLayout(self)
        self._build_capture_panel(layout)

    # ---------- UI construction ----------

    def _build_capture_panel(self, parent_layout):
        group = QGroupBox("Screen Capture")
        layout = QVBoxLayout(group)

        toolbar = QHBoxLayout()
        self.btn_capture = QPushButton("Capture")
        self.btn_capture.clicked.connect(self._on_capture)
        toolbar.addWidget(self.btn_capture)

        self.btn_save = QPushButton("Save PNG")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._on_save)
        toolbar.addWidget(self.btn_save)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.image_label = QLabel("ยังไม่มีภาพ — กด Capture")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #888888;")
        self.image_label.setMinimumHeight(300)
        layout.addWidget(self.image_label, 1)

        parent_layout.addWidget(group)

    # ---------- Enable/disable ----------

    def set_enabled(self, enabled):
        self.btn_capture.setEnabled(enabled)
        if not enabled:
            self.btn_save.setEnabled(False)

    # ---------- Event handlers ----------

    def _on_capture(self):
        data = self.run_safely(self.controller.capture_screen, "จับภาพหน้าจอสำเร็จ")
        if not data:
            return

        self._last_image_bytes = data
        self.btn_save.setEnabled(True)

        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            scaled = pixmap.scaled(
                800, 500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText(f"ได้ข้อมูลภาพ {len(data)} bytes (แสดงภาพไม่สำเร็จ)")
            self.log("แสดงภาพไม่สำเร็จ — ข้อมูลอาจไม่ใช่รูปแบบภาพที่รองรับ", level="error")

    def _on_save(self):
        if not self._last_image_bytes:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save PNG", "scope_screen.png", "PNG files (*.png)"
        )
        if not path:
            return

        try:
            with open(path, "wb") as f:
                f.write(self._last_image_bytes)
            self.log(f"บันทึกภาพแล้ว: {path}", level="ok")
        except OSError as exc:
            self.log(f"บันทึกไฟล์ไม่สำเร็จ: {exc}", level="error")