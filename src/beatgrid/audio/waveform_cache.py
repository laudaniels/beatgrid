from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_BUCKET_SIZES = (16, 64, 256, 1024, 4096)


@dataclass(frozen=True)
class PeakLevel:
    bucket_size: int
    mins: np.ndarray
    maxs: np.ndarray


@dataclass(frozen=True)
class WaveformCache:
    sample_rate: int
    levels: list[PeakLevel]  # sorted by increasing bucket_size

    def level_for_samples_per_pixel(self, samples_per_pixel: float) -> PeakLevel:
        """The coarsest level whose bucket_size doesn't exceed samples_per_pixel
        (so a redraw touches roughly one bucket per screen pixel), falling back
        to the finest level when fully zoomed in."""
        candidates = [level for level in self.levels if level.bucket_size <= samples_per_pixel]
        return candidates[-1] if candidates else self.levels[0]


def level_to_xy(level: PeakLevel, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """A (xs, ys) pair ready for a `connect="pairs"` plot curve: one vertical
    min-to-max segment per bucket, centered on the bucket's time position —
    an efficient envelope rendering of a peak level (no need to touch
    individual samples)."""
    n = len(level.mins)
    if n == 0:
        return np.empty(0), np.empty(0)

    bucket_centers_sec = (np.arange(n) * level.bucket_size + level.bucket_size / 2) / sample_rate
    xs = np.repeat(bucket_centers_sec, 2)
    ys = np.empty(n * 2, dtype=np.float32)
    ys[0::2] = level.mins
    ys[1::2] = level.maxs
    return xs, ys


def build_waveform_cache(
    audio: np.ndarray,
    sample_rate: int,
    bucket_sizes: tuple[int, ...] = DEFAULT_BUCKET_SIZES,
) -> WaveformCache:
    levels = [_build_level(audio, size) for size in sorted(bucket_sizes)]
    return WaveformCache(sample_rate=sample_rate, levels=levels)


def _build_level(audio: np.ndarray, bucket_size: int) -> PeakLevel:
    n_buckets = len(audio) // bucket_size
    if n_buckets == 0:
        return PeakLevel(bucket_size=bucket_size, mins=audio.copy(), maxs=audio.copy())

    usable = audio[: n_buckets * bucket_size].reshape(n_buckets, bucket_size)
    mins = usable.min(axis=1)
    maxs = usable.max(axis=1)

    remainder = audio[n_buckets * bucket_size :]
    if len(remainder):
        mins = np.append(mins, remainder.min())
        maxs = np.append(maxs, remainder.max())

    return PeakLevel(bucket_size=bucket_size, mins=mins, maxs=maxs)
