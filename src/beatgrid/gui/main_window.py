from __future__ import annotations

import copy
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_for
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QScrollArea,
    QScrollBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from beatgrid.audio.loader import LoadedAudio, load_audio
from beatgrid.audio.offset_detection import detect_offset
from beatgrid.audio.validation import validate_stems
from beatgrid.detection.refine import propose_anchor
from beatgrid.detection.registry import available_detectors, get_detector
from beatgrid.detection.transient import compute_drift, detect_transients
from beatgrid.export.registry import get_exporter
from beatgrid.grid.model import Anchor, Beat, BeatGrid, TimeSignature, average_bpm
from beatgrid.grid.snap import snap_offsets
from beatgrid.grid.timeline import project_time_to_stem_time, stem_time_to_project_time
from beatgrid.gui.controllers.project_controller import ProjectController
from beatgrid.gui.playback.audio_player import AudioPlayer, PlaybackStem
from beatgrid.gui.playback.metronome import build_metronome
from beatgrid.gui.widgets.anchor_item import AnchorItem
from beatgrid.gui.widgets.downbeat_item import DownbeatItem
from beatgrid.gui.widgets.stem_track_view import StemTrackView
from beatgrid.gui.widgets.transport_bar import TransportBar
from beatgrid.gui.widgets.warp_dialog import WarpDialog
from beatgrid.project.models import Project, Stem, default_reference_stem_id
from beatgrid.project.project_io import load_project, save_project
from beatgrid.render.engines.registry import get_engine
from beatgrid.render.warp_renderer import render_warp

DEFAULT_BPM = 120.0
DRIFT_THRESHOLD_SEC = 0.02
INITIAL_VIEW_FRACTION = 0.5  # show the first half of the track after loading
SNAP_TOLERANCE_SEC = 0.04  # around where the band currently is, see grid/snap.py
PLAYHEAD_TIMER_INTERVAL_MS = 33  # ~30Hz


T = TypeVar("T")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BeatGrid")
        self.resize(1200, 700)

        self._controller: ProjectController | None = None
        self._track_views: dict[str, StemTrackView] = {}
        self._audio: dict[str, LoadedAudio] = {}
        self._transients_by_stem: dict[str, list[float]] = {}
        self._show_drift = False
        self._selected_anchor_id: str | None = None
        self._audio_player: AudioPlayer | None = None
        self._current_project_path: Path | None = None
        self._time_view_box = None  # the reference track's view box; all rows link to it

        self._playhead_timer = QTimer(self)
        self._playhead_timer.setInterval(PLAYHEAD_TIMER_INTERVAL_MS)
        self._playhead_timer.timeout.connect(self._on_playhead_tick)

        self._build_toolbar()
        self._build_central_widget()

    @property
    def controller(self) -> ProjectController | None:
        return self._controller

    @property
    def track_views(self) -> dict[str, StemTrackView]:
        return self._track_views

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        load_action = QAction("Load stems...", self)
        load_action.triggered.connect(self._on_load_stems)
        toolbar.addAction(load_action)

        open_project_action = QAction("Open project...", self)
        open_project_action.setShortcut(QKeySequence.StandardKey.Open)
        open_project_action.triggered.connect(self._on_open_project)
        toolbar.addAction(open_project_action)

        save_project_action = QAction("Save project...", self)
        save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        save_project_action.triggered.connect(self._on_save_project)
        toolbar.addAction(save_project_action)

        export_action = QAction("Export grid...", self)
        export_action.triggered.connect(self._on_export_grid)
        toolbar.addAction(export_action)

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setEnabled(False)
        self.undo_action.triggered.connect(self._on_undo)
        toolbar.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setEnabled(False)
        self.redo_action.triggered.connect(self._on_redo)
        toolbar.addAction(self.redo_action)

        toolbar.addWidget(QLabel(" Reference stem: "))
        self.reference_combo = QComboBox()
        self.reference_combo.currentTextChanged.connect(self._on_reference_changed)
        toolbar.addWidget(self.reference_combo)

        toolbar.addWidget(QLabel(" Detector: "))
        self.detector_combo = QComboBox()
        self.detector_combo.addItems(available_detectors())
        toolbar.addWidget(self.detector_combo)

        detect_action = QAction("Detect", self)
        detect_action.triggered.connect(self._on_detect)
        toolbar.addAction(detect_action)

        detect_offsets_action = QAction("Detect offsets", self)
        detect_offsets_action.triggered.connect(self._on_detect_offsets)
        toolbar.addAction(detect_offsets_action)

        self.drift_action = QAction("Show drift", self)
        self.drift_action.setCheckable(True)
        self.drift_action.toggled.connect(self._on_toggle_drift)
        toolbar.addAction(self.drift_action)

        snap_beats_action = QAction("Snap beats", self)
        snap_beats_action.setToolTip(
            "Make the grid follow the band: snap every beat to a transient on the "
            f"reference stem (within ±{SNAP_TOLERANCE_SEC * 1000:.0f} ms of the band's "
            "current timing)"
        )
        snap_beats_action.triggered.connect(self._on_snap_beats)
        toolbar.addAction(snap_beats_action)

        add_anchor_action = QAction("Add anchor", self)
        add_anchor_action.setToolTip(
            "Add a new anchor at the center of the reference stem's current view"
        )
        add_anchor_action.triggered.connect(self._on_add_anchor)
        toolbar.addAction(add_anchor_action)

        self.remove_anchor_action = QAction("Remove anchor", self)
        self.remove_anchor_action.setToolTip(
            "Remove the selected anchor (click an anchor to select it)"
        )
        self.remove_anchor_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.remove_anchor_action.triggered.connect(self._on_remove_anchor)
        toolbar.addAction(self.remove_anchor_action)

        warp_action = QAction("Warp...", self)
        warp_action.setToolTip("Warp/time-stretch all stems to a fixed tempo (prototype engine)")
        warp_action.triggered.connect(self._on_open_warp_dialog)
        toolbar.addAction(warp_action)

        self.play_pause_action = QAction("Play/Pause", self)
        self.play_pause_action.setShortcut(QKeySequence(Qt.Key.Key_Space))
        self.play_pause_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.play_pause_action.triggered.connect(self._on_play_pause_shortcut)
        self.addAction(self.play_pause_action)  # no toolbar button; shortcut only

    def _build_central_widget(self) -> None:
        tracks_container = QWidget()
        self._tracks_layout = QVBoxLayout(tracks_container)
        self._tracks_layout.setContentsMargins(4, 4, 4, 4)
        self._tracks_layout.setSpacing(2)
        self._tracks_layout.addStretch(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(tracks_container)
        self._tracks_container = tracks_container

        self.transport_bar = TransportBar()
        self.transport_bar.bpm_changed.connect(self._on_bpm_changed)
        self.transport_bar.nudge_requested.connect(self._on_nudge)
        self.transport_bar.play_toggled.connect(self._on_play_toggled)
        self.transport_bar.metronome_toggled.connect(self._on_metronome_toggled)

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll_area)
        # scrolls the (linked) time axis of every track at once
        self.time_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self.time_scrollbar.setEnabled(False)
        self.time_scrollbar.valueChanged.connect(self._on_time_scrolled)
        wrapper_layout.addWidget(self.time_scrollbar)
        wrapper_layout.addWidget(self.transport_bar)
        self.setCentralWidget(wrapper)

    def _on_load_stems(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Load stems", "", "Audio files (*.wav *.flac *.mp3)"
        )
        if not paths:
            return
        try:
            self.load_stems([Path(p) for p in paths])
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            QMessageBox.warning(self, "Could not load stems", str(exc))

    def load_stems(self, paths: list[Path]) -> None:
        """Load the given audio files as stems of a new project: a drums stem
        (if any, else the first) as reference, and one anchor placed by
        running the selected detector on it. GUI entry point for the MVP
        flow; also used directly by tests without a file dialog."""
        audio_by_id: dict[str, LoadedAudio] = {}
        stems: list[Stem] = []
        progress = self._start_progress("Loading stems", len(paths))
        for i, path in enumerate(paths):
            progress.setLabelText(f"Loading {path.name} ({i + 1}/{len(paths)})...")
            progress.setValue(i)
            try:
                loaded = self._in_background(load_audio, path)
            except Exception:
                progress.close()
                raise
            stem_id = path.stem
            stems.append(
                Stem(
                    id=stem_id,
                    path=path,
                    sample_rate=loaded.sample_rate,
                    channels=1,
                    duration_sec=len(loaded.audio) / loaded.sample_rate,
                )
            )
            audio_by_id[stem_id] = loaded

        reference_stem_id = default_reference_stem_id(stems)
        reference_audio = audio_by_id[reference_stem_id]
        progress.setLabelText(f"Detecting beats on {reference_stem_id}...")
        progress.setRange(0, 0)  # busy indicator: detection can't report progress
        try:
            anchor_time, bpm = self._detect_initial_anchor(reference_audio)
        finally:
            progress.close()
        grid = BeatGrid(
            time_signature=TimeSignature(4, 4),
            anchors=[
                Anchor(
                    id="anchor-0",
                    time_sec=anchor_time,
                    sample_index=round(anchor_time * reference_audio.sample_rate),
                    beat_index=0,
                    bpm=bpm,
                )
            ],
            sample_rate=stems[0].sample_rate,
        )
        project = Project(
            name="Untitled",
            stems=stems,
            reference_stem_id=reference_stem_id,
            grid=grid,
            created_at=datetime.now(),
        )
        self._current_project_path = None
        self._activate_project(project, audio_by_id)

    def _detect_initial_anchor(self, audio: LoadedAudio) -> tuple[float, float]:
        """(anchor_time, bpm) for a freshly loaded project, the same way the
        Detect action computes it. Falls back to t=0 at DEFAULT_BPM (with a
        warning) if detection fails, so loading itself never fails on it."""
        detector_name = self.detector_combo.currentText()

        def detect() -> tuple[float, float]:
            result = get_detector(detector_name).detect(audio.audio, audio.sample_rate)
            return propose_anchor(result.beat_times, audio.audio, audio.sample_rate)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            return self._in_background(detect)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            QMessageBox.warning(
                self,
                "Detection failed",
                f"{exc}\n\nGrid set to {DEFAULT_BPM:g} BPM; use Detect to retry.",
            )
            return 0.0, DEFAULT_BPM
        finally:
            QApplication.restoreOverrideCursor()

    def open_project(self, path: Path) -> None:
        """Load a previously saved .beatgrid project file: re-reads each
        stem's audio from its stored path and restores the full grid
        (anchors, offsets, mute/solo) exactly as saved."""
        project = load_project(path)
        audio_by_id: dict[str, LoadedAudio] = {}
        progress = self._start_progress("Opening project", len(project.stems))
        try:
            for i, stem in enumerate(project.stems):
                progress.setLabelText(f"Loading {stem.path.name} ({i + 1}/{len(project.stems)})...")
                progress.setValue(i)
                audio_by_id[stem.id] = self._in_background(load_audio, stem.path)
        finally:
            progress.close()
        self._current_project_path = path
        self._activate_project(project, audio_by_id)

    def _start_progress(self, title: str, steps: int) -> QProgressDialog:
        progress = QProgressDialog("", None, 0, steps, self)  # no cancel button
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setMinimumWidth(420)
        progress.setValue(0)
        return progress

    @staticmethod
    def _in_background(fn: Callable[..., T], *args: object) -> T:
        """Run fn(*args) on a worker thread while keeping the GUI responsive
        (progress dialogs repaint, busy bars animate); re-raises its error."""
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn, *args)
            while not future.done():
                QApplication.processEvents()
                wait_for([future], timeout=0.03)
            return future.result()

    def _activate_project(self, project: Project, audio_by_id: dict[str, LoadedAudio]) -> None:
        warnings = validate_stems(project.stems, reference_stem_id=project.reference_stem_id)

        if self._audio_player is not None:
            self._audio_player.stop()
        self._playhead_timer.stop()
        self.transport_bar.set_playing(False)

        self._audio = audio_by_id
        self._transients_by_stem = {}
        self._show_drift = False
        self._selected_anchor_id = project.grid.anchors[0].id
        self._audio_player = AudioPlayer(sample_rate=project.grid.sample_rate)
        self.drift_action.blockSignals(True)
        self.drift_action.setChecked(False)
        self.drift_action.blockSignals(False)
        self._controller = ProjectController(project)
        self._controller.project_changed.connect(self._redraw)
        self._build_track_views()
        self._redraw()
        self._show_initial_view()

        if warnings:
            text = "\n".join(f"{w.stem_id}: {w.message}" for w in warnings)
            QMessageBox.warning(self, "Stem validation warnings", text)

    def _build_track_views(self) -> None:
        assert self._controller is not None

        for view in self._track_views.values():
            self._tracks_layout.removeWidget(view)
            view.setParent(None)
        self._track_views.clear()

        self.reference_combo.blockSignals(True)
        self.reference_combo.clear()

        reference_view_box = None
        for stem in self._controller.project.stems:
            view = StemTrackView(stem, self._audio[stem.id])
            view.stem_panel.muted_changed.connect(self._on_stem_muted)
            view.stem_panel.solo_changed.connect(self._on_stem_solo)
            view.seek_requested.connect(self._make_seek_handler(stem.id))
            # stretch 1: rows share any extra height (the trailing stretch has 0)
            self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, view, 1)
            self._track_views[stem.id] = view
            self.reference_combo.addItem(stem.id)

            if reference_view_box is None:
                reference_view_box = view.view_box()
            else:
                view.view_box().setXLink(reference_view_box)

        self._time_view_box = reference_view_box
        if reference_view_box is not None:
            reference_view_box.sigXRangeChanged.connect(self._sync_time_scrollbar)

        self.reference_combo.setCurrentText(self._controller.project.reference_stem_id)
        self.reference_combo.blockSignals(False)

    def _timeline_end_sec(self) -> float:
        """Where the last stem ends on the project timeline."""
        assert self._controller is not None
        return max(
            stem.start_offset_sec + stem.duration_sec for stem in self._controller.project.stems
        )

    def _show_initial_view(self) -> None:
        if self._time_view_box is None:
            return
        self._time_view_box.setXRange(
            0.0, self._timeline_end_sec() * INITIAL_VIEW_FRACTION, padding=0
        )
        self.time_scrollbar.setEnabled(True)
        self._sync_time_scrollbar()

    def _sync_time_scrollbar(self, *_args: object) -> None:
        """Mirror the visible time range (after zooming/panning in a track)
        in the scrollbar: handle size = visible span, position = its start.
        Units are milliseconds."""
        if self._time_view_box is None or self._controller is None:
            return
        x_min, x_max = self._time_view_box.viewRange()[0]
        visible_ms = max(1, round((x_max - x_min) * 1000))
        end_ms = round(self._timeline_end_sec() * 1000)
        self.time_scrollbar.blockSignals(True)
        self.time_scrollbar.setRange(0, max(0, end_ms - visible_ms))
        self.time_scrollbar.setPageStep(visible_ms)
        self.time_scrollbar.setSingleStep(max(1, visible_ms // 10))
        self.time_scrollbar.setValue(round(x_min * 1000))
        self.time_scrollbar.blockSignals(False)

    def _on_time_scrolled(self, value_ms: int) -> None:
        if self._time_view_box is None:
            return
        x_min, x_max = self._time_view_box.viewRange()[0]
        start = value_ms / 1000
        self._time_view_box.setXRange(start, start + (x_max - x_min), padding=0)

    def _redraw(self) -> None:
        assert self._controller is not None
        project = self._controller.project
        reference_stem = project.reference_stem()
        beats = project.grid.generate_beats(end_time_sec=reference_stem.duration_sec)

        if self._selected_anchor_id not in {a.id for a in project.grid.anchors}:
            self._selected_anchor_id = project.grid.anchors[0].id
        selected_id = self._selected_anchor_id

        for stem_id, view in self._track_views.items():
            view.set_beats(beats)
            view.clear_anchor_items()
            view.set_bar_numbers(None)
            if stem_id == project.reference_stem_id:
                view.set_bar_numbers(
                    [
                        (project_time_to_stem_time(b.time_sec, reference_stem), b.bar)
                        for b in beats
                        if b.is_downbeat
                    ]
                )
                for anchor in project.grid.anchors:
                    anchor_local_time = project_time_to_stem_time(anchor.time_sec, reference_stem)
                    item = AnchorItem(
                        anchor.id, anchor_local_time, is_selected=anchor.id == selected_id
                    )
                    item.position_changed.connect(self._on_anchor_moved)
                    item.selected.connect(self._on_anchor_selected)
                    view.add_anchor_item(item)
                first_downbeat = next((b for b in beats if b.bar == 1 and b.is_downbeat), None)
                if first_downbeat is not None:
                    marker = DownbeatItem(
                        project_time_to_stem_time(first_downbeat.time_sec, reference_stem)
                    )
                    marker.moved.connect(self._on_downbeat_moved)
                    view.add_anchor_item(marker)

            if self._show_drift:
                stem = next(s for s in project.stems if s.id == stem_id)
                local_beat_times = [project_time_to_stem_time(b.time_sec, stem) for b in beats]
                transients = self._transients_by_stem.get(stem_id, [])
                points = compute_drift(
                    transients, local_beat_times, threshold_sec=DRIFT_THRESHOLD_SEC
                )
                view.set_drift_points(points)

        selected_anchor = self._find_anchor(selected_id)
        if selected_anchor is not None:
            self.transport_bar.set_bpm(selected_anchor.bpm)
        self.transport_bar.set_sample_rate(reference_stem.sample_rate)

        self.undo_action.setEnabled(self._controller.can_undo)
        self.redo_action.setEnabled(self._controller.can_redo)

        self._refresh_player(beats)

    def _refresh_player(self, beats: list[Beat]) -> None:
        if self._audio_player is None:
            return
        project = self._controller.project
        reference_stem = project.reference_stem()

        playback_stems = [
            PlaybackStem(
                stem_id=stem.id,
                audio=self._audio[stem.id].audio,
                start_offset_sec=stem.start_offset_sec,
                muted=stem.muted,
                solo=stem.solo,
            )
            for stem in project.stems
        ]
        self._audio_player.set_stems(playback_stems)
        self._audio_player.set_duration(reference_stem.duration_sec)

        if self.transport_bar.metronome_checkbox.isChecked():
            self._audio_player.set_metronome(build_metronome(beats, reference_stem.sample_rate))
        else:
            self._audio_player.set_metronome(None)

    def _find_anchor(self, anchor_id: str | None) -> Anchor | None:
        if self._controller is None or anchor_id is None:
            return None
        for anchor in self._controller.project.grid.anchors:
            if anchor.id == anchor_id:
                return anchor
        return None

    def _on_anchor_moved(self, anchor_id: str, new_local_time_sec: float) -> None:
        assert self._controller is not None
        reference_stem = self._controller.project.reference_stem()
        project_time = new_local_time_sec + reference_stem.start_offset_sec
        self._selected_anchor_id = anchor_id
        self._controller.move_anchor(anchor_id, project_time)

    def _on_downbeat_moved(self, new_local_time_sec: float) -> None:
        assert self._controller is not None
        reference_stem = self._controller.project.reference_stem()
        self._controller.set_downbeat(stem_time_to_project_time(new_local_time_sec, reference_stem))

    def _on_anchor_selected(self, anchor_id: str) -> None:
        if self._selected_anchor_id == anchor_id:
            return
        self._selected_anchor_id = anchor_id
        anchor = self._find_anchor(anchor_id)
        if anchor is not None:
            self.transport_bar.set_bpm(anchor.bpm)

    def _on_bpm_changed(self, bpm: float) -> None:
        if self._controller is None or self._selected_anchor_id is None:
            return
        self._controller.set_anchor_bpm(self._selected_anchor_id, bpm)

    def _on_nudge(self, delta_sec: float) -> None:
        if self._controller is None or self._selected_anchor_id is None:
            return
        self._controller.nudge_anchor(self._selected_anchor_id, delta_sec)

    def _on_reference_changed(self, stem_id: str) -> None:
        if self._controller is None or not stem_id:
            return
        if stem_id != self._controller.project.reference_stem_id:
            self._controller.set_reference_stem(stem_id)

    def _on_detect(self) -> None:
        """Run the selected detector on the reference stem, refine its raw
        beat times with our own transient-snap + linear-regression fit
        (detection.refine.propose_anchor), and move the first anchor there."""
        if self._controller is None:
            return
        project = self._controller.project
        reference_stem = project.reference_stem()
        audio = self._audio[reference_stem.id].audio

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            detector = get_detector(self.detector_combo.currentText())
            result = detector.detect(audio, reference_stem.sample_rate)
            anchor_time, bpm = propose_anchor(result.beat_times, audio, reference_stem.sample_rate)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            QMessageBox.warning(self, "Detection failed", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        anchor_id = project.grid.anchors[0].id
        self._selected_anchor_id = anchor_id
        self._controller.set_anchor_bpm(anchor_id, bpm)
        self._controller.move_anchor(anchor_id, anchor_time)

    def _on_stem_muted(self, stem_id: str, muted: bool) -> None:
        if self._controller is None:
            return
        self._controller.set_stem_muted(stem_id, muted)

    def _on_stem_solo(self, stem_id: str, solo: bool) -> None:
        if self._controller is None:
            return
        self._controller.set_stem_solo(stem_id, solo)

    def _on_detect_offsets(self) -> None:
        """Propose a start_offset_sec for every non-reference stem via
        cross-correlation against the reference, then ask for one explicit
        confirmation before applying any of them — never automatic."""
        if self._controller is None:
            return
        project = self._controller.project
        reference_stem = project.reference_stem()
        reference_audio = self._audio[reference_stem.id].audio

        proposals: dict[str, float] = {}
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for stem in project.stems:
                if stem.id == reference_stem.id:
                    continue
                try:
                    proposals[stem.id] = detect_offset(
                        reference_audio,
                        reference_stem.sample_rate,
                        self._audio[stem.id].audio,
                        stem.sample_rate,
                    )
                except ValueError as exc:
                    QMessageBox.warning(self, "Offset detection failed", f"{stem.id}: {exc}")
        finally:
            QApplication.restoreOverrideCursor()

        if not proposals:
            return

        lines = "\n".join(f"{stem_id}: {offset:+.3f}s" for stem_id, offset in proposals.items())
        answer = QMessageBox.question(
            self,
            "Apply detected offsets?",
            f"Proposed start offsets relative to {reference_stem.id}:\n\n{lines}\n\n"
            "Apply these to the project?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            for stem_id, offset in proposals.items():
                self._controller.set_stem_offset(stem_id, offset)

    def _on_toggle_drift(self, checked: bool) -> None:
        self._show_drift = checked
        if self._controller is None:
            return
        if checked:
            self._ensure_transients_cached()
        else:
            for view in self._track_views.values():
                view.clear_drift_points()
        self._redraw()

    def _on_snap_beats(self) -> None:
        """Make the grid follow the band: snap each beat onto a transient of
        the reference stem within SNAP_TOLERANCE_SEC of where the band
        currently is (grid/snap.py tracks a live drummer's drift off the
        constant-tempo grid). Anchors themselves stay put. Re-snaps from the
        unsnapped grid, so repeated presses don't accumulate."""
        if self._controller is None:
            return
        self._ensure_transients_cached()
        project = self._controller.project
        reference_stem = project.reference_stem()
        unsnapped_grid = copy.deepcopy(project.grid)
        unsnapped_grid.beat_offsets = {}
        beats = unsnapped_grid.generate_beats(end_time_sec=reference_stem.duration_sec)
        transients = [
            stem_time_to_project_time(t, reference_stem)
            for t in self._transients_by_stem.get(reference_stem.id, [])
        ]
        result = snap_offsets(
            beats,
            transients,
            max_distance_sec=SNAP_TOLERANCE_SEC,
            anchor_indices=frozenset(a.beat_index for a in project.grid.anchors),
        )
        self._controller.set_beat_offsets(result.offsets)
        self.statusBar().showMessage(
            f"Snapped {result.snapped} of {len(beats)} beats to transients", 5000
        )

    def _ensure_transients_cached(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for stem_id, loaded in self._audio.items():
                if stem_id not in self._transients_by_stem:
                    self._transients_by_stem[stem_id] = detect_transients(
                        loaded.audio, loaded.sample_rate
                    )
        finally:
            QApplication.restoreOverrideCursor()

    def _on_add_anchor(self) -> None:
        """Insert a new anchor at the center of the reference stem's current
        view, with a locally-estimated BPM (refine.py applied to just that
        segment, via _estimate_local_bpm) rather than inheriting a
        neighboring anchor's tempo wholesale."""
        if self._controller is None:
            return
        project = self._controller.project
        reference_stem = project.reference_stem()
        reference_view = self._track_views[reference_stem.id]

        x_min, x_max = reference_view.view_box().viewRange()[0]
        local_time = (x_min + x_max) / 2.0
        project_time = local_time + reference_stem.start_offset_sec

        bpm = self._estimate_local_bpm(project_time, reference_stem)
        anchor_id = self._controller.add_anchor(project_time, bpm)
        self._selected_anchor_id = anchor_id

    def _on_remove_anchor(self) -> None:
        if self._controller is None or self._selected_anchor_id is None:
            return
        if len(self._controller.project.grid.anchors) <= 1:
            QMessageBox.information(
                self, "Cannot remove anchor", "A project needs at least one anchor."
            )
            return
        try:
            self._controller.remove_anchor(self._selected_anchor_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not remove anchor", str(exc))
            return
        self._selected_anchor_id = None  # _redraw() falls back to the first remaining anchor

    def _estimate_local_bpm(self, project_time: float, reference_stem: Stem) -> float:
        """Detect tempo in a short window of audio around project_time —
        the same detection+refine pipeline as the initial anchor estimate
        (detection.refine.propose_anchor), just applied to one segment
        instead of the whole track."""
        audio = self._audio[reference_stem.id].audio
        sample_rate = reference_stem.sample_rate
        window_sec = 8.0
        center_sample = int(project_time * sample_rate)
        half_window = int(window_sec / 2 * sample_rate)
        segment = audio[max(0, center_sample - half_window) : center_sample + half_window]

        fallback_bpm = min(
            self._controller.project.grid.anchors, key=lambda a: abs(a.time_sec - project_time)
        ).bpm

        if len(segment) < sample_rate:  # too short a window to analyze meaningfully
            return fallback_bpm

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            detector = get_detector(self.detector_combo.currentText())
            result = detector.detect(segment, sample_rate)
            _anchor_time, bpm = propose_anchor(result.beat_times, segment, sample_rate)
            return bpm
        except Exception:  # noqa: BLE001 - local estimate is best-effort, never fatal
            return fallback_bpm
        finally:
            QApplication.restoreOverrideCursor()

    def _on_play_toggled(self, play: bool) -> None:
        if self._audio_player is None:
            return
        if play:
            self._audio_player.play()
            self._playhead_timer.start()
        else:
            self._audio_player.stop()
            self._playhead_timer.stop()

    def _make_seek_handler(self, stem_id: str):
        # look the stem up at click time: undo/redo and offset changes
        # replace the project's Stem objects after the view was built
        def handler(stem_time_sec: float) -> None:
            if self._controller is None:
                return
            stem = next(s for s in self._controller.project.stems if s.id == stem_id)
            self.seek_and_play(stem_time_to_project_time(stem_time_sec, stem))

        return handler

    def seek_and_play(self, project_time_sec: float) -> None:
        """Move the playhead to `project_time_sec` (double-click on a track)
        and play from there; if already playing, playback just jumps."""
        if self._audio_player is None:
            return
        self._audio_player.seek(max(0.0, project_time_sec))
        self._update_playhead_positions()
        if not self._audio_player.is_playing:
            self.transport_bar.play_button.setChecked(True)

    def _on_metronome_toggled(self, enabled: bool) -> None:
        if self._controller is None or self._audio_player is None:
            return
        if not enabled:
            self._audio_player.set_metronome(None)
            return
        project = self._controller.project
        reference_stem = project.reference_stem()
        beats = project.grid.generate_beats(end_time_sec=reference_stem.duration_sec)
        self._audio_player.set_metronome(build_metronome(beats, reference_stem.sample_rate))

    def _on_playhead_tick(self) -> None:
        if self._controller is None or self._audio_player is None:
            return
        if not self._audio_player.is_playing:
            # the track reached the end on its own -- sync the button state
            # and close the now-finished stream (must happen on this thread,
            # see AudioPlayer.cleanup_finished_stream)
            self._audio_player.cleanup_finished_stream()
            self.transport_bar.set_playing(False)
            self._playhead_timer.stop()
            return
        self._update_playhead_positions()

    def _update_playhead_positions(self) -> None:
        assert self._controller is not None
        assert self._audio_player is not None
        project_time = self._audio_player.position_sec
        for stem in self._controller.project.stems:
            view = self._track_views.get(stem.id)
            if view is not None:
                view.set_playhead(project_time_to_stem_time(project_time, stem))

    def _on_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "BeatGrid project (*.beatgrid)"
        )
        if not path:
            return
        try:
            self.open_project(Path(path))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            QMessageBox.warning(self, "Could not open project", str(exc))

    def _on_save_project(self) -> None:
        if self._controller is None:
            return
        default_path = str(
            self._current_project_path or f"{self._controller.project.name}.beatgrid"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project", default_path, "BeatGrid project (*.beatgrid)"
        )
        if not path:
            return
        try:
            save_project(self._controller.project, Path(path))
        except OSError as exc:
            QMessageBox.warning(self, "Could not save project", str(exc))
            return
        self._current_project_path = Path(path)

    def _on_export_grid(self) -> None:
        if self._controller is None:
            return
        default_path = f"{self._controller.project.name}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Export grid", default_path, "JSON (*.json)")
        if not path:
            return
        try:
            get_exporter("json").export(self._controller.project, Path(path))
        except OSError as exc:
            QMessageBox.warning(self, "Could not export grid", str(exc))

    def _on_open_warp_dialog(self) -> None:
        """Variant B: warp every stem to a fixed tempo. See
        render/warp_renderer.py for the actual algorithm (GUI-independent).
        Defaults to the M9 production engine (rubberband-timemap) when
        installed, falling back to the M8 prototype (pedalboard) otherwise —
        both are offered in the dialog's engine picker; see PLAN.md for the
        license trade-off between them."""
        if self._controller is None:
            return
        # default: the track's own overall tempo, rounded to 2 decimals so it
        # can be typed into a DAW exactly (e.g. FL Studio's Stretch Pro)
        project = self._controller.project
        reference_stem = project.reference_stem()
        beats = project.grid.generate_beats(end_time_sec=reference_stem.duration_sec)
        own_bpm = average_bpm(beats) if len(beats) >= 2 else project.grid.anchors[0].bpm
        dialog = WarpDialog(round(own_bpm, 2), parent=self)
        dialog.render_requested.connect(
            lambda bpm, engine_name: self._on_warp_requested(dialog, bpm, engine_name)
        )
        dialog.exec()

    def _on_warp_requested(self, dialog: WarpDialog, target_bpm: float, engine_name: str) -> None:
        assert self._controller is not None
        project = self._controller.project
        reference_stem = project.reference_stem()
        output_dir = reference_stem.path.parent / "warped"

        def on_progress(done: int, total: int, stem_id: str) -> None:
            dialog.show_progress(done, total, stem_id)
            QApplication.processEvents()  # repaint between (blocking) per-stem renders

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        dialog.set_busy(True)
        try:
            engine = get_engine(engine_name)
            warp_render = render_warp(
                project, target_bpm, engine, output_dir, self._audio, on_progress=on_progress
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            dialog.show_error(str(exc))
            return
        finally:
            dialog.set_busy(False)
            QApplication.restoreOverrideCursor()

        self._controller.add_warp_render(warp_render)
        dialog.show_result(warp_render.output_paths)

    def _on_undo(self) -> None:
        if self._controller is not None:
            self._controller.undo()

    def _on_redo(self) -> None:
        if self._controller is not None:
            self._controller.redo()

    def _on_play_pause_shortcut(self) -> None:
        self.transport_bar.play_button.click()
