"""
CrowdSense — Dashboard Tab  (src/ui/dashboard.py)
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSplitter, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap


class DashboardTab(QWidget):
    """
    Main monitoring view. Pure UI — no detection or database logic here.
    Emits signals for user actions; MainWindow handles all business logic.
    """

    load_requested     = pyqtSignal()
    live_requested     = pyqtSignal(str)   # camera index string or RTSP URL
    play_requested     = pyqtSignal()
    pause_requested    = pyqtSignal()
    stop_requested     = pyqtSignal()
    speed_changed      = pyqtSignal(float)
    settings_requested = pyqtSignal()
    logout_requested   = pyqtSignal()

    _SPEEDS = {"0.5x": 0.5, "1.0x": 1.0, "1.5x": 1.5, "2.0x": 2.0}

    def __init__(self, username: str, role: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.role     = role
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Video preview
        self.video_lbl = QLabel(
            "No source loaded\n\nSelect a CCTV channel to begin"
        )
        self.video_lbl.setObjectName("videoPreview")
        self.video_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        splitter.addWidget(self.video_lbl)
        splitter.addWidget(self._make_sidebar())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([900, 175])

        root.addWidget(splitter, 1)

        # Alert banner (hidden until triggered)
        self.alert_banner = QLabel("ALERT: Safety limit exceeded.")
        self.alert_banner.setObjectName("alertBanner")
        self.alert_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alert_banner.hide()
        root.addWidget(self.alert_banner)

        root.addWidget(self._make_toolbar())

    def _make_sidebar(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        panel.setFixedWidth(175)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 14, 12, 10)
        lay.setSpacing(0)

        # User info
        self.lbl_user = QLabel(self.username)
        self.lbl_user.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #e6edf3;"
        )
        role_color = "#f85149" if self.role == "admin" else "#3fb950"
        self.lbl_role = QLabel(self.role.upper())
        self.lbl_role.setStyleSheet(
            f"font-size: 10px; color: {role_color}; font-weight: 600;"
        )

        lay.addWidget(self.lbl_user)
        lay.addSpacing(2)
        lay.addWidget(self.lbl_role)
        lay.addSpacing(12)
        lay.addWidget(self._sep())
        lay.addSpacing(10)

        # Detection stats (compact key-value rows)
        self.lbl_count_val   = self._val_lbl()
        self.lbl_density_val = self._val_lbl()
        self.lbl_status_val  = self._val_lbl()
        self.lbl_fps_val     = self._val_lbl()
        self.lbl_latency_val = self._val_lbl()

        for name, val in [("Count",   self.lbl_count_val),
                          ("Density", self.lbl_density_val),
                          ("Status",  self.lbl_status_val),
                          ("FPS",     self.lbl_fps_val),
                          ("Latency", self.lbl_latency_val)]:
            lay.addLayout(self._kv_row(name, val))
            lay.addSpacing(5)

        lay.addSpacing(8)
        lay.addWidget(self._sep())
        lay.addSpacing(10)

        # Clock
        self.lbl_clock = QLabel()
        self.lbl_clock.setStyleSheet(
            "font-size: 16px; font-weight: 300; color: #484f58;"
            " font-family: 'Consolas', monospace;"
        )
        self.lbl_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_clock()
        t = QTimer(self)
        t.timeout.connect(self._update_clock)
        t.start(1000)
        lay.addWidget(self.lbl_clock)

        lay.addStretch()
        lay.addWidget(self._sep())
        lay.addSpacing(8)

        # Model status
        self.lbl_model = QLabel("Loading model...")
        self.lbl_model.setStyleSheet("font-size: 10px; color: #484f58;")
        self.lbl_model.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_model.setWordWrap(True)
        lay.addWidget(self.lbl_model)
        lay.addSpacing(8)

        btn_logout = QPushButton("Logout")
        btn_logout.setObjectName("dangerBtn")
        btn_logout.setFixedHeight(26)
        btn_logout.clicked.connect(self.logout_requested)
        lay.addWidget(btn_logout)

        return panel

    def _make_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("toolbar")
        cl = QHBoxLayout(bar)
        cl.setContentsMargins(10, 5, 10, 5)
        cl.setSpacing(3)

        self.cmb_channels = QComboBox()
        self.cmb_channels.addItem("Select CCTV Channel...")
        self.cmb_channels.addItem("Channel 1: Entrance Lobby (Cam 0)")
        self.cmb_channels.addItem("Channel 2: Main Gate (Cam 1)")
        self.cmb_channels.addItem("Channel 3: Custom RTSP/RTMP Feed...")
        self.cmb_channels.addItem("Channel 4: Load Offline Video File...")
        self.cmb_channels.currentIndexChanged.connect(self._on_channel_selected)

        self.btn_play  = QPushButton("Play")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop  = QPushButton("Stop")

        self.btn_play.setObjectName("primaryBtn")

        for btn in (self.btn_play, self.btn_pause, self.btn_stop):
            btn.setEnabled(False)

        self.btn_play.clicked.connect(self.play_requested)
        self.btn_pause.clicked.connect(self.pause_requested)
        self.btn_stop.clicked.connect(self.stop_requested)

        self.cmb_speed = QComboBox()
        for label in self._SPEEDS:
            self.cmb_speed.addItem(label)
        self.cmb_speed.setCurrentText("1.0x")
        self.cmb_speed.currentTextChanged.connect(
            lambda t: self.speed_changed.emit(self._SPEEDS.get(t, 1.0))
        )

        self.btn_settings = QPushButton("Settings")
        self.btn_settings.clicked.connect(self.settings_requested)
        if self.role != "admin":
            self.btn_settings.hide()

        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setStyleSheet("color: #21262d;")

        cl.addWidget(self.cmb_channels)
        cl.addSpacing(3)
        cl.addWidget(vsep)
        cl.addSpacing(3)
        cl.addWidget(self.btn_play)
        cl.addWidget(self.btn_pause)
        cl.addWidget(self.btn_stop)
        cl.addStretch()
        cl.addWidget(QLabel("Speed:"))
        cl.addWidget(self.cmb_speed)
        cl.addSpacing(6)
        cl.addWidget(self.btn_settings)

        return bar

    # --- Helpers ------------------------------------------------------------

    def _sep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color: #21262d;")
        return f

    def _val_lbl(self) -> QLabel:
        lbl = QLabel("-")
        lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #e6edf3;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    def _kv_row(self, key: str, val_lbl: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        k = QLabel(key)
        k.setStyleSheet("font-size: 11px; color: #8b949e;")
        row.addWidget(k)
        row.addWidget(val_lbl, 1)
        return row

    def _on_channel_selected(self, index: int):
        if index == 0:
            return
        elif index == 1:
            self.live_requested.emit("0")
        elif index == 2:
            self.live_requested.emit("1")
        elif index == 3:
            from ui._camera_picker import CameraPickerDialog
            dlg = CameraPickerDialog(self)
            if dlg.exec():
                source = dlg.selected_source
                if source is not None:
                    self.live_requested.emit(str(source))
        elif index == 4:
            self.load_requested.emit()
        
        # Reset back to the placeholder item so the selection triggers next time as well
        self.cmb_channels.setCurrentIndex(0)

    def _update_clock(self):
        self.lbl_clock.setText(datetime.now().strftime("%H:%M:%S"))

    # --- Public API (called by MainWindow) ----------------------------------

    def update_frame(self, qimage: QImage):
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            self.video_lbl.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_lbl.setPixmap(scaled)

    def update_stats(self, count: int, density_label: str,
                     density_color: str, is_alert: bool, fps: float = 0.0, latency: float = 0.0):
        self.lbl_count_val.setText(str(count))
        self.lbl_count_val.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {density_color};"
        )
        self.lbl_density_val.setText(density_label)
        self.lbl_density_val.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {density_color};"
        )
        if is_alert:
            self.lbl_status_val.setText("ALERT")
            self.lbl_status_val.setStyleSheet(
                "font-size: 13px; font-weight: 600; color: #f85149;"
            )
            self.alert_banner.show()
        else:
            self.lbl_status_val.setText("OK")
            self.lbl_status_val.setStyleSheet(
                "font-size: 13px; font-weight: 600; color: #3fb950;"
            )
            self.alert_banner.hide()

        self.lbl_fps_val.setText(f"{fps:.1f} FPS" if fps > 0 else "-")
        self.lbl_latency_val.setText(f"{latency:.1f} ms" if latency > 0 else "-")

    def set_model_status(self, msg: str):
        self.lbl_model.setText(msg)

    def set_video_label(self, text: str):
        self.video_lbl.clear()
        self.video_lbl.setText(text)

    def set_playback_state(self, state: str):
        playing = state == "playing"
        paused  = state == "paused"
        stopped = state == "stopped"
        self.btn_play.setEnabled(stopped or paused)
        self.btn_pause.setEnabled(playing)
        self.btn_stop.setEnabled(playing or paused)
        self.cmb_channels.setEnabled(stopped)
