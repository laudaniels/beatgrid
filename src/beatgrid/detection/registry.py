from __future__ import annotations

from beatgrid.detection.base import BeatDetector
from beatgrid.detection.librosa_detector import LibrosaBeatDetector

_REGISTRY: dict[str, type[BeatDetector]] = {
    "librosa": LibrosaBeatDetector,
}

DEFAULT_DETECTOR_NAME = "librosa"

try:
    from beatgrid.detection.beat_this_detector import BeatThisDetector

    _REGISTRY["beat_this"] = BeatThisDetector
    DEFAULT_DETECTOR_NAME = "beat_this"
except ImportError:
    pass  # beat-this (and its PyTorch dependency) isn't installed — librosa stays the default


def register(name: str, detector_cls: type[BeatDetector]) -> None:
    _REGISTRY[name] = detector_cls


def get_detector(name: str | None = None) -> BeatDetector:
    detector_name = name or DEFAULT_DETECTOR_NAME
    try:
        detector_cls = _REGISTRY[detector_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown detector {detector_name!r}; available: {sorted(_REGISTRY)}"
        ) from exc
    return detector_cls()


def available_detectors() -> list[str]:
    return sorted(_REGISTRY)
