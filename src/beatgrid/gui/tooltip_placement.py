from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from beatgrid.gui import theme

# Gap between the mouse pointer and the tooltip.
_GAP = QPoint(4, 20)
# Distance kept from the window's edges.
_EDGE_MARGIN = 8
# Tooltip width: the texts' own 440 px (tooltips.tip) plus padding/border.
_WIDTH_PX = 440 + 2 * 6
# Hide a tooltip after this long even if the pointer doesn't move.
_TIMEOUT_MS = 15000

# Anything that should make a visible tooltip go away.
_HIDE_ON = {
    QEvent.Type.Leave,
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseButtonDblClick,
    QEvent.Type.Wheel,
    QEvent.Type.KeyPress,
    QEvent.Type.WindowDeactivate,
    QEvent.Type.Hide,
}


def place_inside(cursor: QPoint, size: QSize, area: QRect) -> QPoint:
    """Top-left corner for a tooltip of `size` near `cursor` that stays
    inside `area`: below-right of the pointer by default, shifted left at the
    right edge and flipped above the pointer at the bottom edge."""
    area = area.adjusted(_EDGE_MARGIN, _EDGE_MARGIN, -_EDGE_MARGIN, -_EDGE_MARGIN)
    x = cursor.x() + _GAP.x()
    y = cursor.y() + _GAP.y()
    if x + size.width() > area.right():
        x = area.right() - size.width()
    if y + size.height() > area.bottom():
        y = cursor.y() - _GAP.y() // 2 - size.height()  # above the pointer
    x = max(area.left(), x)
    y = max(area.top(), y)
    return QPoint(x, y)


class TooltipsInsideWindow(QObject):
    """App-wide event filter that draws every widget tooltip as a child of
    the window it belongs to, instead of as Qt's own tooltip window.

    A separate tooltip window is placed by the window system, and under
    WSLg/Wayland an app can't position it reliably -- tooltips of controls
    along the right and bottom edges ran out of the app (moving Qt's tooltip
    window afterwards stopped working once the main window became frameless).
    A child widget can't leave its window at all."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._label: QLabel | None = None
        self._source: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    @property
    def label(self) -> QLabel | None:
        """The tooltip currently shown, if any (for tests)."""
        return self._label if self._label is not None and self._label.isVisible() else None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        kind = event.type()
        if kind == QEvent.Type.ToolTip and isinstance(watched, QWidget):
            text = watched.toolTip()
            if not text:
                return False  # let Qt handle it (e.g. items inside a plot)
            assert isinstance(event, QHelpEvent)
            self.show(watched, event.pos(), text)
            return True
        if kind in _HIDE_ON and self.label is not None:
            if kind != QEvent.Type.Leave or watched is self._source:
                self.hide()
        return False

    def show(self, widget: QWidget, pos: QPoint, text: str) -> None:
        window = widget.window()
        if self._label is None or self._label.parent() is not window:
            self.hide()
            self._label = _make_label(window)
        self._source = widget
        self._label.setText(text)
        # fixed width (never wider than the window), height to fit the text
        width = min(_WIDTH_PX, window.width() - 2 * _EDGE_MARGIN)
        self._label.setFixedWidth(width)
        self._label.setFixedHeight(self._label.heightForWidth(width))
        cursor = widget.mapTo(window, pos)
        self._label.move(place_inside(cursor, self._label.size(), window.rect()))
        self._label.show()
        self._label.raise_()
        self._timer.start(_TIMEOUT_MS)

    def hide(self) -> None:
        if self._label is not None:
            self._label.hide()
        self._source = None
        self._timer.stop()


def _make_label(window: QWidget) -> QLabel:
    label = QLabel(window)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setWordWrap(True)
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    label.setStyleSheet(
        f"QLabel {{ background: {theme.BUTTON.name()}; color: {theme.TEXT.name()};"
        f" border: 1px solid {theme.OUTLINE.name()}; border-radius: 3px; padding: 5px; }}"
    )
    label.hide()
    return label


def keep_tooltips_inside_windows(app: QApplication) -> TooltipsInsideWindow:
    tooltip_filter = TooltipsInsideWindow(app)
    app.installEventFilter(tooltip_filter)
    return tooltip_filter
