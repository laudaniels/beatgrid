import numpy as np
import soundfile as sf

from beatgrid.render.wav_markers import add_cue_markers, read_cue_markers


def test_markers_roundtrip_and_audio_stays_readable(tmp_path):
    path = tmp_path / "x.wav"
    audio = np.linspace(-0.5, 0.5, 4410, dtype=np.float32)
    sf.write(path, audio, 44100)

    markers = [(0, "Bar 1"), (2205, "Bar 2"), (4000, "Bar 13")]  # odd-length labels too
    add_cue_markers(path, markers)

    assert read_cue_markers(path) == markers
    data, sample_rate = sf.read(path, dtype="float32")
    assert sample_rate == 44100
    assert len(data) == len(audio)
    raw = path.read_bytes()
    assert int.from_bytes(raw[4:8], "little") == len(raw) - 8  # RIFF size updated


def test_no_markers_leaves_file_untouched(tmp_path):
    path = tmp_path / "x.wav"
    sf.write(path, np.zeros(100, dtype=np.float32), 44100)
    before = path.read_bytes()
    add_cue_markers(path, [])
    assert path.read_bytes() == before
