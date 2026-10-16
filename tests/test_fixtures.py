import numpy as np
from fixtures import make_click_track, make_stem_set


def test_make_click_track_beat_count_and_spacing():
    track = make_click_track(bpm=120.0, duration_sec=4.0, sample_rate=8000)

    assert track.sample_rate == 8000
    assert track.audio.dtype == np.float32
    assert len(track.audio) == 4.0 * 8000

    # 120 BPM -> one beat every 0.5s -> beats at 0.0, 0.5, 1.0, ... < 4.0
    assert track.beat_times[:3] == [0.0, 0.5, 1.0]
    spacings = np.diff(track.beat_times)
    assert np.allclose(spacings, 0.5)


def test_make_click_track_start_offset():
    track = make_click_track(bpm=100.0, duration_sec=2.0, sample_rate=8000, start_offset_sec=0.3)

    assert track.beat_times[0] == 0.3


def test_make_stem_set_shares_grid_with_independent_offsets():
    offsets = [0.0, 0.05, -0.02]
    stems = make_stem_set(
        bpm=128.0, duration_sec=3.0, n_stems=3, sample_rate=8000, offsets_sec=offsets
    )

    assert len(stems) == 3
    for stem, offset in zip(stems, offsets, strict=True):
        assert stem.beat_times[0] == offset
        # same tempo -> same beat spacing across all stems
        assert np.allclose(np.diff(stem.beat_times), 60.0 / 128.0)
