from beatgrid.grid.model import Beat
from beatgrid.grid.snap import snap_offsets


def _beats(times):
    return [
        Beat(
            index=i,
            time_sec=t,
            sample_index=0,
            bar=1,
            beat_in_bar=i + 1,
            is_downbeat=i == 0,
        )
        for i, t in enumerate(times)
    ]


def test_snaps_beats_within_tolerance_on_either_side():
    beats = _beats([1.0, 1.5, 2.0])
    result = snap_offsets(beats, [1.0, 1.51, 1.98], max_distance_sec=0.03)
    assert result.snapped == 3
    assert abs(result.offsets[1] - 0.01) < 1e-9
    assert abs(result.offsets[2] + 0.02) < 1e-9


def test_follows_a_band_that_drifts_past_the_tolerance():
    # the band falls 10 ms further behind every beat (a 2% slower tempo): by
    # beat 20 it is 200 ms late, far outside the 40 ms tolerance around the
    # fixed grid
    grid = [i * 0.5 for i in range(21)]
    hits = [t + 0.010 * i for i, t in enumerate(grid)]
    # off-beat hits halfway, which a fixed grid would wrongly reach for
    offbeats = [t + 0.25 for t in hits]

    result = snap_offsets(_beats(grid), hits + offbeats, max_distance_sec=0.04)

    assert result.snapped == 21
    for i in range(1, 21):
        assert abs(result.offsets[i] - 0.010 * i) < 1e-9


def test_beats_without_a_hit_move_along_with_the_current_drift():
    beats = _beats([1.0, 1.5, 2.0, 2.5])
    # beats 0 and 1 are hit 20 ms late, beat 2 has no hit, beat 3 does again
    result = snap_offsets(beats, [1.02, 1.52, 2.52], max_distance_sec=0.04)

    assert result.snapped == 3
    drift_after_two = 0.5 * (0.5 * 0.0 + 0.5 * 0.02) + 0.5 * 0.02
    assert abs(result.offsets[2] - drift_after_two) < 1e-9
    assert abs(result.offsets[3] - 0.02) < 1e-9


def test_anchors_get_no_offset_and_reset_the_drift():
    beats = _beats([1.0, 1.5, 2.0, 2.5])
    result = snap_offsets(
        beats, [1.03, 1.53, 2.0, 2.53], max_distance_sec=0.04, anchor_indices=frozenset({2})
    )
    assert 2 not in result.offsets
    # after the anchor the search starts from the grid again, not from +30 ms
    assert abs(result.offsets[3] - 0.03) < 1e-9


def test_picks_nearest_of_two_close_transients():
    result = snap_offsets(_beats([1.0]), [0.98, 1.005, 1.02], max_distance_sec=0.03)
    assert abs(result.offsets[0] - 0.005) < 1e-9


def test_no_transients_gives_no_offsets():
    result = snap_offsets(_beats([1.0]), [], max_distance_sec=0.03)
    assert result.offsets == {} and result.snapped == 0
