# CLAUDE.md

Guidance for working on this repo. See `PLAN.md` for the full design and
milestones — read it before making architectural changes.

## Module boundaries

- `src/beatgrid/project`, `audio`, `detection`, `grid`, `render`, `export` are
  core logic: pure Python/NumPy, no `PySide6`/`pyqtgraph` import, ever. They
  must stay independently unit-testable with no display/audio-device needed.
- `src/beatgrid/gui` is presentation and interaction only. It calls into core
  modules for all beat/grid math and playback decisions; it never computes
  beat positions, tempo, or stretch ratios itself.
- Detectors (`detection/*_detector.py`), exporters (`export/*_exporter.py`)
  and warp engines (`render/engines/*_stretcher.py`) each implement a small
  protocol (`BeatDetector`, `GridExporter`, `TimeStretcher`) and register
  themselves in their module's `registry.py`. Add a new implementation by
  writing one file and registering it — don't touch the callers.

## Test conventions

- `tests/data/` holds **only synthetically generated** fixtures (see
  `tests/fixtures.py`: `make_click_track`, `make_stem_set`). Never commit real
  or copyrighted audio to this repo.
- GUI tests live in `tests/gui/`, run with `QT_QPA_PLATFORM=offscreen`, marked
  `@pytest.mark.gui`, and are structural only (no pixel comparisons, no real
  drag simulation).
- Tests that need the external `rubberband-cli` binary are marked
  `@pytest.mark.requires_rubberband` and skip gracefully if it isn't found.
- Run everything except GUI tests with `uv run pytest -m "not gui"`.

## Adding things

- **New beat detector**: implement `BeatDetector` in `detection/`, register it
  in `detection/registry.py`.
- **New export format**: implement `GridExporter` in `export/`, register it in
  `export/registry.py`.
- **New warp/time-stretch engine**: implement `TimeStretcher` in
  `render/engines/`, register it in `render/engines/registry.py`.

## Known gotchas

- PySide6 is pinned `<6.12` (see `pyproject.toml`'s `gui` extra): 6.12.0 has a
  refcounting regression (PYSIDE-3477) where bool-typed signal emissions —
  which pyqtgraph's graphics-item view-change machinery does internally —
  can crash the interpreter with `Fatal Python error: bool_dealloc` on
  Python <3.12. Don't bump PySide6 past 6.12 without checking that bug is
  fixed upstream.
- `GridOverlay` draws all beat/bar lines as two persistent `PlotCurveItem`s
  (updated via `setData`) instead of one `pg.InfiniteLine` per beat — adding
  hundreds of individual `InfiniteLine` GraphicsObjects is both what
  triggered the crash above in practice and needlessly expensive to redraw.
  Only the single draggable anchor should ever be a real `InfiniteLine`.

## License trade-offs to remember

- `beat-this` and `librosa` are MIT/ISC — no concerns.
- The warp engines are GPL-exposed by design (see `PLAN.md`): `pedalboard`
  (M8 prototype) is GPL-3.0 as a whole; `pyrubberband` (M9 production, the
  default engine) shells out to a separately-installed `rubberband-cli`
  binary (subprocess, "mere aggregation", lower risk for our own MIT code).
  Don't bundle either into a distributed executable (`packaging/beatgrid.spec`)
  without re-reading that trade-off — it's documented again at the top of
  the spec file itself.

## Lessons learned (M0–M10)

- **Verify third-party APIs empirically before writing wrapper code.**
  Beat This!'s `Audio2Beats` interface, `pedalboard.time_stretch`'s channel
  shape (it wants `(channels, samples)`, not a flat 1D array — a flat array
  silently gives a 1-sample output instead of erroring) and
  `pyrubberband.pyrb.timemap_stretch`'s `(source_sample, target_sample)`
  keyframe convention were all confirmed by running them against real audio
  in a scratch script first. Guessing the shape/convention from docs alone
  would have cost more time than the empirical check.
- **Real audio content finds bugs synthetic fixtures don't.** Several of the
  most important fixes in this project (listed below) only surfaced once
  real multi-stem content was loaded through the actual app, not from the
  synthetic `tests/fixtures.py` data. When a milestone touches detection,
  playback, or rendering, do a manual pass with real stems before calling it
  done, even though the repo's committed tests stay synthetic-only.
- **Beat index continuity needs to be derived from one source of truth.**
  `BeatGrid.generate_beats()` originally re-derived each segment's beat count
  from a time cutoff independently of `renumber_anchors()`'s beat-index
  bookkeeping; rounding disagreements between the two caused duplicate/
  skipped beat indices right at segment boundaries. Fixed by always deriving
  a non-last segment's beat count from `next_anchor.beat_index -
  anchor.beat_index` — never re-derive the same count two different ways.
- **`sounddevice`'s `finished_callback` runs on the PortAudio audio thread,
  not the GUI thread.** Closing the stream from inside that callback (even
  indirectly) caused a `pthread_join` self-join error; closing the stream
  that just finished (via a stale reference) after a new one had already
  started caused an `AttributeError` race. Fix: grab-and-clear the stream
  reference atomically in `stop()`, match the specific stream instance in
  the finished callback via a closure, and only ever call
  `cleanup_finished_stream()` from the main thread (driven by the playhead
  `QTimer`), never from the callback itself.
- **Undo/redo: push the snapshot after validation, not before.** Several
  `ProjectController` mutators originally called `_push_undo()` before
  checking whether the target anchor/stem id existed, so a failed (raising)
  call still polluted the undo stack with a no-op entry. Validate first,
  then snapshot, then mutate.
- **When slicing a precomputed pyramid/cache for a viewport, slice before
  converting, not after.** `WaveformItem` first converted the *entire*
  chosen peak-pyramid level to draw points before trimming to the visible
  x-range, which meant zooming into a short section of a long file still
  built millions of points every redraw. Slice `mins`/`maxs` to the visible
  bucket range first, convert only that slice, then offset its x-values by
  the slice's start.
- **A rejected/interrupted tool call can still have run partially.** A
  `pyinstaller` invocation that was rejected mid-command had already
  completed its Analysis and PYZ phases before being killed, leaving a
  multi-GB `packaging/build/` directory on disk. After any interrupted
  build/long-running command, check for and clean up partial artifacts
  rather than assuming nothing happened.
- **Don't build a real executable unless asked.** Packaging polish (M10)
  only needed a correct, well-documented PyInstaller `.spec` — the user
  explicitly didn't want an actual build/exe produced in-session ("vergeet
  de exe maar, als het kan draaien in Linux is prima"). Running the app
  normally via `uv run python -m beatgrid.gui.app` on Linux was the bar, not
  a compiled binary.
- **Rubber Band's timemap is approximate; measure warp precision with a
  method that's identical before and after the warp.** Findings (R3, CLI
  4.0): it renders a timemap's *first segment unstretched* (fixed by the
  engine's silent pre-roll); over a whole song its output drifts off the
  keyframes (~+15 ms after 8 min even at a constant ratio); and per-beat
  ratio changes (snapped beats) make it lose alignment that it never
  regains within that render. Iteratively correcting the timemap doesn't
  converge on real material. What works is `render/chunked_timemap.py`:
  64-beat chunks with 2 beats of context, joined at a common zero crossing
  plus a 2 ms fade — a normal crossfade between two renders of the same
  audio dips in level wherever their phases differ. Short level windows
  (10 ms) mismeasure low tones like a 55 Hz bass; use ≥50 ms. Earlier
  "+18 ms late" readings came from comparing grid positions before the warp
  with re-detected transients after it — two different measurements.
