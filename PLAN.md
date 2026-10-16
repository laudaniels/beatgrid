# BeatGrid — plan

## Context

Doel: een lokale, GitHub-hostbare open-source Python-tool om de beats van een nummer correct op een 4/4-grid te krijgen, met een visuele editor en **ondersteuning voor tot ~10 stems**. Workflow: stems laden (wav/flac/mp3) → waveforms tonen → één stem (meestal de kick) kiezen als referentie → automatische BPM/beat-detectie op die referentie-stem als voorstel → handmatig de eerste downbeat exact op de grid zetten (snap op transients, fijne nudge) → grid genereren vanaf dat anker + BPM → visueel en via metronoom-afspelen controleren en corrigeren (BPM, hele grid verschuiven, losse beats/secties, meerdere ankers bij tempo-drift) → hetzelfde grid wordt automatisch toegepast op alle andere stems, zodat afwijkingen (bv. een licht "ademende" live bas) zichtbaar zijn zonder automatisch gecorrigeerd te worden → optioneel: alle stems warpen/time-stretchen naar een vast grid (zoals Ableton warp-markers) → projectbestand (JSON) met stem-paden, referentie-stem, grid en instellingen → export van het grid als JSON.

Multi-stem (tot ~10 stems) en zowel Variant A als Variant B zitten vanaf het begin in de architectuur, geen latere verbouwing. Het project bestaat nog niet (lege map, geen git-repo) — dit is een greenfield-opzet.

**Al genomen/bevestigde beslissingen:**
- Python 3.11+, dependency management met **uv**.
- GUI: **PySide6 + pyqtgraph** (native desktop, één proces). Blijft ook met tot 10 stems de juiste keuze: meerdere pyqtgraph-plots met gelinkte X-as (gedeelde zoom/scroll) is een standaardpatroon, en alle stems samen afspelen/mixen kan in één `sounddevice`-callback in hetzelfde proces — frame-accurate en zonder browser/server-omweg. Web-UI (FastAPI+wavesurfer.js) en hybride webview zijn afgewezen.
- **Beatdetectie: Beat This! (CPJKU) als primaire detector, librosa als lichte fallback**, achter een gemeenschappelijke `BeatDetector`-interface zodat implementaties verwisselbaar zijn. Beat This! (ISMIR 2024, `pip install beat-this`, code+weights MIT-licensed) haalt hogere nauwkeurigheid dan madmom's DBN-aanpak zonder de GPL-last van madmom, maar brengt PyTorch als dependency mee (CPU-inferentie is prima, dit is eenmalige analyse, geen realtime-vereiste) — dit wordt duidelijk in de README genoemd als zwaardere install-stap. librosa blijft beschikbaar als lichte fallback (geen torch nodig) voor wie dat liever heeft. madmom blijft bewust buiten de default-scope (breekt op Python ≥3.10 + numpy ≥1.24, GPL-licensed), eventueel later toe te voegen via dezelfde registry.
- Detecties worden verfijnd met een **eigen sample-precieze transient-snap** (onset-gebaseerd, los van welke detector de ruwe beats levert) en een **BPM + anker-schatting via lineaire regressie** over de gedetecteerde beatposities (least-squares fit van `beat_index` tegen `beat_time`: de richtingscoëfficiënt geeft `60/bpm`, het snijpunt geeft de ankertijd) — dit middelt kleine per-beat-jitter uit de ruwe detector-output tot een robuuste globale schatting, zowel voor de initiële single-anchor-schatting als per segment bij multi-anchor tempo-drift.
- Licentie: **MIT**. Beat This! (MIT) en librosa (ISC) zijn probleemloos compatibel. De warp-engine (hieronder) brengt bewust afgewogen GPL-blootstelling met zich mee — zie de licentie-afweging.
- **Variant A én Variant B zijn beide in scope**, niet alleen A: Variant A (grid past zich aan de audio aan, audio blijft ongewijzigd) is de kern en komt eerst (M0–M7). Variant B (audio warpen/time-stretchen naar een vast grid, zoals Ableton warp-markers) wordt **nu ook gebouwd**, als twee aparte mijlpalen ná een stabiel grid-model: eerst een werkend prototype (M8), dan de productie-engine (M9) — zie "Variant B: warpen/time-stretchen" hieronder voor het volledige ontwerp en de licentie-afweging.
- **Warp-engine: twee fasen, bewust gescheiden.**
  - **Prototype (M8) — `pedalboard.time_stretch`**: snelste weg naar een werkend end-to-end warp-pipeline (model, GUI, provenance) om de architectuur te valideren, met constante-ratio stretching per segment + korte crossfade op de segmentgrenzen.
  - **Productie (M9) — `pyrubberband.timemap_stretch`**: Rubber Band ondersteunt een native **timemap** — een lijst `(input_sample, output_sample)`-keyframeparen — waarmee de engine zelf fasecontinu varieert tussen ankerpunten. Dat is precies wat piecewise-warpen tussen grid-ankers nodig heeft, zónder zelf te knippen/crossfaden zoals bij het prototype. **Correctie op eerder in dit plan**: Pedalboard is géén Apache-2.0-project zoals ik eerder abusievelijk stelde — het is zelf **GPL-3.0**, omdat het Rubber Band, FFTW en JUCE statisch in één gecompileerde wheel bundelt. Een PyInstaller-executable die Pedalboard meeneemt (M10) zou daardoor als geheel GPL-3.0-plichtig zijn bij distributie. `pyrubberband` roept daarentegen de losse, apart te installeren `rubberband-cli` (ook GPL, dual-licensed) aan via **subprocess** — vergelijkbaar met onze bestaande ffmpeg-afhankelijkheid voor mp3: dit is "mere aggregation" (een los gedistribueerd extern programma aanroepen, geen linking), wat het GPL-risico voor onze eigen MIT-broncode laag houdt, zolang we dat binary zelf niet in een gebundelde executable meeleveren. Dit verschil — en niet alleen de timemap-functionaliteit — is de reden dat `pyrubberband` de productie-keuze is; zie de volledige afweging (incl. het MIT-zuivere maar nog te bouwen Signalsmith Stretch-alternatief) in de sectie "Variant B" hieronder.
  - Beide zitten achter dezelfde `TimeStretcher`-interface (`render/engines/base.py`), zodat de swap van prototype naar productie geen herontwerp van `warp_renderer.py` vereist.
- **Doelgroep**: vooral voor de gebruiker zelf; open-source voor transparantie/portfolio. Geen actieve community-werving nodig → README praktisch en kort, geen CONTRIBUTING.md/issue templates/CODE_OF_CONDUCT nodig (kan altijd later worden toegevoegd als er animo blijkt).
- **Testaudio**: `tests/data/` bevat uitsluitend **synthetisch gegenereerde** tracks/stems (bekende BPM, tempo-drift, offsets) — licentieveilig in een publieke repo en geeft exact verifieerbare verwachte uitkomsten. Geen echte muziekfragmenten in de repo.
- Kernlogica (project, audio, detectie, grid, render, export) strikt gescheiden van de GUI, geen Qt-import buiten `gui/`, met pytest-dekking.
- MVP = project met meerdere stems laden + waveforms tonen + gedeeld grid tonen + handmatig één anker zetten op de referentie-stem (ongewijzigd t.o.v. eerdere afstemming; detectie, warp, playback etc. zijn mijlpalen ná de MVP).

## Architectuur

Eén `uv`-project, **één top-level package** `src/beatgrid/` met losse submodules (geen split in twee installeerbare packages — dat voegt complexiteit toe die hier niet nodig is; een lichte, Qt-vrije CI-job blijft wel mogelijk via optionele dependency-extras in één `pyproject.toml`, bv. `beatgrid[gui]`). Dit volgt het door de gebruiker voorgestelde schema, aangevuld met `render/` voor Variant B en een rijkere `detection/`:

```
beatgrid/
├── pyproject.toml                 # extras: core (numpy/librosa/beat-this/soundfile), gui (PySide6/pyqtgraph/sounddevice), warp-prototype (pedalboard), warp (pyrubberband; vereist los geïnstalleerde rubberband-cli)
├── README.md
├── LICENSE                        # MIT
├── CLAUDE.md                      # module-grenzen, testconventies, hoe een detector/exporter/renderer toe te voegen
├── .gitignore
├── .github/workflows/ci.yml
├── docs/
│   ├── ARCHITECTURE.md            # dit ontwerp, voor onderhoud na deze planningssessie
│   └── EXPORT_SCHEMA.md           # JSON-schema v1, met voorbeeld
├── src/beatgrid/
│   ├── project/
│   │   ├── models.py               # Stem, Project, WarpRender dataclasses
│   │   └── project_io.py           # save/load *.beatgrid-projectbestand (JSON)
│   ├── audio/
│   │   ├── loader.py               # wav/flac/mp3 laden; mp3 via audioread/ffmpeg-fallback
│   │   ├── validation.py           # samplerate/lengte/offset-checks tussen stems, waarschuwingen
│   │   ├── offset_detection.py     # cross-correlatie-gebaseerde offset-schatting tussen stems
│   │   ├── kick_derivation.py      # kick afleiden uit drums-stem: low-pass 100-150Hz + onset-detectie
│   │   └── waveform_cache.py       # multi-resolutie min/max peak-pyramide per stem, voor snel zoomen
│   ├── detection/
│   │   ├── base.py                 # BeatDetector protocol + DetectionResult
│   │   ├── beat_this_detector.py    # primaire detector, pip install beat-this (torch)
│   │   ├── librosa_detector.py     # lichte fallback zonder torch
│   │   ├── refine.py               # lineaire-regressiefit van beat_index -> beat_time per segment -> (anchor_time, bpm)
│   │   ├── transient.py            # eigen sample-precieze onset/transient-snap; ook voor drift-visualisatie
│   │   └── registry.py             # naam -> BeatDetector (extensiepunt voor madmom/BeatNet later)
│   ├── grid/
│   │   ├── model.py                # Anchor, TimeSignature, Beat, BeatGrid, generate_beats()
│   │   └── timeline.py             # vertaling project-tijd <-> per-stem sample-positie (offset-gecorrigeerd)
│   ├── render/
│   │   ├── warp_renderer.py        # Variant B: orchestreert warpen van elke stem naar een vast doel-tempo
│   │   ├── timemap.py              # bouwt (input_sample, output_sample)-keyframes uit ankers + doel-BPM
│   │   └── engines/
│   │       ├── base.py              # TimeStretcher protocol
│   │       ├── pedalboard_stretcher.py     # M8-prototype: constante ratio per segment + crossfade-splice
│   │       ├── rubberband_timemap_stretcher.py  # M9-productie: pyrubberband.timemap_stretch, natief piecewise
│   │       └── registry.py          # naam -> TimeStretcher (extensiepunt, bv. voor Signalsmith Stretch later)
│   ├── export/
│   │   ├── base.py                 # GridExporter ABC
│   │   ├── json_exporter.py        # schema v1
│   │   └── registry.py             # extensiepunt (Ableton/Rekordbox later)
│   ├── gui/
│   │   ├── app.py
│   │   ├── main_window.py
│   │   ├── widgets/
│   │   │   ├── stem_track_view.py   # één rij per stem (tot ~10), pyqtgraph-plots met gelinkte X-as
│   │   │   ├── grid_overlay.py      # bar/beat/anchor-markers, per stem offset-gecorrigeerd getekend
│   │   │   ├── anchor_item.py       # sleepbare InfiniteLine; alleen actief op de referentie-stem-rij
│   │   │   ├── drift_overlay.py     # toont per-stem transients t.o.v. het gedeelde grid (puur diagnostisch)
│   │   │   ├── transport_bar.py     # play/pause, BPM, nudge (ms/samples), metronoom-toggle
│   │   │   ├── stem_panel.py        # per-stem mute/solo, rol (kick/drums/bass/...), referentie-keuze
│   │   │   └── warp_dialog.py       # doel-BPM kiezen, warp starten, voortgang/resultaatoverzicht
│   │   ├── playback/
│   │   │   ├── audio_player.py      # sounddevice.OutputStream, multi-stem mix (mute/solo), sample-teller
│   │   │   └── metronome.py         # sample-accurate click-mixing in dezelfde audiocallback
│   │   └── controllers/project_controller.py  # model<->widgets, undo/redo, dirty-state
│   └── cli.py                      # optioneel: `beatgrid detect`/`export`/`warp` batch-commando's, geen Qt
└── tests/
    ├── data/                        # alleen synthetisch gegenereerde fixtures (zie fixtures.py)
    ├── fixtures.py                  # make_click_track(), make_stem_set(offset=..., drift=...)
    ├── test_grid_model.py
    ├── test_waveform_cache.py
    ├── test_validation.py
    ├── test_offset_detection.py
    ├── test_kick_derivation.py
    ├── test_detection_registry.py
    ├── test_beat_this_detector.py
    ├── test_librosa_detector.py
    ├── test_detection_refine.py
    ├── test_timemap.py
    ├── test_warp_renderer_pedalboard.py
    ├── test_warp_renderer_rubberband.py   # @pytest.mark.requires_rubberband, geskipt zonder geïnstalleerde rubberband-cli
    ├── test_export_json.py
    ├── test_project_io.py
    └── gui/test_smoke_mainwindow.py   # pytest-qt, offscreen, @pytest.mark.gui
```

### Datamodel: Project, Stem en gedeeld grid

```python
@dataclass
class Stem:
    id: str
    path: Path
    role: str                    # "kick" | "drums" | "bass" | "vocals" | "other" | vrij
    sample_rate: int
    channels: int
    duration_sec: float
    start_offset_sec: float = 0.0   # positie van stem-t=0 t.o.v. de project-tijdlijn
    derived_kick: bool = False      # True als kick via kick_derivation.py is afgeleid i.p.v. een eigen stem

@dataclass
class WarpRender:
    target_bpm: float
    engine: str                  # bv. "rubberband-timemap" (productie) of "pedalboard" (prototype)
    rendered_at: datetime
    output_paths: dict[str, Path]  # stem_id -> pad naar gewarpt bestand

@dataclass
class Project:
    name: str
    stems: list[Stem]            # tot ~10
    reference_stem_id: str
    grid: BeatGrid               # één gedeeld grid voor het hele project
    warp_renders: list[WarpRender]  # historie van warp-renders (optioneel, leeg bij alleen Variant A-gebruik)
    created_at: datetime
    app_version: str
```

Het grid wordt **uitsluitend** op de referentie-stem gedetecteerd/bewerkt en in **project-tijd** opgeslagen (tijdlijn van de referentie-stem bij `start_offset_sec = 0`). `grid/timeline.py` rekent voor elke andere stem `stem_sample_index = round((beat.time_sec - stem.start_offset_sec) * stem.sample_rate)` — zo tekent en speelt elke stem-rij het grid op de juiste plek, ook als stems onderling net iets andere start-offsets hebben (bv. verschillend bijgesneden intro's).

Tempo-drift blijft **piecewise-constant**: elk anker is een harde her-pin met een vaste lokale BPM tot het volgende anker (`t_n = anchor.time_sec + n * 60/anchor.bpm`). Dit blijft project-breed gelden — alle stems delen dezelfde ankerlijst. MVP werkt met exact één anker; multi-anchor is additief (zie M6).

Met tot ~10 stems van een paar minuten blijft volledig in-memory laden (NumPy-arrays) qua geheugen ruim werkbaar (orde grootte ~1GB voor 10 stereo-stems van 5 minuten op 44.1kHz/float32) — geen streaming-architectuur nodig voor v1. Dit wordt als bewuste, niet-blokkerende aanname gedocumenteerd (`docs/ARCHITECTURE.md`), met blokgewijs/`soundfile`-streamed laden als mogelijke latere optimalisatie bij veel langere sessies.

### Multi-stem validatie en kick-afleiding

- `audio/validation.py`: bij het laden van stems wordt gecontroleerd op samplerate-verschillen, lengteverschillen en (optioneel) startoffset-afwijkingen; resultaten zijn niet-blokkerende waarschuwingen in de GUI (bv. "stem X heeft een andere samplerate (44.1kHz vs 48kHz)"). Audio wordt nooit stilzwijgend aangepast.
- `audio/offset_detection.py`: cross-correlatie tussen de amplitude-envelope van de referentie-stem en een andere stem (gedownsampled voor snelheid, bv. via `scipy.signal.fftconvolve`/`numpy.correlate` binnen een beperkt zoekvenster, bv. ±2s) levert een voorgestelde `start_offset_sec`. Dit is altijd een **voorstel dat de gebruiker expliciet bevestigt**, nooit een automatische correctie.
- `audio/kick_derivation.py`: als er geen losse kick-stem is, wordt uit de drums-stem een kick-achtig signaal afgeleid via een low-pass filter rond 100–150 Hz (bv. `scipy.signal.butter` + `filtfilt`) gevolgd door onset-detectie op dat gefilterde signaal. Dit afgeleide signaal wordt alleen gebruikt om de detector te voeden (geen audio-bestand, in-memory of lokaal gecachet), nooit geëxporteerd of als "echte" stem behandeld.

### Detectie: Beat This! + librosa + eigen verfijning

- `detection/base.py`: `BeatDetector` protocol (`detect(audio, sample_rate) -> DetectionResult`) en `DetectionResult` (ruwe beat-tijden + geschat tempo), geïmplementeerd door zowel `beat_this_detector.py` als `librosa_detector.py`.
- `detection/registry.py`: naam → detector-klasse, default `"beat_this"`, met `"librosa"` als expliciet te kiezen lichte fallback (bv. als torch niet geïnstalleerd is of de gebruiker snelheid boven nauwkeurigheid verkiest).
- `detection/transient.py`: sample-precieze onset/transient-snap (eigen implementatie, losstaand van welke detector de ruwe beats leverde), gebruikt bij (a) het verfijnen van een voorgestelde beat-/anker-positie, (b) live snapping tijdens het slepen van een anker, en (c) de drift-visualisatie per stem.
- `detection/refine.py`: `fit_anchor_and_bpm(beat_times: Sequence[float], beat_indices: Sequence[int]) -> tuple[float, float]` — lineaire regressie (`numpy.polyfit`, graad 1) van `beat_index` tegen `beat_time`; de richtingscoëfficiënt levert `60/bpm`, het snijpunt de ankertijd. Dit wordt zowel gebruikt voor de initiële single-anchor-schatting (M5) als per segment bij multi-anchor tempo-drift (M6), om kleine per-beat-jitter uit de ruwe detectoroutput te middelen tot een robuuste, stabiele schatting.

### GUI: gedeeld grid over meerdere stems

- `stem_track_view.py`: één pyqtgraph-plotrij per stem (tot ~10), X-assen aan elkaar gelinkt (`setXLink`) zodat zoomen/scrollen op één rij alle rijen synchroon houdt.
- `grid_overlay.py` tekent dezelfde bar/beat/anchor-lijnen op elke rij, gepositioneerd via `grid/timeline.py`'s per-stem omrekening.
- `anchor_item.py` (het sleepbare anker) is alleen interactief op de rij van de **referentie-stem**; andere rijen tonen het grid read-only — zo blijft "één grid voor alle stems" gegarandeerd.
- `drift_overlay.py`: per stem worden de eigen transients (via `detection/transient.py`) getoond als kleine markers; een transient die meer dan een drempel (bv. 15–20 ms, instelbaar) van de dichtstbijzijnde gridlijn afligt wordt visueel geaccentueerd (bv. oranje/rood) — puur diagnostisch, past het grid nooit automatisch aan.
- `stem_panel.py`: mute/solo per stem en referentie-stem kiezen/wijzigen. Playback (`playback/audio_player.py`) mixt alle niet-gemutete stems in dezelfde `sounddevice`-callback; de metronoom-klik wordt daar sample-accuraat bovenop gemixt (precompute klik-buffer, per uitgaand blok de `Beat.sample_index`-waarden in bereik inmixen).

### Variant B: warpen/time-stretchen naar een vast grid

Kerninzicht: de ankerlijst (`time_sec` + lokale `bpm` per anker) is wiskundig al precies de informatie die nodig is om een warp-map te berekenen — er zijn dus **geen extra velden nodig** in `Anchor`/`BeatGrid`. Variant B is een **nieuwe consument** van hetzelfde model, geen herontwerp ervan. De warp-engine zelf zit achter een eigen `TimeStretcher`-interface (`render/engines/base.py`, protocol: `stretch(audio, sample_rate, mapping) -> np.ndarray`), zodat `warp_renderer.py` niet hoeft te weten welke engine eronder zit.

**Doel-tempo**: standaard de BPM van het eerste anker (hele track wordt op die constante tempo gezet), door de gebruiker overschrijfbaar naar een vrij gekozen doel-BPM via `warp_dialog.py`.

**Licentie-afweging (geëxpliciteerd, want relevant voor een MIT-repo):**

| | GPL-risico | Piecewise-warp | Installatie |
|---|---|---|---|
| **pyrubberband** (subprocess naar los `rubberband-cli`-binary) — **gekozen productie-engine (M9)** | Laag voor onze eigen broncode: een subprocess-aanroep naar een los gedistribueerd extern programma is "mere aggregation", geen linking — hetzelfde patroon als onze bestaande ffmpeg-afhankelijkheid. Het binary zelf is GPL/dual-licensed; wordt het ooit in een gebundelde PyInstaller-executable meegeleverd (M10), dan is dát specifieke bestand GPL-plichtig bij distributie. | Ja, nativief via `timemap_stretch()` — fasecontinu, geen handmatige segmentatie/crossfade nodig | extra systeemvereiste (apt/brew), zoals ffmpeg |
| **pedalboard** — **gekozen prototype-engine (M8)** | Hoger: Pedalboard is zelf GPL-3.0 (bundelt Rubber Band + FFTW + JUCE statisch in de wheel). Puur als dev-dependency voor het prototype is dit geen probleem; het zou wel een probleem worden als Pedalboard meegaat in een gedistribueerde M10-executable. | Onbevestigd of inmiddels ondersteund (PR #334 "variable time-stretching", mei 2024, merge-status niet vast te stellen) — vooralsnog alleen constante ratio, dus handmatig segmenteren + crossfaden | pure pip install, geen systeembinary |
| **Signalsmith Stretch** — **niet gekozen, future/optioneel** | Schoon MIT, geen copyleft waar dan ook | Onbevestigd of er een native timemap-modus is; vermoedelijk zelf per-block ratio aansturen vanuit onze eigen ankerwiskunde | Geen Python-binding bestaat — zou zelf gebouwd (pybind11/cffi rond de header-only C++-lib) en onderhouden moeten worden; bovenstrooms zelf maar bescheiden onderhouden (laatste push feb 2024) |

**M8 — Prototype** (`render/engines/pedalboard_stretcher.py`): per segment tussen opeenvolgende ankers wordt de **gemeten** duur (via de bestaande per-stem offset-correctie uit `grid/timeline.py`) vergeleken met de **ideale** duur bij het doel-tempo (`aantal_beats_in_segment * 60/target_bpm`); stretch-ratio = ideale/gemeten duur; elk segment wordt onafhankelijk gestretcht via `pedalboard.time_stretch(..., high_quality=True)` en de segmenten worden aan elkaar geplakt met een korte crossfade (~5–10 ms) op elke naad. Doel: snel een werkend end-to-end pad (model → render → GUI → projectbestand) om de rest van de architectuur te valideren.

**M9 — Productie** (`render/engines/rubberband_timemap_stretcher.py` + `render/timemap.py`): `timemap.py` bouwt uit de ankerlijst + doel-BPM rechtstreeks een lijst `(input_sample, output_sample)`-keyframeparen (voor elke beat: `input_sample` = de gemeten positie in de originele audio, `output_sample` = de ideale positie bij het doel-tempo); dit wordt in één keer doorgegeven aan `pyrubberband.pyrb.timemap_stretch()`, die zelf fasecontinu interpoleert tussen de keyframes — geen handmatige segment-splice/crossfade meer nodig. Dezelfde keyframe-lijst (vertaald naar elke stem zijn eigen sample-as via de bestaande offset-correctie) wordt op elke stem toegepast, zodat alle stems na het warpen gegarandeerd even lang blijven en onderling gesynchroniseerd zijn.

Beide engines schrijven naar nieuwe, niet-destructieve bestanden (bv. `<project_dir>/warped/<stem_id>_warped.wav`), nooit de originele stems overschrijven. Het resultaat wordt als `WarpRender` (doel-BPM, gebruikte engine, tijdstip, output-paden) in het projectbestand vastgelegd zodat de geschiedenis van renders bewaard blijft.

**Verificatie-eis voor M9** (expliciet gevraagd): een test die bevestigt dat (a) elk anker na het warpen sample-nauwkeurig op zijn ideale doel-grid-positie landt, en (b) alle gestretchte stems van één render exact dezelfde output-lengte hebben.

### JSON-projectbestand en exportschema (v1)

Projectbestand (`project_io.py`) bevat de volledige `Project` (stems met paden/rollen/offsets, referentie-stem-id, grid met ankers, warp-render-geschiedenis, instellingen) zodat later verder werken mogelijk is. Export (`export/json_exporter.py`) is een afgeleid, read-only artefact voor het grid zelf (warp-renders zijn audiobestanden, geen onderdeel van dit schema):

```json
{
  "schema_version": 1,
  "generator": { "name": "beatgrid", "version": "0.1.0" },
  "reference_stem": { "id": "kick", "path": "stems/kick.wav", "sha256": "...", "sample_rate": 44100 },
  "time_signature": { "numerator": 4, "denominator": 4 },
  "anchors": [ { "id": "a1", "time_sec": 1.2345, "sample_index": 54441, "beat_index": 0, "bpm": 128.0 } ],
  "beats": [ { "index": 0, "time_sec": 1.2345, "sample_index": 54441, "bar": 1, "beat_in_bar": 1, "is_downbeat": true } ],
  "created_at": "2026-10-16T10:28:00Z"
}
```

`beats` is volledig gematerialiseerd. Nieuwe exportformaten implementeren `GridExporter.export(project, path)` en registreren zich in `export/registry.py` — niets anders in de app hoeft te veranderen. Ableton `.asd`/Rekordbox-export blijven bewust buiten scope (proprietary formaten, geen onderbouwd ontwerp nu nodig).

### Playback en waveform-rendering

- **Playback: `sounddevice`**, niet `QtMultimedia`/`pyaudio` — rechtstreekse callback op NumPy-buffers, geen format-indirectie. Multi-stem mix (tot ~10 stems) gebeurt binnen dezelfde callback (som van niet-gemutete stems), met een losse sample-teller voor de playhead die via een Qt-`QTimer` (~30–60 Hz) wordt uitgelezen.
- **Waveform**: MVP gebruikt pyqtgraph's ingebouwde `autoDownsample=True, downsampleMethod='peak'`. `waveform_cache.py` (vanaf M1) bouwt per stem een min/max-bucket-pyramide voor O(zichtbare buckets)-redraws bij lange bestanden/veel stems.
- **mp3-caveat**: `soundfile` leest mp3 niet overal betrouwbaar; `loader.py` valt voor mp3 terug op `librosa`/`audioread`, wat `ffmpeg` op het PATH vereist — komt in de README als vereiste, naast PyTorch (voor Beat This!) als zwaardere install-stap.

### Testen en CI

- Core: alles getest met **synthetische** fixtures uit `tests/fixtures.py` (`make_click_track`, `make_stem_set(offset=..., drift=...)` voor multi-stem-scenario's met bekende offsets/tempo-drift). `test_beat_this_detector.py`/`test_librosa_detector.py` testen alleen "roept de wrapper de detector correct aan en is het resultaat zinnig" (tempo binnen tolerantie op een bekende synthetische track), niet de nauwkeurigheid van het onderliggende model/algoritme zelf.
- `test_detection_refine.py`: synthetische beat-tijden met kleine, bekende jitter; verifieert dat de lineaire-regressiefit de ware BPM/ankertijd binnen tolerantie teruggeeft.
- `test_offset_detection.py`: twee synthetische stems met een bekende, opzettelijke offset; verifieert dat de cross-correlatie die offset binnen een kleine tolerantie terugvindt.
- `test_kick_derivation.py`: synthetische "drums"-track met een duidelijk laagfrequent kick-component en hogere ruis; verifieert dat de afgeleide onsets dicht bij de bekende kick-tijden liggen.
- `test_timemap.py`: pure wiskunde, geen engine nodig — verifieert dat `timemap.py` uit een bekende ankerlijst + doel-BPM de juiste `(input_sample, output_sample)`-keyframes berekent.
- `test_warp_renderer_pedalboard.py`: synthetische multi-anchor track warpen via het M8-prototype; verifieert dat de output-segmentduren overeenkomen met de ideale duur bij het doel-tempo.
- `test_warp_renderer_rubberband.py` (`@pytest.mark.requires_rubberband`, geskipt als `rubberband-cli` niet gevonden wordt): verifieert voor de productie-engine dat (a) elk anker sample-nauwkeurig op zijn ideale doel-positie landt, en (b) alle gestretchte stems van één render exact dezelfde output-lengte hebben.
- GUI: kleine pytest-qt smoke-suite (`QT_QPA_PLATFORM=offscreen`), structureel (app/MainWindow bouwt, meerdere synthetische stems laden crasht niet, programmatisch een anker verplaatsen update het gedeelde grid correct over alle stem-rijen) — geen pixel-vergelijkingen of echte drag-simulatie.
- CI (`.github/workflows/ci.yml`): `lint` (`ruff check`/`ruff format --check`), `test-core` (matrix 3.11/3.12, apt-installeert ook `rubberband-cli` zodat `test_warp_renderer_rubberband.py` meedraait, `uv run pytest tests -m "not gui"` — let op: deze job installeert ook PyTorch/pedalboard voor de detectie-/warp-tests, dus iets trager dan een pure NumPy-CI-job, maar blijft zonder Qt), `test-gui` (apt Qt-runtime libs, offscreen, `pytest tests/gui -m gui`).
- WSL2-kanttekening: de GUI zelf bedienen vereist WSLg of een X-server; blokkeert development/CI niet (offscreen-tests werken zonder display).

## Mijlpalen

- **M0 — Scaffolding**: `uv init`, `pyproject.toml` (extras `core`/`gui`/`warp`), ruff-config, pytest-config, package-skeletten onder `src/beatgrid/` (incl. `render/`), `.github/workflows/ci.yml`, `README.md`-stub (met PyTorch/ffmpeg als genoemde install-vereisten), `LICENSE` (MIT), `CLAUDE.md`, `.gitignore`, `docs/ARCHITECTURE.md`-stub, `tests/fixtures.py` met synthetische generators. Geen functionele logica.
- **M1 — Core-fundament**: `project/models.py` (incl. `WarpRender`), `project/project_io.py`, `audio/loader.py`, `audio/validation.py`, `grid/model.py` (single-anchor `generate_beats`), `grid/timeline.py`, `audio/waveform_cache.py`. Volledige unit-testdekking met synthetische multi-stem-fixtures (incl. een bewust-afwijkende offset).
- **M2 — MVP**: `MainWindow`, `stem_track_view.py` (meerdere stems, gelinkte X-as), `grid_overlay.py`, sleepbaar `anchor_item.py` (alleen op referentie-stem), BPM-veld, nudge-controls (ms/samples), referentie-stem-keuze. Komt exact overeen met de MVP-definitie: stems laden + waveform + gedeeld grid tonen + handmatig anker zetten op de referentie-stem.
- **M3 — Automatische detectie**: `detection/base.py`, `beat_this_detector.py` (primair), `librosa_detector.py` (fallback), `registry.py`, `transient.py`, `refine.py` (lineaire-regressie-BPM/anker-fit), `audio/kick_derivation.py` voor wanneer er geen losse kick-stem is. GUI krijgt een "Detect"-actie op de referentie-stem, met keuze uit detector in instellingen.
- **M4 — Stem-validatie, offset-detectie en drift-visualisatie**: `audio/offset_detection.py` (cross-correlatie, altijd met bevestiging), waarschuwings-UI voor samplerate/lengte/offset-afwijkingen, `stem_panel.py` (mute/solo), `drift_overlay.py` (per-stem transients t.o.v. het gedeelde grid, puur diagnostisch).
- **M5 — Multi-anchor tempo-drift (variabel grid)**: uitbreiden naar een geordende ankerlijst, UI om ankers toe te voegen/verplaatsen/verwijderen met waarborgen voor doorlopende `beat_index`-nummering, `refine.py` toegepast per segment, project-breed toegepast op alle stems.
- **M6 — Playback + metronoom**: `playback/audio_player.py` (multi-stem mix tot ~10 stems, mute/solo-gerespecteerd), `metronome.py` (sample-accurate click-mixing), `transport_bar.py`, playhead-sync.
- **M7 — Export v1 + projectbestand**: `export/base.py`, `json_exporter.py`, `export/registry.py`, afronden `project_io.py`, GUI-menu voor export/opslaan/openen. `docs/EXPORT_SCHEMA.md` geschreven.
- **M8 — Variant B prototype**: `render/engines/base.py` (`TimeStretcher`-interface), `render/engines/pedalboard_stretcher.py` (constante ratio per segment + crossfade-splice), `render/warp_renderer.py` (orchestratie, consistent over alle stems), `warp_dialog.py` (doel-BPM kiezen, starten, resultaatoverzicht), `WarpRender`-historie in het projectbestand. Doel: snel een werkend end-to-end warp-pad om de architectuur te valideren. Bouwt expliciet voort op het stabiele multi-anchor-grid uit M5.
- **M9 — Variant B productie-engine**: `render/timemap.py` (keyframes uit ankers + doel-BPM), `render/engines/rubberband_timemap_stretcher.py` (`pyrubberband.timemap_stretch`, native piecewise, faseconsistent), `render/engines/registry.py` (default wordt de Rubber Band-timemap-engine; Pedalboard blijft beschikbaar als alternatief), documentatie van `rubberband-cli` als systeemvereiste (naast ffmpeg). Tests zoals hierboven, incl. de expliciet gevraagde sample-nauwkeurigheids- en gelijke-lengte-check.
- **M10 — Packaging & polish**: PyInstaller-spec (met expliciete aandacht voor de GPL-gevolgen als Pedalboard/rubberband-cli in een gedistribueerde executable terechtkomen — zie licentie-afweging hierboven), undo/redo-afwerking, sneltoetsen, foutafhandeling, perf-pass op lange bestanden/veel stems (pyramide inschakelen waar nodig), README met screenshots, `CLAUDE.md` bijgewerkt met geleerde lessen.
- **Expliciet buiten scope van dit plan (future/optioneel)**: Ableton `.asd`/Rekordbox-export (proprietary formaten); alternatieve/aanvullende detectors zoals madmom's `DBNBeatTracker` of BeatNet via `detection/registry.py`; een MIT-zuivere Signalsmith Stretch-binding als die ooit de moeite waard blijkt.

## Verificatie

- Na M0: `uv sync`, `uv run pytest` (groen/leeg), `uv run ruff check .` slaagt, CI groen op een lege push.
- Na M1: `uv run pytest tests/test_grid_model.py tests/test_validation.py -v` — handmatig doorgerekende verwachte beat-lijsten en validatiewaarschuwingen kloppen voor synthetische multi-stem-sets met bekende offsets.
- Na M2 (MVP): `uv run python -m beatgrid.gui.app` (vereist WSLg/X-server), meerdere synthetische testbestanden als stems laden, zoomen/scrollen synchroon over alle rijen controleren, een anker op de referentie-stem-rij slepen en zien dat het grid op **alle** rijen meebeweegt.
- Na M3/M4: detectie + offset-detectie op synthetische multi-stem-fixtures met bekende BPM/offset/drift draaien en resultaten tegen de bekende waarden verifiëren; `uv run pytest tests/test_offset_detection.py tests/test_kick_derivation.py tests/test_beat_this_detector.py tests/test_librosa_detector.py tests/test_detection_refine.py`.
- Na M6: afspelen met metronoom aan, op gehoor controleren dat klikken exact op de beats vallen en dat mute/solo de mix correct beïnvloedt.
- Na M7: een export genereren en tegen het schema in `docs/EXPORT_SCHEMA.md` controleren; een project opslaan, de app herstarten, heropenen en verifiëren dat alle stems/offsets/ankers behouden blijven.
- Na M8 (prototype): een multi-anchor synthetische track warpen via de Pedalboard-engine en verifiëren dat (a) alle stems nog onderling synchroon lopen, (b) de beats van het resultaat op een regelmatig grid bij het doel-tempo vallen, (c) `uv run pytest tests/test_timemap.py tests/test_warp_renderer_pedalboard.py` slaagt.
- Na M9 (productie): dezelfde check met de Rubber Band-timemap-engine, plus de expliciet gevraagde sample-nauwkeurigheids- en gelijke-lengte-test: `uv run pytest tests/test_warp_renderer_rubberband.py` (vereist `rubberband-cli` lokaal geïnstalleerd, anders geskipt).
- Doorlopend: `uv run pytest tests -m "not gui"` moet na elke mijlpaal groen blijven zonder regressies.
