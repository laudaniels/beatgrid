# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a standalone BeatGrid executable.

Build from the project root (so the `beatgrid` package and its extras are
importable from the active venv):

    uv run pyinstaller packaging/beatgrid.spec

License note — see PLAN.md for the full trade-off, this is the short
version: PyInstaller bundles whatever is importable in the environment the
build runs from.

- Beat This! and librosa (detection, the `core` extra) are MIT/ISC: no
  concerns either way.
- `pedalboard` (the `warp-prototype` extra) is a compiled Python extension
  that statically links Rubber Band, FFTW and JUCE. If it's installed when
  you build, PyInstaller bundles that compiled code directly into this
  executable, making the *whole distributed binary* GPL-3.0-obligated.
- `pyrubberband` (the `warp` extra) does NOT have that problem: it only
  shells out via subprocess to a separately-installed `rubberband-cli`
  system binary, which is not part of the Python import graph, so
  PyInstaller has no reason to bundle it. A build made with `pyrubberband`
  installed still requires end users to install `rubberband-cli`
  themselves (same as the source install) — the executable itself stays
  free of bundled GPL code.

For a distributable with no GPL exposure at all, build from a venv that has
`warp-prototype` NOT installed; the app still runs, it just won't offer
"pedalboard" in the warp-engine picker (and offers no warp engine at all if
`warp` isn't installed either, beyond grid editing and export — Variant A
is fully GPL-free either way).
"""

import os

project_root = os.path.join(SPECPATH, "..")  # noqa: F821 - SPECPATH is injected by PyInstaller
src_path = os.path.join(project_root, "src")
entry_script = os.path.join(src_path, "beatgrid", "gui", "app.py")

block_cipher = None

a = Analysis(  # noqa: F821 - PyInstaller injects its spec-file globals at exec time
    [entry_script],
    pathex=[src_path],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Detector/engine implementations are only reached via each
        # registry's conditional `try: import ...` — list them explicitly
        # so PyInstaller's static analysis doesn't need to guess.
        "beatgrid.detection.beat_this_detector",
        "beatgrid.detection.librosa_detector",
        "beatgrid.render.engines.pedalboard_stretcher",
        "beatgrid.render.engines.rubberband_timemap_stretcher",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="beatgrid",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
