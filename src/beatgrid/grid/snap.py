from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from beatgrid.grid.model import Beat

# How much of the current drift carries over when a beat snaps: 0.5 averages
# the new beat's offset with the running drift, so one early/late hit doesn't
# throw off where the next beat is looked for.
DRIFT_SMOOTHING = 0.5


@dataclass(frozen=True)
class SnapResult:
    offsets: dict[int, float]  # beat index -> seconds; unlisted beats stay on the grid
    snapped: int  # how many of those landed on a transient


def snap_offsets(
    beats: Sequence[Beat],
    transient_times: Sequence[float],
    *,
    max_distance_sec: float,
    anchor_indices: frozenset[int] = frozenset(),
) -> SnapResult:
    """Per-beat offsets (beat index -> seconds) that make the grid follow
    the band: each beat is moved onto the nearest transient within
    `max_distance_sec` of where the band currently *is* -- its grid position
    plus the drift measured on the beats before it -- not of the fixed grid.

    A live band slowly drifting off one constant tempo (measured: +125 ms
    after 90 s on a real drum stem) would otherwise fall outside any sane
    tolerance, and the fixed grid then sits close to the *off-beats*
    instead, snapping beats onto the wrong hits. Beats without a transient
    nearby keep the current drift, so they move along too.

    Anchors (`anchor_indices`) are user-placed truths: they get no offset
    and reset the drift to zero for the beats after them.
    """
    transients = np.sort(np.asarray(transient_times, dtype=float))
    offsets: dict[int, float] = {}
    drift = 0.0
    snapped = 0
    for beat in sorted(beats, key=lambda b: b.index):
        if beat.index in anchor_indices:
            drift = 0.0
            continue
        expected = beat.time_sec + drift
        if len(transients):
            i = int(np.searchsorted(transients, expected))
            candidates = transients[max(0, i - 1) : i + 1]
            nearest = float(candidates[np.argmin(np.abs(candidates - expected))])
            if abs(nearest - expected) <= max_distance_sec:
                offset = nearest - beat.time_sec
                drift = DRIFT_SMOOTHING * drift + (1.0 - DRIFT_SMOOTHING) * offset
                offsets[beat.index] = offset
                snapped += 1
                continue
        if drift:
            offsets[beat.index] = drift
    return SnapResult(offsets=offsets, snapped=snapped)
