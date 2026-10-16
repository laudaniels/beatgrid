from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from beatgrid.audio.waveform_cache import (
    PeakLevel,
    build_waveform_cache,
    level_to_xy,
    samples_to_xy,
)

WAVEFORM_PEN = pg.mkPen((100, 180, 255))


class WaveformItem:
    """Renders a waveform efficiently via a precomputed multi-resolution
    min/max peak pyramid (audio/waveform_cache.py): each redraw picks the
    coarsest level that still has roughly one bucket per screen pixel *and*
    converts only the buckets actually within the visible range — touching
    the chosen level's full extent regardless of zoom would defeat the
    point of picking a finer level in the first place. This is what keeps a
    redraw cheap even on very long files, unlike pyqtgraph's own
    autoDownsample, which rescans the whole backing array every time.

    The y-range is fixed to the whole file's peak: auto-ranging on the
    visible slice (or on whatever was visible at construction time, e.g. a
    quiet intro) would scale loud passages far past the plot's edges."""

    def __init__(self, plot_item: pg.PlotItem, audio: np.ndarray, sample_rate: int) -> None:
        self._audio = audio
        self._sample_rate = sample_rate
        self._cache = build_waveform_cache(audio, sample_rate)
        self._curve = pg.PlotCurveItem(pen=WAVEFORM_PEN)
        plot_item.addItem(self._curve)

        view_box = plot_item.getViewBox()
        view_box.sigXRangeChanged.connect(self._on_range_changed)
        self._redraw(view_box)
        plot_item.autoRange()
        y_extent = self._cache.peak if self._cache.peak > 0 else 1.0
        view_box.setYRange(-y_extent, y_extent, padding=0.05)
        view_box.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

    def _on_range_changed(self, view_box: pg.ViewBox, _x_range: tuple[float, float]) -> None:
        self._redraw(view_box)

    def _redraw(self, view_box: pg.ViewBox) -> None:
        (x_min, x_max), _y_range = view_box.viewRange()
        width_px = max(1, view_box.width())
        visible_sec = max(1e-9, x_max - x_min)
        samples_per_pixel = visible_sec * self._sample_rate / width_px

        if samples_per_pixel < self._cache.levels[0].bucket_size:
            xs, ys = samples_to_xy(
                self._audio,
                self._sample_rate,
                int(x_min * self._sample_rate) - 1,
                int(x_max * self._sample_rate) + 2,
            )
            self._curve.setData(xs, ys, connect="all")
            return

        level = self._cache.level_for_samples_per_pixel(samples_per_pixel)
        bucket_sec = level.bucket_size / self._sample_rate
        start_bucket = max(0, int(x_min / bucket_sec) - 1)
        end_bucket = min(len(level.mins), int(x_max / bucket_sec) + 2)

        visible_level = PeakLevel(
            bucket_size=level.bucket_size,
            mins=level.mins[start_bucket:end_bucket],
            maxs=level.maxs[start_bucket:end_bucket],
        )
        xs, ys = level_to_xy(visible_level, self._sample_rate)
        xs = xs + start_bucket * bucket_sec
        self._curve.setData(xs, ys, connect="pairs")
