"""
CrowdSense — Audit Logs Tab  (src/ui/logs_tab.py)

Displays the audit log from the database.
Supports full-text search and an Alerts Only toggle to show only alert events.
"""

import csv
import winsound
from datetime import datetime
from pathlib import Path

_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QLineEdit, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from auth.db import get_audit_log


class LogsTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alerts_only = False
        self._build_ui()

    # ─── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 10)
        root.setSpacing(10)

        # Header row
        title = QLabel("Audit Log")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e6edf3;")

        note = QLabel(
            "All video loads, detections, alerts, and key actions "
            "are recorded here with a cryptographic hash chain."
        )
        note.setStyleSheet("font-size: 11px; color: #8b949e;")
        note.setWordWrap(True)

        top = QHBoxLayout()
        top.addWidget(title)
        top.addSpacing(12)
        top.addWidget(note, 1)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh)
        top.addWidget(btn_refresh)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self._export)
        top.addWidget(self.btn_export)

        root.addLayout(top)

        # Search Bar & Alerts-Only toggle row
        filter_lay = QHBoxLayout()
        search_lbl = QLabel("Search:")
        search_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #8b949e;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search action or details...")
        self.txt_search.textChanged.connect(self._on_search_changed)

        self.chk_alerts = QCheckBox("Alerts Only")
        self.chk_alerts.toggled.connect(self._on_alerts_only_toggled)

        filter_lay.addWidget(search_lbl)
        filter_lay.addWidget(self.txt_search, 1)
        filter_lay.addSpacing(12)
        filter_lay.addWidget(self.chk_alerts)
        root.addLayout(filter_lay)

        # Integrity check label
        self.lbl_integrity = QLabel()
        self.lbl_integrity.setStyleSheet(
            "font-size: 11px; font-weight: 600; padding: 6px; border-radius: 4px;"
        )
        self.lbl_integrity.hide()
        root.addWidget(self.lbl_integrity)

        # Audit log table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Action", "Details"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { alternate-background-color: #111820; }"
        )
        root.addWidget(self.table, 1)

    # ─── Slots ────────────────────────────────────────────────────────────

    def _on_search_changed(self, _text: str):
        self.refresh_data()

    def _on_alerts_only_toggled(self, checked: bool):
        self._alerts_only = checked
        self.refresh_data()

    # ─── Data Loading ─────────────────────────────────────────────────────

    def refresh(self):
        self.refresh_data()

    def refresh_data(self):
        from auth.db import verify_audit_log_integrity
        integrity_ok = verify_audit_log_integrity()

        if integrity_ok:
            self.lbl_integrity.hide()
        else:
            self.lbl_integrity.setText("CRITICAL: Database tampering detected! Audit log integrity check failed.")
            self.lbl_integrity.setStyleSheet(
                "font-size: 11px; font-weight: 600; padding: 6px; border-radius: 4px;"
                "background: #3d1a1a; color: #f85149; border: 1px solid #5a1e1e;"
            )
            self.lbl_integrity.show()
            # Play a system error chime once on tamper detection
            try:
                winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                pass

        search = self.txt_search.text().strip() or None
        rows = get_audit_log(limit=None, search_query=search, alerts_only=self._alerts_only)

        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            ts = str(row.get("timestamp", ""))[:19].replace("T", " ")
            vals = [
                ts,
                str(row.get("action", "")),
                str(row.get("details", "")),
            ]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col == 1 and "ALERT" in val.upper():
                    item.setForeground(QColor("#f85149"))
                self.table.setItem(r, col, item)

    # ─── Export ───────────────────────────────────────────────────────────

    def _export(self):
        search = self.txt_search.text().strip() or None
        rows = get_audit_log(limit=None, search_query=search, alerts_only=self._alerts_only)
        if not rows:
            QMessageBox.information(self, "Export", "No log entries to export.")
            return

        _OUTPUT_DIR.mkdir(exist_ok=True)
        default = str(_OUTPUT_DIR / f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Audit Log", default, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["timestamp", "action", "details", "entry_hash"]
                )
                writer.writeheader()
                writer.writerows(rows)
            QMessageBox.information(self, "Export Complete",
                                    f"Audit log saved to:\n{path}")
        except Exception:
            QMessageBox.critical(self, "Export Failed",
                                 "Could not write the file. Check permissions.")
