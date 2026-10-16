from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from beatgrid.grid.model import BeatGrid


@dataclass
class Stem:
    id: str
    path: Path
    role: str = "other"
    sample_rate: int = 0
    channels: int = 0
    duration_sec: float = 0.0
    start_offset_sec: float = 0.0
    derived_kick: bool = False
    muted: bool = False
    solo: bool = False


@dataclass
class WarpRender:
    target_bpm: float
    engine: str
    rendered_at: datetime
    output_paths: dict[str, Path] = field(default_factory=dict)


@dataclass
class Project:
    name: str
    stems: list[Stem]
    reference_stem_id: str
    grid: BeatGrid
    warp_renders: list[WarpRender] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    app_version: str = "0.1.0"

    def reference_stem(self) -> Stem:
        for stem in self.stems:
            if stem.id == self.reference_stem_id:
                return stem
        raise ValueError(f"reference_stem_id {self.reference_stem_id!r} not found in stems")
