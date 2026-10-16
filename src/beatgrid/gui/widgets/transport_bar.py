from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

NUDGE_MS_STEPS = (-10.0, -1.0, 1.0, 10.0)
NUDGE_SAMPLE_STEPS = (-1, 1)


class TransportBar(QWidget):
    """Play/pause, metronome toggle, BPM and nudge (ms/sample) controls for
    the current anchor."""

    bpm_changed = Signal(float)
    nudge_requested = Signal(float)  # delta seconds, positive = later
    play_toggled = Signal(bool)  # True = play requested, False = stop requested
    metronome_toggled = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._sample_rate = 44100

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.play_button = QPushButton("Play")
        self.play_button.setCheckable(True)
        self.play_button.toggled.connect(self._on_play_toggled)
        layout.addWidget(self.play_button)

        self.metronome_checkbox = QCheckBox("Metronome")
        self.metronome_checkbox.setChecked(True)
        self.metronome_checkbox.toggled.connect(self.metronome_toggled.emit)
        layout.addWidget(self.metronome_checkbox)

        layout.addWidget(QLabel("BPM:"))
        self.bpm_spinbox = QDoubleSpinBox()
        self.bpm_spinbox.setRange(20.0, 300.0)
        self.bpm_spinbox.setDecimals(2)
        self.bpm_spinbox.valueChanged.connect(self.bpm_changed.emit)
        layout.addWidget(self.bpm_spinbox)

        layout.addWidget(QLabel("Nudge:"))
        for delta_ms in NUDGE_MS_STEPS:
            button = QPushButton(f"{delta_ms:+.0f}ms")
            button.clicked.connect(self._make_ms_nudge_handler(delta_ms))
            layout.addWidget(button)
        for delta_samples in NUDGE_SAMPLE_STEPS:
            button = QPushButton(f"{delta_samples:+d}smp")
            button.clicked.connect(self._make_sample_nudge_handler(delta_samples))
            layout.addWidget(button)

        layout.addStretch(1)

    def _make_ms_nudge_handler(self, delta_ms: float):
        def handler(_checked: bool = False) -> None:
            self.nudge_requested.emit(delta_ms / 1000.0)

        return handler

    def _make_sample_nudge_handler(self, delta_samples: int):
        def handler(_checked: bool = False) -> None:
            self.nudge_requested.emit(delta_samples / self._sample_rate)

        return handler

    def set_bpm(self, bpm: float) -> None:
        self.bpm_spinbox.blockSignals(True)
        self.bpm_spinbox.setValue(bpm)
        self.bpm_spinbox.blockSignals(False)

    def set_sample_rate(self, sample_rate: int) -> None:
        self._sample_rate = sample_rate

    def _on_play_toggled(self, checked: bool) -> None:
        self.play_button.setText("Pause" if checked else "Play")
        self.play_toggled.emit(checked)

    def set_playing(self, playing: bool) -> None:
        """Sync the button's visual state without re-emitting play_toggled —
        used when playback stops on its own (end of track)."""
        self.play_button.blockSignals(True)
        self.play_button.setChecked(playing)
        self.play_button.setText("Pause" if playing else "Play")
        self.play_button.blockSignals(False)
