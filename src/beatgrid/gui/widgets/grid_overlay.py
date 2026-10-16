from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from beatgrid.grid.model import Beat
from beatgrid.grid.timeline import project_time_to_stem_time
from beatgrid.project.models import Stem

BEAT_PEN = pg.mkPen((255, 255, 255, 80), width=1)
DOWNBEAT_PEN = pg.mkPen((255, 255, 255, 200), width=2)

# Audio is normalized float32 (~[-1, 1]); lines are drawn full-height and
# excluded from Y-axis autorange (ignoreBounds=True below), so this just
# needs to comfortably cover the waveform's amplitude.
_LINE_Y_RANGE = (-1.5, 1.5)


class GridOverlay:
    """Non-interactive beat/bar lines drawn on one stem's plot, positioned in
    that stem's own local time.

    Drawn as two persistent multi-segment curves (one per pen style, updated
    via setData on redraw) rather than one pg.InfiniteLine GraphicsObject per
    beat: adding hundreds of individual InfiniteLine items in a loop has
    triggered native "bool_dealloc" crashes in pyqtgraph/PySide6, and this is
    also far cheaper to draw for long tracks with many beats.
    """

    def __init__(self, plot_item: pg.PlotItem) -> None:
        self._beat_curve = pg.PlotCurveItem(pen=BEAT_PEN)
        self._downbeat_curve = pg.PlotCurveItem(pen=DOWNBEAT_PEN)
        plot_item.addItem(self._beat_curve, ignoreBounds=True)
        plot_item.addItem(self._downbeat_curve, ignoreBounds=True)
        self._line_count = 0

    @property
    def line_count(self) -> int:
        return self._line_count

    def set_beats(self, beats: list[Beat], stem: Stem) -> None:
        beat_times: list[float] = []
        downbeat_times: list[float] = []
        for beat in beats:
            local_time = project_time_to_stem_time(beat.time_sec, stem)
            (downbeat_times if beat.is_downbeat else beat_times).append(local_time)

        self._set_segments(self._beat_curve, beat_times)
        self._set_segments(self._downbeat_curve, downbeat_times)
        self._line_count = len(beats)

    def clear(self) -> None:
        self._set_segments(self._beat_curve, [])
        self._set_segments(self._downbeat_curve, [])
        self._line_count = 0

    @staticmethod
    def _set_segments(curve: pg.PlotCurveItem, times: list[float]) -> None:
        y_min, y_max = _LINE_Y_RANGE
        xs = np.repeat(np.asarray(times, dtype=np.float64), 2)
        ys = np.tile([y_min, y_max], len(times))
        curve.setData(xs, ys, connect="pairs")
