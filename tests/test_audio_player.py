import numpy as np
import pytest

pytest.importorskip("sounddevice")

from beatgrid.gui.playback.audio_player import (  # noqa: E402
    AudioPlayer,
    PlaybackStem,
    read_stem_segment,
    select_active_stems,
)


def _stem(stem_id, audio, start_offset_sec=0.0, muted=False, solo=False):
    return PlaybackStem(
        stem_id=stem_id,
        audio=np.asarray(audio, dtype=np.float32),
        start_offset_sec=start_offset_sec,
        muted=muted,
        solo=solo,
    )


def test_select_active_stems_default_all_unmuted():
    stems = [_stem("a", [0]), _stem("b", [0], muted=True), _stem("c", [0])]
    assert [s.stem_id for s in select_active_stems(stems)] == ["a", "c"]


def test_select_active_stems_solo_overrides_everything_else():
    stems = [_stem("a", [0]), _stem("b", [0], solo=True), _stem("c", [0], muted=True)]
    assert [s.stem_id for s in select_active_stems(stems)] == ["b"]


def test_read_stem_segment_no_offset():
    stem = _stem("a", np.arange(10, dtype=np.float32))
    segment = read_stem_segment(stem, project_start=2, project_end=6, sample_rate=1)
    assert np.array_equal(segment, [2, 3, 4, 5])


def test_read_stem_segment_with_positive_offset():
    # stem's own t=0 is at project sample 5 -> project sample 7 reads stem[2]
    stem = _stem("a", np.arange(10, dtype=np.float32), start_offset_sec=5.0)
    segment = read_stem_segment(stem, project_start=5, project_end=9, sample_rate=1)
    assert np.array_equal(segment, [0, 1, 2, 3])


def test_read_stem_segment_before_stem_starts_is_silence():
    stem = _stem("a", np.arange(10, dtype=np.float32), start_offset_sec=5.0)
    segment = read_stem_segment(stem, project_start=0, project_end=4, sample_rate=1)
    assert np.array_equal(segment, [0, 0, 0, 0])


def test_read_stem_segment_partially_overlapping_start():
    stem = _stem("a", np.arange(10, dtype=np.float32), start_offset_sec=5.0)
    # project samples [3, 8) -> stem samples [-2, 3) -> first 2 silent, then stem[0:3]
    segment = read_stem_segment(stem, project_start=3, project_end=8, sample_rate=1)
    assert np.array_equal(segment, [0, 0, 0, 1, 2])


def test_read_stem_segment_past_stem_end_is_silence():
    stem = _stem("a", np.arange(5, dtype=np.float32))
    segment = read_stem_segment(stem, project_start=3, project_end=8, sample_rate=1)
    assert np.array_equal(segment, [3, 4, 0, 0, 0])


def test_render_block_mixes_unmuted_stems():
    player = AudioPlayer(sample_rate=1)
    player.set_stems(
        [
            _stem("a", [1.0, 1.0, 1.0, 1.0]),
            _stem("b", [0.5, 0.5, 0.5, 0.5], muted=True),
            _stem("c", [0.25, 0.25, 0.25, 0.25]),
        ]
    )

    block = player.render_block(4)

    assert np.allclose(block, [1.25, 1.25, 1.25, 1.25])


def test_render_block_advances_position():
    player = AudioPlayer(sample_rate=10)
    player.set_stems([_stem("a", np.zeros(100))])

    assert player.position_sec == 0.0
    player.render_block(5)
    assert player.position_sec == 0.5
    player.render_block(5)
    assert player.position_sec == 1.0


def test_seek_sets_position():
    player = AudioPlayer(sample_rate=10)
    player.seek(2.5)
    assert player.position_sec == 2.5


def test_render_block_returns_none_past_duration():
    player = AudioPlayer(sample_rate=10)
    player.set_stems([_stem("a", np.zeros(100))])
    player.set_duration(1.0)

    player.seek(0.9)
    assert player.render_block(1) is not None  # still before 1.0s
    player.seek(1.0)
    assert player.render_block(1) is None


def test_render_block_includes_metronome():
    from beatgrid.gui.playback.metronome import Metronome

    player = AudioPlayer(sample_rate=1)
    player.set_stems([])
    player.set_metronome(
        Metronome(
            beat_click=np.array([1.0], dtype=np.float32),
            downbeat_click=np.zeros(0, dtype=np.float32),
            beat_samples=np.array([2], dtype=np.int64),
            downbeat_samples=np.array([], dtype=np.int64),
        )
    )

    block = player.render_block(4)

    assert np.allclose(block, [0.0, 0.0, 0.6, 0.0])
