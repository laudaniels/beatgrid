from __future__ import annotations

from collections.abc import Sequence

from beatgrid.grid.model import Beat
from beatgrid.grid.timeline import project_time_to_stem_sample
from beatgrid.project.models import Stem


def build_timemap(
    beats: Sequence[Beat],
    stem: Stem,
    sample_rate: int,
    target_bpm: float,
    total_samples: int,
) -> list[tuple[int, int]]:
    """(source_sample, target_sample) keyframes, in `stem`'s own sample axis,
    for pyrubberband's native timemap stretch.

    The *first* beat's position never moves (`target == source` for it);
    every later beat is repositioned relative to it at a constant
    `target_bpm`, so the grid becomes perfectly even while the track's
    overall starting point stays put. The same `beats` list (from
    BeatGrid.generate_beats(), shared project-wide) applied to every stem —
    each just translating it to its own sample axis via start_offset_sec —
    keeps every stem mutually in sync after warping.

    Audio before the first beat / after the last one is kept at its original
    duration (an unstretched lead-in/tail), matching render/warp_renderer.py's
    (M8 prototype) handling of the same regions. pyrubberband requires the
    last keyframe's source to equal `total_samples` exactly, which the
    trailing keyframe added here satisfies.
    """
    if not beats:
        raise ValueError("need at least one beat to build a timemap")

    beats = sorted(beats, key=lambda b: b.index)
    interval_samples = 60.0 / target_bpm * sample_rate

    first_beat = beats[0]
    first_source = max(0, project_time_to_stem_sample(first_beat.time_sec, stem, sample_rate))
    first_target = first_source  # the first beat's own position is unchanged

    keyframes: list[tuple[int, int]] = []
    if first_source > 0:
        keyframes.append((0, 0))  # lead-in: unstretched

    for beat in beats:
        source_sample = max(0, project_time_to_stem_sample(beat.time_sec, stem, sample_rate))
        if source_sample > total_samples:
            # this and every later beat (beats are sorted) fall beyond this
            # stem's own audio -- e.g. a short/trimmed stem.
            break
        target_sample = round(first_target + (beat.index - first_beat.index) * interval_samples)
        keyframes.append((source_sample, target_sample))

    if not keyframes:
        keyframes.append((0, 0))

    last_source, last_target = keyframes[-1]
    if last_source < total_samples:
        tail_length = total_samples - last_source
        keyframes.append((total_samples, last_target + tail_length))  # tail: unstretched

    return keyframes
