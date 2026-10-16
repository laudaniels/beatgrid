from __future__ import annotations

import numpy as np
from scipy.signal import correlate, correlation_lags


def detect_offset(
    reference_audio: np.ndarray,
    reference_sample_rate: int,
    other_audio: np.ndarray,
    other_sample_rate: int,
    *,
    max_search_sec: float = 2.0,
    envelope_hz: float = 200.0,
) -> float:
    """Propose a `start_offset_sec` for `other_audio` relative to the
    reference, via cross-correlation of coarse amplitude envelopes
    (downsampled for speed) within a limited search window.

    This is always a *proposal* — the caller (GUI) presents it for the user
    to explicitly confirm before applying it to a Stem; it never adjusts
    audio or state on its own.

    Caveat: on strongly periodic content (e.g. a constant-tempo click track),
    the correlation has near-equally-strong peaks spaced by the beat period,
    so an offset larger than roughly half a beat can lock onto the wrong
    peak. Real multi-stem misalignments (different trim points, slightly
    different leading silence) are typically much smaller than that, but a
    proposed offset should still always be visually/audibly confirmed by the
    user, never applied blindly.
    """
    if reference_sample_rate != other_sample_rate:
        raise ValueError("cross-correlation needs both stems at the same sample rate")

    ref_env = _envelope(reference_audio, reference_sample_rate, downsample_hz=envelope_hz)
    other_env = _envelope(other_audio, other_sample_rate, downsample_hz=envelope_hz)

    correlation = correlate(other_env, ref_env, mode="full")
    lags = correlation_lags(len(other_env), len(ref_env), mode="full")

    max_lag_buckets = int(round(max_search_sec * envelope_hz))
    in_range = np.abs(lags) <= max_lag_buckets
    local_delay = lags[in_range][np.argmax(correlation[in_range])] / envelope_hz

    # local_delay is how much later the same content appears in `other`'s own
    # timeline than in the reference's; start_offset_sec is where `other`'s
    # own t=0 falls on the project timeline, i.e. its negation.
    return float(-local_delay)


def _envelope(audio: np.ndarray, sample_rate: int, *, downsample_hz: float) -> np.ndarray:
    factor = max(1, int(round(sample_rate / downsample_hz)))
    n_buckets = len(audio) // factor
    if n_buckets == 0:
        return np.abs(audio)
    usable = np.abs(audio[: n_buckets * factor]).reshape(n_buckets, factor)
    return usable.mean(axis=1)
