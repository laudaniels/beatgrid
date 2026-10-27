# BeatGrid

A local, visual beatgrid editor for multi-stem tracks: load up to ~10 stems of
the same song, let BeatGrid detect the tempo on the drums stem, make the grid
follow the band's live timing beat by beat, mark the first downbeat, and warp
every stem onto one constant tempo -- the track's own -- so a DAW can take it
from there. Correct everything visually and by ear with a metronome click.

See [`PLAN.md`](PLAN.md) for the full design, architecture and milestones.

## Typical workflow (e.g. for FL Studio)

1. **Load stems** (wav/flac/mp3). A stem with "drum" in its name becomes the
   reference; beats are detected on it right away (tempos above 180 BPM are
   folded to half time). A progress dialog shows loading and detection.
2. Drag the cyan **"1" marker** at the top of the reference row onto the beat
   where bar 1 starts; bar numbers along the top count from it.
3. **Snap beats**: every beat moves onto the drum hit within ±40 ms of where
   the band currently is, so the grid follows a live drummer drifting off a
   single tempo (on one test track: +125 ms by 1:30). Add anchors where the
   tempo really changes.
4. **Warp...** defaults to the track's own average tempo, rounded to 2
   decimals. Every stem is written to `<stem_dir>/warped/` (originals are
   never touched) as `<stem>_warped_<bpm>bpm.wav` (e.g.
   `Drums - Song_warped_118.54bpm.wav`), a WAV that:
   - plays at exactly that constant tempo,
   - carries the tempo in an ACID chunk (FL Studio shows it as
     "embedded" tempo when the sample is loaded),
   - has a "Bar N" cue marker on every downbeat,
   - starts with just enough silence that bar 1 lands on a whole bar, the
     same one in every stem -- drop all stems at bar 1 and they sit on the
     grid and line up with each other.
5. **Download...** in the same dialog copies the latest render to a folder
   of your choice -- by default the Windows Downloads folder when running
   under WSL, so a Windows DAW doesn't have to reach into `\\wsl$`; the
   chosen folder is remembered. **Clean up warped folder** shows how many
   warped files (and how much space) the `warped` folder holds and deletes
   them after confirmation -- only files named `*_warped*.wav` (and
   leftovers of an interrupted render), never anything else in that folder.
6. In FL Studio, pick the embedded tempo and use Stretch Pro + tempo
   automation to take the stems to any tempo.

Always warp all stems together after changing the grid or the downbeat --
a stem rendered on its own can end up a different length than the others.
Files are written under a temporary name and swapped in whole, so a DAW
that has the previous render loaded never catches a half-written file; it
may still need the sample reloaded (or dragged in again) to pick up a new
render.

## Status

Through M10 plus the work after it: stacked waveforms with a shared grid
(multi-resolution peak pyramid, so zooming stays cheap; a scrollbar pans all
rows; the view opens on the first half of the track; time shown as m:ss),
draggable anchors, automatic BPM/beat detection ("Detect", also run on
load), tempo-following beat snapping ("Snap beats"), a movable first-downbeat
marker, non-blocking warnings for inconsistent stems, proposed
cross-correlation start offsets ("Detect offsets", always confirmed by you),
mute/solo, a diagnostic "Show drift" overlay, add/remove anchors, undo/redo,
playback of the mixed stems with a sample-accurate metronome click and a
synced playhead (double-click a row to play from there), save/open projects
(`.beatgrid`), JSON grid export (schema in `docs/EXPORT_SCHEMA.md`), and
warping all stems to a fixed tempo with a choice of engine:
**rubberband-timemap**, the default, or **pedalboard**, the M8 prototype
(constant ratio per segment, crossfaded splices, no cue markers). See the
license trade-off between the two in `PLAN.md`.

The rubberband engine renders in 64-beat chunks, in parallel, joined at a
common zero crossing: Rubber Band's own timemap drifts off its keyframes
over a whole song, especially when the tempo changes beat to beat. In a
test on a real snapped drum stem, 89% of snapped beats landed within 5 ms
of the grid (a single pass: 67%), and five 8-minute stems warped in about
8 seconds. The details are in `CLAUDE.md`.

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+O` | Open project |
| `Ctrl+S` | Save project |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Delete` | Remove the selected anchor |
| `Space` | Play / pause |
| Double-click a row | Play from that position |

Click an anchor on the reference stem's row to select it (the BPM field and
nudge buttons act on whichever anchor is selected). Click a stem's name bar
to give that row half of the tracks area (the others share the rest); click
it again to restore equal heights -- this is only a view, independent of the
reference stem. Every control explains itself when hovered.

### Look and window

The app uses a dark, blue-ish theme (`src/beatgrid/gui/theme.py`) and draws
its own title bar and window outline: under WSLg, Qt's Wayland window
decorations are a fixed light grey that can't follow the theme. Drag the
title bar to move the window, double-click it (or use its middle button) to
maximise/restore, and drag an edge or corner to resize a restored window.
Tooltips are drawn inside the window they belong to, so they can't end up
off-screen.

## Running the app

```bash
uv sync --extra core --extra gui --extra warp-prototype --extra warp --extra dev
uv run python -m beatgrid.gui.app
```

Needs an actual display -- on WSL2 that means WSLg (the window opens
maximized on the largest screen) or an X server; headless environments can
still run the structural tests via
`QT_QPA_PLATFORM=offscreen uv run pytest tests/gui -m gui`.

Detection-related tests (`uv run pytest -m "not gui"`) need the `core` extra
(`uv sync --extra core`); the first run downloads and caches the Beat This!
model checkpoint (~tens of MB) from the CPJKU cloud. Warp-related tests need
the `warp-prototype` extra (pedalboard) and/or the `warp` extra
(pyrubberband, plus `rubberband` on `PATH` -- see Prerequisites); each
gracefully skips if its dependency isn't installed.

## Prerequisites

Beyond the Python dependencies installed via `uv`, a few things are expected
on your system `PATH`:

- **ffmpeg** — needed for loading `.mp3` files (`soundfile` doesn't reliably
  decode mp3 on all platforms; the loader falls back to `librosa`/`audioread`,
  which needs `ffmpeg`).
- **PyTorch** (installed automatically via the `beat-this` dependency) is a
  heavier install than the rest of the stack — CPU inference is fine, this is
  one-off analysis, not realtime.
- **Rubber Band 3.0 or newer** (the `rubberband` command) -- needed for the
  default warp engine (`rubberband-timemap`), which uses the R3 engine
  (`-3`); version 2.x doesn't have it. Ubuntu 22.04's `rubberband-cli` is
  2.0.0, so build it from source there:

  ```bash
  sudo apt install build-essential meson ninja-build pkg-config \
      libsndfile1-dev libsamplerate0-dev libfftw3-dev
  wget https://breakfastquay.com/files/releases/rubberband-4.0.0.tar.bz2
  tar xjf rubberband-4.0.0.tar.bz2 && cd rubberband-4.0.0
  meson setup build -Dbuildtype=release -Dfft=fftw -Dresampler=libsamplerate
  ninja -C build && sudo ninja -C build install && sudo ldconfig
  ```

  Rubber Band is GPL-licensed and invoked as a separate process, which is
  why it's lower license-risk for our own MIT code than the `pedalboard`
  alternative engine (GPL-3.0 as a whole) -- see the trade-off in `PLAN.md`.
  Without it, warping falls back to `pedalboard` if that's installed.
- **Audio playback under WSL2** -- PortAudio only talks ALSA, and WSLg only
  provides a PulseAudio server. Install the ALSA pulse plugin
  (`sudo apt install libasound2-plugins`) and route ALSA's default device
  to it in `~/.asoundrc`:

  ```
  pcm.!default { type pulse }
  ctl.!default { type pulse }
  ```

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
