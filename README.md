# BeatGrid

A local, visual beatgrid editor for multi-stem tracks: load up to ~10 stems of
the same song, pick a reference stem (usually the kick), snap the first
downbeat exactly onto the grid, and let BeatGrid propagate that grid to every
other stem. Correct it visually and by ear with a metronome click. Optionally
warp/time-stretch all stems onto a fixed tempo (Ableton warp-marker style).

See [`PLAN.md`](PLAN.md) for the full design, architecture and milestones.

## Status

Through M10: load multiple stems, see their waveforms stacked with a shared
grid (rendered from a multi-resolution peak pyramid, so zooming stays cheap
even on long files), drag anchors on the reference stem to reposition the
grid, run automatic BPM/beat detection ("Detect"), see non-blocking warnings
when stems' sample rate/length/offset look inconsistent, propose
cross-correlation based start offsets ("Detect offsets" — always a proposal
you confirm, never applied automatically), mute/solo per stem, toggle a
diagnostic "Show drift" overlay that marks where a stem's own transients
stray from the shared grid without ever correcting it, add/remove anchors
for tracks with tempo drift, undo/redo any edit, play the mixed stems back
with mute/solo respected, a sample-accurate metronome click and a synced
playhead, save/open the full project (`.beatgrid`), export the grid as JSON
(schema in `docs/EXPORT_SCHEMA.md`), and warp all stems to a fixed tempo
("Warp..." — written to `<stem_dir>/warped/`, never touching the originals,
with a choice of engine: **rubberband-timemap**, the default production
engine, native phase-continuous piecewise warping in one pass; or
**pedalboard**, the M8 prototype, constant-ratio-per-segment with crossfaded
splices). See the license trade-off between the two engines in `PLAN.md`.

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+O` | Open project |
| `Ctrl+S` | Save project |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Delete` | Remove the selected anchor |
| `Space` | Play / pause |

Click an anchor on the reference stem's row to select it (the BPM field and
nudge buttons act on whichever anchor is selected).

## Running the app

```bash
uv sync --extra core --extra gui --extra warp-prototype --extra warp --extra dev
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
the `warp-prototype` extra (pedalboard) and/or the `warp` extra
(pyrubberband, plus `rubberband-cli` on `PATH` — see Prerequisites); each
gracefully skips if its dependency isn't installed. Warping a multi-minute
multi-stem project is slow (tens of seconds) with either engine — this
hasn't been optimized for speed yet.

## Prerequisites

Beyond the Python dependencies installed via `uv`, a few things are expected
on your system `PATH`:

- **ffmpeg** — needed for loading `.mp3` files (`soundfile` doesn't reliably
  decode mp3 on all platforms; the loader falls back to `librosa`/`audioread`,
  which needs `ffmpeg`).
- **PyTorch** (installed automatically via the `beat-this` dependency) is a
  heavier install than the rest of the stack — CPU inference is fine, this is
  one-off analysis, not realtime.
- **rubberband-cli** — needed for the default production warp/time-stretch
  engine (`rubberband-timemap`). Install via your system package manager
  (e.g. `apt install rubberband-cli` / `brew install rubberband`). It is
  GPL-licensed and invoked as a separate process, which is why it's lower
  license-risk for our own MIT code than the `pedalboard` alternative engine
  (GPL-3.0 as a whole) — see the trade-off in `PLAN.md`. Without it, warping
  falls back to `pedalboard` if that's installed.

## Development

```bash
uv sync --extra core --extra gui --extra dev
uv run pytest
uv run ruff check .
```

## Packaging

`packaging/beatgrid.spec` is a [PyInstaller](https://pyinstaller.org) spec for
a standalone executable:

```bash
uv sync --extra core --extra gui --extra dev --extra package  # add --extra warp(-prototype) if wanted
uv run pyinstaller packaging/beatgrid.spec --distpath packaging/dist
```

Read the comment at the top of that file before building with either warp
extra installed — including `pedalboard` makes the *distributed executable*
GPL-3.0-obligated as a whole (it statically links Rubber Band/FFTW/JUCE),
while `pyrubberband` doesn't have that problem (it only shells out to a
separately-installed `rubberband-cli`, which stays external even in a build).
A trial run (with every extra installed, including PyTorch) completed
PyInstaller's full dependency analysis and archive packaging without errors
— only the usual benign "missing optional module" noise every numpy/scipy/
torch build produces — but wasn't taken all the way through final linking and
a launch smoke-test, so treat it as promising rather than verified.

## License

MIT — see [`LICENSE`](LICENSE).
