"""Application entry point."""

import tkinter as tk

from controller import ScopeController
from gui_tk.app import OscilloscopeApp


def main():
    controller = ScopeController()
    root = tk.Tk()
    OscilloscopeApp(root, controller)
    root.mainloop()


if __name__ == "__main__":
    main()