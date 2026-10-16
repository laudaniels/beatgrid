from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from beatgrid.export.base import GridExporter
from beatgrid.project.models import Project

SCHEMA_VERSION = 1
GENERATOR_NAME = "beatgrid"
GENERATOR_VERSION = "0.1.0"


class JSONExporter(GridExporter):
    """Schema v1 — see docs/EXPORT_SCHEMA.md. A read-only, derived artifact
    for the grid itself; the full editable project state lives in a separate
    `.beatgrid` file (project/project_io.py)."""

    format_name = "json"
    file_extension = ".json"

    def export(self, project: Project, path: Path) -> None:
        Path(path).write_text(json.dumps(build_export_dict(project), indent=2))


def build_export_dict(project: Project) -> dict:
    reference_stem = project.reference_stem()
    beats = project.grid.generate_beats(end_time_sec=reference_stem.duration_sec)
    anchors = sorted(project.grid.anchors, key=lambda a: a.time_sec)

    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "reference_stem": {
            "id": reference_stem.id,
            "path": str(reference_stem.path),
            "sha256": _sha256_of_file(reference_stem.path),
            "sample_rate": reference_stem.sample_rate,
        },
        "time_signature": {
            "numerator": project.grid.time_signature.numerator,
            "denominator": project.grid.time_signature.denominator,
        },
        "anchors": [
            {
                "id": anchor.id,
                "time_sec": anchor.time_sec,
                "sample_index": anchor.sample_index,
                "beat_index": anchor.beat_index,
                "bpm": anchor.bpm,
            }
            for anchor in anchors
        ],
        "beats": [
            {
                "index": beat.index,
                "time_sec": beat.time_sec,
                "sample_index": beat.sample_index,
                "bar": beat.bar,
                "beat_in_bar": beat.beat_in_bar,
                "is_downbeat": beat.is_downbeat,
            }
            for beat in beats
        ],
        "created_at": datetime.now(UTC).isoformat(),
    }


def _sha256_of_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
