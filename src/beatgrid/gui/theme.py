from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# A dark, slightly blue window chrome: text, toolbar actions, buttons and the
# scrollbar stand out against it, and it sits quietly around the black plots.
WINDOW = QColor(38, 46, 62)
BASE = QColor(26, 32, 44)  # text fields, spin boxes, lists
ALTERNATE_BASE = QColor(33, 40, 54)
BUTTON = QColor(58, 70, 92)
TEXT = QColor(230, 236, 245)
DISABLED_TEXT = QColor(120, 130, 148)
HIGHLIGHT = QColor(74, 144, 217)
HIGHLIGHTED_TEXT = QColor(255, 255, 255)
LINK = QColor(110, 180, 255)
TITLE_BAR = QColor(22, 27, 38)  # BeatGrid's own title bar, darker than the window
OUTLINE = HIGHLIGHT  # the border around the whole window


def apply_theme(app: QApplication) -> None:
    """Fusion style with the dark blue-ish palette above (Fusion follows the
    palette consistently on every platform, unlike the native styles)."""
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: WINDOW,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: BASE,
        QPalette.ColorRole.AlternateBase: ALTERNATE_BASE,
        QPalette.ColorRole.ToolTipBase: BUTTON,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.PlaceholderText: DISABLED_TEXT,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: BUTTON,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.BrightText: QColor(255, 120, 120),
        QPalette.ColorRole.Highlight: HIGHLIGHT,
        QPalette.ColorRole.HighlightedText: HIGHLIGHTED_TEXT,
        QPalette.ColorRole.Link: LINK,
        QPalette.ColorRole.Light: BUTTON.lighter(130),
        QPalette.ColorRole.Midlight: BUTTON.lighter(115),
        QPalette.ColorRole.Mid: BUTTON.darker(130),
        QPalette.ColorRole.Dark: WINDOW.darker(150),
        QPalette.ColorRole.Shadow: QColor(0, 0, 0),
    }
    for role, color in roles.items():
        palette.setColor(role, color)
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, DISABLED_TEXT)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, WINDOW)
    app.setPalette(palette)

    # Fusion fills checkbox/radio indicators with Base, which is nearly the
    # window colour here -- the per-row M/S boxes all but disappeared.
    indicators = QPalette(palette)
    indicators.setColor(QPalette.ColorRole.Base, BUTTON.lighter(125))
    app.setPalette(indicators, "QCheckBox")
