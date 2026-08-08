// controller.cpp
// Backend layer: hardware communication with RIGOL oscilloscope via SCPI.
// Mirrors controller.py's ScopeController class method-for-method.
// Uses libusb directly with hand-rolled USB-TMC framing (no NI-VISA).
// No Qt/UI code in this file — declaration and implementation both live
// here since the project intentionally has no header files.

#pragma once

#include <string>
#include <vector>
#include <optional>
#include <stdexcept>
#include <cstring>
#include <sstream>
#include <algorithm>

#include <libusb-1.0/libusb.h>

// เทียบเท่ากับ ScopeError ใน controller.py
class ScopeError : public std::runtime_error {
public:
    explicit ScopeError(const std::string& message) : std::runtime_error(message) {}
};

class ScopeController {
public:
    ScopeController()
        : ctx_(nullptr), handle_(nullptr), connected_(false),
          timeoutMs_(5000), currentTag_(0), endpointOut_(0), endpointIn_(0),
          interfaceNumber_(0) {
        if (libusb_init(&ctx_) < 0) {
            throw ScopeError("libusb_init failed");
        }
    }

    ~ScopeController() {
        disconnect();
        if (ctx_) {
            libusb_exit(ctx_);
        }
    }

    ScopeController(const ScopeController&) = delete;
    ScopeController& operator=(const ScopeController&) = delete;

    // ---------- Connection ----------

    // address รูปแบบ "VID:PID" เช่น "1AB1:044C" (ค่า default ของ DHO814)
    // หรือส่งสตริงว่างเพื่อให้ค้นหาอุปกรณ์ RIGOL ตัวแรกที่เจอ
    std::string connect(const std::string& address, int timeoutMs = 5000) {
        timeoutMs_ = timeoutMs;

        int vid = kRigolVid;
        int pid = -1; // -1 หมายถึง "หาอุปกรณ์ RIGOL ตัวแรกที่เจอ ไม่สนใจ PID"

        if (!address.empty()) {
            size_t colonPos = address.find(':');
            if (colonPos != std::string::npos) {
                vid = std::stoi(address.substr(0, colonPos), nullptr, 16);
                pid = std::stoi(address.substr(colonPos + 1), nullptr, 16);
            }
        }

        libusb_device** deviceList;
        ssize_t count = libusb_get_device_list(ctx_, &deviceList);
        if (count < 0) {
            throw ScopeError("USB: cannot list devices");
        }

        libusb_device* target = nullptr;
        for (ssize_t i = 0; i < count; ++i) {
            struct libusb_device_descriptor desc;
            if (libusb_get_device_descriptor(deviceList[i], &desc) != 0) continue;
            if (desc.idVendor == vid && (pid == -1 || desc.idProduct == pid)) {
                target = deviceList[i];
                break;
            }
        }

        if (!target) {
            libusb_free_device_list(deviceList, 1);
            std::ostringstream oss;
            oss << "USB: no RIGOL device found (VID 0x" << std::hex << vid
                << ") — check the cable and USB passthrough to this VM";
            throw ScopeError(oss.str());
        }

        int status = libusb_open(target, &handle_);
        libusb_free_device_list(deviceList, 1);

        if (status != LIBUSB_SUCCESS) {
            throw ScopeError(std::string("USB: libusb_open failed: ") + libusb_error_name(status));
        }

        interfaceNumber_ = 0; // เครื่องมือวัดส่วนใหญ่ใช้ interface 0 สำหรับ USB-TMC

        if (libusb_kernel_driver_active(handle_, interfaceNumber_) == 1) {
            libusb_detach_kernel_driver(handle_, interfaceNumber_);
        }

        status = libusb_claim_interface(handle_, interfaceNumber_);
        if (status != LIBUSB_SUCCESS) {
            libusb_close(handle_);
            handle_ = nullptr;
            throw ScopeError(std::string("USB: cannot claim interface: ") + libusb_error_name(status));
        }

        // endpoint มาตรฐานของ USB-TMC ส่วนใหญ่ (รวม RIGOL) — ถ้าไม่ตรงให้เช็คด้วย
        // `lsusb -v -d 1ab1:044c | grep bEndpointAddress` แล้วแก้ตรงนี้
        endpointOut_ = 0x01;
        endpointIn_ = 0x81;

        connected_ = true;
        return query("*IDN?");
    }

    void disconnect() {
        if (handle_) {
            libusb_release_interface(handle_, interfaceNumber_);
            libusb_close(handle_);
            handle_ = nullptr;
        }
        connected_ = false;
    }

    bool isConnected() const {
        return connected_;
    }

    // ---------- Low-level SCPI ----------

    void write(const std::string& command) {
        requireConnection();
        std::string cmd = command + "\n";
        std::vector<uint8_t> payload(cmd.begin(), cmd.end());
        sendBulkOut(payload);
    }

    std::string query(const std::string& command) {
        requireConnection();
        write(command);
        std::vector<uint8_t> data = receiveBulkIn(65536);
        std::string result(data.begin(), data.end());
        while (!result.empty() && (result.back() == '\n' || result.back() == '\r' || result.back() == ' ')) {
            result.pop_back();
        }
        return result;
    }

    // ---------- Channel ----------

    void setChannelDisplay(int channel, bool on) {
        write(":CHANnel" + std::to_string(channel) + ":DISPlay " + (on ? "ON" : "OFF"));
    }

    void setChannelCoupling(int channel, const std::string& coupling) {
        write(":CHANnel" + std::to_string(channel) + ":COUPling " + coupling);
    }

    void setVoltageScale(int channel, double voltsPerDiv) {
        write(":CHANnel" + std::to_string(channel) + ":SCALe " + std::to_string(voltsPerDiv));
    }

    double getVoltageScale(int channel) {
        return std::stod(query(":CHANnel" + std::to_string(channel) + ":SCALe?"));
    }

    void setChannelOffset(int channel, double offset) {
        write(":CHANnel" + std::to_string(channel) + ":OFFSet " + std::to_string(offset));
    }

    // ---------- Timebase ----------

    void setTimeScale(double secondsPerDiv) {
        write(":TIMebase:MAIN:SCALe " + std::to_string(secondsPerDiv));
    }

    double getTimeScale() {
        return std::stod(query(":TIMebase:MAIN:SCALe?"));
    }

    // ---------- Acquisition ----------

    void run() { write(":RUN"); }
    void stop() { write(":STOP"); }
    void single() { write(":SINGle"); }
    void autoscale() { write(":AUTOSet"); }

    // ---------- Trigger ----------

    void setTriggerSource(int channel) {
        write(":TRIGger:EDGE:SOURce CHANnel" + std::to_string(channel));
    }

    void setTriggerSlope(const std::string& slope) {
        write(":TRIGger:EDGE:SLOPe " + slope);
    }

    void setTriggerLevel(double level) {
        write(":TRIGger:EDGE:LEVel " + std::to_string(level));
    }

    void setTriggerMode(const std::string& mode) {
        write(":TRIGger:SWEep " + mode);
    }

    // ---------- Measurement ----------

    std::optional<double> measure(int channel, const std::string& item) {
        std::string response = query(":MEASure:ITEM? " + item + ",CHANnel" + std::to_string(channel));
        double value;
        try {
            value = std::stod(response);
        } catch (const std::exception&) {
            return std::nullopt;
        }
        // เครื่องคืนค่า 9.9e37 เมื่อวัดไม่ได้
        if (std::abs(value) > 1e37) {
            return std::nullopt;
        }
        return value;
    }

    // ---------- Screen capture ----------

    // คืนค่าเป็น bytes ของไฟล์ PNG
    std::vector<uint8_t> captureScreen() {
        requireConnection();
        write(":DISPlay:DATA?");
        return readRawFramed(1024 * 1024);
    }

    // ---------- Waveform ----------

    struct WaveformData {
        std::vector<double> times;
        std::vector<double> volts;
    };

    WaveformData readWaveform(int channel) {
        requireConnection();

        write(":WAVeform:SOURce CHANnel" + std::to_string(channel));
        write(":WAVeform:MODE NORMal");
        write(":WAVeform:FORMat BYTE");

        // preamble มี 10 ค่าคั่นด้วยจุลภาค: format,type,points,count,xinc,xorig,xref,yinc,yorig,yref
        std::string preambleStr = query(":WAVeform:PREamble?");
        std::vector<double> preamble;
        {
            std::stringstream ss(preambleStr);
            std::string field;
            while (std::getline(ss, field, ',')) {
                preamble.push_back(std::stod(field));
            }
        }
        if (preamble.size() < 10) {
            throw ScopeError("Unexpected preamble format: " + preambleStr);
        }

        double xIncrement = preamble[4];
        double xOrigin = preamble[5];
        double yIncrement = preamble[7];
        double yOrigin = preamble[8];
        double yReference = preamble[9];

        write(":WAVeform:DATA?");
        std::vector<uint8_t> raw = readRawFramed(1024 * 1024);

        WaveformData result;
        result.times.reserve(raw.size());
        result.volts.reserve(raw.size());

        for (size_t i = 0; i < raw.size(); ++i) {
            double time = xOrigin + static_cast<double>(i) * xIncrement;
            double volt = (static_cast<double>(raw[i]) - yReference - yOrigin) * yIncrement;
            result.times.push_back(time);
            result.volts.push_back(volt);
        }

        return result;
    }

private:
    static constexpr int kRigolVid = 0x1AB1;
    static constexpr uint8_t kDevDepMsgOut = 1;
    static constexpr uint8_t kRequestDevDepMsgIn = 2;

    void requireConnection() const {
        if (!connected_) {
            throw ScopeError("Oscilloscope is not connected");
        }
    }

    uint8_t nextTag() {
        currentTag_++;
        if (currentTag_ == 0) currentTag_ = 1; // tag ต้องไม่เป็น 0 ตามสเปก USBTMC
        return currentTag_;
    }

    void sendBulkOut(const std::vector<uint8_t>& payload) {
        uint8_t tag = nextTag();

        // USB-TMC DEV_DEP_MSG_OUT header: 12 bytes
        std::vector<uint8_t> header(12, 0);
        header[0] = kDevDepMsgOut;
        header[1] = tag;
        header[2] = static_cast<uint8_t>(~tag);
        header[3] = 0;

        uint32_t transferSize = static_cast<uint32_t>(payload.size());
        header[4] = transferSize & 0xFF;
        header[5] = (transferSize >> 8) & 0xFF;
        header[6] = (transferSize >> 16) & 0xFF;
        header[7] = (transferSize >> 24) & 0xFF;
        header[8] = 0x01; // EOM bit — ทุกคำสั่งของเราจบในแพ็กเก็ตเดียวเสมอ

        std::vector<uint8_t> packet = header;
        packet.insert(packet.end(), payload.begin(), payload.end());

        while (packet.size() % 4 != 0) {
            packet.push_back(0);
        }

        int transferred = 0;
        int status = libusb_bulk_transfer(
            handle_, endpointOut_, packet.data(), static_cast<int>(packet.size()),
            &transferred, timeoutMs_
        );
        if (status != LIBUSB_SUCCESS) {
            throw ScopeError(std::string("USB: bulk write failed: ") + libusb_error_name(status));
        }
    }

    std::vector<uint8_t> receiveBulkIn(size_t maxLength) {
        uint8_t tag = nextTag();

        std::vector<uint8_t> requestHeader(12, 0);
        requestHeader[0] = kRequestDevDepMsgIn;
        requestHeader[1] = tag;
        requestHeader[2] = static_cast<uint8_t>(~tag);
        requestHeader[3] = 0;

        uint32_t requestedSize = static_cast<uint32_t>(maxLength);
        requestHeader[4] = requestedSize & 0xFF;
        requestHeader[5] = (requestedSize >> 8) & 0xFF;
        requestHeader[6] = (requestedSize >> 16) & 0xFF;
        requestHeader[7] = (requestedSize >> 24) & 0xFF;

        int transferred = 0;
        int status = libusb_bulk_transfer(
            handle_, endpointOut_, requestHeader.data(), static_cast<int>(requestHeader.size()),
            &transferred, timeoutMs_
        );
        if (status != LIBUSB_SUCCESS) {
            throw ScopeError(std::string("USB: request-in failed: ") + libusb_error_name(status));
        }

        std::vector<uint8_t> buffer(maxLength + 12);
        status = libusb_bulk_transfer(
            handle_, endpointIn_, buffer.data(), static_cast<int>(buffer.size()),
            &transferred, timeoutMs_
        );
        if (status != LIBUSB_SUCCESS) {
            throw ScopeError(std::string("USB: bulk read failed: ") + libusb_error_name(status));
        }

        if (transferred < 12) {
            throw ScopeError("USB: response too short to contain TMC header");
        }

        uint32_t actualSize = buffer[4] | (buffer[5] << 8) | (buffer[6] << 16) | (buffer[7] << 24);
        size_t available = static_cast<size_t>(transferred) - 12;
        size_t dataSize = std::min(static_cast<size_t>(actualSize), available);

        return std::vector<uint8_t>(buffer.begin() + 12, buffer.begin() + 12 + dataSize);
    }

    // อ่านข้อมูลที่มี TMC "#<n><length><data>" header ครอบอยู่ (screen capture / waveform data)
    // วนขอเพิ่มถ้าก้อนแรกยังไม่ครบตามที่ header บอกไว้
    std::vector<uint8_t> readRawFramed(size_t chunkSize) {
        std::vector<uint8_t> raw = receiveBulkIn(chunkSize);

        if (raw.empty() || raw[0] != '#') {
            throw ScopeError("USB: unexpected data format (no # header)");
        }
        int digits = raw[1] - '0';
        size_t headerLen = 2 + digits;

        if (raw.size() < headerLen) {
            throw ScopeError("USB: header incomplete");
        }

        std::string lengthStr(raw.begin() + 2, raw.begin() + headerLen);
        size_t dataLength = std::stoul(lengthStr);
        size_t totalExpected = headerLen + dataLength;

        while (raw.size() < totalExpected) {
            std::vector<uint8_t> more = receiveBulkIn(chunkSize);
            if (more.empty()) {
                throw ScopeError(
                    "USB: data incomplete (got " + std::to_string(raw.size() - headerLen) +
                    " of " + std::to_string(dataLength) + " bytes)"
                );
            }
            raw.insert(raw.end(), more.begin(), more.end());
        }

        return std::vector<uint8_t>(raw.begin() + headerLen, raw.begin() + totalExpected);
    }

    libusb_context* ctx_;
    libusb_device_handle* handle_;
    bool connected_;
    int timeoutMs_;
    uint8_t currentTag_;
    uint8_t endpointOut_;
    uint8_t endpointIn_;
    int interfaceNumber_;
};