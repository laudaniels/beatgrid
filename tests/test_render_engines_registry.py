import pytest

from beatgrid.render.engines.base import TimeStretcher
from beatgrid.render.engines.registry import available_engines, get_engine, register


def test_pedalboard_is_available_when_installed():
    pytest.importorskip("pedalboard")
    assert "pedalboard" in available_engines()
    assert get_engine("pedalboard").name == "pedalboard"


def test_rubberband_timemap_is_available_and_default_when_installed():
    pytest.importorskip("pyrubberband")
    assert "rubberband-timemap" in available_engines()
    # preferred over pedalboard (lower GPL exposure, native piecewise warp)
    # whenever both are installed -- see PLAN.md's license trade-off.
    assert get_engine().name == "rubberband-timemap"


def test_unknown_engine_raises():
    with pytest.raises(ValueError):
        get_engine("does-not-exist")


def test_register_custom_engine():
    class DummyEngine:
        name = "dummy"

        def stretch(self, audio, sample_rate, ratio):
            return audio

    register("dummy", DummyEngine)

    assert "dummy" in available_engines()
    engine: TimeStretcher = get_engine("dummy")
    assert isinstance(engine, DummyEngine)
