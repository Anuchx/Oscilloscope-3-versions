// gui_cpp/app.cpp
// Main window: Connection panel + Log + Tabs. Mirrors gui_tk/app.py's
// structure and behavior. Tabs call controller only through the
// runSafely/log callbacks defined here. No header.

#pragma once

#include <QMainWindow>
#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QLabel>
#include <QComboBox>
#include <QPushButton>
#include <QTabWidget>
#include <QTextEdit>
#include <QMessageBox>
#include <QDateTime>
#include <QTextCursor>
#include <QTextCharFormat>
#include <QCloseEvent>
#include <QColor>

#include <map>
#include <algorithm>

#include "../controller.cpp"
#include "workspace_tab.cpp"
#include "tools_tab.cpp"

namespace {
const std::map<std::string, QString> kErrorHints = {
    {"USB: no RIGOL device found",
     "ไม่พบออสซิลโลสโคป — ตรวจสอบสาย USB และการตั้งค่า USB passthrough ของ VM"},
    {"USB: bulk write failed", "ส่งคำสั่งไม่สำเร็จ — ตรวจสอบการเชื่อมต่อ USB"},
    {"USB: bulk read failed", "อ่านค่าไม่สำเร็จ — เครื่องอาจไม่ตอบสนองหรือ endpoint ไม่ตรง"},
    {"not connected", "ยังไม่ได้เชื่อมต่อกับออสซิลโลสโคป"},
};
}

class OscilloscopeApp : public QMainWindow {
    Q_OBJECT

public:
    explicit OscilloscopeApp(ScopeController& controller, QWidget* parent = nullptr)
        : QMainWindow(parent), controller_(controller) {
        setWindowTitle("Oscilloscope Controller (C++/Qt6)");
        resize(1100, 820);
        setMinimumSize(950, 700);

        auto* central = new QWidget(this);
        setCentralWidget(central);
        auto* layout = new QVBoxLayout(central);

        buildConnectionPanel(layout);
        buildLogPanel(layout);   // สร้างก่อน tabs เพื่อจองพื้นที่เสมอ (เหมือน Tkinter/PyQt6)
        buildTabs(layout);

        setTabsEnabled(false);
    }

    // logger เรียกใช้จาก tab ผ่าน lambda — public เพื่อให้ WorkspaceTab/ToolsTab เรียกได้
    void log(const QString& message, const QString& level = "info") {
        QString color = "#dddddd";
        if (level == "ok") color = "#8ce99a";
        else if (level == "error") color = "#ff6b6b";

        QString timestamp = QDateTime::currentDateTime().toString("HH:mm:ss");

        QTextCharFormat fmt;
        fmt.setForeground(QColor(color));

        QTextCursor cursor = logText_->textCursor();
        cursor.movePosition(QTextCursor::MoveOperation::End);
        cursor.setCharFormat(fmt);
        cursor.insertText(QString("[%1] %2\n").arg(timestamp, message));

        logText_->setTextCursor(cursor);
        logText_->ensureCursorVisible();
    }

    // เรียก action ของ controller พร้อมดัก ScopeError — ให้ tab ใช้ผ่าน std::function
    bool runSafely(std::function<void()> action, const QString& successMessage) {
        try {
            action();
            if (!successMessage.isEmpty()) {
                log(successMessage, "ok");
            }
            return true;
        } catch (const ScopeError& exc) {
            QString message = friendlyError(exc);
            QMessageBox::critical(this, "เกิดข้อผิดพลาด", message);
            log(message, "error");
            return false;
        }
    }

protected:
    void closeEvent(QCloseEvent* event) override {
        controller_.disconnect();
        event->accept();
    }

private slots:
    void onScan() {
        // libusb ไม่มีแนวคิด "list resources" แบบ VISA ตรงๆ
        // แจ้งผู้ใช้ให้กด Connect ตรงๆ เลย (ScopeController::connect ค้นหาอุปกรณ์ RIGOL ให้อัตโนมัติ)
        log("โหมด USB (libusb): ไม่ต้อง Scan — กด Connect เพื่อค้นหาและเชื่อมต่ออุปกรณ์ RIGOL อัตโนมัติ", "info");
        addressBox_->clear();
        addressBox_->addItem(""); // ว่าง = auto-detect
        addressBox_->addItem("1AB1:044C"); // ค่า default ของ DHO814 ระบุตรงๆ ได้ถ้า auto-detect ไม่เจอ
    }

    void onConnect() {
        QString address = addressBox_->currentText().trimmed();

        std::string idn;
        bool ok = runSafely(
            [this, &address, &idn] { idn = controller_.connect(address.toStdString()); },
            ""
        );
        if (ok) {
            log(QString("Connected: %1").arg(QString::fromStdString(idn)), "ok");
            setConnectionIndicator(true);
            btnConnect_->setEnabled(false);
            btnDisconnect_->setEnabled(true);
            setTabsEnabled(true);
        }
    }

    void onDisconnect() {
        controller_.disconnect();
        log("Disconnected", "info");
        setConnectionIndicator(false);
        btnConnect_->setEnabled(true);
        btnDisconnect_->setEnabled(false);
        setTabsEnabled(false);
    }

private:
    void buildConnectionPanel(QVBoxLayout* parentLayout) {
        auto* group = new QGroupBox("Connection", this);
        auto* row = new QHBoxLayout(group);

        row->addWidget(new QLabel("VID:PID (USB):", group));

        addressBox_ = new QComboBox(group);
        addressBox_->setEditable(true);
        addressBox_->addItem("");          // ว่าง = auto-detect อุปกรณ์ RIGOL ตัวแรก
        addressBox_->addItem("1AB1:044C"); // DHO814 default
        addressBox_->setMinimumWidth(200);
        row->addWidget(addressBox_);

        btnScan_ = new QPushButton("Scan", group);
        connect(btnScan_, &QPushButton::clicked, this, &OscilloscopeApp::onScan);
        row->addWidget(btnScan_);

        btnConnect_ = new QPushButton("Connect", group);
        connect(btnConnect_, &QPushButton::clicked, this, &OscilloscopeApp::onConnect);
        row->addWidget(btnConnect_);

        btnDisconnect_ = new QPushButton("Disconnect", group);
        btnDisconnect_->setEnabled(false);
        connect(btnDisconnect_, &QPushButton::clicked, this, &OscilloscopeApp::onDisconnect);
        row->addWidget(btnDisconnect_);

        statusLabel_ = new QLabel("● Not connected", group);
        row->addWidget(statusLabel_);

        row->addStretch();
        parentLayout->addWidget(group);
    }

    void buildLogPanel(QVBoxLayout* parentLayout) {
        auto* group = new QGroupBox("Log", this);
        auto* layout = new QVBoxLayout(group);

        logText_ = new QTextEdit(group);
        logText_->setReadOnly(true);
        logText_->setFixedHeight(70);
        logText_->setStyleSheet(
            "background-color: #1e1e1e; color: #dddddd; "
            "font-family: Consolas, monospace; font-size: 9pt;"
        );
        layout->addWidget(logText_);

        parentLayout->addWidget(group);
        log("โปรแกรมเริ่มทำงาน", "info");
        log("โปรเจกต์นี้ใช้ libusb ต่อผ่าน USB เท่านั้น (ไม่มี LAN backend)", "info");
    }

    void buildTabs(QVBoxLayout* parentLayout) {
        tabs_ = new QTabWidget(this);

        WorkspaceTab::Logger logger = [this](const QString& msg, const QString& level) { log(msg, level); };
        WorkspaceTab::RunSafely runSafelyFn =
            [this](std::function<void()> action, const QString& msg) { return runSafely(action, msg); };

        workspaceTab_ = new WorkspaceTab(controller_, logger, runSafelyFn);
        toolsTab_ = new ToolsTab(controller_, logger, runSafelyFn);

        tabs_->addTab(workspaceTab_, "Workspace");
        tabs_->addTab(toolsTab_, "Tools");

        parentLayout->addWidget(tabs_, 1);
    }

    void setConnectionIndicator(bool connected) {
        QString color = connected ? "#2ecc71" : "#888888";
        QString text = connected ? "● Connected" : "● Not connected";
        statusLabel_->setText(text);
        statusLabel_->setStyleSheet(QString("color: %1;").arg(color));
    }

    void setTabsEnabled(bool enabled) {
        workspaceTab_->setEnabledState(enabled);
        toolsTab_->setEnabledState(enabled);
    }

    QString friendlyError(const std::exception& exc) {
        QString text = QString::fromStdString(exc.what());
        for (const auto& pair : kErrorHints) {
            if (text.contains(QString::fromStdString(pair.first))) {
                return pair.second;
            }
        }
        return text;
    }

    ScopeController& controller_;

    QComboBox* addressBox_;
    QPushButton* btnScan_;
    QPushButton* btnConnect_;
    QPushButton* btnDisconnect_;
    QLabel* statusLabel_;

    QTextEdit* logText_;
    QTabWidget* tabs_;
    WorkspaceTab* workspaceTab_;
    ToolsTab* toolsTab_;
};
#include "app.moc"
