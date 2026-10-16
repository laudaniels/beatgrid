# Export schema (v1)

Produced by `export/json_exporter.py` (`JSONExporter`, registered as
`"json"` in `export/registry.py`). This is a **read-only, derived artifact**
for the grid itself — the full editable project state (all stems, offsets,
mute/solo, every anchor) lives separately in a `.beatgrid` project file
(`project/project_io.py`), which is what "Save project..."/"Open
project..." read and write.

## Example

```json
{
  "schema_version": 1,
  "generator": { "name": "beatgrid", "version": "0.1.0" },
  "reference_stem": {
    "id": "kick",
    "path": "/path/to/kick.wav",
    "sha256": "cfc6b206e99b298a229480f020e61d2b22a791e08a840fdd40ef62d8bd78b155",
    "sample_rate": 44100
  },
  "time_signature": { "numerator": 4, "denominator": 4 },
  "anchors": [
    { "id": "a1", "time_sec": 1.2345, "sample_index": 54441, "beat_index": 0, "bpm": 128.0 }
  ],
  "beats": [
    { "index": 0, "time_sec": 1.2345, "sample_index": 54441, "bar": 1, "beat_in_bar": 1, "is_downbeat": true },
    { "index": 1, "time_sec": 1.70325, "sample_index": 75113, "bar": 1, "beat_in_bar": 2, "is_downbeat": false }
  ],
  "created_at": "2026-10-16T13:24:46.972068+00:00"
}
```

(`beats` is truncated above for readability — a real export fully
materializes every beat up to the reference stem's duration.)

## Fields

- **`schema_version`** (int): currently `1`. A future incompatible change
  bumps this rather than guessing from field presence.
- **`generator`**: the app name/version that produced the file.
- **`reference_stem`**: the stem the grid was built from.
  - `path`: as stored on the `Stem` (relative or absolute, whatever the
    project used).
  - `sha256`: hash of the referenced audio file's current bytes, so a
    downstream tool can detect if that file changed since export.
  - `sample_rate`: also the sample rate `anchors[].sample_index` and
    `beats[].sample_index` are expressed in (the project's sample rate —
    see `grid/model.py`'s `BeatGrid.sample_rate`).
- **`time_signature`**: `{numerator, denominator}`. Only 4/4 is exercised
  today; the fields exist for future time signatures.
- **`anchors`**: every anchor in the grid, sorted by `time_sec`. Each one:
  `id`, `time_sec` (seconds, project-time — see `grid/timeline.py`),
  `sample_index` (redundant with `time_sec`, avoids float round-trip drift),
  `beat_index` (the global beat ordinal this anchor pins; kept continuous by
  `BeatGrid.renumber_anchors()` across inserts/moves/removals — see
  `PLAN.md`'s multi-anchor design), `bpm` (this anchor's local tempo, held
  constant until the next one — piecewise-constant, not interpolated).
- **`beats`**: the fully materialized result of
  `BeatGrid.generate_beats()` — every beat from the first anchor up to the
  reference stem's duration. Downstream consumers never need to re-run the
  piecewise-constant algorithm themselves. Each one: `index` (global,
  continuous), `time_sec`, `sample_index`, `bar`/`beat_in_bar` (1-based),
  `is_downbeat` (`beat_in_bar == 1`).
- **`created_at`**: ISO 8601 UTC timestamp of the export, not of the project.

## Extending

A new export format implements `GridExporter.export(project, path)`
(`export/base.py`) and registers itself in `export/registry.py` — nothing
else in the app needs to change. Ableton `.asd`/Rekordbox export remain out
of scope (see `PLAN.md`); a future warp-render export (Variant B, M8/M9)
would be audio files plus `WarpRender` metadata in the project file, not a
change to this schema.
