from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

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
