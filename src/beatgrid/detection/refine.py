from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def propose_anchor(
    beat_times: Sequence[float],
    audio: np.ndarray,
    sample_rate: int,
    *,
    snap_tolerance_sec: float = 0.05,
) -> tuple[float, float]:
    """From a detector's raw beat times: snap each to the nearest sample-
    precise transient (when close enough) to remove detector-level jitter,
    then fit a robust (anchor_time, bpm) via linear regression over the
    refined times. Used by the GUI's "Detect" action, independent of which
    BeatDetector produced the raw beat_times."""
    from beatgrid.detection.transient import detect_transients, snap_to_nearest_transient

    transients = detect_transients(audio, sample_rate)
    refined_times = [
        snap_to_nearest_transient(t, transients, max_distance_sec=snap_tolerance_sec)
        for t in beat_times
    ]
    return fit_anchor_and_bpm(refined_times, list(range(len(refined_times))))


def fit_anchor_and_bpm(
    beat_times: Sequence[float], beat_indices: Sequence[int]
) -> tuple[float, float]:
    """Least-squares fit of beat_index -> beat_time: the slope gives 60/bpm,
    the intercept gives the anchor time. Averages out small per-beat jitter
    in raw detector output into one robust (anchor_time, bpm) estimate —
    used both for the initial single-anchor estimate and, per segment, for
    multi-anchor tempo drift.
    """
    if len(beat_times) < 2:
        raise ValueError("need at least 2 beats to fit a tempo")

    slope, intercept = np.polyfit(beat_indices, beat_times, deg=1)
    if slope <= 0:
        raise ValueError("beat times must increase with beat index")

    bpm = 60.0 / slope
    return float(intercept), float(bpm)
