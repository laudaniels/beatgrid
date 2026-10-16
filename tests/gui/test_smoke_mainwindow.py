from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtWidgets import QMessageBox

from beatgrid.gui.main_window import MainWindow

pytestmark = pytest.mark.gui


def _write_wav(path: Path, duration_sec: float = 2.0, sample_rate: int = 8000) -> None:
    t = np.arange(int(duration_sec * sample_rate)) / sample_rate
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, audio, sample_rate)


def _load_two_stems(window: MainWindow, tmp_path: Path) -> None:
    paths = []
    for name in ("kick", "bass"):
        path = tmp_path / f"{name}.wav"
        _write_wav(path)
        paths.append(path)
    window.load_stems(paths)


def test_main_window_builds_without_crashing(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "BeatGrid"
    assert window.controller is None


def test_loading_stems_builds_one_row_per_stem(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)

    _load_two_stems(window, tmp_path)

    assert len(window.track_views) == 2
    assert window.reference_combo.count() == 2
    assert window.controller is not None
    assert window.controller.project.reference_stem_id == "kick"


def test_every_row_gets_grid_lines(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)

    _load_two_stems(window, tmp_path)

    for view in window.track_views.values():
        assert view.grid_overlay.line_count > 0


def test_moving_anchor_updates_grid_on_all_rows(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)

    _load_two_stems(window, tmp_path)
    anchor_id = window.controller.project.grid.anchors[0].id

    window._on_anchor_moved(anchor_id, 0.5)

    assert window.controller.project.grid.anchors[0].time_sec == pytest.approx(0.5)
    for view in window.track_views.values():
        assert view.grid_overlay.line_count > 0


def test_bpm_change_updates_anchor(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)

    _load_two_stems(window, tmp_path)

    window._on_bpm_changed(140.0)

    assert window.controller.project.grid.anchors[0].bpm == 140.0


def test_nudge_moves_anchor_by_requested_delta(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)

    _load_two_stems(window, tmp_path)
    initial_time = window.controller.project.grid.anchors[0].time_sec

    window._on_nudge(0.01)

    assert window.controller.project.grid.anchors[0].time_sec == pytest.approx(initial_time + 0.01)


def test_changing_reference_stem_updates_project(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)

    _load_two_stems(window, tmp_path)
    window.reference_combo.setCurrentText("bass")

    assert window.controller.project.reference_stem_id == "bass"


def test_detect_action_updates_anchor_from_detector_result(qtbot, tmp_path, monkeypatch):
    # Stubs out both the detector and the refine step so this test needs only
    # PySide6 — no librosa/beat-this (and their heavier dependencies) required
    # just to check the GUI wiring.
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    from beatgrid.detection.base import DetectionResult

    class StubDetector:
        name = "stub"

        def detect(self, audio, sample_rate):
            return DetectionResult(bpm=999.0, beat_times=[0.0, 1.0])

    monkeypatch.setattr("beatgrid.gui.main_window.get_detector", lambda name=None: StubDetector())
    monkeypatch.setattr(
        "beatgrid.gui.main_window.propose_anchor",
        lambda beat_times, audio, sample_rate: (0.25, 140.0),
    )

    window._on_detect()

    anchor = window.controller.project.grid.anchors[0]
    assert anchor.bpm == pytest.approx(140.0)
    assert anchor.time_sec == pytest.approx(0.25)


def test_mute_checkbox_updates_stem_state(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    view = window.track_views["kick"]
    view.stem_panel.mute_checkbox.setChecked(True)

    stem = next(s for s in window.controller.project.stems if s.id == "kick")
    assert stem.muted is True


def test_solo_checkbox_updates_stem_state(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    view = window.track_views["bass"]
    view.stem_panel.solo_checkbox.setChecked(True)

    stem = next(s for s in window.controller.project.stems if s.id == "bass")
    assert stem.solo is True


def test_validation_warning_shown_for_mismatched_stems(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)

    warned = {}
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QMessageBox.warning",
        lambda self, title, text: warned.update(title=title, text=text),
    )

    kick_path = tmp_path / "kick.wav"
    bass_path = tmp_path / "bass.wav"
    _write_wav(kick_path, duration_sec=2.0, sample_rate=8000)
    _write_wav(bass_path, duration_sec=2.0, sample_rate=16000)  # mismatched sample rate

    window.load_stems([kick_path, bass_path])

    assert warned.get("title") == "Stem validation warnings"
    assert "sample rate" in warned.get("text", "")


def test_detect_offsets_applies_proposal_on_confirmation(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    monkeypatch.setattr("beatgrid.gui.main_window.detect_offset", lambda *a, **k: 0.123)
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )

    window._on_detect_offsets()

    bass_stem = next(s for s in window.controller.project.stems if s.id == "bass")
    assert bass_stem.start_offset_sec == pytest.approx(0.123)


def test_detect_offsets_does_not_apply_without_confirmation(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    monkeypatch.setattr("beatgrid.gui.main_window.detect_offset", lambda *a, **k: 0.123)
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )

    window._on_detect_offsets()

    bass_stem = next(s for s in window.controller.project.stems if s.id == "bass")
    assert bass_stem.start_offset_sec == 0.0


def test_toggle_drift_populates_and_clears_overlays(qtbot, tmp_path, monkeypatch):
    # Stub out detect_transients so this needs only PySide6, not librosa.
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    monkeypatch.setattr(
        "beatgrid.gui.main_window.detect_transients", lambda audio, sample_rate: [0.01, 0.52]
    )

    window.drift_action.setChecked(True)
    for view in window.track_views.values():
        assert view.drift_overlay.point_count > 0

    window.drift_action.setChecked(False)
    for view in window.track_views.values():
        assert view.drift_overlay.point_count == 0


def test_add_anchor_inserts_at_view_center_with_local_bpm(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    from beatgrid.detection.base import DetectionResult

    class StubDetector:
        name = "stub"

        def detect(self, audio, sample_rate):
            return DetectionResult(bpm=1.0, beat_times=[0.0, 1.0])

    monkeypatch.setattr("beatgrid.gui.main_window.get_detector", lambda name=None: StubDetector())
    monkeypatch.setattr(
        "beatgrid.gui.main_window.propose_anchor", lambda beat_times, audio, sr: (0.0, 130.0)
    )

    reference_view = window.track_views["kick"]
    reference_view.view_box().setXRange(0.4, 0.6, padding=0)  # center ~0.5s

    window._on_add_anchor()

    anchors = window.controller.project.grid.anchors
    assert len(anchors) == 2
    new_anchor = anchors[1]
    assert new_anchor.time_sec == pytest.approx(0.5, abs=0.05)
    assert new_anchor.bpm == 130.0
    assert window._selected_anchor_id == new_anchor.id


def test_remove_selected_anchor(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    second_id = window.controller.add_anchor(1.0, 120.0)
    window._selected_anchor_id = second_id

    window._on_remove_anchor()

    remaining_ids = [a.id for a in window.controller.project.grid.anchors]
    assert second_id not in remaining_ids
    assert len(remaining_ids) == 1


def test_cannot_remove_last_remaining_anchor(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)
    monkeypatch.setattr("beatgrid.gui.main_window.QMessageBox.information", lambda *a, **k: None)

    window._on_remove_anchor()

    assert len(window.controller.project.grid.anchors) == 1


def test_clicking_anchor_selects_it_and_updates_bpm_display(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    second_id = window.controller.add_anchor(1.0, 140.0)

    window._on_anchor_selected(second_id)

    assert window._selected_anchor_id == second_id
    assert window.transport_bar.bpm_spinbox.value() == pytest.approx(140.0)


def test_detect_action_shows_warning_on_failure(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    def _boom(name=None):
        raise RuntimeError("detector exploded")

    monkeypatch.setattr("beatgrid.gui.main_window.get_detector", _boom)
    monkeypatch.setattr("beatgrid.gui.main_window.QMessageBox.warning", lambda *a, **k: None)

    original_bpm = window.controller.project.grid.anchors[0].bpm
    window._on_detect()  # must not raise or crash

    assert window.controller.project.grid.anchors[0].bpm == original_bpm


def test_loading_stems_creates_a_player_with_stems_and_metronome(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    assert window._audio_player is not None
    assert window._audio_player.metronome is not None  # on by default


def test_play_toggle_starts_and_stops_player_without_opening_a_real_device(
    qtbot, tmp_path, monkeypatch
):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    calls = []
    monkeypatch.setattr(window._audio_player, "play", lambda: calls.append("play"))
    monkeypatch.setattr(window._audio_player, "stop", lambda: calls.append("stop"))

    window.transport_bar.play_button.setChecked(True)
    assert calls == ["play"]
    assert window.transport_bar.play_button.text() == "Pause"
    assert window._playhead_timer.isActive()

    window.transport_bar.play_button.setChecked(False)
    assert calls == ["play", "stop"]
    assert window.transport_bar.play_button.text() == "Play"
    assert not window._playhead_timer.isActive()


def test_metronome_checkbox_enables_and_disables_click(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    window.transport_bar.metronome_checkbox.setChecked(False)
    assert window._audio_player.metronome is None

    window.transport_bar.metronome_checkbox.setChecked(True)
    assert window._audio_player.metronome is not None


def test_mute_solo_changes_propagate_to_the_player(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    window.track_views["kick"].stem_panel.mute_checkbox.setChecked(True)

    from beatgrid.gui.playback.audio_player import select_active_stems

    active_ids = {s.stem_id for s in select_active_stems(window._audio_player.stems)}
    assert active_ids == {"bass"}


def test_update_playhead_positions_accounts_for_stem_offset(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    kick_stem = next(s for s in window.controller.project.stems if s.id == "kick")
    window._controller.set_stem_offset("bass", 0.1)
    window._audio_player.seek(0.5)

    window._update_playhead_positions()

    assert window.track_views["kick"].playhead_time == pytest.approx(
        0.5 - kick_stem.start_offset_sec
    )
    assert window.track_views["bass"].playhead_time == pytest.approx(0.4)


def test_save_then_open_project_restores_grid_state(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    anchor_id = window.controller.project.grid.anchors[0].id
    window.controller.move_anchor(anchor_id, 0.3)
    window.controller.set_anchor_bpm(anchor_id, 135.0)
    window.controller.set_stem_muted("bass", True)

    project_path = tmp_path / "project.beatgrid"
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(project_path), ""),
    )
    window._on_save_project()
    assert project_path.exists()

    reopened = MainWindow()
    qtbot.addWidget(reopened)
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(project_path), ""),
    )
    reopened._on_open_project()

    anchor = reopened.controller.project.grid.anchors[0]
    assert anchor.time_sec == pytest.approx(0.3)
    assert anchor.bpm == pytest.approx(135.0)
    bass_stem = next(s for s in reopened.controller.project.stems if s.id == "bass")
    assert bass_stem.muted is True


def test_load_stems_shows_warning_on_failure_instead_of_crashing(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)

    bad_path = tmp_path / "corrupt.wav"
    bad_path.write_bytes(b"not actually audio")
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QFileDialog.getOpenFileNames",
        lambda *a, **k: ([str(bad_path)], ""),
    )
    warned = []
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QMessageBox.warning",
        lambda *a, **k: warned.append(True),
    )

    window._on_load_stems()  # must not raise

    assert warned == [True]
    assert window.controller is None  # load never completed


def test_open_project_shows_warning_on_failure(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)

    missing_path = tmp_path / "does-not-exist.beatgrid"
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(missing_path), ""),
    )
    warned = []
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QMessageBox.warning",
        lambda *a, **k: warned.append(True),
    )

    window._on_open_project()  # must not raise

    assert warned == [True]


def test_export_grid_writes_json(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    export_path = tmp_path / "grid.json"
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(export_path), ""),
    )

    window._on_export_grid()

    import json

    data = json.loads(export_path.read_text())
    assert data["schema_version"] == 1
    assert data["reference_stem"]["id"] == "kick"


def test_open_warp_dialog_prefills_default_bpm_from_first_anchor(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)
    window.controller.set_anchor_bpm(window.controller.project.grid.anchors[0].id, 95.0)

    captured = {}

    def fake_exec(self):
        captured["bpm"] = self.target_bpm
        return 0

    monkeypatch.setattr("beatgrid.gui.widgets.warp_dialog.WarpDialog.exec", fake_exec)

    window._on_open_warp_dialog()

    assert captured["bpm"] == pytest.approx(95.0)


def test_warp_requested_success_adds_warp_render_and_shows_result(qtbot, tmp_path, monkeypatch):
    from datetime import datetime

    from beatgrid.gui.widgets.warp_dialog import WarpDialog
    from beatgrid.project.models import WarpRender

    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    fake_warp_render = WarpRender(
        target_bpm=130.0,
        engine="pedalboard",
        rendered_at=datetime.now(),
        output_paths={"kick": tmp_path / "kick_warped.wav"},
    )
    monkeypatch.setattr("beatgrid.gui.main_window.get_engine", lambda name=None: object())
    monkeypatch.setattr("beatgrid.gui.main_window.render_warp", lambda *a, **k: fake_warp_render)

    dialog = WarpDialog(120.0)
    qtbot.addWidget(dialog)

    window._on_warp_requested(dialog, 130.0, "pedalboard")

    assert window.controller.project.warp_renders == [fake_warp_render]
    assert "Done" in dialog.status_label.text()


def test_warp_requested_failure_shows_error_in_dialog(qtbot, tmp_path, monkeypatch):
    from beatgrid.gui.widgets.warp_dialog import WarpDialog

    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    def _boom(*a, **k):
        raise ValueError("no anchors to warp from")

    monkeypatch.setattr("beatgrid.gui.main_window.get_engine", lambda name=None: object())
    monkeypatch.setattr("beatgrid.gui.main_window.render_warp", _boom)

    dialog = WarpDialog(120.0)
    qtbot.addWidget(dialog)

    window._on_warp_requested(dialog, 130.0, "pedalboard")

    assert window.controller.project.warp_renders == []
    assert "Failed" in dialog.status_label.text()


def test_playhead_tick_stops_itself_when_player_is_not_playing(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    window.transport_bar.set_playing(True)  # simulate UI state without really playing
    window._playhead_timer.start()

    window._on_playhead_tick()  # _audio_player.is_playing is False: .play() was never called

    assert window.transport_bar.play_button.isChecked() is False
    assert not window._playhead_timer.isActive()


def test_undo_redo_actions_disabled_before_any_edit(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    assert window.undo_action.isEnabled() is False
    assert window.redo_action.isEnabled() is False


def test_undo_action_reverts_last_edit_and_updates_enabled_state(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    window._on_bpm_changed(140.0)
    assert window.undo_action.isEnabled() is True

    window._on_undo()

    assert window.controller.project.grid.anchors[0].bpm == 120.0
    assert window.undo_action.isEnabled() is False
    assert window.redo_action.isEnabled() is True


def test_redo_action_reapplies_undone_edit(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    window._on_bpm_changed(140.0)
    window._on_undo()
    window._on_redo()

    assert window.controller.project.grid.anchors[0].bpm == 140.0
    assert window.redo_action.isEnabled() is False


def test_remove_anchor_action_has_delete_shortcut(qtbot, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence

    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    assert window.remove_anchor_action.shortcut() == QKeySequence(Qt.Key.Key_Delete)


def test_play_pause_shortcut_toggles_play_button(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    calls = []
    monkeypatch.setattr(window._audio_player, "play", lambda: calls.append("play"))
    monkeypatch.setattr(window._audio_player, "stop", lambda: calls.append("stop"))

    window._on_play_pause_shortcut()
    assert calls == ["play"]

    window._on_play_pause_shortcut()
    assert calls == ["play", "stop"]
