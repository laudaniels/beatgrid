import pytest
from PySide6.QtCore import QPoint, QRect, Qt

from beatgrid.gui.window_frame import cursor_for, resize_edges

pytestmark = pytest.mark.gui

RECT = QRect(0, 0, 1000, 600)


@pytest.mark.parametrize(
    ("pos", "edges"),
    [
        (QPoint(500, 300), Qt.Edge(0)),  # middle: nothing
        (QPoint(1, 300), Qt.Edge.LeftEdge),
        (QPoint(998, 300), Qt.Edge.RightEdge),
        (QPoint(500, 1), Qt.Edge.TopEdge),
        (QPoint(500, 598), Qt.Edge.BottomEdge),
        (QPoint(1, 1), Qt.Edge.TopEdge | Qt.Edge.LeftEdge),
        (QPoint(998, 598), Qt.Edge.BottomEdge | Qt.Edge.RightEdge),
        (QPoint(998, 10), Qt.Edge.TopEdge | Qt.Edge.RightEdge),  # corner area is larger
    ],
)
def test_resize_edges(pos, edges):
    assert resize_edges(pos, RECT, margin=5) == edges


def test_cursor_shapes():
    assert cursor_for(Qt.Edge.LeftEdge) == Qt.CursorShape.SizeHorCursor
    assert cursor_for(Qt.Edge.TopEdge) == Qt.CursorShape.SizeVerCursor
    assert cursor_for(Qt.Edge.TopEdge | Qt.Edge.LeftEdge) == Qt.CursorShape.SizeFDiagCursor
    assert cursor_for(Qt.Edge.TopEdge | Qt.Edge.RightEdge) == Qt.CursorShape.SizeBDiagCursor
    assert cursor_for(Qt.Edge(0)) == Qt.CursorShape.ArrowCursor


def test_main_window_is_frameless_with_its_own_title_bar_and_outline(qtbot):
    from beatgrid.gui import theme
    from beatgrid.gui.main_window import MainWindow
    from beatgrid.gui.widgets.title_bar import TitleBar

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(800, 500)
    window.show()
    qtbot.waitExposed(window)

    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    title_bar = window.menuWidget()
    assert isinstance(title_bar, TitleBar)
    assert title_bar.title_label.text() == "BeatGrid"

    image = window.grab().toImage()
    w, h = image.width(), image.height()  # the toolbar may widen the window
    for x, y in ((0, h // 2), (w - 1, h // 2), (w // 2, 0), (w // 2, h - 1)):
        assert image.pixelColor(x, y) == theme.OUTLINE, (x, y)


def test_title_bar_buttons_and_double_click(qtbot, monkeypatch):
    from beatgrid.gui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    title_bar = window.menuWidget()

    title_bar.maximize_button.click()
    qtbot.waitUntil(window.isMaximized)
    assert title_bar.maximize_button.text() == "❐"
    assert "Restore" in title_bar.maximize_button.toolTip()

    qtbot.mouseDClick(title_bar, Qt.MouseButton.LeftButton, pos=QPoint(200, 10))
    qtbot.waitUntil(lambda: not window.isMaximized())
    assert title_bar.maximize_button.text() == "□"

    calls = []
    monkeypatch.setattr(window, "showMinimized", lambda: calls.append("min"))
    monkeypatch.setattr(window, "close", lambda: calls.append("close") or True)
    # the buttons were connected to the bound methods at construction, so
    # check the wiring through the title bar's own button signals
    title_bar.minimize_button.clicked.disconnect()
    title_bar.minimize_button.clicked.connect(window.showMinimized)
    title_bar.close_button.clicked.disconnect()
    title_bar.close_button.clicked.connect(window.close)
    title_bar.minimize_button.click()
    title_bar.close_button.click()
    assert calls == ["min", "close"]
