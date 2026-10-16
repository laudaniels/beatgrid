from pathlib import Path

from beatgrid.grid.model import Beat
from beatgrid.grid.timeline import (
    beats_to_stem_samples,
    project_time_to_stem_sample,
    project_time_to_stem_time,
    stem_sample_to_project_time,
    stem_time_to_project_time,
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


def test_project_time_to_stem_sample_explicit_sample_rate_overrides_stem_metadata():
    # the Stem's own sample_rate metadata says 44100, but the caller holds a
    # buffer actually loaded at 22050 -- the explicit rate must win.
    stem = _stem(sample_rate=44100, start_offset_sec=0.0)
    assert project_time_to_stem_sample(1.0, stem, sample_rate=22050) == 22050


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


def test_stem_time_to_project_time_inverts_project_time_to_stem_time():
    stem = _stem(start_offset_sec=0.75)
    assert stem_time_to_project_time(1.0, stem) == 1.75
    assert project_time_to_stem_time(stem_time_to_project_time(1.0, stem), stem) == 1.0
