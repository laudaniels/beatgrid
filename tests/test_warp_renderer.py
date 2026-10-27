from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fixtures import make_click_track

from beatgrid.grid.model import Anchor, BeatGrid, TimeSignature
from beatgrid.project.models import Project, Stem, WarpRender
from beatgrid.render.warp_renderer import build_segment_plan, render_warp, warp_stem_audio


def _anchor(time_sec, beat_index, bpm, anchor_id="a"):
    return Anchor(
        id=anchor_id,
        time_sec=time_sec,
        sample_index=round(time_sec * 44100),
        beat_index=beat_index,
        bpm=bpm,
    )


def test_build_segment_plan_single_anchor():
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4), anchors=[_anchor(0.0, 0, 120.0)], sample_rate=44100
    )

    segments = build_segment_plan(grid, end_time_sec=4.0)

    assert len(segments) == 1
    assert segments[0].start_sec == 0.0
    assert segments[0].end_sec == 4.0
    assert segments[0].beat_count == 8  # 120 BPM -> 0.5s/beat -> 8 beats in 4s
    assert segments[0].bpm == 120.0


def test_build_segment_plan_multi_anchor_matches_beat_index_gap():
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(0.0, 0, 120.0, "a1"), _anchor(2.0, 4, 100.0, "a2")],
        sample_rate=44100,
    )

    segments = build_segment_plan(grid, end_time_sec=3.2)

    assert len(segments) == 2
    assert segments[0].beat_count == 4
    assert segments[0].bpm == 120.0
    assert segments[1].start_sec == 2.0
    assert segments[1].end_sec == 3.2
    assert segments[1].bpm == 100.0


def test_build_segment_plan_empty_grid():
    grid = BeatGrid(time_signature=TimeSignature(), anchors=[], sample_rate=44100)
    assert build_segment_plan(grid, end_time_sec=10.0) == []


class _IdentityStretcher:
    """A no-op stretch engine (resamples via simple repetition/stride) good
    enough to exercise warp_stem_audio's segment math without pedalboard."""

    name = "identity-ish"

    def stretch(self, audio: np.ndarray, sample_rate: int, ratio: float) -> np.ndarray:
        target_length = max(1, round(len(audio) * ratio))
        indices = np.linspace(0, len(audio) - 1, target_length).astype(np.int64)
        return audio[indices]


def test_warp_stem_audio_pins_exact_expected_length():
    bpm = 120.0
    target_bpm = 140.0
    sample_rate = 8000
    track = make_click_track(bpm=bpm, duration_sec=4.0, sample_rate=sample_rate)
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4), anchors=[_anchor(0.0, 0, bpm)], sample_rate=sample_rate
    )
    segments = build_segment_plan(grid, end_time_sec=4.0)
    stem = Stem(id="s", path=Path("s.wav"), sample_rate=sample_rate, duration_sec=4.0)

    warped = warp_stem_audio(
        track.audio, sample_rate, stem, segments, target_bpm, _IdentityStretcher()
    )

    expected_samples = round(segments[0].beat_count * 60.0 / target_bpm * sample_rate)
    assert len(warped) == expected_samples


def test_warp_stem_audio_preserves_lead_in_and_tail():
    sample_rate = 8000
    # anchor starts 1s into the audio, grid covers [1.0, 3.0); audio runs to 4.0s
    track = make_click_track(
        bpm=120.0, duration_sec=4.0, sample_rate=sample_rate, start_offset_sec=1.0
    )
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(1.0, 0, 120.0)],
        sample_rate=sample_rate,
    )
    segments = build_segment_plan(grid, end_time_sec=3.0)
    stem = Stem(id="s", path=Path("s.wav"), sample_rate=sample_rate, duration_sec=4.0)

    warped = warp_stem_audio(track.audio, sample_rate, stem, segments, 120.0, _IdentityStretcher())

    # the last/first few ms of the lead-in/tail are intentionally crossfaded
    # with the adjacent (stretched) segment to avoid a splice click, so only
    # compare the parts safely before/after that crossfade zone.
    from beatgrid.render.warp_renderer import CROSSFADE_SEC

    margin = round(CROSSFADE_SEC * sample_rate) + 10
    lead_in_samples = round(1.0 * sample_rate)
    tail_samples = round(1.0 * sample_rate)  # audio from 3.0s to 4.0s

    assert np.array_equal(
        warped[: lead_in_samples - margin], track.audio[: lead_in_samples - margin]
    )
    assert np.array_equal(
        warped[-(tail_samples - margin) :], track.audio[-(tail_samples - margin) :]
    )


def test_warp_stem_audio_all_stems_same_length_for_shared_segments():
    bpm = 120.0
    target_bpm = 128.0
    sample_rate = 8000
    duration = 4.0
    track_a = make_click_track(bpm=bpm, duration_sec=duration, sample_rate=sample_rate)
    track_b = make_click_track(
        bpm=bpm, duration_sec=duration, sample_rate=sample_rate, noise_level=0.01, seed=1
    )

    grid = BeatGrid(
        time_signature=TimeSignature(4, 4), anchors=[_anchor(0.0, 0, bpm)], sample_rate=sample_rate
    )
    segments = build_segment_plan(grid, end_time_sec=duration)
    stem_a = Stem(id="a", path=Path("a.wav"), sample_rate=sample_rate, duration_sec=duration)
    stem_b = Stem(id="b", path=Path("b.wav"), sample_rate=sample_rate, duration_sec=duration)

    engine = _IdentityStretcher()
    warped_a = warp_stem_audio(track_a.audio, sample_rate, stem_a, segments, target_bpm, engine)
    warped_b = warp_stem_audio(track_b.audio, sample_rate, stem_b, segments, target_bpm, engine)

    assert len(warped_a) == len(warped_b)


def test_warp_stem_audio_with_pedalboard_matches_target_duration():
    pytest.importorskip("pedalboard")
    from beatgrid.render.engines.pedalboard_stretcher import PedalboardStretcher

    bpm = 120.0
    target_bpm = 140.0
    sample_rate = 22050
    track = make_click_track(bpm=bpm, duration_sec=4.0, sample_rate=sample_rate)
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4), anchors=[_anchor(0.0, 0, bpm)], sample_rate=sample_rate
    )
    segments = build_segment_plan(grid, end_time_sec=4.0)
    stem = Stem(id="s", path=Path("s.wav"), sample_rate=sample_rate, duration_sec=4.0)

    warped = warp_stem_audio(
        track.audio, sample_rate, stem, segments, target_bpm, PedalboardStretcher()
    )

    expected_samples = round(segments[0].beat_count * 60.0 / target_bpm * sample_rate)
    assert len(warped) == expected_samples


def test_render_warp_writes_non_destructive_files_and_returns_warp_render(tmp_path):
    pytest.importorskip("pedalboard")
    from beatgrid.audio.loader import LoadedAudio
    from beatgrid.render.engines.pedalboard_stretcher import PedalboardStretcher

    sample_rate = 22050
    bpm = 120.0
    track_kick = make_click_track(bpm=bpm, duration_sec=2.0, sample_rate=sample_rate)
    track_bass = make_click_track(bpm=bpm, duration_sec=2.0, sample_rate=sample_rate, seed=2)

    kick_path = tmp_path / "kick.wav"
    bass_path = tmp_path / "bass.wav"
    sf.write(kick_path, track_kick.audio, sample_rate)
    sf.write(bass_path, track_bass.audio, sample_rate)

    grid = BeatGrid(
        time_signature=TimeSignature(4, 4), anchors=[_anchor(0.0, 0, bpm)], sample_rate=sample_rate
    )
    stems = [
        Stem(id="kick", path=kick_path, sample_rate=sample_rate, duration_sec=2.0),
        Stem(id="bass", path=bass_path, sample_rate=sample_rate, duration_sec=2.0),
    ]
    project = Project(name="t", stems=stems, reference_stem_id="kick", grid=grid)
    audio_by_stem = {
        "kick": LoadedAudio(audio=track_kick.audio, sample_rate=sample_rate),
        "bass": LoadedAudio(audio=track_bass.audio, sample_rate=sample_rate),
    }

    output_dir = tmp_path / "warped"
    progress = []
    result = render_warp(
        project,
        target_bpm=130.0,
        engine=PedalboardStretcher(),
        output_dir=output_dir,
        audio_by_stem=audio_by_stem,
        on_progress=lambda done, total, stem_id: progress.append((done, total, stem_id)),
    )

    assert progress == [(0, 2, "kick"), (1, 2, "bass"), (2, 2, "")]
    from beatgrid.render.wav_markers import read_acid_tempo

    for path in result.output_paths.values():
        bpm, num_beats, numerator, denominator = read_acid_tempo(path)
        frames = sf.info(path).frames
        assert bpm == pytest.approx(130.0, abs=1e-4)
        assert num_beats == round(frames / sample_rate * 130.0 / 60.0)
        assert (numerator, denominator) == (4, 4)
    assert isinstance(result, WarpRender)
    assert result.target_bpm == 130.0
    assert result.engine == "pedalboard"
    assert set(result.output_paths) == {"kick", "bass"}
    for path in result.output_paths.values():
        assert path.exists()
    # originals untouched
    assert sf.info(kick_path).frames == len(track_kick.audio)
    # both warped files end up the same length
    kick_out, _ = sf.read(result.output_paths["kick"])
    bass_out, _ = sf.read(result.output_paths["bass"])
    assert len(kick_out) == len(bass_out)


def _impulse_track(positions: list[int], length: int) -> np.ndarray:
    """A clean impulse train (not a click burst) for measuring exactly where
    content ends up after stretching — a single-sample peak is much easier
    to pinpoint precisely than a windowed click, isolating the warp engine's
    own fidelity from any onset-detector imprecision."""
    audio = np.zeros(length, dtype=np.float32)
    for position in positions:
        if 0 <= position < length:
            audio[position] = 1.0
    return audio


def _rubberband_available() -> bool:
    from beatgrid.render.engines.rubberband_timemap_stretcher import find_rubberband

    return find_rubberband() is not None


requires_rubberband = pytest.mark.skipif(
    not _rubberband_available(), reason="rubberband is not installed"
)


@requires_rubberband
def test_render_warp_rubberband_anchors_land_sample_accurately_and_stems_match_length(tmp_path):
    from beatgrid.audio.loader import LoadedAudio
    from beatgrid.render.engines.rubberband_timemap_stretcher import RubberbandTimemapStretcher

    sample_rate = 22050
    duration_sec = 6.0
    length = round(duration_sec * sample_rate)
    bpm = 118.0  # deliberately not a round number, like a real detected tempo
    target_bpm = 120.0
    interval_samples = 60.0 / bpm * sample_rate
    positions = [round(i * interval_samples) for i in range(12)]

    track_kick = _impulse_track(positions, length)
    track_bass = _impulse_track(positions, length)  # same grid, independent "stem"

    kick_path = tmp_path / "kick.wav"
    bass_path = tmp_path / "bass.wav"
    sf.write(kick_path, track_kick, sample_rate)
    sf.write(bass_path, track_bass, sample_rate)

    grid = BeatGrid(
        time_signature=TimeSignature(4, 4), anchors=[_anchor(0.0, 0, bpm)], sample_rate=sample_rate
    )
    stems = [
        Stem(id="kick", path=kick_path, sample_rate=sample_rate, duration_sec=duration_sec),
        Stem(id="bass", path=bass_path, sample_rate=sample_rate, duration_sec=duration_sec),
    ]
    project = Project(name="t", stems=stems, reference_stem_id="kick", grid=grid)
    audio_by_stem = {
        "kick": LoadedAudio(audio=track_kick, sample_rate=sample_rate),
        "bass": LoadedAudio(audio=track_bass, sample_rate=sample_rate),
    }

    result = render_warp(
        project,
        target_bpm=target_bpm,
        engine=RubberbandTimemapStretcher(),
        output_dir=tmp_path / "warped",
        audio_by_stem=audio_by_stem,
    )
    assert result.engine == "rubberband-timemap"

    # (a) anchors land sample-accurately on the *fixed-tempo* grid position
    # -- i.e. where build_timemap told the engine to put them, not their
    # original (pre-warp) position. A phase-vocoder engine introduces a
    # small, roughly constant processing latency (observed ~9ms on this
    # engine/signal) relative to that target, which this allows for.
    beats = grid.generate_beats(end_time_sec=duration_sec)
    ideal_interval_samples = 60.0 / target_bpm * sample_rate
    first_target = beats[0].sample_index  # the first beat's own position is unchanged
    expected_targets = [
        round(first_target + (beat.index - beats[0].index) * ideal_interval_samples)
        for beat in beats
    ]

    kick_out, _ = sf.read(result.output_paths["kick"], dtype="float32")
    search_window = round(0.015 * sample_rate)  # 15ms, comfortably covers the latency
    detected_peaks = []
    for expected in expected_targets:
        lo, hi = max(0, expected - search_window), min(len(kick_out), expected + search_window)
        detected_peaks.append(lo + int(np.argmax(np.abs(kick_out[lo:hi]))))

    deviations = np.abs(np.array(detected_peaks) - np.array(expected_targets))
    assert np.all(deviations < sample_rate * 0.012)  # within ~12ms of the ideal grid position

    # (b) all stretched stems come out exactly the same length
    kick_frames = sf.info(result.output_paths["kick"]).frames
    bass_frames = sf.info(result.output_paths["bass"]).frames
    assert kick_frames == bass_frames

    # (c) every downbeat gets a "Bar N" cue marker at its warped position
    from beatgrid.render.wav_markers import read_cue_markers

    expected_markers = [
        (target, f"Bar {beat.bar}")
        for beat, target in zip(beats, expected_targets, strict=True)
        if beat.is_downbeat
    ]
    assert read_cue_markers(result.output_paths["kick"]) == expected_markers
    assert read_cue_markers(result.output_paths["bass"]) == expected_markers


def test_render_warp_raises_without_anchors(tmp_path):
    grid = BeatGrid(time_signature=TimeSignature(), anchors=[], sample_rate=44100)
    stem = Stem(id="s", path=tmp_path / "s.wav", sample_rate=44100, duration_sec=1.0)
    project = Project(name="t", stems=[stem], reference_stem_id="s", grid=grid)

    with pytest.raises(ValueError):
        render_warp(
            project,
            target_bpm=120.0,
            engine=_IdentityStretcher(),
            output_dir=tmp_path,
            audio_by_stem={},
        )


def test_bar_aligned_padding_puts_first_downbeat_on_the_same_whole_bar_in_every_stem():
    from beatgrid.render.warp_renderer import bar_aligned_padding

    bpm = 120.0  # a 4/4 bar is 2.0 s
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4), anchors=[_anchor(3.3, 0, bpm)], sample_rate=44100
    )
    stems = [
        Stem(id="a", path=Path("a.wav"), sample_rate=44100, duration_sec=10.0),
        # starts 0.5 s later on the project timeline: first beat at 2.8 s of its own audio
        Stem(
            id="b", path=Path("b.wav"), sample_rate=44100, duration_sec=10.0, start_offset_sec=0.5
        ),
    ]
    project = Project(name="t", stems=stems, reference_stem_id="a", grid=grid)

    padding = bar_aligned_padding(project, target_bpm=bpm)

    # both stems' first downbeat ends up 4.0 s (2 whole bars) into the file
    assert 3.3 + padding["a"] == pytest.approx(4.0)
    assert 2.8 + padding["b"] == pytest.approx(4.0)


def test_bar_aligned_padding_is_zero_when_already_on_a_bar():
    from beatgrid.render.warp_renderer import bar_aligned_padding

    grid = BeatGrid(
        time_signature=TimeSignature(4, 4), anchors=[_anchor(4.0, 0, 120.0)], sample_rate=44100
    )
    stem = Stem(id="a", path=Path("a.wav"), sample_rate=44100, duration_sec=10.0)
    project = Project(name="t", stems=[stem], reference_stem_id="a", grid=grid)

    assert bar_aligned_padding(project, target_bpm=120.0)["a"] == pytest.approx(0.0)


def test_bar_aligned_padding_follows_a_moved_downbeat():
    from beatgrid.render.warp_renderer import bar_aligned_padding

    # first beat (anchor) at 3.3 s, but bar 1 starts one beat later, at 3.8 s
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(3.3, 0, 120.0)],
        sample_rate=44100,
        downbeat_sec=3.8,
    )
    stem = Stem(id="a", path=Path("a.wav"), sample_rate=44100, duration_sec=10.0)
    project = Project(name="t", stems=[stem], reference_stem_id="a", grid=grid)

    padding = bar_aligned_padding(project, target_bpm=120.0)

    # the downbeat (3.8 s) lands on 4.0 s = 2 whole bars into the file
    assert 3.8 + padding["a"] == pytest.approx(4.0)


def test_render_warp_swaps_in_complete_files_and_leaves_no_partials(tmp_path, monkeypatch):
    """A reader that opens the output the moment it appears must already
    see the tempo chunk -- the file is only ever replaced whole."""
    pytest.importorskip("pedalboard")
    import os as os_module

    from beatgrid.audio.loader import LoadedAudio
    from beatgrid.render.engines.pedalboard_stretcher import PedalboardStretcher
    from beatgrid.render.wav_markers import read_acid_tempo

    sample_rate = 22050
    track = make_click_track(bpm=120.0, duration_sec=2.0, sample_rate=sample_rate)
    path = tmp_path / "kick.wav"
    sf.write(path, track.audio, sample_rate)
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[_anchor(0.0, 0, 120.0)],
        sample_rate=sample_rate,
    )
    stem = Stem(id="kick", path=path, sample_rate=sample_rate, duration_sec=2.0)
    project = Project(name="t", stems=[stem], reference_stem_id="kick", grid=grid)

    seen_on_arrival = []
    real_replace = os_module.replace

    def spying_replace(src, dst):
        seen_on_arrival.append(read_acid_tempo(src))
        real_replace(src, dst)

    monkeypatch.setattr("beatgrid.render.warp_renderer.os.replace", spying_replace)
    output_dir = tmp_path / "warped"
    render_warp(
        project,
        target_bpm=125.0,
        engine=PedalboardStretcher(),
        output_dir=output_dir,
        audio_by_stem={"kick": LoadedAudio(audio=track.audio, sample_rate=sample_rate)},
    )

    assert seen_on_arrival and seen_on_arrival[0][0] == pytest.approx(125.0)
    assert [p.name for p in output_dir.iterdir()] == ["kick_warped_125bpm.wav"]
