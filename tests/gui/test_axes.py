import pytest

from beatgrid.gui.widgets.axes import BarAxisItem, format_time

pytestmark = pytest.mark.gui


@pytest.mark.parametrize(
    ("seconds", "spacing", "expected"),
    [
        (90.0, 10.0, "1:30"),
        (5.0, 10.0, "0:05"),
        (90.5, 0.5, "1:30.5"),
        (90.25, 0.05, "1:30.25"),
        (89.6, 10.0, "1:30"),
        (-2.0, 1.0, "-0:02"),
    ],
)
def test_format_time_as_minutes_and_seconds(seconds, spacing, expected):
    assert format_time(seconds, spacing) == expected


def test_bar_axis_labels_downbeats_and_thins_out_when_zoomed_out(qtbot):
    axis = BarAxisItem("top")
    bars = [(2.0 * i, i + 1) for i in range(64)]  # a bar every 2 s, bars 1..64
    axis.set_bars(bars)

    # zoomed in: 10 s over 1000 px -> every bar has room (200 px apart)
    ((_spacing, values),) = axis.tickValues(0.0, 10.0, 1000)
    assert values == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    assert axis.tickStrings(values, 1.0, 2.0) == ["1", "2", "3", "4", "5", "6"]

    # zoomed out: 128 s over 400 px -> ~6 px per bar, so every 8th bar
    ((_spacing, values),) = axis.tickValues(0.0, 128.0, 400)
    assert axis.tickStrings(values, 1.0, 16.0) == ["1", "9", "17", "25", "33", "41", "49", "57"]


def test_bar_numbers_only_on_the_reference_row_and_follow_the_downbeat(qtbot, tmp_path):
    import numpy as np
    import soundfile as sf

    from beatgrid.gui.main_window import MainWindow

    paths = []
    for name in ("kick", "bass"):
        path = tmp_path / f"{name}.wav"
        sf.write(path, (0.3 * np.sin(np.arange(8 * 8000) / 5)).astype(np.float32), 8000)
        paths.append(path)
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_stems(paths)  # anchor at 0 s, 120 BPM: a bar every 2 s

    kick_axis = window.track_views["kick"].plot_widget.getPlotItem().getAxis("top")
    bass_axis = window.track_views["bass"].plot_widget.getPlotItem().getAxis("top")
    assert kick_axis.isVisible() and not bass_axis.isVisible()
    assert kick_axis._times.tolist()[:3] == [0.0, 2.0, 4.0]
    assert kick_axis._bars.tolist()[:3] == [1, 2, 3]

    window.controller.set_downbeat(0.5)
    assert kick_axis._times.tolist()[:3] == [0.5, 2.5, 4.5]
    assert kick_axis._bars.tolist()[:3] == [1, 2, 3]
