import numpy as np
import pytest

from beatgrid.render.chunked_timemap import _zero_crossing_cut, stretch_in_chunks


def _exact_stretch(audio, sample_rate, timemap):
    """A position-exact fake engine: every output sample reads the input at
    the timemap's (linearly interpolated) source position."""
    sources, targets = zip(*timemap, strict=True)
    positions = np.interp(np.arange(targets[-1]), targets, sources)
    return np.interp(positions, np.arange(len(audio)), audio).astype(np.float32)


def _live_timemap(n_beats=150, sample_rate=8000, seed=0):
    rng = np.random.default_rng(seed)
    interval = 0.5 * sample_rate
    sources = np.cumsum(interval + rng.uniform(-0.06, 0.06, n_beats) * sample_rate).astype(int)
    targets = sources[0] + np.round(np.arange(n_beats) * 0.49 * sample_rate).astype(int)
    length = int(sources[-1] + sample_rate)
    timemap = [(0, 0)] + list(zip(sources.tolist(), targets.tolist(), strict=True))
    timemap.append((length, timemap[-1][1] + length - timemap[-1][0]))
    return timemap, length


def test_chunked_output_matches_single_pass_for_an_exact_engine():
    sample_rate = 8000
    timemap, length = _live_timemap(sample_rate=sample_rate)
    audio = np.random.default_rng(1).standard_normal(length).astype(np.float32)

    single = _exact_stretch(audio, sample_rate, timemap)
    chunked = stretch_in_chunks(audio, sample_rate, timemap, _exact_stretch, chunk_keyframes=16)

    assert len(chunked) == timemap[-1][1] == len(single)
    np.testing.assert_allclose(chunked, single, atol=1e-5)


def test_each_chunk_gets_margin_context_and_short_timemaps():
    sample_rate = 8000
    timemap, length = _live_timemap(sample_rate=sample_rate)
    audio = np.zeros(length, dtype=np.float32)
    calls = []

    def spy(chunk_audio, sr, sub_map):
        calls.append(sub_map)
        assert sub_map[0] == (0, 0)
        assert sub_map[-1][0] == len(chunk_audio)
        return _exact_stretch(chunk_audio, sr, sub_map)

    stretch_in_chunks(audio, sample_rate, timemap, spy, chunk_keyframes=16, margin_keyframes=2)

    assert len(calls) == pytest.approx(len(timemap) / 16, abs=1)
    assert max(len(m) for m in calls) <= 16 + 1 + 2 * 2 + 1


def test_short_timemap_is_a_single_pass():
    calls = []

    def spy(chunk_audio, sr, sub_map):
        calls.append(sub_map)
        return _exact_stretch(chunk_audio, sr, sub_map)

    timemap = [(0, 0), (4000, 3900), (8000, 7900)]
    stretch_in_chunks(np.zeros(8000, dtype=np.float32), 8000, timemap, spy)
    assert calls == [timemap]


def test_cut_lands_where_both_renders_cross_zero_the_same_way():
    sample_rate = 8000
    t = np.arange(400) / sample_rate
    # same 100 Hz tone, the right render lagging a little in phase
    left = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    right = np.sin(2 * np.pi * 100 * t - 0.3).astype(np.float32)

    cut = _zero_crossing_cut(left, 0, right, 0, seam=200, window=60)

    assert abs(cut - 200) <= 60
    # the renders never cross zero together (0.3 rad apart); the cut is the
    # best compromise in the window, with both moving the same way
    near_zero = np.abs(left[140:261]) + np.abs(right[140:261])
    assert abs(left[cut]) + abs(right[cut]) <= near_zero.min() + 0.05
    assert np.sign(left[cut + 1] - left[cut]) == np.sign(right[cut + 1] - right[cut])


def test_splices_have_no_level_dip_even_when_renders_differ_in_phase():
    """Each chunk render here has a different, arbitrary phase -- the case
    where a plain crossfade would dip -- yet the output keeps its level."""
    sample_rate = 8000
    timemap, length = _live_timemap(n_beats=150, sample_rate=sample_rate)
    rng = np.random.default_rng(2)

    def phase_shifting_stretch(audio, sr, sub_map):
        n = sub_map[-1][1]
        return (
            0.5 * np.sin(2 * np.pi * 110 * np.arange(n) / sr + rng.uniform(0, 2 * np.pi))
        ).astype(np.float32)

    out = stretch_in_chunks(
        np.zeros(length, dtype=np.float32),
        sample_rate,
        timemap,
        phase_shifting_stretch,
        chunk_keyframes=16,
    )
    window = int(0.02 * sample_rate)
    levels = [
        np.sqrt(np.mean(out[i : i + window] ** 2)) for i in range(0, len(out) - window, window)
    ]
    assert min(levels) > 0.5 / np.sqrt(2) * 0.8  # never more than ~2 dB below a steady tone
