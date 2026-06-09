"""
CrowdSense — Analytics Tab  (src/ui/analytics.py)

Displays per-session detection statistics:
  • Peak count, average count, alert events, samples collected
  • Scrollable table of readings sampled at ~1 Hz
  • Export to CSV
"""

import csv
from datetime import datetime
from pathlib import Path

_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class _StatBox(QFrame):
    """Small modern flat stat card used in the top grid."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setStyleSheet(
            "QFrame#statCard {"
            "    background-color: #161b22;"
            "    border: 1px solid #21262d;"
            "    border-radius: 8px;"
            "}"
            "QLabel {"
            "    background: transparent;"
            "    border: none;"
            "}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)

        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;"
        )
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._lbl = QLabel("—")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._lbl.setStyleSheet(
            "font-size: 24px; font-weight: 600; color: #e6edf3;"
        )

        lay.addWidget(self._title_lbl)
        lay.addWidget(self._lbl)

    def set(self, text: str, color: str = "#e6edf3"):
        self._lbl.setText(text)
        self._lbl.setStyleSheet(
            f"font-size: 24px; font-weight: 600; color: {color};"
        )


class AnalyticsTab(QWidget):
    """Per-session analytics view."""

    MAX_ROWS = 500   # rolling window of stored readings

    def __init__(self, parent=None):
        super().__init__(parent)
        self._readings:     list[dict] = []
        self._peak:         int = 0
        self._alert_count:  int = 0
        self._build_ui()

    # ─── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 10)
        root.setSpacing(14)

        # Header row (Unified style matching Audit Logs tab)
        title = QLabel("Session Analytics")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e6edf3;")

        note = QLabel(
            "Real-time statistical aggregates and historical logs "
            "captured from the active monitoring session."
        )
        note.setStyleSheet("font-size: 11px; color: #8b949e;")
        note.setWordWrap(True)

        top = QHBoxLayout()
        top.addWidget(title)
        top.addSpacing(12)
        top.addWidget(note, 1)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self._export)
        top.addWidget(self.btn_export)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_session)
        top.addWidget(self.btn_clear)

        root.addLayout(top)

        # Stat cards grid
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        self.box_samples = _StatBox("Samples")
        self.box_peak    = _StatBox("Peak Count")
        self.box_avg     = _StatBox("Average")
        self.box_alerts  = _StatBox("Alert Events")

        grid.addWidget(self.box_samples, 0, 0)
        grid.addWidget(self.box_peak,    0, 1)
        grid.addWidget(self.box_avg,     0, 2)
        grid.addWidget(self.box_alerts,  0, 3)
        root.addWidget(grid_w)

        # Section header for the log table
        log_header_lbl = QLabel("Detection Log")
        log_header_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #e6edf3;")
        root.addWidget(log_header_lbl)

        # Detection log table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Time", "People Count", "Density", "Alert"]
        )
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { alternate-background-color: #111820; }"
        )
        root.addWidget(self.table, 1)

    # ─── Public API ───────────────────────────────────────────────────────

    def add_reading(self, timestamp: str, count: int,
                    density: str, is_alert: bool):
        """Append one detection sample and update all stats."""
        reading = {
            "timestamp": timestamp,
            "count":     count,
            "density":   density,
            "alert":     "YES" if is_alert else "no",
        }
        self._readings.append(reading)

        # Rolling window
        if len(self._readings) > self.MAX_ROWS:
            self._readings.pop(0)

        # Update aggregates
        self._peak = max(self._peak, count)
        if is_alert:
            self._alert_count += 1

        n   = len(self._readings)
        avg = sum(r["count"] for r in self._readings) / n if n else 0.0

        # Update stat cards
        self.box_samples.set(str(n))
        self.box_peak.set(
            str(self._peak),
            "#f85149" if self._peak >= 50 else ("#ff9800" if self._peak >= 25 else "#58a6ff")
        )
        self.box_avg.set(f"{avg:.1f}")
        self.box_alerts.set(
            str(self._alert_count),
            "#f85149" if self._alert_count > 0 else "#3fb950"
        )

        # Prepend row to table (newest first)
        self.table.insertRow(0)
        
        # Simple color map matching detector.py
        col_map = {
            "Low": "#3fb950",
            "Medium": "#ff9800",
            "High": "#f85149",
            "Critical": "#9c27b0"
        }
        density_color = col_map.get(density, "#e6edf3")
        alert_text = "ALERT" if is_alert else "no"
        alert_color = "#f85149" if is_alert else "#8b949e"

        vals = [timestamp, str(count), density, alert_text]
        for col, val in enumerate(vals):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 1 or col == 2:
                item.setForeground(QColor(density_color))
            elif col == 3:
                item.setForeground(QColor(alert_color))
            self.table.setItem(0, col, item)

    def clear_session(self):
        """Reset all session data."""
        self._readings.clear()
        self._peak        = 0
        self._alert_count = 0
        self.table.setRowCount(0)
        for box in (self.box_samples, self.box_peak, self.box_avg, self.box_alerts):
            box.set("—")

    # ─── Export ───────────────────────────────────────────────────────────

    def _export(self):
        if not self._readings:
            QMessageBox.information(self, "Export", "No data to export yet.")
            return

        _OUTPUT_DIR.mkdir(exist_ok=True)
        default = str(_OUTPUT_DIR / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session Log", default, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["timestamp", "count", "density", "alert"]
                )
                writer.writeheader()
                writer.writerows(self._readings)
            QMessageBox.information(self, "Export Complete",
                                    f"Session log saved to:\n{path}")
        except Exception:
            QMessageBox.critical(self, "Export Failed",
                                 "Could not write the file. Check permissions.")
