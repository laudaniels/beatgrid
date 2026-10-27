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


def test_open_warp_dialog_prefills_own_average_bpm_rounded(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)  # 2 s stems
    window.controller.set_anchor_bpm(window.controller.project.grid.anchors[0].id, 95.123)

    captured = {}

    def fake_exec(self):
        captured["bpm"] = self.target_bpm
        return 0

    monkeypatch.setattr("beatgrid.gui.widgets.warp_dialog.WarpDialog.exec", fake_exec)

    window._on_open_warp_dialog()

    assert captured["bpm"] == 95.12


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
    progress_seen = []

    def fake_render_warp(*a, on_progress=None, **k):
        on_progress(0, 1, "kick")
        progress_seen.append((dialog.progress_bar.value(), dialog.render_button.isEnabled()))
        on_progress(1, 1, "")
        return fake_warp_render

    monkeypatch.setattr("beatgrid.gui.main_window.render_warp", fake_render_warp)

    dialog = WarpDialog(120.0)
    qtbot.addWidget(dialog)

    window._on_warp_requested(dialog, 130.0, "pedalboard")

    assert progress_seen == [(0, False)]  # inputs locked while rendering
    assert dialog.render_button.isEnabled()
    assert window.controller.project.warp_renders == [fake_warp_render]
    assert "Done" in dialog.status_label.text()
    assert "kick_warped.wav" in dialog.results_view.toPlainText()


def test_warp_dialog_preselects_default_engine(qtbot, monkeypatch):
    from beatgrid.gui.widgets import warp_dialog

    monkeypatch.setattr(warp_dialog, "available_engines", lambda: ["a-engine", "z-engine"])
    monkeypatch.setattr(warp_dialog, "default_engine_name", lambda: "z-engine")
    dialog = warp_dialog.WarpDialog(120.0)
    qtbot.addWidget(dialog)
    assert dialog.engine_name == "z-engine"


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


@pytest.mark.auto_detect
def test_load_stems_places_anchor_from_detection_on_drums_stem(qtbot, tmp_path, monkeypatch):
    from beatgrid.detection.base import DetectionResult

    detected_on = []

    class StubDetector:
        name = "stub"

        def detect(self, audio, sample_rate):
            detected_on.append(audio)
            return DetectionResult(bpm=999.0, beat_times=[0.0, 1.0])

    monkeypatch.setattr("beatgrid.gui.main_window.get_detector", lambda name=None: StubDetector())
    monkeypatch.setattr(
        "beatgrid.gui.main_window.propose_anchor",
        lambda beat_times, audio, sample_rate: (0.25, 101.5),
    )
    window = MainWindow()
    qtbot.addWidget(window)
    paths = []
    for name in ("Bass", "Drums"):
        path = tmp_path / f"{name}.wav"
        _write_wav(path)
        paths.append(path)
    window.load_stems(paths)

    project = window.controller.project
    assert project.reference_stem_id == "Drums"
    assert len(detected_on) == 1
    anchor = project.grid.anchors[0]
    assert anchor.time_sec == pytest.approx(0.25)
    assert anchor.sample_index == 2000  # 0.25 s at 8 kHz
    assert anchor.bpm == pytest.approx(101.5)
    assert not window.controller.can_undo


@pytest.mark.auto_detect
def test_load_stems_falls_back_to_default_bpm_when_detection_fails(qtbot, tmp_path, monkeypatch):
    def failing_detector(name=None):
        raise RuntimeError("boom")

    warnings = []
    monkeypatch.setattr("beatgrid.gui.main_window.get_detector", failing_detector)
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QMessageBox.warning", lambda *a, **k: warnings.append(a)
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    anchor = window.controller.project.grid.anchors[0]
    assert anchor.time_sec == 0.0
    assert anchor.bpm == pytest.approx(120.0)
    assert len(warnings) == 1


def test_track_seek_request_moves_playhead_and_starts_playback(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)
    window.controller.set_stem_offset("bass", 0.5)

    calls = []
    monkeypatch.setattr(window._audio_player, "play", lambda: calls.append("play"))

    # a double-click at 1.0s on bass's own timeline is project time 1.5s
    window._track_views["bass"].seek_requested.emit(1.0)

    assert window._audio_player.position_sec == pytest.approx(1.5)
    assert calls == ["play"]
    assert window.transport_bar.play_button.isChecked()
    assert window._track_views["kick"].playhead_time == pytest.approx(1.5)
    assert window._track_views["bass"].playhead_time == pytest.approx(1.0)


def test_snap_beats_nudges_beats_to_nearby_transients(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)  # anchor at 0 s, 120 BPM: beats every 0.5 s

    # beat 1 (0.5 s) has a transient 15 ms late; beats 2 and 3 have none
    # nearby (0.92 s is far too early), so they move along with the drift;
    # beat 0 is the anchor itself
    monkeypatch.setattr(
        "beatgrid.gui.main_window.detect_transients", lambda audio, sr: [0.005, 0.515, 0.92]
    )
    window._on_snap_beats()

    offsets = window.controller.project.grid.beat_offsets
    assert offsets.keys() == {1, 2, 3}
    assert offsets[1] == pytest.approx(0.015)
    assert offsets[2] == offsets[3] == pytest.approx(0.0075)
    assert window.statusBar().currentMessage() == "Snapped 1 of 4 beats to transients"
    window._on_snap_beats()  # re-snapping doesn't accumulate
    assert window.controller.project.grid.beat_offsets[1] == pytest.approx(0.015)

    window.controller.undo()
    window.controller.undo()
    assert window.controller.project.grid.beat_offsets == {}


def test_downbeat_marker_sits_on_bar_one_and_dragging_it_moves_the_bars(qtbot, tmp_path):
    from beatgrid.gui.widgets.downbeat_item import DownbeatItem

    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)  # anchor at 0 s, 120 BPM; "kick" is the reference

    def markers():
        return [i for i in window.track_views["kick"]._anchor_items if isinstance(i, DownbeatItem)]

    assert len(markers()) == 1
    assert markers()[0].value() == pytest.approx(0.0)
    bass_markers = [
        i for i in window.track_views["bass"]._anchor_items if isinstance(i, DownbeatItem)
    ]
    assert bass_markers == []  # reference row only

    markers()[0].moved.emit(0.47)  # dropped near the beat at 0.5 s

    assert window.controller.project.grid.downbeat_sec == pytest.approx(0.5)
    assert markers()[0].value() == pytest.approx(0.5)  # redrawn exactly on the beat
    beats = window.controller.project.grid.generate_beats(end_time_sec=2.0)
    assert [b.time_sec for b in beats if b.is_downbeat] == [0.5]


def test_loading_starts_zoomed_to_half_the_track_with_a_matching_scrollbar(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)  # 2 s stems

    view_box = window.track_views["kick"].view_box()
    x_min, x_max = view_box.viewRange()[0]
    assert (x_min, x_max) == (pytest.approx(0.0), pytest.approx(1.0))

    bar = window.time_scrollbar
    assert bar.isEnabled()
    assert bar.pageStep() == 1000  # 1 s visible, in ms
    assert (bar.minimum(), bar.maximum(), bar.value()) == (0, 1000, 0)


def test_scrollbar_pans_every_track_and_follows_zooming(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    window.time_scrollbar.setValue(600)
    for stem_id in ("kick", "bass"):
        x_min, x_max = window.track_views[stem_id].view_box().viewRange()[0]
        assert (x_min, x_max) == (pytest.approx(0.6), pytest.approx(1.6))

    # zooming in a track (e.g. mouse wheel) resizes and moves the handle
    window.track_views["bass"].view_box().setXRange(0.2, 0.7, padding=0)
    bar = window.time_scrollbar
    assert (bar.pageStep(), bar.value(), bar.maximum()) == (500, 200, 1500)


def test_loading_reports_progress_and_closes_the_dialog(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QProgressDialog

    labels = []
    real_set_label = QProgressDialog.setLabelText
    monkeypatch.setattr(
        QProgressDialog,
        "setLabelText",
        lambda self, text: (labels.append(text), real_set_label(self, text))[1],
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)

    assert labels == [
        "Loading kick.wav (1/2)...",
        "Loading bass.wav (2/2)...",
        "Detecting beats on kick...",
    ]
    assert not any(
        isinstance(w, QProgressDialog) and w.isVisible()
        for w in window.findChildren(QProgressDialog)
    )


class _FakeSettings:
    store: dict = {}

    def __init__(self, *_args):
        pass

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):  # noqa: N802 - Qt API
        self.store[key] = value


def _window_with_a_render(qtbot, tmp_path, monkeypatch):
    """A loaded project whose latest warp render has two real files in
    <stems>/warped, plus an unrelated file that must never be touched."""
    from datetime import datetime

    from beatgrid.gui.widgets.warp_dialog import WarpDialog
    from beatgrid.project.models import WarpRender

    monkeypatch.setattr("beatgrid.gui.main_window.QSettings", _FakeSettings)
    _FakeSettings.store = {}
    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)
    warped = tmp_path / "warped"
    warped.mkdir()
    outputs = {}
    for stem_id in ("kick", "bass"):
        outputs[stem_id] = warped / f"{stem_id}_warped_120bpm.wav"
        outputs[stem_id].write_bytes(b"x" * 1000)
    (warped / "keep me.txt").write_text("not warp output")
    window.controller.add_warp_render(
        WarpRender(120.0, "rubberband-timemap", datetime.now(), outputs)
    )
    dialog = WarpDialog(120.0, parent=window)
    qtbot.addWidget(dialog)
    window._refresh_warp_files(dialog)
    return window, dialog, warped


def test_warp_dialog_shows_folder_contents_and_enables_download(qtbot, tmp_path, monkeypatch):
    _window, dialog, _warped = _window_with_a_render(qtbot, tmp_path, monkeypatch)

    assert dialog.cleanup_button.isEnabled()
    assert dialog.cleanup_button.text() == "Clean up warped folder (2 files, 2 KB)..."
    assert dialog.download_button.isEnabled()


def test_download_copies_the_latest_render_and_remembers_the_folder(qtbot, tmp_path, monkeypatch):
    window, dialog, _warped = _window_with_a_render(qtbot, tmp_path, monkeypatch)
    destination = tmp_path / "Downloads"
    destination.mkdir()
    asked = []
    monkeypatch.setattr("beatgrid.gui.main_window.default_download_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "beatgrid.gui.main_window.QFileDialog.getExistingDirectory",
        lambda *args: asked.append(args[2]) or str(destination),
    )

    window._on_download_warped(dialog)

    assert sorted(p.name for p in destination.iterdir()) == [
        "bass_warped_120bpm.wav",
        "kick_warped_120bpm.wav",
    ]
    assert asked == [str(tmp_path)]
    assert _FakeSettings.store["download_dir"] == str(destination)
    assert "Downloaded 2 files" in dialog.status_label.text()

    window._on_download_warped(dialog)  # second time starts in the remembered folder
    assert asked[-1] == str(destination)


def test_clean_up_asks_first_and_deletes_only_warp_output(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    window, dialog, warped = _window_with_a_render(qtbot, tmp_path, monkeypatch)

    monkeypatch.setattr(
        "beatgrid.gui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )
    window._on_clean_warp_folder(dialog)
    assert len(list(warped.iterdir())) == 3  # declined: nothing deleted

    monkeypatch.setattr(
        "beatgrid.gui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    window._on_clean_warp_folder(dialog)

    assert [p.name for p in warped.iterdir()] == ["keep me.txt"]
    assert dialog.cleanup_button.text() == "Clean up warped folder (empty)"
    assert not dialog.cleanup_button.isEnabled()
    assert not dialog.download_button.isEnabled()  # the latest render's files are gone


def test_clicking_a_name_bar_enlarges_that_row_and_clicking_again_restores(qtbot, tmp_path):
    from PySide6.QtCore import Qt

    window = MainWindow()
    qtbot.addWidget(window)
    paths = []
    for name in ("kick", "bass", "keys", "vox"):
        path = tmp_path / f"{name}.wav"
        _write_wav(path)
        paths.append(path)
    window.load_stems(paths)
    layout = window._tracks_layout

    def stretches():
        return {sid: layout.stretch(layout.indexOf(v)) for sid, v in window.track_views.items()}

    qtbot.mouseClick(window.track_views["bass"].stem_panel, Qt.MouseButton.LeftButton)
    # bass weighs as much as the other three together: half the height
    assert stretches() == {"kick": 1, "bass": 3, "keys": 1, "vox": 1}
    assert window.track_views["bass"].stem_panel.name_label.font().bold()
    assert window.controller.project.reference_stem_id == "kick"  # focus != reference

    qtbot.mouseClick(window.track_views["keys"].stem_panel, Qt.MouseButton.LeftButton)
    assert stretches() == {"kick": 1, "bass": 1, "keys": 3, "vox": 1}

    qtbot.mouseClick(window.track_views["keys"].stem_panel, Qt.MouseButton.LeftButton)
    assert set(stretches().values()) == {1}
    assert not window.track_views["keys"].stem_panel.name_label.font().bold()


def test_mute_checkbox_click_does_not_change_the_focus(qtbot, tmp_path):
    from PySide6.QtCore import Qt

    window = MainWindow()
    qtbot.addWidget(window)
    _load_two_stems(window, tmp_path)
    window.show()
    qtbot.waitExposed(window)  # laid out, so the click lands on the checkbox
    panel = window.track_views["bass"].stem_panel

    qtbot.mouseClick(panel.mute_checkbox, Qt.MouseButton.LeftButton)

    assert panel.mute_checkbox.isChecked()
    assert window._focused_stem_id is None
