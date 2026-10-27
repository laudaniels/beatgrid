import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QCheckBox

from beatgrid.gui import theme

pytestmark = pytest.mark.gui


def test_theme_sets_a_dark_palette_with_visible_checkboxes(qtbot):
    app = QApplication.instance()
    original_style, original_palette = app.style().name(), app.palette()
    try:
        theme.apply_theme(app)

        palette = app.palette()
        assert app.style().name().lower() == "fusion"
        assert palette.color(QPalette.ColorRole.Window) == theme.WINDOW
        assert palette.color(QPalette.ColorRole.WindowText) == theme.TEXT
        # text must be far lighter than the background it sits on
        assert theme.TEXT.lightness() - theme.WINDOW.lightness() > 150

        box = QCheckBox("M")
        qtbot.addWidget(box)
        box.ensurePolished()  # per-class palettes are applied when polished
        indicator = box.palette().color(QPalette.ColorRole.Base)
        assert indicator.lightness() > theme.WINDOW.lightness() + 30
    finally:
        app.setStyle(original_style)
        app.setPalette(original_palette)
