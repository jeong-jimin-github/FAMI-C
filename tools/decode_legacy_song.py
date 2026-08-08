#!/usr/bin/env python3
"""Decode the original compressed arrangement into an `asset song`.

`examples/tetris.c` used to carry its 4:26 arrangement in a bespoke
delta-compressed form (`MUSIC_PULSE1_BASE[77]`, `MUSIC_TUPLE_NOISE[156]`, ...)
that only the old driver understood, and that no agent could read or edit.
The arrangement itself is hand-worked and worth keeping, so this script
expands it once into the row format `asset song` uses.

It is a one-shot migration, kept in the tree so the derivation stays checkable:

    python tools/decode_legacy_song.py --source <old tetris.c> \
        --name SONG_TETRIS --out examples/tetris_song.c

The compressed layout, as implemented by the old runtime:

* the song is a list of 8-step patterns named by an order list
  (`MUSIC_ORDER0[256]` then `MUSIC_ORDER1[50]`, 306 entries, 2448 steps);
* an order entry indexes `MUSIC_TUPLE_<CH>` to get one pattern per channel;
* a tonal pattern is a base note plus four bytes, each holding two 4-bit
  scale degrees (high nibble = even step, low nibble = odd);
* a degree of 0 is a rest, otherwise the note is `base + degree - 1`
  as a MIDI note number;
* the noise pattern packs percussion types 1..6 the same way.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from famic.assets import NOTE_MIN_OCTAVE, NOTE_NAMES, NOTE_BASE


STEPS_PER_PATTERN = 8
ORDER0_LEN = 256
ORDER1_LEN = 50

# Percussion type -> the name the new format uses.
NOISE_NAMES = {
    0: "0",
    1: "NOISE_HAT",
    2: "NOISE_HAT_OPEN",
    3: "NOISE_KICK",
    4: "NOISE_SNARE",
    5: "NOISE_TOM",
    6: "NOISE_CYMBAL",
}

# The old driver ran on a phase accumulator: it added this per NMI to a
# 16-bit counter and stepped on overflow.  0x2730 / 65536 * 60 = 9.184
# steps/second, which is 138 BPM in sixteenths.
PHASE_INCREMENT = 0x2730


def parse_arrays(source: str) -> Dict[str, List[int]]:
    """Pull every `const unsigned char NAME[n] = { ... };` out of the source."""

    arrays: Dict[str, List[int]] = {}
    pattern = re.compile(
        r"const\s+unsigned\s+char\s+(\w+)\s*\[\s*(\d+)\s*\]\s*=\s*\{(.*?)\};",
        re.S,
    )
    for match in pattern.finditer(source):
        name, size, body = match.group(1), int(match.group(2)), match.group(3)
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
        values = [int(v, 0) for v in re.findall(r"-?\b(?:0[xX][0-9a-fA-F]+|\d+)\b", body)]
        if len(values) != size:
            raise SystemExit(f"{name}: {len(values)}개 값, 선언은 [{size}]")
        arrays[name] = values
    return arrays


def decode_tonal(arrays: Dict[str, List[int]], stem: str, pattern: int, step: int) -> int:
    """One step of a tonal channel, as a MIDI note number (0 = rest)."""

    base = arrays[f"MUSIC_{stem}_BASE"][pattern]
    packed = arrays[f"MUSIC_{stem}_PAIR{step // 2}"][pattern]
    degree = (packed >> 4) if step % 2 == 0 else (packed & 0x0F)
    if degree == 0:
        return 0
    note = base + degree - 1
    # The driver silenced anything outside the range its timer table covered.
    return note if 0x1D <= note < 0x60 else 0


def decode_noise(arrays: Dict[str, List[int]], pattern: int, step: int) -> int:
    packed = arrays[f"MUSIC_NOISE_PAIR{step // 2}"][pattern]
    return (packed >> 4) if step % 2 == 0 else (packed & 0x0F)


def decode(arrays: Dict[str, List[int]]) -> List[Tuple[int, int, int, int]]:
    order = arrays["MUSIC_ORDER0"][:ORDER0_LEN] + arrays["MUSIC_ORDER1"][:ORDER1_LEN]
    rows: List[Tuple[int, int, int, int]] = []
    for order_index, tuple_index in enumerate(order):
        patterns = {
            stem: arrays[f"MUSIC_TUPLE_{stem}"][tuple_index]
            for stem in ("PULSE1", "PULSE2", "TRIANGLE", "NOISE")
        }
        for step in range(STEPS_PER_PATTERN):
            rows.append(
                (
                    decode_tonal(arrays, "PULSE1", patterns["PULSE1"], step),
                    decode_tonal(arrays, "PULSE2", patterns["PULSE2"], step),
                    decode_tonal(arrays, "TRIANGLE", patterns["TRIANGLE"], step),
                    decode_noise(arrays, patterns["NOISE"], step),
                )
            )
    return rows


def midi_to_note_id(midi: int) -> int:
    """MIDI note number -> the note id `asset song` uses."""

    lowest = (NOTE_MIN_OCTAVE + 1) * 12          # MIDI number of C1
    return midi - lowest + NOTE_BASE


def note_name(midi: int) -> str:
    lowest = (NOTE_MIN_OCTAVE + 1) * 12
    index = midi - lowest
    return f"N_{NOTE_NAMES[index % 12]}{NOTE_MIN_OCTAVE + index // 12}"


def to_song_rows(rows: Sequence[Tuple[int, int, int, int]]) -> List[List[str]]:
    """Turn decoded MIDI rows into `asset song` cells.

    The old driver only rewrote a channel when its note changed, so a repeated
    note sustained rather than retriggering.  `HOLD` is how the row format says
    the same thing.
    """

    out: List[List[str]] = []
    previous = [None, None, None]
    for p1, p2, tri, noise in rows:
        cells: List[str] = []
        for channel, value in enumerate((p1, p2, tri)):
            if value == previous[channel]:
                cells.append("HOLD")
            elif value == 0:
                cells.append("0")
            else:
                cells.append(note_name(value))
            previous[channel] = value
        cells.append(NOISE_NAMES.get(noise, "0"))
        out.append(cells)
    return out


def render(name: str, rows: Sequence[Sequence[str]], whole: int, frac: int) -> str:
    total_frames = len(rows) * (whole + frac / 256.0)
    seconds = total_frames / 60.0
    lines = [
        "/* 원본 편곡을 asset song 으로 옮긴 것.",
        " *",
        " * tools/decode_legacy_song.py 가 예전 압축 포맷(MUSIC_* 배열들)에서",
        " * 펼쳐 낸 결과다. 음과 타이밍은 원본 그대로이고, 표현만 사람이 읽고",
        " * 고칠 수 있는 행 단위로 바뀌었다.",
        " *",
        " * 원본 데이터를 다시 꺼내려면:",
        " *   git show bb1d567:examples/tetris.c > /tmp/old_tetris.c",
        " *   python tools/decode_legacy_song.py --source /tmp/old_tetris.c \\",
        " *       --name SONG_TETRIS --out examples/tetris_song.c",
        " *",
        f" * {len(rows)}행, 행당 {whole}+{frac}/256 프레임 "
        f"= {int(seconds // 60)}:{seconds % 60:06.3f}",
        " *",
        " * 한 행은 { 펄스1, 펄스2, 삼각파, 노이즈 } 이고",
        " * HOLD 는 앞 음 유지, 0 은 쉼표다.",
        " */",
        "",
        f"asset song {name} = {{ {whole}, {frac},",
    ]
    for index, row in enumerate(rows):
        cells = ", ".join(f"{cell:>14}" for cell in row)
        comma = "" if index == len(rows) - 1 else ","
        marker = ""
        if index % (STEPS_PER_PATTERN * 4) == 0:
            marker = f"    /* {index:4d} */"
        lines.append(f"    {{ {cells} }}{comma}{marker}")
    lines.append("};")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="예전 tetris.c 경로")
    parser.add_argument("--name", default="SONG_TETRIS")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    arrays = parse_arrays(Path(args.source).read_text())
    rows = decode(arrays)

    # frames per row = 65536 / increment, kept as whole + frac/256.
    frames = 65536.0 / PHASE_INCREMENT
    whole = int(frames)
    frac = int(round((frames - whole) * 256))
    if frac >= 256:
        whole, frac = whole + 1, 0

    text = render(args.name, to_song_rows(rows), whole, frac)
    Path(args.out).write_text(text)

    sounding = sum(1 for r in rows if any(r))
    print(f"{len(rows)}행 디코드, {sounding}행에 소리 있음")
    print(f"행당 {whole}+{frac}/256 프레임 ({frames:.4f})")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
