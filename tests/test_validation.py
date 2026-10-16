from pathlib import Path

import pytest

from beatgrid.audio.validation import validate_stems
from beatgrid.project.models import Stem


def _stem(id_, sample_rate=44100, duration_sec=180.0, start_offset_sec=0.0):
    return Stem(
        id=id_,
        path=Path(f"{id_}.wav"),
        sample_rate=sample_rate,
        duration_sec=duration_sec,
        start_offset_sec=start_offset_sec,
    )


def test_no_warnings_for_matching_stems():
    stems = [_stem("kick"), _stem("bass")]
    assert validate_stems(stems, reference_stem_id="kick") == []


def test_sample_rate_mismatch_warns():
    stems = [_stem("kick", sample_rate=44100), _stem("bass", sample_rate=48000)]
    warnings = validate_stems(stems, reference_stem_id="kick")

    assert len(warnings) == 1
    assert warnings[0].stem_id == "bass"
    assert "sample rate" in warnings[0].message


def test_duration_mismatch_warns():
    stems = [_stem("kick", duration_sec=180.0), _stem("bass", duration_sec=170.0)]
    warnings = validate_stems(stems, reference_stem_id="kick")

    assert any("duration" in w.message for w in warnings)


def test_large_offset_warns():
    stems = [_stem("kick"), _stem("bass", start_offset_sec=1.2)]
    warnings = validate_stems(stems, reference_stem_id="kick")

    assert any("offset" in w.message for w in warnings)


def test_unknown_reference_raises():
    with pytest.raises(ValueError):
        validate_stems([_stem("kick")], reference_stem_id="does-not-exist")
