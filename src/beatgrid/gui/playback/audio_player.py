from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

from beatgrid.gui.playback.metronome import Metronome


@dataclass
class PlaybackStem:
    stem_id: str
    audio: np.ndarray  # mono float32, in this stem's own native timeline
    start_offset_sec: float
    muted: bool = False
    solo: bool = False


def select_active_stems(stems: list[PlaybackStem]) -> list[PlaybackStem]:
    """Stems that should actually be heard: if any stem is soloed, only
    soloed stems play; otherwise every non-muted stem plays."""
    soloed = [s for s in stems if s.solo]
    if soloed:
        return soloed
    return [s for s in stems if not s.muted]


def read_stem_segment(
    stem: PlaybackStem, project_start: int, project_end: int, sample_rate: int
) -> np.ndarray:
    """The `project_end - project_start` project-sample block of `stem`'s own
    audio, translated via its start_offset_sec — silence wherever that falls
    outside the stem's own buffer (hasn't started yet / already ended)."""
    n = project_end - project_start
    out = np.zeros(n, dtype=np.float32)

    offset_samples = round(stem.start_offset_sec * sample_rate)
    stem_start = project_start - offset_samples
    stem_end = project_end - offset_samples

    read_start = max(0, stem_start)
    read_end = min(len(stem.audio), stem_end)
    if read_end <= read_start:
        return out

    out_offset = read_start - stem_start
    out[out_offset : out_offset + (read_end - read_start)] = stem.audio[read_start:read_end]
    return out


class AudioPlayer:
    """Multi-stem playback with a shared project-time clock. Mixing happens
    directly in the audio callback via `render_block` (pure, independently
    testable); `play`/`stop`/the `sounddevice.OutputStream` itself are a
    thin, untested-by-unit-test device I/O layer — only covered by GUI
    smoke tests (with the device layer mocked)."""

    def __init__(self, sample_rate: int) -> None:
        self._sample_rate = sample_rate
        self._lock = threading.Lock()
        self._stems: list[PlaybackStem] = []
        self._metronome: Metronome | None = None
        self._duration_samples: int | None = None
        self._position_samples = 0
        self._stream: sd.OutputStream | None = None
        self._pending_close: sd.OutputStream | None = None

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def is_playing(self) -> bool:
        return self._stream is not None

    @property
    def metronome(self) -> Metronome | None:
        return self._metronome

    @property
    def stems(self) -> list[PlaybackStem]:
        return list(self._stems)

    @property
    def position_sec(self) -> float:
        with self._lock:
            return self._position_samples / self._sample_rate

    def set_stems(self, stems: list[PlaybackStem]) -> None:
        with self._lock:
            self._stems = stems

    def set_metronome(self, metronome: Metronome | None) -> None:
        with self._lock:
            self._metronome = metronome

    def set_duration(self, duration_sec: float | None) -> None:
        with self._lock:
            self._duration_samples = (
                None if duration_sec is None else round(duration_sec * self._sample_rate)
            )

    def seek(self, position_sec: float) -> None:
        with self._lock:
            self._position_samples = max(0, round(position_sec * self._sample_rate))

    def render_block(self, frames: int) -> np.ndarray | None:
        """Mix `frames` samples starting at the current position and advance
        it, or return None if playback has reached its set duration."""
        with self._lock:
            start = self._position_samples
            if self._duration_samples is not None and start >= self._duration_samples:
                return None

            end = start + frames
            mix = np.zeros(frames, dtype=np.float32)
            for stem in select_active_stems(self._stems):
                mix += read_stem_segment(stem, start, end, self._sample_rate)
            if self._metronome is not None:
                self._metronome.mix_into(mix, start)

            self._position_samples = end
            return mix

    def play(self) -> None:
        self.cleanup_finished_stream()
        if self._stream is not None:
            return
        # finished_callback can only be wired up at construction time, but we
        # need the *resulting* stream object inside it (to tell "this stream
        # finished" apart from "a newer one is now playing") -- a one-element
        # container sidesteps the chicken-and-egg ordering.
        container: dict[str, sd.OutputStream] = {}
        stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
            finished_callback=lambda: self._on_finished(container["stream"]),
        )
        container["stream"] = stream
        self._stream = stream
        stream.start()

    def stop(self) -> None:
        # Grab-and-clear atomically first: closing a *local* reference avoids
        # racing finished_callback (fired by our own .stop() call below)
        # nulling self._stream out from under us mid-method.
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            stream.stop()
            stream.close()
        self.cleanup_finished_stream()

    def cleanup_finished_stream(self) -> None:
        """Close a stream that finished on its own (end of track).

        Must be called from the main thread, never from inside
        `_on_finished` itself: `finished_callback` runs on PortAudio's own
        audio thread, and closing a stream joins that very thread — doing it
        from within the callback is a self-join and corrupts the stream's
        internal state (observed as a low-level "pthread_join failed" error).
        The GUI's playhead timer calls this once it notices playback stopped.
        """
        with self._lock:
            stream = self._pending_close
            self._pending_close = None
        if stream is not None:
            stream.close()

    def _on_finished(self, stream: sd.OutputStream) -> None:
        # Only queue it for closing if stop() didn't already claim (and
        # close) this exact stream instance first.
        with self._lock:
            if self._stream is stream:
                self._stream = None
                self._pending_close = stream

    def _callback(
        self, outdata: np.ndarray, frames: int, time_info: object, status: object
    ) -> None:
        block = self.render_block(frames)
        if block is None:
            outdata[:, 0] = 0.0
            raise sd.CallbackStop()
        outdata[:, 0] = block
