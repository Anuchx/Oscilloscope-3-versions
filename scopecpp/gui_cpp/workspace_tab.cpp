// gui_cpp/workspace_tab.cpp
// Workspace tab: all frequently-adjusted controls on the left, waveform +
// measurement + SCPI console on the right. Mirrors gui_tk/workspace_tab.py
// feature-for-feature. Only calls controller methods, config_manager, and
// the logger/runSafely callbacks passed in. No header.

#pragma once

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>
#include <QGroupBox>
#include <QLabel>
#include <QComboBox>
#include <QCheckBox>
#include <QLineEdit>
#include <QPushButton>
#include <QTreeWidget>
#include <QTreeWidgetItem>
#include <QTextEdit>
#include <QFileDialog>
#include <QTimer>
#include <QColor>

#include <functional>
#include <fstream>
#include <sstream>
#include <vector>

#include "../controller.cpp"
#include "../config_manager.cpp"
#include "waveform_widget.cpp"

namespace {
const QStringList kChannels = {"1", "2", "3", "4"};
const QStringList kVoltScales = {"0.01", "0.05", "0.1", "0.5", "1", "2", "5"};
const QStringList kTimeScales = {"1e-6", "1e-5", "1e-4", "1e-3", "1e-2", "0.1", "1"};
const QStringList kCouplings = {"DC", "AC", "GND"};
const QStringList kSlopes = {"POSitive", "NEGative"};
const QStringList kTriggerModes = {"AUTO", "NORMal", "SINGle"};
const QStringList kRefreshIntervals = {"1", "2", "5", "10"};

const std::vector<std::pair<QString, std::string>> kMeasurementItems = {
    {"Vpp", "VPP"}, {"Vmax", "VMAX"}, {"Vmin", "VMIN"},
    {"Vrms", "VRMS"}, {"Frequency", "FREQuency"}, {"Period", "PERiod"},
};

const std::vector<std::pair<QString, std::string>> kConsolePresets = {
    {"*IDN? (ข้อมูลเครื่อง)", "*IDN?"},
    {"*RST (รีเซ็ตเครื่อง)", "*RST"},
    {":RUN", ":RUN"},
    {":STOP", ":STOP"},
    {":AUTOSet", ":AUTOSet"},
    {":CHANnel1:SCALe?", ":CHANnel1:SCALe?"},
    {":TIMebase:MAIN:SCALe?", ":TIMebase:MAIN:SCALe?"},
    {":MEASure:ITEM? VPP,CHANnel1", ":MEASure:ITEM? VPP,CHANnel1"},
};
}

class WorkspaceTab : public QWidget {
    Q_OBJECT

public:
    using Logger = std::function<void(const QString&, const QString&)>;
    // runSafely: รับ action กับ success message คืน true ถ้าสำเร็จ (ดักจับ ScopeError ให้)
    using RunSafely = std::function<bool(std::function<void()>, const QString&)>;

    WorkspaceTab(ScopeController& controller, Logger logger, RunSafely runSafely, QWidget* parent = nullptr)
        : QWidget(parent), controller_(controller), log_(std::move(logger)), runSafely_(std::move(runSafely)) {

        autoRefreshTimer_ = new QTimer(this);
        connect(autoRefreshTimer_, &QTimer::timeout, this, &WorkspaceTab::onMeasure);

        auto* rootLayout = new QHBoxLayout(this);

        auto* leftWidget = new QWidget(this);
        auto* leftLayout = new QVBoxLayout(leftWidget);
        leftWidget->setFixedWidth(230);

        buildAcquisitionPanel(leftLayout);
        buildChannelPanel(leftLayout);
        buildTimebasePanel(leftLayout);
        buildTriggerPanel(leftLayout);
        leftLayout->addStretch();

        auto* rightWidget = new QWidget(this);
        auto* rightLayout = new QVBoxLayout(rightWidget);

        buildWaveformPanel(rightLayout);
        buildMeasurementPanel(rightLayout);
        buildConsolePanel(rightLayout);

        rootLayout->addWidget(leftWidget);
        rootLayout->addWidget(rightWidget, 1);
    }

    void setEnabledState(bool enabled) {
        acquisitionGroup_->setEnabled(enabled);
        channelGroup_->setEnabled(enabled);
        timebaseGroup_->setEnabled(enabled);
        triggerGroup_->setEnabled(enabled);

        btnRead_->setEnabled(enabled);
        btnExport_->setEnabled(enabled);
        btnSaveConfig_->setEnabled(enabled);
        btnLoadConfig_->setEnabled(enabled);
        btnMeasure_->setEnabled(enabled);
        autoRefreshCheck_->setEnabled(enabled);
        refreshIntervalBox_->setEnabled(enabled);

        presetBox_->setEnabled(enabled);
        consoleCommandEdit_->setEnabled(enabled);
        btnConsoleSend_->setEnabled(enabled);
        btnConsoleClear_->setEnabled(enabled);

        if (!enabled && autoRefreshTimer_->isActive()) {
            autoRefreshCheck_->setChecked(false);
            autoRefreshTimer_->stop();
        }
    }

private:
    // ---------- UI construction: left column ----------

    void buildAcquisitionPanel(QVBoxLayout* parentLayout) {
        acquisitionGroup_ = new QGroupBox("Acquisition", this);
        auto* grid = new QGridLayout(acquisitionGroup_);

        btnRun_ = new QPushButton("Run", acquisitionGroup_);
        btnStop_ = new QPushButton("Stop", acquisitionGroup_);
        btnSingle_ = new QPushButton("Single", acquisitionGroup_);
        btnAutoscale_ = new QPushButton("Autoscale", acquisitionGroup_);

        connect(btnRun_, &QPushButton::clicked, this, &WorkspaceTab::onRun);
        connect(btnStop_, &QPushButton::clicked, this, &WorkspaceTab::onStop);
        connect(btnSingle_, &QPushButton::clicked, this, &WorkspaceTab::onSingle);
        connect(btnAutoscale_, &QPushButton::clicked, this, &WorkspaceTab::onAutoscale);

        grid->addWidget(btnRun_, 0, 0);
        grid->addWidget(btnStop_, 0, 1);
        grid->addWidget(btnSingle_, 1, 0);
        grid->addWidget(btnAutoscale_, 1, 1);

        parentLayout->addWidget(acquisitionGroup_);
    }

    void buildChannelPanel(QVBoxLayout* parentLayout) {
        channelGroup_ = new QGroupBox("Channel", this);
        auto* grid = new QGridLayout(channelGroup_);

        grid->addWidget(new QLabel("Channel:", channelGroup_), 0, 0);
        channelBox_ = new QComboBox(channelGroup_);
        channelBox_->addItems(kChannels);
        grid->addWidget(channelBox_, 0, 1);

        displayCheck_ = new QCheckBox("Display", channelGroup_);
        displayCheck_->setChecked(true);
        connect(displayCheck_, &QCheckBox::toggled, this, &WorkspaceTab::onDisplayToggle);
        grid->addWidget(displayCheck_, 1, 0, 1, 2);

        grid->addWidget(new QLabel("Coupling:", channelGroup_), 2, 0);
        couplingBox_ = new QComboBox(channelGroup_);
        couplingBox_->addItems(kCouplings);
        connect(couplingBox_, &QComboBox::currentTextChanged, this, &WorkspaceTab::onCouplingChange);
        grid->addWidget(couplingBox_, 2, 1);

        grid->addWidget(new QLabel("V/div:", channelGroup_), 3, 0);
        voltBox_ = new QComboBox(channelGroup_);
        voltBox_->addItems(kVoltScales);
        voltBox_->setCurrentText("1");
        connect(voltBox_, &QComboBox::currentTextChanged, this, &WorkspaceTab::onVoltChange);
        grid->addWidget(voltBox_, 3, 1);

        grid->addWidget(new QLabel("Offset:", channelGroup_), 4, 0);
        offsetEdit_ = new QLineEdit("0", channelGroup_);
        connect(offsetEdit_, &QLineEdit::returnPressed, this, &WorkspaceTab::onOffsetChange);
        grid->addWidget(offsetEdit_, 4, 1);

        btnOffsetApply_ = new QPushButton("ตั้งค่า Offset", channelGroup_);
        connect(btnOffsetApply_, &QPushButton::clicked, this, &WorkspaceTab::onOffsetChange);
        grid->addWidget(btnOffsetApply_, 5, 0, 1, 2);

        parentLayout->addWidget(channelGroup_);
    }

    void buildTimebasePanel(QVBoxLayout* parentLayout) {
        timebaseGroup_ = new QGroupBox("Timebase", this);
        auto* grid = new QGridLayout(timebaseGroup_);

        grid->addWidget(new QLabel("Time/div:", timebaseGroup_), 0, 0);
        timeBox_ = new QComboBox(timebaseGroup_);
        timeBox_->addItems(kTimeScales);
        timeBox_->setCurrentText("1e-3");
        connect(timeBox_, &QComboBox::currentTextChanged, this, &WorkspaceTab::onTimeChange);
        grid->addWidget(timeBox_, 0, 1);

        parentLayout->addWidget(timebaseGroup_);
    }

    void buildTriggerPanel(QVBoxLayout* parentLayout) {
        triggerGroup_ = new QGroupBox("Trigger", this);
        auto* grid = new QGridLayout(triggerGroup_);

        grid->addWidget(new QLabel("Source:", triggerGroup_), 0, 0);
        trigSourceBox_ = new QComboBox(triggerGroup_);
        trigSourceBox_->addItems(kChannels);
        connect(trigSourceBox_, &QComboBox::currentTextChanged, this, &WorkspaceTab::onTriggerSourceChange);
        grid->addWidget(trigSourceBox_, 0, 1);

        grid->addWidget(new QLabel("Slope:", triggerGroup_), 1, 0);
        trigSlopeBox_ = new QComboBox(triggerGroup_);
        trigSlopeBox_->addItems(kSlopes);
        connect(trigSlopeBox_, &QComboBox::currentTextChanged, this, &WorkspaceTab::onTriggerSlopeChange);
        grid->addWidget(trigSlopeBox_, 1, 1);

        grid->addWidget(new QLabel("Level:", triggerGroup_), 2, 0);
        trigLevelEdit_ = new QLineEdit("0", triggerGroup_);
        connect(trigLevelEdit_, &QLineEdit::returnPressed, this, &WorkspaceTab::onTriggerLevelChange);
        grid->addWidget(trigLevelEdit_, 2, 1);

        grid->addWidget(new QLabel("Mode:", triggerGroup_), 3, 0);
        trigModeBox_ = new QComboBox(triggerGroup_);
        trigModeBox_->addItems(kTriggerModes);
        connect(trigModeBox_, &QComboBox::currentTextChanged, this, &WorkspaceTab::onTriggerModeChange);
        grid->addWidget(trigModeBox_, 3, 1);

        btnTriggerLevelApply_ = new QPushButton("ตั้งค่า Level", triggerGroup_);
        connect(btnTriggerLevelApply_, &QPushButton::clicked, this, &WorkspaceTab::onTriggerLevelChange);
        grid->addWidget(btnTriggerLevelApply_, 4, 0, 1, 2);

        parentLayout->addWidget(triggerGroup_);
    }

    // ---------- UI construction: right column ----------

    void buildWaveformPanel(QVBoxLayout* parentLayout) {
        auto* group = new QGroupBox("Waveform", this);
        auto* layout = new QVBoxLayout(group);

        auto* toolbar = new QHBoxLayout();
        btnRead_ = new QPushButton("Read Waveform", group);
        btnExport_ = new QPushButton("Export CSV", group);
        btnSaveConfig_ = new QPushButton("Save Config", group);
        btnLoadConfig_ = new QPushButton("Load Config", group);

        connect(btnRead_, &QPushButton::clicked, this, &WorkspaceTab::onReadWaveform);
        connect(btnExport_, &QPushButton::clicked, this, &WorkspaceTab::onExportCsv);
        connect(btnSaveConfig_, &QPushButton::clicked, this, &WorkspaceTab::onSaveConfig);
        connect(btnLoadConfig_, &QPushButton::clicked, this, &WorkspaceTab::onLoadConfig);

        toolbar->addWidget(btnRead_);
        toolbar->addWidget(btnExport_);
        toolbar->addWidget(btnSaveConfig_);
        toolbar->addWidget(btnLoadConfig_);
        toolbar->addStretch();
        layout->addLayout(toolbar);

        canvas_ = new WaveformWidget(group);
        layout->addWidget(canvas_);

        parentLayout->addWidget(group);
    }

    void buildMeasurementPanel(QVBoxLayout* parentLayout) {
        auto* group = new QGroupBox("Measurement", this);
        auto* layout = new QVBoxLayout(group);

        auto* toolbar = new QHBoxLayout();
        btnMeasure_ = new QPushButton("Measure", group);
        connect(btnMeasure_, &QPushButton::clicked, this, &WorkspaceTab::onMeasure);
        toolbar->addWidget(btnMeasure_);

        autoRefreshCheck_ = new QCheckBox("Auto-Refresh", group);
        connect(autoRefreshCheck_, &QCheckBox::toggled, this, &WorkspaceTab::onAutoRefreshToggle);
        toolbar->addWidget(autoRefreshCheck_);

        toolbar->addWidget(new QLabel("ทุก", group));
        refreshIntervalBox_ = new QComboBox(group);
        refreshIntervalBox_->addItems(kRefreshIntervals);
        refreshIntervalBox_->setCurrentText("2");
        toolbar->addWidget(refreshIntervalBox_);
        toolbar->addWidget(new QLabel("วิ", group));
        toolbar->addStretch();
        layout->addLayout(toolbar);

        table_ = new QTreeWidget(group);
        table_->setHeaderLabels({"Item", "Value"});
        table_->setRootIsDecorated(false);
        table_->setMaximumHeight(140);

        for (const auto& pair : kMeasurementItems) {
            auto* row = new QTreeWidgetItem({pair.first, "—"});
            table_->addTopLevelItem(row);
            rowItems_[pair.second] = row;
        }

        layout->addWidget(table_);
        parentLayout->addWidget(group);
    }

    void buildConsolePanel(QVBoxLayout* parentLayout) {
        auto* group = new QGroupBox("SCPI Console", this);
        auto* layout = new QVBoxLayout(group);

        auto* entryRow = new QGridLayout();
        entryRow->addWidget(new QLabel("Preset:", group), 0, 0);
        presetBox_ = new QComboBox(group);
        for (const auto& pair : kConsolePresets) {
            presetBox_->addItem(pair.first);
        }
        connect(presetBox_, &QComboBox::currentTextChanged, this, &WorkspaceTab::onConsolePresetSelected);
        entryRow->addWidget(presetBox_, 0, 1);

        consoleCommandEdit_ = new QLineEdit(group);
        connect(consoleCommandEdit_, &QLineEdit::returnPressed, this, &WorkspaceTab::onConsoleSend);
        entryRow->addWidget(consoleCommandEdit_, 0, 2);

        btnConsoleSend_ = new QPushButton("Send", group);
        connect(btnConsoleSend_, &QPushButton::clicked, this, &WorkspaceTab::onConsoleSend);
        entryRow->addWidget(btnConsoleSend_, 0, 3);

        btnConsoleClear_ = new QPushButton("Clear", group);
        connect(btnConsoleClear_, &QPushButton::clicked, this, &WorkspaceTab::onConsoleClear);
        entryRow->addWidget(btnConsoleClear_, 0, 4);

        entryRow->setColumnStretch(2, 1);
        layout->addLayout(entryRow);

        consoleResponse_ = new QTextEdit(group);
        consoleResponse_->setReadOnly(true);
        consoleResponse_->setMaximumHeight(90);
        consoleResponse_->setStyleSheet(
            "background-color: #1e1e1e; color: #dddddd; "
            "font-family: Consolas, monospace; font-size: 9pt;"
        );
        layout->addWidget(consoleResponse_);

        parentLayout->addWidget(group);
    }

    // ---------- Helpers ----------

    int currentChannel() const {
        return channelBox_->currentText().toInt();
    }

    static QString formatValue(const std::string& item, std::optional<double> value) {
        if (!value.has_value()) return "—";
        if (item == "FREQuency") return QString("%1 Hz").arg(*value, 0, 'f', 3);
        if (item == "PERiod") return QString("%1 ms").arg(*value * 1000, 0, 'f', 3);
        return QString("%1 V").arg(*value, 0, 'f', 3);
    }

    // ---------- Event handlers: acquisition ----------

    void onRun() {
        runSafely_([this] { controller_.run(); }, "Running");
    }

    void onStop() {
        runSafely_([this] { controller_.stop(); }, "Stopped");
    }

    void onSingle() {
        runSafely_([this] { controller_.single(); }, "Single trigger armed");
    }

    void onAutoscale() {
        runSafely_([this] { controller_.autoscale(); }, "Autoscale done");
    }

    // ---------- Event handlers: channel ----------

    void onDisplayToggle(bool checked) {
        int channel = currentChannel();
        runSafely_(
            [this, channel, checked] { controller_.setChannelDisplay(channel, checked); },
            QString("CH%1 display %2").arg(channel).arg(checked ? "ON" : "OFF")
        );
    }

    void onCouplingChange(const QString& coupling) {
        int channel = currentChannel();
        std::string couplingStr = coupling.toStdString();
        runSafely_(
            [this, channel, couplingStr] { controller_.setChannelCoupling(channel, couplingStr); },
            QString("CH%1 coupling = %2").arg(channel).arg(coupling)
        );
    }

    void onVoltChange(const QString& scale) {
        int channel = currentChannel();
        double value = scale.toDouble();
        runSafely_(
            [this, channel, value] { controller_.setVoltageScale(channel, value); },
            QString("CH%1 scale = %2 V/div").arg(channel).arg(value)
        );
    }

    void onOffsetChange() {
        int channel = currentChannel();
        bool ok = false;
        double offset = offsetEdit_->text().toDouble(&ok);
        if (!ok) {
            log_("ค่า Offset ต้องเป็นตัวเลข", "error");
            return;
        }
        runSafely_(
            [this, channel, offset] { controller_.setChannelOffset(channel, offset); },
            QString("CH%1 offset = %2 V").arg(channel).arg(offset)
        );
    }

    // ---------- Event handlers: timebase ----------

    void onTimeChange(const QString& scale) {
        double value = scale.toDouble();
        runSafely_(
            [this, value] { controller_.setTimeScale(value); },
            QString("Timebase = %1 s/div").arg(value)
        );
    }

    // ---------- Event handlers: trigger ----------

    void onTriggerSourceChange(const QString& channelStr) {
        int channel = channelStr.toInt();
        runSafely_(
            [this, channel] { controller_.setTriggerSource(channel); },
            QString("Trigger source = CH%1").arg(channel)
        );
    }

    void onTriggerSlopeChange(const QString& slope) {
        std::string slopeStr = slope.toStdString();
        runSafely_(
            [this, slopeStr] { controller_.setTriggerSlope(slopeStr); },
            QString("Trigger slope = %1").arg(slope)
        );
    }

    void onTriggerLevelChange() {
        bool ok = false;
        double level = trigLevelEdit_->text().toDouble(&ok);
        if (!ok) {
            log_("ค่า Trigger Level ต้องเป็นตัวเลข", "error");
            return;
        }
        runSafely_(
            [this, level] { controller_.setTriggerLevel(level); },
            QString("Trigger level = %1 V").arg(level)
        );
    }

    void onTriggerModeChange(const QString& mode) {
        std::string modeStr = mode.toStdString();
        runSafely_(
            [this, modeStr] { controller_.setTriggerMode(modeStr); },
            QString("Trigger mode = %1").arg(mode)
        );
    }

    // ---------- Event handlers: waveform / measurement ----------

    void onReadWaveform() {
        int channel = currentChannel();
        ScopeController::WaveformData data;
        bool ok = runSafely_(
            [this, channel, &data] { data = controller_.readWaveform(channel); },
            QString("Waveform read from CH%1").arg(channel)
        );
        if (ok) {
            lastTimes_ = data.times;
            lastVolts_ = data.volts;
            canvas_->setData(data.times, data.volts, channel);
        }
    }

    void onExportCsv() {
        if (lastVolts_.empty()) {
            log_("ยังไม่มีข้อมูล waveform ให้ export กด Read Waveform ก่อน", "error");
            return;
        }

        QString path = QFileDialog::getSaveFileName(this, "Export CSV", "waveform.csv", "CSV files (*.csv)");
        if (path.isEmpty()) return;

        std::ofstream file(path.toStdString());
        if (!file.is_open()) {
            log_("บันทึกไฟล์ไม่สำเร็จ", "error");
            return;
        }
        file << "time_s,voltage_v\n";
        for (size_t i = 0; i < lastTimes_.size(); ++i) {
            file << lastTimes_[i] << "," << lastVolts_[i] << "\n";
        }
        log_(QString("บันทึกไฟล์แล้ว: %1").arg(path), "ok");
    }

    void onMeasure() {
        int channel = currentChannel();
        for (const auto& pair : kMeasurementItems) {
            const std::string& item = pair.second;
            std::optional<double> value;
            runSafely_(
                [this, channel, item, &value] { value = controller_.measure(channel, item); },
                QString()
            );
            rowItems_[item]->setText(1, formatValue(item, value));
        }
        log_(QString("วัดค่าจาก CH%1 เสร็จแล้ว").arg(channel), "ok");
    }

    // ---------- Auto-refresh ----------

    void onAutoRefreshToggle(bool checked) {
        if (checked) {
            int intervalMs = static_cast<int>(refreshIntervalBox_->currentText().toDouble() * 1000);
            autoRefreshTimer_->start(intervalMs);
            onMeasure();
        } else {
            autoRefreshTimer_->stop();
        }
    }

    // ---------- Console ----------

    void onConsolePresetSelected(const QString& label) {
        for (const auto& pair : kConsolePresets) {
            if (pair.first == label) {
                consoleCommandEdit_->setText(QString::fromStdString(pair.second));
                break;
            }
        }
    }

    void appendConsoleResponse(const QString& text, const QString& color) {
        consoleResponse_->setTextColor(QColor(color));
        consoleResponse_->append(text);
    }

    void onConsoleSend() {
        QString command = consoleCommandEdit_->text().trimmed();
        if (command.isEmpty()) return;

        QString upper = command.toUpper();
        if (upper.contains("DISP") && upper.contains("DATA")) {
            log_("คำสั่งนี้คืนค่าเป็นภาพ (binary) ใช้ปุ่ม Capture ใน Tools tab แทน", "error");
            return;
        }

        appendConsoleResponse("> " + command, "#8ce99a");

        std::string commandStr = command.toStdString();
        if (command.endsWith("?")) {
            std::string response;
            bool ok = runSafely_(
                [this, commandStr, &response] { response = controller_.query(commandStr); },
                QString()
            );
            if (ok) {
                appendConsoleResponse("< " + QString::fromStdString(response), "#dddddd");
            }
        } else {
            runSafely_(
                [this, commandStr] { controller_.write(commandStr); },
                QString("ส่งคำสั่ง: %1").arg(command)
            );
        }
    }

    void onConsoleClear() {
        consoleResponse_->clear();
    }

    // ---------- Save / Load config ----------

    ConfigMap collectConfig() const {
        return ConfigMap{
            {"channel", channelBox_->currentText().toStdString()},
            {"display", displayCheck_->isChecked() ? "true" : "false"},
            {"coupling", couplingBox_->currentText().toStdString()},
            {"vdiv", voltBox_->currentText().toStdString()},
            {"offset", offsetEdit_->text().toStdString()},
            {"time_div", timeBox_->currentText().toStdString()},
            {"trigger_source", trigSourceBox_->currentText().toStdString()},
            {"trigger_slope", trigSlopeBox_->currentText().toStdString()},
            {"trigger_level", trigLevelEdit_->text().toStdString()},
            {"trigger_mode", trigModeBox_->currentText().toStdString()},
        };
    }

    void onSaveConfig() {
        QString path = QFileDialog::getSaveFileName(this, "Save Config", "scope_config.json", "JSON files (*.json)");
        if (path.isEmpty()) return;

        try {
            saveConfig(path.toStdString(), collectConfig());
            log_(QString("บันทึกการตั้งค่าแล้ว: %1").arg(path), "ok");
        } catch (const std::exception& exc) {
            log_(QString("บันทึกการตั้งค่าไม่สำเร็จ: %1").arg(exc.what()), "error");
        }
    }

    void onLoadConfig() {
        QString path = QFileDialog::getOpenFileName(this, "Load Config", "", "JSON files (*.json)");
        if (path.isEmpty()) return;

        ConfigMap settings;
        try {
            settings = loadConfig(path.toStdString());
        } catch (const std::exception& exc) {
            log_(QString("โหลดการตั้งค่าไม่สำเร็จ: %1").arg(exc.what()), "error");
            return;
        }

        auto get = [&settings](const std::string& key, const std::string& fallback) {
            auto it = settings.find(key);
            return it != settings.end() ? it->second : fallback;
        };

        channelBox_->setCurrentText(QString::fromStdString(get("channel", channelBox_->currentText().toStdString())));
        displayCheck_->setChecked(get("display", "true") == "true");
        couplingBox_->setCurrentText(QString::fromStdString(get("coupling", couplingBox_->currentText().toStdString())));
        voltBox_->setCurrentText(QString::fromStdString(get("vdiv", voltBox_->currentText().toStdString())));
        offsetEdit_->setText(QString::fromStdString(get("offset", offsetEdit_->text().toStdString())));
        timeBox_->setCurrentText(QString::fromStdString(get("time_div", timeBox_->currentText().toStdString())));
        trigSourceBox_->setCurrentText(QString::fromStdString(get("trigger_source", trigSourceBox_->currentText().toStdString())));
        trigSlopeBox_->setCurrentText(QString::fromStdString(get("trigger_slope", trigSlopeBox_->currentText().toStdString())));
        trigLevelEdit_->setText(QString::fromStdString(get("trigger_level", trigLevelEdit_->text().toStdString())));
        trigModeBox_->setCurrentText(QString::fromStdString(get("trigger_mode", trigModeBox_->currentText().toStdString())));

        // ยิงค่าที่โหลดมาไปที่เครื่องจริงทีละคำสั่ง เพื่อให้ log เห็นทุกขั้นตอน
        onDisplayToggle(displayCheck_->isChecked());
        onCouplingChange(couplingBox_->currentText());
        onVoltChange(voltBox_->currentText());
        onOffsetChange();
        onTimeChange(timeBox_->currentText());
        onTriggerSourceChange(trigSourceBox_->currentText());
        onTriggerSlopeChange(trigSlopeBox_->currentText());
        onTriggerLevelChange();
        onTriggerModeChange(trigModeBox_->currentText());

        log_(QString("โหลดการตั้งค่าแล้ว: %1").arg(path), "ok");
    }

    // ---------- Members ----------

    ScopeController& controller_;
    Logger log_;
    RunSafely runSafely_;

    std::vector<double> lastTimes_;
    std::vector<double> lastVolts_;
    QTimer* autoRefreshTimer_;

    // Acquisition
    QGroupBox* acquisitionGroup_;
    QPushButton* btnRun_;
    QPushButton* btnStop_;
    QPushButton* btnSingle_;
    QPushButton* btnAutoscale_;

    // Channel
    QGroupBox* channelGroup_;
    QComboBox* channelBox_;
    QCheckBox* displayCheck_;
    QComboBox* couplingBox_;
    QComboBox* voltBox_;
    QLineEdit* offsetEdit_;
    QPushButton* btnOffsetApply_;

    // Timebase
    QGroupBox* timebaseGroup_;
    QComboBox* timeBox_;

    // Trigger
    QGroupBox* triggerGroup_;
    QComboBox* trigSourceBox_;
    QComboBox* trigSlopeBox_;
    QLineEdit* trigLevelEdit_;
    QComboBox* trigModeBox_;
    QPushButton* btnTriggerLevelApply_;

    // Waveform
    QPushButton* btnRead_;
    QPushButton* btnExport_;
    QPushButton* btnSaveConfig_;
    QPushButton* btnLoadConfig_;
    WaveformWidget* canvas_;

    // Measurement
    QPushButton* btnMeasure_;
    QCheckBox* autoRefreshCheck_;
    QComboBox* refreshIntervalBox_;
    QTreeWidget* table_;
    std::map<std::string, QTreeWidgetItem*> rowItems_;

    // Console
    QComboBox* presetBox_;
    QLineEdit* consoleCommandEdit_;
    QPushButton* btnConsoleSend_;
    QPushButton* btnConsoleClear_;
    QTextEdit* consoleResponse_;
};
#include "workspace_tab.moc"
