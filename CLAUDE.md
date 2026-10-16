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
  (M8 prototype) is GPL-3.0 as a whole; `pyrubberband` (M9 production) shells
  out to a separately-installed `rubberband-cli` binary (subprocess, "mere
  aggregation", lower risk for our own MIT code). Don't bundle either into a
  distributed executable (M10 packaging) without re-reading that trade-off.
