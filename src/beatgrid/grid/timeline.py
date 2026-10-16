from __future__ import annotations

from beatgrid.grid.model import Beat
from beatgrid.project.models import Stem


def project_time_to_stem_time(time_sec: float, stem: Stem) -> float:
    """A project-time position translated to `stem`'s own continuous timeline."""
    return time_sec - stem.start_offset_sec


def project_time_to_stem_sample(time_sec: float, stem: Stem, sample_rate: int | None = None) -> int:
    """A project-time position (the reference stem's own timeline, offset 0)
    translated to a sample index in `stem`'s own audio.

    `sample_rate` defaults to `stem.sample_rate`, but callers that hold the
    actual loaded audio buffer (e.g. the warp renderer) can pass its real
    sample rate explicitly, since that's what the returned index must index
    into."""
    rate = stem.sample_rate if sample_rate is None else sample_rate
    return round(project_time_to_stem_time(time_sec, stem) * rate)


def stem_sample_to_project_time(sample_index: int, stem: Stem) -> float:
    return sample_index / stem.sample_rate + stem.start_offset_sec


def beats_to_stem_samples(beats: list[Beat], stem: Stem) -> list[int]:
    return [project_time_to_stem_sample(beat.time_sec, stem) for beat in beats]
