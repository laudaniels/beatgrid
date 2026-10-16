from __future__ import annotations

from beatgrid.render.engines.base import TimeStretcher

_REGISTRY: dict[str, type[TimeStretcher]] = {}
DEFAULT_ENGINE_NAME = "pedalboard"

try:
    from beatgrid.render.engines.pedalboard_stretcher import PedalboardStretcher

    _REGISTRY["pedalboard"] = PedalboardStretcher
except ImportError:
    pass  # pedalboard isn't installed (the "warp-prototype" extra)


def register(name: str, engine_cls: type[TimeStretcher]) -> None:
    _REGISTRY[name] = engine_cls


def get_engine(name: str | None = None) -> TimeStretcher:
    engine_name = name or DEFAULT_ENGINE_NAME
    try:
        engine_cls = _REGISTRY[engine_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown warp engine {engine_name!r}; available: {sorted(_REGISTRY)}"
        ) from exc
    return engine_cls()


def available_engines() -> list[str]:
    return sorted(_REGISTRY)
