from __future__ import annotations

import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

from beatgrid.audio.loader import LoadedAudio
from beatgrid.grid.model import Beat, BeatGrid
from beatgrid.grid.timeline import project_time_to_stem_sample, project_time_to_stem_time
from beatgrid.project.models import Project, Stem, WarpRender
from beatgrid.render.chunked_timemap import stretch_in_chunks
from beatgrid.render.engines.base import TimemapStretcher, TimeStretcher
from beatgrid.render.timemap import build_timemap, place_beats
from beatgrid.render.warp_output import warped_filename
from beatgrid.render.wav_markers import add_acid_tempo, add_cue_markers

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
        lead_in_end = project_time_to_stem_sample(segments[0].start_sec, stem, sample_rate)
        if lead_in_end > 0:
            pieces.append(audio[: min(lead_in_end, len(audio))])

    for segment in segments:
        start_sample = project_time_to_stem_sample(segment.start_sec, stem, sample_rate)
        end_sample = project_time_to_stem_sample(segment.end_sec, stem, sample_rate)
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
        tail_start = project_time_to_stem_sample(segments[-1].end_sec, stem, sample_rate)
        if 0 <= tail_start < len(audio):
            pieces.append(audio[tail_start:])

    return _concatenate_with_crossfade(pieces, sample_rate, crossfade_sec)


def warp_stem_audio_timemap(
    audio: np.ndarray,
    sample_rate: int,
    stem: Stem,
    beats: list[Beat],
    target_bpm: float,
    engine: TimemapStretcher,
) -> np.ndarray:
    """Time-stretch one stem's audio via a native timemap (render/timemap.py)
    — the M9 production path, used instead of warp_stem_audio()'s manual
    segment-splitting/crossfading for engines that support it
    (TimemapStretcher).

    Rendered in 64-beat chunks (render/chunked_timemap.py) rather than one
    pass: over a whole song Rubber Band's output drifts progressively off
    the keyframes, worst with snapped beats' per-beat ratio changes; short
    chunks keep beats within a few ms."""
    timemap = build_timemap(beats, stem, sample_rate, target_bpm, total_samples=len(audio))
    return stretch_in_chunks(audio, sample_rate, timemap, engine.stretch_with_timemap)


def render_warp(
    project: Project,
    target_bpm: float,
    engine: TimeStretcher | TimemapStretcher,
    output_dir: Path,
    audio_by_stem: dict[str, LoadedAudio],
    on_progress: Callable[[int, int, str], None] | None = None,
) -> WarpRender:
    """Warp every stem in `project` to `target_bpm` and write each to a new,
    non-destructive file under `output_dir` — the originals are never
    touched. Returns a WarpRender describing the result, for the caller to
    append to Project.warp_renders.

    Dispatches to the native-timemap path (warp_stem_audio_timemap) when
    `engine` supports it (the M9 production engine), otherwise falls back to
    the segment+crossfade path (warp_stem_audio, M8's prototype engine).

    With the timemap path, each output file also gets a cue marker
    ("Bar N") on every downbeat, exactly where the warp put it. The segment
    path doesn't get markers: its crossfaded joins shift later audio by a
    few ms per anchor, so marker positions wouldn't be exact.

    Every output file also declares `target_bpm` in an ACID chunk, so DAWs
    that read it pick up the tempo without it being typed in, and starts
    with just enough silence that the first downbeat sits on a whole bar
    (bar_aligned_padding).

    `on_progress(done, total, stem_id)` is called before each stem is
    warped (stem_id = the one about to start) and once more at the end
    (done == total, stem_id == "").
    """
    reference_stem = project.reference_stem()
    end_time_sec = reference_stem.duration_sec
    uses_timemap = hasattr(engine, "stretch_with_timemap")

    if uses_timemap:
        beats = project.grid.generate_beats(end_time_sec=end_time_sec)
        if not beats:
            raise ValueError("project has no anchors to warp from")
    else:
        segments = build_segment_plan(project.grid, end_time_sec=end_time_sec)
        if not segments:
            raise ValueError("project has no anchors to warp from")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    padding_sec = bar_aligned_padding(project, target_bpm)
    output_paths: dict[str, Path] = {}
    total = len(project.stems)
    for done, stem in enumerate(project.stems):
        if on_progress is not None:
            on_progress(done, total, stem.id)
        loaded = audio_by_stem[stem.id]
        if uses_timemap:
            warped = warp_stem_audio_timemap(
                loaded.audio, loaded.sample_rate, stem, beats, target_bpm, engine
            )
        else:
            warped = warp_stem_audio(
                loaded.audio, loaded.sample_rate, stem, segments, target_bpm, engine
            )
        pad = round(padding_sec[stem.id] * loaded.sample_rate)
        warped = np.concatenate([np.zeros(pad, dtype=np.float32), warped])
        out_path = output_dir / warped_filename(stem.id, target_bpm)
        # Build the complete file (audio, markers, tempo) under a temporary
        # name and only then swap it in: a DAW that has the previous render
        # loaded may reload it the moment it changes, and would otherwise
        # catch a plain WAV without markers/tempo in between.
        partial = out_path.with_name(f".{out_path.name}.partial")
        sf.write(partial, warped, loaded.sample_rate, format="WAV")
        if uses_timemap:
            markers = bar_markers(beats, stem, loaded.sample_rate, target_bpm, len(loaded.audio))
            add_cue_markers(partial, [(sample + pad, label) for sample, label in markers])
        add_acid_tempo(
            partial,
            target_bpm,
            num_beats=round(len(warped) / loaded.sample_rate * target_bpm / 60.0),
            numerator=project.grid.time_signature.numerator,
            denominator=project.grid.time_signature.denominator,
        )
        os.replace(partial, out_path)
        output_paths[stem.id] = out_path

    if on_progress is not None:
        on_progress(total, total, "")
    return WarpRender(
        target_bpm=target_bpm,
        engine=engine.name,
        rendered_at=datetime.now(),
        output_paths=output_paths,
    )


def bar_aligned_padding(project: Project, target_bpm: float) -> dict[str, float]:
    """Seconds of silence to put before each stem's warped audio so that the
    grid's first downbeat lands on a whole bar counted from the start of the
    file -- the *same* bar in every stem -- so the files line up with a
    DAW's grid (and with each other) when dropped at bar 1.

    The warp leaves the first beat in place and spaces every later beat at
    exactly the target tempo, so the first downbeat ends up a whole number
    of target-tempo beats after the first beat.
    """
    grid = project.grid
    beats = grid.generate_beats(end_time_sec=project.reference_stem().duration_sec)
    beat_sec = 60.0 / target_bpm
    bar_sec = grid.time_signature.numerator * beat_sec
    first_beat = beats[0]
    first_downbeat = next(b for b in beats if b.is_downbeat)
    downbeat_after_first_beat = (first_downbeat.index - first_beat.index) * beat_sec
    first_downbeat_sec = {
        stem.id: max(0.0, project_time_to_stem_time(first_beat.time_sec, stem))
        + downbeat_after_first_beat
        for stem in project.stems
    }
    # tiny tolerance: a downbeat already on a bar line needs no extra bar
    bars = max(math.ceil(t / bar_sec - 1e-9) for t in first_downbeat_sec.values())
    return {stem_id: bars * bar_sec - t for stem_id, t in first_downbeat_sec.items()}


def bar_markers(
    beats: list[Beat], stem: Stem, sample_rate: int, target_bpm: float, total_samples: int
) -> list[tuple[int, str]]:
    """(sample, "Bar N") for every downbeat, at its position in `stem`'s
    timemap-warped output."""
    return [
        (target, f"Bar {beat.bar}")
        for beat, _source, target in place_beats(
            beats, stem, sample_rate, target_bpm, total_samples
        )
        if beat.is_downbeat
    ]


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
