"""Tools tab: screen capture. Only calls controller.capture_screen()."""

import io
from tkinter import ttk, filedialog

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ToolsTab(ttk.Frame):
    """จับภาพหน้าจอจากเครื่องและบันทึกเป็นไฟล์"""

    def __init__(self, parent, controller, logger, run_safely):
        super().__init__(parent, padding=10)
        self.controller = controller
        self.log = logger
        self.run_safely = run_safely

        self._last_image_bytes = None
        self._tk_image = None  # ต้องเก็บ reference ไว้ ไม่งั้น Tkinter จะลบภาพทิ้ง

        self._build_capture_panel()

        if not PIL_AVAILABLE:
            self.log(
                "ไม่พบไลบรารี Pillow — ติดตั้งด้วย 'pip install Pillow' เพื่อแสดงภาพหน้าจอ",
                level="error",
            )

    # ---------- UI construction ----------

    def _build_capture_panel(self):
        frame = ttk.LabelFrame(self, text="Screen Capture", padding=10)
        frame.pack(fill="both", expand=True)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 8))

        self.btn_capture = ttk.Button(toolbar, text="Capture", command=self._on_capture)
        self.btn_capture.pack(side="left", padx=3)

        self.btn_save = ttk.Button(
            toolbar, text="Save PNG", command=self._on_save, state="disabled"
        )
        self.btn_save.pack(side="left", padx=3)

        self.image_label = ttk.Label(
            frame, text="ยังไม่มีภาพ — กด Capture", anchor="center", relief="sunken"
        )
        self.image_label.pack(fill="both", expand=True)

        self.capture_toolbar = toolbar

    # ---------- Enable/disable ----------

    def set_enabled(self, enabled):
        self.btn_capture.configure(state="normal" if enabled else "disabled")
        if not enabled:
            self.btn_save.configure(state="disabled")

    # ---------- Event handlers ----------

    def _on_capture(self):
        data = self.run_safely(self.controller.capture_screen, "จับภาพหน้าจอสำเร็จ")
        if not data:
            return

        self._last_image_bytes = data
        self.btn_save.configure(state="normal")

        if not PIL_AVAILABLE:
            self.image_label.configure(
                text=f"ได้ข้อมูลภาพ {len(data)} bytes (ติดตั้ง Pillow เพื่อแสดงภาพ)"
            )
            return

        try:
            pil_image = Image.open(io.BytesIO(data))
            pil_image.thumbnail((800, 500))
            self._tk_image = ImageTk.PhotoImage(pil_image)
            self.image_label.configure(image=self._tk_image, text="")
        except Exception as exc:
            self.log(f"แสดงภาพไม่สำเร็จ: {exc}", level="error")

    def _on_save(self):
        if not self._last_image_bytes:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            initialfile="scope_screen.png",
        )
        if not path:
            return

        try:
            with open(path, "wb") as f:
                f.write(self._last_image_bytes)
            self.log(f"บันทึกภาพแล้ว: {path}", level="ok")
        except OSError as exc:
            self.log(f"บันทึกไฟล์ไม่สำเร็จ: {exc}", level="error")