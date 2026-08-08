"""Workspace tab: all frequently-adjusted controls (channel, timebase, trigger)
on the left; waveform, measurement, and SCPI console on the right — everything
needed during a live test session lives in one tab. Only calls controller
methods, config_manager, and the shared logger."""

import csv
import tkinter as tk
from tkinter import ttk, filedialog

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


class WorkspaceTab(ttk.Frame):
    """รวม Control, Measure, และ Console ไว้หน้าเดียว ปรับค่าซ้าย เห็นผลขวาทันที"""

    def __init__(self, parent, controller, logger, run_safely):
        super().__init__(parent, padding=10)
        self.controller = controller
        self.log = logger
        self.run_safely = run_safely

        self._last_times = []
        self._last_volts = []
        self._auto_refresh_job = None  # เก็บ id ของ root.after ไว้ยกเลิกได้

        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 10))

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        self._build_acquisition_panel(left)
        self._build_channel_panel(left)
        self._build_timebase_panel(left)
        self._build_trigger_panel(left)

        self._build_waveform_panel(right)
        self._build_measurement_panel(right)
        self._build_console_panel(right)

    # ---------- Left column: controls ----------

    def _build_acquisition_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Acquisition", padding=10)
        frame.pack(fill="x", pady=(0, 8))

        ttk.Button(frame, text="Run", command=self._on_run).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(frame, text="Stop", command=self._on_stop).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(frame, text="Single", command=self._on_single).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(frame, text="Autoscale", command=self._on_autoscale).grid(row=1, column=1, padx=2, pady=2)

        self.acquisition_frame = frame

    def _build_channel_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Channel", padding=10)
        frame.pack(fill="x", pady=(0, 8))

        ttk.Label(frame, text="Channel:").grid(row=0, column=0, sticky="e")
        self.channel_var = tk.StringVar(value="1")
        channel_box = ttk.Combobox(
            frame, textvariable=self.channel_var, values=CHANNELS,
            width=6, state="readonly"
        )
        channel_box.grid(row=0, column=1, sticky="w", padx=4)

        self.display_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Display", variable=self.display_var,
            command=self._on_display_toggle
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(frame, text="Coupling:").grid(row=2, column=0, sticky="e", pady=(6, 0))
        self.coupling_var = tk.StringVar(value="DC")
        coupling_box = ttk.Combobox(
            frame, textvariable=self.coupling_var, values=COUPLINGS,
            width=6, state="readonly"
        )
        coupling_box.grid(row=2, column=1, sticky="w", padx=4, pady=(6, 0))
        coupling_box.bind("<<ComboboxSelected>>", self._on_coupling_change)

        ttk.Label(frame, text="V/div:").grid(row=3, column=0, sticky="e", pady=(6, 0))
        self.volt_var = tk.StringVar(value="1")
        volt_box = ttk.Combobox(
            frame, textvariable=self.volt_var, values=VOLT_SCALES,
            width=8, state="readonly"
        )
        volt_box.grid(row=3, column=1, sticky="w", padx=4, pady=(6, 0))
        volt_box.bind("<<ComboboxSelected>>", self._on_volt_change)

        ttk.Label(frame, text="Offset:").grid(row=4, column=0, sticky="e", pady=(6, 0))
        self.offset_var = tk.StringVar(value="0")
        offset_entry = ttk.Entry(frame, textvariable=self.offset_var, width=8)
        offset_entry.grid(row=4, column=1, sticky="w", padx=4, pady=(6, 0))
        offset_entry.bind("<Return>", self._on_offset_change)

        ttk.Button(
            frame, text="ตั้งค่า Offset", command=self._on_offset_change
        ).grid(row=5, column=0, columnspan=2, pady=(6, 0))

        self.channel_frame = frame

    def _build_timebase_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Timebase", padding=10)
        frame.pack(fill="x", pady=(0, 8))

        ttk.Label(frame, text="Time/div:").grid(row=0, column=0, sticky="e")
        self.time_var = tk.StringVar(value="1e-3")
        time_box = ttk.Combobox(
            frame, textvariable=self.time_var, values=TIME_SCALES,
            width=8, state="readonly"
        )
        time_box.grid(row=0, column=1, sticky="w", padx=4)
        time_box.bind("<<ComboboxSelected>>", self._on_time_change)

        self.timebase_frame = frame

    def _build_trigger_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Trigger", padding=10)
        frame.pack(fill="x", pady=(0, 8))

        ttk.Label(frame, text="Source:").grid(row=0, column=0, sticky="e")
        self.trig_source_var = tk.StringVar(value="1")
        trig_source_box = ttk.Combobox(
            frame, textvariable=self.trig_source_var, values=CHANNELS,
            width=6, state="readonly"
        )
        trig_source_box.grid(row=0, column=1, sticky="w", padx=4)
        trig_source_box.bind("<<ComboboxSelected>>", self._on_trigger_source_change)

        ttk.Label(frame, text="Slope:").grid(row=1, column=0, sticky="e", pady=(6, 0))
        self.trig_slope_var = tk.StringVar(value="POSitive")
        trig_slope_box = ttk.Combobox(
            frame, textvariable=self.trig_slope_var, values=SLOPES,
            width=10, state="readonly"
        )
        trig_slope_box.grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        trig_slope_box.bind("<<ComboboxSelected>>", self._on_trigger_slope_change)

        ttk.Label(frame, text="Level:").grid(row=2, column=0, sticky="e", pady=(6, 0))
        self.trig_level_var = tk.StringVar(value="0")
        trig_level_entry = ttk.Entry(frame, textvariable=self.trig_level_var, width=8)
        trig_level_entry.grid(row=2, column=1, sticky="w", padx=4, pady=(6, 0))
        trig_level_entry.bind("<Return>", self._on_trigger_level_change)

        ttk.Label(frame, text="Mode:").grid(row=3, column=0, sticky="e", pady=(6, 0))
        self.trig_mode_var = tk.StringVar(value="AUTO")
        trig_mode_box = ttk.Combobox(
            frame, textvariable=self.trig_mode_var, values=TRIGGER_MODES,
            width=10, state="readonly"
        )
        trig_mode_box.grid(row=3, column=1, sticky="w", padx=4, pady=(6, 0))
        trig_mode_box.bind("<<ComboboxSelected>>", self._on_trigger_mode_change)

        ttk.Button(
            frame, text="ตั้งค่า Level", command=self._on_trigger_level_change
        ).grid(row=4, column=0, columnspan=2, pady=(6, 0))

        self.trigger_frame = frame

    def _build_config_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Configuration", padding=10)
        frame.pack(fill="x")

        self.btn_save_config = ttk.Button(frame, text="Save Config", command=self._on_save_config)
        self.btn_save_config.pack(fill="x", pady=(0, 4))

        self.btn_load_config = ttk.Button(frame, text="Load Config", command=self._on_load_config)
        self.btn_load_config.pack(fill="x")

        self.config_frame = frame

    # ---------- Right column: waveform + measurement + console ----------

    def _build_waveform_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Waveform", padding=8)
        frame.pack(fill="x", pady=(0, 6))

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 4))

        self.btn_read = ttk.Button(toolbar, text="Read Waveform", command=self._on_read_waveform)
        self.btn_read.pack(side="left", padx=3)

        self.btn_export = ttk.Button(toolbar, text="Export CSV", command=self._on_export_csv)
        self.btn_export.pack(side="left", padx=3)

        self.btn_save_config = ttk.Button(toolbar, text="Save Config", command=self._on_save_config)
        self.btn_save_config.pack(side="left", padx=3)

        self.btn_load_config = ttk.Button(toolbar, text="Load Config", command=self._on_load_config)
        self.btn_load_config.pack(side="left", padx=3)

        self.canvas = tk.Canvas(frame, bg="black", highlightthickness=0, height=80)
    def _build_measurement_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Measurement", padding=8)
        frame.pack(fill="x", pady=(0, 6))

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 4))

        self.btn_measure = ttk.Button(toolbar, text="Measure", command=self._on_measure)
        self.btn_measure.pack(side="left", padx=(0, 15))

        self.auto_refresh_var = tk.BooleanVar(value=False)
        self.chk_auto_refresh = ttk.Checkbutton(
            toolbar, text="Auto-Refresh", variable=self.auto_refresh_var,
            command=self._on_auto_refresh_toggle
        )
        self.chk_auto_refresh.pack(side="left", padx=(0, 4))

        ttk.Label(toolbar, text="ทุก").pack(side="left")
        self.refresh_interval_var = tk.StringVar(value="2")
        self.refresh_interval_box = ttk.Combobox(
            toolbar, textvariable=self.refresh_interval_var, values=REFRESH_INTERVALS,
            width=4, state="readonly"
        )
        self.refresh_interval_box.pack(side="left", padx=4)
        ttk.Label(toolbar, text="วิ").pack(side="left")

        # ความสูงตาราง 4 แถวแทน 6 (พอดีกับพื้นที่จำกัด เลื่อนดูที่เหลือได้)
        self.table = ttk.Treeview(
            frame, columns=("value",), show="tree headings", height=4
        )
        self.table.heading("#0", text="Item")
        self.table.heading("value", text="Value")
        self.table.column("#0", width=150)
        self.table.column("value", width=150)
        self.table.pack(fill="x")

        self._row_ids = {}
        for label, item in MEASUREMENT_ITEMS:
            row_id = self.table.insert("", "end", text=label, values=("—",))
            self._row_ids[item] = row_id

        self.measurement_frame = frame

    def _build_console_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="SCPI Console", padding=8)
        frame.pack(fill="both", expand=True)

        entry_row = ttk.Frame(frame)
        entry_row.pack(fill="x", pady=(0, 4))

        ttk.Label(entry_row, text="Preset:").grid(row=0, column=0, sticky="e")
        self.preset_var = tk.StringVar()
        self.preset_box = ttk.Combobox(
            entry_row, textvariable=self.preset_var,
            values=[label for label, _ in CONSOLE_PRESETS],
            width=26, state="disabled"
        )
        self.preset_box.grid(row=0, column=1, sticky="we", padx=4)
        self.preset_box.bind("<<ComboboxSelected>>", self._on_console_preset_selected)

        self.console_command_var = tk.StringVar()
        self.console_command_entry = ttk.Entry(
            entry_row, textvariable=self.console_command_var, state="disabled"
        )
        self.console_command_entry.grid(row=0, column=2, sticky="we", padx=4)
        self.console_command_entry.bind("<Return>", self._on_console_send)

        self.btn_console_send = ttk.Button(
            entry_row, text="Send", command=self._on_console_send, state="disabled"
        )
        self.btn_console_send.grid(row=0, column=3, padx=2)

        self.btn_console_clear = ttk.Button(
            entry_row, text="Clear", command=self._on_console_clear, state="disabled"
        )
        self.btn_console_clear.grid(row=0, column=4, padx=2)

        entry_row.columnconfigure(2, weight=1)

        self.console_response = tk.Text(
            frame, height=4, state="disabled",
            bg="#1e1e1e", fg="#dddddd", font=("Consolas", 9)
        )
        self.console_response.pack(fill="both", expand=True)
        self.console_response.tag_config("sent", foreground="#8ce99a")
        self.console_response.tag_config("recv", foreground="#dddddd")

        self.console_frame = frame

    # ---------- Drawing ----------

    def _draw_grid(self):
        self.canvas.delete("grid")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        for i in range(1, 12):
            x = width * i / 12
            self.canvas.create_line(x, 0, x, height, fill="#333333", tags="grid")
        for i in range(1, 8):
            y = height * i / 8
            self.canvas.create_line(0, y, width, y, fill="#333333", tags="grid")

    def _plot(self, times, volts, channel):
        self.canvas.delete("wave")
        self._draw_grid()

        if not volts:
            return

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        v_min, v_max = min(volts), max(volts)
        v_range = (v_max - v_min) or 1.0

        points = []
        for index, voltage in enumerate(volts):
            x = width * index / (len(volts) - 1)
            y = height - ((voltage - v_min) / v_range) * height * 0.9 - height * 0.05
            points.extend([x, y])

        color = CHANNEL_COLORS.get(channel, "#ffff00")
        if len(points) >= 4:
            self.canvas.create_line(*points, fill=color, tags="wave")

    # ---------- Enable/disable ----------

    def set_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for frame in (
            self.acquisition_frame, self.channel_frame, self.timebase_frame,
            self.trigger_frame,
        ):
            for child in frame.winfo_children():
                if isinstance(child, ttk.Combobox):
                    child.configure(state="readonly" if enabled else "disabled")
                elif isinstance(child, (ttk.Button, ttk.Checkbutton, ttk.Entry)):
                    child.configure(state=state)

        self.btn_read.configure(state=state)
        self.btn_export.configure(state=state)
        self.btn_save_config.configure(state=state)
        self.btn_load_config.configure(state=state)

        if not enabled and self._auto_refresh_job is not None:
            self.auto_refresh_var.set(False)
            self._stop_auto_refresh()

    # ---------- Helpers ----------

    def _channel(self):
        return int(self.channel_var.get())

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

    def _on_display_toggle(self):
        channel = self._channel()
        state = self.display_var.get()
        self.run_safely(
            lambda: self.controller.set_channel_display(channel, state),
            f"CH{channel} display {'ON' if state else 'OFF'}"
        )

    def _on_coupling_change(self, event=None):
        channel = self._channel()
        coupling = self.coupling_var.get()
        self.run_safely(
            lambda: self.controller.set_channel_coupling(channel, coupling),
            f"CH{channel} coupling = {coupling}"
        )

    def _on_volt_change(self, event=None):
        channel = self._channel()
        scale = float(self.volt_var.get())
        self.run_safely(
            lambda: self.controller.set_voltage_scale(channel, scale),
            f"CH{channel} scale = {scale} V/div"
        )

    def _on_offset_change(self, event=None):
        channel = self._channel()
        try:
            offset = float(self.offset_var.get())
        except ValueError:
            self.log("ค่า Offset ต้องเป็นตัวเลข", level="error")
            return
        self.run_safely(
            lambda: self.controller.set_channel_offset(channel, offset),
            f"CH{channel} offset = {offset} V"
        )

    def _on_time_change(self, event=None):
        scale = float(self.time_var.get())
        self.run_safely(
            lambda: self.controller.set_time_scale(scale),
            f"Timebase = {scale} s/div"
        )

    # ---------- Event handlers: trigger ----------

    def _on_trigger_source_change(self, event=None):
        channel = int(self.trig_source_var.get())
        self.run_safely(
            lambda: self.controller.set_trigger_source(channel),
            f"Trigger source = CH{channel}"
        )

    def _on_trigger_slope_change(self, event=None):
        slope = self.trig_slope_var.get()
        self.run_safely(
            lambda: self.controller.set_trigger_slope(slope),
            f"Trigger slope = {slope}"
        )

    def _on_trigger_level_change(self, event=None):
        try:
            level = float(self.trig_level_var.get())
        except ValueError:
            self.log("ค่า Trigger Level ต้องเป็นตัวเลข", level="error")
            return
        self.run_safely(
            lambda: self.controller.set_trigger_level(level),
            f"Trigger level = {level} V"
        )

    def _on_trigger_mode_change(self, event=None):
        mode = self.trig_mode_var.get()
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
            self._plot(times, volts, channel)

    def _on_export_csv(self):
        if not self._last_volts:
            self.log("ยังไม่มีข้อมูล waveform ให้ export กด Read Waveform ก่อน", level="error")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="waveform.csv",
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
            self.table.item(self._row_ids[item], values=(display,))
        self.log(f"วัดค่าจาก CH{channel} เสร็จแล้ว", level="ok")

    @staticmethod
    def _format_value(item, value):
        if value is None:
            return "—"
        if item in ("FREQuency",):
            return f"{value:.3f} Hz"
        if item in ("PERiod",):
            return f"{value * 1000:.3f} ms"
        return f"{value:.3f} V"

    # ---------- Auto-refresh ----------

    def _on_auto_refresh_toggle(self):
        if self.auto_refresh_var.get():
            self._schedule_auto_refresh()
        else:
            self._stop_auto_refresh()

    def _schedule_auto_refresh(self):
        interval_ms = int(float(self.refresh_interval_var.get()) * 1000)
        self._on_measure()
        self._auto_refresh_job = self.after(interval_ms, self._auto_refresh_tick)

    def _auto_refresh_tick(self):
        if not self.auto_refresh_var.get():
            return
        self._on_measure()
        interval_ms = int(float(self.refresh_interval_var.get()) * 1000)
        self._auto_refresh_job = self.after(interval_ms, self._auto_refresh_tick)

    def _stop_auto_refresh(self):
        if self._auto_refresh_job is not None:
            self.after_cancel(self._auto_refresh_job)
            self._auto_refresh_job = None

    # ---------- Console ----------

    def _on_console_preset_selected(self, event=None):
        label = self.preset_var.get()
        for preset_label, command in CONSOLE_PRESETS:
            if preset_label == label:
                self.console_command_var.set(command)
                break

    def _append_console_response(self, text, tag):
        self.console_response.configure(state="normal")
        self.console_response.insert("end", text + "\n", tag)
        self.console_response.see("end")
        self.console_response.configure(state="disabled")

    def _on_console_send(self, event=None):
        command = self.console_command_var.get().strip()
        if not command:
            return

        if "DISP" in command.upper() and "DATA" in command.upper():
            self.log(
                "คำสั่งนี้คืนค่าเป็นภาพ (binary) ใช้ปุ่ม Capture ใน Tools tab แทน",
                level="error",
            )
            return

        self._append_console_response(f"> {command}", "sent")

        if command.endswith("?"):
            response = self.run_safely(lambda: self.controller.query(command))
            if response is not None:
                self._append_console_response(f"< {response}", "recv")
        else:
            self.run_safely(lambda: self.controller.write(command), f"ส่งคำสั่ง: {command}")

    def _on_console_clear(self):
        self.console_response.configure(state="normal")
        self.console_response.delete("1.0", "end")
        self.console_response.configure(state="disabled")

    # ---------- Save / Load config ----------

    def _collect_config(self):
        return {
            "channel": self.channel_var.get(),
            "display": self.display_var.get(),
            "coupling": self.coupling_var.get(),
            "vdiv": self.volt_var.get(),
            "offset": self.offset_var.get(),
            "time_div": self.time_var.get(),
            "trigger_source": self.trig_source_var.get(),
            "trigger_slope": self.trig_slope_var.get(),
            "trigger_level": self.trig_level_var.get(),
            "trigger_mode": self.trig_mode_var.get(),
        }

    def _on_save_config(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="scope_config.json",
        )
        if not path:
            return
        try:
            save_config(path, self._collect_config())
            self.log(f"บันทึกการตั้งค่าแล้ว: {path}", level="ok")
        except OSError as exc:
            self.log(f"บันทึกการตั้งค่าไม่สำเร็จ: {exc}", level="error")

    def _on_load_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not path:
            return

        try:
            settings = load_config(path)
        except (OSError, ValueError) as exc:
            self.log(f"โหลดการตั้งค่าไม่สำเร็จ: {exc}", level="error")
            return

        self.channel_var.set(settings.get("channel", self.channel_var.get()))
        self.display_var.set(settings.get("display", self.display_var.get()))
        self.coupling_var.set(settings.get("coupling", self.coupling_var.get()))
        self.volt_var.set(settings.get("vdiv", self.volt_var.get()))
        self.offset_var.set(settings.get("offset", self.offset_var.get()))
        self.time_var.set(settings.get("time_div", self.time_var.get()))
        self.trig_source_var.set(settings.get("trigger_source", self.trig_source_var.get()))
        self.trig_slope_var.set(settings.get("trigger_slope", self.trig_slope_var.get()))
        self.trig_level_var.set(settings.get("trigger_level", self.trig_level_var.get()))
        self.trig_mode_var.set(settings.get("trigger_mode", self.trig_mode_var.get()))

        self._on_display_toggle()
        self._on_coupling_change()
        self._on_volt_change()
        self._on_offset_change()
        self._on_time_change()
        self._on_trigger_source_change()
        self._on_trigger_slope_change()
        self._on_trigger_level_change()
        self._on_trigger_mode_change()

        self.log(f"โหลดการตั้งค่าแล้ว: {path}", level="ok")