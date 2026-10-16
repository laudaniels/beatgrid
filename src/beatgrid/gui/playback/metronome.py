from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from beatgrid.grid.model import Beat

BEAT_CLICK_FREQ_HZ = 1000.0
DOWNBEAT_CLICK_FREQ_HZ = 1800.0
CLICK_DURATION_SEC = 0.02


@dataclass
class Metronome:
    """Sample-accurate metronome click, mixed directly into an output block
    at the exact sample offset of each beat — not scheduled via a timer, so
    it's independent of OS/GUI-thread jitter."""

    beat_click: np.ndarray
    downbeat_click: np.ndarray
    beat_samples: np.ndarray  # project-sample positions of non-downbeats
    downbeat_samples: np.ndarray  # project-sample positions of downbeats
    volume: float = 0.6

    def mix_into(self, buffer: np.ndarray, start_sample: int) -> None:
        """Add click audio for every beat overlapping
        [start_sample, start_sample + len(buffer)) into `buffer` in place."""
        self._mix_clicks(buffer, start_sample, self.beat_samples, self.beat_click)
        self._mix_clicks(buffer, start_sample, self.downbeat_samples, self.downbeat_click)

    def _mix_clicks(
        self, buffer: np.ndarray, start_sample: int, positions: np.ndarray, click: np.ndarray
    ) -> None:
        end_sample = start_sample + len(buffer)
        # a click starting just before start_sample can still overlap this block
        lo = np.searchsorted(positions, start_sample - len(click), side="left")
        hi = np.searchsorted(positions, end_sample, side="left")

        for beat_sample in positions[lo:hi]:
            click_start = int(beat_sample) - start_sample
            out_start = max(0, click_start)
            out_end = min(len(buffer), click_start + len(click))
            if out_end <= out_start:
                continue
            click_offset = out_start - click_start
            length = out_end - out_start
            buffer[out_start:out_end] += click[click_offset : click_offset + length] * self.volume


def build_metronome(
    beats: list[Beat],
    sample_rate: int,
    *,
    beat_click_freq: float = BEAT_CLICK_FREQ_HZ,
    downbeat_click_freq: float = DOWNBEAT_CLICK_FREQ_HZ,
    click_duration_sec: float = CLICK_DURATION_SEC,
    volume: float = 0.6,
) -> Metronome:
    beat_samples = np.array([b.sample_index for b in beats if not b.is_downbeat], dtype=np.int64)
    downbeat_samples = np.array([b.sample_index for b in beats if b.is_downbeat], dtype=np.int64)
    return Metronome(
        beat_click=_make_click(sample_rate, click_duration_sec, beat_click_freq),
        downbeat_click=_make_click(sample_rate, click_duration_sec, downbeat_click_freq),
        beat_samples=beat_samples,
        downbeat_samples=downbeat_samples,
        volume=volume,
    )


def _make_click(sample_rate: int, duration_sec: float, freq: float) -> np.ndarray:
    n = int(round(duration_sec * sample_rate))
    t = np.arange(n) / sample_rate
    envelope = np.exp(-t * 60.0)
    return (np.sin(2 * np.pi * freq * t) * envelope).astype(np.float32)
