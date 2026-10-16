from __future__ import annotations

from dataclasses import dataclass

from beatgrid.project.models import Stem


@dataclass(frozen=True)
class ValidationWarning:
    stem_id: str
    message: str


def validate_stems(
    stems: list[Stem],
    reference_stem_id: str,
    *,
    duration_tolerance_sec: float = 0.5,
    offset_warning_threshold_sec: float = 0.5,
) -> list[ValidationWarning]:
    """Non-blocking checks of each stem against the reference stem: sample
    rate, length and unusually large start offsets. Never modifies audio —
    actual offset *detection* is a separate, user-confirmed step
    (audio/offset_detection.py)."""
    reference = next((s for s in stems if s.id == reference_stem_id), None)
    if reference is None:
        raise ValueError(f"reference_stem_id {reference_stem_id!r} not found in stems")

    warnings: list[ValidationWarning] = []
    for stem in stems:
        if stem.id == reference.id:
            continue

        if stem.sample_rate != reference.sample_rate:
            warnings.append(
                ValidationWarning(
                    stem.id,
                    f"sample rate {stem.sample_rate} Hz differs from reference "
                    f"{reference.sample_rate} Hz",
                )
            )

        if abs(stem.duration_sec - reference.duration_sec) > duration_tolerance_sec:
            warnings.append(
                ValidationWarning(
                    stem.id,
                    f"duration {stem.duration_sec:.2f}s differs from reference "
                    f"{reference.duration_sec:.2f}s by more than {duration_tolerance_sec}s",
                )
            )

        if abs(stem.start_offset_sec) > offset_warning_threshold_sec:
            warnings.append(
                ValidationWarning(
                    stem.id,
                    f"start offset {stem.start_offset_sec:.3f}s is unusually large "
                    "— confirm this is intentional or run offset detection",
                )
            )

    return warnings
