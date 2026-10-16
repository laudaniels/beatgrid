from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from beatgrid.audio.loader import LoadedAudio
from beatgrid.grid.model import Beat
from beatgrid.gui.widgets.anchor_item import AnchorItem
from beatgrid.gui.widgets.grid_overlay import GridOverlay
from beatgrid.project.models import Stem


class StemTrackView(QWidget):
    """One pyqtgraph plot row for a single stem: waveform + grid overlay.
    X-axes of all rows are linked together by the caller so zoom/scroll stays
    in sync across stems."""

    def __init__(self, stem: Stem, audio: LoadedAudio) -> None:
        super().__init__()
        self._stem = stem
        self._anchor_item: AnchorItem | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(f"{stem.role} — {stem.path.name}"))

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setDownsampling(auto=True, mode="peak")
        self.plot_widget.setClipToView(True)
        self.plot_widget.getPlotItem().hideAxis("left")
        layout.addWidget(self.plot_widget)

        time_axis = np.arange(len(audio.audio)) / audio.sample_rate
        self.plot_widget.plot(time_axis, audio.audio, pen=pg.mkPen((100, 180, 255)))

        self.grid_overlay = GridOverlay(self.plot_widget.getPlotItem())

    @property
    def stem(self) -> Stem:
        return self._stem

    def view_box(self) -> pg.ViewBox:
        return self.plot_widget.getPlotItem().getViewBox()

    def set_beats(self, beats: list[Beat]) -> None:
        self.grid_overlay.set_beats(beats, self._stem)

    def set_anchor_item(self, item: AnchorItem) -> None:
        self._anchor_item = item
        self.plot_widget.addItem(item)

    def clear_anchor_item(self) -> None:
        if self._anchor_item is not None:
            self.plot_widget.removeItem(self._anchor_item)
            self._anchor_item = None
