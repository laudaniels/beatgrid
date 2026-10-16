import pytest

pytest.importorskip("pyrubberband")

from beatgrid.render.engines.rubberband_timemap_stretcher import (  # noqa: E402
    RubberbandTimemapStretcher,
)


def _rubberband_cli_available() -> bool:
    import shutil

    return shutil.which("rubberband") is not None


requires_rubberband = pytest.mark.skipif(
    not _rubberband_cli_available(), reason="rubberband-cli is not installed"
)


@requires_rubberband
def test_engine_name():
    assert RubberbandTimemapStretcher().name == "rubberband-timemap"


@requires_rubberband
def test_stretch_with_timemap_respects_final_target_length():
    import numpy as np

    sample_rate = 8000
    audio = np.sin(2 * np.pi * 440 * np.arange(16000) / sample_rate).astype(np.float32)
    timemap = [(0, 0), (8000, 10000), (16000, 20000)]

    stretched = RubberbandTimemapStretcher().stretch_with_timemap(audio, sample_rate, timemap)

    assert len(stretched) == pytest.approx(20000, abs=5)
