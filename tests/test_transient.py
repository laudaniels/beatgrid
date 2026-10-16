import pytest
from fixtures import make_click_track

from beatgrid.detection.transient import (
    compute_drift,
    detect_transients,
    snap_to_nearest_transient,
)


def test_detect_transients_finds_times_close_to_known_clicks():
    pytest.importorskip("librosa")
    track = make_click_track(bpm=120.0, duration_sec=6.0, sample_rate=44100)

    transients = detect_transients(track.audio, track.sample_rate)

    assert len(transients) >= 4
    # every detected transient should land near one of the known click times
    for transient_time in transients:
        nearest_known = min(track.beat_times, key=lambda t: abs(t - transient_time))
        assert abs(nearest_known - transient_time) < 0.05


def test_snap_to_nearest_transient_within_tolerance():
    transients = [1.0, 2.0, 3.0]
    assert snap_to_nearest_transient(1.03, transients, max_distance_sec=0.05) == 1.0


def test_snap_to_nearest_transient_outside_tolerance_unchanged():
    transients = [1.0, 2.0, 3.0]
    assert snap_to_nearest_transient(1.5, transients, max_distance_sec=0.05) == 1.5


def test_snap_to_nearest_transient_with_no_transients_unchanged():
    assert snap_to_nearest_transient(1.5, [], max_distance_sec=0.05) == 1.5


def test_compute_drift_flags_points_beyond_threshold():
    grid_beats = [0.0, 0.5, 1.0]
    transients = [0.005, 0.5, 1.03]

    points = compute_drift(transients, grid_beats, threshold_sec=0.02)

    assert [p.is_drifting for p in points] == [False, False, True]
    assert points[2].deviation_sec == pytest.approx(0.03, abs=1e-9)


def test_compute_drift_with_empty_grid_never_flags():
    points = compute_drift([0.1, 0.2], [], threshold_sec=0.02)

    assert all(not p.is_drifting for p in points)
    assert [p.deviation_sec for p in points] == [0.0, 0.0]


def test_compute_drift_with_no_transients():
    assert compute_drift([], [0.0, 0.5], threshold_sec=0.02) == []
