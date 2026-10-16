from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from beatgrid.project.models import Stem


class StemPanel(QWidget):
    """Per-stem header: name/role, mute, solo. Mute/solo are just state on
    the Stem until playback (M6) exists to actually act on them."""

    muted_changed = Signal(str, bool)  # (stem_id, muted)
    solo_changed = Signal(str, bool)  # (stem_id, solo)

    def __init__(self, stem: Stem) -> None:
        super().__init__()
        self._stem_id = stem.id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel(f"{stem.role} — {stem.path.name}"))
        layout.addStretch(1)

        self.mute_checkbox = QCheckBox("M")
        self.mute_checkbox.setToolTip("Mute")
        self.mute_checkbox.setChecked(stem.muted)
        self.mute_checkbox.toggled.connect(
            lambda checked: self.muted_changed.emit(self._stem_id, checked)
        )
        layout.addWidget(self.mute_checkbox)

        self.solo_checkbox = QCheckBox("S")
        self.solo_checkbox.setToolTip("Solo")
        self.solo_checkbox.setChecked(stem.solo)
        self.solo_checkbox.toggled.connect(
            lambda checked: self.solo_changed.emit(self._stem_id, checked)
        )
        layout.addWidget(self.solo_checkbox)
