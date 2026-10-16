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


def test_renumber_single_anchor_resets_to_zero():
    grid = BeatGrid(
        time_signature=TimeSignature(), anchors=[_anchor(5.0, 7, 120.0)], sample_rate=44100
    )
    grid.renumber_anchors()
    assert grid.anchors[0].beat_index == 0


def test_renumber_computes_elapsed_beats_between_anchors():
    # 120 BPM -> 0.5s/beat; anchor2 is 2.0s after anchor1 -> 4 beats elapsed
    grid = BeatGrid(
        time_signature=TimeSignature(),
        anchors=[
            _anchor(0.0, 99, 120.0, "a1"),  # stale beat_index, must be overwritten
            _anchor(2.0, 99, 100.0, "a2"),
        ],
        sample_rate=44100,
    )
    grid.renumber_anchors()

    assert grid.anchors[0].beat_index == 0
    assert grid.anchors[1].beat_index == 4


def test_renumber_resorts_anchors_by_time():
    grid = BeatGrid(
        time_signature=TimeSignature(),
        anchors=[_anchor(3.0, 0, 120.0, "late"), _anchor(0.0, 0, 120.0, "early")],
        sample_rate=44100,
    )
    grid.renumber_anchors()

    assert [a.id for a in grid.anchors] == ["early", "late"]
    assert grid.anchors[1].beat_index == 6  # 3.0s / 0.5s per beat


def test_renumber_clamps_minimum_one_beat_for_close_anchors():
    grid = BeatGrid(
        time_signature=TimeSignature(),
        anchors=[_anchor(0.0, 0, 120.0, "a1"), _anchor(0.01, 0, 120.0, "a2")],
        sample_rate=44100,
    )
    grid.renumber_anchors()

    assert grid.anchors[1].beat_index == 1


def test_generate_beats_no_collision_when_renumber_rounds_down():
    # anchor2 placed so elapsed-beat rounding rounds DOWN (23.25 -> 23); a
    # naive "while time_sec < segment_end" segment loop independently emits
    # one extra beat here, colliding with the next anchor's beat_index 23 —
    # a real collision found against real-world content, fixed by deriving
    # each segment's beat count directly from the anchors' beat_index gap.
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(0.0, 0, 150.0, "a1"), _anchor(9.3, 0, 150.0, "a2")],
        sample_rate=44100,
    )
    grid.renumber_anchors()
    assert grid.anchors[1].beat_index == 23

    beats = grid.generate_beats(end_time_sec=10.0)
    indices = [b.index for b in beats]

    assert indices == list(range(len(indices)))
    assert len(set(indices)) == len(indices)


def test_renumber_then_generate_beats_stays_continuous_after_insertion():
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(0.0, 0, 120.0, "a1"), _anchor(4.0, 8, 120.0, "a2")],
        sample_rate=44100,
    )
    # insert a new anchor in between, with a stale/placeholder beat_index
    grid.anchors.append(_anchor(2.0, 0, 120.0, "a3"))
    grid.renumber_anchors()

    beats = grid.generate_beats(end_time_sec=4.5)
    # still one beat every 0.5s throughout, no jump/duplicate at the insertion point
    assert [b.index for b in beats] == list(range(len(beats)))
    times = [round(b.time_sec, 3) for b in beats]
    assert times == sorted(times)
    assert all(round(b - a, 3) == 0.5 for a, b in zip(times, times[1:], strict=False))


def test_beat_offsets_nudge_individual_beats():
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(1.0, 0, 120.0)],
        sample_rate=44100,
        beat_offsets={1: 0.01, 3: -0.02},
    )
    beats = grid.generate_beats(end_time_sec=3.0)

    assert [b.time_sec for b in beats] == [1.0, 1.51, 2.0, 2.48]
    assert beats[1].sample_index == round(1.51 * 44100)
