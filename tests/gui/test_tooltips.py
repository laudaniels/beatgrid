import pytest
from PySide6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox, QToolBar

from beatgrid.gui.main_window import MainWindow
from beatgrid.gui.widgets.warp_dialog import WarpDialog

pytestmark = pytest.mark.gui


def _assert_full_help(name: str, text: str) -> None:
    assert "<b>" in text, f"{name}: no title"
    assert "<br>" in text and len(text) > 60, f"{name}: no explanation"
    assert "{" not in text, f"{name}: unfilled placeholder"


def test_every_toolbar_action_and_control_explains_itself(qtbot, tmp_path):
    import numpy as np
    import soundfile as sf

    window = MainWindow()
    qtbot.addWidget(window)
    paths = []
    for name in ("kick", "bass"):
        path = tmp_path / f"{name}.wav"
        sf.write(path, np.zeros(16000, dtype=np.float32), 8000)
        paths.append(path)
    window.load_stems(paths)

    toolbar = window.findChild(QToolBar)
    toolbar_actions = [a for a in toolbar.actions() if a.text() and not a.isSeparator()]
    assert len(toolbar_actions) >= 12
    for action in toolbar_actions:
        _assert_full_help(action.text(), action.toolTip())

    controls = window.findChildren(QAbstractButton) + window.findChildren(QComboBox)
    controls += window.findChildren(QAbstractSpinBox)
    for widget in controls:
        if widget.objectName().startswith("qt_") or not widget.isVisibleTo(window):
            continue  # Qt's own internals (toolbar extension, scroll arrows, ...)
        _assert_full_help(
            type(widget).__name__ + " " + getattr(widget, "text", str)(), widget.toolTip()
        )

    for view in window.track_views.values():
        _assert_full_help("name bar", view.stem_panel.toolTip())
    _assert_full_help("scrollbar", window.time_scrollbar.toolTip())


def test_warp_dialog_controls_explain_themselves(qtbot):
    from pathlib import Path

    dialog = WarpDialog(120.0)
    qtbot.addWidget(dialog)
    dialog.set_folder_contents(Path("/music/warped"), 3, 3000)
    for widget in dialog.findChildren(QAbstractButton) + [dialog.bpm_spinbox, dialog.engine_combo]:
        _assert_full_help(getattr(widget, "text", str)(), widget.toolTip())
    assert "/music/warped" in dialog.cleanup_button.toolTip()
