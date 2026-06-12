"""
CrowdSense — Main Window  (src/ui/main_window.py)

Orchestrates the detection pipeline, UI tabs, settings persistence,
session analytics recording, and alerting (winsound + native tray notification).
"""

import sys
import time
import winsound
import threading
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMessageBox, QFileDialog,
    QApplication, QSystemTrayIcon
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage, QIcon

from auth.db import (
    log_event, get_setting, save_setting,
    create_session, close_session, insert_reading, prune_database
)
from detection.worker import ModelLoaderWorker, DetectionWorker
from detection.detector import CrowdDetector
from ui.dashboard import DashboardTab
from ui.analytics import AnalyticsTab
from ui.logs_tab import LogsTab
from ui.about_tab import AboutTab

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _ASSETS_DIR = Path(sys._MEIPASS) / "assets"
else:
    _ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Generate checkmark image programmatically on boot
        self._generate_check_image()

        # Detection state
        self.detector = None
        self.loader   = None
        self.worker   = None
        self.video_path   = ""
        self.source_label = ""
        self.playback_state = "stopped"

        # Application settings — loaded from DB on startup
        self.safety_limit         = int(get_setting("safety_limit",         30))
        self.confidence           = float(get_setting("confidence",          0.40))
        self.inference_interval   = int(get_setting("inference_interval",    1))
        self.inference_resolution = int(get_setting("inference_resolution",  640))

        # Session analytics tracking
        self._current_session_id: int | None = None
        self._last_reading_t = 0.0
        self._session_peak   = 0
        self._session_alerts = 0
        self._session_total  = 0
        self._session_sum    = 0

        # Alert state
        self._alert_active   = False

        # Notification cooldown logic (cooldown limit: 30 seconds)
        self._last_notification_t = 0.0

        # Overlay state (mirrored from checkbox)
        self._show_overlay = True

        self._build_ui()
        self._load_model_async()

        # Prune database on boot if retention limit is set
        retention = int(get_setting("retention_days", 0))
        if retention > 0:
            prune_database(retention)

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("CrowdSense")
        self.resize(1280, 760)
        self.setMinimumSize(960, 620)

        # Window icon
        logo_path = _ASSETS_DIR / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # Initialize QSystemTrayIcon for native notification toast
        self.tray_icon = QSystemTrayIcon(self)
        if logo_path.exists():
            self.tray_icon.setIcon(QIcon(str(logo_path)))
        self.tray_icon.show()

        self.tabs = QTabWidget()

        self.dash  = DashboardTab()
        self.analy = AnalyticsTab()
        self.analy.safety_limit = self.safety_limit  # sync initial safety limit
        self.logs  = LogsTab()
        self.about = AboutTab()

        self.tabs.addTab(self.dash,  "Dashboard")
        self.tabs.addTab(self.analy, "Analytics")
        self.tabs.addTab(self.logs,  "Audit Logs")
        self.tabs.addTab(self.about, "About")

        self.setCentralWidget(self.tabs)

        self.sb = QStatusBar()
        self.setStatusBar(self.sb)
        self.sb.showMessage("Loading model...")

        # Dashboard signals
        self.dash.load_requested.connect(self._on_load)
        self.dash.live_requested.connect(self._on_live)
        self.dash.play_requested.connect(self._on_play)
        self.dash.pause_requested.connect(self._on_pause)
        self.dash.stop_requested.connect(self._on_stop)
        self.dash.speed_changed.connect(self._on_speed)
        self.dash.settings_requested.connect(self._on_settings)
        self.dash.overlay_toggled.connect(self._on_overlay_toggled)

        self.tabs.currentChanged.connect(self._on_tab_changed)

    # ── Model Pipeline ────────────────────────────────────────────────────

    def _load_model_async(self):
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
        self.sb.showMessage("Model loaded. Ready.")
        if self.video_path:
            self.dash.btn_play.setEnabled(True)

    def _on_model_error(self, err: str):
        self.dash.set_model_status("Model: load error")
        self.sb.showMessage("Model error — check that a model file exists in the models/ folder.")
        log_event("MODEL_ERROR", err[:300])

    # ── Media Loading & Controls ──────────────────────────────────────────

    def _on_load(self):
        videos_dir = str(Path(__file__).resolve().parents[2] / "videos")
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", videos_dir,
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm *.m4v)"
        )
        if not path:
            return

        self.video_path   = path
        self.source_label = path.replace("\\", "/").split("/")[-1]
        self.dash.set_video_label(f"{self.source_label}\n\nPress Play to start detection")
        self.sb.showMessage(f"Video loaded: {self.source_label}")
        log_event("VIDEO_LOADED", self.source_label)

        if self.detector:
            self.dash.btn_play.setEnabled(True)

    def _on_play(self):
        if not self.video_path:
            self.sb.showMessage("Load a video or select a live camera first.")
            return
        if not self.detector:
            self.sb.showMessage("Model is still loading — please wait a moment.")
            return

        if self.playback_state == "paused" and self.worker:
            self.worker.resume()
            self._set_state("playing")
            self.sb.showMessage("Resumed.")
            return

        self._stop_worker()
        self.analy.clear_session()
        self._last_reading_t    = 0.0
        self._session_peak      = 0
        self._session_alerts    = 0
        self._session_total     = 0
        self._session_sum       = 0

        # Open a persistent session record in the database
        self._current_session_id = create_session(self.source_label, self.safety_limit)

        self.worker = DetectionWorker(
            source=self.video_path,
            detector=self.detector,
            safety_limit=self.safety_limit,
            speed=getattr(self, "current_speed", 1.0),
            inference_interval=self.inference_interval,
            show_overlay=self._show_overlay,
        )
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.stats_updated.connect(self._on_stats)
        self.worker.video_ended.connect(self._on_video_ended)
        self.worker.error_occurred.connect(self._on_detect_error)
        self.worker.start()

        self._set_state("playing")
        log_event("DETECTION_STARTED",
                  f"source={self.source_label} limit={self.safety_limit}")

    def _on_pause(self):
        if self.worker:
            self.worker.pause()
        self._set_state("paused")
        self.sb.showMessage("Paused.")
        # Stop sound loop if active
        self._stop_alert_sound()
        self._alert_active = False

    def _on_stop(self):
        self._stop_worker()
        self._set_state("stopped")
        self.dash.set_video_label("Stopped. Load a video or select a live camera.")
        self.dash.update_stats(0, "-", "#8b949e", False)
        log_event("DETECTION_STOPPED", "")
        self.sb.showMessage("Stopped.")
        self._stop_alert_sound()
        self._alert_active = False
        self._finalise_session()

    def _stop_worker(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

    def _finalise_session(self):
        """Close the current DB session with computed aggregates."""
        if self._current_session_id is None:
            return
        avg = self._session_sum / self._session_total if self._session_total else 0.0
        close_session(
            self._current_session_id,
            peak_count=self._session_peak,
            avg_count=round(avg, 2),
            total_samples=self._session_total,
            alert_events=self._session_alerts,
        )
        self._current_session_id = None

    # ── Pipeline Communication ────────────────────────────────────────────

    def _on_frame(self, qimage: QImage):
        self.dash.update_frame(qimage)

    def _on_stats(self, count: int, density_label: str, density_color: str,
                  is_alert: bool, fps: float = 0.0, latency: float = 0.0):
        self.dash.update_stats(count, density_label, density_color, is_alert, fps, latency)

        # 1-Hz sample recording (live UI + database)
        now = time.monotonic()
        if now - self._last_reading_t >= 1.0:
            self._last_reading_t = now
            ts_str = datetime.now().strftime("%H:%M:%S")
            self.analy.add_reading(
                timestamp=ts_str,
                count=count,
                density=density_label,
                is_alert=is_alert,
            )
            # Persist to database
            if self._current_session_id is not None:
                insert_reading(self._current_session_id, count, density_label, is_alert)

            # Update rolling aggregates for session close
            self._session_total += 1
            self._session_sum   += count
            self._session_peak   = max(self._session_peak, count)
            if is_alert:
                self._session_alerts += 1

        # Alert handling
        if is_alert and not self._alert_active:
            self._alert_active = True
            log_event("ALERT_TRIGGERED",
                      f"count={count} limit={self.safety_limit}")
            self._play_alert_sound()
            self._send_desktop_notification(count)
        elif not is_alert and self._alert_active:
            self._alert_active = False
            self._stop_alert_sound()
            log_event("ALERT_CLEARED", f"count={count}")

        if is_alert:
            self.sb.showMessage(f"ALERT: {count} people detected (limit: {self.safety_limit})")

    def _on_video_ended(self):
        self._stop_worker()
        self._set_state("stopped")
        self.sb.showMessage("Playback complete.")
        log_event("VIDEO_ENDED", "")
        self._stop_alert_sound()
        self._alert_active = False
        self._finalise_session()

    def _on_detect_error(self, msg: str):
        self.sb.showMessage("A detection error occurred (see audit log).")
        log_event("DETECTION_ERROR", msg[:300])

    def _on_live(self, source: str):
        if not self.detector:
            self.sb.showMessage("Model is still loading.")
            return

        self._stop_worker()
        self.analy.clear_session()
        self._last_reading_t    = 0.0
        self._session_peak      = 0
        self._session_alerts    = 0
        self._session_total     = 0
        self._session_sum       = 0

        self.video_path   = source
        self.source_label = f"Camera {source}" if source.isdigit() else source

        # Open persistent session in DB
        self._current_session_id = create_session(self.source_label, self.safety_limit)

        self.worker = DetectionWorker(
            source=source,
            detector=self.detector,
            safety_limit=self.safety_limit,
            speed=getattr(self, "current_speed", 1.0),
            inference_interval=self.inference_interval,
            show_overlay=self._show_overlay,
        )
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.stats_updated.connect(self._on_stats)
        self.worker.video_ended.connect(self._on_video_ended)
        self.worker.error_occurred.connect(self._on_detect_error)
        self.worker.start()

        self._set_state("playing")
        log_event("LIVE_STARTED", f"source={source}")
        self.sb.showMessage(f"Live: {self.source_label}")

    def _on_speed(self, speed: float):
        self.current_speed = speed
        if self.worker:
            self.worker.speed = speed

    # ── Overlay Toggle ────────────────────────────────────────────────────

    def _on_overlay_toggled(self, show: bool):
        self._show_overlay = show
        if self.worker:
            self.worker.show_overlay = show

    # ── Settings ──────────────────────────────────────────────────────────

    def _on_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(
            safety_limit=self.safety_limit,
            confidence=self.confidence,
            inference_interval=self.inference_interval,
            inference_resolution=self.inference_resolution,
            parent=self,
        )
        if dlg.exec():
            self.safety_limit         = dlg.safety_limit
            self.confidence           = dlg.confidence
            self.inference_interval   = dlg.inference_interval
            self.inference_resolution = dlg.inference_resolution

            # Persist settings
            save_setting("safety_limit",         self.safety_limit)
            save_setting("confidence",            self.confidence)
            save_setting("inference_interval",    self.inference_interval)
            save_setting("inference_resolution",  self.inference_resolution)

            # Sync with Analytics tab
            self.analy.safety_limit = self.safety_limit

            if self.worker:
                self.worker.safety_limit       = self.safety_limit
                self.worker.inference_interval = self.inference_interval

            if self.detector:
                self.detector.confidence = self.confidence
                self.detector.imgsz      = self.inference_resolution

            log_event("SETTINGS_CHANGED",
                      f"limit={self.safety_limit} conf={self.confidence:.2f} "
                      f"interval={self.inference_interval} res={self.inference_resolution}")

    # ── Tab Changes ───────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int):
        if self.tabs.widget(index) is self.logs:
            self.logs.refresh()

    # ── Alert Sound & Notification ────────────────────────────────────────

    def _play_alert_sound(self):
        """Play Windows system alert sound once (non-blocking)."""
        try:
            winsound.PlaySound(
                "SystemAsterisk",
                winsound.SND_ALIAS | winsound.SND_ASYNC
            )
        except Exception:
            pass

    def _stop_alert_sound(self):
        """Stop playing alert sound."""
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def _send_desktop_notification(self, count: int):
        """Send a native desktop notification toast using QSystemTrayIcon (with cooldown)."""
        now = time.monotonic()
        if now - self._last_notification_t >= 30.0:
            self._last_notification_t = now
            self.tray_icon.showMessage(
                "CrowdSense - Safety Alert",
                f"Safety limit exceeded! {count} people detected.",
                QSystemTrayIcon.MessageIcon.Warning,
                8000
            )

    # ── State Management ──────────────────────────────────────────────────

    def _set_state(self, state: str):
        self.playback_state = state
        self.dash.set_playback_state(state)

    def _generate_check_image(self):
        """Programmatically generate a clean checkbox checkmark image if missing."""
        check_path = _ASSETS_DIR / "check.png"
        if not check_path.exists():
            try:
                _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                from PIL import Image, ImageDraw
                im = Image.new("RGBA", (16, 16), (255, 255, 255, 0))
                draw = ImageDraw.Draw(im)
                # Draw a sleek anti-aliased checkmark line
                draw.line([(3, 8), (7, 12), (13, 4)], fill=(230, 237, 243), width=2, joint="round")
                im.save(str(check_path))
            except Exception:
                pass

    def closeEvent(self, event):
        self._stop_alert_sound()
        self._stop_worker()
        self._finalise_session()
        super().closeEvent(event)