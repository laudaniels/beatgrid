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


def test_drift_markers_fall_inside_visible_y_range(qtbot):
    from pathlib import Path

    from beatgrid.audio.loader import LoadedAudio
    from beatgrid.detection.transient import DriftPoint
    from beatgrid.gui.widgets.stem_track_view import StemTrackView
    from beatgrid.project.models import Stem

    audio = (0.3 * np.random.default_rng(0).uniform(-1, 1, 8 * SAMPLE_RATE)).astype(np.float32)
    view = StemTrackView(
        Stem(id="s", path=Path("s.wav"), sample_rate=SAMPLE_RATE), LoadedAudio(audio, SAMPLE_RATE)
    )
    qtbot.addWidget(view)
    view.set_drift_points([DriftPoint(time_sec=1.0, deviation_sec=0.0, is_drifting=False)])

    _xs, ys = view.drift_overlay._scatter.getData()
    y_min, y_max = view.view_box().viewRange()[1]
    assert y_min < ys[0] < y_max
