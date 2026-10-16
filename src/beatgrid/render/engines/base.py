from __future__ import annotations

from typing import Protocol

import numpy as np


class TimeStretcher(Protocol):
    """Constant-ratio engine (M8 prototype) — render/warp_renderer.py splits
    a track into segments and crossfades them back together around calls to
    this interface."""

    name: str

    def stretch(self, audio: np.ndarray, sample_rate: int, ratio: float) -> np.ndarray:
        """Time-stretch mono `audio` so its output duration is `ratio` times
        its input duration (ratio > 1 lengthens, ratio < 1 shortens),
        without changing pitch."""
        ...


class TimemapStretcher(Protocol):
    """Native piecewise-warp engine (M9 production) — one phase-continuous
    call per stem, no manual segmentation/crossfading. render/warp_renderer.py
    picks this path over TimeStretcher when an engine supports it."""

    name: str

    def stretch_with_timemap(
        self, audio: np.ndarray, sample_rate: int, timemap: list[tuple[int, int]]
    ) -> np.ndarray:
        """Time-stretch mono `audio` so each `(source_sample, target_sample)`
        keyframe in `timemap` lands where specified, interpolating
        phase-continuously in between. `timemap` must be sorted and
        non-decreasing in both elements, and its last entry's source must
        equal `len(audio)`."""
        ...
