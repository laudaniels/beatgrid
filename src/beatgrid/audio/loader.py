from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass
class LoadedAudio:
    audio: np.ndarray  # mono, float32, shape (n_samples,)
    sample_rate: int


def load_audio(path: Path) -> LoadedAudio:
    """Load wav/flac/mp3 as mono float32.

    soundfile (libsndfile) handles wav/flac directly. Some mp3s aren't
    decodable by libsndfile, so those fall back to librosa/audioread, which
    needs ffmpeg on PATH.
    """
    path = Path(path)
    try:
        data, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    except RuntimeError:
        data, sample_rate = _load_via_librosa(path)

    if data.ndim > 1:
        data = data.mean(axis=1).astype(np.float32)

    return LoadedAudio(audio=data, sample_rate=sample_rate)


def _load_via_librosa(path: Path) -> tuple[np.ndarray, int]:
    try:
        import librosa
    except ImportError as exc:
        raise RuntimeError(
            f"Could not load {path} via soundfile, and librosa (needed as a "
            "fallback for formats like mp3) is not installed. "
            "Install the 'core' extra: uv sync --extra core"
        ) from exc

    audio, sample_rate = librosa.load(path, sr=None, mono=False)
    # librosa returns (channels, samples) for stereo; soundfile's convention
    # (and the rest of this function) expects (samples, channels).
    if audio.ndim > 1:
        audio = audio.T
    return audio, sample_rate
