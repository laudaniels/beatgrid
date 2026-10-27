from pathlib import Path

from beatgrid.grid.model import Anchor, BeatGrid, TimeSignature
from beatgrid.project.models import Project, Stem
from beatgrid.render.warp_output import (
    clean_warp_folder,
    copy_files,
    format_bpm,
    scan_warp_folder,
    warp_output_dir,
    warped_filename,
)


def test_bpm_in_file_names_without_trailing_zeros():
    assert format_bpm(118.54) == "118.54"
    assert format_bpm(101.5) == "101.5"
    assert format_bpm(120.0) == "120"
    assert format_bpm(118.546) == "118.55"
    assert warped_filename("Drums - Song", 118.54) == "Drums - Song_warped_118.54bpm.wav"


def test_warp_output_dir_sits_next_to_the_reference_stem(tmp_path):
    grid = BeatGrid(TimeSignature(4, 4), [Anchor("a", 0.0, 0, 0, 120.0)], 44100)
    stems = [
        Stem(id="bass", path=tmp_path / "other" / "bass.wav"),
        Stem(id="drums", path=tmp_path / "stems" / "drums.wav"),
    ]
    project = Project(name="t", stems=stems, reference_stem_id="drums", grid=grid)
    assert warp_output_dir(project) == tmp_path / "stems" / "warped"


def _write(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_scan_counts_only_warp_output(tmp_path):
    folder = tmp_path / "warped"
    _write(folder / "Drums_warped_118.54bpm.wav", 100)
    _write(folder / "Bass_warped.wav", 50)  # from before the tempo was in the name
    _write(folder / ".Vocals_warped_118.54bpm.wav.partial", 7)  # interrupted render
    _write(folder / "my notes.txt", 1000)
    _write(folder / "loop.wav", 1000)

    contents = scan_warp_folder(folder)

    assert [p.name for p in contents.files] == [
        ".Vocals_warped_118.54bpm.wav.partial",
        "Bass_warped.wav",
        "Drums_warped_118.54bpm.wav",
    ]
    assert contents.total_bytes == 157
    assert scan_warp_folder(tmp_path / "missing").files == []


def test_clean_deletes_only_warp_output_and_keeps_a_non_empty_folder(tmp_path):
    folder = tmp_path / "warped"
    _write(folder / "Drums_warped_118.54bpm.wav", 100)
    keep = _write(folder / "my notes.txt", 10)

    deleted = clean_warp_folder(folder)

    assert [p.name for p in deleted.files] == ["Drums_warped_118.54bpm.wav"]
    assert keep.exists() and folder.is_dir()


def test_clean_removes_the_folder_once_empty(tmp_path):
    folder = tmp_path / "warped"
    _write(folder / "Drums_warped_118.54bpm.wav", 100)
    clean_warp_folder(folder)
    assert not folder.exists()


def test_copy_files_reports_progress_and_tolerates_copying_onto_itself(tmp_path):
    a = _write(tmp_path / "src" / "a_warped_120bpm.wav", 5)
    b = _write(tmp_path / "src" / "b_warped_120bpm.wav", 6)
    progress = []

    copied = copy_files([a, b], tmp_path / "dest", lambda *args: progress.append(args))

    assert [p.read_bytes() for p in copied] == [b"x" * 5, b"x" * 6]
    assert progress == [(0, 2, "a_warped_120bpm.wav"), (1, 2, "b_warped_120bpm.wav"), (2, 2, "")]
    assert copy_files([a], tmp_path / "src") == [a]  # same folder: nothing to do
