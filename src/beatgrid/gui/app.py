from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from beatgrid.gui.main_window import MainWindow
from beatgrid.gui.theme import apply_theme
from beatgrid.gui.tooltip_placement import keep_tooltips_inside_windows


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    keep_tooltips_inside_windows(app)
    window = MainWindow()
    # Under WSLg with several monitors, Qt's "primary" screen isn't
    # necessarily the main/largest one -- open maximized on the largest.
    screen = max(app.screens(), key=lambda s: s.size().width() * s.size().height())
    window.setGeometry(screen.availableGeometry())
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
