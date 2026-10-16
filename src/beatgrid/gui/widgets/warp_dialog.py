from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WarpDialog(QDialog):
    """Pick a target BPM and trigger a warp render (Variant B). This is just
    the target-BPM picker + a results display — the actual rendering is
    driven by the caller (MainWindow) via `render_requested`, and the render
    logic itself lives entirely in render/warp_renderer.py, independent of
    the GUI."""

    render_requested = Signal(float)  # target_bpm

    def __init__(self, default_bpm: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Warp to a fixed tempo")

        self.bpm_spinbox = QDoubleSpinBox()
        self.bpm_spinbox.setRange(20.0, 300.0)
        self.bpm_spinbox.setDecimals(2)
        self.bpm_spinbox.setValue(default_bpm)

        form = QFormLayout()
        form.addRow("Target BPM:", self.bpm_spinbox)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        self.render_button = QPushButton("Render")
        self.render_button.clicked.connect(self._on_render_clicked)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(self.render_button)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)

    @property
    def target_bpm(self) -> float:
        return self.bpm_spinbox.value()

    def show_result(self, output_paths: dict[str, Path]) -> None:
        lines = "\n".join(f"{stem_id}: {path}" for stem_id, path in output_paths.items())
        self.status_label.setText(f"Done:\n{lines}")

    def show_error(self, message: str) -> None:
        self.status_label.setText(f"Failed: {message}")

    def _on_render_clicked(self) -> None:
        self.render_requested.emit(self.target_bpm)
