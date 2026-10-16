from __future__ import annotations

import copy
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from beatgrid.grid.model import Anchor
from beatgrid.project.models import Project, Stem, WarpRender

MAX_UNDO_DEPTH = 50


class ProjectController(QObject):
    """Mediates between the Project model and the GUI widgets. Widgets never
    mutate the model directly — they call a method here, which emits
    `project_changed` so every view redraws from the single shared model.

    Undo/redo works by snapshotting the whole Project (a plain dataclass
    tree with no Qt objects, so a deepcopy is cheap and simple) before each
    mutation, rather than recording per-operation inverse commands — correct
    by construction and much less code for a project this size.
    """

    project_changed = Signal()

    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project
        self._undo_stack: list[Project] = []
        self._redo_stack: list[Project] = []

    @property
    def project(self) -> Project:
        return self._project

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._project)
        self._project = self._undo_stack.pop()
        self.project_changed.emit()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._project)
        self._project = self._redo_stack.pop()
        self.project_changed.emit()

    def _push_undo(self) -> None:
        self._undo_stack.append(copy.deepcopy(self._project))
        if len(self._undo_stack) > MAX_UNDO_DEPTH:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def set_project(self, project: Project) -> None:
        """Replace the project wholesale (e.g. loading a different one) —
        not an undoable edit, and it clears any undo/redo history from the
        previous project."""
        self._project = project
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.project_changed.emit()

    def _anchor(self, anchor_id: str) -> Anchor:
        for anchor in self._project.grid.anchors:
            if anchor.id == anchor_id:
                return anchor
        raise ValueError(f"anchor {anchor_id!r} not found")

    def move_anchor(self, anchor_id: str, new_time_sec: float) -> None:
        self._anchor(anchor_id)  # raises if unknown, before touching the undo stack
        reference = self._project.reference_stem()
        self._push_undo()
        anchor = self._anchor(anchor_id)
        anchor.time_sec = max(0.0, new_time_sec)
        anchor.sample_index = round(anchor.time_sec * reference.sample_rate)
        self._project.grid.renumber_anchors()
        self._project.grid.beat_offsets.clear()  # snapped to the old grid
        self.project_changed.emit()

    def nudge_anchor(self, anchor_id: str, delta_sec: float) -> None:
        anchor = self._anchor(anchor_id)
        self.move_anchor(anchor_id, anchor.time_sec + delta_sec)

    def set_anchor_bpm(self, anchor_id: str, bpm: float) -> None:
        self._anchor(anchor_id)  # raises if unknown, before touching the undo stack
        self._push_undo()
        self._anchor(anchor_id).bpm = bpm
        self._project.grid.renumber_anchors()
        self._project.grid.beat_offsets.clear()  # snapped to the old grid
        self.project_changed.emit()

    def add_anchor(self, time_sec: float, bpm: float) -> str:
        """Insert a new anchor at time_sec with a local bpm estimate;
        beat_index is recomputed for every anchor (renumber_anchors) so bar/
        beat numbering stays continuous. Returns the new anchor's id."""
        reference = self._project.reference_stem()
        time_sec = max(0.0, time_sec)
        self._push_undo()
        anchor = Anchor(
            id=f"anchor-{uuid4().hex[:8]}",
            time_sec=time_sec,
            sample_index=round(time_sec * reference.sample_rate),
            beat_index=0,  # placeholder; renumber_anchors fixes this below
            bpm=bpm,
        )
        self._project.grid.anchors.append(anchor)
        self._project.grid.renumber_anchors()
        self._project.grid.beat_offsets.clear()  # snapped to the old grid
        self.project_changed.emit()
        return anchor.id

    def remove_anchor(self, anchor_id: str) -> None:
        if len(self._project.grid.anchors) <= 1:
            raise ValueError("cannot remove the last remaining anchor")
        self._anchor(anchor_id)  # raises if unknown
        self._push_undo()
        self._project.grid.anchors = [a for a in self._project.grid.anchors if a.id != anchor_id]
        self._project.grid.renumber_anchors()
        self._project.grid.beat_offsets.clear()  # snapped to the old grid
        self.project_changed.emit()

    def set_beat_offsets(self, offsets: dict[int, float]) -> None:
        self._push_undo()
        self._project.grid.beat_offsets = dict(offsets)
        self.project_changed.emit()

    def set_reference_stem(self, stem_id: str) -> None:
        if stem_id not in {stem.id for stem in self._project.stems}:
            raise ValueError(f"stem {stem_id!r} not in project")
        self._push_undo()
        self._project.reference_stem_id = stem_id
        self.project_changed.emit()

    def _stem(self, stem_id: str) -> Stem:
        for stem in self._project.stems:
            if stem.id == stem_id:
                return stem
        raise ValueError(f"stem {stem_id!r} not found")

    def set_stem_muted(self, stem_id: str, muted: bool) -> None:
        self._stem(stem_id)  # raises if unknown, before touching the undo stack
        self._push_undo()
        self._stem(stem_id).muted = muted
        self.project_changed.emit()

    def set_stem_solo(self, stem_id: str, solo: bool) -> None:
        self._stem(stem_id)  # raises if unknown, before touching the undo stack
        self._push_undo()
        self._stem(stem_id).solo = solo
        self.project_changed.emit()

    def set_stem_offset(self, stem_id: str, start_offset_sec: float) -> None:
        self._stem(stem_id)  # raises if unknown, before touching the undo stack
        self._push_undo()
        self._stem(stem_id).start_offset_sec = start_offset_sec
        self.project_changed.emit()

    def add_warp_render(self, warp_render: WarpRender) -> None:
        self._push_undo()
        self._project.warp_renders.append(warp_render)
        self.project_changed.emit()
