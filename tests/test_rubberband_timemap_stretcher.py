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


@requires_rubberband
def test_timemap_starting_on_a_hit_still_places_hits_on_their_targets():
    """Rubber Band renders a timemap's first segment unstretched; without the
    engine's silent pre-roll, a render starting right on a hit at ratio 0.989
    put every later hit ~5.8 ms late."""
    import numpy as np

    sample_rate = 44100
    interval = sample_rate // 2
    positions = np.arange(12) * interval
    rng = np.random.default_rng(0)
    audio = 0.001 * rng.standard_normal(positions[-1] + sample_rate)
    body = np.arange(int(0.15 * sample_rate)) / sample_rate
    for p in positions:
        audio[p : p + len(body)] += 0.8 * np.exp(-body / 0.03) * rng.standard_normal(len(body))
    audio = audio.astype(np.float32)

    targets = np.round(positions * 0.989).astype(int)
    timemap = list(zip(positions.tolist(), targets.tolist(), strict=True))
    timemap.append((len(audio), int(targets[-1] + len(audio) - positions[-1])))

    out = RubberbandTimemapStretcher().stretch_with_timemap(audio, sample_rate, timemap)

    def attack(signal, around):
        lo = max(0, around - int(0.03 * sample_rate))
        level = np.convolve(np.abs(signal[lo : around + int(0.03 * sample_rate)]), np.ones(44) / 44)
        return lo + int(np.argmax(level > 0.2 * level.max()))

    bias = np.median([attack(audio, p) - p for p in positions])
    deviations_ms = [(attack(out, t) - t - bias) / sample_rate * 1000 for t in targets]
    assert len(out) == timemap[-1][1]
    assert max(abs(d) for d in deviations_ms) < 1.5
