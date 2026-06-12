"""
CrowdSense - Settings Dialog (src/ui/settings_dialog.py)

Tuning for detection parameters (safety limit, confidence, resolution)
and database retention.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QPushButton, QWidget, QComboBox,
    QAbstractSpinBox, QSlider, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

class DoubleClickLabel(QLabel):
    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()

from auth.db import get_setting, save_setting


class SettingsDialog(QDialog):
    """
    Settings dialog containing both detection options and database retention controls.
    """

    # Resolution options: display label -> pixels
    _RESOLUTIONS = [
        ("320 px (Fastest)",       320),
        ("416 px (Balanced)",      416),
        ("640 px (Most Accurate)", 640),
    ]

    # Retention options: display label -> days
    _RETENTION_OPTIONS = [
        ("Forever",  0),
        ("7 Days",   7),
        ("30 Days",  30),
        ("90 Days",  90),
    ]

    def __init__(self, safety_limit: int, confidence: float,
                 inference_interval: int = 1,
                 inference_resolution: int = 640,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings - CrowdSense")
        self.resize(520, 460)
        self.setModal(True)

        self.safety_limit         = safety_limit
        self.confidence           = confidence
        self.inference_interval   = inference_interval
        self.inference_resolution = inference_resolution

        # Load database retention setting
        self.retention_days = int(get_setting("retention_days", 0))

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._make_settings_panel(), 1)
        root.addWidget(self._make_button_row())

    def _make_settings_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(32, 24, 32, 16)
        lay.setSpacing(20)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # ── SECTION 1: Detection Settings ─────────────────────────────────────
        sec_det_lbl = QLabel("Detection Parameters")
        sec_det_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #58a6ff; margin-top: 5px;")
        form.addRow(sec_det_lbl)

        # Safety limit slider
        self.slider_limit = QSlider(Qt.Orientation.Horizontal)
        self.slider_limit.setRange(1, 300)
        self.slider_limit.setValue(self.safety_limit)
        self.slider_limit.setMinimumWidth(200)

        self.lbl_limit_val = DoubleClickLabel(f"{self.safety_limit} people")
        self.lbl_limit_val.setStyleSheet("color: #e6edf3; font-weight: bold; min-width: 80px;")
        self.lbl_limit_val.setToolTip("Double-click to enter a custom limit")
        self.lbl_limit_val.doubleClicked.connect(self._on_limit_label_double_clicked)
        self.slider_limit.valueChanged.connect(self._on_limit_slider_changed)

        limit_layout = QHBoxLayout()
        limit_layout.setSpacing(8)
        limit_layout.addWidget(self.slider_limit)
        limit_layout.addWidget(self.lbl_limit_val)
        limit_layout.addStretch()
        form.addRow("Safety limit:", limit_layout)

        # Confidence slider
        self.slider_conf = QSlider(Qt.Orientation.Horizontal)
        self.slider_conf.setRange(10, 90)
        self.slider_conf.setValue(int(self.confidence * 100))
        self.slider_conf.setMinimumWidth(200)

        self.lbl_conf_val = DoubleClickLabel(f"{int(self.confidence * 100)}%")
        self.lbl_conf_val.setStyleSheet("color: #e6edf3; font-weight: bold; min-width: 40px;")
        self.lbl_conf_val.setToolTip("Double-click to enter a custom confidence")
        self.lbl_conf_val.doubleClicked.connect(self._on_conf_label_double_clicked)
        self.slider_conf.valueChanged.connect(self._on_conf_slider_changed)

        conf_layout = QHBoxLayout()
        conf_layout.setSpacing(8)
        conf_layout.addWidget(self.slider_conf)
        conf_layout.addWidget(self.lbl_conf_val)
        conf_layout.addStretch()
        form.addRow("Confidence threshold:", conf_layout)

        # Inference interval
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 30)
        self.spin_interval.setValue(self.inference_interval)
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_interval.setMinimumWidth(120)
        self.spin_interval.setFixedHeight(32)

        interval_layout = QHBoxLayout()
        interval_layout.setSpacing(8)
        interval_layout.addWidget(self.spin_interval)
        lbl_frames = QLabel("frames")
        lbl_frames.setStyleSheet("color: #8b949e;")
        interval_layout.addWidget(lbl_frames)
        interval_layout.addStretch()
        form.addRow("Inference every:", interval_layout)

        # Inference resolution
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.setFixedHeight(32)
        self.cmb_resolution.setMinimumWidth(200)
        for label, _ in self._RESOLUTIONS:
            self.cmb_resolution.addItem(label)
        # Select matching resolution index
        for i, (_, px) in enumerate(self._RESOLUTIONS):
            if px == self.inference_resolution:
                self.cmb_resolution.setCurrentIndex(i)
                break

        res_layout = QHBoxLayout()
        res_layout.setSpacing(8)
        res_layout.addWidget(self.cmb_resolution)
        res_layout.addStretch()
        form.addRow("Inference resolution:", res_layout)

        # ── SECTION 2: Data Management Settings ───────────────────────────────
        sec_db_lbl = QLabel("Data Retention")
        sec_db_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #58a6ff; margin-top: 15px;")
        form.addRow(sec_db_lbl)

        # Data retention combo box
        self.cmb_retention = QComboBox()
        self.cmb_retention.setFixedHeight(32)
        self.cmb_retention.setMinimumWidth(200)
        for label, _ in self._RETENTION_OPTIONS:
            self.cmb_retention.addItem(label)
        # Select matching retention index
        for i, (_, days) in enumerate(self._RETENTION_OPTIONS):
            if days == self.retention_days:
                self.cmb_retention.setCurrentIndex(i)
                break

        retention_layout = QHBoxLayout()
        retention_layout.setSpacing(8)
        retention_layout.addWidget(self.cmb_retention)
        retention_layout.addStretch()
        form.addRow("Data retention limit:", retention_layout)

        # Database backup button (Export Backup & Import Backup side-by-side)
        self.btn_backup = QPushButton("Export Backup")
        self.btn_backup.setFixedHeight(32)
        self.btn_backup.setFixedWidth(130)
        self.btn_backup.clicked.connect(self._on_backup_db)

        self.btn_import = QPushButton("Import Backup")
        self.btn_import.setFixedHeight(32)
        self.btn_import.setFixedWidth(130)
        self.btn_import.clicked.connect(self._on_import_db)

        backup_layout = QHBoxLayout()
        backup_layout.setSpacing(8)
        backup_layout.addWidget(self.btn_backup)
        backup_layout.addWidget(self.btn_import)
        backup_layout.addStretch()
        form.addRow("Database backup:", backup_layout)

        lay.addLayout(form)

        # Quick guide hints
        hints = QLabel(
            "Safety limit - alert fires when count exceeds this limit.\n"
            "Inference resolution - lower resolution is much faster on CPU.\n"
            "Data retention - sessions older than the selected period are automatically "
            "cleared on startup to maintain database performance."
        )
        hints.setStyleSheet("font-size: 11px; color: #484f58; line-height: 1.5; margin-top: 10px;")
        hints.setWordWrap(True)
        lay.addWidget(hints)

        lay.addStretch()
        return panel

    def _make_button_row(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("border-top: 1px solid #21262d;")
        bar.setFixedHeight(64)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 12, 16, 12)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedWidth(100)
        btn_apply  = QPushButton("Apply")
        btn_apply.setFixedWidth(100)
        btn_apply.setObjectName("primaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_apply.clicked.connect(self._apply)

        row.addStretch()
        row.addWidget(btn_cancel)
        row.addSpacing(6)
        row.addWidget(btn_apply)
        return bar

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_limit_slider_changed(self, val: int):
        self.lbl_limit_val.setText(f"{val} people")

    def _on_conf_slider_changed(self, val: int):
        self.lbl_conf_val.setText(f"{val}%")

    def _on_limit_label_double_clicked(self):
        val, ok = QInputDialog.getInt(
            self, "Safety Limit", "Enter custom safety limit (1 - 1000):",
            value=self.slider_limit.value(), min=1, max=1000
        )
        if ok:
            if val > self.slider_limit.maximum():
                self.slider_limit.setMaximum(val)
            self.slider_limit.setValue(val)
            self.lbl_limit_val.setText(f"{val} people")

    def _on_conf_label_double_clicked(self):
        val, ok = QInputDialog.getDouble(
            self, "Confidence Threshold", "Enter confidence percentage (10 - 90):",
            value=self.slider_conf.value(), min=10, max=90, decimals=0
        )
        if ok:
            ival = int(val)
            self.slider_conf.setValue(ival)
            self.lbl_conf_val.setText(f"{ival}%")

    def _on_backup_db(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        import shutil
        from auth.db import DB_PATH

        data_dir = Path(__file__).resolve().parents[2] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        default_path = str(data_dir / "backup.db")

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Database Backup", default_path, "SQLite Database (*.db)"
        )
        if path:
            try:
                shutil.copy2(str(DB_PATH), path)
                QMessageBox.information(self, "Backup Success", f"Database successfully backed up to:\n\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Backup Error", f"Could not create database backup:\n\n{exc}")

    def _on_import_db(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        import shutil
        import sqlite3
        from auth.db import DB_PATH, init_db, get_setting

        reply = QMessageBox.warning(
            self, "Import Database",
            "Are you sure you want to import a database?\n\n"
            "This will overwrite all current settings, sessions, and logs. "
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        data_dir = Path(__file__).resolve().parents[2] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getOpenFileName(
            self, "Import Database", str(data_dir), "SQLite Database (*.db)"
        )
        if not path:
            return

        # Verify database validity
        try:
            conn = sqlite3.connect(path)
            conn.execute("SELECT name FROM sqlite_master").close()
            conn.close()
        except Exception:
            QMessageBox.critical(self, "Import Error", "The selected file is not a valid SQLite database.")
            return

        try:
            shutil.copy2(path, str(DB_PATH))
            init_db()

            # Load settings from the imported database and update dialog widgets
            self.safety_limit         = int(get_setting("safety_limit", 30))
            self.confidence           = float(get_setting("confidence", 0.40))
            self.inference_interval   = int(get_setting("inference_interval", 1))
            self.inference_resolution = int(get_setting("inference_resolution", 640))
            self.retention_days       = int(get_setting("retention_days", 0))

            # Update widgets
            if self.safety_limit > self.slider_limit.maximum():
                self.slider_limit.setMaximum(self.safety_limit)
            self.slider_limit.setValue(self.safety_limit)
            self.lbl_limit_val.setText(f"{self.safety_limit} people")

            self.slider_conf.setValue(int(self.confidence * 100))
            self.lbl_conf_val.setText(f"{int(self.confidence * 100)}%")

            self.spin_interval.setValue(self.inference_interval)

            for i, (_, px) in enumerate(self._RESOLUTIONS):
                if px == self.inference_resolution:
                    self.cmb_resolution.setCurrentIndex(i)
                    break

            for i, (_, days) in enumerate(self._RETENTION_OPTIONS):
                if days == self.retention_days:
                    self.cmb_retention.setCurrentIndex(i)
                    break

            QMessageBox.information(
                self, "Import Success",
                "Database successfully imported!\n\n"
                "Settings have been loaded. Click 'Apply' to save and update the main dashboard."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", f"Could not import database:\n\n{exc}")

    def _apply(self):
        self.safety_limit         = self.slider_limit.value()
        self.confidence           = self.slider_conf.value() / 100.0
        self.inference_interval   = self.spin_interval.value()
        idx = self.cmb_resolution.currentIndex()
        self.inference_resolution = self._RESOLUTIONS[idx][1]

        # Save retention days
        self.retention_days = self._RETENTION_OPTIONS[self.cmb_retention.currentIndex()][1]
        save_setting("retention_days", self.retention_days)

        self.accept()
