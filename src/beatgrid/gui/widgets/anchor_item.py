from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal

from beatgrid.gui import tooltips

_UNSELECTED_PEN = pg.mkPen("y", width=2)
_SELECTED_PEN = pg.mkPen((255, 80, 80), width=3)


class AnchorItem(pg.InfiniteLine):
    """A draggable vertical line representing one grid anchor, positioned in
    the local time of whichever stem's plot it's added to. Only ever added to
    the reference stem's row — other rows render the grid read-only."""

    position_changed = Signal(str, float)  # (anchor_id, new_local_time_sec)
    selected = Signal(str)  # anchor_id

    def __init__(self, anchor_id: str, local_time_sec: float, *, is_selected: bool = False) -> None:
        super().__init__(
            pos=local_time_sec,
            angle=90,
            movable=True,
            pen=_SELECTED_PEN if is_selected else _UNSELECTED_PEN,
        )
        self.anchor_id = anchor_id
        self.setToolTip(tooltips.ANCHOR)
        self.sigPositionChangeFinished.connect(self._on_position_changed)
        self.sigClicked.connect(self._on_clicked)

    def _on_position_changed(self) -> None:
        self.position_changed.emit(self.anchor_id, float(self.value()))

    def _on_clicked(self, _line: pg.InfiniteLine, _event: object) -> None:
        self.selected.emit(self.anchor_id)
