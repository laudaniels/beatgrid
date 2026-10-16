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
    offsets = snap_offsets(beats, [1.51, 1.98], max_distance_sec=0.03)
    assert offsets.keys() == {1, 2}
    assert abs(offsets[1] - 0.01) < 1e-9
    assert abs(offsets[2] + 0.02) < 1e-9


def test_beats_without_close_transient_and_skipped_indices_stay_put():
    beats = _beats([1.0, 1.5, 2.0])
    offsets = snap_offsets(
        beats, [1.01, 1.55, 2.01], max_distance_sec=0.03, skip_indices=frozenset({0})
    )
    assert offsets.keys() == {2}  # 0 skipped, 1 is 50 ms off


def test_picks_nearest_of_two_close_transients():
    beats = _beats([1.0])
    assert snap_offsets(beats, [0.98, 1.005, 1.02], max_distance_sec=0.03) == {
        0: snap_offsets(beats, [1.005], max_distance_sec=0.03)[0]
    }


def test_no_transients_gives_no_offsets():
    assert snap_offsets(_beats([1.0]), [], max_distance_sec=0.03) == {}
