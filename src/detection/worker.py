"""
CrowdSense — Detection Worker Threads  (src/detection/worker.py)

ModelLoaderWorker  — loads YOLO in the background so the UI stays responsive
DetectionWorker    — reads frames and runs detection; supports:
                       * video file paths  (str)
                       * camera indices    (int, or str digit e.g. "0")

Performance knobs:
  inference_interval — run YOLO only every N frames (default 1 = every frame).
                       Frames in between are still emitted with cached boxes
                       and stats drawn by the detector, keeping playback smooth.

For live sources (camera), temporary read failures are retried rather
than treated as end-of-stream, and video_ended is never emitted.
"""

import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from detection.detector import CrowdDetector


class ModelLoaderWorker(QThread):
    ready = pyqtSignal(object)   # emits CrowdDetector on success
    error = pyqtSignal(str)

    def __init__(self, model_path=None, confidence: float = 0.40,
                 imgsz: int = 640, parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.confidence = confidence
        self.imgsz      = imgsz

    def run(self):
        try:
            self.ready.emit(
                CrowdDetector(self.model_path, self.confidence, self.imgsz)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class DetectionWorker(QThread):
    """
    Reads frames from a source and emits annotated frames + stats.

    source             — str file path | str camera index ("0", "1") | int camera index
    detector           — CrowdDetector instance
    safety_limit       — person count threshold for alerts
    speed              — playback speed multiplier (file sources only)
    inference_interval — run YOLO inference on every Nth frame (1 = every frame,
                         2 = every other frame, 3 = every third frame, etc.).
                         Skipped frames still display cached boxes — no flickering.
    is_live            — set automatically based on source type
    """

    frame_ready    = pyqtSignal(QImage)
    stats_updated  = pyqtSignal(int, str, str, bool, float, float)   # count, label, hex_color, is_alert, fps, latency
    video_ended    = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, source, detector: CrowdDetector,
                 safety_limit: int = 30, speed: float = 1.0,
                 inference_interval: int = 1,
                 show_overlay: bool = True, parent=None):
        super().__init__(parent)
        self.detector           = detector
        self.safety_limit       = safety_limit
        self.speed              = speed
        self.inference_interval = max(1, inference_interval)
        self.show_overlay       = show_overlay
        self._running           = True
        self._paused            = False
        self._frame_count       = 0   # counts every decoded frame
        self._last_frame_time   = None
        self._fps_ema           = None

        # Normalise source and classify as live or file
        if isinstance(source, int):
            self._src    = source
            self.is_live = True
        elif isinstance(source, str) and source.strip().isdigit():
            self._src    = int(source.strip())
            self.is_live = True
        else:
            self._src    = source
            self.is_live = False

    def run(self):
        cap = cv2.VideoCapture(self._src)
        if not cap.isOpened():
            self.error_occurred.emit("Cannot open source.")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        import time

        self._last_frame_time = None
        self._fps_ema = None

        while self._running:
            if self._paused:
                self.msleep(50)
                continue

            ret, frame = cap.read()
            if not ret:
                if self.is_live:
                    self.msleep(50)   # transient camera hiccup — retry
                    continue
                else:
                    self.video_ended.emit()
                    break

            self._frame_count += 1
            # Skip inference on frames that are not multiples of the interval.
            # The detector will reuse cached boxes from the last real inference.
            skip = (self.inference_interval > 1 and
                    self._frame_count % self.inference_interval != 0)

            t_start = time.perf_counter()
            try:
                annotated, stats = self.detector.detect(
                    frame,
                    self.safety_limit,
                    skip_inference=skip,
                    show_overlay=self.show_overlay,
                )
            except Exception as exc:
                self.error_occurred.emit(str(exc))
                continue
            t_end = time.perf_counter()
            inference_ms = (t_end - t_start) * 1000.0

            # Calculate actual loop rendering FPS
            t_now = time.perf_counter()
            if self._last_frame_time is not None:
                dt = t_now - self._last_frame_time
                instant_fps = 1.0 / dt if dt > 0 else 0.0
                if self._fps_ema is None:
                    self._fps_ema = instant_fps
                else:
                    self._fps_ema = 0.9 * self._fps_ema + 0.1 * instant_fps
            else:
                self._fps_ema = 0.0
            self._last_frame_time = t_now

            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

            self.frame_ready.emit(qimg)
            self.stats_updated.emit(
                stats["count"],
                stats["density_label"],
                stats["density_color_hex"],
                stats["is_alert"],
                self._fps_ema or 0.0,
                inference_ms,
            )

            # Frame-rate throttle
            if self.is_live:
                self.msleep(33)   # ~30 fps cap for live feeds
            else:
                delay = max(1, int(1000 / (fps * max(0.1, self.speed))))
                self.msleep(delay)

        cap.release()

    def pause(self):  self._paused = True
    def resume(self): 
        self._paused = False
        self._last_frame_time = None

    def stop(self):
        self._running = False
        self._paused  = False
        self.wait(3000)
