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

    placed = place_beats(beats, stem, sample_rate, target_bpm, total_samples)

    keyframes: list[tuple[int, int]] = []
    if placed and placed[0][1] > 0:
        keyframes.append((0, 0))  # lead-in: unstretched
    keyframes.extend((source, target) for _beat, source, target in placed)

    if not keyframes:
        keyframes.append((0, 0))

    last_source, last_target = keyframes[-1]
    if last_source < total_samples:
        tail_length = total_samples - last_source
        keyframes.append((total_samples, last_target + tail_length))  # tail: unstretched

    return keyframes


def place_beats(
    beats: Sequence[Beat],
    stem: Stem,
    sample_rate: int,
    target_bpm: float,
    total_samples: int,
) -> list[tuple[Beat, int, int]]:
    """(beat, source_sample, target_sample) for every beat inside `stem`'s
    own audio, sorted by index: where each beat is now and where it lands
    after warping to `target_bpm` (the first beat stays put, the rest
    follow at a constant interval). Shared by build_timemap and by anything
    that needs to know beat positions in the warped output (e.g. markers).
    """
    if not beats:
        return []
    beats = sorted(beats, key=lambda b: b.index)
    interval_samples = 60.0 / target_bpm * sample_rate

    first_beat = beats[0]
    first_target = max(0, project_time_to_stem_sample(first_beat.time_sec, stem, sample_rate))

    placed: list[tuple[Beat, int, int]] = []
    for beat in beats:
        source_sample = max(0, project_time_to_stem_sample(beat.time_sec, stem, sample_rate))
        if source_sample > total_samples:
            # this and every later beat (beats are sorted) fall beyond this
            # stem's own audio -- e.g. a short/trimmed stem.
            break
        target_sample = round(first_target + (beat.index - first_beat.index) * interval_samples)
        placed.append((beat, source_sample, target_sample))
    return placed
