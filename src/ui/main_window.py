import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMessageBox, QFileDialog,
    QApplication
)
from PyQt6.QtCore import QTimer, QEvent, QObject
from PyQt6.QtGui import QImage

from auth.db import log_event
from detection.worker import ModelLoaderWorker, DetectionWorker
from detection.detector import CrowdDetector
from ui.dashboard import DashboardTab
from ui.analytics import AnalyticsTab
from ui.logs_tab import LogsTab
from ui.about_tab import AboutTab


class MainWindow(QMainWindow):

    SESSION_TIMEOUT_MS = 15 * 60 * 1000   # 15 minutes

    def __init__(self, username: str, role: str):
        super().__init__()
        self.username = username
        self.role = role

        # Detection state
        self.detector = None
        self.loader = None
        self.worker = None
        self.video_path = ""
        self.playback_state = "stopped"

        # Application settings
        self.safety_limit = 30
        self.confidence = 0.40
        self.current_speed = 1.0
        self.inference_interval = 1
        self.inference_resolution = 640
        self._last_reading_t = 0.0

        self.build_ui()
        self.load_model_async()
        self.start_session_timer()

    # Session Management

    def start_session_timer(self):
        self.session_timer = QTimer(self)
        self.session_timer.setSingleShot(True)
        self.session_timer.setInterval(self.SESSION_TIMEOUT_MS)
        self.session_timer.timeout.connect(self._on_session_expired)
        self.session_timer.start()
        
        # Reset the timer on any user activity across the app
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj: QObject, event) -> bool:
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            self.session_timer.start()
        return False

    def _on_session_expired(self):
        self.sb.showMessage("Session expired due to inactivity.")
        log_event(self.username, "SESSION_EXPIRED", "Auto-logout after 15 min idle")
        self.stop_worker()
        self.hide()
        QMessageBox.information(
            None, "Session Expired",
            "You have been logged out due to 15 minutes of inactivity."
        )
        self.prompt_relogin()

    # UI Construction

    def build_ui(self):
        self.setWindowTitle("CrowdSense")
        self.resize(1280, 760)
        self.setMinimumSize(960, 620)

        self.tabs = QTabWidget()

        self.dash = DashboardTab(self.username, self.role)
        self.analy = AnalyticsTab()
        self.logs = LogsTab(username=self.username, role=self.role)
        self.about = AboutTab(username=self.username, role=self.role)

        self.tabs.addTab(self.dash, "Dashboard")
        self.tabs.addTab(self.analy, "Analytics")
        self.tabs.addTab(self.logs, "Audit Logs")
        self.tabs.addTab(self.about, "About")

        # Enforce role-based tab access
        logs_idx = self.tabs.indexOf(self.logs)
        if logs_idx != -1:
            self.tabs.setTabVisible(logs_idx, self.role == "admin")

        self.setCentralWidget(self.tabs)

        self.sb = QStatusBar()
        self.setStatusBar(self.sb)
        self.sb.showMessage(f"Logged in as {self.username} ({self.role}) | Loading model...")

        # Dashboard signals
        self.dash.load_requested.connect(self._on_load)
        self.dash.live_requested.connect(self._on_live)
        self.dash.play_requested.connect(self._on_play)
        self.dash.pause_requested.connect(self._on_pause)
        self.dash.stop_requested.connect(self._on_stop)
        self.dash.speed_changed.connect(self._on_speed)
        self.dash.settings_requested.connect(self._on_settings)
        self.dash.logout_requested.connect(self._on_logout)

        self.about.logout_requested.connect(self._on_logout)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    # Core Model Pipeline

    def load_model_async(self):
        self.loader = ModelLoaderWorker(
            confidence=self.confidence,
            imgsz=self.inference_resolution,
        )
        self.loader.ready.connect(self._on_model_ready)
        self.loader.error.connect(self._on_model_error)
        self.loader.start()

    def _on_model_ready(self, detector: CrowdDetector):
        self.detector = detector
        self.dash.set_model_status(f"{detector.model_name} - Ready")
        self.sb.showMessage(f"Model loaded. Logged in as {self.username} ({self.role}).")
        if self.video_path:
            self.dash.btn_play.setEnabled(True)

    def _on_model_error(self, err: str):
        self.dash.set_model_status("Model: load error")
        self.sb.showMessage("Model error - check that a model file exists in the models/ folder.")
        log_event(self.username, "MODEL_ERROR", err[:300])

    # Media Loading & Controls

    def _on_load(self):
        videos_dir = str(Path(__file__).resolve().parents[2] / "videos")
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", videos_dir,
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm *.m4v)"
        )
        if not path:
            return

        self.video_path = path
        fname = path.replace("\\", "/").split("/")[-1]
        self.dash.set_video_label(f"{fname}\n\nPress Play to start detection")
        self.sb.showMessage(f"Video loaded: {fname}")
        log_event(self.username, "VIDEO_LOADED", fname)

        if self.detector:
            self.dash.btn_play.setEnabled(True)

    def _on_play(self):
        if not self.video_path:
            self.sb.showMessage("Load a video first.")
            return
        if not self.detector:
            self.sb.showMessage("Model is still loading — please wait a moment.")
            return

        if self.playback_state == "paused" and self.worker:
            self.worker.resume()
            self.set_state("playing")
            self.sb.showMessage("Resumed.")
            return

        self.stop_worker()
        self.analy.clear_session()
        self._last_reading_t = 0.0

        self.worker = DetectionWorker(
            source=self.video_path,
            detector=self.detector,
            safety_limit=self.safety_limit,
            speed=self.current_speed,
            inference_interval=self.inference_interval,
        )
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.stats_updated.connect(self._on_stats)
        self.worker.video_ended.connect(self._on_video_ended)
        self.worker.error_occurred.connect(self._on_detect_error)
        self.worker.start()

        self.set_state("playing")
        fname = self.video_path.replace("\\", "/").split("/")[-1]
        log_event(self.username, "DETECTION_STARTED", f"file={fname} limit={self.safety_limit}")
        self.sb.showMessage("Detection running...")

    def _on_pause(self):
        if self.worker:
            self.worker.pause()
        self.set_state("paused")
        self.sb.showMessage("Paused.")

    def _on_stop(self):
        self.stop_worker()
        self.set_state("stopped")
        self.dash.set_video_label("Stopped. Select a CCTV channel to begin.")
        self.dash.update_stats(0, "-", "#8b949e", False)
        log_event(self.username, "DETECTION_STOPPED", "")
        self.sb.showMessage("Stopped.")

    def stop_worker(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

    # Pipeline Communication Handlers

    def _on_frame(self, qimage: QImage):
        self.dash.update_frame(qimage)

    def _on_stats(self, count: int, density_label: str, density_color: str, 
                  is_alert: bool, fps: float = 0.0, latency: float = 0.0):
        self.dash.update_stats(count, density_label, density_color, is_alert, fps, latency)

        now = time.monotonic()
        if now - self._last_reading_t >= 1.0:
            self._last_reading_t = now
            self.analy.add_reading(
                timestamp=datetime.now().strftime("%H:%M:%S"),
                count=count,
                density=density_label,
                is_alert=is_alert,
            )

        if is_alert:
            self.sb.showMessage(f"ALERT: {count} people detected (limit: {self.safety_limit})")

    def _on_video_ended(self):
        self.stop_worker()
        self.set_state("stopped")
        self.sb.showMessage("Playback complete.")
        log_event(self.username, "VIDEO_ENDED", "")

    def _on_detect_error(self, msg: str):
        self.sb.showMessage("A detection error occurred (see audit log).")
        log_event(self.username, "DETECTION_ERROR", msg[:300])

    def _on_live(self, source: str):
        if not self.detector:
            self.sb.showMessage("Model is still loading.")
            return

        self.stop_worker()
        self.analy.clear_session()
        self._last_reading_t = 0.0
        self.video_path = source

        self.worker = DetectionWorker(
            source=source,
            detector=self.detector,
            safety_limit=self.safety_limit,
            speed=self.current_speed,
            inference_interval=self.inference_interval,
        )
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.stats_updated.connect(self._on_stats)
        self.worker.video_ended.connect(self._on_video_ended)
        self.worker.error_occurred.connect(self._on_detect_error)
        self.worker.start()

        self.set_state("playing")
        label = f"Camera {source}" if source.isdigit() else source
        log_event(self.username, "LIVE_STARTED", f"source={source}")
        self.sb.showMessage(f"Live: {label}")

    def _on_speed(self, speed: float):
        self.current_speed = speed
        if self.worker:
            self.worker.speed = speed

    # Program Configuration & Tab Changes

    def _on_settings(self):
        if self.role != "admin":
            return
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(
            safety_limit=self.safety_limit,
            confidence=self.confidence,
            inference_interval=self.inference_interval,
            inference_resolution=self.inference_resolution,
            parent=self,
        )
        if dlg.exec():
            self.safety_limit = dlg.safety_limit
            self.confidence = dlg.confidence
            self.inference_interval = dlg.inference_interval
            self.inference_resolution = dlg.inference_resolution

            if self.worker:
                self.worker.safety_limit = self.safety_limit
                self.worker.inference_interval = self.inference_interval

            if self.detector:
                self.detector.confidence = self.confidence
                self.detector.imgsz = self.inference_resolution

    def _on_tab_changed(self, index: int):
        if self.tabs.widget(index) is self.logs:
            self.logs.refresh()

    # Session Lifecycle & Authentication Realignment

    def _on_logout(self):
        reply = QMessageBox.question(
            self, "Logout",
            f"Log out as {self.username}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.stop_worker()
        log_event(self.username, "LOGOUT", "")
        self.prompt_relogin()

    def prompt_relogin(self):
        """Hides current session layout and presents validation checks."""
        self.hide()
        from auth.login_dialog import LoginDialog
        login = LoginDialog(None)
        if login.exec() == LoginDialog.DialogCode.Accepted:
            old_role = self.role
            self.username = login.authenticated_username
            self.role = login.authenticated_role
            self.update_user_context(old_role)
            self.show()
        else:
            self.close()

    def update_user_context(self, old_role: str):
        """Clears stale views and reconfigures permissions post authentication."""
        self.dash.username = self.username
        self.dash.role = self.role
        self.dash.lbl_user.setText(self.username)

        role_color = "#f85149" if self.role == "admin" else "#3fb950"
        self.dash.lbl_role.setText(self.role.upper())
        self.dash.lbl_role.setStyleSheet(
            f"font-size: 10px; color: {role_color}; font-weight: 600;"
        )
        
        if self.role == "admin":
            self.dash.btn_settings.show()
        else:
            self.dash.btn_settings.hide()

        self.about.update_user(self.username, self.role)
        self.logs.set_user_context(self.username, self.role)
        
        logs_idx = self.tabs.indexOf(self.logs)
        if logs_idx != -1:
            self.tabs.setTabVisible(logs_idx, self.role == "admin")

        self.analy.clear_session()
        self.tabs.setCurrentIndex(0)

        self.set_state("stopped")
        self.video_path = ""
        self.dash.set_video_label("No channel selected\n\nSelect a CCTV channel to begin")
        self.dash.update_stats(0, "—", "#8b949e", False)

        self.sb.showMessage(f"Logged in as {self.username} ({self.role}).")
        log_event(self.username, "LOGIN_SUCCESS", "Re-login after logout")

    def set_state(self, state: str):
        self.playback_state = state
        self.dash.set_playback_state(state)

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self.stop_worker()
        super().closeEvent(event)