import pytest
from fixtures import make_click_track

from beatgrid.detection.base import DetectionResult
from beatgrid.detection.librosa_detector import LibrosaBeatDetector

pytest.importorskip("librosa")


def test_detects_tempo_within_tolerance_on_synthetic_click_track():
    track = make_click_track(bpm=120.0, duration_sec=10.0, sample_rate=44100)
    detector = LibrosaBeatDetector()

    result = detector.detect(track.audio, track.sample_rate)

    assert isinstance(result, DetectionResult)
    assert result.bpm == pytest.approx(120.0, abs=2.0)
    assert len(result.beat_times) >= 4


def test_detector_name():
    assert LibrosaBeatDetector().name == "librosa"
