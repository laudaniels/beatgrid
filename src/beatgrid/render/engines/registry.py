from __future__ import annotations

from beatgrid.render.engines.base import TimemapStretcher, TimeStretcher

_REGISTRY: dict[str, type] = {}
DEFAULT_ENGINE_NAME: str | None = None

try:
    from beatgrid.render.engines.pedalboard_stretcher import PedalboardStretcher

    _REGISTRY["pedalboard"] = PedalboardStretcher
    DEFAULT_ENGINE_NAME = "pedalboard"
except ImportError:
    pass  # pedalboard isn't installed (the "warp-prototype" extra)

try:
    from beatgrid.render.engines.rubberband_timemap_stretcher import RubberbandTimemapStretcher

    _REGISTRY["rubberband-timemap"] = RubberbandTimemapStretcher
    DEFAULT_ENGINE_NAME = "rubberband-timemap"  # preferred over pedalboard when both are installed
except ImportError:
    pass  # pyrubberband isn't installed (the "warp" extra); rubberband-cli
    # itself (a system binary, not a Python package) is only checked at
    # actual render time, surfacing as a RuntimeError from pyrubberband.


def register(name: str, engine_cls: type) -> None:
    _REGISTRY[name] = engine_cls


def get_engine(name: str | None = None) -> TimeStretcher | TimemapStretcher:
    engine_name = name or DEFAULT_ENGINE_NAME
    if engine_name is None:
        raise ValueError("No warp engine installed — install the 'warp' or 'warp-prototype' extra")
    try:
        engine_cls = _REGISTRY[engine_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown warp engine {engine_name!r}; available: {sorted(_REGISTRY)}"
        ) from exc
    return engine_cls()


def available_engines() -> list[str]:
    return sorted(_REGISTRY)


def default_engine_name() -> str | None:
    return DEFAULT_ENGINE_NAME
