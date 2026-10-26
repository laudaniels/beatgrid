from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

Timemap = list[tuple[int, int]]

# Rubber Band's R3 engine follows a long timemap only approximately: over a
# whole song its output drifts off the keyframes (+15 ms after 8 min even at
# a constant ratio), and per-beat ratio changes (snapped beats) make it lose
# alignment that it never regains within the render. Rendering 64 beats at a
# time (2 beats of context either side) resets that: on a real snapped drum
# stem 89% of beats land within 5 ms (one pass: 67%), and rendering the
# chunks in parallel is ~10x faster than one pass. Smaller chunks weren't
# more precise on real stems but add seams.
CHUNK_KEYFRAMES = 64
MARGIN_KEYFRAMES = 2
# Seams are hard cuts at a common zero crossing (searched within this
# window), rounded off with a very short crossfade. A normal crossfade
# between two renders of the same audio dips in level wherever their phases
# differ (measured down to -12 dB on a bass tone); a bare hard cut left a
# click at ~14% of bass seams, which the 2 ms fade removes.
SPLICE_SEARCH_SEC = 0.01
SPLICE_FADE_SEC = 0.002


def stretch_in_chunks(
    audio: np.ndarray,
    sample_rate: int,
    timemap: Timemap,
    stretch: Callable[[np.ndarray, int, Timemap], np.ndarray],
    *,
    chunk_keyframes: int = CHUNK_KEYFRAMES,
    margin_keyframes: int = MARGIN_KEYFRAMES,
    splice_search_sec: float = SPLICE_SEARCH_SEC,
    splice_fade_sec: float = SPLICE_FADE_SEC,
    max_workers: int | None = None,
) -> np.ndarray:
    """Apply `stretch(audio, sample_rate, timemap)` piecewise, so a long
    timemap can't accumulate positional error inside the engine.

    The timemap is cut every `chunk_keyframes` keyframes, near the midpoint
    between two keyframes (between two beats). Each chunk is rendered with
    `margin_keyframes` extra keyframes of context on both sides -- using the
    *same* keyframes as its neighbour, so both renders put the audio around
    a seam in the same place -- and neighbouring chunks are joined at a
    common zero crossing (see SPLICE_*). Output length is exactly
    `timemap[-1][1]`, as for a single pass.
    """
    n = len(timemap)
    total = timemap[-1][1]
    if n <= chunk_keyframes + 2 * margin_keyframes:
        return _fit(stretch(audio, sample_rate, timemap), total)

    # seams: target-sample positions halfway between keyframes k and k+1
    seam_after = list(range(chunk_keyframes, n - 1 - margin_keyframes, chunk_keyframes))
    seams = [(timemap[k][1] + timemap[k + 1][1]) // 2 for k in seam_after]

    bounds = [0, *seam_after, n - 1]
    spans = [
        (max(0, bounds[i] - margin_keyframes), min(n - 1, bounds[i + 1] + 1 + margin_keyframes))
        for i in range(len(bounds) - 1)
    ]

    def render(span: tuple[int, int]) -> np.ndarray:
        lo, hi = span
        src0, tgt0 = timemap[lo]
        src1, tgt1 = timemap[hi]
        sub_map = [(s - src0, t - tgt0) for s, t in timemap[lo : hi + 1]]
        return _fit(stretch(audio[src0:src1], sample_rate, sub_map), tgt1 - tgt0)

    # chunks are independent; engines like Rubber Band run as a subprocess,
    # so threads parallelise them fine
    with ThreadPoolExecutor(max_workers=max_workers or os.cpu_count() or 1) as pool:
        pieces = list(pool.map(render, spans))
    starts = [timemap[lo][1] for lo, _hi in spans]

    window = max(1, int(round(splice_search_sec * sample_rate)))
    cuts = [
        _zero_crossing_cut(pieces[i], starts[i], pieces[i + 1], starts[i + 1], seam, window)
        for i, seam in enumerate(seams)
    ]

    out = np.zeros(total, dtype=np.float32)
    edges = [0, *cuts, total]
    for i, piece in enumerate(pieces):
        a, b = edges[i], edges[i + 1]
        out[a:b] = piece[a - starts[i] : b - starts[i]]

    # round off the remaining kink with a very short crossfade centred on
    # each cut: both renders are near zero there, so it can't cause a dip
    half = int(round(splice_fade_sec * sample_rate)) // 2
    for i, cut in enumerate(cuts):
        a, b = max(cut - half, starts[i + 1]), min(cut + half, starts[i] + len(pieces[i]))
        if b - a < 2:
            continue
        ramp = (np.arange(b - a, dtype=np.float32) + 0.5) / (b - a)
        left = pieces[i][a - starts[i] : b - starts[i]]
        right = pieces[i + 1][a - starts[i + 1] : b - starts[i + 1]]
        out[a:b] = left * (1.0 - ramp) + right * ramp
    return out


def _zero_crossing_cut(
    left: np.ndarray, left_start: int, right: np.ndarray, right_start: int, seam: int, window: int
) -> int:
    """The output sample within `window` of `seam` where switching from
    `left` to `right` is least audible: both renders close to zero *and*
    moving the same way, so the joined waveform has neither a jump nor a
    kink."""
    lo = max(seam - window, left_start, right_start)
    hi = min(seam + window, left_start + len(left) - 1, right_start + len(right) - 1)
    if hi <= lo:
        return seam
    a = left[lo - left_start : hi - left_start + 1].astype(np.float64)
    b = right[lo - right_start : hi - right_start + 1].astype(np.float64)
    scale = np.sqrt(np.mean(a**2) + np.mean(b**2)) + 1e-12
    cost = (np.abs(a[:-1]) + np.abs(b[:-1]) + np.abs(np.diff(a) - np.diff(b))) / scale
    return lo + int(np.argmin(cost))


def _fit(audio: np.ndarray, length: int) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if len(audio) >= length:
        return audio[:length]
    return np.pad(audio, (0, length - len(audio)))
