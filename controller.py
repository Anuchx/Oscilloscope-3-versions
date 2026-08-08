"""Backend layer: hardware communication with RIGOL oscilloscope via SCPI."""

import pyvisa


class ScopeError(Exception):
    """Raised when a scope operation fails."""
    pass


class ScopeController:
    """Controls a RIGOL oscilloscope over VISA. Contains no UI code."""

    def __init__(self):
        self.rm = pyvisa.ResourceManager("@py")
        self.scope = None

    # ---------- Connection ----------

    def list_resources(self):
        """คืนรายการ VISA address ที่พบในระบบ"""
        try:
            return list(self.rm.list_resources())
        except Exception as exc:
            raise ScopeError(f"Cannot list resources: {exc}")

    def connect(self, address, timeout=5000):
        """เชื่อมต่อกับเครื่อง คืนค่า IDN string"""
        try:
            self.scope = self.rm.open_resource(address)
            self.scope.timeout = timeout
            return self.query("*IDN?")
        except Exception as exc:
            self.scope = None
            raise ScopeError(f"Connection failed: {exc}")

    def disconnect(self):
        if self.scope is not None:
            try:
                self.scope.close()
            except Exception:
                pass
            finally:
                self.scope = None

    def is_connected(self):
        return self.scope is not None

    # ---------- Low-level SCPI ----------

    def write(self, command):
        self._require_connection()
        try:
            self.scope.write(command)
        except Exception as exc:
            raise ScopeError(f"Write failed ({command}): {exc}")

    def query(self, command):
        self._require_connection()
        try:
            return self.scope.query(command).strip()
        except Exception as exc:
            raise ScopeError(f"Query failed ({command}): {exc}")

    def _require_connection(self):
        if self.scope is None:
            raise ScopeError("Oscilloscope is not connected")

    # ---------- Channel ----------

    def set_channel_display(self, channel, on):
        self.write(f":CHANnel{channel}:DISPlay {'ON' if on else 'OFF'}")

    def set_channel_coupling(self, channel, coupling):
        """coupling: AC, DC หรือ GND"""
        self.write(f":CHANnel{channel}:COUPling {coupling}")

    def set_voltage_scale(self, channel, volts_per_div):
        self.write(f":CHANnel{channel}:SCALe {volts_per_div}")

    def get_voltage_scale(self, channel):
        return float(self.query(f":CHANnel{channel}:SCALe?"))

    def set_channel_offset(self, channel, offset):
        self.write(f":CHANnel{channel}:OFFSet {offset}")

    # ---------- Timebase ----------

    def set_time_scale(self, seconds_per_div):
        self.write(f":TIMebase:MAIN:SCALe {seconds_per_div}")

    def get_time_scale(self):
        return float(self.query(":TIMebase:MAIN:SCALe?"))

    # ---------- Acquisition ----------

    def run(self):
        self.write(":RUN")

    def stop(self):
        self.write(":STOP")

    def single(self):
        self.write(":SINGle")

    def autoscale(self):
        self.write(":AUTOSet")

    # ---------- Trigger ----------

    def set_trigger_source(self, channel):
        self.write(f":TRIGger:EDGE:SOURce CHANnel{channel}")

    def set_trigger_slope(self, slope):
        """slope: POSitive หรือ NEGative"""
        self.write(f":TRIGger:EDGE:SLOPe {slope}")

    def set_trigger_level(self, level):
        self.write(f":TRIGger:EDGE:LEVel {level}")

    def set_trigger_mode(self, mode):
        """mode: AUTO, NORMal หรือ SINGle"""
        self.write(f":TRIGger:SWEep {mode}")

    # ---------- Measurement ----------

    def measure(self, channel, item):
        """
        อ่านค่าวัดหนึ่งรายการ เช่น VPP, VMAX, VMIN, FREQuency, PERiod
        คืนค่าเป็น float หรือ None ถ้าเครื่องวัดไม่ได้
        """
        raw = self.query(f":MEASure:ITEM? {item},CHANnel{channel}")
        try:
            value = float(raw)
        except ValueError:
            return None
        # เครื่องคืนค่า 9.9e37 เมื่อวัดไม่ได้
        return None if abs(value) > 1e37 else value

    # ---------- Screen capture ----------

    def capture_screen(self):
        """
        ดึงภาพหน้าจอจากเครื่อง คืนค่าเป็น bytes ของไฟล์ PNG
        DHO800 ซีรีส์ใช้ :DISPlay:DATA? โดยไม่มีพารามิเตอร์
        """
        self._require_connection()

        original_timeout = self.scope.timeout
        original_chunk = self.scope.chunk_size
        self.scope.timeout = 20000
        self.scope.chunk_size = 1024 * 1024  # เพิ่ม chunk ให้โตพอสำหรับภาพขนาดใหญ่
        try:
            self.write(":DISPlay:DATA?")
            data = self.scope.read_raw()
        except Exception as exc:
            raise ScopeError(f"Screen capture failed: {exc}")
        finally:
            self.scope.timeout = original_timeout
            self.scope.chunk_size = original_chunk

        if data[:1] != b"#":
            raise ScopeError(f"Unexpected screen data format (got {data[:20]!r})")

        digits = int(data[1:2])
        start = 2 + digits
        length = int(data[2:start])
        payload = data[start:start + length]

        if len(payload) < length:
            raise ScopeError(
                f"Screen data incomplete: expected {length} bytes, got {len(payload)}"
            )

        return payload

    # ---------- Waveform ----------

    def read_waveform(self, channel):
        """
        อ่านข้อมูลรูปคลื่นจากหน้าจอ คืนค่าเป็น (time_list, voltage_list)
        ใช้โหมด NORMal ซึ่งได้ข้อมูลเท่าที่แสดงบนจอ (1200 จุด)
        """
        self._require_connection()

        self.write(f":WAVeform:SOURce CHANnel{channel}")
        self.write(":WAVeform:MODE NORMal")
        self.write(":WAVeform:FORMat BYTE")

        # preamble มี 10 ค่า: format,type,points,count,xinc,xorig,xref,yinc,yorig,yref
        preamble = self.query(":WAVeform:PREamble?").split(",")
        x_increment = float(preamble[4])
        x_origin = float(preamble[5])
        y_increment = float(preamble[7])
        y_origin = float(preamble[8])
        y_reference = float(preamble[9])

        try:
            raw = self.scope.query_binary_values(
                ":WAVeform:DATA?", datatype="B", container=list
            )
        except Exception as exc:
            raise ScopeError(f"Waveform read failed: {exc}")

        times = [x_origin + i * x_increment for i in range(len(raw))]
        volts = [(value - y_reference - y_origin) * y_increment for value in raw]
        return times, volts