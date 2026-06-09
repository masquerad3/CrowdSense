"""
CrowdSense — About Tab  (src/ui/about_tab.py)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal


class AboutTab(QWidget):
    logout_requested = pyqtSignal()

    def __init__(self, username: str, role: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.role     = role
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # App title
        title = QLabel("CrowdSense")
        title.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #e6edf3;"
        )

        version = QLabel("Crowd Monitoring & Analysis System  |  v1.0")
        version.setStyleSheet("font-size: 12px; color: #8b949e;")

        desc = QLabel(
            "Analyzes video footage to detect and count people in real time, "
            "classify crowd density, and raise alerts when occupancy exceeds a "
            "configurable threshold."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.5;")

        root.addWidget(title)
        root.addSpacing(4)
        root.addWidget(version)
        root.addSpacing(12)
        root.addWidget(desc)
        root.addSpacing(24)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #21262d;")
        root.addWidget(sep)
        root.addSpacing(20)

        # Session info
        session_label = QLabel("Current session")
        session_label.setStyleSheet("font-size: 11px; color: #484f58;")
        root.addWidget(session_label)
        root.addSpacing(10)

        self.lbl_user_info = QLabel()
        self.lbl_user_info.setStyleSheet("font-size: 13px; color: #c9d1d9; line-height: 1.8;")
        self.lbl_user_info.setTextFormat(Qt.TextFormat.RichText)
        self._refresh_user_label()
        root.addWidget(self.lbl_user_info)
        root.addSpacing(16)

        btn_logout = QPushButton("Logout")
        btn_logout.setObjectName("dangerBtn")
        btn_logout.setFixedWidth(100)
        btn_logout.clicked.connect(self.logout_requested)
        root.addWidget(btn_logout)

        root.addStretch()

    def update_user(self, username: str, role: str):
        self.username = username
        self.role     = role
        self._refresh_user_label()

    def _refresh_user_label(self):
        role_color = "#f85149" if self.role == "admin" else "#3fb950"
        self.lbl_user_info.setText(
            f"<b style='color:#e6edf3;'>{self.username}</b>"
            f"&nbsp;&nbsp;<span style='color:{role_color}; font-size:11px;'>"
            f"{self.role.upper()}</span>"
        )
