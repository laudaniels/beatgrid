import pytest
from PySide6.QtCore import QEvent, QPoint, QRect, QSize
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication

from beatgrid.gui.tooltip_placement import TooltipsInsideWindow, place_inside

pytestmark = pytest.mark.gui

WINDOW = QRect(0, 0, 1000, 600)
TIP = QSize(300, 60)


def test_tooltip_goes_below_right_of_the_pointer_when_there_is_room():
    assert place_inside(QPoint(100, 100), TIP, WINDOW) == QPoint(104, 120)


def test_tooltip_shifts_left_at_the_right_edge():
    top_left = place_inside(QPoint(980, 100), TIP, WINDOW)
    assert top_left.x() + TIP.width() <= WINDOW.right()
    assert top_left.y() == 120


def test_tooltip_flips_above_the_pointer_at_the_bottom_edge():
    top_left = place_inside(QPoint(100, 590), TIP, WINDOW)
    assert top_left.y() + TIP.height() < 590  # entirely above the pointer
    assert top_left.y() >= WINDOW.top()


def test_controls_at_the_bottom_and_right_show_tooltips_inside_the_window(qtbot, tmp_path):
    import numpy as np
    import soundfile as sf

    from beatgrid.gui.main_window import MainWindow

    app = QApplication.instance()
    tooltip_filter = TooltipsInsideWindow()
    app.installEventFilter(tooltip_filter)
    try:
        window = MainWindow()
        qtbot.addWidget(window)
        paths = []
        for name in ("kick", "bass"):
            path = tmp_path / f"{name}.wav"
            sf.write(path, np.zeros(16000, dtype=np.float32), 8000)
            paths.append(path)
        window.load_stems(paths)
        window.resize(1100, 650)
        window.show()
        qtbot.waitExposed(window)

        panel = window.track_views["bass"].stem_panel
        for widget in (
            window.transport_bar.play_button,
            panel.solo_checkbox,
            window.time_scrollbar,
        ):
            local = QPoint(widget.width() - 2, widget.height() // 2)
            QApplication.sendEvent(
                widget, QHelpEvent(QEvent.Type.ToolTip, local, widget.mapToGlobal(local))
            )
            label = tooltip_filter.label
            assert label is not None and label.parent() is window  # drawn inside the window
            assert window.rect().contains(label.geometry()), widget.toolTip()[:40]
            assert not label.geometry().contains(
                widget.mapTo(window, local)
            )  # not over the pointer
            assert label.text() == widget.toolTip()

            QApplication.sendEvent(widget, QEvent(QEvent.Type.Leave))
            assert tooltip_filter.label is None  # gone when the pointer leaves
    finally:
        app.removeEventFilter(tooltip_filter)


def test_tooltips_in_a_dialog_stay_inside_that_dialog(qtbot):
    from beatgrid.gui.widgets.warp_dialog import WarpDialog

    app = QApplication.instance()
    tooltip_filter = TooltipsInsideWindow()
    app.installEventFilter(tooltip_filter)
    try:
        dialog = WarpDialog(120.0)
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitExposed(dialog)
        button = dialog.close_button
        local = QPoint(button.width() - 2, button.height() - 2)
        QApplication.sendEvent(
            button, QHelpEvent(QEvent.Type.ToolTip, local, button.mapToGlobal(local))
        )
        label = tooltip_filter.label
        assert label is not None and label.parent() is dialog
        assert dialog.rect().contains(label.geometry())
    finally:
        app.removeEventFilter(tooltip_filter)
