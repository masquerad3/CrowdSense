import sys

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtGui import QIcon


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CrowdSense")
        self.resize(800, 600)
        self.setWindowIcon(QIcon("CrowdSense.png"))




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())