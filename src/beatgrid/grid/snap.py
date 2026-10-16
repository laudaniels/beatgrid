from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from beatgrid.grid.model import Beat


def snap_offsets(
    beats: Sequence[Beat],
    transient_times: Sequence[float],
    *,
    max_distance_sec: float,
    skip_indices: frozenset[int] = frozenset(),
) -> dict[int, float]:
    """Per-beat offsets (beat index -> transient_time - beat_time) moving each
    beat onto its nearest transient, for beats that have one within
    max_distance_sec. Beats without a close transient, and those in
    skip_indices (e.g. the anchors themselves, which the user placed),
    are left out, i.e. stay on the constant-tempo grid."""
    if not transient_times:
        return {}
    transients = np.sort(np.asarray(transient_times, dtype=float))
    offsets: dict[int, float] = {}
    for beat in beats:
        if beat.index in skip_indices:
            continue
        i = int(np.searchsorted(transients, beat.time_sec))
        candidates = transients[max(0, i - 1) : i + 1]
        nearest = float(candidates[np.argmin(np.abs(candidates - beat.time_sec))])
        if abs(nearest - beat.time_sec) <= max_distance_sec:
            offsets[beat.index] = nearest - beat.time_sec
    return offsets
