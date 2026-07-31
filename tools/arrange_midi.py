#!/usr/bin/env python3
"""Create the deterministic, compressed four-channel NES Tetris soundtrack.

The source MIDI is never copied into the project.  The generated JSON and C
arrays contain only a locally arranged 2A03 reduction.  Eight sixteenth-note
steps form one pattern; repeated patterns and four-channel pattern tuples are
deduplicated before the remaining values are nibble packed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

try:
    import mido
except ImportError as exc:  # pragma: no cover - exercised only without dependency
    raise SystemExit(
        "mido is required; install it with: python -m pip install mido"
    ) from exc


SOURCE_BEAT_START = 8
SOURCE_BEAT_END = 620
STEPS_PER_BEAT = 4
STEP_COUNT = (SOURCE_BEAT_END - SOURCE_BEAT_START) * STEPS_PER_BEAT
PATTERN_STEPS = 8
ORDER_COUNT = STEP_COUNT // PATTERN_STEPS
ORDER_PAGE_SIZE = 256
ORDER_PAGE_LENGTHS = (ORDER_PAGE_SIZE, ORDER_COUNT - ORDER_PAGE_SIZE)

if STEP_COUNT % PATTERN_STEPS:
    raise RuntimeError("music section must contain a whole number of patterns")

TRACK_VOCAL = "Vocal"
TRACK_BELL = "Bell"
TRACK_SYNTH_PICKUP = "Synth 2"
TRACK_SYNTH = "Synth 1"
TRACK_BASS = "Bass"
TRACK_DRUMS = "Drums"

# Values are the runtime playback contract, not the collision priority.
NOISE_CODES = {
    "rest": 0,
    "closed_hat": 1,
    "open_hat": 2,
    "kick": 3,
    "snare": 4,
    "tom_stick": 5,
    "cymbal": 6,
}

# Collision priority is cymbal > snare > kick > tom/stick > open > closed.
# It must remain independent from the runtime code values above.
NOISE_PRIORITY_BY_CODE = {
    NOISE_CODES["closed_hat"]: 1,
    NOISE_CODES["open_hat"]: 2,
    NOISE_CODES["tom_stick"]: 3,
    NOISE_CODES["kick"]: 4,
    NOISE_CODES["snare"]: 5,
    NOISE_CODES["cymbal"]: 6,
}

# General MIDI percussion notes.  Hand clap is kept with the snare family;
# pedal hi-hat is kept with closed hi-hat.  Unsupported auxiliary percussion
# is deliberately omitted so that it cannot displace the six NES noise voices.
DRUM_NOTE_TO_CODE = {
    **{note: NOISE_CODES["cymbal"] for note in (49, 51, 52, 53, 55, 57, 59)},
    **{note: NOISE_CODES["snare"] for note in (38, 39, 40)},
    **{note: NOISE_CODES["kick"] for note in (35, 36)},
    **{
        note: NOISE_CODES["tom_stick"]
        for note in (37, 41, 43, 45, 47, 48, 50)
    },
    46: NOISE_CODES["open_hat"],
    42: NOISE_CODES["closed_hat"],
    44: NOISE_CODES["closed_hat"],
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "tetris_music.json"
MUSIC_DATA_START_MARKER = "/* MUSIC_DATA_START */"
MUSIC_DATA_END_MARKER = "/* MUSIC_DATA_END */"
CHANNELS = ("pulse1", "pulse2", "triangle", "noise")
TONAL_CHANNELS = ("pulse1", "pulse2", "triangle")
C_CHANNEL_STEMS = {
    "pulse1": "PULSE1",
    "pulse2": "PULSE2",
    "triangle": "TRIANGLE",
    "noise": "NOISE",
}
C_VALUES_PER_LINE = 16


@dataclass(frozen=True)
class NoteEvent:
    start_tick: int
    end_tick: int
    note: int
    velocity: int
    sequence: int


def clean_track_name(name: str) -> str:
    """Remove the NUL padding used by the source MIDI's track names."""

    return name.replace("\x00", "").strip()


def discover_default_input() -> Path:
    """Find a direct child of Downloads whose MIDI filename contains ``88``."""

    downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        raise FileNotFoundError(f"Downloads directory not found: {downloads}")

    candidates = sorted(
        (
            path
            for path in downloads.iterdir()
            if path.is_file()
            and "88" in path.name
            and path.suffix.casefold() in {".mid", ".midi"}
        ),
        key=lambda path: (path.name.casefold(), path.name),
    )
    if not candidates:
        raise FileNotFoundError(
            f"no direct MIDI file containing '88' was found in {downloads}"
        )
    return candidates[0]


def resolve_input(explicit_input: Path | None) -> Path:
    source = explicit_input.expanduser() if explicit_input else discover_default_input()
    if not source.is_file():
        raise FileNotFoundError(f"MIDI input not found: {source}")
    if source.suffix.casefold() not in {".mid", ".midi"}:
        raise ValueError(f"input must be a .mid or .midi file: {source}")
    return source


def track_name(track: mido.MidiTrack) -> str:
    for message in track:
        if message.type == "track_name":
            return clean_track_name(message.name)
    return ""


def find_track(mid: mido.MidiFile, wanted_name: str) -> mido.MidiTrack:
    matches = [
        track
        for track in mid.tracks
        if track_name(track).casefold() == wanted_name.casefold()
    ]
    if len(matches) != 1:
        available = ", ".join(
            repr(name) for name in (track_name(track) for track in mid.tracks) if name
        )
        raise ValueError(
            f"expected exactly one {wanted_name!r} track, found {len(matches)}; "
            f"available tracks: {available}"
        )
    return matches[0]


def extract_note_events(track: mido.MidiTrack) -> list[NoteEvent]:
    """Pair note-on/off messages and retain deterministic onset ordering."""

    absolute_tick = 0
    sequence = 0
    active: dict[tuple[int, int], tuple[int, int, int]] = {}
    events: list[NoteEvent] = []

    for message in track:
        absolute_tick += message.time
        if message.type == "note_on" and message.velocity > 0:
            key = (message.channel, message.note)
            # Treat an unclosed duplicate note-on as a retrigger.  This avoids
            # an ambiguous stack of equal pitches and is stable across mido versions.
            previous = active.pop(key, None)
            if previous is not None:
                start_tick, velocity, previous_sequence = previous
                events.append(
                    NoteEvent(
                        start_tick,
                        absolute_tick,
                        message.note,
                        velocity,
                        previous_sequence,
                    )
                )
            active[key] = (absolute_tick, message.velocity, sequence)
            sequence += 1
        elif message.type in {"note_off", "note_on"} and hasattr(message, "note"):
            key = (message.channel, message.note)
            previous = active.pop(key, None)
            if previous is not None:
                start_tick, velocity, previous_sequence = previous
                events.append(
                    NoteEvent(
                        start_tick,
                        absolute_tick,
                        message.note,
                        velocity,
                        previous_sequence,
                    )
                )

    # Close malformed/dangling notes at the track end rather than discarding them.
    for (_channel, note), (start_tick, velocity, event_sequence) in active.items():
        events.append(
            NoteEvent(start_tick, absolute_tick, note, velocity, event_sequence)
        )

    return sorted(
        events,
        key=lambda event: (event.start_tick, event.sequence, event.note, event.end_tick),
    )


def step_bounds(step: int, ticks_per_beat: int) -> tuple[float, float]:
    section_start = SOURCE_BEAT_START * ticks_per_beat
    return (
        section_start + step * ticks_per_beat / STEPS_PER_BEAT,
        section_start + (step + 1) * ticks_per_beat / STEPS_PER_BEAT,
    )


def overlapping_events(
    events: Iterable[NoteEvent], slot_start: float, slot_end: float
) -> list[tuple[NoteEvent, float]]:
    return [
        (event, min(event.end_tick, slot_end) - max(event.start_tick, slot_start))
        for event in events
        if event.end_tick > slot_start and event.start_tick < slot_end
    ]


def pick_overlap_note(
    events: Sequence[NoteEvent], slot_start: float, slot_end: float
) -> int:
    candidates = overlapping_events(events, slot_start, slot_end)
    if not candidates:
        return 0
    event, _overlap = max(
        candidates,
        key=lambda candidate: (
            candidate[1],
            candidate[0].velocity,
            candidate[0].start_tick,
            candidate[0].sequence,
            candidate[0].note,
        ),
    )
    return event.note


def arrange_pulse1(
    vocal_events: Sequence[NoteEvent],
    bell_events: Sequence[NoteEvent],
    pickup_events: Sequence[NoteEvent],
    ticks_per_beat: int,
) -> list[int]:
    """Use vocal, then bell, then the opening Synth 2 pickup by priority."""

    result: list[int] = []
    for step in range(STEP_COUNT):
        slot_start, slot_end = step_bounds(step, ticks_per_beat)
        note = 0
        for events in (vocal_events, bell_events, pickup_events):
            note = pick_overlap_note(events, slot_start, slot_end)
            if note:
                break
        if note < 29 or note > 95:
            note = 0
        result.append(note)
    return result


def quantized_step(tick: int, ticks_per_beat: int) -> int:
    """Round an absolute tick to the nearest section-local sixteenth step."""

    section_start = SOURCE_BEAT_START * ticks_per_beat
    numerator = (tick - section_start) * STEPS_PER_BEAT
    quotient, remainder = divmod(numerator, ticks_per_beat)
    if remainder * 2 >= ticks_per_beat:
        quotient += 1
    return max(0, min(STEP_COUNT - 1, quotient))


def onset_events_in_section(
    events: Iterable[NoteEvent], ticks_per_beat: int
) -> list[NoteEvent]:
    section_start = SOURCE_BEAT_START * ticks_per_beat
    section_end = SOURCE_BEAT_END * ticks_per_beat
    return [
        event
        for event in events
        if section_start <= event.start_tick < section_end
    ]


def arrange_pulse2(
    synth_events: Sequence[NoteEvent], ticks_per_beat: int
) -> list[int]:
    """Quantize Synth 1 onsets and give every onset one sixteenth-note gate."""

    section_start = SOURCE_BEAT_START * ticks_per_beat
    by_step: list[list[NoteEvent]] = [[] for _ in range(STEP_COUNT)]
    for event in onset_events_in_section(synth_events, ticks_per_beat):
        by_step[quantized_step(event.start_tick, ticks_per_beat)].append(event)

    result = [0] * STEP_COUNT
    for step, candidates in enumerate(by_step):
        if not candidates:
            continue
        grid_tick = section_start + step * ticks_per_beat / STEPS_PER_BEAT
        winner = max(
            candidates,
            key=lambda event: (
                -abs(event.start_tick - grid_tick),
                event.velocity,
                event.start_tick,
                event.sequence,
                event.note,
            ),
        )
        result[step] = winner.note
    return result


def fold_triangle_note(note: int) -> int:
    while note < 29:
        note += 12
    return note


def arrange_triangle(
    bass_events: Sequence[NoteEvent], ticks_per_beat: int
) -> list[int]:
    result: list[int] = []
    for step in range(STEP_COUNT):
        slot_start, slot_end = step_bounds(step, ticks_per_beat)
        candidates = overlapping_events(bass_events, slot_start, slot_end)
        if not candidates:
            result.append(0)
            continue

        lowest_note = min(event.note for event, _overlap in candidates)
        same_pitch = [
            candidate for candidate in candidates if candidate[0].note == lowest_note
        ]
        winner, _overlap = max(
            same_pitch,
            key=lambda candidate: (
                candidate[1],
                candidate[0].velocity,
                candidate[0].start_tick,
                candidate[0].sequence,
            ),
        )
        result.append(fold_triangle_note(winner.note))
    return result


def arrange_noise(
    drum_events: Sequence[NoteEvent], ticks_per_beat: int
) -> list[int]:
    section_start = SOURCE_BEAT_START * ticks_per_beat
    by_step: list[list[tuple[NoteEvent, int]]] = [
        [] for _ in range(STEP_COUNT)
    ]
    for event in onset_events_in_section(drum_events, ticks_per_beat):
        code = DRUM_NOTE_TO_CODE.get(event.note)
        if code is None:
            continue
        by_step[quantized_step(event.start_tick, ticks_per_beat)].append((event, code))

    result = [NOISE_CODES["rest"]] * STEP_COUNT
    for step, candidates in enumerate(by_step):
        if not candidates:
            continue
        grid_tick = section_start + step * ticks_per_beat / STEPS_PER_BEAT
        winner, code = max(
            candidates,
            key=lambda candidate: (
                NOISE_PRIORITY_BY_CODE[candidate[1]],
                candidate[0].velocity,
                -abs(candidate[0].start_tick - grid_tick),
                candidate[0].start_tick,
                candidate[0].sequence,
                candidate[0].note,
            ),
        )
        del winner  # The selected event only determines the category code.
        result[step] = code
    return result


def meta_at_section_start(mid: mido.MidiFile) -> tuple[int, int, int]:
    """Return tempo and time signature in effect at the arranged first beat."""

    target_tick = SOURCE_BEAT_START * mid.ticks_per_beat
    tempo_events: list[tuple[int, int, int, int]] = []
    signature_events: list[tuple[int, int, int, int, int]] = []
    for track_index, track in enumerate(mid.tracks):
        absolute_tick = 0
        for message_index, message in enumerate(track):
            absolute_tick += message.time
            if absolute_tick > target_tick:
                continue
            if message.type == "set_tempo":
                tempo_events.append(
                    (absolute_tick, track_index, message_index, message.tempo)
                )
            elif message.type == "time_signature":
                signature_events.append(
                    (
                        absolute_tick,
                        track_index,
                        message_index,
                        message.numerator,
                        message.denominator,
                    )
                )

    tempo = max(tempo_events, default=(0, 0, 0, 500_000))[-1]
    signature = max(signature_events, default=(0, 0, 0, 4, 4))
    return tempo, signature[-2], signature[-1]


def source_seconds_between(mid: mido.MidiFile, start_tick: int, end_tick: int) -> float:
    """Integrate all deterministic tempo events over a source-tick interval."""

    tempo_events: list[tuple[int, int, int, int]] = []
    for track_index, track in enumerate(mid.tracks):
        absolute_tick = 0
        for message_index, message in enumerate(track):
            absolute_tick += message.time
            if message.type == "set_tempo":
                tempo_events.append(
                    (absolute_tick, track_index, message_index, message.tempo)
                )
    tempo_events.sort()

    cursor = start_tick
    tempo = 500_000
    seconds = 0.0
    for tick, _track_index, _message_index, new_tempo in tempo_events:
        if tick <= start_tick:
            tempo = new_tempo
            continue
        if tick >= end_tick:
            break
        seconds += mido.tick2second(tick - cursor, mid.ticks_per_beat, tempo)
        cursor = tick
        tempo = new_tempo
    seconds += mido.tick2second(end_tick - cursor, mid.ticks_per_beat, tempo)
    return seconds


def beat_value(tick: int, ticks_per_beat: int) -> int | float:
    quotient, remainder = divmod(tick, ticks_per_beat)
    if not remainder:
        return quotient
    return round(tick / ticks_per_beat, 6)


def section_meta_events(mid: mido.MidiFile) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return inherited and in-section tempo/signature events for documentation."""

    start_tick = SOURCE_BEAT_START * mid.ticks_per_beat
    end_tick = SOURCE_BEAT_END * mid.ticks_per_beat
    tempo, numerator, denominator = meta_at_section_start(mid)
    tempos: list[dict[str, object]] = [
        {
            "beat": SOURCE_BEAT_START,
            "tempo_us_per_beat": tempo,
            "bpm": round(mido.tempo2bpm(tempo), 6),
        }
    ]
    signatures: list[dict[str, object]] = [
        {
            "beat": SOURCE_BEAT_START,
            "numerator": numerator,
            "denominator": denominator,
        }
    ]

    events: list[tuple[int, int, int, object]] = []
    for track_index, track in enumerate(mid.tracks):
        absolute_tick = 0
        for message_index, message in enumerate(track):
            absolute_tick += message.time
            if start_tick < absolute_tick < end_tick and message.type in {
                "set_tempo",
                "time_signature",
            }:
                events.append((absolute_tick, track_index, message_index, message))
    for tick, _track_index, _message_index, message in sorted(events):
        beat = beat_value(tick, mid.ticks_per_beat)
        if message.type == "set_tempo":
            tempos.append(
                {
                    "beat": beat,
                    "tempo_us_per_beat": message.tempo,
                    "bpm": round(mido.tempo2bpm(message.tempo), 6),
                }
            )
        else:
            signatures.append(
                {
                    "beat": beat,
                    "numerator": message.numerator,
                    "denominator": message.denominator,
                }
            )
    return tempos, signatures


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fold_tonal_patterns(values: Sequence[int]) -> tuple[list[int], int]:
    """Octave-fold only patterns too wide for the local four-bit pitch code."""

    folded = list(values)
    changed = 0
    for offset in range(0, len(folded), PATTERN_STEPS):
        pattern = folded[offset : offset + PATTERN_STEPS]
        sounding = [note for note in pattern if note]
        if not sounding:
            continue
        base = min(sounding)
        for index, note in enumerate(pattern):
            original = note
            while note and note > base + 14:
                note -= 12
            if note != original:
                changed += 1
                pattern[index] = note
        folded[offset : offset + PATTERN_STEPS] = pattern
    return folded, changed


def deduplicate(items: Iterable[tuple[int, ...]]) -> tuple[list[tuple[int, ...]], list[int]]:
    pool: list[tuple[int, ...]] = []
    ids: dict[tuple[int, ...], int] = {}
    order: list[int] = []
    for item in items:
        item_id = ids.get(item)
        if item_id is None:
            item_id = len(pool)
            ids[item] = item_id
            pool.append(item)
        order.append(item_id)
    return pool, order


def pack_tonal_patterns(patterns: Sequence[tuple[int, ...]]) -> dict[str, object]:
    bases: list[int] = []
    pairs: list[list[int]] = [[] for _ in range(PATTERN_STEPS // 2)]
    for pattern in patterns:
        sounding = [note for note in pattern if note]
        base = min(sounding) if sounding else 0
        codes = [0 if note == 0 else note - base + 1 for note in pattern]
        if any(code < 0 or code > 15 for code in codes):
            raise ValueError(f"tonal pattern exceeds four-bit pitch window: {pattern}")
        bases.append(base)
        for pair_index in range(PATTERN_STEPS // 2):
            high = codes[pair_index * 2]
            low = codes[pair_index * 2 + 1]
            pairs[pair_index].append((high << 4) | low)
    return {"base": bases, "pairs": pairs}


def pack_noise_patterns(patterns: Sequence[tuple[int, ...]]) -> dict[str, object]:
    pairs: list[list[int]] = [[] for _ in range(PATTERN_STEPS // 2)]
    for pattern in patterns:
        for pair_index in range(PATTERN_STEPS // 2):
            high = pattern[pair_index * 2]
            low = pattern[pair_index * 2 + 1]
            pairs[pair_index].append((high << 4) | low)
    return {"pairs": pairs}


def encoded_size_bytes(payload: dict[str, object]) -> int:
    patterns = payload["patterns"]
    tuples = payload["tuples"]
    order_pages = payload["order_pages"]
    assert isinstance(patterns, dict)
    assert isinstance(tuples, dict)
    assert isinstance(order_pages, list)
    total = 0
    for channel in TONAL_CHANNELS:
        packed = patterns[channel]
        assert isinstance(packed, dict)
        total += len(packed["base"])
        total += sum(len(page) for page in packed["pairs"])
    noise = patterns["noise"]
    assert isinstance(noise, dict)
    total += sum(len(page) for page in noise["pairs"])
    total += sum(len(tuples[channel]) for channel in CHANNELS)
    total += sum(len(page) for page in order_pages)
    return total


def compress_channels(raw_channels: dict[str, list[int]]) -> tuple[dict[str, object], dict[str, int]]:
    """Build first-use-stable pattern, tuple, and order dictionaries."""

    folded_channels: dict[str, list[int]] = {}
    folded_counts: dict[str, int] = {}
    for channel in CHANNELS:
        values = raw_channels[channel]
        if len(values) != STEP_COUNT:
            raise ValueError(f"{channel} must contain {STEP_COUNT} raw steps")
        if channel in TONAL_CHANNELS:
            if any(note < 0 or note > 95 or (note and note < 29) for note in values):
                raise ValueError(f"{channel} contains an unsupported 2A03 pitch")
            folded, changed = fold_tonal_patterns(values)
            folded_channels[channel] = folded
            folded_counts[channel] = changed
        else:
            if any(code < 0 or code > 6 for code in values):
                raise ValueError("noise codes must be in the range 0..6")
            folded_channels[channel] = list(values)
            folded_counts[channel] = 0

    pattern_pools: dict[str, list[tuple[int, ...]]] = {}
    channel_orders: dict[str, list[int]] = {}
    for channel in CHANNELS:
        values = folded_channels[channel]
        pool, order = deduplicate(
            tuple(values[offset : offset + PATTERN_STEPS])
            for offset in range(0, STEP_COUNT, PATTERN_STEPS)
        )
        if len(pool) > 256:
            raise ValueError(f"{channel} needs more than 256 pattern IDs")
        pattern_pools[channel] = pool
        channel_orders[channel] = order

    tuple_pool, song_order = deduplicate(
        tuple(channel_orders[channel][index] for channel in CHANNELS)
        for index in range(ORDER_COUNT)
    )
    if len(tuple_pool) > 256:
        raise ValueError("arrangement needs more than 256 tuple IDs")

    payload: dict[str, object] = {
        "patterns": {
            **{
                channel: pack_tonal_patterns(pattern_pools[channel])
                for channel in TONAL_CHANNELS
            },
            "noise": pack_noise_patterns(pattern_pools["noise"]),
        },
        "tuples": {
            channel: [entry[index] for entry in tuple_pool]
            for index, channel in enumerate(CHANNELS)
        },
        "order_pages": [
            song_order[:ORDER_PAGE_SIZE],
            song_order[ORDER_PAGE_SIZE:],
        ],
    }
    return payload, folded_counts


def arrange_midi(source: Path) -> dict[str, object]:
    mid = mido.MidiFile(filename=str(source))
    tracks = {
        "vocal": find_track(mid, TRACK_VOCAL),
        "bell": find_track(mid, TRACK_BELL),
        "pickup": find_track(mid, TRACK_SYNTH_PICKUP),
        "synth": find_track(mid, TRACK_SYNTH),
        "bass": find_track(mid, TRACK_BASS),
        "drums": find_track(mid, TRACK_DRUMS),
    }
    events = {key: extract_note_events(track) for key, track in tracks.items()}
    tempo, numerator, denominator = meta_at_section_start(mid)
    tempo_events, signature_events = section_meta_events(mid)
    raw_channels = {
        "pulse1": arrange_pulse1(
            events["vocal"],
            events["bell"],
            events["pickup"],
            mid.ticks_per_beat,
        ),
        "pulse2": arrange_pulse2(events["synth"], mid.ticks_per_beat),
        "triangle": arrange_triangle(events["bass"], mid.ticks_per_beat),
        "noise": arrange_noise(events["drums"], mid.ticks_per_beat),
    }
    payload, folded_counts = compress_channels(raw_channels)
    patterns = payload["patterns"]
    tuples = payload["tuples"]
    assert isinstance(patterns, dict)
    assert isinstance(tuples, dict)
    pattern_counts = {
        channel: len(patterns[channel]["base"])
        if channel in TONAL_CHANNELS
        else len(patterns[channel]["pairs"][0])
        for channel in CHANNELS
    }
    tuple_count = len(tuples["pulse1"])

    metadata: dict[str, object] = {
            "format": "fami-c-nes-arrangement-v2",
            "source_file": source.name,
            "source_sha256": sha256_file(source),
            "source_ticks_per_beat": mid.ticks_per_beat,
            "source_beats": [SOURCE_BEAT_START, SOURCE_BEAT_END],
            "source_file_duration_seconds": round(mid.length, 6),
            "source_duration_seconds": round(
                source_seconds_between(
                    mid,
                    SOURCE_BEAT_START * mid.ticks_per_beat,
                    SOURCE_BEAT_END * mid.ticks_per_beat,
                ),
                6,
            ),
            "source_tempo_us_per_beat": tempo,
            "source_bpm": round(mido.tempo2bpm(tempo), 3),
            "source_time_signature": [numerator, denominator],
            "source_tempo_events": tempo_events,
            "source_time_signature_events": signature_events,
            "bars": (SOURCE_BEAT_END - SOURCE_BEAT_START) // 4,
            "steps_per_beat": STEPS_PER_BEAT,
            "step_count": STEP_COUNT,
            "pattern_steps": PATTERN_STEPS,
            "order_count": ORDER_COUNT,
            "order_page_lengths": list(ORDER_PAGE_LENGTHS),
            "pattern_counts": pattern_counts,
            "tuple_count": tuple_count,
            "uncompressed_bytes": STEP_COUNT * len(CHANNELS),
            "track_mapping": {
                "pulse1": [TRACK_VOCAL, TRACK_BELL, TRACK_SYNTH_PICKUP],
                "pulse2": TRACK_SYNTH,
                "triangle": TRACK_BASS,
                "noise": TRACK_DRUMS,
            },
            "noise_codes": NOISE_CODES,
            "tonal_encoding": "base plus four high-nibble-first step pairs",
            "octave_folded_cells": folded_counts,
    }
    metadata["compressed_bytes"] = encoded_size_bytes(payload)
    result: dict[str, object] = {"metadata": metadata, **payload}
    validate_arrangement(result)
    return result


def validate_arrangement(arrangement: dict[str, object]) -> None:
    """Fail fast if compressed data cannot be represented by the NES player."""

    metadata = arrangement.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    if metadata.get("format") != "fami-c-nes-arrangement-v2":
        raise ValueError("metadata.format must be fami-c-nes-arrangement-v2")
    if metadata.get("source_beats") != [SOURCE_BEAT_START, SOURCE_BEAT_END]:
        raise ValueError("metadata.source_beats does not match the runtime contract")
    if metadata.get("step_count") != STEP_COUNT:
        raise ValueError(f"metadata.step_count must be {STEP_COUNT}")
    if metadata.get("pattern_steps") != PATTERN_STEPS:
        raise ValueError(f"metadata.pattern_steps must be {PATTERN_STEPS}")
    if metadata.get("order_count") != ORDER_COUNT:
        raise ValueError(f"metadata.order_count must be {ORDER_COUNT}")
    if metadata.get("order_page_lengths") != list(ORDER_PAGE_LENGTHS):
        raise ValueError("metadata.order_page_lengths does not match the player")

    patterns = arrangement.get("patterns")
    tuples = arrangement.get("tuples")
    order_pages = arrangement.get("order_pages")
    if not isinstance(patterns, dict):
        raise ValueError("patterns must be an object")
    if not isinstance(tuples, dict):
        raise ValueError("tuples must be an object")
    if not isinstance(order_pages, list) or len(order_pages) != 2:
        raise ValueError("order_pages must contain two arrays")

    def byte_array(value: object, label: str, expected: int | None = None) -> list[int]:
        if not isinstance(value, list) or any(type(item) is not int for item in value):
            raise ValueError(f"{label} must be an integer array")
        if expected is not None and len(value) != expected:
            raise ValueError(f"{label} must contain {expected} bytes")
        if any(item < 0 or item > 255 for item in value):
            raise ValueError(f"{label} values must fit in one byte")
        return value

    pattern_counts: dict[str, int] = {}
    for channel in CHANNELS:
        packed = patterns.get(channel)
        if not isinstance(packed, dict):
            raise ValueError(f"patterns.{channel} must be an object")
        pairs = packed.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != PATTERN_STEPS // 2:
            raise ValueError(f"patterns.{channel}.pairs must contain four arrays")
        if channel in TONAL_CHANNELS:
            bases = byte_array(packed.get("base"), f"patterns.{channel}.base")
            count = len(bases)
            if count == 0 or count > 256:
                raise ValueError(f"patterns.{channel} count must be 1..256")
            if any(base != 0 and not 29 <= base <= 95 for base in bases):
                raise ValueError(f"patterns.{channel}.base contains an invalid pitch")
        else:
            first_pair = byte_array(pairs[0], "patterns.noise.pairs[0]")
            count = len(first_pair)
            if count == 0 or count > 256:
                raise ValueError("patterns.noise count must be 1..256")
        checked_pairs = [
            byte_array(pair, f"patterns.{channel}.pairs[{index}]", count)
            for index, pair in enumerate(pairs)
        ]
        if channel in TONAL_CHANNELS:
            bases = packed["base"]
            assert isinstance(bases, list)
            for pattern_id, base in enumerate(bases):
                for pair in checked_pairs:
                    packed_value = pair[pattern_id]
                    for code in (packed_value >> 4, packed_value & 0x0F):
                        if code and (base == 0 or base + code - 1 > 95):
                            raise ValueError(
                                f"patterns.{channel} decodes outside the pitch range"
                            )
        else:
            for pair in checked_pairs:
                if any((value >> 4) > 6 or (value & 0x0F) > 6 for value in pair):
                    raise ValueError("noise pattern contains an invalid nibble code")
        pattern_counts[channel] = count

    tuple_arrays = {
        channel: byte_array(tuples.get(channel), f"tuples.{channel}")
        for channel in CHANNELS
    }
    tuple_count = len(tuple_arrays["pulse1"])
    if tuple_count == 0 or tuple_count > 256:
        raise ValueError("tuple count must be 1..256")
    for channel, values in tuple_arrays.items():
        if len(values) != tuple_count:
            raise ValueError("all tuple channel arrays must have equal length")
        if any(pattern_id >= pattern_counts[channel] for pattern_id in values):
            raise ValueError(f"tuples.{channel} references a missing pattern")

    checked_order_pages = [
        byte_array(page, f"order_pages[{index}]", ORDER_PAGE_LENGTHS[index])
        for index, page in enumerate(order_pages)
    ]
    if any(tuple_id >= tuple_count for page in checked_order_pages for tuple_id in page):
        raise ValueError("order page references a missing tuple")

    if metadata.get("pattern_counts") != pattern_counts:
        raise ValueError("metadata.pattern_counts does not match pattern data")
    if metadata.get("tuple_count") != tuple_count:
        raise ValueError("metadata.tuple_count does not match tuple data")
    size = encoded_size_bytes(arrangement)
    if metadata.get("compressed_bytes") != size:
        raise ValueError("metadata.compressed_bytes does not match encoded arrays")


def render_json(arrangement: dict[str, object]) -> str:
    return json.dumps(arrangement, indent=2, ensure_ascii=True) + "\n"


def c_array_values(arrangement: dict[str, object]) -> list[tuple[str, list[int]]]:
    validate_arrangement(arrangement)
    patterns = arrangement["patterns"]
    tuples = arrangement["tuples"]
    order_pages = arrangement["order_pages"]
    assert isinstance(patterns, dict)
    assert isinstance(tuples, dict)
    assert isinstance(order_pages, list)
    arrays: list[tuple[str, list[int]]] = []
    for channel in TONAL_CHANNELS:
        stem = C_CHANNEL_STEMS[channel]
        packed = patterns[channel]
        assert isinstance(packed, dict)
        arrays.append((f"MUSIC_{stem}_BASE", packed["base"]))
        for pair_index, values in enumerate(packed["pairs"]):
            arrays.append((f"MUSIC_{stem}_PAIR{pair_index}", values))
    noise = patterns["noise"]
    assert isinstance(noise, dict)
    for pair_index, values in enumerate(noise["pairs"]):
        arrays.append((f"MUSIC_NOISE_PAIR{pair_index}", values))
    for channel in CHANNELS:
        arrays.append((f"MUSIC_TUPLE_{C_CHANNEL_STEMS[channel]}", tuples[channel]))
    for page_index, values in enumerate(order_pages):
        arrays.append((f"MUSIC_ORDER{page_index}", values))
    return arrays


def render_c_arrays(arrangement: dict[str, object], newline: str = "\n") -> str:
    """Render the 25 compressed runtime arrays in their fixed ABI order."""

    blocks: list[str] = []
    for symbol, values in c_array_values(arrangement):
        lines = [f"const unsigned char {symbol}[{len(values)}] = {{"]
        for offset in range(0, len(values), C_VALUES_PER_LINE):
            row = values[offset : offset + C_VALUES_PER_LINE]
            lines.append("    " + ", ".join(str(value) for value in row) + ",")
        lines.append("};")
        blocks.append(newline.join(lines))
    return (newline * 2).join(blocks)


def decode_arrangement(arrangement: dict[str, object]) -> dict[str, list[int]]:
    """Decode the ROM representation; used by deterministic regression tests."""

    validate_arrangement(arrangement)
    patterns = arrangement["patterns"]
    tuples = arrangement["tuples"]
    order_pages = arrangement["order_pages"]
    assert isinstance(patterns, dict)
    assert isinstance(tuples, dict)
    assert isinstance(order_pages, list)
    order = order_pages[0] + order_pages[1]
    decoded: dict[str, list[int]] = {channel: [] for channel in CHANNELS}

    for tuple_id in order:
        for step in range(PATTERN_STEPS):
            pair_index = step // 2
            high_nibble = step % 2 == 0
            for channel in CHANNELS:
                pattern_id = tuples[channel][tuple_id]
                packed = patterns[channel]["pairs"][pair_index][pattern_id]
                code = (packed >> 4) if high_nibble else (packed & 0x0F)
                if channel in TONAL_CHANNELS:
                    base = patterns[channel]["base"][pattern_id]
                    value = 0 if code == 0 else base + code - 1
                else:
                    value = code
                decoded[channel].append(value)
    return decoded


def detect_newline(text: str) -> str:
    """Choose the dominant existing line ending without normalizing the file."""

    crlf_count = text.count("\r\n")
    lf_count = text.count("\n") - crlf_count
    cr_count = text.count("\r") - crlf_count
    counts = ((crlf_count, "\r\n"), (lf_count, "\n"), (cr_count, "\r"))
    count, newline = max(counts, key=lambda item: item[0])
    return newline if count else "\n"


def replace_c_music_data(text: str, arrangement: dict[str, object]) -> str:
    """Replace only the content enclosed by the two exact C marker comments."""

    start_count = text.count(MUSIC_DATA_START_MARKER)
    end_count = text.count(MUSIC_DATA_END_MARKER)
    if start_count != 1 or end_count != 1:
        raise ValueError(
            "C file must contain exactly one "
            f"{MUSIC_DATA_START_MARKER!r} and one {MUSIC_DATA_END_MARKER!r}; "
            f"found {start_count} and {end_count}"
        )

    content_start = text.index(MUSIC_DATA_START_MARKER) + len(
        MUSIC_DATA_START_MARKER
    )
    content_end = text.index(MUSIC_DATA_END_MARKER)
    if content_start > content_end:
        raise ValueError("C music data end marker appears before its start marker")

    newline = detect_newline(text)
    replacement = newline + render_c_arrays(arrangement, newline) + newline
    return text[:content_start] + replacement + text[content_end:]


def read_text_preserving_newlines(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"C embed target not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as input_file:
        return input_file.read()


def write_text_preserving_newlines(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as output_file:
        output_file.write(text)


def run_embedding_self_test() -> None:
    """Exercise packing, decoding, validation, and marker refusal in memory."""

    pattern_sets = {
        "pulse1": (
            (55, 70, 55, 0, 67, 55, 0, 55),
            (60, 60, 62, 62, 64, 64, 0, 0),
        ),
        "pulse2": (
            (48, 60, 0, 60, 48, 60, 0, 60),
            (50, 62, 0, 62, 50, 62, 0, 62),
        ),
        "triangle": (
            (36, 36, 36, 36, 48, 48, 48, 48),
            (38, 38, 38, 38, 50, 50, 50, 50),
        ),
        "noise": (
            (3, 1, 0, 1, 4, 1, 0, 1),
            (3, 1, 5, 1, 4, 1, 6, 1),
        ),
    }
    raw = {
        channel: [
            value
            for order_index in range(ORDER_COUNT)
            for value in pattern_sets[channel][order_index % 2]
        ]
        for channel in CHANNELS
    }
    payload, folded_counts = compress_channels(raw)
    patterns = payload["patterns"]
    tuples = payload["tuples"]
    assert isinstance(patterns, dict)
    assert isinstance(tuples, dict)
    pattern_counts = {
        channel: len(patterns[channel]["base"])
        if channel in TONAL_CHANNELS
        else len(patterns[channel]["pairs"][0])
        for channel in CHANNELS
    }
    metadata = {
        "format": "fami-c-nes-arrangement-v2",
        "source_beats": [SOURCE_BEAT_START, SOURCE_BEAT_END],
        "step_count": STEP_COUNT,
        "pattern_steps": PATTERN_STEPS,
        "order_count": ORDER_COUNT,
        "order_page_lengths": list(ORDER_PAGE_LENGTHS),
        "pattern_counts": pattern_counts,
        "tuple_count": len(tuples["pulse1"]),
        "octave_folded_cells": folded_counts,
    }
    metadata["compressed_bytes"] = encoded_size_bytes(payload)
    fixture: dict[str, object] = {"metadata": metadata, **payload}
    validate_arrangement(fixture)

    decoded = decode_arrangement(fixture)
    for channel in CHANNELS:
        expected = (
            fold_tonal_patterns(raw[channel])[0]
            if channel in TONAL_CHANNELS
            else raw[channel]
        )
        if decoded[channel] != expected:
            raise ValueError(f"compression round-trip failed for {channel}")

    rendered = render_c_arrays(fixture)
    arrays = c_array_values(fixture)
    if len(arrays) != 25:
        raise ValueError("C embedding self-test expected exactly 25 arrays")
    for symbol, values in arrays:
        declaration = f"const unsigned char {symbol}[{len(values)}] = {{"
        if rendered.count(declaration) != 1:
            raise ValueError(f"C embedding self-test failed for {symbol}")
    if sum(len(values) for _symbol, values in arrays) != metadata["compressed_bytes"]:
        raise ValueError("C array sizes do not match compressed byte metadata")

    rendered_json = render_json(fixture)
    loaded = json.loads(rendered_json)
    validate_arrangement(loaded)
    if render_json(loaded) != rendered_json:
        raise ValueError("JSON rendering is not deterministic")

    source = (
        "before\r\n"
        + MUSIC_DATA_START_MARKER
        + "\r\nold data\r\n"
        + MUSIC_DATA_END_MARKER
        + "\r\nafter\r\n"
    )
    replaced = replace_c_music_data(source, fixture)
    if "old data" in replaced or "before\r\n" not in replaced:
        raise ValueError("C embedding replacement self-test failed")
    if "\n" in replaced.replace("\r\n", ""):
        raise ValueError("C embedding newline preservation self-test failed")

    invalid_sources = (
        "no markers",
        MUSIC_DATA_START_MARKER + MUSIC_DATA_START_MARKER + MUSIC_DATA_END_MARKER,
        MUSIC_DATA_END_MARKER + MUSIC_DATA_START_MARKER,
    )
    for invalid_source in invalid_sources:
        try:
            replace_c_music_data(invalid_source, fixture)
        except ValueError:
            continue
        raise ValueError("C embedding marker refusal self-test failed")

    corruptions: list[tuple[str, object]] = []
    bad_order = copy.deepcopy(fixture)
    bad_order["order_pages"][1][-1] = metadata["tuple_count"]
    corruptions.append(("bad tuple ID", bad_order))
    bad_noise = copy.deepcopy(fixture)
    bad_noise["patterns"]["noise"]["pairs"][0][0] = 0x70
    corruptions.append(("bad noise nibble", bad_noise))
    bad_size = copy.deepcopy(fixture)
    bad_size["metadata"]["compressed_bytes"] += 1
    corruptions.append(("bad compressed size", bad_size))
    for label, invalid in corruptions:
        try:
            validate_arrangement(invalid)
        except ValueError:
            continue
        raise ValueError(f"validation self-test accepted {label}")


def print_stats(arrangement: dict[str, object], prefix: str) -> None:
    metadata = arrangement["metadata"]
    assert isinstance(metadata, dict)
    print(prefix)
    print(
        "  patterns: "
        + ", ".join(
            f"{channel}={metadata['pattern_counts'][channel]}"
            for channel in CHANNELS
        )
    )
    print(
        f"  tuples={metadata['tuple_count']}, order={metadata['order_count']} "
        f"({metadata['order_page_lengths'][0]}+{metadata['order_page_lengths'][1]})"
    )
    print(
        f"  bytes={metadata['compressed_bytes']} compressed from "
        f"{metadata.get('uncompressed_bytes', STEP_COUNT * len(CHANNELS))}"
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="source MIDI (default: direct ~/Downloads MIDI containing '88')",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output JSON (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that JSON and requested C embedding match; do not write",
    )
    parser.add_argument(
        "--embed-c",
        type=Path,
        metavar="PATH",
        help=(
            "replace content between exact MUSIC_DATA marker comments in a C file"
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the in-memory C rendering and marker validation self-test",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        if args.self_test:
            run_embedding_self_test()
            print("OK: C embedding self-test passed")
            return 0

        source = resolve_input(args.input)
        arrangement = arrange_midi(source)
        rendered = render_json(arrangement)
        output = args.output.expanduser()

        embed_path = args.embed_c.expanduser() if args.embed_c else None
        current_c: str | None = None
        embedded_c: str | None = None
        if embed_path is not None:
            current_c = read_text_preserving_newlines(embed_path)
            # Validate both markers and fully render before making any writes.
            embedded_c = replace_c_music_data(current_c, arrangement)

        if args.check:
            outdated: list[str] = []
            if not output.is_file():
                outdated.append(f"output does not exist: {output}")
            elif output.read_text(encoding="utf-8") != rendered:
                outdated.append(f"generated JSON differs: {output}")
            if embed_path is not None and current_c != embedded_c:
                outdated.append(f"embedded C data differs: {embed_path}")
            if outdated:
                for message in outdated:
                    print(f"OUTDATED: {message}", file=sys.stderr)
                return 1
            checked = str(output)
            if embed_path is not None:
                checked += f" and {embed_path}"
            print_stats(arrangement, f"OK: {checked} are deterministic and current")
            return 0

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
        written = str(output)
        if embed_path is not None:
            assert embedded_c is not None
            if current_c != embedded_c:
                write_text_preserving_newlines(embed_path, embedded_c)
            written += f"; embedded {embed_path}"
        print_stats(arrangement, f"WROTE: {written}")
        return 0
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
