import pytest

from beatgrid.detection.base import DetectionResult
from beatgrid.detection.librosa_detector import LibrosaBeatDetector
from beatgrid.detection.registry import available_detectors, get_detector, register


def test_librosa_is_always_available():
    assert "librosa" in available_detectors()
    assert isinstance(get_detector("librosa"), LibrosaBeatDetector)


def test_beat_this_is_default_when_installed():
    pytest.importorskip("beat_this")
    # If beat-this weren't installed, DEFAULT_DETECTOR_NAME would fall back
    # to "librosa" instead — see the try/except around its import in
    # registry.py.
    assert "beat_this" in available_detectors()
    assert get_detector().name == "beat_this"


def test_unknown_detector_raises():
    with pytest.raises(ValueError):
        get_detector("does-not-exist")


def test_register_adds_new_detector():
    class DummyDetector:
        name = "dummy"

        def detect(self, audio, sample_rate):
            return DetectionResult(bpm=120.0, beat_times=[0.0, 0.5])

    register("dummy", DummyDetector)

    assert "dummy" in available_detectors()
    assert isinstance(get_detector("dummy"), DummyDetector)
