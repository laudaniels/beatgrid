from beatgrid.grid.model import Anchor, BeatGrid, TimeSignature


def _anchor(time_sec, beat_index, bpm, anchor_id="a"):
    return Anchor(
        id=anchor_id,
        time_sec=time_sec,
        sample_index=round(time_sec * 44100),
        beat_index=beat_index,
        bpm=bpm,
    )


def test_single_anchor_constant_tempo():
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(1.0, 0, 120.0)],
        sample_rate=44100,
    )
    beats = grid.generate_beats(end_time_sec=3.0)

    assert [b.time_sec for b in beats] == [1.0, 1.5, 2.0, 2.5]
    assert [b.index for b in beats] == [0, 1, 2, 3]
    assert [b.bar for b in beats] == [1, 1, 1, 1]
    assert [b.beat_in_bar for b in beats] == [1, 2, 3, 4]
    assert [b.is_downbeat for b in beats] == [True, False, False, False]
    assert beats[0].sample_index == 44100


def test_downbeat_rolls_over_into_next_bar():
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(0.0, 0, 120.0)],
        sample_rate=44100,
    )
    beats = grid.generate_beats(end_time_sec=3.0)  # indices 0..5

    assert [b.bar for b in beats] == [1, 1, 1, 1, 2, 2]
    assert [b.beat_in_bar for b in beats] == [1, 2, 3, 4, 1, 2]
    assert [b.is_downbeat for b in beats] == [True, False, False, False, True, False]


def test_multi_anchor_tempo_drift_segment_boundaries():
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[
            _anchor(0.0, 0, 120.0, "a1"),  # 0.5s/beat until the re-pin
            _anchor(2.0, 4, 100.0, "a2"),  # re-pin at beat 4, 0.6s/beat afterwards
        ],
        sample_rate=44100,
    )
    beats = grid.generate_beats(end_time_sec=3.2)

    assert [round(b.time_sec, 3) for b in beats] == [0.0, 0.5, 1.0, 1.5, 2.0, 2.6]
    assert [b.index for b in beats] == [0, 1, 2, 3, 4, 5]


def test_empty_grid_has_no_beats():
    grid = BeatGrid(time_signature=TimeSignature(), anchors=[], sample_rate=44100)
    assert grid.generate_beats(end_time_sec=10.0) == []
