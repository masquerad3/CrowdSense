"""
CrowdSense — YOLO Person Detector  (src/detection/detector.py)

Wraps YOLOv8n / YOLO11n to:
  • Detect people (class 0) in a single video frame
  • Draw bounding boxes + confidence labels on the frame
  • Overlay a HUD panel (count + density level)
  • Draw an alert indicator when the safety limit is exceeded
  • Return structured stats for the UI
  • Support inference skipping: cached boxes are redrawn on skipped frames
    so the video stays smooth without running the model every frame.
  • Support configurable inference resolution (imgsz) for CPU speed control.
  • Automatically detects the best available model format (OpenVINO > ONNX > PyTorch)
    for maximum CPU inference performance.

Model auto-detection priority order (all searched inside models/):
  1. yolo11n_openvino_model/   (OpenVINO — fastest on Intel CPU, ~2-4x speedup)
  2. yolo11n.onnx              (ONNX Runtime — portable, ~1.5x speedup)
  3. yolo11n.pt               (PyTorch — baseline)
  4. yolov8n_openvino_model/  (OpenVINO fallback)
  5. yolov8n.onnx             (ONNX fallback)
  6. yolov8n.pt               (PyTorch fallback)
  If none are found, ultralytics will auto-download yolov8n.pt on first run.
"""

import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

# ── Model auto-detection ──────────────────────────────────────────────────────
_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"

# Priority order: OpenVINO > ONNX > PyTorch (for each model variant)
# Each entry: (path, display_label)
_CANDIDATES = [
    (_MODELS_DIR / "yolo11n_openvino_model", "YOLO11n (OpenVINO)"),
    (_MODELS_DIR / "yolo11n.onnx",           "YOLO11n (ONNX)"),
    (_MODELS_DIR / "yolo11n.pt",             "YOLO11n (PyTorch)"),
    (_MODELS_DIR / "yolov8n_openvino_model", "YOLOv8n (OpenVINO)"),
    (_MODELS_DIR / "yolov8n.onnx",           "YOLOv8n (ONNX)"),
    (_MODELS_DIR / "yolov8n.pt",             "YOLOv8n (PyTorch)"),
]

def _detect_best_model() -> tuple[Path, str]:
    """Return (model_path, display_label) for the best available format."""
    for path, label in _CANDIDATES:
        if path.exists():
            return path, label
    # Fallback: let ultralytics auto-download yolov8n.pt
    return _MODELS_DIR / "yolov8n.pt", "YOLOv8n (PyTorch)"


# ── Density classification ────────────────────────────────────────────────────
# Each entry: (min_count, max_count, label, qt_hex_color, cv2_bgr_color)
DENSITY_LEVELS = [
    (0,   10,   "Low",      "#4caf50", (80,  175, 76)),   # green
    (10,  25,   "Medium",   "#ff9800", (0,   152, 255)),  # orange
    (25,  50,   "High",     "#f44336", (54,  67,  244)),  # red
    (50,  9999, "Critical", "#9c27b0", (176, 39,  156)),  # purple
]


def _get_level(count: int) -> tuple[str, str, tuple]:
    """Return (label, hex_color, bgr_color) for a given people count."""
    for lo, hi, label, hex_col, bgr in DENSITY_LEVELS:
        if lo <= count < hi:
            return label, hex_col, bgr
    return DENSITY_LEVELS[-1][2], DENSITY_LEVELS[-1][3], DENSITY_LEVELS[-1][4]


class CrowdDetector:
    """
    YOLOv8n / YOLO11n-based person detector.

    Automatically selects the best available model format (OpenVINO > ONNX > PyTorch)
    from the models/ directory for maximum CPU performance.

    Usage:
        detector = CrowdDetector()
        annotated_frame, stats = detector.detect(frame, safety_limit=30)
        # On skipped frames (no inference needed):
        annotated_frame, stats = detector.detect(frame, safety_limit=30,
                                                  skip_inference=True)

    stats dict keys:
        count            int   — number of people detected
        density_label    str   — "Low" / "Medium" / "High" / "Critical"
        density_color_hex str  — hex color string for Qt widgets
        is_alert         bool  — True when count >= safety_limit

    Properties:
        model_name  — human-readable string identifying the loaded model and format,
                      e.g. "YOLO11n (OpenVINO)", "YOLO11n (ONNX)", "YOLOv8n (PyTorch)"

    Parameters:
        model_path  — explicit .pt / .onnx / OpenVINO path, or None to auto-detect
        confidence  — detection confidence threshold (0.0 – 1.0)
        imgsz       — YOLO inference resolution in pixels (e.g. 320, 416, 640)
                      Smaller = faster on CPU; display resolution is unaffected.
    """

    def __init__(self, model_path: str | None = None,
                 confidence: float = 0.40,
                 imgsz: int = 640):
        if model_path:
            path = str(model_path)
            # Derive a label from the explicit path
            p = Path(path)
            self._model_name = p.stem.replace("_", " ").title()
        else:
            best_path, best_label = _detect_best_model()
            path = str(best_path)
            self._model_name = best_label

        self.model      = YOLO(path, task='detect')
        self.confidence = confidence
        self.imgsz      = imgsz

        # ── Inference-skip cache ──────────────────────────────────────
        # Stores the boxes from the last real inference run so that
        # skipped frames can still display bounding boxes.
        self._cached_boxes: list[tuple] = []   # [(x1,y1,x2,y2,conf), ...]
        self._cached_count: int         = 0
        self._cached_stats: dict        = {
            "count": 0,
            "density_label":     "Low",
            "density_color_hex": "#4caf50",
            "is_alert":          False,
        }

        self._warmup()

    @property
    def model_name(self) -> str:
        """Human-readable model name and format, e.g. 'YOLO11n (OpenVINO)'."""
        return self._model_name

    def _warmup(self):
        """Run a dummy inference to initialize CUDA/CPU buffers."""
        dummy = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
        self.model.predict(dummy, conf=self.confidence, classes=[0],
                           imgsz=self.imgsz, verbose=False)

    # ─── Main detection method ────────────────────────────────────────────

    def detect(self, frame: np.ndarray,
               safety_limit: int = 30,
               skip_inference: bool = False) -> tuple:
        """
        Detect people in a BGR frame.

        Args:
            frame          — input BGR image (any resolution)
            safety_limit   — alert threshold (person count)
            skip_inference — if True, skip YOLO model call and reuse cached
                             boxes from the previous detected frame. This keeps
                             the video at full playback speed on slow CPUs.

        Returns: (annotated_frame: np.ndarray, stats: dict)
        """
        annotated = frame.copy()

        if not skip_inference:
            # ── Run YOLO ──────────────────────────────────────────────
            results = self.model.predict(
                frame,
                conf=self.confidence,
                classes=[0],        # class 0 = person in COCO
                imgsz=self.imgsz,
                verbose=False,
            )
            result = results[0]

            boxes: list[tuple] = []
            for box in result.boxes:
                if int(box.cls[0]) != 0:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf            = float(box.conf[0])
                boxes.append((x1, y1, x2, y2, conf))

            # Update cache
            self._cached_boxes = boxes
            self._cached_count = len(boxes)

        # Use cached or freshly computed boxes
        boxes = self._cached_boxes
        count = self._cached_count

        # ── Draw bounding boxes ────────────────────────────────────────
        box_color = (0, 230, 118)   # bright green
        for x1, y1, x2, y2, conf in boxes:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2)

            badge = f"{conf:.0%}"
            (tw, th), _ = cv2.getTextSize(
                badge, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1
            )
            cv2.rectangle(
                annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1),
                box_color, -1
            )
            cv2.putText(
                annotated, badge, (x1 + 2, y1 - 3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA
            )

        # ── Density & alert state ──────────────────────────────────────
        density_label, density_hex, density_bgr = _get_level(count)
        is_alert = count >= safety_limit

        # Update cached stats
        self._cached_stats = {
            "count":             count,
            "density_label":     density_label,
            "density_color_hex": density_hex,
            "is_alert":          is_alert,
        }

        h, w = annotated.shape[:2]

        # ── HUD panel (top-left semi-transparent overlay) ──────────────
        hud = annotated.copy()
        cv2.rectangle(hud, (0, 0), (260, 82), (8, 8, 12), -1)
        cv2.addWeighted(hud, 0.70, annotated, 0.30, 0, annotated)

        cv2.putText(
            annotated, f"People: {count}", (12, 30),
            cv2.FONT_HERSHEY_DUPLEX, 0.82, (255, 255, 255), 1, cv2.LINE_AA
        )
        cv2.putText(
            annotated, f"Density: {density_label}", (12, 64),
            cv2.FONT_HERSHEY_DUPLEX, 0.65, density_bgr, 1, cv2.LINE_AA
        )

        # ── Alert indicators ───────────────────────────────────────────
        if is_alert:
            cv2.rectangle(annotated, (0, 0), (w - 1, h - 1), (0, 0, 220), 5)

            bar = annotated.copy()
            cv2.rectangle(bar, (0, h - 48), (w, h), (0, 0, 130), -1)
            cv2.addWeighted(bar, 0.75, annotated, 0.25, 0, annotated)

            alert_text = "!! ALERT: SAFETY LIMIT EXCEEDED"
            (aw, _), _ = cv2.getTextSize(
                alert_text, cv2.FONT_HERSHEY_DUPLEX, 0.78, 2
            )
            ax = max(0, (w - aw) // 2)
            cv2.putText(
                annotated, alert_text, (ax, h - 14),
                cv2.FONT_HERSHEY_DUPLEX, 0.78, (255, 255, 255), 2, cv2.LINE_AA
            )

        return annotated, self._cached_stats
