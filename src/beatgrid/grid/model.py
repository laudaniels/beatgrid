from __future__ import annotations

from dataclasses import dataclass, field


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
    # Per-beat nudge (beat index -> seconds, signed) on top of the anchors'
    # constant-tempo positions, e.g. from snapping beats to transients. Kept
    # separate from the anchors so a live-played grid doesn't need one
    # anchor per beat; any anchor edit invalidates (clears) it.
    beat_offsets: dict[int, float] = field(default_factory=dict)

    def renumber_anchors(self) -> None:
        """Recompute every anchor's beat_index from its neighbors' timing and
        tempo, so inserting, moving or removing an anchor keeps bar/beat
        numbering continuous instead of leaving stale indices behind.

        The earliest anchor by time always becomes beat_index 0 (it defines
        where the grid's bar/beat counting starts); every later anchor's
        beat_index is the previous anchor's plus however many whole beats
        (at the previous anchor's tempo) elapse before it — at least 1, even
        for two anchors placed closer together than one beat.
        """
        anchors = sorted(self.anchors, key=lambda a: a.time_sec)
        if not anchors:
            return

        anchors[0].beat_index = 0
        for previous, current in zip(anchors, anchors[1:], strict=False):
            interval = 60.0 / previous.bpm
            elapsed_beats = round((current.time_sec - previous.time_sec) / interval)
            current.beat_index = previous.beat_index + max(1, elapsed_beats)

        self.anchors = anchors

    def generate_beats(self, end_time_sec: float) -> list[Beat]:
        """Piecewise-constant tempo: each anchor is a hard re-pin with a fixed
        local BPM until the next anchor (or end_time_sec for the last one).

        Every segment but the last emits *exactly* `next_anchor.beat_index -
        anchor.beat_index` beats — the same beat count `renumber_anchors`
        used to assign that index — rather than independently re-deriving a
        count from elapsed time. Mixing a rounded elapsed-beats estimate
        (renumber_anchors) with a strict time cutoff (the old `while
        time_sec < segment_end` here) could disagree by one beat right at
        the boundary, duplicating or skipping an index. Call
        renumber_anchors() first if the anchors' beat_index values aren't
        already consistent with their timing.
        """
        if not self.anchors:
            return []

        anchors = sorted(self.anchors, key=lambda a: a.time_sec)
        numerator = self.time_signature.numerator
        beats: list[Beat] = []

        for i, anchor in enumerate(anchors):
            interval = 60.0 / anchor.bpm
            beat_count = (
                anchors[i + 1].beat_index - anchor.beat_index if i + 1 < len(anchors) else None
            )

            n = 0
            while True:
                time_sec = anchor.time_sec + n * interval
                if beat_count is None:
                    if time_sec >= end_time_sec:
                        break
                elif n >= beat_count:
                    break

                beat_index = anchor.beat_index + n
                time_sec += self.beat_offsets.get(beat_index, 0.0)
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
                n += 1

        return beats


def average_bpm(beats: list[Beat]) -> float:
    """The track's own overall tempo: whole beats elapsed between the first
    and last beat over the time between them -- what a constant-tempo warp
    of the whole grid "to its own BPM" should use, even with several
    anchors at different local tempos."""
    if len(beats) < 2:
        raise ValueError("need at least 2 beats for an average tempo")
    first, last = min(beats, key=lambda b: b.index), max(beats, key=lambda b: b.index)
    return 60.0 * (last.index - first.index) / (last.time_sec - first.time_sec)
