# BeatGrid

A local, visual beatgrid editor for multi-stem tracks: load up to ~10 stems of
the same song, pick a reference stem (usually the kick), snap the first
downbeat exactly onto the grid, and let BeatGrid propagate that grid to every
other stem. Correct it visually and by ear with a metronome click. Optionally
warp/time-stretch all stems onto a fixed tempo (Ableton warp-marker style).

See [`PLAN.md`](PLAN.md) for the full design, architecture and milestones.

## Status

Through M8: load multiple stems, see their waveforms stacked with a shared
grid, drag anchors on the reference stem to reposition the grid, run
automatic BPM/beat detection ("Detect"), see non-blocking warnings when
stems' sample rate/length/offset look inconsistent, propose cross-correlation
based start offsets ("Detect offsets" — always a proposal you confirm, never
applied automatically), mute/solo per stem, toggle a diagnostic "Show drift"
overlay that marks where a stem's own transients stray from the shared grid
without ever correcting it, add/remove anchors for tracks with tempo drift,
play the mixed stems back with mute/solo respected, a sample-accurate
metronome click and a synced playhead, save/open the full project
(`.beatgrid`), export the grid as JSON (schema in `docs/EXPORT_SCHEMA.md`),
and warp all stems to a fixed tempo ("Warp..." — Variant B *prototype*: a
constant-ratio-per-segment engine with crossfaded splices, written to
`<stem_dir>/warped/`, never touching the originals). The M9 production
engine (native piecewise warping, lower GPL exposure) hasn't started yet —
see the milestones in `PLAN.md`.

## Running the app

```bash
uv sync --extra core --extra gui --extra warp-prototype --extra dev
uv run python -m beatgrid.gui.app
```

This opens a window to load stems (wav/flac/mp3), with a reference-stem
picker, a detector picker + "Detect" button, BPM field and ms/sample nudge
buttons for the first anchor. Needs an actual display — on WSL2 that means
WSLg or an X server; headless environments can still run the structural
tests via `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui -m gui`.

Detection-related tests (`uv run pytest -m "not gui"`) need the `core` extra
(`uv sync --extra core`); the first run downloads and caches the Beat This!
model checkpoint (~tens of MB) from the CPJKU cloud. Warp-related tests need
the `warp-prototype` extra (`uv sync --extra warp-prototype`). Warping a
multi-minute multi-stem project is slow (tens of seconds) — this is a
prototype engine, not yet optimized.

## Prerequisites

Beyond the Python dependencies installed via `uv`, a few things are expected
on your system `PATH`:

- **ffmpeg** — needed for loading `.mp3` files (`soundfile` doesn't reliably
  decode mp3 on all platforms; the loader falls back to `librosa`/`audioread`,
  which needs `ffmpeg`).
- **PyTorch** (installed automatically via the `beat-this` dependency) is a
  heavier install than the rest of the stack — CPU inference is fine, this is
  one-off analysis, not realtime.
- **rubberband-cli** — only needed for the production warp/time-stretch engine
  (Variant B, milestone M9). Install via your system package manager (e.g.
  `apt install rubberband-cli` / `brew install rubberband`). It is GPL-licensed
  and invoked as a separate process — see the license trade-off in `PLAN.md`.

## Development

```bash
uv sync --extra core --extra gui --extra dev
uv run pytest
uv run ruff check .
```

## License

MIT — see [`LICENSE`](LICENSE).
