from __future__ import annotations

from typing import Protocol

import numpy as np


class TimeStretcher(Protocol):
    name: str

    def stretch(self, audio: np.ndarray, sample_rate: int, ratio: float) -> np.ndarray:
        """Time-stretch mono `audio` so its output duration is `ratio` times
        its input duration (ratio > 1 lengthens, ratio < 1 shortens),
        without changing pitch."""
        ...
