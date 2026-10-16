from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from beatgrid.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    # Under WSLg with several monitors, Qt's "primary" screen isn't
    # necessarily the main/largest one -- open maximized on the largest.
    screen = max(app.screens(), key=lambda s: s.size().width() * s.size().height())
    window.setGeometry(screen.availableGeometry())
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
