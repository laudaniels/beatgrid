from __future__ import annotations

import pyqtgraph as pg

from beatgrid.grid.model import Beat
from beatgrid.grid.timeline import project_time_to_stem_time
from beatgrid.project.models import Stem

BEAT_PEN = pg.mkPen((255, 255, 255, 80), width=1)
DOWNBEAT_PEN = pg.mkPen((255, 255, 255, 200), width=2)


class GridOverlay:
    """Non-interactive beat/bar lines drawn on one stem's plot, positioned in
    that stem's own local time. The reference stem additionally gets a
    draggable AnchorItem, added separately by the caller."""

    def __init__(self, plot_item: pg.PlotItem) -> None:
        self._plot_item = plot_item
        self._lines: list[pg.InfiniteLine] = []

    @property
    def line_count(self) -> int:
        return len(self._lines)

    def set_beats(self, beats: list[Beat], stem: Stem) -> None:
        self.clear()
        for beat in beats:
            local_time = project_time_to_stem_time(beat.time_sec, stem)
            pen = DOWNBEAT_PEN if beat.is_downbeat else BEAT_PEN
            line = pg.InfiniteLine(pos=local_time, angle=90, movable=False, pen=pen)
            self._plot_item.addItem(line)
            self._lines.append(line)

    def clear(self) -> None:
        for line in self._lines:
            self._plot_item.removeItem(line)
        self._lines.clear()
