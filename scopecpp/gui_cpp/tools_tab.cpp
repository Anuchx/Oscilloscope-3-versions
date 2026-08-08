// gui_cpp/tools_tab.cpp
// Tools tab: screen capture. Only calls controller.captureScreen().
// Mirrors gui_tk/tools_tab.py. No header — declaration + implementation
// live here together, included once from app.cpp.

#pragma once

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QLabel>
#include <QPushButton>
#include <QFileDialog>
#include <QPixmap>
#include <functional>
#include <fstream>

#include "../controller.cpp"

class ToolsTab : public QWidget {
    Q_OBJECT

public:
    using Logger = std::function<void(const QString&, const QString&)>;
    using RunSafely = std::function<bool(std::function<void()>, const QString&)>;

    ToolsTab(ScopeController& controller, Logger logger, RunSafely runSafely, QWidget* parent = nullptr)
        : QWidget(parent), controller_(controller), log_(std::move(logger)), runSafely_(std::move(runSafely)) {
        auto* layout = new QVBoxLayout(this);
        buildCapturePanel(layout);
    }

    void setEnabledState(bool enabled) {
        btnCapture_->setEnabled(enabled);
        if (!enabled) {
            btnSave_->setEnabled(false);
        }
    }

private:
    void buildCapturePanel(QVBoxLayout* parentLayout) {
        auto* group = new QGroupBox("Screen Capture", this);
        auto* layout = new QVBoxLayout(group);

        auto* toolbar = new QHBoxLayout();
        btnCapture_ = new QPushButton("Capture", group);
        connect(btnCapture_, &QPushButton::clicked, this, &ToolsTab::onCapture);
        toolbar->addWidget(btnCapture_);

        btnSave_ = new QPushButton("Save PNG", group);
        btnSave_->setEnabled(false);
        connect(btnSave_, &QPushButton::clicked, this, &ToolsTab::onSave);
        toolbar->addWidget(btnSave_);
        toolbar->addStretch();
        layout->addLayout(toolbar);

        imageLabel_ = new QLabel("ยังไม่มีภาพ — กด Capture", group);
        imageLabel_->setAlignment(Qt::AlignmentFlag::AlignCenter);
        imageLabel_->setStyleSheet("border: 1px solid #888888;");
        imageLabel_->setMinimumHeight(300);
        layout->addWidget(imageLabel_, 1);

        parentLayout->addWidget(group);
    }

    void onCapture() {
        std::vector<uint8_t> data;
        bool ok = runSafely_(
            [this, &data] { data = controller_.captureScreen(); },
            "จับภาพหน้าจอสำเร็จ"
        );
        if (!ok || data.empty()) return;

        lastImageBytes_ = data;
        btnSave_->setEnabled(true);

        QPixmap pixmap;
        if (pixmap.loadFromData(reinterpret_cast<const uchar*>(data.data()), static_cast<int>(data.size()))) {
            QPixmap scaled = pixmap.scaled(
                800, 500,
                Qt::AspectRatioMode::KeepAspectRatio,
                Qt::TransformationMode::SmoothTransformation
            );
            imageLabel_->setPixmap(scaled);
        } else {
            imageLabel_->setText(QString("ได้ข้อมูลภาพ %1 bytes (แสดงภาพไม่สำเร็จ)").arg(data.size()));
            log_("แสดงภาพไม่สำเร็จ — ข้อมูลอาจไม่ใช่รูปแบบภาพที่รองรับ", "error");
        }
    }

    void onSave() {
        if (lastImageBytes_.empty()) return;

        QString path = QFileDialog::getSaveFileName(
            this, "Save PNG", "scope_screen.png", "PNG files (*.png)"
        );
        if (path.isEmpty()) return;

        std::ofstream file(path.toStdString(), std::ios::binary);
        if (!file.is_open()) {
            log_("บันทึกไฟล์ไม่สำเร็จ", "error");
            return;
        }
        file.write(reinterpret_cast<const char*>(lastImageBytes_.data()), lastImageBytes_.size());
        log_(QString("บันทึกภาพแล้ว: %1").arg(path), "ok");
    }

    ScopeController& controller_;
    Logger log_;
    RunSafely runSafely_;

    std::vector<uint8_t> lastImageBytes_;

    QPushButton* btnCapture_;
    QPushButton* btnSave_;
    QLabel* imageLabel_;
};
#include "tools_tab.moc"
