from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from beatgrid.grid.model import Anchor, BeatGrid, TimeSignature
from beatgrid.project.models import Project, Stem, WarpRender


def save_project(project: Project, path: Path) -> None:
    Path(path).write_text(json.dumps(asdict(project), indent=2, default=_json_default))


def load_project(path: Path) -> Project:
    data = json.loads(Path(path).read_text())
    return _project_from_dict(data)


def _json_default(obj: object) -> str:
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _project_from_dict(data: dict) -> Project:
    return Project(
        name=data["name"],
        stems=[_stem_from_dict(s) for s in data["stems"]],
        reference_stem_id=data["reference_stem_id"],
        grid=_grid_from_dict(data["grid"]),
        warp_renders=[_warp_render_from_dict(w) for w in data["warp_renders"]],
        created_at=datetime.fromisoformat(data["created_at"]),
        app_version=data["app_version"],
    )


def _stem_from_dict(data: dict) -> Stem:
    return Stem(
        id=data["id"],
        path=Path(data["path"]),
        role=data["role"],
        sample_rate=data["sample_rate"],
        channels=data["channels"],
        duration_sec=data["duration_sec"],
        start_offset_sec=data["start_offset_sec"],
        derived_kick=data["derived_kick"],
        muted=data.get("muted", False),
        solo=data.get("solo", False),
    )


def _grid_from_dict(data: dict) -> BeatGrid:
    return BeatGrid(
        time_signature=TimeSignature(**data["time_signature"]),
        anchors=[Anchor(**a) for a in data["anchors"]],
        sample_rate=data["sample_rate"],
        # JSON object keys are strings; older projects have no offsets
        beat_offsets={int(k): v for k, v in data.get("beat_offsets", {}).items()},
        downbeat_sec=data.get("downbeat_sec"),
    )


def _warp_render_from_dict(data: dict) -> WarpRender:
    return WarpRender(
        target_bpm=data["target_bpm"],
        engine=data["engine"],
        rendered_at=datetime.fromisoformat(data["rendered_at"]),
        output_paths={k: Path(v) for k, v in data["output_paths"].items()},
    )
