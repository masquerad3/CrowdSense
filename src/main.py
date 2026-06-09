import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont

from auth.db import init_db
from auth.login_dialog import LoginDialog
from ui.main_window import MainWindow
from ui.styles import MAIN_STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CrowdSense")
    app.setApplicationDisplayName("CrowdSense")
    app.setStyleSheet(MAIN_STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))

    # Initialize database
    # Creates tables and default accounts (admin / viewer) on first run.
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

    # Login
    login = LoginDialog()
    if login.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)    # user closed the login dialog -> clean exit

    # Launch main window
    window = MainWindow(
        username=login.authenticated_username,
        role=login.authenticated_role,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()