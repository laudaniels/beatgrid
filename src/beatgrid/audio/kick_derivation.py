from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt


def derive_kick_signal(
    audio: np.ndarray,
    sample_rate: int,
    *,
    cutoff_hz: float = 120.0,
    order: int = 4,
) -> np.ndarray:
    """A kick-like signal derived from a drums stem: low-pass filtered to
    emphasize the kick's low-frequency thump.

    Used only to feed a beat detector when a project has no dedicated kick
    stem — this is never exported or treated as a real stem.
    """
    nyquist = sample_rate / 2.0
    normalized_cutoff = min(cutoff_hz / nyquist, 0.99)
    b, a = butter(N=order, Wn=normalized_cutoff, btype="low")
    return filtfilt(b, a, audio).astype(np.float32)
