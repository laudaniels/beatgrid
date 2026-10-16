import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

from beatgrid.export.base import GridExporter
from beatgrid.export.json_exporter import JSONExporter, build_export_dict
from beatgrid.export.registry import available_formats, get_exporter, register
from beatgrid.grid.model import Anchor, BeatGrid, TimeSignature
from beatgrid.project.models import Project, Stem


def _project_with_real_file(tmp_path: Path) -> Project:
    audio = np.zeros(44100, dtype=np.float32)
    path = tmp_path / "kick.wav"
    sf.write(path, audio, 44100)

    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[Anchor(id="a1", time_sec=0.0, sample_index=0, beat_index=0, bpm=120.0)],
        sample_rate=44100,
    )
    stem = Stem(id="kick", path=path, role="kick", sample_rate=44100, channels=1, duration_sec=1.0)
    return Project(name="Test", stems=[stem], reference_stem_id="kick", grid=grid)


def test_build_export_dict_matches_schema_v1(tmp_path):
    project = _project_with_real_file(tmp_path)

    data = build_export_dict(project)

    assert data["schema_version"] == 1
    assert data["generator"]["name"] == "beatgrid"
    assert data["reference_stem"]["id"] == "kick"
    assert data["reference_stem"]["path"] == str(project.reference_stem().path)
    assert data["reference_stem"]["sample_rate"] == 44100

    expected_hash = hashlib.sha256(project.reference_stem().path.read_bytes()).hexdigest()
    assert data["reference_stem"]["sha256"] == expected_hash

    assert data["time_signature"] == {"numerator": 4, "denominator": 4}

    assert len(data["anchors"]) == 1
    assert data["anchors"][0]["id"] == "a1"
    assert data["anchors"][0]["bpm"] == 120.0

    # 120 BPM over 1.0s -> beats at 0.0 and 0.5
    assert [b["time_sec"] for b in data["beats"]] == [0.0, 0.5]
    assert data["beats"][0]["is_downbeat"] is True
    assert data["beats"][0]["bar"] == 1
    assert data["beats"][0]["beat_in_bar"] == 1

    datetime.fromisoformat(data["created_at"])  # must be a valid ISO 8601 timestamp


def test_anchors_are_exported_sorted_by_time(tmp_path):
    project = _project_with_real_file(tmp_path)
    # deliberately out of order relative to time
    project.grid.anchors = [
        Anchor(id="late", time_sec=0.5, sample_index=0, beat_index=1, bpm=120.0),
        Anchor(id="early", time_sec=0.0, sample_index=0, beat_index=0, bpm=120.0),
    ]

    data = build_export_dict(project)

    assert [a["id"] for a in data["anchors"]] == ["early", "late"]


def test_json_exporter_writes_a_readable_file(tmp_path):
    project = _project_with_real_file(tmp_path)
    out_path = tmp_path / "grid.json"

    JSONExporter().export(project, out_path)

    data = json.loads(out_path.read_text())
    assert data["schema_version"] == 1
    assert len(data["beats"]) == 2


def test_json_exporter_is_a_grid_exporter():
    exporter = JSONExporter()
    assert isinstance(exporter, GridExporter)
    assert exporter.format_name == "json"
    assert exporter.file_extension == ".json"


def test_registry_default_contains_json():
    assert "json" in available_formats()
    assert isinstance(get_exporter("json"), JSONExporter)


def test_registry_unknown_format_raises():
    import pytest

    with pytest.raises(ValueError):
        get_exporter("does-not-exist")


def test_registry_register_custom_exporter(tmp_path):
    class DummyExporter(GridExporter):
        format_name = "dummy"
        file_extension = ".dummy"

        def export(self, project: Project, path: Path) -> None:
            Path(path).write_text("dummy")

    register("dummy", DummyExporter)

    assert "dummy" in available_formats()
    exporter = get_exporter("dummy")
    assert isinstance(exporter, DummyExporter)

    out_path = tmp_path / "out.dummy"
    exporter.export(_project_with_real_file(tmp_path), out_path)
    assert out_path.read_text() == "dummy"
