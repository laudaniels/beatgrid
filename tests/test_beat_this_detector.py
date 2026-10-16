import numpy as np
import pytest
from fixtures import make_click_track

from beatgrid.detection.base import DetectionResult
from beatgrid.detection.beat_this_detector import BeatThisDetector

pytest.importorskip("beat_this")


def test_detect_returns_sane_result_on_synthetic_click_track():
    track = make_click_track(bpm=128.0, duration_sec=8.0, sample_rate=44100)
    detector = BeatThisDetector()

    result = detector.detect(track.audio, track.sample_rate)

    assert isinstance(result, DetectionResult)
    assert len(result.beat_times) >= 2
    assert result.beat_times == sorted(result.beat_times)
    # Beat This! is trained on real music, not synthetic clicks, so this is a
    # loose sanity check on the wrapper (units, array handling, the
    # refine.fit_anchor_and_bpm integration) rather than an accuracy claim.
    assert 60.0 < result.bpm < 200.0


def test_detector_name():
    assert BeatThisDetector().name == "beat_this"


def test_raises_when_fewer_than_two_beats_detected(monkeypatch):
    detector = BeatThisDetector()
    monkeypatch.setattr(detector, "_get_audio2beats", lambda: lambda audio, sr: ([0.1], []))

    with pytest.raises(ValueError):
        detector.detect(np.zeros(100, dtype=np.float32), 44100)
