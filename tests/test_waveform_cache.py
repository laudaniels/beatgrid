import numpy as np

from beatgrid.audio.waveform_cache import build_waveform_cache


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
