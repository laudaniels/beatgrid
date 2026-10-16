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


def _drum_like_hits(hit_times, sample_rate=44100, duration_sec=4.0):
    """Decaying noise bursts with a second, slightly weaker burst 25 ms into
    each hit's body -- the shape that used to yield an early (backtracked)
    onset plus a duplicate late one per hit."""
    import numpy as np

    rng = np.random.default_rng(0)
    audio = 0.002 * rng.standard_normal(int(duration_sec * sample_rate))
    body = np.arange(int(0.3 * sample_rate)) / sample_rate
    for hit in hit_times:
        for delay, amp in ((0.0, 0.8), (0.025, 0.6)):
            start = int((hit + delay) * sample_rate)
            burst = amp * np.exp(-body / 0.06) * rng.standard_normal(len(body))
            audio[start : start + len(body)] += burst[: len(audio) - start]
    return audio.astype(np.float32)


def test_detect_transients_gives_one_transient_at_each_hits_attack():
    pytest.importorskip("librosa")
    hit_times = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    audio = _drum_like_hits(hit_times)

    transients = detect_transients(audio, 44100)

    assert len(transients) == len(hit_times)
    for hit, transient in zip(hit_times, transients, strict=True):
        assert abs(transient - hit) < 0.005
