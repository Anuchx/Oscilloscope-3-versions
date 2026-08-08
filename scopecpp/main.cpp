// main.cpp
// Application entry point.

#include <QApplication>
#include <QMessageBox>

#include "controller.cpp"
#include "gui_cpp/app.cpp"

int main(int argc, char* argv[]) {
    QApplication app(argc, argv);

    try {
        ScopeController controller;
        OscilloscopeApp window(controller);
        window.show();
        return app.exec();
    } catch (const std::exception& exc) {
        QMessageBox::critical(nullptr, "เริ่มโปรแกรมไม่สำเร็จ", exc.what());
        return 1;
    }
}