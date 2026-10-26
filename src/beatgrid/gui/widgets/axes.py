from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg

# Leave at least this much room per bar-number label.
_MIN_LABEL_SPACING_PX = 45


def format_time(seconds: float, spacing: float) -> str:
    """m:ss, with as many decimals as the tick spacing needs (1:30, 1:30.5,
    1:30.25); negative times get a leading minus."""
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    decimals = 0 if spacing >= 1 else min(3, math.ceil(-math.log10(spacing) - 1e-9))
    minutes, rest = divmod(round(seconds, decimals), 60)
    width = 2 if decimals == 0 else 3 + decimals
    return f"{sign}{int(minutes)}:{rest:0{width}.{decimals}f}"


class TimeAxisItem(pg.AxisItem):
    """Bottom axis showing seconds as m:ss, the way people talk about a
    position in a song ("around 1:30")."""

    def tickStrings(self, values, scale, spacing):  # noqa: N802 - pyqtgraph API
        return [format_time(v * scale, spacing * scale) for v in values]


class BarAxisItem(pg.AxisItem):
    """Top axis with bar numbers at each downbeat (a bar's first beat), in the
    track's local time. Thins out to every 2nd/4th/8th... bar when zoomed
    out so labels never overlap."""

    def __init__(self, orientation: str = "top", **kwargs) -> None:
        super().__init__(orientation, **kwargs)
        self._times = np.empty(0)
        self._bars = np.empty(0, dtype=int)

    def set_bars(self, bars: list[tuple[float, int]]) -> None:
        """(local time of the downbeat, bar number) pairs, in time order."""
        self._times = np.array([t for t, _bar in bars], dtype=float)
        self._bars = np.array([bar for _t, bar in bars], dtype=int)
        self.picture = None  # pyqtgraph: force a re-layout of the ticks
        self.update()

    def tickValues(self, minVal, maxVal, size):  # noqa: N802 - pyqtgraph API
        if len(self._times) < 2 or maxVal <= minVal or size <= 0:
            return []
        px_per_sec = size / (maxVal - minVal)
        bar_sec = float(np.median(np.diff(self._times)))
        step = 1
        while step * bar_sec * px_per_sec < _MIN_LABEL_SPACING_PX:
            step *= 2
        shown = (self._times >= minVal) & (self._times <= maxVal) & ((self._bars - 1) % step == 0)
        return [(step * bar_sec, self._times[shown].tolist())]

    def tickStrings(self, values, scale, spacing):  # noqa: N802 - pyqtgraph API
        labels = []
        for value in values:
            i = int(np.argmin(np.abs(self._times - value))) if len(self._times) else -1
            labels.append(str(self._bars[i]) if i >= 0 else "")
        return labels
