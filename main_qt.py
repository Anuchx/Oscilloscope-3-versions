"""Application entry point for the PyQt6 version."""

import sys
from PyQt6.QtWidgets import QApplication

from controller import ScopeController
from gui_qt.app import OscilloscopeApp


def main():
    controller = ScopeController()
    app = QApplication(sys.argv)
    window = OscilloscopeApp(controller)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()