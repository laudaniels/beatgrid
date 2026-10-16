from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from beatgrid.audio.loader import LoadedAudio, load_audio
from beatgrid.grid.model import Anchor, BeatGrid, TimeSignature
from beatgrid.grid.timeline import project_time_to_stem_time
from beatgrid.gui.controllers.project_controller import ProjectController
from beatgrid.gui.widgets.anchor_item import AnchorItem
from beatgrid.gui.widgets.stem_track_view import StemTrackView
from beatgrid.gui.widgets.transport_bar import TransportBar
from beatgrid.project.models import Project, Stem

DEFAULT_BPM = 120.0


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BeatGrid")
        self.resize(1200, 700)

        self._controller: ProjectController | None = None
        self._track_views: dict[str, StemTrackView] = {}
        self._audio: dict[str, LoadedAudio] = {}

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

        toolbar.addWidget(QLabel(" Reference stem: "))
        self.reference_combo = QComboBox()
        self.reference_combo.currentTextChanged.connect(self._on_reference_changed)
        toolbar.addWidget(self.reference_combo)

    def _build_central_widget(self) -> None:
        tracks_container = QWidget()
        self._tracks_layout = QVBoxLayout(tracks_container)
        self._tracks_layout.setContentsMargins(4, 4, 4, 4)
        self._tracks_layout.setSpacing(2)
        self._tracks_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(tracks_container)
        self._tracks_container = tracks_container

        self.transport_bar = TransportBar()
        self.transport_bar.bpm_changed.connect(self._on_bpm_changed)
        self.transport_bar.nudge_requested.connect(self._on_nudge)

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll_area)
        wrapper_layout.addWidget(self.transport_bar)
        self.setCentralWidget(wrapper)

    def _on_load_stems(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Load stems", "", "Audio files (*.wav *.flac *.mp3)"
        )
        if paths:
            self.load_stems([Path(p) for p in paths])

    def load_stems(self, paths: list[Path]) -> None:
        """Load the given audio files as stems of a new project: one default
        anchor at t=0, the first stem as reference. GUI entry point for the
        MVP flow; also used directly by tests without a file dialog."""
        audio_by_id: dict[str, LoadedAudio] = {}
        stems: list[Stem] = []
        for path in paths:
            loaded = load_audio(path)
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

        grid = BeatGrid(
            time_signature=TimeSignature(4, 4),
            anchors=[
                Anchor(id="anchor-0", time_sec=0.0, sample_index=0, beat_index=0, bpm=DEFAULT_BPM)
            ],
            sample_rate=stems[0].sample_rate,
        )
        project = Project(
            name="Untitled",
            stems=stems,
            reference_stem_id=stems[0].id,
            grid=grid,
            created_at=datetime.now(),
        )

        self._audio = audio_by_id
        self._controller = ProjectController(project)
        self._controller.project_changed.connect(self._redraw)
        self._build_track_views()
        self._redraw()

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
            self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, view)
            self._track_views[stem.id] = view
            self.reference_combo.addItem(stem.id)

            if reference_view_box is None:
                reference_view_box = view.view_box()
            else:
                view.view_box().setXLink(reference_view_box)

        self.reference_combo.setCurrentText(self._controller.project.reference_stem_id)
        self.reference_combo.blockSignals(False)

    def _redraw(self) -> None:
        assert self._controller is not None
        project = self._controller.project
        reference_stem = project.reference_stem()
        anchor = project.grid.anchors[0]
        beats = project.grid.generate_beats(end_time_sec=reference_stem.duration_sec)

        for stem_id, view in self._track_views.items():
            view.set_beats(beats)
            view.clear_anchor_item()
            if stem_id == project.reference_stem_id:
                anchor_local_time = project_time_to_stem_time(anchor.time_sec, reference_stem)
                item = AnchorItem(anchor.id, anchor_local_time)
                item.position_changed.connect(self._on_anchor_moved)
                view.set_anchor_item(item)

        self.transport_bar.set_bpm(anchor.bpm)
        self.transport_bar.set_sample_rate(reference_stem.sample_rate)

    def _on_anchor_moved(self, anchor_id: str, new_local_time_sec: float) -> None:
        assert self._controller is not None
        reference_stem = self._controller.project.reference_stem()
        project_time = new_local_time_sec + reference_stem.start_offset_sec
        self._controller.move_anchor(anchor_id, project_time)

    def _on_bpm_changed(self, bpm: float) -> None:
        if self._controller is None:
            return
        anchor_id = self._controller.project.grid.anchors[0].id
        self._controller.set_anchor_bpm(anchor_id, bpm)

    def _on_nudge(self, delta_sec: float) -> None:
        if self._controller is None:
            return
        anchor_id = self._controller.project.grid.anchors[0].id
        self._controller.nudge_anchor(anchor_id, delta_sec)

    def _on_reference_changed(self, stem_id: str) -> None:
        if self._controller is None or not stem_id:
            return
        if stem_id != self._controller.project.reference_stem_id:
            self._controller.set_reference_stem(stem_id)
