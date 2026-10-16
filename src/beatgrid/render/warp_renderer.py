from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

from beatgrid.audio.loader import LoadedAudio
from beatgrid.grid.model import BeatGrid
from beatgrid.grid.timeline import project_time_to_stem_time
from beatgrid.project.models import Project, Stem, WarpRender
from beatgrid.render.engines.base import TimeStretcher

CROSSFADE_SEC = 0.008


@dataclass(frozen=True)
class SegmentPlan:
    """One piecewise-constant-tempo segment of the grid, in project time."""

    start_sec: float
    end_sec: float
    beat_count: int
    bpm: float  # this segment's local tempo (from its starting anchor)


def build_segment_plan(grid: BeatGrid, end_time_sec: float) -> list[SegmentPlan]:
    """The grid's anchors as a list of segments (project-time boundaries,
    beat count, tempo) — the same boundaries BeatGrid.generate_beats() uses
    internally, extracted here so the warp renderer can compute per-segment
    stretch ratios without re-deriving beat counts itself."""
    anchors = sorted(grid.anchors, key=lambda a: a.time_sec)
    if not anchors:
        return []

    segments = []
    for i, anchor in enumerate(anchors):
        if i + 1 < len(anchors):
            next_anchor = anchors[i + 1]
            end_sec = next_anchor.time_sec
            beat_count = next_anchor.beat_index - anchor.beat_index
        else:
            end_sec = end_time_sec
            beat_count = max(0, round((end_time_sec - anchor.time_sec) / (60.0 / anchor.bpm)))
        segments.append(
            SegmentPlan(
                start_sec=anchor.time_sec, end_sec=end_sec, beat_count=beat_count, bpm=anchor.bpm
            )
        )
    return segments


def warp_stem_audio(
    audio: np.ndarray,
    sample_rate: int,
    stem: Stem,
    segments: list[SegmentPlan],
    target_bpm: float,
    engine: TimeStretcher,
    *,
    crossfade_sec: float = CROSSFADE_SEC,
) -> np.ndarray:
    """Time-stretch one stem's audio so every segment lands on `target_bpm`.

    Each project-time segment boundary is translated to this stem's own
    sample positions via its start_offset_sec, so the *same* `segments` list
    applied to every stem in a project keeps them all mutually in sync after
    warping. Each stretched segment is pinned to its exact expected sample
    length (derived purely from beat_count/target_bpm/sample_rate, identical
    across stems) rather than trusting the engine's natural output length —
    that's what actually guarantees every stem comes out the same length.
    Audio before the first anchor / after the last segment is copied through
    unmodified rather than dropped.
    """
    pieces: list[np.ndarray] = []

    if segments:
        lead_in_end = _to_stem_sample(segments[0].start_sec, stem, sample_rate)
        if lead_in_end > 0:
            pieces.append(audio[: min(lead_in_end, len(audio))])

    for segment in segments:
        start_sample = _to_stem_sample(segment.start_sec, stem, sample_rate)
        end_sample = _to_stem_sample(segment.end_sec, stem, sample_rate)
        start_sample = max(0, start_sample)
        end_sample = min(len(audio), end_sample)
        if end_sample <= start_sample or segment.beat_count <= 0:
            continue

        measured_duration = (end_sample - start_sample) / sample_rate
        ideal_duration = segment.beat_count * 60.0 / target_bpm
        ratio = ideal_duration / measured_duration

        stretched = engine.stretch(audio[start_sample:end_sample], sample_rate, ratio)
        pieces.append(_fit_to_length(stretched, round(ideal_duration * sample_rate)))

    if segments:
        tail_start = _to_stem_sample(segments[-1].end_sec, stem, sample_rate)
        if 0 <= tail_start < len(audio):
            pieces.append(audio[tail_start:])

    return _concatenate_with_crossfade(pieces, sample_rate, crossfade_sec)


def render_warp(
    project: Project,
    target_bpm: float,
    engine: TimeStretcher,
    output_dir: Path,
    audio_by_stem: dict[str, LoadedAudio],
) -> WarpRender:
    """Warp every stem in `project` to `target_bpm` and write each to a new,
    non-destructive file under `output_dir` — the originals are never
    touched. Returns a WarpRender describing the result, for the caller to
    append to Project.warp_renders."""
    reference_stem = project.reference_stem()
    segments = build_segment_plan(project.grid, end_time_sec=reference_stem.duration_sec)
    if not segments:
        raise ValueError("project has no anchors to warp from")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_paths: dict[str, Path] = {}
    for stem in project.stems:
        loaded = audio_by_stem[stem.id]
        warped = warp_stem_audio(
            loaded.audio, loaded.sample_rate, stem, segments, target_bpm, engine
        )
        out_path = output_dir / f"{stem.id}_warped.wav"
        sf.write(out_path, warped, loaded.sample_rate)
        output_paths[stem.id] = out_path

    return WarpRender(
        target_bpm=target_bpm,
        engine=engine.name,
        rendered_at=datetime.now(),
        output_paths=output_paths,
    )


def _to_stem_sample(project_time_sec: float, stem: Stem, sample_rate: int) -> int:
    return round(project_time_to_stem_time(project_time_sec, stem) * sample_rate)


def _fit_to_length(audio: np.ndarray, target_length: int) -> np.ndarray:
    target_length = max(0, target_length)
    if len(audio) == target_length:
        return audio
    if len(audio) > target_length:
        return audio[:target_length]
    return np.pad(audio, (0, target_length - len(audio)))


def _concatenate_with_crossfade(
    pieces: list[np.ndarray], sample_rate: int, crossfade_sec: float
) -> np.ndarray:
    pieces = [p for p in pieces if len(p) > 0]
    if not pieces:
        return np.zeros(0, dtype=np.float32)
    if len(pieces) == 1:
        return pieces[0].astype(np.float32)

    crossfade_samples = max(1, round(crossfade_sec * sample_rate))
    result = pieces[0].astype(np.float32).copy()
    for piece in pieces[1:]:
        piece = piece.astype(np.float32)
        n = min(crossfade_samples, len(result), len(piece))
        if n <= 0:
            result = np.concatenate([result, piece])
            continue
        fade_out = np.linspace(1.0, 0.0, n, dtype=np.float32)
        fade_in = np.linspace(0.0, 1.0, n, dtype=np.float32)
        overlap = result[-n:] * fade_out + piece[:n] * fade_in
        result = np.concatenate([result[:-n], overlap, piece[n:]])
    return result
