"""Synthetic audio generators for tests. No real/copyrighted audio in this repo."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ClickTrack:
    audio: np.ndarray
    sample_rate: int
    beat_times: list[float]


def _click_burst(sample_rate: int, duration_sec: float, freq: float) -> np.ndarray:
    n = int(round(duration_sec * sample_rate))
    t = np.arange(n) / sample_rate
    envelope = np.exp(-t * 40.0)
    return (np.sin(2 * np.pi * freq * t) * envelope).astype(np.float32)


def make_click_track(
    bpm: float,
    duration_sec: float,
    sample_rate: int = 44100,
    *,
    start_offset_sec: float = 0.0,
    click_freq: float = 1000.0,
    click_duration_sec: float = 0.03,
    amplitude: float = 0.8,
    noise_level: float = 0.0,
    seed: int | None = None,
) -> ClickTrack:
    """A synthetic click track at a constant BPM, with known ground-truth beat times."""
    n_samples = int(round(duration_sec * sample_rate))
    audio = np.zeros(n_samples, dtype=np.float32)
    burst = _click_burst(sample_rate, click_duration_sec, click_freq) * amplitude

    beat_interval = 60.0 / bpm
    beat_times: list[float] = []
    t = start_offset_sec
    while t < duration_sec:
        beat_times.append(t)
        start = int(round(t * sample_rate))
        audio_start = max(start, 0)
        audio_end = min(start + len(burst), n_samples)
        if audio_end > audio_start:
            burst_start = audio_start - start
            audio[audio_start:audio_end] += burst[
                burst_start : burst_start + (audio_end - audio_start)
            ]
        t += beat_interval

    if noise_level:
        rng = np.random.default_rng(seed)
        audio += rng.normal(0.0, noise_level, size=n_samples).astype(np.float32)

    return ClickTrack(audio=audio, sample_rate=sample_rate, beat_times=beat_times)


def make_stem_set(
    bpm: float,
    duration_sec: float,
    n_stems: int = 2,
    sample_rate: int = 44100,
    *,
    offsets_sec: list[float] | None = None,
    noise_level: float = 0.01,
    seed: int = 0,
) -> list[ClickTrack]:
    """Multiple synthetic stems sharing one underlying beat grid, each with its own
    start offset and independent noise — for testing validation/offset-detection."""
    offsets = offsets_sec if offsets_sec is not None else [0.0] * n_stems
    if len(offsets) != n_stems:
        raise ValueError("offsets_sec must have exactly n_stems entries")

    rng = np.random.default_rng(seed)
    return [
        make_click_track(
            bpm,
            duration_sec,
            sample_rate,
            start_offset_sec=offset,
            noise_level=noise_level,
            seed=int(rng.integers(0, 2**31 - 1)),
        )
        for offset in offsets
    ]
