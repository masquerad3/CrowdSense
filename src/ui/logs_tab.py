"""
CrowdSense — Audit Logs Tab  (src/ui/logs_tab.py)

Displays the audit log from the database.
Role-based access:
  admin  — can refresh AND export to CSV
  user   — can only view (no export button)
"""

import csv
from datetime import datetime
from pathlib import Path

_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from auth.db import get_audit_log


class LogsTab(QWidget):

    def __init__(self, username: str, role: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.role = role
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
            "All login attempts, logouts, video loads, and key actions "
            "are recorded here for accountability."
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
        self.btn_export.setVisible(self.role == "admin")

        root.addLayout(top)

        # Search Bar & User Filter Row
        search_lay = QHBoxLayout()
        search_lbl = QLabel("Search:")
        search_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #8b949e;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search action or details...")
        self.txt_search.textChanged.connect(self._on_search_changed)
        
        user_lbl = QLabel("User Filter:")
        user_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #8b949e;")
        self.cmb_user_filter = QComboBox()
        # Enable autocomplete search inside the dropdown
        self.cmb_user_filter.setEditable(True)
        self.cmb_user_filter.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if self.cmb_user_filter.lineEdit():
            self.cmb_user_filter.lineEdit().setPlaceholderText("Search/select user...")
        completer = self.cmb_user_filter.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.cmb_user_filter.currentTextChanged.connect(self._on_user_filter_changed)
        
        search_lay.addWidget(search_lbl)
        search_lay.addWidget(self.txt_search, 1)
        search_lay.addSpacing(12)
        search_lay.addWidget(user_lbl)
        search_lay.addWidget(self.cmb_user_filter)
        root.addLayout(search_lay)

        # Integrity check label
        self.lbl_integrity = QLabel()
        self.lbl_integrity.setStyleSheet(
            "font-size: 11px; font-weight: 600; padding: 6px; border-radius: 4px;"
        )
        root.addWidget(self.lbl_integrity)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Timestamp", "Username", "Action", "Details"]
        )
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { alternate-background-color: #111820; }"
        )
        root.addWidget(self.table, 1)

        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet("font-size: 11px; color: #484f58;")
        root.addWidget(self.lbl_count)

    # ─── Public API ───────────────────────────────────────────────────────

    def set_user_context(self, username: str, role: str):
        """Update active operator's context."""
        self.username = username
        self.role = role
        self.btn_export.setVisible(role == "admin")

    def refresh(self):
        """Full refresh: updates user dropdown list and selects current user by default."""
        self.txt_search.blockSignals(True)
        self.txt_search.clear()
        self.txt_search.blockSignals(False)

        # Populate user filter dropdown from users table
        from auth.db import get_users
        users_list = get_users()
        usernames = ["[All Users]"] + [u["username"] for u in users_list]

        self.cmb_user_filter.blockSignals(True)
        self.cmb_user_filter.clear()
        self.cmb_user_filter.addItems(usernames)
        
        # Default to showing the current logged-in user's logs
        if self.username in usernames:
            self.cmb_user_filter.setCurrentText(self.username)
        else:
            self.cmb_user_filter.setCurrentIndex(0)
        self.cmb_user_filter.blockSignals(False)

        self.refresh_data()

    def refresh_data(self):
        """Reload the audit log from the database matching the active filters."""
        from auth.db import verify_audit_log_integrity
        integrity_ok = verify_audit_log_integrity()
        if integrity_ok:
            self.lbl_integrity.hide()
        else:
            self.lbl_integrity.setText("CRITICAL: Database tampering detected! Audit log integrity check failed.")
            self.lbl_integrity.setStyleSheet(
                "font-size: 11px; font-weight: 600; padding: 6px; border-radius: 4px; "
                "background-color: rgba(248, 81, 73, 0.12); color: #f85149; border: 1px solid rgba(248, 81, 73, 0.25);"
            )
            self.lbl_integrity.show()

        query = self.txt_search.text().strip()
        selected_user = self.cmb_user_filter.currentText().strip() if self.cmb_user_filter.count() > 0 else "[All Users]"

        rows = get_audit_log(
            limit=500,
            username=selected_user,
            search_query=query if query else None
        )
        self.table.setRowCount(0)

        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)

            ts     = str(row.get("timestamp", ""))[:19].replace("T", "  ")
            user   = str(row.get("username", ""))
            action = str(row.get("action",   ""))
            detail = str(row.get("details",  ""))

            vals = [ts, user, action, detail]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col == 2:
                    # Color-code the action column
                    if "FAILED" in action or "ERROR" in action:
                        item.setForeground(QColor("#f85149"))   # red
                    elif "SUCCESS" in action:
                        item.setForeground(QColor("#3fb950"))   # green
                    elif "LOGOUT" in action:
                        item.setForeground(QColor("#ff9800"))   # orange
                    else:
                        item.setForeground(QColor("#8b949e"))   # muted
                self.table.setItem(r, col, item)

        n = len(rows)
        self.lbl_count.setText(
            f"Showing {n} most recent matching record{'s' if n != 1 else ''}  "
            f"(max 500)"
        )

    def _on_search_changed(self):
        self.refresh_data()

    def _on_user_filter_changed(self):
        self.refresh_data()

    # ─── Export ───────────────────────────────────────────────────────────

    def _export(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "Export", "No records to export.")
            return

        _OUTPUT_DIR.mkdir(exist_ok=True)
        default = str(_OUTPUT_DIR / f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Audit Log", default, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            query = self.txt_search.text().strip()
            selected_user = self.cmb_user_filter.currentText().strip() if self.cmb_user_filter.count() > 0 else "[All Users]"

            rows = get_audit_log(
                limit=None,
                username=selected_user,
                search_query=query if query else None
            )
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["timestamp", "username", "action", "details"]
                )
                writer.writeheader()
                writer.writerows(rows)
            QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")
        except Exception:
            QMessageBox.critical(self, "Export Failed",
                                 "Could not write the file. Check permissions.")
