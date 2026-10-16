import numpy as np
import pytest

pytest.importorskip("pedalboard")

from beatgrid.render.engines.pedalboard_stretcher import PedalboardStretcher  # noqa: E402


def _tone(sample_rate=8000, duration_sec=2.0):
    t = np.arange(int(duration_sec * sample_rate)) / sample_rate
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_stretch_lengthens_audio_by_ratio():
    sr = 8000
    audio = _tone(sr, 2.0)

    out = PedalboardStretcher().stretch(audio, sr, ratio=1.25)

    assert len(out) == pytest.approx(len(audio) * 1.25, rel=0.02)


def test_stretch_shortens_audio_by_ratio():
    sr = 8000
    audio = _tone(sr, 2.0)

    out = PedalboardStretcher().stretch(audio, sr, ratio=0.8)

    assert len(out) == pytest.approx(len(audio) * 0.8, rel=0.02)


def test_ratio_one_preserves_length_approximately():
    sr = 8000
    audio = _tone(sr, 2.0)

    out = PedalboardStretcher().stretch(audio, sr, ratio=1.0)

    assert len(out) == pytest.approx(len(audio), rel=0.02)


def test_rejects_non_positive_ratio():
    stretcher = PedalboardStretcher()
    with pytest.raises(ValueError):
        stretcher.stretch(np.zeros(100, dtype=np.float32), 8000, ratio=0.0)
    with pytest.raises(ValueError):
        stretcher.stretch(np.zeros(100, dtype=np.float32), 8000, ratio=-1.0)


def test_engine_name():
    assert PedalboardStretcher().name == "pedalboard"
