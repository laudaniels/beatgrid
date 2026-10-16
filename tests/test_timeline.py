from pathlib import Path

from beatgrid.grid.model import Beat
from beatgrid.grid.timeline import (
    beats_to_stem_samples,
    project_time_to_stem_sample,
    stem_sample_to_project_time,
)
from beatgrid.project.models import Stem


def _stem(sample_rate=44100, start_offset_sec=0.0):
    return Stem(
        id="s", path=Path("s.wav"), sample_rate=sample_rate, start_offset_sec=start_offset_sec
    )


def test_project_time_to_stem_sample_no_offset():
    stem = _stem(sample_rate=44100, start_offset_sec=0.0)
    assert project_time_to_stem_sample(1.0, stem) == 44100


def test_project_time_to_stem_sample_with_offset():
    stem = _stem(sample_rate=44100, start_offset_sec=0.5)
    assert project_time_to_stem_sample(1.0, stem) == 22050


def test_roundtrip_sample_to_time_to_sample():
    stem = _stem(sample_rate=48000, start_offset_sec=-0.25)
    sample = 12000
    time_sec = stem_sample_to_project_time(sample, stem)
    assert project_time_to_stem_sample(time_sec, stem) == sample


def test_beats_to_stem_samples():
    stem = _stem(sample_rate=44100, start_offset_sec=0.1)
    beats = [
        Beat(index=0, time_sec=0.1, sample_index=4410, bar=1, beat_in_bar=1, is_downbeat=True),
        Beat(index=1, time_sec=0.6, sample_index=26460, bar=1, beat_in_bar=2, is_downbeat=False),
    ]
    assert beats_to_stem_samples(beats, stem) == [0, round(0.5 * 44100)]
