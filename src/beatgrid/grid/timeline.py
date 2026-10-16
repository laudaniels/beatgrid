from __future__ import annotations

from beatgrid.grid.model import Beat
from beatgrid.project.models import Stem


def project_time_to_stem_sample(time_sec: float, stem: Stem) -> int:
    """A project-time position (the reference stem's own timeline, offset 0)
    translated to a sample index in `stem`'s own audio."""
    return round((time_sec - stem.start_offset_sec) * stem.sample_rate)


def stem_sample_to_project_time(sample_index: int, stem: Stem) -> float:
    return sample_index / stem.sample_rate + stem.start_offset_sec


def beats_to_stem_samples(beats: list[Beat], stem: Stem) -> list[int]:
    return [project_time_to_stem_sample(beat.time_sec, stem) for beat in beats]
