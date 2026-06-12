import sys
import os

# Pre-load torch to prevent Windows DLL namespace / OpenMP runtime conflicts when PyQt6 loads first
try:
    import torch
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont, QIcon

from auth.db import init_db
from ui.main_window import MainWindow
from ui.styles import MAIN_STYLESHEET

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _ASSETS_DIR = Path(sys._MEIPASS) / "assets"
else:
    _ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"



def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CrowdSense")
    app.setApplicationDisplayName("CrowdSense")
    app.setStyleSheet(MAIN_STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))

    # Set application-wide window icon
    logo_path = _ASSETS_DIR / "logo.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    # Initialize database — creates tables and seeds defaults on first run
    try:
        init_db()
    except Exception as exc:
        QMessageBox.critical(
            None, "Startup Error",
            "CrowdSense could not initialize its database.\n\n"
            "Make sure the application has write permission to the project folder.\n\n"
            f"Detail: {type(exc).__name__}"
        )
        sys.exit(1)

    # Launch main window directly — no login required
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()