from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

PRE_ROLL_SEC = 0.1
# Set to the full path of the rubberband executable to override the lookup.
RUBBERBAND_ENV = "BEATGRID_RUBBERBAND"


def find_rubberband() -> str | None:
    """The Rubber Band command-line program: $BEATGRID_RUBBERBAND, then
    `rubberband` on PATH, then (Windows) a per-user install under
    %LOCALAPPDATA%\\Programs\\rubberband. It's a separately installed GPL
    program, never bundled with BeatGrid (see PLAN.md's license note)."""
    override = os.environ.get(RUBBERBAND_ENV)
    if override and Path(override).is_file():
        return override
    found = shutil.which("rubberband")
    if found:
        return found
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "rubberband"
        for candidate in sorted(local.glob("**/rubberband.exe")):
            return str(candidate)
    return None


class RubberbandTimemapStretcher:
    """M9 production warp engine: Rubber Band's native timemap support --
    one phase-continuous call per chunk. Runs the separately installed
    `rubberband` command-line program as a subprocess ("mere aggregation",
    lower GPL exposure for our own MIT code than Pedalboard, M8's prototype
    engine -- see PLAN.md's license trade-off). Uses the R3 ("Finer") engine.

    Calls rubberband directly rather than via pyrubberband: that one hands
    the audio over as 16-bit WAV (we use 32-bit float) and, on Windows,
    flashes a console window for every call (we suppress it).
    """

    name = "rubberband-timemap"

    def stretch_with_timemap(
        self, audio: np.ndarray, sample_rate: int, timemap: list[tuple[int, int]]
    ) -> np.ndarray:
        # Rubber Band renders the timemap's first segment unstretched
        # (measured: a render starting on a hit at ratio 0.989 put every later
        # hit (1 - 0.989) x first-segment-length late, ~5.6 ms per beat).
        # A silent, genuinely unstretched pre-roll makes that first segment
        # harmless; it's cut off again afterwards.
        pre = int(round(PRE_ROLL_SEC * sample_rate))
        padded = np.concatenate([np.zeros(pre, dtype=np.float32), audio.astype(np.float32)])
        padded_map = [(0, 0), (pre, pre)] + [
            (s + pre, t + pre) for s, t in timemap if (s, t) != (0, 0)
        ]
        return _timemap_stretch(padded, sample_rate, padded_map)[pre:]


def _timemap_stretch(
    audio: np.ndarray, sample_rate: int, timemap: list[tuple[int, int]]
) -> np.ndarray:
    """`rubberband -3 --time <total ratio> --timemap <file>` on `audio`, with
    the same keyframe conventions as pyrubberband.timemap_stretch: (source,
    target) sample pairs, non-negative and monotonic, the last pair's source
    equal to len(audio)."""
    if any(s < 0 or t < 0 for s, t in timemap):
        raise ValueError("timemap must be non-negative")
    if any(a[0] > b[0] or a[1] > b[1] for a, b in zip(timemap, timemap[1:], strict=False)):
        raise ValueError("timemap is not monotonic")
    if timemap[-1][0] != len(audio):
        raise ValueError("timemap's last source frame must equal the audio length")
    executable = find_rubberband()
    if executable is None:
        raise RuntimeError(
            "Rubber Band (the `rubberband` program) isn't installed -- see the README's "
            "Prerequisites."
        )

    with tempfile.TemporaryDirectory(prefix="beatgrid-rb-") as folder:
        source = Path(folder) / "in.wav"
        target = Path(folder) / "out.wav"
        keyframes = Path(folder) / "timemap.txt"
        sf.write(source, audio, sample_rate, subtype="FLOAT")
        keyframes.write_text("".join(f"{s} {t}\n" for s, t in timemap))
        ratio = timemap[-1][1] / timemap[-1][0]
        command = [executable, "-q", "-3", "--time", repr(ratio), "--timemap", str(keyframes)]
        try:
            subprocess.run(
                [*command, str(source), str(target)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode(errors="replace").strip().splitlines()[-1:] or [""]
            raise RuntimeError(f"rubberband failed: {detail[0]}") from exc
        stretched, _ = sf.read(target, dtype="float32", always_2d=False)
    return np.asarray(stretched, dtype=np.float32).reshape(-1)
