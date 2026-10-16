from __future__ import annotations

from beatgrid.export.base import GridExporter
from beatgrid.export.json_exporter import JSONExporter

_REGISTRY: dict[str, type[GridExporter]] = {
    "json": JSONExporter,
}


def register(name: str, exporter_cls: type[GridExporter]) -> None:
    _REGISTRY[name] = exporter_cls


def get_exporter(name: str) -> GridExporter:
    try:
        exporter_cls = _REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unknown export format {name!r}; available: {sorted(_REGISTRY)}") from exc
    return exporter_cls()


def available_formats() -> list[str]:
    return sorted(_REGISTRY)
