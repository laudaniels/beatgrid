import numpy as np
import soundfile as sf

from beatgrid.audio.loader import load_audio


def test_load_mono_wav(tmp_path):
    sample_rate = 8000
    audio = np.sin(2 * np.pi * 440 * np.arange(sample_rate) / sample_rate).astype(np.float32)
    path = tmp_path / "mono.wav"
    sf.write(path, audio, sample_rate)

    loaded = load_audio(path)

    assert loaded.sample_rate == sample_rate
    assert loaded.audio.ndim == 1
    assert len(loaded.audio) == sample_rate
    assert np.allclose(loaded.audio, audio, atol=1e-4)


def test_load_stereo_wav_downmixes_to_mono(tmp_path):
    sample_rate = 8000
    left = np.full(sample_rate, 0.5, dtype=np.float32)
    right = np.full(sample_rate, -0.5, dtype=np.float32)
    stereo = np.stack([left, right], axis=1)
    path = tmp_path / "stereo.wav"
    sf.write(path, stereo, sample_rate)

    loaded = load_audio(path)

    assert loaded.audio.ndim == 1
    assert np.allclose(loaded.audio, 0.0, atol=1e-6)
