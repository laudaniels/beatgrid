import json
from datetime import datetime
from pathlib import Path

from beatgrid.grid.model import Anchor, BeatGrid, TimeSignature
from beatgrid.project.models import Project, Stem, WarpRender
from beatgrid.project.project_io import load_project, save_project


def _sample_project() -> Project:
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[Anchor(id="a1", time_sec=1.0, sample_index=44100, beat_index=0, bpm=128.0)],
        sample_rate=44100,
    )
    stems = [
        Stem(
            id="kick",
            path=Path("stems/kick.wav"),
            role="kick",
            sample_rate=44100,
            channels=1,
            duration_sec=180.0,
        ),
        Stem(
            id="bass",
            path=Path("stems/bass.wav"),
            role="bass",
            sample_rate=44100,
            channels=2,
            duration_sec=180.0,
            start_offset_sec=0.02,
        ),
    ]
    return Project(
        name="Test Track",
        stems=stems,
        reference_stem_id="kick",
        grid=grid,
        warp_renders=[
            WarpRender(
                target_bpm=128.0,
                engine="rubberband-timemap",
                rendered_at=datetime(2026, 1, 1, 12, 0, 0),
                output_paths={"kick": Path("warped/kick_warped.wav")},
            )
        ],
    )


def test_save_and_load_project_roundtrip(tmp_path):
    project = _sample_project()
    path = tmp_path / "test.beatgrid"

    save_project(project, path)
    loaded = load_project(path)

    assert loaded.name == project.name
    assert loaded.reference_stem_id == project.reference_stem_id
    assert [s.id for s in loaded.stems] == [s.id for s in project.stems]
    assert loaded.stems[1].start_offset_sec == 0.02
    assert loaded.grid.anchors[0].bpm == 128.0
    assert loaded.warp_renders[0].output_paths["kick"] == Path("warped/kick_warped.wav")
    assert loaded.reference_stem().id == "kick"


def test_save_produces_readable_json(tmp_path):
    path = tmp_path / "test.beatgrid"
    save_project(_sample_project(), path)

    data = json.loads(path.read_text())
    assert data["name"] == "Test Track"
    assert data["grid"]["anchors"][0]["bpm"] == 128.0
