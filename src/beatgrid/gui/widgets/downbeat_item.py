from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal

from beatgrid.gui import tooltips

_PEN = pg.mkPen((60, 220, 255), width=3)
_HOVER_PEN = pg.mkPen((150, 240, 255), width=4)
# Only the top part of the row: an anchor usually sits on the same beat, and
# a full-height line would cover it and steal its drags.
_SPAN = (0.8, 1.0)


class DownbeatItem(pg.InfiniteLine):
    """The draggable "first downbeat" marker (bar 1, beat 1) on the reference
    stem's row, in that stem's local time. Where it's dropped is only a
    request: the controller moves the downbeat to the nearest beat and the
    next redraw puts the marker exactly there."""

    moved = Signal(float)  # new local time, seconds

    def __init__(self, local_time_sec: float) -> None:
        super().__init__(
            pos=local_time_sec,
            angle=90,
            movable=True,
            pen=_PEN,
            hoverPen=_HOVER_PEN,
            span=_SPAN,
            label="1",
            labelOpts={"position": 0.95, "color": (60, 220, 255), "anchors": [(0, 0.5), (0, 0.5)]},
        )
        self.setToolTip(tooltips.FIRST_DOWNBEAT)
        self.setZValue(5)
        self.sigPositionChangeFinished.connect(lambda: self.moved.emit(float(self.value())))
