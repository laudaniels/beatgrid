from __future__ import annotations

import numpy as np


class PedalboardStretcher:
    """M8 prototype time-stretch engine (pedalboard.time_stretch), operating
    on one already-split segment at a constant ratio — render/warp_renderer.py
    handles splitting a track into per-anchor segments and crossfading them
    back together.

    See PLAN.md's license trade-off for why this stays the *prototype*
    engine: Pedalboard is GPL-3.0 as a whole (it statically bundles Rubber
    Band, FFTW and JUCE), unlike the planned M9 production engine
    (pyrubberband, which shells out to a separately-installed system binary
    — lower GPL exposure for our own code — and supports a native timemap
    for genuinely continuous piecewise warping instead of segment+crossfade).
    """

    name = "pedalboard"

    def stretch(self, audio: np.ndarray, sample_rate: int, ratio: float) -> np.ndarray:
        if ratio <= 0:
            raise ValueError(f"ratio must be positive, got {ratio}")

        import pedalboard

        # pedalboard.time_stretch expects (channels, samples) and a
        # stretch_factor that's the *inverse* of our ratio convention: a
        # higher stretch_factor means a SHORTER (faster) output, whereas our
        # `ratio` is output_duration / input_duration.
        stretched = pedalboard.time_stretch(
            audio.reshape(1, -1).astype(np.float32),
            float(sample_rate),
            stretch_factor=1.0 / ratio,
            high_quality=True,
        )
        return np.asarray(stretched, dtype=np.float32).reshape(-1)
