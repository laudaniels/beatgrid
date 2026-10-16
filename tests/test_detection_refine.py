import numpy as np
import pytest
from fixtures import make_click_track

from beatgrid.detection.refine import fit_anchor_and_bpm, propose_anchor


def test_fit_recovers_exact_tempo_and_anchor_without_jitter():
    bpm = 128.0
    anchor_time = 1.234
    interval = 60.0 / bpm
    indices = list(range(16))
    times = [anchor_time + i * interval for i in indices]

    fitted_anchor, fitted_bpm = fit_anchor_and_bpm(times, indices)

    assert fitted_anchor == pytest.approx(anchor_time, abs=1e-9)
    assert fitted_bpm == pytest.approx(bpm, abs=1e-9)


def test_fit_recovers_tempo_within_tolerance_under_jitter():
    bpm = 120.0
    anchor_time = 0.0
    interval = 60.0 / bpm
    indices = list(range(32))
    rng = np.random.default_rng(0)
    jitter = rng.normal(0.0, 0.003, size=len(indices))
    times = [anchor_time + i * interval + j for i, j in zip(indices, jitter, strict=True)]

    fitted_anchor, fitted_bpm = fit_anchor_and_bpm(times, indices)

    assert fitted_bpm == pytest.approx(bpm, abs=0.5)
    assert fitted_anchor == pytest.approx(anchor_time, abs=0.01)


def test_propose_anchor_cleans_up_jittery_detector_output():
    pytest.importorskip("librosa")
    bpm = 120.0
    anchor_time = 0.5
    track = make_click_track(
        bpm=bpm, duration_sec=6.0, sample_rate=44100, start_offset_sec=anchor_time
    )

    # simulate a detector that's slightly imprecise (jittered by a few ms)
    rng = np.random.default_rng(1)
    jittered = [t + rng.normal(0.0, 0.01) for t in track.beat_times]

    fitted_anchor, fitted_bpm = propose_anchor(jittered, track.audio, track.sample_rate)

    assert fitted_bpm == pytest.approx(bpm, abs=1.0)
    assert fitted_anchor == pytest.approx(anchor_time, abs=0.01)


def test_requires_at_least_two_beats():
    with pytest.raises(ValueError):
        fit_anchor_and_bpm([1.0], [0])


def test_rejects_non_increasing_times():
    with pytest.raises(ValueError):
        fit_anchor_and_bpm([1.0, 0.5, 0.0], [0, 1, 2])
