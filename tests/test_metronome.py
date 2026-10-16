import numpy as np

from beatgrid.grid.model import Beat
from beatgrid.gui.playback.metronome import Metronome, build_metronome


def _beat(index, sample_index, is_downbeat):
    return Beat(
        index=index,
        time_sec=sample_index / 44100,
        sample_index=sample_index,
        bar=index // 4 + 1,
        beat_in_bar=index % 4 + 1,
        is_downbeat=is_downbeat,
    )


def test_build_metronome_splits_downbeats_from_regular_beats():
    beats = [
        _beat(0, 0, True),
        _beat(1, 22050, False),
        _beat(2, 44100, False),
        _beat(3, 66150, False),
    ]

    metronome = build_metronome(beats, sample_rate=44100)

    assert list(metronome.downbeat_samples) == [0]
    assert list(metronome.beat_samples) == [22050, 44100, 66150]
    assert len(metronome.beat_click) > 0
    assert len(metronome.downbeat_click) > 0


def test_mix_into_adds_click_at_exact_sample_offset():
    click = np.array([1.0, 0.5, 0.25], dtype=np.float32)
    metronome = Metronome(
        beat_click=click,
        downbeat_click=np.zeros(0, dtype=np.float32),
        beat_samples=np.array([10], dtype=np.int64),
        downbeat_samples=np.array([], dtype=np.int64),
        volume=1.0,
    )

    buffer = np.zeros(20, dtype=np.float32)
    metronome.mix_into(buffer, start_sample=0)

    expected = np.zeros(20, dtype=np.float32)
    expected[10:13] = click
    assert np.allclose(buffer, expected)


def test_mix_into_respects_volume():
    click = np.array([1.0], dtype=np.float32)
    metronome = Metronome(
        beat_click=click,
        downbeat_click=np.zeros(0, dtype=np.float32),
        beat_samples=np.array([0], dtype=np.int64),
        downbeat_samples=np.array([], dtype=np.int64),
        volume=0.5,
    )

    buffer = np.zeros(4, dtype=np.float32)
    metronome.mix_into(buffer, start_sample=0)

    assert buffer[0] == 0.5


def test_mix_into_handles_click_spanning_two_blocks():
    click = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    metronome = Metronome(
        beat_click=click,
        downbeat_click=np.zeros(0, dtype=np.float32),
        beat_samples=np.array([8], dtype=np.int64),
        downbeat_samples=np.array([], dtype=np.int64),
        volume=1.0,
    )

    # beat at sample 8, click is 4 samples long (8..11); split across two
    # 8-sample blocks: [0,8) and [8,16)
    block1 = np.zeros(8, dtype=np.float32)
    block2 = np.zeros(8, dtype=np.float32)
    metronome.mix_into(block1, start_sample=0)
    metronome.mix_into(block2, start_sample=8)

    assert np.allclose(block1, np.zeros(8))
    expected2 = np.zeros(8, dtype=np.float32)
    expected2[0:4] = click
    assert np.allclose(block2, expected2)


def test_mix_into_click_straddling_block_boundary_from_the_left():
    # beat at sample 6, click length 4 -> occupies [6, 10); a block starting
    # at 8 should still receive the tail of that click (samples [8,10))
    click = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    metronome = Metronome(
        beat_click=click,
        downbeat_click=np.zeros(0, dtype=np.float32),
        beat_samples=np.array([6], dtype=np.int64),
        downbeat_samples=np.array([], dtype=np.int64),
        volume=1.0,
    )

    block = np.zeros(8, dtype=np.float32)
    metronome.mix_into(block, start_sample=8)

    expected = np.zeros(8, dtype=np.float32)
    expected[0:2] = click[2:4]
    assert np.allclose(block, expected)
