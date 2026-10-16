from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class DetectionResult:
    bpm: float
    beat_times: list[float]  # seconds, in the analyzed audio's own timeline


class BeatDetector(Protocol):
    name: str

    def detect(self, audio: np.ndarray, sample_rate: int) -> DetectionResult: ...
