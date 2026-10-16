import numpy as np
import pyqtgraph as pg
import pytest

from beatgrid.gui.widgets.waveform_item import WaveformItem

pytestmark = pytest.mark.gui

SAMPLE_RATE = 8000


def _quiet_intro_then_loud() -> np.ndarray:
    # 2s near-silent intro, then 8s at full level: auto-ranging on the
    # initially visible intro would scale the loud part ~100x off-screen.
    rng = np.random.default_rng(0)
    quiet = 0.005 * rng.uniform(-1, 1, 2 * SAMPLE_RATE)
    loud = 0.8 * rng.uniform(-1, 1, 8 * SAMPLE_RATE)
    return np.concatenate([quiet, loud]).astype(np.float32)


def test_y_range_covers_whole_file_peak(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    WaveformItem(widget.getPlotItem(), _quiet_intro_then_loud(), SAMPLE_RATE)

    view_box = widget.getPlotItem().getViewBox()
    view_box.setXRange(0.0, 0.5, padding=0)  # zoom into the quiet intro
    (y_min, y_max) = view_box.viewRange()[1]
    assert y_min <= -0.8 and y_max >= 0.8


def test_zoomed_past_finest_level_draws_connected_raw_samples(qtbot):
    widget = pg.PlotWidget()
    widget.resize(800, 200)
    qtbot.addWidget(widget)
    audio = _quiet_intro_then_loud()
    item = WaveformItem(widget.getPlotItem(), audio, SAMPLE_RATE)

    view_box = widget.getPlotItem().getViewBox()
    view_box.setXRange(5.0, 5.01, padding=0)  # 80 samples across the view
    xs, ys = item._curve.getData()
    start = int(xs[0] * SAMPLE_RATE + 0.5)
    assert np.array_equal(ys, audio[start : start + len(ys)])
