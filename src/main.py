import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QSplitter, QPushButton, QComboBox,
    QStatusBar, QSizePolicy, QGroupBox
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # --- Window Settings ---
        self.setWindowTitle("CrowdSense")
        self.resize(1200, 720)
        self.setWindowIcon(QIcon("CrowdSense.png"))

        self.video_path = ""

        # --- Tab Layout ---
        tabs = QTabWidget()

        # ----------- Tab 1: Dashboard tab -----------
        dashboard = QWidget()
        dashboard_layout = QVBoxLayout(dashboard)
        dashboard_layout.setContentsMargins(10, 10, 10, 10)
        dashboard_layout.setSpacing(10)

        # --- Header ---
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        title = QLabel("Dashboard")
        title.setStyleSheet("QLabel { font-size: 18px; font-weight: bold; }")
        self.lbl_model = QLabel("Model: YOLOv8n (not loaded)")
        self.lbl_video = QLabel("Video: none")

        self.lbl_model.setStyleSheet("color: #555;")
        self.lbl_video.setStyleSheet("color: #555;")

        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.lbl_model)
        header_layout.addWidget(self.lbl_video)

        dashboard_layout.addWidget(header)


        # --- Preview ---
        self.preview = QLabel("Video Preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(700, 420)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.setStyleSheet(
            "QLabel { background: #f3f3f3; border: 1px solid #d0d0d0; border-radius: 10px; }"
        )


        # --- Sidebar ---
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(10)

        sidebar_layout.addWidget(self.make_card("People Count", "—"))
        sidebar_layout.addWidget(self.make_card("Density", "—"))
        sidebar_layout.addWidget(self.make_card("Safety", "—"))


        # --- Splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.preview)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(0)

        dashboard_layout.addWidget(splitter, 1)


        # --- Controls ---
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self.btn_load = QPushButton("Load Video")
        self.btn_play = QPushButton("Play")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")
        self.btn_settings = QPushButton("Settings")

        # Phase 0: disabled playback & seek
        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

        self.speed = QComboBox()
        self.speed.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self.speed.setCurrentText("1.0x")

        controls_layout.addWidget(self.btn_load)
        controls_layout.addSpacing(6)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addStretch(1)
        controls_layout.addWidget(QLabel("Speed:"))
        controls_layout.addWidget(self.speed)
        controls_layout.addWidget(self.btn_settings)

        dashboard_layout.addWidget(controls)


        # ----------- Tab 2: Analytics tab -----------
        analytics = QWidget()
        analytics_layout = QVBoxLayout(analytics)
        analytics_layout.addWidget(QLabel("Analytics Placeholder (counts over time, max count, alerts, etc.)"))
        analytics_layout.addStretch(1)

        # ----------- Tab 3: Logs tab -----------
        logs = QWidget()
        logs_layout = QVBoxLayout(logs)
        logs_layout.addWidget(QLabel("Logs Placeholder (table + export button later)."))
        logs_layout.addStretch(1)

        # ----------- Tab 4: About tab -----------
        about = QWidget()
        about_layout = QVBoxLayout(about)
        about_layout.addWidget(QLabel("CrowdSense\ncrowd monitoring (PyQt6 + OpenCV + YOLOv8)."))
        about_layout.addStretch(1)


        # --- Layout ---
        tabs.addTab(dashboard, "Dashboard")
        tabs.addTab(analytics, "Analytics")
        tabs.addTab(logs, "Logs")
        tabs.addTab(about, "About")

        self.setCentralWidget(tabs)

        # --- Status bar ---
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        self.setStatusBar(self.status_bar)


    def make_card(self, title: str, big_text: str) -> QGroupBox:
        """Card-like group box for sidebar metrics."""
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        label = QLabel(big_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("QLabel { font-size: 24px; font-weight: bold; }")
        layout.addWidget(label)
        return box


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())