from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QPalette
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from beatgrid.gui import tooltips
from beatgrid.project.models import Stem


class StemPanel(QWidget):
    """Per-stem header: name/role, mute, solo. Clicking the bar itself (not
    the checkboxes) asks for this stem's row to be enlarged."""

    muted_changed = Signal(str, bool)  # (stem_id, muted)
    solo_changed = Signal(str, bool)  # (stem_id, solo)
    clicked = Signal(str)  # stem_id

    def __init__(self, stem: Stem) -> None:
        super().__init__()
        self._stem_id = stem.id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.name_label = QLabel(f"{stem.role} — {stem.path.name}")
        layout.addWidget(self.name_label)
        layout.addStretch(1)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltips.STEM_NAME_BAR)
        self.setAutoFillBackground(True)
        self._normal_palette = QPalette(self.palette())

        self.mute_checkbox = QCheckBox("M")
        self.mute_checkbox.setToolTip(tooltips.MUTE)
        self.mute_checkbox.setChecked(stem.muted)
        self.mute_checkbox.toggled.connect(
            lambda checked: self.muted_changed.emit(self._stem_id, checked)
        )
        layout.addWidget(self.mute_checkbox)

        self.solo_checkbox = QCheckBox("S")
        self.solo_checkbox.setToolTip(tooltips.SOLO)
        self.solo_checkbox.setChecked(stem.solo)
        self.solo_checkbox.toggled.connect(
            lambda checked: self.solo_changed.emit(self._stem_id, checked)
        )
        layout.addWidget(self.solo_checkbox)

    def set_focused(self, focused: bool) -> None:
        """Highlight the bar of the enlarged stem."""
        palette = QPalette(self._normal_palette)
        if focused:
            highlight = palette.color(QPalette.ColorRole.Highlight)
            palette.setColor(QPalette.ColorRole.Window, highlight.darker(220))
        self.setPalette(palette)
        font = QFont(self.name_label.font())
        font.setBold(focused)
        self.name_label.setFont(font)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._stem_id)
            event.accept()
            return
        super().mousePressEvent(event)
