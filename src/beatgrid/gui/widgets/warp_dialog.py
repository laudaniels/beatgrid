from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from beatgrid.detection.refine import MAX_BPM
from beatgrid.render.engines.registry import available_engines, default_engine_name


class WarpDialog(QDialog):
    """Pick a target BPM and engine, then trigger a warp render (Variant B).
    This is just the target-BPM/engine picker + a results display — the
    actual rendering is driven by the caller (MainWindow) via
    `render_requested`, and the render logic itself lives entirely in
    render/warp_renderer.py, independent of the GUI."""

    render_requested = Signal(float, str)  # target_bpm, engine_name
    download_requested = Signal()
    cleanup_requested = Signal()

    def __init__(self, default_bpm: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Warp to a fixed tempo")
        self.setMinimumSize(720, 420)

        self.bpm_spinbox = QDoubleSpinBox()
        self.bpm_spinbox.setRange(20.0, MAX_BPM)
        self.bpm_spinbox.setDecimals(2)
        self.bpm_spinbox.setValue(default_bpm)

        self.engine_combo = QComboBox()
        self.engine_combo.addItems(available_engines())
        default_engine = default_engine_name()
        if default_engine is not None:
            self.engine_combo.setCurrentText(default_engine)

        form = QFormLayout()
        form.addRow("Target BPM:", self.bpm_spinbox)
        form.addRow("Engine:", self.engine_combo)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.results_view = QPlainTextEdit()
        self.results_view.setReadOnly(True)
        self.results_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.results_view.setVisible(False)

        self.render_button = QPushButton("Render")
        self.render_button.clicked.connect(self._on_render_clicked)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        self.download_button = QPushButton("Download...")
        self.download_button.setToolTip("Copy the latest render's files to a folder of your choice")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_requested.emit)
        self.cleanup_button = QPushButton("Clean up warped folder")
        self.cleanup_button.setEnabled(False)
        self.cleanup_button.clicked.connect(self.cleanup_requested.emit)

        files_row = QHBoxLayout()
        files_row.addWidget(self.download_button)
        files_row.addWidget(self.cleanup_button)

        buttons = QHBoxLayout()
        buttons.addWidget(self.render_button)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.results_view, 1)
        layout.addStretch(0)
        layout.addLayout(files_row)
        layout.addLayout(buttons)

    @property
    def target_bpm(self) -> float:
        return self.bpm_spinbox.value()

    @property
    def engine_name(self) -> str:
        return self.engine_combo.currentText()

    def set_busy(self, busy: bool) -> None:
        """Lock the inputs while a render runs (it pumps the event loop for
        progress updates, so the buttons would otherwise stay clickable)."""
        for widget in (self.render_button, self.close_button, self.bpm_spinbox, self.engine_combo):
            widget.setEnabled(not busy)
        if busy:
            self.download_button.setEnabled(False)
            self.cleanup_button.setEnabled(False)
        if busy:
            self.results_view.setVisible(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)

    def show_progress(self, done: int, total: int, stem_id: str) -> None:
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        if stem_id:
            self.status_label.setText(f"Warping {stem_id} ({done + 1}/{total})...")

    def show_result(self, output_paths: dict[str, Path]) -> None:
        folders = {path.parent for path in output_paths.values()}
        where = f" to {next(iter(folders))}" if len(folders) == 1 else ""
        self.status_label.setText(f"Done: {len(output_paths)} stems written{where}")
        self.results_view.setPlainText("\n".join(path.name for path in output_paths.values()))
        self.results_view.setVisible(True)

    def show_error(self, message: str) -> None:
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Failed: {message}")

    def set_download_available(self, available: bool) -> None:
        self.download_button.setEnabled(available)

    def set_folder_contents(self, folder: Path, file_count: int, total_bytes: int) -> None:
        """Show what the clean-up would delete on its button."""
        if file_count:
            self.cleanup_button.setText(
                f"Clean up warped folder ({file_count} files, {format_size(total_bytes)})..."
            )
        else:
            self.cleanup_button.setText("Clean up warped folder (empty)")
        self.cleanup_button.setToolTip(str(folder))
        self.cleanup_button.setEnabled(file_count > 0)

    def _on_render_clicked(self) -> None:
        self.render_requested.emit(self.target_bpm, self.engine_name)


def format_size(num_bytes: int) -> str:
    """e.g. 211.4 MB / 1.2 GB / 512 KB."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit != "MB" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
