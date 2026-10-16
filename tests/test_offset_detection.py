import numpy as np
import pytest
from fixtures import make_stem_set

from beatgrid.audio.offset_detection import detect_offset


def test_detects_known_offset_between_two_stems():
    reference, other = make_stem_set(
        bpm=120.0,
        duration_sec=6.0,
        n_stems=2,
        sample_rate=8000,
        offsets_sec=[0.0, 0.35],
        noise_level=0.0,
    )

    offset = detect_offset(reference.audio, reference.sample_rate, other.audio, other.sample_rate)

    assert offset == pytest.approx(-0.35, abs=0.01)


def test_detects_negative_offset():
    reference, other = make_stem_set(
        bpm=120.0,
        duration_sec=6.0,
        n_stems=2,
        sample_rate=8000,
        offsets_sec=[0.3, 0.0],
        noise_level=0.0,
    )

    offset = detect_offset(reference.audio, reference.sample_rate, other.audio, other.sample_rate)

    # other's content appears *earlier* than reference's by 0.3s, so other's
    # own t=0 falls *later* on the project timeline -> positive offset
    assert offset == pytest.approx(0.3, abs=0.01)


def test_zero_offset_when_aligned():
    reference, other = make_stem_set(
        bpm=120.0,
        duration_sec=6.0,
        n_stems=2,
        sample_rate=8000,
        offsets_sec=[0.0, 0.0],
        noise_level=0.0,
    )

    offset = detect_offset(reference.audio, reference.sample_rate, other.audio, other.sample_rate)

    assert offset == pytest.approx(0.0, abs=0.01)


def test_robust_to_modest_independent_noise():
    # A small, realistic misalignment (well under half the 0.6s beat
    # interval) -- see the periodicity caveat in offset_detection.py for why
    # a *large* offset on a perfectly periodic click track isn't a fair test.
    reference, other = make_stem_set(
        bpm=100.0,
        duration_sec=8.0,
        n_stems=2,
        sample_rate=8000,
        offsets_sec=[0.0, 0.15],
        noise_level=0.05,
    )

    offset = detect_offset(reference.audio, reference.sample_rate, other.audio, other.sample_rate)

    assert offset == pytest.approx(-0.15, abs=0.01)


def test_raises_on_mismatched_sample_rates():
    with pytest.raises(ValueError):
        detect_offset(np.zeros(100), 44100, np.zeros(100), 48000)
