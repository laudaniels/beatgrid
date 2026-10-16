from __future__ import annotations

import pyqtgraph as pg

from beatgrid.detection.transient import DriftPoint

_NORMAL_BRUSH = pg.mkBrush(100, 200, 255, 180)
_DRIFT_BRUSH = pg.mkBrush(255, 120, 0, 220)


class DriftOverlay:
    """Small markers showing where a stem's own transients fall relative to
    the shared grid — purely diagnostic (detection.transient.compute_drift
    does the actual comparison), never adjusts the grid or the transient.
    A transient flagged as drifting is drawn in a different color."""

    def __init__(self, plot_item: pg.PlotItem, marker_y: float) -> None:
        # marker_y must fall inside the plot's (fixed) y-range, or the
        # markers are silently drawn off-screen
        self._marker_y = marker_y
        self._scatter = pg.ScatterPlotItem(size=8, pen=None)
        plot_item.addItem(self._scatter, ignoreBounds=True)
        self._point_count = 0

    @property
    def point_count(self) -> int:
        return self._point_count

    def set_points(self, points: list[DriftPoint]) -> None:
        if not points:
            self.clear()
            return
        xs = [p.time_sec for p in points]
        ys = [self._marker_y] * len(points)
        brushes = [_DRIFT_BRUSH if p.is_drifting else _NORMAL_BRUSH for p in points]
        self._scatter.setData(xs, ys, brush=brushes)
        self._point_count = len(points)

    def clear(self) -> None:
        self._scatter.setData([], [])
        self._point_count = 0
