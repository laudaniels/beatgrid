import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _no_auto_detect_on_load(request, monkeypatch):
    """load_stems() runs real beat detection by default; most GUI tests only
    need a project, so they start from the plain t=0 / DEFAULT_BPM anchor.
    Tests of the auto-detect itself opt out with @pytest.mark.auto_detect."""
    if request.node.get_closest_marker("auto_detect"):
        return
    from beatgrid.gui.main_window import DEFAULT_BPM, MainWindow

    monkeypatch.setattr(
        MainWindow, "_detect_initial_anchor", lambda self, audio: (0.0, DEFAULT_BPM)
    )
