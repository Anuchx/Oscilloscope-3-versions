"""Workspace tab (PyQt6): all frequently-adjusted controls on the left,
waveform + measurement + SCPI console on the right. Mirrors
gui_tk/workspace_tab.py feature-for-feature. Only calls controller methods,
config_manager, and the logger/run_safely callbacks passed in."""

import csv

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QComboBox, QCheckBox, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QFileDialog,
)

from config_manager import save_config, load_config

CHANNELS = ["1", "2", "3", "4"]
VOLT_SCALES = ["0.01", "0.05", "0.1", "0.5", "1", "2", "5"]
TIME_SCALES = ["1e-6", "1e-5", "1e-4", "1e-3", "1e-2", "0.1", "1"]
COUPLINGS = ["DC", "AC", "GND"]
SLOPES = ["POSitive", "NEGative"]
TRIGGER_MODES = ["AUTO", "NORMal", "SINGle"]
REFRESH_INTERVALS = ["1", "2", "5", "10"]  # วินาที

MEASUREMENT_ITEMS = [
    ("Vpp", "VPP"),
    ("Vmax", "VMAX"),
    ("Vmin", "VMIN"),
    ("Vrms", "VRMS"),
    ("Frequency", "FREQuency"),
    ("Period", "PERiod"),
]

CHANNEL_COLORS = {
    1: "#ffff00",  # เหลือง
    2: "#00bfff",  # ฟ้า
    3: "#ff69b4",  # ชมพู
    4: "#7cfc00",  # เขียว
}

# preset console: (label ที่แสดง, คำสั่งจริง)
CONSOLE_PRESETS = [
    ("*IDN? (ข้อมูลเครื่อง)", "*IDN?"),
    ("*RST (รีเซ็ตเครื่อง)", "*RST"),
    (":RUN", ":RUN"),
    (":STOP", ":STOP"),
    (":AUTOSet", ":AUTOSet"),
    (":CHANnel1:SCALe?", ":CHANnel1:SCALe?"),
    (":TIMebase:MAIN:SCALe?", ":TIMebase:MAIN:SCALe?"),
    (":MEASure:ITEM? VPP,CHANnel1", ":MEASure:ITEM? VPP,CHANnel1"),
]


class WaveformCanvas(QWidget):
    """วาดกริดและรูปคลื่นด้วย QPainter เทียบเท่า tk.Canvas ใน Tkinter"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setStyleSheet("background-color: black;")
        self._times = []
        self._volts = []
        self._channel = 1

    def set_data(self, times, volts, channel):
        self._times = times
        self._volts = volts
        self._channel = channel
        self.update()  # trigger repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        # เติมพื้นหลังดำก่อนเสมอ (stylesheet อย่างเดียวบางทีไม่พอสำหรับ custom paint)
        painter.fillRect(0, 0, width, height, QColor("black"))

        # กริด 12x8 ช่อง
        grid_pen = QPen(QColor("#333333"))
        for i in range(1, 12):
            x = width * i / 12
            painter.drawLine(int(x), 0, int(x), height)
        for i in range(1, 8):
            y = height * i / 8
            painter.drawLine(0, int(y), width, int(y))

        if not self._volts:
            return

        v_min, v_max = min(self._volts), max(self._volts)
        v_range = (v_max - v_min) or 1.0

        color = CHANNEL_COLORS.get(self._channel, "#ffff00")
        wave_pen = QPen(QColor(color))
        wave_pen.setWidth(1)
        painter.setPen(wave_pen)

        points = []
        for index, voltage in enumerate(self._volts):
            x = width * index / (len(self._volts) - 1) if len(self._volts) > 1 else 0
            y = height - ((voltage - v_min) / v_range) * height * 0.9 - height * 0.05
            points.append((x, y))

        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class WorkspaceTab(QWidget):
    """รวม Control, Measure, และ Console ไว้หน้าเดียว ปรับค่าซ้าย เห็นผลขวาทันที"""

    def __init__(self, controller, logger, run_safely, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.log = logger
        self.run_safely = run_safely

        self._last_times = []
        self._last_volts = []
        self._auto_refresh_timer = QTimer()
        self._auto_refresh_timer.timeout.connect(self._on_measure)

        root_layout = QHBoxLayout(self)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_widget.setFixedWidth(230)

        self._build_acquisition_panel(left_layout)
        self._build_channel_panel(left_layout)
        self._build_timebase_panel(left_layout)
        self._build_trigger_panel(left_layout)
        left_layout.addStretch()

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self._build_waveform_panel(right_layout)
        self._build_measurement_panel(right_layout)
        self._build_console_panel(right_layout)

        root_layout.addWidget(left_widget)
        root_layout.addWidget(right_widget, 1)

    # ---------- Left column: controls ----------

    def _build_acquisition_panel(self, parent_layout):
        group = QGroupBox("Acquisition")
        grid = QGridLayout(group)

        self.btn_run = QPushButton("Run")
        self.btn_stop = QPushButton("Stop")
        self.btn_single = QPushButton("Single")
        self.btn_autoscale = QPushButton("Autoscale")

        self.btn_run.clicked.connect(self._on_run)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_single.clicked.connect(self._on_single)
        self.btn_autoscale.clicked.connect(self._on_autoscale)

        grid.addWidget(self.btn_run, 0, 0)
        grid.addWidget(self.btn_stop, 0, 1)
        grid.addWidget(self.btn_single, 1, 0)
        grid.addWidget(self.btn_autoscale, 1, 1)

        parent_layout.addWidget(group)
        self.acquisition_group = group

    def _build_channel_panel(self, parent_layout):
        group = QGroupBox("Channel")
        grid = QGridLayout(group)

        grid.addWidget(QLabel("Channel:"), 0, 0)
        self.channel_box = QComboBox()
        self.channel_box.addItems(CHANNELS)
        grid.addWidget(self.channel_box, 0, 1)

        self.display_check = QCheckBox("Display")
        self.display_check.setChecked(True)
        self.display_check.toggled.connect(self._on_display_toggle)
        grid.addWidget(self.display_check, 1, 0, 1, 2)

        grid.addWidget(QLabel("Coupling:"), 2, 0)
        self.coupling_box = QComboBox()
        self.coupling_box.addItems(COUPLINGS)
        self.coupling_box.currentTextChanged.connect(self._on_coupling_change)
        grid.addWidget(self.coupling_box, 2, 1)

        grid.addWidget(QLabel("V/div:"), 3, 0)
        self.volt_box = QComboBox()
        self.volt_box.addItems(VOLT_SCALES)
        self.volt_box.setCurrentText("1")
        self.volt_box.currentTextChanged.connect(self._on_volt_change)
        grid.addWidget(self.volt_box, 3, 1)

        grid.addWidget(QLabel("Offset:"), 4, 0)
        self.offset_edit = QLineEdit("0")
        self.offset_edit.returnPressed.connect(self._on_offset_change)
        grid.addWidget(self.offset_edit, 4, 1)

        self.btn_offset_apply = QPushButton("ตั้งค่า Offset")
        self.btn_offset_apply.clicked.connect(self._on_offset_change)
        grid.addWidget(self.btn_offset_apply, 5, 0, 1, 2)

        parent_layout.addWidget(group)
        self.channel_group = group

    def _build_timebase_panel(self, parent_layout):
        group = QGroupBox("Timebase")
        grid = QGridLayout(group)

        grid.addWidget(QLabel("Time/div:"), 0, 0)
        self.time_box = QComboBox()
        self.time_box.addItems(TIME_SCALES)
        self.time_box.setCurrentText("1e-3")
        self.time_box.currentTextChanged.connect(self._on_time_change)
        grid.addWidget(self.time_box, 0, 1)

        parent_layout.addWidget(group)
        self.timebase_group = group

    def _build_trigger_panel(self, parent_layout):
        group = QGroupBox("Trigger")
        grid = QGridLayout(group)

        grid.addWidget(QLabel("Source:"), 0, 0)
        self.trig_source_box = QComboBox()
        self.trig_source_box.addItems(CHANNELS)
        self.trig_source_box.currentTextChanged.connect(self._on_trigger_source_change)
        grid.addWidget(self.trig_source_box, 0, 1)

        grid.addWidget(QLabel("Slope:"), 1, 0)
        self.trig_slope_box = QComboBox()
        self.trig_slope_box.addItems(SLOPES)
        self.trig_slope_box.currentTextChanged.connect(self._on_trigger_slope_change)
        grid.addWidget(self.trig_slope_box, 1, 1)

        grid.addWidget(QLabel("Level:"), 2, 0)
        self.trig_level_edit = QLineEdit("0")
        self.trig_level_edit.returnPressed.connect(self._on_trigger_level_change)
        grid.addWidget(self.trig_level_edit, 2, 1)

        grid.addWidget(QLabel("Mode:"), 3, 0)
        self.trig_mode_box = QComboBox()
        self.trig_mode_box.addItems(TRIGGER_MODES)
        self.trig_mode_box.currentTextChanged.connect(self._on_trigger_mode_change)
        grid.addWidget(self.trig_mode_box, 3, 1)

        self.btn_trigger_level_apply = QPushButton("ตั้งค่า Level")
        self.btn_trigger_level_apply.clicked.connect(self._on_trigger_level_change)
        grid.addWidget(self.btn_trigger_level_apply, 4, 0, 1, 2)

        parent_layout.addWidget(group)
        self.trigger_group = group

    # ---------- Right column: waveform + measurement + console ----------

    def _build_waveform_panel(self, parent_layout):
        group = QGroupBox("Waveform")
        layout = QVBoxLayout(group)

        toolbar = QHBoxLayout()
        self.btn_read = QPushButton("Read Waveform")
        self.btn_export = QPushButton("Export CSV")
        self.btn_read.clicked.connect(self._on_read_waveform)
        self.btn_export.clicked.connect(self._on_export_csv)
        toolbar.addWidget(self.btn_read)
        toolbar.addWidget(self.btn_export)

        self.btn_save_config = QPushButton("Save Config")
        self.btn_load_config = QPushButton("Load Config")
        self.btn_save_config.clicked.connect(self._on_save_config)
        self.btn_load_config.clicked.connect(self._on_load_config)
        toolbar.addWidget(self.btn_save_config)
        toolbar.addWidget(self.btn_load_config)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.canvas = WaveformCanvas()
        layout.addWidget(self.canvas)

        parent_layout.addWidget(group)

    def _build_measurement_panel(self, parent_layout):
        group = QGroupBox("Measurement")
        layout = QVBoxLayout(group)

        toolbar = QHBoxLayout()
        self.btn_measure = QPushButton("Measure")
        self.btn_measure.clicked.connect(self._on_measure)
        toolbar.addWidget(self.btn_measure)

        self.auto_refresh_check = QCheckBox("Auto-Refresh")
        self.auto_refresh_check.toggled.connect(self._on_auto_refresh_toggle)
        toolbar.addWidget(self.auto_refresh_check)

        toolbar.addWidget(QLabel("ทุก"))
        self.refresh_interval_box = QComboBox()
        self.refresh_interval_box.addItems(REFRESH_INTERVALS)
        self.refresh_interval_box.setCurrentText("2")
        toolbar.addWidget(self.refresh_interval_box)
        toolbar.addWidget(QLabel("วิ"))
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTreeWidget()
        self.table.setHeaderLabels(["Item", "Value"])
        self.table.setRootIsDecorated(False)
        self.table.setMaximumHeight(140)

        self._row_items = {}
        for label, item in MEASUREMENT_ITEMS:
            row = QTreeWidgetItem([label, "—"])
            self.table.addTopLevelItem(row)
            self._row_items[item] = row

        layout.addWidget(self.table)
        parent_layout.addWidget(group)

    def _build_console_panel(self, parent_layout):
        group = QGroupBox("SCPI Console")
        layout = QVBoxLayout(group)

        entry_row = QGridLayout()
        entry_row.addWidget(QLabel("Preset:"), 0, 0)
        self.preset_box = QComboBox()
        self.preset_box.addItems([label for label, _ in CONSOLE_PRESETS])
        self.preset_box.currentTextChanged.connect(self._on_console_preset_selected)
        entry_row.addWidget(self.preset_box, 0, 1)

        self.console_command_edit = QLineEdit()
        self.console_command_edit.returnPressed.connect(self._on_console_send)
        entry_row.addWidget(self.console_command_edit, 0, 2)

        self.btn_console_send = QPushButton("Send")
        self.btn_console_send.clicked.connect(self._on_console_send)
        entry_row.addWidget(self.btn_console_send, 0, 3)

        self.btn_console_clear = QPushButton("Clear")
        self.btn_console_clear.clicked.connect(self._on_console_clear)
        entry_row.addWidget(self.btn_console_clear, 0, 4)

        entry_row.setColumnStretch(2, 1)
        layout.addLayout(entry_row)

        self.console_response = QTextEdit()
        self.console_response.setReadOnly(True)
        self.console_response.setMaximumHeight(90)
        self.console_response.setStyleSheet(
            "background-color: #1e1e1e; color: #dddddd; "
            "font-family: Consolas, monospace; font-size: 9pt;"
        )
        layout.addWidget(self.console_response)

        parent_layout.addWidget(group)

    # ---------- Enable/disable ----------

    def set_enabled(self, enabled):
        self.acquisition_group.setEnabled(enabled)
        self.channel_group.setEnabled(enabled)
        self.timebase_group.setEnabled(enabled)
        self.trigger_group.setEnabled(enabled)

        self.btn_read.setEnabled(enabled)
        self.btn_export.setEnabled(enabled)
        self.btn_save_config.setEnabled(enabled)
        self.btn_load_config.setEnabled(enabled)
        self.btn_measure.setEnabled(enabled)
        self.auto_refresh_check.setEnabled(enabled)
        self.refresh_interval_box.setEnabled(enabled)

        self.preset_box.setEnabled(enabled)
        self.console_command_edit.setEnabled(enabled)
        self.btn_console_send.setEnabled(enabled)
        self.btn_console_clear.setEnabled(enabled)

        if not enabled and self._auto_refresh_timer.isActive():
            self.auto_refresh_check.setChecked(False)
            self._auto_refresh_timer.stop()

    # ---------- Helpers ----------

    def _channel(self):
        return int(self.channel_box.currentText())

    # ---------- Event handlers: acquisition ----------

    def _on_run(self):
        self.run_safely(self.controller.run, "Running")

    def _on_stop(self):
        self.run_safely(self.controller.stop, "Stopped")

    def _on_single(self):
        self.run_safely(self.controller.single, "Single trigger armed")

    def _on_autoscale(self):
        self.run_safely(self.controller.autoscale, "Autoscale done")

    # ---------- Event handlers: channel ----------

    def _on_display_toggle(self, checked):
        channel = self._channel()
        self.run_safely(
            lambda: self.controller.set_channel_display(channel, checked),
            f"CH{channel} display {'ON' if checked else 'OFF'}"
        )

    def _on_coupling_change(self, coupling):
        channel = self._channel()
        self.run_safely(
            lambda: self.controller.set_channel_coupling(channel, coupling),
            f"CH{channel} coupling = {coupling}"
        )

    def _on_volt_change(self, scale):
        channel = self._channel()
        value = float(scale)
        self.run_safely(
            lambda: self.controller.set_voltage_scale(channel, value),
            f"CH{channel} scale = {value} V/div"
        )

    def _on_offset_change(self):
        channel = self._channel()
        try:
            offset = float(self.offset_edit.text())
        except ValueError:
            self.log("ค่า Offset ต้องเป็นตัวเลข", level="error")
            return
        self.run_safely(
            lambda: self.controller.set_channel_offset(channel, offset),
            f"CH{channel} offset = {offset} V"
        )

    def _on_time_change(self, scale):
        value = float(scale)
        self.run_safely(
            lambda: self.controller.set_time_scale(value),
            f"Timebase = {value} s/div"
        )

    # ---------- Event handlers: trigger ----------

    def _on_trigger_source_change(self, channel_str):
        channel = int(channel_str)
        self.run_safely(
            lambda: self.controller.set_trigger_source(channel),
            f"Trigger source = CH{channel}"
        )

    def _on_trigger_slope_change(self, slope):
        self.run_safely(
            lambda: self.controller.set_trigger_slope(slope),
            f"Trigger slope = {slope}"
        )

    def _on_trigger_level_change(self):
        try:
            level = float(self.trig_level_edit.text())
        except ValueError:
            self.log("ค่า Trigger Level ต้องเป็นตัวเลข", level="error")
            return
        self.run_safely(
            lambda: self.controller.set_trigger_level(level),
            f"Trigger level = {level} V"
        )

    def _on_trigger_mode_change(self, mode):
        self.run_safely(
            lambda: self.controller.set_trigger_mode(mode),
            f"Trigger mode = {mode}"
        )

    # ---------- Event handlers: waveform / measurement ----------

    def _on_read_waveform(self):
        channel = self._channel()
        result = self.run_safely(
            lambda: self.controller.read_waveform(channel),
            f"Waveform read from CH{channel}"
        )
        if result:
            times, volts = result
            self._last_times, self._last_volts = times, volts
            self.canvas.set_data(times, volts, channel)

    def _on_export_csv(self):
        if not self._last_volts:
            self.log("ยังไม่มีข้อมูล waveform ให้ export กด Read Waveform ก่อน", level="error")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "waveform.csv", "CSV files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["time_s", "voltage_v"])
                writer.writerows(zip(self._last_times, self._last_volts))
            self.log(f"บันทึกไฟล์แล้ว: {path}", level="ok")
        except OSError as exc:
            self.log(f"บันทึกไฟล์ไม่สำเร็จ: {exc}", level="error")

    def _on_measure(self):
        channel = self._channel()
        for label, item in MEASUREMENT_ITEMS:
            value = self.run_safely(lambda item=item: self.controller.measure(channel, item))
            display = self._format_value(item, value)
            self._row_items[item].setText(1, display)
        self.log(f"วัดค่าจาก CH{channel} เสร็จแล้ว", level="ok")

    @staticmethod
    def _format_value(item, value):
        if value is None:
            return "—"
        if item == "FREQuency":
            return f"{value:.3f} Hz"
        if item == "PERiod":
            return f"{value * 1000:.3f} ms"
        return f"{value:.3f} V"

    # ---------- Auto-refresh ----------

    def _on_auto_refresh_toggle(self, checked):
        if checked:
            interval_ms = int(float(self.refresh_interval_box.currentText()) * 1000)
            self._auto_refresh_timer.start(interval_ms)
            self._on_measure()
        else:
            self._auto_refresh_timer.stop()

    # ---------- Console ----------

    def _on_console_preset_selected(self, label):
        for preset_label, command in CONSOLE_PRESETS:
            if preset_label == label:
                self.console_command_edit.setText(command)
                break

    def _append_console_response(self, text, color):
        self.console_response.setTextColor(QColor(color))
        self.console_response.append(text)

    def _on_console_send(self):
        command = self.console_command_edit.text().strip()
        if not command:
            return

        if "DISP" in command.upper() and "DATA" in command.upper():
            self.log(
                "คำสั่งนี้คืนค่าเป็นภาพ (binary) ใช้ปุ่ม Capture ใน Tools tab แทน",
                level="error",
            )
            return

        self._append_console_response(f"> {command}", "#8ce99a")

        if command.endswith("?"):
            response = self.run_safely(lambda: self.controller.query(command))
            if response is not None:
                self._append_console_response(f"< {response}", "#dddddd")
        else:
            self.run_safely(lambda: self.controller.write(command), f"ส่งคำสั่ง: {command}")

    def _on_console_clear(self):
        self.console_response.clear()

    # ---------- Save / Load config ----------

    def _collect_config(self):
        return {
            "channel": self.channel_box.currentText(),
            "display": self.display_check.isChecked(),
            "coupling": self.coupling_box.currentText(),
            "vdiv": self.volt_box.currentText(),
            "offset": self.offset_edit.text(),
            "time_div": self.time_box.currentText(),
            "trigger_source": self.trig_source_box.currentText(),
            "trigger_slope": self.trig_slope_box.currentText(),
            "trigger_level": self.trig_level_edit.text(),
            "trigger_mode": self.trig_mode_box.currentText(),
        }

    def _on_save_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", "scope_config.json", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            save_config(path, self._collect_config())
            self.log(f"บันทึกการตั้งค่าแล้ว: {path}", level="ok")
        except OSError as exc:
            self.log(f"บันทึกการตั้งค่าไม่สำเร็จ: {exc}", level="error")

    def _on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Config", "", "JSON files (*.json)")
        if not path:
            return

        try:
            settings = load_config(path)
        except (OSError, ValueError) as exc:
            self.log(f"โหลดการตั้งค่าไม่สำเร็จ: {exc}", level="error")
            return

        self.channel_box.setCurrentText(settings.get("channel", self.channel_box.currentText()))
        self.display_check.setChecked(settings.get("display", self.display_check.isChecked()))
        self.coupling_box.setCurrentText(settings.get("coupling", self.coupling_box.currentText()))
        self.volt_box.setCurrentText(settings.get("vdiv", self.volt_box.currentText()))
        self.offset_edit.setText(str(settings.get("offset", self.offset_edit.text())))
        self.time_box.setCurrentText(settings.get("time_div", self.time_box.currentText()))
        self.trig_source_box.setCurrentText(
            settings.get("trigger_source", self.trig_source_box.currentText())
        )
        self.trig_slope_box.setCurrentText(
            settings.get("trigger_slope", self.trig_slope_box.currentText())
        )
        self.trig_level_edit.setText(str(settings.get("trigger_level", self.trig_level_edit.text())))
        self.trig_mode_box.setCurrentText(settings.get("trigger_mode", self.trig_mode_box.currentText()))

        # ยิงค่าที่โหลดมาไปที่เครื่องจริงทีละคำสั่ง เพื่อให้ log เห็นทุกขั้นตอน
        self._on_display_toggle(self.display_check.isChecked())
        self._on_coupling_change(self.coupling_box.currentText())
        self._on_volt_change(self.volt_box.currentText())
        self._on_offset_change()
        self._on_time_change(self.time_box.currentText())
        self._on_trigger_source_change(self.trig_source_box.currentText())
        self._on_trigger_slope_change(self.trig_slope_box.currentText())
        self._on_trigger_level_change()
        self._on_trigger_mode_change(self.trig_mode_box.currentText())

        self.log(f"โหลดการตั้งค่าแล้ว: {path}", level="ok")
