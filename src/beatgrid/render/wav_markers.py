from __future__ import annotations

import struct
from collections.abc import Sequence
from pathlib import Path


def add_cue_markers(path: Path, markers: Sequence[tuple[int, str]]) -> None:
    """Append named markers -- (sample_offset, label) pairs -- to an existing
    RIFF/WAVE file as a standard `cue ` chunk plus a `LIST`/`adtl` chunk of
    `labl` names, the form Reaper (and most editors) import as markers.
    The audio itself is untouched; only the RIFF size field is updated.
    """
    if not markers:
        return
    path = Path(path)
    data = bytearray(path.read_bytes())
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"{path} is not a RIFF/WAVE file")

    cue_points = b"".join(
        struct.pack("<II4sIII", cue_id, sample, b"data", 0, 0, sample)
        for cue_id, (sample, _label) in enumerate(markers, start=1)
    )
    cue_body = struct.pack("<I", len(markers)) + cue_points

    labels = b""
    for cue_id, (_sample, label) in enumerate(markers, start=1):
        text = label.encode("utf-8") + b"\0"
        labels += _chunk(b"labl", struct.pack("<I", cue_id) + text)
    list_body = b"adtl" + labels

    data += _chunk(b"cue ", cue_body) + _chunk(b"LIST", list_body)
    data[4:8] = struct.pack("<I", len(data) - 8)
    path.write_bytes(bytes(data))


def read_cue_markers(path: Path) -> list[tuple[int, str]]:
    """The (sample_offset, label) markers in a WAV file's cue/labl chunks --
    the inverse of add_cue_markers, for tests and round-trip checks."""
    data = Path(path).read_bytes()
    positions: dict[int, int] = {}
    labels: dict[int, str] = {}
    offset = 12
    while offset + 8 <= len(data):
        chunk_id, size = struct.unpack_from("<4sI", data, offset)
        body = data[offset + 8 : offset + 8 + size]
        if chunk_id == b"cue ":
            (count,) = struct.unpack_from("<I", body)
            for i in range(count):
                cue_id, sample = struct.unpack_from("<II", body, 4 + 24 * i)
                positions[cue_id] = sample
        elif chunk_id == b"LIST" and body[:4] == b"adtl":
            sub = 4
            while sub + 8 <= len(body):
                sub_id, sub_size = struct.unpack_from("<4sI", body, sub)
                if sub_id == b"labl":
                    (cue_id,) = struct.unpack_from("<I", body, sub + 8)
                    raw = body[sub + 12 : sub + 8 + sub_size]
                    labels[cue_id] = raw.split(b"\0", 1)[0].decode("utf-8")
                sub += 8 + sub_size + (sub_size % 2)
        offset += 8 + size + (size % 2)
    return [(positions[i], labels.get(i, "")) for i in sorted(positions)]


def _chunk(chunk_id: bytes, body: bytes) -> bytes:
    pad = b"\0" if len(body) % 2 else b""
    return chunk_id + struct.pack("<I", len(body)) + body + pad
