"""
CrowdSense — Dark Mode Stylesheet  (src/ui/styles.py)

Professional surveillance-dashboard aesthetic:
  • Deep navy/charcoal backgrounds (#0d1117, #161b22)
  • Blue accent (#58a6ff)
  • Colour-coded status: green OK, orange medium, red high/alert
  • Clean sans-serif typography (Segoe UI)
"""

MAIN_STYLESHEET = """
/* ================================================================
   GLOBAL — suppress focus rectangles everywhere
   ================================================================ */
* { outline: 0; }

/* ================================================================
   BASE
   ================================================================ */
QMainWindow, QDialog, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* ================================================================
   TAB WIDGET
   ================================================================ */
QTabWidget::pane {
    border: 1px solid #21262d;
    background: #0d1117;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background: #161b22;
    color: #8b949e;
    padding: 9px 22px;
    border: 1px solid transparent;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    min-width: 90px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #0d1117;
    color: #58a6ff;
    border-color: #21262d;
    border-bottom-color: #0d1117;
}
QTabBar::tab:hover:!selected {
    background: #1c2128;
    color: #e6edf3;
}

/* ================================================================
   BUTTONS
   ================================================================ */
QPushButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #58a6ff;
    color: #58a6ff;
}
QPushButton:pressed {
    background-color: #1c2128;
    border-color: #388bfd;
}
QPushButton:focus {
    outline: none;
    border-color: #58a6ff;
}
QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

/* Primary (blue) button */
QPushButton#primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #1f6feb, stop:1 #2d8cf0);
    border-color: #388bfd;
    color: white;
}
QPushButton#primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #388bfd, stop:1 #58a6ff);
}
QPushButton#primaryBtn:disabled {
    background: #21262d;
    color: #484f58;
    border-color: #21262d;
}

/* Danger (red) button */
QPushButton#dangerBtn {
    background-color: #2d1515;
    border-color: #b91c1c;
    color: #f85149;
}
QPushButton#dangerBtn:hover {
    background-color: #3d1f1f;
    border-color: #ef4444;
    color: #ff6b6b;
}

/* ================================================================
   GROUP BOX  (sidebar metric cards)
   ================================================================ */
QGroupBox {
    border: 1px solid #21262d;
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 8px 8px 8px;
    background: #161b22;
    color: #8b949e;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #8b949e;
    font-size: 11px;
}

/* ================================================================
   LABELS
   ================================================================ */
QLabel { color: #e6edf3; }

/* ================================================================
   VIDEO PREVIEW
   ================================================================ */
QLabel#videoPreview {
    background: #010409;
    border: 1px solid #21262d;
    border-radius: 10px;
    color: #484f58;
    font-size: 15px;
    qproperty-alignment: 'AlignCenter';
}

/* ================================================================
   ALERT BANNER
   ================================================================ */
QLabel#alertBanner {
    background-color: #3d1515;
    color: #f85149;
    font-weight: 700;
    font-size: 13px;
    border: 1px solid #b91c1c;
    border-radius: 6px;
    padding: 7px 14px;
}

/* ================================================================
   COMBO BOX
   ================================================================ */
QComboBox {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 80px;
}
QComboBox:hover { border-color: #58a6ff; }
QComboBox::drop-down { border: none; padding-right: 6px; }
QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
}

/* ================================================================
   STATUS BAR
   ================================================================ */
QStatusBar {
    background: #161b22;
    color: #8b949e;
    border-top: 1px solid #21262d;
    font-size: 11px;
    padding: 2px 8px;
}

/* ================================================================
   TABLE WIDGET
   ================================================================ */
QTableWidget {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #21262d;
    border-radius: 6px;
    gridline-color: #21262d;
    outline: none;
}
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected {
    background-color: #1f3a5f;
    color: #e6edf3;
}
QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    border: none;
    border-bottom: 1px solid #21262d;
    border-right: 1px solid #21262d;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* ================================================================
   SCROLLBARS
   ================================================================ */
QScrollBar:vertical {
    background: #161b22;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #58a6ff; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: #161b22;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #30363d;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: #58a6ff; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ================================================================
   SPLITTER
   ================================================================ */
QSplitter::handle { background: #21262d; }
QSplitter::handle:horizontal { width: 1px; }

/* ================================================================
   LINE EDIT (general)
   ================================================================ */
QLineEdit {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #1f6feb;
}
QLineEdit:focus { border-color: #58a6ff; }

/* ================================================================
   SPIN BOX
   ================================================================ */
QSpinBox, QDoubleSpinBox {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #1f6feb;
}
QSpinBox:focus, QDoubleSpinBox:focus { border-color: #58a6ff; }

/* ================================================================
   FRAME SEPARATORS
   ================================================================ */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #21262d; }

/* ================================================================
   SCROLL AREA
   ================================================================ */
QScrollArea { border: none; background: transparent; }

/* ================================================================
   LOGIN DIALOG  (shared stylesheet, scoped by objectName)
   ================================================================ */
QLabel#loginTitle {
    font-size: 24px;
    font-weight: 600;
    color: #e6edf3;
    letter-spacing: -0.3px;
}
QLabel#loginSubtitle {
    font-size: 13px;
    color: #8b949e;
}
QLabel#loginFieldLabel {
    font-size: 12px;
    font-weight: 600;
    color: #8b949e;
}
QLabel#loginError {
    color: #f85149;
    font-size: 12px;
}
QLabel#loginFooter {
    color: #484f58;
    font-size: 10px;
}
QLineEdit#loginField {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 13px;
}
QLineEdit#loginField:focus { border-color: #58a6ff; }
QPushButton#loginBtn {
    background-color: #1f6feb;
    color: white;
    border: 1px solid #388bfd;
    border-radius: 6px;
    padding: 11px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#loginBtn:hover {
    background-color: #388bfd;
    border-color: #58a6ff;
}
QPushButton#loginBtn:disabled {
    background-color: #21262d;
    color: #484f58;
    border-color: #21262d;
}

/* ================================================================
   FORM LAYOUT labels inside dialogs
   ================================================================ */
QFormLayout QLabel { color: #8b949e; font-size: 12px; }

/* ================================================================
   STATUS PANEL (right sidebar on Dashboard)
   ================================================================ */
QFrame#statusPanel {
    background: #0d1117;
    border-left: 1px solid #21262d;
}

/* ================================================================
   TOOLBAR (bottom control bar on Dashboard)
   ================================================================ */
QWidget#toolbar {
    background: #0d1117;
    border-top: 1px solid #21262d;
}
QWidget#toolbar QPushButton {
    min-height: 22px;
    padding: 3px 10px;
    font-size: 12px;
}
"""
