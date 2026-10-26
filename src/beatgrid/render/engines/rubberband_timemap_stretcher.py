from __future__ import annotations

import numpy as np

PRE_ROLL_SEC = 0.1


class RubberbandTimemapStretcher:
    """M9 production warp engine: pyrubberband's native timemap support —
    one phase-continuous call per stem, no manual segment splitting or
    crossfading. Shells out to the separately-installed `rubberband-cli`
    system binary via subprocess ("mere aggregation", lower GPL exposure for
    our own MIT code than Pedalboard, M8's prototype engine — see PLAN.md's
    license trade-off). Uses Rubber Band's R3 ("Finer") engine.
    """

    name = "rubberband-timemap"

    def stretch_with_timemap(
        self, audio: np.ndarray, sample_rate: int, timemap: list[tuple[int, int]]
    ) -> np.ndarray:
        import pyrubberband as pyrb

        # Rubber Band renders the timemap's first segment unstretched
        # (measured: a render starting on a hit at ratio 0.989 put every later
        # hit (1 - 0.989) x first-segment-length late, ~5.6 ms per beat).
        # A silent, genuinely unstretched pre-roll makes that first segment
        # harmless; it's cut off again afterwards.
        pre = int(round(PRE_ROLL_SEC * sample_rate))
        padded = np.concatenate([np.zeros(pre, dtype=np.float32), audio.astype(np.float32)])
        padded_map = [(0, 0), (pre, pre)] + [
            (s + pre, t + pre) for s, t in timemap if (s, t) != (0, 0)
        ]
        stretched = pyrb.timemap_stretch(padded, sample_rate, padded_map, rbargs={"-3": ""})
        return np.asarray(stretched, dtype=np.float32).reshape(-1)[pre:]
