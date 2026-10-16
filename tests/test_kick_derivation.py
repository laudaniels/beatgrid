import numpy as np

from beatgrid.audio.kick_derivation import derive_kick_signal


def test_derive_kick_signal_attenuates_high_frequency_content():
    sample_rate = 8000
    duration_sec = 1.0
    t = np.arange(int(duration_sec * sample_rate)) / sample_rate

    low = np.sin(2 * np.pi * 60 * t)  # well within the kick band
    high = np.sin(2 * np.pi * 3000 * t)  # well above the cutoff
    mixed = (low + high).astype(np.float32)

    filtered = derive_kick_signal(mixed, sample_rate, cutoff_hz=120.0)

    assert np.std(filtered) < np.std(mixed)
    assert np.corrcoef(filtered, low)[0, 1] > 0.9


def test_derive_kick_signal_preserves_length_and_dtype():
    sample_rate = 8000
    audio = np.random.default_rng(0).normal(size=sample_rate).astype(np.float32)

    filtered = derive_kick_signal(audio, sample_rate)

    assert len(filtered) == len(audio)
    assert filtered.dtype == np.float32
