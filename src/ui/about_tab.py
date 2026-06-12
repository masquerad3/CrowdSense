"""
CrowdSense — About Tab  (src/ui/about_tab.py)
Displays app branding, version info, and logo.
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _ASSETS_DIR = Path(sys._MEIPASS) / "assets"
else:
    _ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"



class AboutTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Container to group elements and align centrally
        container = QWidget()
        container_lay = QVBoxLayout(container)
        container_lay.setContentsMargins(0, 0, 0, 0)
        container_lay.setSpacing(20)
        container_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── Logo ──────────────────────────────────────────────────────────────
        logo_path = _ASSETS_DIR / "logo.png"
        lbl_logo = QLabel()
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            lbl_logo.setPixmap(
                pix.scaled(250, 250,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        container_lay.addWidget(lbl_logo)

        # ── App Title & Description ───────────────────────────────────────────
        title = QLabel("CrowdSense")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 28px; font-weight: 700; color: #e6edf3; letter-spacing: -0.5px;"
        )
        container_lay.addWidget(title)

        version = QLabel("Crowd Monitoring & Analysis System  |  v1.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("font-size: 13px; color: #8b949e; font-weight: 500;")
        container_lay.addWidget(version)

        desc = QLabel(
            "Analyzes video footage to detect and count people in real time, "
            "classify crowd density, and raise alerts when occupancy exceeds a "
            "configurable threshold."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setMaximumWidth(460)
        desc.setStyleSheet("color: #8b949e; font-size: 13px; line-height: 1.6;")
        container_lay.addWidget(desc)

        root.addWidget(container)
