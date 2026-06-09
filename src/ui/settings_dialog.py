"""
CrowdSense — Settings Dialog  (src/ui/settings_dialog.py)
Admin-only: detection tuning + full user management (create, lock, unlock,
edit role, change password, delete, search).
"""

import re
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton, QTabWidget,
    QWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QFrame, QMessageBox, QAbstractSpinBox,
    QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, QSortFilterProxyModel
from PyQt6.QtGui import QColor

from auth.db import (
    get_users, create_user, reset_lockout, lock_user,
    update_role, delete_user, change_password,
)

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,64}$')


class SettingsDialog(QDialog):
    """
    Admin settings dialog.
    After accept(), read:  dlg.safety_limit, dlg.confidence,
                           dlg.inference_interval, dlg.inference_resolution
    """

    # Resolution options: display label → pixel size
    _RESOLUTIONS = [
        ("320 px  (Fastest)",       320),
        ("416 px  (Balanced)",      416),
        ("640 px  (Most Accurate)", 640),
    ]

    def __init__(self, safety_limit: int, confidence: float,
                 inference_interval: int = 1,
                 inference_resolution: int = 640,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings — CrowdSense")
        self.resize(600, 620)
        self.setModal(True)

        self.safety_limit        = safety_limit
        self.confidence          = confidence
        self.inference_interval  = inference_interval
        self.inference_resolution = inference_resolution

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._make_detection_tab(), "Detection")
        tabs.addTab(self._make_users_tab(),     "Users")

        root.addWidget(tabs, 1)
        root.addWidget(self._make_button_row())

    # ── Detection tab ─────────────────────────────────────────────────────

    def _make_detection_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(32, 28, 32, 16)
        lay.setSpacing(20)

        form = QFormLayout()
        form.setSpacing(18)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Safety limit — manual number field (no buttons) with a separate suffix label
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 500)
        self.spin_limit.setValue(self.safety_limit)
        self.spin_limit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_limit.setMinimumWidth(120)
        self.spin_limit.setFixedHeight(36)

        limit_layout = QHBoxLayout()
        limit_layout.setSpacing(8)
        limit_layout.addWidget(self.spin_limit)
        lbl_people = QLabel("people")
        lbl_people.setStyleSheet("color: #8b949e;")
        limit_layout.addWidget(lbl_people)
        limit_layout.addStretch()
        form.addRow("Safety limit:", limit_layout)

        # Confidence threshold — manual number field (no buttons)
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.10, 0.90)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setDecimals(2)
        self.spin_conf.setValue(self.confidence)
        self.spin_conf.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_conf.setMinimumWidth(120)
        self.spin_conf.setFixedHeight(36)

        conf_layout = QHBoxLayout()
        conf_layout.setSpacing(8)
        conf_layout.addWidget(self.spin_conf)
        conf_layout.addStretch()
        form.addRow("Confidence:", conf_layout)

        # ── Inference interval ─────────────────────────────────────────────
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 30)
        self.spin_interval.setValue(self.inference_interval)
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_interval.setMinimumWidth(120)
        self.spin_interval.setFixedHeight(36)

        interval_layout = QHBoxLayout()
        interval_layout.setSpacing(8)
        interval_layout.addWidget(self.spin_interval)
        lbl_frames = QLabel("frames")
        lbl_frames.setStyleSheet("color: #8b949e;")
        interval_layout.addWidget(lbl_frames)
        interval_layout.addStretch()
        form.addRow("Inference every:", interval_layout)

        # ── Inference resolution ───────────────────────────────────────────
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.setFixedHeight(36)
        self.cmb_resolution.setMinimumWidth(200)
        for label, _ in self._RESOLUTIONS:
            self.cmb_resolution.addItem(label)
        # Select the entry matching the current resolution
        for i, (_, px) in enumerate(self._RESOLUTIONS):
            if px == self.inference_resolution:
                self.cmb_resolution.setCurrentIndex(i)
                break

        res_layout = QHBoxLayout()
        res_layout.setSpacing(8)
        res_layout.addWidget(self.cmb_resolution)
        res_layout.addStretch()
        form.addRow("Inference resolution:", res_layout)

        lay.addLayout(form)

        hints = QLabel(
            "Safety limit — alert fires when people count exceeds this number.\n"
            "Confidence — how certain the model must be before counting a person "
            "(0.40 is a good default; lower catches more, higher reduces false positives).\n"
            "Inference every N frames — 1 = every frame (most accurate, slowest). "
            "Higher values skip frames to boost CPU speed; bounding boxes stay visible.\n"
            "Inference resolution — lower px = much faster on CPU; "
            "video display quality is unaffected.\n\n"
            "Click inside a number field to type or use your mouse scroll wheel."
        )
        hints.setStyleSheet("font-size: 11px; color: #484f58; line-height: 1.6;")
        hints.setWordWrap(True)
        lay.addWidget(hints)

        lay.addStretch()
        return tab

    # ── Users tab ─────────────────────────────────────────────────────────

    def _make_users_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        # ── Search + action buttons bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search users...")
        self.search_box.setFixedHeight(30)
        self.search_box.textChanged.connect(self._filter_users)
        top_bar.addWidget(self.search_box, 1)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedHeight(30)
        btn_refresh.clicked.connect(self._refresh_users)
        top_bar.addWidget(btn_refresh)

        lay.addLayout(top_bar)

        # ── Accounts table
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(4)
        self.user_table.setHorizontalHeaderLabels(["Username", "Role", "Created", "Status"])
        hh = self.user_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.user_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.user_table.verticalHeader().setVisible(False)
        self.user_table.setFixedHeight(160)
        self.user_table.itemSelectionChanged.connect(self._on_row_changed)
        lay.addWidget(self.user_table)

        # ── Action buttons for selected account
        act_bar = QHBoxLayout()
        act_bar.setSpacing(6)

        self.btn_unlock = QPushButton("Unlock")
        self.btn_unlock.setToolTip("Reset lockout and failure counter")
        self.btn_unlock.setFixedHeight(28)
        self.btn_unlock.clicked.connect(self._unlock_selected)

        self.btn_lock = QPushButton("Lock")
        self.btn_lock.setToolTip("Manually lock the selected account")
        self.btn_lock.setFixedHeight(28)
        self.btn_lock.clicked.connect(self._lock_selected)

        self.btn_toggle_role = QPushButton("Make Admin")
        self.btn_toggle_role.setToolTip("Toggle role between user and admin")
        self.btn_toggle_role.setFixedHeight(28)
        self.btn_toggle_role.clicked.connect(self._toggle_role)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setObjectName("dangerBtn")
        self.btn_delete.setToolTip("Permanently delete this account")
        self.btn_delete.setFixedHeight(28)
        self.btn_delete.clicked.connect(self._delete_selected)

        for btn in (self.btn_unlock, self.btn_lock, self.btn_toggle_role, self.btn_delete):
            btn.setEnabled(False)
            act_bar.addWidget(btn)

        act_bar.addStretch()
        lay.addLayout(act_bar)

        # ── Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #21262d;")
        lay.addWidget(sep)

        # ── Change password for selected account
        pwd_lbl = QLabel("Change password for selected account")
        pwd_lbl.setStyleSheet("font-size: 11px; color: #484f58;")
        lay.addWidget(pwd_lbl)

        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(6)
        self.pwd_field = QLineEdit()
        self.pwd_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_field.setPlaceholderText("New password (min. 6 chars)")
        self.pwd_field.setFixedHeight(30)
        self.pwd_field.setEnabled(False)
        pwd_row.addWidget(self.pwd_field, 1)

        self.btn_set_pwd = QPushButton("Set Password")
        self.btn_set_pwd.setFixedHeight(30)
        self.btn_set_pwd.setEnabled(False)
        self.btn_set_pwd.clicked.connect(self._set_password)
        pwd_row.addWidget(self.btn_set_pwd)
        lay.addLayout(pwd_row)

        # ── Divider
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #21262d;")
        lay.addWidget(sep2)

        # ── Add account form
        add_lbl = QLabel("Create new account")
        add_lbl.setStyleSheet("font-size: 11px; color: #484f58;")
        lay.addWidget(add_lbl)

        add_form = QFormLayout()
        add_form.setSpacing(8)
        add_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        add_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.new_username = QLineEdit()
        self.new_username.setMaxLength(64)
        self.new_username.setPlaceholderText("letters, numbers, underscores")
        self.new_username.setFixedHeight(30)
        add_form.addRow("Username:", self.new_username)

        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setMaxLength(128)
        self.new_password.setPlaceholderText("min. 6 characters")
        self.new_password.setFixedHeight(30)
        add_form.addRow("Password:", self.new_password)

        role_row = QHBoxLayout()
        self.new_role = QComboBox()
        self.new_role.addItems(["user", "admin"])
        self.new_role.setFixedWidth(120)
        self.new_role.setFixedHeight(30)
        role_row.addWidget(self.new_role)
        role_row.addStretch()
        add_form.addRow("Role:", role_row)

        lay.addLayout(add_form)

        btn_add_row = QHBoxLayout()
        btn_add_row.setSpacing(8)
        self.lbl_add_status = QLabel("")
        self.lbl_add_status.setStyleSheet("font-size: 11px;")
        self.lbl_add_status.setWordWrap(True)
        btn_add_row.addWidget(self.lbl_add_status, 1)

        btn_add = QPushButton("Create Account")
        btn_add.setFixedHeight(32)
        btn_add.clicked.connect(self._add_user)
        btn_add_row.addWidget(btn_add)
        lay.addLayout(btn_add_row)

        self._refresh_users()
        return tab

    # ── Button row ────────────────────────────────────────────────────────

    def _make_button_row(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("border-top: 1px solid #21262d;")
        bar.setFixedHeight(54)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 10, 16, 10)

        btn_cancel = QPushButton("Cancel")
        btn_apply  = QPushButton("Apply")
        btn_apply.setObjectName("primaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_apply.clicked.connect(self._apply)

        row.addStretch()
        row.addWidget(btn_cancel)
        row.addSpacing(6)
        row.addWidget(btn_apply)
        return bar

    # ── Slots ─────────────────────────────────────────────────────────────

    def _apply(self):
        self.safety_limit         = self.spin_limit.value()
        self.confidence           = self.spin_conf.value()
        self.inference_interval   = self.spin_interval.value()
        idx = self.cmb_resolution.currentIndex()
        self.inference_resolution = self._RESOLUTIONS[idx][1]
        self.accept()

    def _refresh_users(self):
        self._all_users = get_users()
        self._populate_table(self._all_users)

    def _filter_users(self, text: str):
        text = text.strip().lower()
        if not text:
            self._populate_table(self._all_users)
        else:
            filtered = [u for u in self._all_users
                        if text in u["username"].lower() or text in u["role"].lower()]
            self._populate_table(filtered)

    def _populate_table(self, users: list):
        now = datetime.now().isoformat()
        self.user_table.setRowCount(0)
        for user in users:
            r = self.user_table.rowCount()
            self.user_table.insertRow(r)

            self.user_table.setItem(r, 0, QTableWidgetItem(user["username"]))

            role_item = QTableWidgetItem(user["role"])
            role_item.setForeground(
                QColor("#f85149" if user["role"] == "admin" else "#3fb950")
            )
            self.user_table.setItem(r, 1, role_item)

            ts = str(user.get("created_at", ""))[:10]
            self.user_table.setItem(r, 2, QTableWidgetItem(ts))

            locked_until = user.get("locked_until")
            if locked_until and now < locked_until:
                status_item = QTableWidgetItem("LOCKED")
                status_item.setForeground(QColor("#f85149"))
            else:
                attempts = user.get("failed_attempts", 0) or 0
                if attempts > 0:
                    status_item = QTableWidgetItem(f"{attempts} fail(s)")
                    status_item.setForeground(QColor("#ff9800"))
                else:
                    status_item = QTableWidgetItem("OK")
                    status_item.setForeground(QColor("#3fb950"))
            self.user_table.setItem(r, 3, status_item)

        self._update_action_buttons()

    def _on_row_changed(self):
        self._update_action_buttons()

    def _update_action_buttons(self):
        row = self.user_table.currentRow()
        has_sel = row >= 0
        for btn in (self.btn_unlock, self.btn_lock, self.btn_toggle_role,
                    self.btn_delete, self.btn_set_pwd, self.pwd_field):
            btn.setEnabled(has_sel)

        if has_sel:
            role_item = self.user_table.item(row, 1)
            if role_item:
                role = role_item.text()
                self.btn_toggle_role.setText(
                    "Make User" if role == "admin" else "Make Admin"
                )

    def _selected_username(self) -> str | None:
        row = self.user_table.currentRow()
        if row < 0:
            return None
        item = self.user_table.item(row, 0)
        return item.text() if item else None

    def _unlock_selected(self):
        username = self._selected_username()
        if not username:
            return
        if reset_lockout(username):
            self._refresh_users()
            self._show_info("Unlocked", f"'{username}' has been unlocked.")
        else:
            self._show_warn("Error", "Could not unlock account.")

    def _lock_selected(self):
        username = self._selected_username()
        if not username:
            return
        reply = QMessageBox.question(
            self, "Lock account",
            f"Manually lock '{username}' for 30 minutes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if lock_user(username):
                self._refresh_users()
                self._show_info("Locked", f"'{username}' is now locked.")
            else:
                self._show_warn("Error", "Could not lock account.")

    def _toggle_role(self):
        username = self._selected_username()
        if not username:
            return
        row = self.user_table.currentRow()
        current_role = self.user_table.item(row, 1).text() if self.user_table.item(row, 1) else "user"
        new_role = "user" if current_role == "admin" else "admin"
        if update_role(username, new_role):
            self._refresh_users()
        else:
            self._show_warn("Error", "Could not update role.")

    def _delete_selected(self):
        username = self._selected_username()
        if not username:
            return
        reply = QMessageBox.warning(
            self, "Delete account",
            f"Permanently delete '{username}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if delete_user(username):
                self._refresh_users()
                self.pwd_field.clear()
            else:
                self._show_warn("Error", "Could not delete account.")

    def _set_password(self):
        username = self._selected_username()
        if not username:
            return
        pwd = self.pwd_field.text()
        if len(pwd) < 6:
            self._show_warn("Weak password", "Password must be at least 6 characters.")
            return
        if change_password(username, pwd):
            self.pwd_field.clear()
            self._show_info("Done", f"Password for '{username}' has been updated.")
        else:
            self._show_warn("Error", "Could not change password.")

    def _add_user(self):
        try:
            self.lbl_add_status.setText("")
            username = self.new_username.text().strip()
            password = self.new_password.text()
            role     = self.new_role.currentText()

            if not _USERNAME_RE.match(username):
                self._set_add_status(
                    "Username must be 3-64 chars: letters, numbers, underscores.",
                    error=True
                )
                return
            if len(password) < 6:
                self._set_add_status("Password must be at least 6 characters.", error=True)
                return

            err = create_user(username, password, role)
            if err is None:
                self.new_username.clear()
                self.new_password.clear()
                self._refresh_users()
                self._set_add_status(f"Account '{username}' created.", error=False)
            elif err == "username_taken":
                self._set_add_status(
                    f"'{username}' is already registered.", error=True
                )
            else:
                self._set_add_status(f"Error: {err}", error=True)
        except Exception as ex:
            self._set_add_status(f"Unexpected error: {ex}", error=True)

    def _set_add_status(self, msg: str, error: bool = False):
        color = "#f85149" if error else "#3fb950"
        self.lbl_add_status.setStyleSheet(f"font-size: 11px; color: {color};")
        self.lbl_add_status.setText(msg)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _show_info(self, title: str, msg: str):
        QMessageBox.information(self, title, msg)

    def _show_warn(self, title: str, msg: str):
        QMessageBox.warning(self, title, msg)
