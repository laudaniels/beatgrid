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

from beatgrid.render.engines.rubberband_timemap_stretcher import (  # noqa: E402
    RubberbandTimemapStretcher,
    find_rubberband,
)

_REGISTRY["rubberband-timemap"] = RubberbandTimemapStretcher
# Preferred whenever the separately installed `rubberband` program is there;
# without it, fall back to pedalboard if that's installed (rendering with
# rubberband-timemap would only fail with "not installed").
if find_rubberband() is not None or DEFAULT_ENGINE_NAME is None:
    DEFAULT_ENGINE_NAME = "rubberband-timemap"


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
