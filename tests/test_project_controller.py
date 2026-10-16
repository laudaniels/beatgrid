from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from beatgrid.grid.model import Anchor, BeatGrid, TimeSignature  # noqa: E402
from beatgrid.gui.controllers.project_controller import ProjectController  # noqa: E402
from beatgrid.project.models import Project, Stem, WarpRender  # noqa: E402


def _controller(*, anchors=None) -> ProjectController:
    grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=anchors or [Anchor("a1", 0.0, 0, 0, 120.0)],
        sample_rate=44100,
    )
    stem = Stem(id="s1", path=Path("s1.wav"), sample_rate=44100, duration_sec=10.0)
    project = Project(
        name="t", stems=[stem], reference_stem_id="s1", grid=grid, created_at=datetime.now()
    )
    return ProjectController(project)


def test_add_anchor_inserts_and_renumbers():
    controller = _controller()

    anchor_id = controller.add_anchor(2.0, 100.0)

    anchors = controller.project.grid.anchors
    assert [a.id for a in anchors] == ["a1", anchor_id]
    assert anchors[1].beat_index == 4  # 2.0s at 120 BPM (previous anchor's tempo) = 4 beats
    assert anchors[1].bpm == 100.0


def test_add_anchor_emits_project_changed():
    controller = _controller()
    received = []
    controller.project_changed.connect(lambda: received.append(True))

    controller.add_anchor(1.0, 120.0)

    assert received == [True]


def test_remove_anchor_renumbers_remaining():
    controller = _controller(
        anchors=[
            Anchor("a1", 0.0, 0, 0, 120.0),
            Anchor("a2", 1.0, 0, 2, 120.0),
            Anchor("a3", 3.0, 0, 8, 120.0),
        ]
    )

    controller.remove_anchor("a2")

    anchors = controller.project.grid.anchors
    assert [a.id for a in anchors] == ["a1", "a3"]
    assert anchors[1].beat_index == 6  # 3.0s / 0.5s per beat from a1


def test_remove_last_anchor_raises():
    controller = _controller()

    with pytest.raises(ValueError):
        controller.remove_anchor("a1")


def test_remove_unknown_anchor_raises():
    controller = _controller(
        anchors=[Anchor("a1", 0.0, 0, 0, 120.0), Anchor("a2", 1.0, 0, 2, 120.0)]
    )

    with pytest.raises(ValueError):
        controller.remove_anchor("does-not-exist")


def test_set_anchor_bpm_renumbers_later_anchors():
    controller = _controller(
        anchors=[Anchor("a1", 0.0, 0, 0, 120.0), Anchor("a2", 2.0, 0, 4, 120.0)]
    )

    # slow a1 down -> fewer beats elapse by the time a2's position is reached
    controller.set_anchor_bpm("a1", 60.0)

    assert controller.project.grid.anchors[1].beat_index == 2  # 2.0s / 1.0s per beat


def test_move_anchor_renumbers():
    controller = _controller(
        anchors=[Anchor("a1", 0.0, 0, 0, 120.0), Anchor("a2", 2.0, 0, 4, 120.0)]
    )

    controller.move_anchor("a2", 1.0)

    assert controller.project.grid.anchors[1].beat_index == 2  # 1.0s / 0.5s per beat


def test_cannot_undo_or_redo_initially():
    controller = _controller()
    assert controller.can_undo is False
    assert controller.can_redo is False


def test_undo_reverts_last_mutation():
    controller = _controller()
    anchor_id = controller.project.grid.anchors[0].id

    controller.set_anchor_bpm(anchor_id, 140.0)
    assert controller.project.grid.anchors[0].bpm == 140.0
    assert controller.can_undo is True

    controller.undo()

    assert controller.project.grid.anchors[0].bpm == 120.0
    assert controller.can_undo is False
    assert controller.can_redo is True


def test_redo_reapplies_undone_mutation():
    controller = _controller()
    anchor_id = controller.project.grid.anchors[0].id

    controller.set_anchor_bpm(anchor_id, 140.0)
    controller.undo()
    controller.redo()

    assert controller.project.grid.anchors[0].bpm == 140.0
    assert controller.can_redo is False


def test_new_mutation_after_undo_clears_redo_stack():
    controller = _controller()
    anchor_id = controller.project.grid.anchors[0].id

    controller.set_anchor_bpm(anchor_id, 140.0)
    controller.undo()
    assert controller.can_redo is True

    controller.set_anchor_bpm(anchor_id, 150.0)

    assert controller.can_redo is False
    assert controller.project.grid.anchors[0].bpm == 150.0


def test_undo_with_empty_stack_is_a_no_op():
    controller = _controller()
    original_bpm = controller.project.grid.anchors[0].bpm

    controller.undo()

    assert controller.project.grid.anchors[0].bpm == original_bpm


def test_undo_emits_project_changed():
    controller = _controller()
    anchor_id = controller.project.grid.anchors[0].id
    controller.set_anchor_bpm(anchor_id, 140.0)

    received = []
    controller.project_changed.connect(lambda: received.append(True))
    controller.undo()

    assert received == [True]


def test_failed_mutation_does_not_push_undo_entry():
    controller = _controller()

    with pytest.raises(ValueError):
        controller.set_anchor_bpm("does-not-exist", 140.0)

    assert controller.can_undo is False


def test_undo_spans_multiple_mutations_in_order():
    controller = _controller(
        anchors=[Anchor("a1", 0.0, 0, 0, 120.0), Anchor("a2", 2.0, 0, 4, 120.0)]
    )

    controller.set_anchor_bpm("a1", 100.0)
    controller.move_anchor("a2", 3.0)
    assert controller.project.grid.anchors[1].time_sec == 3.0

    controller.undo()
    assert controller.project.grid.anchors[1].time_sec == 2.0
    assert controller.project.grid.anchors[0].bpm == 100.0

    controller.undo()
    assert controller.project.grid.anchors[0].bpm == 120.0


def test_set_project_clears_undo_history():
    controller = _controller()
    anchor_id = controller.project.grid.anchors[0].id
    controller.set_anchor_bpm(anchor_id, 140.0)
    assert controller.can_undo is True

    new_grid = BeatGrid(
        time_signature=TimeSignature(4, 4),
        anchors=[Anchor("b1", 0.0, 0, 0, 90.0)],
        sample_rate=44100,
    )
    new_stem = Stem(id="s2", path=Path("s2.wav"), sample_rate=44100, duration_sec=5.0)
    new_project = Project(name="other", stems=[new_stem], reference_stem_id="s2", grid=new_grid)

    controller.set_project(new_project)

    assert controller.can_undo is False
    assert controller.can_redo is False


def test_add_warp_render_appends_and_emits():
    controller = _controller()
    received = []
    controller.project_changed.connect(lambda: received.append(True))
    warp_render = WarpRender(
        target_bpm=128.0, engine="pedalboard", rendered_at=datetime.now(), output_paths={}
    )

    controller.add_warp_render(warp_render)

    assert controller.project.warp_renders == [warp_render]
    assert received == [True]
