from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from beatgrid.project.models import Project

WARP_DIR_NAME = "warped"
# What counts as warp output in that folder -- and the only files the
# clean-up ever deletes: renders (with or without a tempo in the name) and
# half-written leftovers of an interrupted render.
_OUTPUT_PATTERNS = ("*_warped*.wav", ".*_warped*.wav.partial")


def warp_output_dir(project: Project) -> Path:
    """Where warped stems are written: a `warped` folder next to the
    reference stem (the originals are never touched)."""
    return project.reference_stem().path.parent / WARP_DIR_NAME


def format_bpm(bpm: float) -> str:
    """A tempo the way it's written in file names: at most 2 decimals, no
    trailing zeros (118.54, 101.5, 120)."""
    return f"{bpm:.2f}".rstrip("0").rstrip(".")


def warped_filename(stem_id: str, bpm: float) -> str:
    """e.g. "Drums - Song_warped_118.54bpm.wav": the tempo in the name keeps
    renders at different tempos apart and tells a DAW (or a person) the
    tempo even where the embedded ACID tempo isn't read."""
    return f"{stem_id}_warped_{format_bpm(bpm)}bpm.wav"


@dataclass(frozen=True)
class WarpFolderContents:
    files: list[Path]
    total_bytes: int


def scan_warp_folder(folder: Path) -> WarpFolderContents:
    """The warp output files directly in `folder` (none if it doesn't exist)."""
    folder = Path(folder)
    if not folder.is_dir():
        return WarpFolderContents(files=[], total_bytes=0)
    files = sorted(
        {path for pattern in _OUTPUT_PATTERNS for path in folder.glob(pattern) if path.is_file()}
    )
    return WarpFolderContents(files=files, total_bytes=sum(p.stat().st_size for p in files))


def clean_warp_folder(folder: Path) -> WarpFolderContents:
    """Delete the warp output files in `folder` (and the folder itself if
    that leaves it empty); other files are left alone. Returns what was
    deleted."""
    contents = scan_warp_folder(folder)
    for path in contents.files:
        path.unlink()
    folder = Path(folder)
    if folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()
    return contents


def copy_files(
    paths: Sequence[Path],
    destination: Path,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[Path]:
    """Copy `paths` into the folder `destination` (created if needed),
    replacing files of the same name; `on_progress(done, total, name)` is
    called before each file and once at the end (done == total, name "")."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for done, path in enumerate(paths):
        if on_progress is not None:
            on_progress(done, len(paths), Path(path).name)
        target = destination / Path(path).name
        if not (target.exists() and target.samefile(path)):  # already there
            shutil.copy2(path, target)
        copied.append(target)
    if on_progress is not None:
        on_progress(len(paths), len(paths), "")
    return copied
