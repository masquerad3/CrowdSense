"""
CrowdSense — Analytics Line Chart Widget (src/ui/graph.py)

A custom, high-end vector line chart widget painted using QPainter.
Supports smooth antialiased curves, vertical/horizontal gridlines,
gradient fills, and safety limit threshold indicators.
"""

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QLinearGradient, QPainterPath, QFont
)
from PyQt6.QtCore import Qt, QPointF, QRectF


class LineGraphWidget(QWidget):
    """
    Custom QPainter-drawn line graph.
    Pass in data as a list of readings containing person counts.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._readings: list[int] = []
        self._safety_limit: int = 30
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(150)
        self.setStyleSheet("background-color: #161b22; border: 1px solid #21262d; border-radius: 8px;")
        self.setMouseTracking(True)
        self._hover_idx = -1

    def set_data(self, counts: list[int], safety_limit: int = 30):
        """Update chart with new list of integer counts."""
        self._readings = counts
        self._safety_limit = safety_limit
        self.update()

    def clear(self):
        """Reset data list."""
        self._readings = []
        self._hover_idx = -1
        self.update()

    def mouseMoveEvent(self, event):
        if not self._readings:
            self._hover_idx = -1
            self.update()
            return

        w = self.width()
        margin_left = 40
        margin_right = 20
        pw = w - margin_left - margin_right

        if pw <= 0:
            self._hover_idx = -1
            self.update()
            return

        mx = event.position().x()
        n = len(self._readings)

        if n > 1:
            relative_x = mx - margin_left
            if 0 <= relative_x <= pw:
                idx = round((relative_x / pw) * (n - 1))
                self._hover_idx = max(0, min(idx, n - 1))
            else:
                self._hover_idx = -1
        elif n == 1:
            self._hover_idx = 0
        else:
            self._hover_idx = -1

        self.update()

    def leaveEvent(self, event):
        self._hover_idx = -1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Draw background and border matching stat cards
        bg_color = QColor("#161b22")
        border_color = QColor("#21262d")
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 8.0, 8.0)

        # Draw empty state message if no data points
        if not self._readings:
            painter.setPen(QPen(QColor("#8b949e")))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No sensor readings recorded for this session."
            )
            return

        # Dimensions & margins
        margin_left = 40
        margin_right = 20
        margin_top = 20
        margin_bottom = 25

        pw = w - margin_left - margin_right
        ph = h - margin_top - margin_bottom

        # Get statistics
        n = len(self._readings)
        max_val = max(self._readings)
        max_val = max(max_val, self._safety_limit, 10)  # scale axis reasonably

        # ── Draw Gridlines ────────────────────────────────────────────────────
        grid_pen = QPen(QColor("#21262d"), 1, Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)

        # Horizontal gridlines at 25%, 50%, 75%
        for ratio in [0.25, 0.50, 0.75]:
            gy = margin_top + ph - (ratio * ph)
            painter.drawLine(margin_left, int(gy), w - margin_right, int(gy))

            # Draw small horizontal axis text labels
            val_lbl = int(ratio * max_val)
            painter.setPen(QPen(QColor("#484f58")))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(
                margin_left - 35, int(gy + 4),
                f"{val_lbl:>3}"
            )
            painter.setPen(grid_pen)

        # ── Draw Safety Limit Line ───────────────────────────────────────────
        if self._safety_limit > 0:
            s_ratio = self._safety_limit / max_val
            sy = margin_top + ph - (s_ratio * ph)

            # Red dashed safety limit line
            safety_pen = QPen(QColor("#f85149"), 1, Qt.PenStyle.DashLine)
            painter.setPen(safety_pen)
            painter.drawLine(margin_left, int(sy), w - margin_right, int(sy))

            # Safety label text
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                w - margin_right - 90, int(sy - 4),
                f"LIMIT: {self._safety_limit}"
            )

        # ── Map Points ────────────────────────────────────────────────────────
        points = []
        for i, val in enumerate(self._readings):
            cx = margin_left + (i / (n - 1) * pw if n > 1 else pw / 2)
            cy = margin_top + ph - (val / max_val * ph)
            points.append(QPointF(cx, cy))

        # ── Draw Gradient Fill under the Curve ────────────────────────────────
        fill_path = QPainterPath()
        fill_path.moveTo(margin_left, margin_top + ph)
        for pt in points:
            fill_path.lineTo(pt)
        fill_path.lineTo(points[-1].x(), margin_top + ph)
        fill_path.closeSubpath()

        # Modern gradient: semi-transparent blue to transparent
        grad = QLinearGradient(0, margin_top, 0, margin_top + ph)
        grad.setColorAt(0.0, QColor(88, 166, 255, 60))
        grad.setColorAt(1.0, QColor(88, 166, 255, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(fill_path)

        # ── Draw Smooth Line Curve ────────────────────────────────────────────
        line_path = QPainterPath()
        line_path.moveTo(points[0])
        for pt in points[1:]:
            line_path.lineTo(pt)

        line_pen = QPen(QColor("#58a6ff"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line_path)

        # ── Draw Max & Current Labels ─────────────────────────────────────────
        painter.setPen(QPen(QColor("#8b949e")))
        painter.setFont(QFont("Segoe UI", 8))
        # Y-axis top label
        painter.drawText(margin_left - 35, margin_top + 4, f"{int(max_val):>3}")
        # Y-axis bottom label
        painter.drawText(margin_left - 35, margin_top + ph + 4, "  0")

        # X-axis label (Samples)
        painter.drawText(
            margin_left, margin_top + ph + 16,
            f"0 sec"
        )
        painter.drawText(
            w - margin_right - 60, margin_top + ph + 16,
            f"{n} samples (1Hz)"
        )

        # ── Draw Hover Guide & Tooltip ────────────────────────────────────────
        if self._hover_idx != -1 and self._hover_idx < len(points):
            pt = points[self._hover_idx]
            cx = pt.x()
            cy = pt.y()

            # 1. Vertical dashed guide line
            guide_pen = QPen(QColor("#8b949e"), 1, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            painter.drawLine(int(cx), margin_top, int(cx), margin_top + ph)

            # 2. Concentric highlight circle at data point
            painter.setBrush(QBrush(QColor(88, 166, 255, 60)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), 8.0, 8.0)

            painter.setBrush(QBrush(QColor("#58a6ff")))
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.drawEllipse(QPointF(cx, cy), 4.5, 4.5)

            # 3. Floating tooltip box
            val = self._readings[self._hover_idx]
            time_txt = f"Time: {self._hover_idx}s"
            count_txt = f"Count: {val}"

            box_w = 90
            box_h = 42

            # Position tooltip box near point, preventing viewport clipping
            bx = cx + 12 if cx + 12 + box_w < w - margin_right else cx - 12 - box_w
            by = cy - box_h - 10 if cy - box_h - 10 > margin_top else cy + 10

            # Draw tooltip box background
            painter.setBrush(QBrush(QColor(13, 17, 23, 230)))
            painter.setPen(QPen(QColor("#30363d"), 1))
            painter.drawRoundedRect(QRectF(bx, by, box_w, box_h), 4.0, 4.0)

            # Draw text
            painter.setPen(QPen(QColor("#c9d1d9")))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(int(bx + 8), int(by + 16), count_txt)

            painter.setPen(QPen(QColor("#8b949e")))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(int(bx + 8), int(by + 32), time_txt)
