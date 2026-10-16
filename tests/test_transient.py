import pytest
from fixtures import make_click_track

from beatgrid.detection.transient import detect_transients, snap_to_nearest_transient

pytest.importorskip("librosa")


def test_detect_transients_finds_times_close_to_known_clicks():
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
