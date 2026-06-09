"""
CrowdSense Secure Login Dialog
"""

import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from auth.db import authenticate, log_event

# Username validation regex (alphanumeric + underscore, 1-64 chars)
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{1,64}$')


class LoginDialog(QDialog):
    # Secure login screen shown before the main application launches.

    MAX_ATTEMPTS = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CrowdSense — Secure Login")
        self.setFixedSize(400, 390)
        
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        self.setModal(True)

        self.authenticated_username = ""
        self.authenticated_role = ""
        self.login_attempts = 0

        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(44, 40, 44, 32)
        root.setSpacing(0)

        # Title & Header
        title = QLabel("CrowdSense")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Crowd Monitoring & Analysis System")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)
        root.addSpacing(24)

        # Username Field
        user_label = QLabel("Username")
        user_label.setObjectName("loginFieldLabel")
        self.username_input = QLineEdit()
        self.username_input.setObjectName("loginField")
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setMaxLength(64)

        root.addWidget(user_label)
        root.addSpacing(5)
        root.addWidget(self.username_input)
        root.addSpacing(18)

        # Password Field
        password_label = QLabel("Password")
        password_label.setObjectName("loginFieldLabel")
        self.password_input = QLineEdit()
        self.password_input.setObjectName("loginField")
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMaxLength(128)
        self.password_input.returnPressed.connect(self.attempt_login)

        root.addWidget(password_label)
        root.addSpacing(5)
        root.addWidget(self.password_input)
        root.addSpacing(10)

        # Error Messaging
        self.error_label = QLabel("")
        self.error_label.setObjectName("loginError")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setMinimumHeight(18)
        root.addWidget(self.error_label)
        root.addSpacing(18)

        # Submission Button
        self.login_button = QPushButton("Sign In")
        self.login_button.setObjectName("loginBtn")
        self.login_button.setMinimumHeight(46)
        self.login_button.clicked.connect(self.attempt_login)
        root.addWidget(self.login_button)

        root.addStretch(1)

    def validate_inputs(self) -> str | None:
        # Validates credentials format prior to authentication checks.
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            return "Please fill in both fields."

        if not USERNAME_RE.match(username):
            return "Username: letters, numbers, and underscores only (max 64)."

        if len(password) > 128:
            return "Password exceeds maximum allowed length."

        return None

    def attempt_login(self):
        # Processes user authentication and updates UI state accordingly.
        error = self.validate_inputs()
        if error:
            self.show_error(error)
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()

        result = authenticate(username, password)

        if result and not result.get("locked"):
            log_event(username, "LOGIN_SUCCESS", "Authenticated via login dialog")
            self.authenticated_username = result["username"]
            self.authenticated_role = result["role"]
            self.accept()

        elif result and result.get("locked"):
            log_event(username, "LOGIN_BLOCKED", "Account is locked")
            self.password_input.clear()
            self.show_error("This account is locked. Contact an administrator.")
            
            self.login_button.setEnabled(False)
            self.username_input.setEnabled(False)
            self.password_input.setEnabled(False)

        else:
            log_event(username, "LOGIN_FAILED", "Invalid credentials")
            self.password_input.clear()
            self.show_error("Invalid credentials.")

    def show_error(self, message: str):
        self.error_label.setText(message)