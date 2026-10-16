import numpy as np

from beatgrid.audio.waveform_cache import build_waveform_cache, level_to_xy, samples_to_xy


def test_level_matches_manual_min_max():
    audio = np.arange(1000, dtype=np.float32)
    cache = build_waveform_cache(audio, sample_rate=44100, bucket_sizes=(10,))
    level = cache.levels[0]

    expected_mins = audio.reshape(100, 10).min(axis=1)
    expected_maxs = audio.reshape(100, 10).max(axis=1)
    assert np.array_equal(level.mins, expected_mins)
    assert np.array_equal(level.maxs, expected_maxs)


def test_remainder_samples_become_final_partial_bucket():
    audio = np.arange(25, dtype=np.float32)
    cache = build_waveform_cache(audio, sample_rate=44100, bucket_sizes=(10,))
    level = cache.levels[0]

    # 2 full buckets of 10 + a partial bucket of 5 remaining samples
    assert len(level.mins) == 3
    assert level.maxs[-1] == 24
    assert level.mins[-1] == 20


def test_level_for_samples_per_pixel_picks_coarsest_fitting_level():
    audio = np.random.default_rng(0).normal(size=10000).astype(np.float32)
    cache = build_waveform_cache(audio, sample_rate=44100, bucket_sizes=(16, 64, 256))

    assert cache.level_for_samples_per_pixel(5).bucket_size == 16
    assert cache.level_for_samples_per_pixel(100).bucket_size == 64
    assert cache.level_for_samples_per_pixel(1000).bucket_size == 256


def test_levels_sorted_by_bucket_size():
    audio = np.zeros(100, dtype=np.float32)
    cache = build_waveform_cache(audio, sample_rate=44100, bucket_sizes=(256, 16, 64))
    assert [level.bucket_size for level in cache.levels] == [16, 64, 256]


def test_level_to_xy_produces_one_vertical_segment_per_bucket():
    audio = np.arange(20, dtype=np.float32)
    cache = build_waveform_cache(audio, sample_rate=10, bucket_sizes=(10,))
    level = cache.levels[0]

    xs, ys = level_to_xy(level, sample_rate=10)

    assert len(xs) == len(ys) == 4  # 2 buckets x 2 points (min, max) each
    # bucket 0 covers samples [0,10) -> center at sample 5 -> 0.5s
    assert xs[0] == xs[1] == 0.5
    assert (ys[0], ys[1]) == (0.0, 9.0)
    # bucket 1 covers samples [10,20) -> center at sample 15 -> 1.5s
    assert xs[2] == xs[3] == 1.5
    assert (ys[2], ys[3]) == (10.0, 19.0)


def test_level_to_xy_empty_level():
    xs, ys = level_to_xy(
        build_waveform_cache(np.zeros(0, dtype=np.float32), 44100).levels[0], 44100
    )
    assert len(xs) == 0
    assert len(ys) == 0


def test_cache_records_whole_file_peak():
    audio = np.array([0.1, -0.8, 0.5], dtype=np.float32)
    cache = build_waveform_cache(audio, sample_rate=44100, bucket_sizes=(2,))
    assert cache.peak == np.float32(0.8)


def test_samples_to_xy_clamps_to_audio_bounds():
    audio = np.arange(10, dtype=np.float32)
    xs, ys = samples_to_xy(audio, sample_rate=10, start_sample=-3, end_sample=4)
    assert np.array_equal(ys, [0, 1, 2, 3])
    assert np.allclose(xs, [0.0, 0.1, 0.2, 0.3])
