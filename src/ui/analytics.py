"""
CrowdSense — Analytics Tab (src/ui/analytics.py)

Two sub-tabs:
  • Live Session — real-time per-session statistics and line graph
  • History      — historical sessions retrieved from SQLite with detailed readings list and graph
"""

import csv
from datetime import datetime
from pathlib import Path

_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QFrame, QTabWidget, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ui.graph import LineGraphWidget


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

        self._lbl = QLabel("-")
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
    """Analytics view with Live Session and History sub-tabs."""

    MAX_ROWS = 500   # rolling window of stored readings

    def __init__(self, parent=None):
        super().__init__(parent)
        self._readings: list[dict] = []
        self._peak: int = 0
        self._alert_count: int = 0
        self.safety_limit: int = 30
        self._build_ui()

    # ─── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("subTabs")  # targeted in styles to remove line
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(self._make_live_tab(),    "Live Session")
        self._tabs.addTab(self._make_history_tab(), "History")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        root.addWidget(self._tabs)

    # ── Live Session tab ──────────────────────────────────────────────────

    def _make_live_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 12, 16, 10)
        lay.setSpacing(12)

        # Header row
        title = QLabel("Live Session")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e6edf3;")

        note = QLabel(
            "Real-time statistical aggregates captured from the active monitoring session."
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

        lay.addLayout(top)

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
        lay.addWidget(grid_w)

        # Live Line Chart
        self.live_graph = LineGraphWidget()
        lay.addWidget(self.live_graph, 1)

        # Section header for the log table
        log_header_lbl = QLabel("Detection Log")
        log_header_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #e6edf3;")
        lay.addWidget(log_header_lbl)

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
        lay.addWidget(self.table, 1)

        return tab

    # ── History tab ───────────────────────────────────────────────────────

    def _make_history_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 12, 16, 10)
        lay.setSpacing(10)

        # Header row
        title = QLabel("Session History")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e6edf3;")

        note = QLabel(
            "All completed detection sessions stored in the database."
        )
        note.setStyleSheet("font-size: 11px; color: #8b949e;")

        top = QHBoxLayout()
        top.addWidget(title)
        top.addSpacing(12)
        top.addWidget(note, 1)

        self.btn_history_refresh = QPushButton("Refresh")
        self.btn_history_refresh.clicked.connect(self._load_history)
        top.addWidget(self.btn_history_refresh)

        self.btn_history_export = QPushButton("Export CSV")
        self.btn_history_export.clicked.connect(self._export_selected_session)
        top.addWidget(self.btn_history_export)

        self.btn_history_delete = QPushButton("Delete All Sessions")
        self.btn_history_delete.setObjectName("dangerBtn")
        self.btn_history_delete.clicked.connect(self._on_delete_all_sessions)
        top.addWidget(self.btn_history_delete)

        lay.addLayout(top)

        # Splitter: sessions list on top, readings details + graph on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Sessions table
        sess_widget = QWidget()
        sess_lay = QVBoxLayout(sess_widget)
        sess_lay.setContentsMargins(0, 0, 0, 0)
        sess_lay.setSpacing(6)

        sess_hdr = QLabel("Sessions")
        sess_hdr.setStyleSheet("font-size: 12px; font-weight: 600; color: #8b949e;")
        sess_lay.addWidget(sess_hdr)

        self.tbl_sessions = QTableWidget()
        self.tbl_sessions.setColumnCount(6)
        self.tbl_sessions.setHorizontalHeaderLabels(
            ["Date", "Source", "Duration", "Peak", "Avg", "Alerts"]
        )
        shh = self.tbl_sessions.horizontalHeader()
        shh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        shh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        shh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for col in (3, 4, 5):
            shh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_sessions.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_sessions.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_sessions.verticalHeader().setVisible(False)
        self.tbl_sessions.setAlternatingRowColors(True)
        self.tbl_sessions.setStyleSheet(
            "QTableWidget { alternate-background-color: #111820; }"
        )
        self.tbl_sessions.itemSelectionChanged.connect(self._on_session_selected)
        self.tbl_sessions.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_sessions.customContextMenuRequested.connect(self._show_context_menu)
        sess_lay.addWidget(self.tbl_sessions)
        splitter.addWidget(sess_widget)

        # Readings details row (readings table on left, line chart on right)
        detail_container = QWidget()
        detail_lay = QHBoxLayout(detail_container)
        detail_lay.setContentsMargins(0, 8, 0, 0)
        detail_lay.setSpacing(12)
        # Force top alignment so header labels match vertically
        detail_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Table panel
        from PyQt6.QtWidgets import QSizePolicy
        tbl_panel = QWidget()
        tbl_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tbl_panel_lay = QVBoxLayout(tbl_panel)
        tbl_panel_lay.setContentsMargins(0, 0, 0, 0)
        tbl_panel_lay.setSpacing(6)

        detail_hdr = QLabel("Session Readings")
        detail_hdr.setStyleSheet("font-size: 12px; font-weight: 600; color: #8b949e;")
        tbl_panel_lay.addWidget(detail_hdr)

        self.tbl_readings = QTableWidget()
        self.tbl_readings.setColumnCount(4)
        self.tbl_readings.setHorizontalHeaderLabels(
            ["Time", "Count", "Density", "Alert"]
        )
        rhh = self.tbl_readings.horizontalHeader()
        rhh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        rhh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        rhh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        rhh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_readings.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_readings.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_readings.verticalHeader().setVisible(False)
        self.tbl_readings.setAlternatingRowColors(True)
        self.tbl_readings.setStyleSheet(
            "QTableWidget { alternate-background-color: #111820; }"
        )
        tbl_panel_lay.addWidget(self.tbl_readings)
        detail_lay.addWidget(tbl_panel, 4)

        # Graph panel
        graph_panel = QWidget()
        graph_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        graph_panel_lay = QVBoxLayout(graph_panel)
        graph_panel_lay.setContentsMargins(0, 0, 0, 0)
        graph_panel_lay.setSpacing(6)

        graph_hdr = QLabel("Visual Trend")
        graph_hdr.setStyleSheet("font-size: 12px; font-weight: 600; color: #8b949e;")
        graph_panel_lay.addWidget(graph_hdr)

        self.history_graph = LineGraphWidget()
        graph_panel_lay.addWidget(self.history_graph)
        detail_lay.addWidget(graph_panel, 6)

        splitter.addWidget(detail_container)
        splitter.setSizes([260, 260])
        lay.addWidget(splitter, 1)

        # Store session id list for export
        self._session_ids: list[int] = []

        return tab

    # ─── Public API ───────────────────────────────────────────────────────

    def add_reading(self, timestamp: str, count: int,
                    density: str, is_alert: bool):
        """Append one detection sample and update all live stats."""
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

        # Update Live Graph
        self.live_graph.set_data([r["count"] for r in self._readings], safety_limit=self.safety_limit)

        # Prepend row to table (newest first)
        self.table.insertRow(0)

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
        """Reset all live session data."""
        self._readings.clear()
        self._peak        = 0
        self._alert_count = 0
        self.table.setRowCount(0)
        self.live_graph.clear()
        for box in (self.box_samples, self.box_peak, self.box_avg, self.box_alerts):
            box.set("-")

    # ─── History loading ──────────────────────────────────────────────────

    def _on_tab_changed(self, index: int):
        if index == 1:  # History tab
            self._load_history()

    def _load_history(self):
        from auth.db import get_sessions
        sessions = get_sessions(limit=200)
        self._session_ids = [s["id"] for s in sessions]
        self._session_safety_limits = {s["id"]: s.get("safety_limit", 30) for s in sessions}
        self.tbl_sessions.setRowCount(0)
        self.tbl_readings.setRowCount(0)
        self.history_graph.clear()

        for s in sessions:
            r = self.tbl_sessions.rowCount()
            self.tbl_sessions.insertRow(r)

            # Date
            started = str(s.get("started_at", ""))[:19].replace("T", " ")
            self.tbl_sessions.setItem(r, 0, QTableWidgetItem(started))

            # Source label
            self.tbl_sessions.setItem(r, 1, QTableWidgetItem(str(s.get("source_label") or "-")))

            # Duration
            dur = "-"
            try:
                t_start = datetime.fromisoformat(str(s["started_at"]))
                if s.get("ended_at"):
                    t_end = datetime.fromisoformat(str(s["ended_at"]))
                    secs = int((t_end - t_start).total_seconds())
                    dur = f"{secs // 60}m {secs % 60}s"
            except Exception:
                pass
            self.tbl_sessions.setItem(r, 2, QTableWidgetItem(dur))

            # Peak
            peak = s.get("peak_count", 0)
            peak_item = QTableWidgetItem(str(peak))
            peak_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if peak >= 50:
                peak_item.setForeground(QColor("#9c27b0"))
            elif peak >= 25:
                peak_item.setForeground(QColor("#f85149"))
            elif peak >= 10:
                peak_item.setForeground(QColor("#ff9800"))
            self.tbl_sessions.setItem(r, 3, peak_item)

            # Avg
            avg_item = QTableWidgetItem(f"{s.get('avg_count', 0):.1f}")
            avg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_sessions.setItem(r, 4, avg_item)

            # Alerts
            alerts = s.get("alert_events", 0)
            alert_item = QTableWidgetItem(str(alerts))
            alert_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if alerts > 0:
                alert_item.setForeground(QColor("#f85149"))
            else:
                alert_item.setForeground(QColor("#3fb950"))
            self.tbl_sessions.setItem(r, 5, alert_item)

    def _on_session_selected(self):
        row = self.tbl_sessions.currentRow()
        if row < 0 or row >= len(self._session_ids):
            return
        session_id = self._session_ids[row]
        safety_limit = getattr(self, "_session_safety_limits", {}).get(session_id, 30)
        self._load_readings(session_id, safety_limit)

    def _load_readings(self, session_id: int, safety_limit: int = 30):
        from auth.db import get_session_readings
        readings = get_session_readings(session_id)
        self.tbl_readings.setRowCount(0)
        self.history_graph.clear()

        col_map = {
            "Low": "#3fb950",
            "Medium": "#ff9800",
            "High": "#f85149",
            "Critical": "#9c27b0"
        }

        # Load Graph
        counts = [rd.get("count", 0) for rd in readings]
        self.history_graph.set_data(counts, safety_limit=safety_limit)

        # Load Table
        for rd in readings:
            r = self.tbl_readings.rowCount()
            self.tbl_readings.insertRow(r)

            ts = str(rd.get("sampled_at", ""))[:19].replace("T", " ")
            self.tbl_readings.setItem(r, 0, QTableWidgetItem(ts))

            count = rd.get("count", 0)
            density = str(rd.get("density", ""))
            is_alert = bool(rd.get("alert_active", 0))

            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            count_item.setForeground(QColor(col_map.get(density, "#e6edf3")))
            self.tbl_readings.setItem(r, 1, count_item)

            density_item = QTableWidgetItem(density)
            density_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            density_item.setForeground(QColor(col_map.get(density, "#e6edf3")))
            self.tbl_readings.setItem(r, 2, density_item)

            alert_text = "ALERT" if is_alert else "-"
            alert_item = QTableWidgetItem(alert_text)
            alert_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            alert_item.setForeground(QColor("#f85149" if is_alert else "#8b949e"))
            self.tbl_readings.setItem(r, 3, alert_item)

    def _show_context_menu(self, pos):
        item = self.tbl_sessions.itemAt(pos)
        if item is None:
            return
        row = self.tbl_sessions.row(item)
        self.tbl_sessions.selectRow(row)

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Session")
        action = menu.exec(self.tbl_sessions.viewport().mapToGlobal(pos))
        if action == delete_action:
            self._delete_session_at_row(row)

    def _on_delete_all_sessions(self):
        reply = QMessageBox.warning(
            self, "Delete All Sessions",
            "Are you sure you want to permanently delete ALL sessions and all their readings?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from auth.db import delete_all_sessions
            if delete_all_sessions():
                QMessageBox.information(self, "Deleted", "All sessions successfully deleted.")
                self._load_history()
            else:
                QMessageBox.critical(self, "Error", "Could not delete sessions.")

    def _delete_session_at_row(self, row: int):
        if row < 0 or row >= len(self._session_ids):
            return
        session_id = self._session_ids[row]
        reply = QMessageBox.warning(
            self, "Delete Session",
            "Are you sure you want to permanently delete this session and all its readings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from auth.db import delete_session
            if delete_session(session_id):
                QMessageBox.information(self, "Deleted", "Session successfully deleted.")
                self._load_history()
            else:
                QMessageBox.critical(self, "Error", "Could not delete session.")

    def _export_selected_session(self):
        row = self.tbl_sessions.currentRow()
        if row < 0 or row >= len(self._session_ids):
            QMessageBox.information(self, "Export", "Select a session row to export.")
            return
        session_id = self._session_ids[row]
        from auth.db import get_session_readings
        readings = get_session_readings(session_id)
        if not readings:
            QMessageBox.information(self, "Export", "No readings found for this session.")
            return

        _OUTPUT_DIR.mkdir(exist_ok=True)
        default = str(_OUTPUT_DIR / f"session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session Readings", default, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["sampled_at", "count", "density", "alert_active"]
                )
                writer.writeheader()
                writer.writerows(readings)
            QMessageBox.information(self, "Export Complete",
                                    f"Session readings saved to:\n{path}")
        except Exception:
            QMessageBox.critical(self, "Export Failed",
                                 "Could not write the file. Check permissions.")

    # ─── Live Export ──────────────────────────────────────────────────────

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
