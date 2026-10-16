from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


def detect_transients(
    audio: np.ndarray,
    sample_rate: int,
    *,
    refine_window_sec: float = 0.015,
    min_gap_sec: float = 0.05,
) -> list[float]:
    """Sample-precise transient (onset) times in seconds.

    librosa's onset detector gives a frame-accurate estimate (hop-length
    resolution, ~11ms by default); each one is refined to the sample with
    the steepest local rise in amplitude nearby, independent of whichever
    detector produced the raw beat proposal.

    No librosa backtracking: it moves each onset back to the preceding
    energy minimum, which inside a decaying tom/cymbal or a quiet stretch
    lies tens of ms before the actual attack (~50 ms on real drum stems).
    A single hit can still yield a second onset a few frames into its
    body; any transient within min_gap_sec after the previous kept one is
    dropped, so each hit is represented by its attack only.
    """
    import librosa

    coarse_times = librosa.onset.onset_detect(y=audio, sr=sample_rate, units="time")
    refined = sorted(
        _refine_to_sample(audio, sample_rate, float(t), window_sec=refine_window_sec)
        for t in coarse_times
    )
    kept: list[float] = []
    for t in refined:
        if not kept or t - kept[-1] >= min_gap_sec:
            kept.append(t)
    return kept


_RISE_WINDOW_SEC = 0.002


def _refine_to_sample(
    audio: np.ndarray,
    sample_rate: int,
    approx_time_sec: float,
    *,
    window_sec: float,
) -> float:
    center = int(round(approx_time_sec * sample_rate))
    half_window = max(1, int(round(window_sec * sample_rate)))
    start = max(0, center - half_window)
    end = min(len(audio), center + half_window)
    # Ratio of the mean level just after vs. just before each candidate
    # sample: a single sample-to-sample jump is almost random on noisy
    # attacks (snare, cymbal), and an absolute difference peaks somewhere
    # inside a loud hit's body rather than at the jump out of the quiet
    # before it. The ratio peaks at the onset itself.
    w = max(1, int(round(_RISE_WINDOW_SEC * sample_rate)))
    lo = max(0, start - w)
    hi = min(len(audio), end + w)
    if hi - lo < 2 * w + 1:
        return approx_time_sec
    csum = np.concatenate(([0.0], np.cumsum(np.abs(audio[lo:hi]), dtype=np.float64)))
    candidates = np.arange(max(start, lo + w), min(end, hi - w))
    if len(candidates) == 0:
        return approx_time_sec
    rel = candidates - lo
    after = csum[rel + w] - csum[rel]
    before = csum[rel] - csum[rel - w]
    eps = 1e-4 * w  # ~-80 dBFS floor so digital silence doesn't divide by zero
    return int(candidates[np.argmax((after + eps) / (before + eps))]) / sample_rate


def snap_to_nearest_transient(
    time_sec: float,
    transient_times: list[float],
    *,
    max_distance_sec: float = 0.05,
) -> float:
    """The nearest transient to `time_sec` if within max_distance_sec,
    otherwise `time_sec` unchanged. Takes a precomputed transient list so
    callers (e.g. live drag-snapping) don't re-run detection per call."""
    if not transient_times:
        return time_sec
    transients = np.asarray(transient_times)
    nearest = float(transients[np.argmin(np.abs(transients - time_sec))])
    return nearest if abs(nearest - time_sec) <= max_distance_sec else time_sec


@dataclass(frozen=True)
class DriftPoint:
    time_sec: float
    deviation_sec: float  # signed: transient_time - nearest_grid_time
    is_drifting: bool


def compute_drift(
    transient_times: Sequence[float],
    grid_beat_times: Sequence[float],
    *,
    threshold_sec: float = 0.02,
) -> list[DriftPoint]:
    """For each transient, the signed deviation from the nearest grid beat
    time, flagged when it exceeds threshold_sec.

    Purely diagnostic — this never adjusts the grid or the transient; it's
    how a stem visibly "breathing" off the shared grid (e.g. a live bass)
    gets surfaced without auto-correction.
    """
    if not grid_beat_times:
        return [
            DriftPoint(time_sec=t, deviation_sec=0.0, is_drifting=False) for t in transient_times
        ]

    grid = np.asarray(grid_beat_times)
    points = []
    for t in transient_times:
        nearest = float(grid[np.argmin(np.abs(grid - t))])
        deviation = t - nearest
        points.append(
            DriftPoint(
                time_sec=t, deviation_sec=deviation, is_drifting=abs(deviation) > threshold_sec
            )
        )
    return points
