from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from beatgrid.grid.model import Anchor
from beatgrid.project.models import Project, Stem


class ProjectController(QObject):
    """Mediates between the Project model and the GUI widgets. Widgets never
    mutate the model directly — they call a method here, which emits
    `project_changed` so every view redraws from the single shared model."""

    project_changed = Signal()

    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project

    @property
    def project(self) -> Project:
        return self._project

    def set_project(self, project: Project) -> None:
        self._project = project
        self.project_changed.emit()

    def _anchor(self, anchor_id: str) -> Anchor:
        for anchor in self._project.grid.anchors:
            if anchor.id == anchor_id:
                return anchor
        raise ValueError(f"anchor {anchor_id!r} not found")

    def move_anchor(self, anchor_id: str, new_time_sec: float) -> None:
        reference = self._project.reference_stem()
        anchor = self._anchor(anchor_id)
        anchor.time_sec = max(0.0, new_time_sec)
        anchor.sample_index = round(anchor.time_sec * reference.sample_rate)
        self.project_changed.emit()

    def nudge_anchor(self, anchor_id: str, delta_sec: float) -> None:
        anchor = self._anchor(anchor_id)
        self.move_anchor(anchor_id, anchor.time_sec + delta_sec)

    def set_anchor_bpm(self, anchor_id: str, bpm: float) -> None:
        self._anchor(anchor_id).bpm = bpm
        self.project_changed.emit()

    def set_reference_stem(self, stem_id: str) -> None:
        if stem_id not in {stem.id for stem in self._project.stems}:
            raise ValueError(f"stem {stem_id!r} not in project")
        self._project.reference_stem_id = stem_id
        self.project_changed.emit()

    def _stem(self, stem_id: str) -> Stem:
        for stem in self._project.stems:
            if stem.id == stem_id:
                return stem
        raise ValueError(f"stem {stem_id!r} not found")

    def set_stem_muted(self, stem_id: str, muted: bool) -> None:
        self._stem(stem_id).muted = muted
        self.project_changed.emit()

    def set_stem_solo(self, stem_id: str, solo: bool) -> None:
        self._stem(stem_id).solo = solo
        self.project_changed.emit()

    def set_stem_offset(self, stem_id: str, start_offset_sec: float) -> None:
        self._stem(stem_id).start_offset_sec = start_offset_sec
        self.project_changed.emit()
