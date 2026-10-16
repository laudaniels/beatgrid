from __future__ import annotations

import numpy as np


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

        stretched = pyrb.timemap_stretch(audio, sample_rate, timemap, rbargs={"-3": ""})
        return np.asarray(stretched, dtype=np.float32).reshape(-1)
