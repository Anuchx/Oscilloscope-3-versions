# RIGOL Oscilloscope Controller

โปรแกรมควบคุมออสซิลโลสโคป RIGOL DHO814 ผ่าน SCPI จากคอมพิวเตอร์
พัฒนาเป็นโปรเจกต์รายวิชา มีสามเวอร์ชันที่ใช้แนวคิด hardware layer
เดียวกัน (แยกชั้นควบคุมฮาร์ดแวร์ออกจาก UI อย่างเด็ดขาด):

| เวอร์ชัน |  | โฟลเดอร์ |
|---|---|---|
| Python + Tkinter |  | `gui_tk/` |
| Python + PyQt6 |  | `gui_qt/` |
| C++ + Qt6 + libusb |  | `scopecpp/` |

ทั้งสามเวอร์ชันมีฟีเจอร์ตรงกัน: Connection, Acquisition, Channel,
Timebase, Trigger, Waveform, Measurement, SCPI Console, Save/Load
Config, และ Screen Capture

---

## เวอร์ชัน Python + Tkinter

### ความสามารถ

- **Connection** — Scan หา VISA device, เรียง USB ขึ้นก่อน, จุดสถานะเขียว/เทา
- **Workspace tab** — ทุกอย่างที่ใช้ระหว่างทดลองอยู่หน้าเดียว:
  - Acquisition: Run / Stop / Single / Autoscale
  - Channel: เลือกช่อง 1–4, Display, Coupling (DC/AC/GND), V/div, Offset
  - Timebase: Time/div
  - Trigger: Source / Slope / Level / Mode
  - Waveform: อ่านรูปคลื่นมาวาดกราฟ (สีต่างกันตามช่อง), Export CSV
  - Measurement: Vpp, Vmax, Vmin, Vrms, Frequency, Period พร้อม Auto-Refresh
  - Save/Load Config (JSON)
  - SCPI Console: ยิงคำสั่งเองพร้อม preset
- **Tools tab** — Screen Capture จากเครื่อง + Save PNG
- **Log** — บันทึกทุกการกระทำพร้อมเวลา สีแยกตามระดับ (สำเร็จ/ผิดพลาด)

### ติดตั้ง

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Windows เพิ่มเติม: ต้องมีไดรเวอร์ USB สำหรับเครื่อง — ใช้ **libusbK** (ผ่าน
[Zadig](https://zadig.akeo.ie/)) คู่กับ backend `pyvisa-py` หรือใช้ **NI-VISA**
(แล้วแก้ `controller.py` เอา `"@py"` ออก)

### รัน

```bash
python main_tk.py
```

กด **Scan** → เลือกที่อยู่ที่ขึ้นต้นด้วย `USB0::0x1AB1::...` → **Connect**

### โครงสร้างโค้ด

```
main.py               จุดเริ่มโปรแกรม
controller.py          ชั้นฮาร์ดแวร์ — PyVISA + SCPI ทั้งหมด ไม่มี UI
config_manager.py      อ่าน/เขียนไฟล์ตั้งค่า JSON
gui_tk/
├── app.py              หน้าต่างหลัก: Connection, Notebook, Log
├── workspace_tab.py    Workspace tab ทั้งหมด
└── tools_tab.py        Screen Capture
```

---

## เวอร์ชัน Python + PyQt6

หน้าตาและฟีเจอร์เหมือนเวอร์ชัน Tkinter ทุกอย่าง ต่างกันแค่ใช้ Qt
widget แทน — ใช้ `ScopeController` และ `config_manager.py` ตัวเดียวกัน
กับ Tkinter (ไม่ต้องเขียนใหม่ เพราะชั้นฮาร์ดแวร์แยกออกจาก UI ตั้งแต่แรก)

### ติดตั้งเพิ่ม

```bash
pip install PyQt6
```

(ใช้ `venv` และ `requirements.txt` เดียวกับ Tkinter ได้เลย เพิ่มแค่ PyQt6)

### รัน

```bash
python main_qt.py
```

### โครงสร้างโค้ด

```
main_qt.py             จุดเริ่มโปรแกรม (PyQt6)
gui_qt/
├── app.py               หน้าต่างหลัก: Connection, Tab widget, Log
├── workspace_tab.py     Workspace tab ทั้งหมด (รวม WaveformCanvas วาดด้วย QPainter)
└── tools_tab.py         Screen Capture
```

**หมายเหตุลำดับการสร้าง UI:** ใน `app.py` ต้องสร้าง Log panel **ก่อน**
Tab widget เสมอ (ไม่ใช่สร้าง Tab ก่อนแล้วค่อย Log) เพราะ Tab widget ที่
ยืดเต็มพื้นที่จะจองพื้นที่ทั้งหมดก่อน ถ้าสร้างก่อน Log อาจไม่มีที่เหลือ
ให้แสดงเลย (เจอปัญหานี้มาแล้วทั้งใน Tkinter และ PyQt6)

---

## เวอร์ชัน C++ + Qt6 + libusb

พอร์ต C++ คุยกับเครื่องผ่าน **libusb** โดยตรง (ไม่ใช้ NI-VISA) เขียน
SCPI/USB-TMC framing เอง ทดสอบ build บน **WSL2 + WSLg**

**สถานะปัจจุบัน:** build ผ่านและเปิดหน้าต่างได้แล้ว ยังไม่เคยทดสอบ
เชื่อมต่อกับเครื่อง DHO814 จริง (ติดขั้นตอน USB passthrough จาก Windows
เข้า WSL2 ที่ยังไม่เสร็จ)

### สิ่งที่ต้องมีก่อนเริ่ม

- Windows 10/11 ที่มี WSL2 + WSLg (เช็คด้วย `wsl --version` ต้องเห็น
  บรรทัด `WSLg version: ...` ถ้าไม่มีให้ `wsl --update`)
- Ubuntu distro ใน WSL2

### ติดตั้ง (รันใน WSL/Ubuntu terminal)

```bash
sudo apt update
sudo apt install -y build-essential cmake qt6-base-dev libusb-1.0-0-dev pkg-config fonts-thai-tlwg
```

ทดสอบว่า GUI แสดงผลได้ก่อน:

```bash
sudo apt install -y x11-apps
xeyes
```

ถ้าเห็นหน้าต่างตาโผล่บนจอ Windows แปลว่าพร้อมใช้งาน

### วิธี build

วางไฟล์ไว้ใน WSL filesystem จะเร็วกว่าเก็บบน `/mnt/d/...`:

```bash
cp -r /mnt/d/path/to/scopecpp ~/scopecpp
cd ~/scopecpp
mkdir -p build && cd build
cmake ..
cmake --build . -j$(nproc)
./ScopeControllerCpp
```

### โครงสร้างโค้ด

```
scopecpp/
├── CMakeLists.txt
├── main.cpp                  จุดเริ่มโปรแกรม
├── controller.cpp             ScopeController — libusb + USB-TMC framing
├── config_manager.cpp         save/load JSON (parser เขียนเอง)
└── gui_cpp/
    ├── app.cpp                 MainWindow: Connection, Log, Tabs
    ├── workspace_tab.cpp       Workspace tab ทั้งหมด
    ├── tools_tab.cpp           Screen Capture
    └── waveform_widget.cpp     วาดกริด+กราฟด้วย QPainter
```

โปรเจกต์นี้ไม่มีไฟล์ `.h` เลยโดยตั้งใจ — แต่ละ `.cpp` มีทั้ง class
declaration และ implementation ในไฟล์เดียว กันซ้ำด้วย `#pragma once`
แล้ว include เข้าหากันตรงๆ ผลคือมีแค่ `main.cpp` เป็น translation unit
จริง

**ข้อจำกัดจากดีไซน์นี้ — Qt MOC:** คลาสที่มี `Q_OBJECT` ต้องมีสองอย่าง
เพิ่ม: (1) เพิ่มไฟล์เข้า `add_executable()` ใน `CMakeLists.txt` พร้อม
mark `HEADER_FILE_ONLY` ให้ AUTOMOC เห็นแต่ไม่ compile ซ้ำ (2) ต้องมี
`#include "ชื่อไฟล์.moc"` ท้ายไฟล์ — ทำไว้แล้วใน `CMakeLists.txt` และ
ท้ายไฟล์ `waveform_widget.cpp`, `workspace_tab.cpp`, `tools_tab.cpp`,
`app.cpp` ถ้าเพิ่มคลาสใหม่ที่มี `Q_OBJECT` ต้องทำสองขั้นตอนนี้ด้วย

### สิ่งที่ยังไม่ได้ทำ

- [ ] ทดสอบเชื่อมต่อกับเครื่อง DHO814 จริง
- [ ] ตั้งค่า USB passthrough จาก Windows เข้า WSL2 (`usbipd-win`)
- [ ] ยืนยัน USB-TMC endpoint address (`0x01`/`0x81` เป็นค่าสมมติ)

### แก้ปัญหาที่พบบ่อย

**ตัวอักษรไทยขึ้นเป็นกล่องสี่เหลี่ยม `□□□`**
```bash
sudo apt install -y fonts-thai-tlwg
```
แล้วปิด-เปิดโปรแกรมใหม่

**`undefined reference to vtable for ClassName`**
คลาสนั้นมี `Q_OBJECT` แต่ยังไม่ได้เพิ่มเข้า `CMakeLists.txt` หรือไม่มี
`#include "ClassName.moc"` ท้ายไฟล์

**`AutoMoc error: does not include "xxx.moc"`**
เพิ่ม `#include "xxx.moc"` บรรทัดสุดท้ายของไฟล์นั้น

**Build ช้ามาก**
ย้ายไฟล์จาก `/mnt/d/...` เข้า `~/scopecpp` (WSL filesystem) ก่อน

---

## หมายเหตุร่วมทุกเวอร์ชัน

- คำสั่ง SCPI ทั้งหมดเหมือนกันทุกตัวอักษรในทั้งสามเวอร์ชัน (ทดสอบกับ
  DHO814 จริงผ่าน Tkinter/PyQt6 แล้ว)
- รุ่นอื่นของ RIGOL อาจใช้คำสั่งต่างกันบ้าง เช่น DHO800 ใช้ `:AUTOSet`
  แทน `:AUToscale` ของ DS1000Z — ถ้าใช้รุ่นอื่นให้ทดสอบผ่าน SCPI
  Console ในโปรแกรมก่อนใช้งานจริง
- เครื่องที่ทดสอบ: RIGOL DHO814 ผ่าน USB, Windows + libusbK + pyvisa-py
