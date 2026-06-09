"""
CrowdSense — Camera Picker Dialog  (src/ui/_camera_picker.py)

Scans camera indices 0-9 using OpenCV to find real devices, then lets the
user pick from a list. Also has a text field for RTSP/RTMP streams.
"""

import cv2
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont


class _ScanWorker(QThread):
    """Scans camera indices in the background so the UI doesn't freeze."""
    found    = pyqtSignal(int, str)   # index, label
    finished = pyqtSignal()

    def run(self):
        for i in range(8):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                label = f"Camera {i}"
                if w and h:
                    label += f"  ({w}×{h})"
                cap.release()
                self.found.emit(i, label)
        self.finished.emit()


class CameraPickerDialog(QDialog):
    """
    Shows available cameras and lets the user pick one.
    After accept(), read selected_source (int index or str RTSP URL).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Camera — CrowdSense")
        self.setFixedSize(440, 330)
        self.setModal(True)
        self.selected_source = None
        self._build_ui()
        self._scan()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        # Camera list
        lbl_cam = QLabel("Detected cameras")
        lbl_cam.setStyleSheet("font-size: 11px; color: #484f58;")
        root.addWidget(lbl_cam)

        self.list = QListWidget()
        self.list.setFixedHeight(120)
        self.list.itemDoubleClicked.connect(self._accept_list)

        self.scanning_lbl = QLabel("Scanning...")
        self.scanning_lbl.setStyleSheet("font-size: 11px; color: #484f58;")
        self.scanning_lbl.setWordWrap(True)

        root.addWidget(self.list)
        root.addWidget(self.scanning_lbl)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #21262d;")
        root.addWidget(sep)

        # RTSP / manual entry
        lbl_rtsp = QLabel("Or enter an RTSP / RTMP URL")
        lbl_rtsp.setStyleSheet("font-size: 11px; color: #484f58;")
        root.addWidget(lbl_rtsp)

        self.txt_rtsp = QLineEdit()
        self.txt_rtsp.setPlaceholderText("rtsp://192.168.1.10/stream")
        root.addWidget(self.txt_rtsp)

        # Buttons
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        self.btn_ok = QPushButton("Connect")
        self.btn_ok.setObjectName("primaryBtn")
        btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addSpacing(6)
        btn_row.addWidget(self.btn_ok)
        root.addLayout(btn_row)

    def _scan(self):
        self._worker = _ScanWorker()
        self._worker.found.connect(self._on_found)
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_found(self, index: int, label: str):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, index)
        self.list.addItem(item)
        if self.list.count() == 1:
            self.list.setCurrentRow(0)

    def _on_scan_done(self):
        if self.list.count() == 0:
            self.scanning_lbl.setText("No cameras detected.")
        else:
            self.scanning_lbl.setText(
                f"{self.list.count()} camera(s) found. "
                "Double-click to connect, or select and click Connect."
            )

    def _accept_list(self, item: QListWidgetItem):
        self.selected_source = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _accept(self):
        rtsp = self.txt_rtsp.text().strip()
        if rtsp:
            self.selected_source = rtsp
            self.accept()
            return

        item = self.list.currentItem()
        if item:
            self.selected_source = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
