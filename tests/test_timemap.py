from pathlib import Path

import pytest

from beatgrid.grid.model import Beat
from beatgrid.project.models import Stem
from beatgrid.render.timemap import build_timemap


def _beat(index, time_sec, sample_rate=44100):
    return Beat(
        index=index,
        time_sec=time_sec,
        sample_index=round(time_sec * sample_rate),
        bar=index // 4 + 1,
        beat_in_bar=index % 4 + 1,
        is_downbeat=index % 4 == 0,
    )


def _stem(sample_rate=44100, start_offset_sec=0.0):
    return Stem(
        id="s", path=Path("s.wav"), sample_rate=sample_rate, start_offset_sec=start_offset_sec
    )


def test_first_beat_position_is_unchanged():
    sample_rate = 44100
    beats = [_beat(0, 1.0, sample_rate), _beat(1, 1.5, sample_rate), _beat(2, 2.0, sample_rate)]
    stem = _stem(sample_rate)
    total_samples = round(3.0 * sample_rate)

    timemap = build_timemap(beats, stem, sample_rate, target_bpm=120.0, total_samples=total_samples)

    first_source = round(1.0 * sample_rate)
    assert timemap[0] == (0, 0)
    assert timemap[1] == (first_source, first_source)


def test_later_beats_land_at_ideal_target_tempo_spacing():
    sample_rate = 44100
    bpm_measured = 118.0  # slightly off from the target -> real-world jitter
    interval_measured = 60.0 / bpm_measured
    beats = [_beat(i, 1.0 + i * interval_measured, sample_rate) for i in range(5)]
    stem = _stem(sample_rate)
    total_samples = round(5.0 * sample_rate)
    target_bpm = 120.0

    timemap = build_timemap(beats, stem, sample_rate, target_bpm, total_samples)

    first_source = round(1.0 * sample_rate)
    ideal_interval_samples = 60.0 / target_bpm * sample_rate
    beat_keyframes = timemap[1 : 1 + len(beats)]
    for i, (_src, tgt) in enumerate(beat_keyframes):
        assert tgt == round(first_source + i * ideal_interval_samples)


def test_appends_tail_keyframe_to_total_samples():
    sample_rate = 44100
    beats = [_beat(0, 0.0, sample_rate), _beat(1, 0.5, sample_rate)]
    stem = _stem(sample_rate)
    total_samples = round(2.0 * sample_rate)

    timemap = build_timemap(beats, stem, sample_rate, target_bpm=120.0, total_samples=total_samples)

    assert timemap[-1][0] == total_samples


def test_no_duplicate_lead_in_when_first_beat_already_at_zero():
    sample_rate = 44100
    beats = [_beat(0, 0.0, sample_rate), _beat(1, 0.5, sample_rate)]
    stem = _stem(sample_rate)
    total_samples = round(1.0 * sample_rate)

    timemap = build_timemap(beats, stem, sample_rate, target_bpm=120.0, total_samples=total_samples)

    assert timemap[0] == (0, 0)  # the first beat's own keyframe, not an extra lead-in
    assert len(timemap) == 3  # beat0, beat1, tail


def test_is_monotonic_non_decreasing():
    sample_rate = 44100
    beats = [_beat(i, i * 0.4, sample_rate) for i in range(10)]
    stem = _stem(sample_rate, start_offset_sec=0.1)
    total_samples = round(4.0 * sample_rate)

    timemap = build_timemap(beats, stem, sample_rate, target_bpm=130.0, total_samples=total_samples)

    for (s0, t0), (s1, t1) in zip(timemap, timemap[1:], strict=False):
        assert s1 >= s0
        assert t1 >= t0
    assert timemap[-1][0] == total_samples


def test_requires_at_least_one_beat():
    with pytest.raises(ValueError):
        build_timemap([], _stem(), 44100, 120.0, 44100)


def test_handles_stem_start_offset():
    sample_rate = 44100
    beats = [_beat(0, 1.0, sample_rate), _beat(1, 1.5, sample_rate)]
    stem = _stem(sample_rate, start_offset_sec=0.2)  # stem's own t=0 is 0.2s into the project
    total_samples = round(2.0 * sample_rate)

    timemap = build_timemap(beats, stem, sample_rate, target_bpm=120.0, total_samples=total_samples)

    expected_first_source = round(0.8 * sample_rate)  # project time 1.0 -> stem-local 0.8
    assert timemap[0] == (0, 0)
    assert timemap[1][0] == expected_first_source


def test_short_stem_with_all_beats_beyond_its_audio_is_left_unstretched():
    sample_rate = 44100
    beats = [_beat(0, 5.0, sample_rate), _beat(1, 5.5, sample_rate)]
    stem = _stem(sample_rate)
    total_samples = round(1.0 * sample_rate)  # much shorter than where the beats fall

    timemap = build_timemap(beats, stem, sample_rate, target_bpm=120.0, total_samples=total_samples)

    assert timemap == [(0, 0), (total_samples, total_samples)]
