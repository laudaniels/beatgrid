from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal


class AnchorItem(pg.InfiniteLine):
    """A draggable vertical line representing one grid anchor, positioned in
    the local time of whichever stem's plot it's added to. Only ever added to
    the reference stem's row — other rows render the grid read-only."""

    position_changed = Signal(str, float)  # (anchor_id, new_local_time_sec)

    def __init__(self, anchor_id: str, local_time_sec: float) -> None:
        super().__init__(pos=local_time_sec, angle=90, movable=True, pen=pg.mkPen("y", width=2))
        self.anchor_id = anchor_id
        self.sigPositionChangeFinished.connect(self._on_position_changed)

    def _on_position_changed(self) -> None:
        self.position_changed.emit(self.anchor_id, float(self.value()))
