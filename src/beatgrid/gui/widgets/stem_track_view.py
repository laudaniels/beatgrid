from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from beatgrid.audio.loader import LoadedAudio
from beatgrid.detection.transient import DriftPoint
from beatgrid.grid.model import Beat
from beatgrid.gui.widgets.anchor_item import AnchorItem
from beatgrid.gui.widgets.axes import BarAxisItem, TimeAxisItem
from beatgrid.gui.widgets.drift_overlay import DriftOverlay
from beatgrid.gui.widgets.grid_overlay import GridOverlay
from beatgrid.gui.widgets.stem_panel import StemPanel
from beatgrid.gui.widgets.waveform_item import WaveformItem
from beatgrid.project.models import Stem


class StemTrackView(QWidget):
    """One pyqtgraph plot row for a single stem: stem panel (name/mute/solo)
    + waveform + grid overlay + drift markers. X-axes of all rows are linked
    together by the caller so zoom/scroll stays in sync across stems."""

    seek_requested = Signal(float)  # stem-local seconds, from a double-click

    def __init__(self, stem: Stem, audio: LoadedAudio) -> None:
        super().__init__()
        self._stem = stem
        self._anchor_items: list[AnchorItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stem_panel = StemPanel(stem)
        layout.addWidget(self.stem_panel)

        self.bar_axis = BarAxisItem("top")
        self.plot_widget = pg.PlotWidget(
            axisItems={"bottom": TimeAxisItem("bottom"), "top": self.bar_axis}
        )
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setClipToView(True)
        self.plot_widget.getPlotItem().hideAxis("left")
        layout.addWidget(self.plot_widget)

        self.waveform_item = WaveformItem(
            self.plot_widget.getPlotItem(), audio.audio, audio.sample_rate
        )

        self.grid_overlay = GridOverlay(self.plot_widget.getPlotItem())
        self.drift_overlay = DriftOverlay(
            self.plot_widget.getPlotItem(), marker_y=0.9 * self.waveform_item.y_extent
        )

        self._playhead = pg.InfiniteLine(
            pos=0.0, angle=90, movable=False, pen=pg.mkPen("w", width=1)
        )
        self._playhead.setZValue(10)
        self.plot_widget.addItem(self._playhead, ignoreBounds=True)

        self.plot_widget.scene().sigMouseClicked.connect(self._on_scene_clicked)

    def _on_scene_clicked(self, event) -> None:
        if not event.double() or event.button() != Qt.MouseButton.LeftButton:
            return
        view_box = self.view_box()
        if not view_box.sceneBoundingRect().contains(event.scenePos()):
            return  # e.g. on the time axis below the plot
        self.seek_requested.emit(view_box.mapSceneToView(event.scenePos()).x())

    @property
    def stem(self) -> Stem:
        return self._stem

    def view_box(self) -> pg.ViewBox:
        return self.plot_widget.getPlotItem().getViewBox()

    def set_beats(self, beats: list[Beat]) -> None:
        self.grid_overlay.set_beats(beats, self._stem)

    def set_bar_numbers(self, bars: list[tuple[float, int]] | None) -> None:
        """Show bar numbers ((local downbeat time, bar) pairs) along the top,
        or hide that axis with None -- only the reference row shows them."""
        if bars is None:
            self.plot_widget.getPlotItem().hideAxis("top")
            return
        self.bar_axis.set_bars(bars)
        self.plot_widget.getPlotItem().showAxis("top")

    def set_drift_points(self, points: list[DriftPoint]) -> None:
        self.drift_overlay.set_points(points)

    def clear_drift_points(self) -> None:
        self.drift_overlay.clear()

    def add_anchor_item(self, item: pg.InfiniteLine) -> None:
        """An anchor or the downbeat marker; both are cleared together."""
        self._anchor_items.append(item)
        self.plot_widget.addItem(item)

    def clear_anchor_items(self) -> None:
        for item in self._anchor_items:
            self.plot_widget.removeItem(item)
        self._anchor_items.clear()

    def set_playhead(self, local_time_sec: float) -> None:
        self._playhead.setPos(local_time_sec)

    @property
    def playhead_time(self) -> float:
        return float(self._playhead.value())
