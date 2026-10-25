from __future__ import annotations

from collections.abc import Sequence

import numpy as np

MAX_BPM = 180.0  # no supported material is faster; above this is double time
_HIT_WINDOW_SEC = 0.03


def propose_anchor(
    beat_times: Sequence[float],
    audio: np.ndarray,
    sample_rate: int,
    *,
    snap_tolerance_sec: float = 0.05,
    max_bpm: float = MAX_BPM,
) -> tuple[float, float]:
    """From a detector's raw beat times: snap each to the nearest sample-
    precise transient (when close enough) to remove detector-level jitter,
    then fit a robust (anchor_time, bpm) via linear regression over the
    refined times. Used by the GUI's "Detect" action, independent of which
    BeatDetector produced the raw beat_times.

    Detectors sometimes lock onto double time (e.g. Beat This! on a busy
    rock mix); a fitted tempo above max_bpm is halved until it isn't.
    """
    from beatgrid.detection.transient import detect_transients, snap_to_nearest_transient

    transients = detect_transients(audio, sample_rate)
    refined_times = [
        snap_to_nearest_transient(t, transients, max_distance_sec=snap_tolerance_sec)
        for t in beat_times
    ]
    indices = _infer_beat_indices(refined_times)
    anchor_time, bpm = fit_anchor_and_bpm(refined_times, indices)
    while bpm > max_bpm and len(refined_times) >= 4:
        refined_times, indices = _halve_tempo(refined_times, indices, audio, sample_rate)
        anchor_time, bpm = fit_anchor_and_bpm(refined_times, indices)
    return anchor_time, bpm


def _halve_tempo(
    beat_times: Sequence[float], beat_indices: Sequence[int], audio: np.ndarray, sample_rate: int
) -> tuple[list[float], list[int]]:
    """Fold a double-time detection down to half tempo: keep every other
    beat, choosing the even- or odd-indexed half whose hits are louder (the
    real beats rather than the off-beats in between)."""
    window = max(1, int(round(_HIT_WINDOW_SEC * sample_rate)))

    def hit_level(t: float) -> float:
        start = max(0, int(round(t * sample_rate)))
        segment = audio[start : start + window]
        return float(np.max(np.abs(segment))) if len(segment) else 0.0

    halves = []
    for parity in (0, 1):
        kept = [(t, i) for t, i in zip(beat_times, beat_indices, strict=True) if i % 2 == parity]
        level = float(np.mean([hit_level(t) for t, _ in kept])) if kept else -1.0
        halves.append((level, kept))
    _level, kept = max(halves, key=lambda h: h[0])
    first_index = kept[0][1]
    return [t for t, _ in kept], [(i - first_index) // 2 for _, i in kept]


def _infer_beat_indices(beat_times: Sequence[float]) -> list[int]:
    """Beat indices robust to the detector occasionally dropping a beat (e.g.
    during a quiet section): naively assuming index == position in the list
    misaligns every later beat once one is missing. Instead, the median
    interval between consecutive detected beats estimates the true beat
    length, and each gap is rounded to the nearest whole number of beats."""
    if len(beat_times) < 2:
        return list(range(len(beat_times)))

    diffs = np.diff(beat_times)
    typical_interval = float(np.median(diffs))
    if typical_interval <= 0:
        return list(range(len(beat_times)))

    indices = [0]
    for diff in diffs:
        step = max(1, round(diff / typical_interval))
        indices.append(indices[-1] + step)
    return indices


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
