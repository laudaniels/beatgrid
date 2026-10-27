"""Hover texts for every control, in one place so they stay consistent and
easy to edit. Rich text (a bold title, then an explanation) so Qt wraps long
texts instead of showing one very wide line."""

from __future__ import annotations

# Qt wraps rich-text tooltips quite narrowly; a fixed-width table gives them
# a comfortable reading width instead.
_WIDTH_PX = 440


def tip(title: str, body: str, shortcut: str | None = None) -> str:
    keys = f" &nbsp;<i>({shortcut})</i>" if shortcut else ""
    return f"<table width={_WIDTH_PX}><tr><td><b>{title}</b>{keys}<br>{body}</td></tr></table>"


# --- toolbar ---------------------------------------------------------------

LOAD_STEMS = tip(
    "Load stems",
    "Open the audio files (wav, flac or mp3) of one song's stems as a new project. "
    "A stem with “drum” in its name becomes the reference stem; the beats are "
    "detected on it right away and the grid is placed. This replaces the current "
    "project – save it first if you want to keep it.",
)
OPEN_PROJECT = tip(
    "Open project",
    "Reopen a saved .beatgrid project. The stems are reloaded from where they were "
    "when you saved, and the grid comes back exactly as it was: anchors, tempo, "
    "first downbeat, snapped beats, start offsets and mute/solo.",
    "Ctrl+O",
)
SAVE_PROJECT = tip(
    "Save project",
    "Save the project as a .beatgrid file: the grid and all settings plus the "
    "locations of the stem files. The audio itself isn't copied, so keep the stems "
    "where they are.",
    "Ctrl+S",
)
EXPORT_GRID = tip(
    "Export grid",
    "Write the grid to a JSON file for use in other tools: the tempo, the anchors "
    "and every beat with its time, bar and position in the bar "
    "(format described in docs/EXPORT_SCHEMA.md).",
)
UNDO = tip("Undo", "Take back the last change to the grid or the stems.", "Ctrl+Z")
REDO = tip("Redo", "Redo the change you just undid.", "Ctrl+Shift+Z")
REFERENCE_STEM = tip(
    "Reference stem",
    "The stem the grid is built on: beat detection and Snap beats use its audio, "
    "and its row carries the anchors, the first-downbeat marker and the bar "
    "numbers. Usually the drums – a clear, steady beat works best.",
)
DETECTOR = tip(
    "Beat detector",
    "Which method Detect (and loading stems) uses to find the beats: "
    "<b>beat_this</b> is a neural network – the most accurate, takes a few seconds; "
    "<b>librosa</b> is a simpler, faster classic method.",
)
DETECT = tip(
    "Detect",
    "Find the beats on the reference stem and place the first anchor on the first "
    "beat, with the detected tempo. Tempos above 180 BPM are treated as double "
    "time and halved. Moves the first anchor and clears snapped beats – run Snap "
    "beats again afterwards.",
)
DETECT_OFFSETS = tip(
    "Detect offsets",
    "Check whether every stem starts at exactly the same moment as the reference "
    "stem, by comparing their loudness over time (up to ±2 seconds). You get the "
    "proposed shifts first and they're only applied if you confirm. Stems separated "
    "from the same song normally line up already; on very regular music a proposal "
    "can be off by one beat, so check it.",
)
SHOW_DRIFT = tip(
    "Show drift",
    "Put a dot above every hit (transient) in each stem: <b>blue</b> if it's within "
    "20 ms of a beat line, <b>orange</b> if it's further away. Shows where the music "
    "drifts off the grid – e.g. where an anchor or Snap beats is needed. Only a "
    "display: it never changes the grid. Hits between beats (e.g. eighth notes) "
    "also show as orange.",
)
SNAP_BEATS = tip(
    "Snap beats",
    "Make the grid follow the band: every beat moves onto the hit on the reference "
    "stem within ±{tolerance_ms} ms of where the band currently is – so the grid "
    "keeps up with a live drummer speeding up or slowing down. Beats without a hit "
    "nearby move along with the drift. Anchors stay where they are. Moving, "
    "adding or removing an anchor or changing its tempo clears the snapping; press "
    "Snap beats again afterwards. The status bar shows how many beats snapped.",
)
ADD_ANCHOR = tip(
    "Add anchor",
    "Add an anchor in the middle of the visible part of the reference stem, with "
    "the tempo estimated from the audio around it. An anchor pins the grid at that "
    "point with its own tempo up to the next anchor – use one where the song really "
    "changes tempo or where the grid runs off. Drag it onto the right beat.",
)
REMOVE_ANCHOR = tip(
    "Remove anchor",
    "Remove the selected anchor (click an anchor to select it; it turns red). The "
    "grid is then carried by the remaining anchors. The last anchor can't be "
    "removed.",
    "Delete",
)
WARP = tip(
    "Warp",
    "Time-stretch every stem onto one constant tempo – by default the song's own "
    "average tempo – so a DAW can take it from there. The files are written to a "
    "“warped” folder next to the reference stem, named with their tempo; they "
    "carry that tempo (and, with the default engine, a marker on every bar) and "
    "start on a whole bar so they line up in a DAW. The originals are never "
    "changed. Download and clean-up are in the same dialog.",
)

# --- tracks ----------------------------------------------------------------

STEM_NAME_BAR = tip(
    "Enlarge this stem",
    "Click to give this stem half of the tracks area; the others share the rest. "
    "Click it again to return to equal heights, or click another stem to enlarge "
    "that one instead. Only changes the view – the reference stem stays the same.",
)
MUTE = tip(
    "Mute",
    "Silence this stem during playback. Doesn't affect warping: every stem is always warped.",
)
SOLO = tip(
    "Solo",
    "Play only the soloed stems (you can solo several). Doesn't affect warping.",
)
ANCHOR = tip(
    "Anchor",
    "Pins the grid here, with its own tempo up to the next anchor. Drag it onto "
    "the beat it belongs on; click it to select it – the BPM field and the nudge "
    "buttons below then act on this anchor (selected anchor is red).",
)
FIRST_DOWNBEAT = tip(
    "First downbeat (bar 1)",
    "Drag this marker onto the beat where the first bar starts; it lands on the "
    "nearest beat when you let go. Bar numbers, the bar lines, the metronome's "
    "accent, the bar markers in warped files and their bar alignment all count "
    "from here. Beats before it become a pickup.",
)
TIME_SCROLLBAR = tip(
    "Scroll through the song",
    "Move left and right through all stems at once. The handle shows how much of "
    "the song is visible: zoom with the mouse wheel over a waveform, drag a "
    "waveform to move it. Double-click a waveform to play from that point.",
)

# --- transport bar ---------------------------------------------------------

PLAY = tip(
    "Play / pause",
    "Play all stems mixed together from the playhead, with mute/solo applied. Tip: "
    "double-click a waveform to start playing from that point.",
    "Space",
)
METRONOME = tip(
    "Metronome",
    "Play a click on every beat of the grid while playing back, with an accent on "
    "the first beat of each bar – the quickest way to hear whether the grid is right.",
)
BPM = tip(
    "Tempo of the selected anchor",
    "The tempo (beats per minute) from the selected anchor up to the next one. "
    "Changing it re-spaces the beats after that anchor (and clears snapped beats). "
    "Maximum 180 BPM.",
)
NUDGE_MS = tip(
    "Nudge anchor",
    "Move the selected anchor – and with it the grid after it – {amount} earlier "
    "(-) or later (+), for fine alignment by ear with the metronome.",
)
NUDGE_SAMPLE = tip(
    "Nudge anchor by one sample",
    "Move the selected anchor one audio sample {direction} – the finest possible adjustment.",
)

# --- warp dialog -----------------------------------------------------------

WARP_TARGET_BPM = tip(
    "Target tempo",
    "The constant tempo every stem is stretched to. Defaults to the song's own "
    "average tempo, rounded to 2 decimals, so the stems hardly change and you can "
    "type the exact same tempo into your DAW. Maximum 180 BPM.",
)
WARP_ENGINE = tip(
    "Stretch engine",
    "<b>rubberband-timemap</b>: the default – best quality, precise beat placement, "
    "writes bar markers. <b>pedalboard</b>: an older prototype, kept for "
    "comparison.",
)
WARP_RENDER = tip(
    "Render",
    "Warp all stems to the target tempo and write them to the warped folder. "
    "Re-rendering at the same tempo replaces the previous files; other tempos are "
    "kept alongside. Takes a few seconds per stem.",
)
WARP_CLOSE = tip("Close", "Close this dialog. Rendered files stay where they are.")
WARP_DOWNLOAD = tip(
    "Download",
    "Copy the files of the latest render to a folder you choose – by default your "
    "Windows Downloads folder, so a Windows program like FL Studio can reach them "
    "easily. The folder you pick is remembered.",
)
WARP_CLEANUP = tip(
    "Clean up warped folder",
    "Delete the warped files in<br><i>{folder}</i><br>after asking for confirmation. "
    "Only BeatGrid's warp output (files named *_warped*.wav) is deleted – never "
    "your original stems or anything else in that folder.",
)

# --- title bar -------------------------------------------------------------

TITLE_MINIMIZE = tip(
    "Minimise", "Hide BeatGrid to the taskbar; click its taskbar icon to bring it back."
)
TITLE_MAXIMIZE = tip(
    "Maximise",
    "Fill the screen with BeatGrid. You can also double-click the title bar; drag "
    "the title bar to move the window and its edges or corners to resize it.",
)
TITLE_RESTORE = tip(
    "Restore",
    "Back to a normal-size window, which you can move by dragging the title bar and "
    "resize by dragging its edges or corners. Double-clicking the title bar does "
    "the same.",
)
TITLE_CLOSE = tip(
    "Close BeatGrid",
    "Quit the app. Unsaved changes to the project are lost – use Save project first "
    "if you want to keep them. Warped files stay on disk.",
)
