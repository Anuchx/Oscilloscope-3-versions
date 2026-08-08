// gui_cpp/waveform_widget.cpp
// Draws the grid + waveform trace using QPainter. Split out from
// workspace_tab.cpp into its own file per the requested file layout.
// No header — declaration and implementation both live here.

#pragma once

#include <QWidget>
#include <QPainter>
#include <QPen>
#include <QColor>
#include <QString>
#include <vector>
#include <map>
#include <algorithm>

class WaveformWidget : public QWidget {
    Q_OBJECT

public:
    explicit WaveformWidget(QWidget* parent = nullptr) : QWidget(parent), channel_(1) {
        setMinimumHeight(80);
        setStyleSheet("background-color: black;");
    }

    void setData(const std::vector<double>& times, const std::vector<double>& volts, int channel) {
        times_ = times;
        volts_ = volts;
        channel_ = channel;
        update(); // trigger repaint
    }

protected:
    void paintEvent(QPaintEvent* event) override {
        Q_UNUSED(event);
        QPainter painter(this);
        int width = this->width();
        int height = this->height();

        // เติมพื้นหลังดำก่อนเสมอ (stylesheet อย่างเดียวไม่พอสำหรับ custom paint)
        painter.fillRect(0, 0, width, height, QColor("black"));

        // กริด 12x8 ช่อง
        QPen gridPen(QColor("#333333"));
        painter.setPen(gridPen);
        for (int i = 1; i < 12; ++i) {
            int x = width * i / 12;
            painter.drawLine(x, 0, x, height);
        }
        for (int i = 1; i < 8; ++i) {
            int y = height * i / 8;
            painter.drawLine(0, y, width, y);
        }

        if (volts_.empty()) {
            return;
        }

        double vMin = *std::min_element(volts_.begin(), volts_.end());
        double vMax = *std::max_element(volts_.begin(), volts_.end());
        double vRange = (vMax - vMin != 0.0) ? (vMax - vMin) : 1.0;

        std::string color = channelColor(channel_);
        QPen wavePen(QColor(QString::fromStdString(color)));
        wavePen.setWidth(1);
        painter.setPen(wavePen);

        std::vector<std::pair<double, double>> points;
        points.reserve(volts_.size());
        for (size_t i = 0; i < volts_.size(); ++i) {
            double x = (volts_.size() > 1)
                ? width * static_cast<double>(i) / (volts_.size() - 1)
                : 0.0;
            double y = height - ((volts_[i] - vMin) / vRange) * height * 0.9 - height * 0.05;
            points.emplace_back(x, y);
        }

        for (size_t i = 0; i + 1 < points.size(); ++i) {
            painter.drawLine(
                static_cast<int>(points[i].first), static_cast<int>(points[i].second),
                static_cast<int>(points[i + 1].first), static_cast<int>(points[i + 1].second)
            );
        }
    }

private:
    static std::string channelColor(int channel) {
        static const std::map<int, std::string> colors = {
            {1, "#ffff00"}, // เหลือง
            {2, "#00bfff"}, // ฟ้า
            {3, "#ff69b4"}, // ชมพู
            {4, "#7cfc00"}, // เขียว
        };
        auto it = colors.find(channel);
        return it != colors.end() ? it->second : "#ffff00";
    }

    std::vector<double> times_;
    std::vector<double> volts_;
    int channel_;
};


#include "waveform_widget.moc"
