from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeSignature:
    numerator: int = 4
    denominator: int = 4


@dataclass
class Anchor:
    id: str
    time_sec: float
    sample_index: int
    beat_index: int
    bpm: float


@dataclass(frozen=True)
class Beat:
    index: int
    time_sec: float
    sample_index: int
    bar: int
    beat_in_bar: int
    is_downbeat: bool


@dataclass
class BeatGrid:
    time_signature: TimeSignature
    anchors: list[Anchor]
    sample_rate: int

    def generate_beats(self, end_time_sec: float) -> list[Beat]:
        """Piecewise-constant tempo: each anchor is a hard re-pin with a fixed
        local BPM until the next anchor (or end_time_sec for the last one)."""
        if not self.anchors:
            return []

        anchors = sorted(self.anchors, key=lambda a: a.time_sec)
        numerator = self.time_signature.numerator
        beats: list[Beat] = []

        for i, anchor in enumerate(anchors):
            segment_end = anchors[i + 1].time_sec if i + 1 < len(anchors) else end_time_sec
            interval = 60.0 / anchor.bpm
            beat_index = anchor.beat_index
            time_sec = anchor.time_sec
            while time_sec < segment_end:
                beats.append(
                    Beat(
                        index=beat_index,
                        time_sec=time_sec,
                        sample_index=round(time_sec * self.sample_rate),
                        bar=beat_index // numerator + 1,
                        beat_in_bar=beat_index % numerator + 1,
                        is_downbeat=beat_index % numerator == 0,
                    )
                )
                beat_index += 1
                time_sec = anchor.time_sec + (beat_index - anchor.beat_index) * interval

        return beats
