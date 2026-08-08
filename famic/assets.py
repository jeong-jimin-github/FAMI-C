"""Asset compilation.

Graphics, palettes, maps and sound live in the same `.c` file as the code that
uses them, declared with `asset`.  The compiler assigns CHR indices, so an
agent never has to keep a `#define TILE_HERO 92` in sync with a tile sheet it
cannot see.

Every asset name becomes a `u8` compile-time constant:

  * `asset tile T`        -> the CHR index of that tile
  * `asset tiles T[n]`    -> the CHR index of the first of n consecutive tiles
  * everything else       -> a small id the matching runtime call takes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import ast
from .diagnostics import CompileError, DiagnosticBag


# Documentation the API manifest re-exports, so `famic api --json` describes the
# asset syntax as well as the function surface.
ASSET_KIND_DOCS: List[Dict[str, str]] = [
    {
        "kind": "palette",
        "syntax": "asset palette NAME = { 32 bytes };",
        "summary": "배경 팔레트 4개 + 스프라이트 팔레트 4개. 각 4바이트.",
        "example": (
            "asset palette PAL_GAME = {\n"
            "    0x0F,0x11,0x21,0x31,  0x0F,0x06,0x16,0x26,\n"
            "    0x0F,0x09,0x19,0x29,  0x0F,0x00,0x10,0x30,\n"
            "    0x0F,0x12,0x22,0x32,  0x0F,0x06,0x16,0x36,\n"
            "    0x0F,0x08,0x18,0x28,  0x0F,0x14,0x24,0x34\n"
            "};"
        ),
    },
    {
        "kind": "tile",
        "syntax": 'asset tile NAME = { 8줄 x 8글자 };',
        "summary": "타일 1개. '.'=투명, '0'~'3'=팔레트 색인.",
        "example": (
            "asset tile T_BRICK = {\n"
            '    "33333333"\n'
            '    "32222221"\n'
            '    "32222221"\n'
            '    "32222221"\n'
            '    "32222221"\n'
            '    "32222221"\n'
            '    "31111111"\n'
            '    "11111111"\n'
            "};"
        ),
    },
    {
        "kind": "tiles",
        "syntax": "asset tiles NAME[n] = { 8n줄 };",
        "summary": "연속 n개 타일. NAME은 첫 타일의 인덱스.",
        "example": 'asset tiles T_HERO[4] = { /* 32줄 */ };  /* T_HERO+0 .. T_HERO+3 */',
    },
    {
        "kind": "metasprite",
        "syntax": "asset metasprite NAME = { {dx,dy,tile,attr}, ... };",
        "summary": "여러 스프라이트를 한 덩어리로. spr_meta(x,y,NAME) 으로 그린다.",
        "example": (
            "asset metasprite MS_HERO = {\n"
            "    { 0, 0, T_HERO+0, SPR_PAL0 },\n"
            "    { 8, 0, T_HERO+1, SPR_PAL0 },\n"
            "    { 0, 8, T_HERO+2, SPR_PAL0 },\n"
            "    { 8, 8, T_HERO+3, SPR_PAL0 }\n"
            "};"
        ),
    },
    {
        "kind": "metatile",
        "syntax": "asset metatile NAME = { tl, tr, bl, br, pal };",
        "summary": "16x16 배경 블록. 타일 4개 + 배경 팔레트 번호(0~3).",
        "example": "asset metatile MT_GROUND = { T_GRASS, T_GRASS, T_DIRT, T_DIRT, 1 };",
    },
    {
        "kind": "map",
        "syntax": "asset map NAME = { w, h, 메타타일 이름들... };",
        "summary": "메타타일로 그린 화면. bg_map(NAME) 이 통째로 그린다. w<=16, h<=15.",
        "example": (
            "asset map MAP_1 = { 4, 2,\n"
            "    MT_SKY,   MT_SKY,    MT_SKY,   MT_SKY,\n"
            "    MT_GROUND,MT_GROUND, MT_GROUND,MT_GROUND\n"
            "};"
        ),
    },
    {
        "kind": "sfx",
        "syntax": "asset sfx NAME = { {vol, note}, ... };",
        "summary": "프레임 단위 효과음. vol 0~15, note 는 N_* 상수 (0이면 무음).",
        "example": "asset sfx SFX_JUMP = { {12, N_C5}, {11, N_E5}, {9, N_G5}, {6, N_C6}, {3, N_C6} };",
    },
    {
        "kind": "song",
        "syntax": "asset song NAME = { speed, {p1,p2,tri,noise}, ... };",
        "summary": "행 단위 BGM. speed 는 행당 프레임 수. 0=쉼, HOLD=유지, N_* = 음.",
        "example": (
            "asset song SONG_MAIN = { 8,\n"
            "    { N_C4, N_E5, N_C3, 1 },\n"
            "    { HOLD, N_G5, HOLD, 0 }\n"
            "};"
        ),
    },
]


# --------------------------------------------------------------------------
# Built-in font
# --------------------------------------------------------------------------

# 5x7 glyphs, drawn one pixel in from the left so text has natural spacing.
FONT_5x7: Dict[str, Tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00001", "00001", "00001", "00001", "10001", "10001", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "01100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "*": ("00000", "10101", "01110", "11111", "01110", "10101", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "'": ("00100", "00100", "00000", "00000", "00000", "00000", "00000"),
}

# The order font tiles are laid into CHR.  Digits come first and contiguous so
# bg_number() only needs the index of '0'.
FONT_ORDER = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ .,:-!?+/()*=<>%'"


# --------------------------------------------------------------------------
# Note table (NTSC)
# --------------------------------------------------------------------------

NOTE_NAMES = ["C", "CS", "D", "DS", "E", "F", "FS", "G", "GS", "A", "AS", "B"]
NOTE_MIN_OCTAVE = 1
NOTE_MAX_OCTAVE = 7

# `HOLD` keeps a channel sounding without retriggering it.
HOLD = 1
# Note ids start at 2 so that 0 means "rest" and 1 means "hold".
NOTE_BASE = 2


def note_constants() -> List[Tuple[str, int]]:
    out: List[Tuple[str, int]] = [("HOLD", HOLD), ("REST", 0)]
    index = NOTE_BASE
    for octave in range(NOTE_MIN_OCTAVE, NOTE_MAX_OCTAVE + 1):
        for name in NOTE_NAMES:
            out.append((f"N_{name}{octave}", index))
            index += 1
    return out


def note_periods() -> List[int]:
    """11-bit APU timer values for every note id, index 0 = rest."""

    periods = [0, 0]
    cpu = 1789773.0
    for octave in range(NOTE_MIN_OCTAVE, NOTE_MAX_OCTAVE + 1):
        for semitone in range(12):
            midi = (octave + 1) * 12 + semitone
            freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
            period = int(round(cpu / (16.0 * freq))) - 1
            periods.append(max(8, min(0x7FF, period)))
    return periods


# --------------------------------------------------------------------------
# Compiled asset tables
# --------------------------------------------------------------------------


@dataclass
class TileImage:
    name: str
    index: int
    count: int
    planes: List[bytes] = field(default_factory=list)


@dataclass
class CompiledAssets:
    # name -> compile-time constant value
    constants: Dict[str, int] = field(default_factory=dict)
    chr_rom: bytearray = field(default_factory=lambda: bytearray(0x2000))
    tiles_used: int = 1  # tile 0 is reserved blank
    tile_owners: List[Tuple[str, int, int]] = field(default_factory=list)

    palettes: List[List[int]] = field(default_factory=list)
    metasprites: List[List[int]] = field(default_factory=list)
    metatiles: List[Tuple[int, int, int, int, int]] = field(default_factory=list)
    maps: List[Tuple[int, int, List[int]]] = field(default_factory=list)
    sfx: List[List[Tuple[int, int]]] = field(default_factory=list)
    songs: List[Tuple[int, List[Tuple[int, int, int, int]]]] = field(default_factory=list)

    font_base: int = -1
    font_map: Dict[str, int] = field(default_factory=dict)

    kinds: Dict[str, str] = field(default_factory=dict)

    def has(self, kind: str) -> bool:
        return kind in self.kinds.values()


class AssetCompiler:
    def __init__(self, program: ast.Program, warnings: DiagnosticBag, file: str = ""):
        self.program = program
        self.warnings = warnings
        self.file = file
        self.out = CompiledAssets()
        self.enums = program.enums

    # -- entry point -------------------------------------------------------

    def compile(self, needs_font: bool) -> CompiledAssets:
        # Tiles first, so metasprites and metatiles can refer to them by name.
        for decl in self.program.assets:
            if decl.kind in ("tile", "tiles"):
                self.compile_tiles(decl)
        if needs_font:
            self.install_font()
        for decl in self.program.assets:
            if decl.kind == "palette":
                self.compile_palette(decl)
        for decl in self.program.assets:
            if decl.kind == "metasprite":
                self.compile_metasprite(decl)
        for decl in self.program.assets:
            if decl.kind == "metatile":
                self.compile_metatile(decl)
        for decl in self.program.assets:
            if decl.kind == "map":
                self.compile_map(decl)
        for decl in self.program.assets:
            if decl.kind == "sfx":
                self.compile_sfx(decl)
        for decl in self.program.assets:
            if decl.kind == "song":
                self.compile_song(decl)
        return self.out

    # -- helpers -----------------------------------------------------------

    def err(self, code: str, message: str, decl: ast.AssetDecl, hint: str = "") -> CompileError:
        return CompileError(code, message, decl.line, decl.col, hint, self.file)

    def declare(self, name: str, value: int, kind: str, decl: ast.AssetDecl) -> None:
        if name in self.out.constants:
            raise self.err("E0302", f"asset {name} 이(가) 이미 있습니다", decl)
        self.out.constants[name] = value
        self.out.kinds[name] = kind

    def resolve_atom(self, item: object, decl: ast.AssetDecl) -> int:
        """Evaluate an asset list entry: a number, a name, or `name + n`."""

        if isinstance(item, int):
            return item
        if isinstance(item, tuple):
            tag = item[0]
            if tag == "ref":
                name = item[1]
                if name in self.out.constants:
                    return self.out.constants[name]
                if name in self.enums:
                    return self.enums[name]
                if name in NOTE_LOOKUP:
                    return NOTE_LOOKUP[name]
                raise self.err(
                    "E0510",
                    f"'{name}' 을(를) 찾을 수 없습니다",
                    decl,
                    hint="asset 은 자기보다 위에 선언된 asset/enum 만 참조할 수 있습니다.",
                )
            if tag == "neg":
                return -self.resolve_atom(item[1], decl)
            if tag == "add":
                return self.resolve_atom(item[1], decl) + self.resolve_atom(item[2], decl)
            if tag == "sub":
                return self.resolve_atom(item[1], decl) - self.resolve_atom(item[2], decl)
        raise self.err("E0205", f"asset 항목 형식이 잘못되었습니다: {item!r}", decl)

    def put_tile(self, index: int, rows: Sequence[str], decl: ast.AssetDecl) -> None:
        base = index * 16
        for r in range(8):
            lo = hi = 0
            for c in range(8):
                ch = rows[r][c]
                if ch in ".":
                    value = 0
                elif ch in "0123":
                    value = int(ch)
                else:
                    raise self.err(
                        "E0502",
                        f"타일 픽셀에 '{ch}' 는 쓸 수 없습니다",
                        decl,
                        hint="쓸 수 있는 글자: '.'(=색0, 투명) '0' '1' '2' '3'",
                    )
                bit = 1 << (7 - c)
                if value & 1:
                    lo |= bit
                if value & 2:
                    hi |= bit
            self.out.chr_rom[base + r] = lo
            self.out.chr_rom[base + 8 + r] = hi

    def alloc_tiles(self, count: int, owner: str, decl: ast.AssetDecl) -> int:
        # Both pattern tables are pointed at $0000, so a tile index is a plain
        # 0..255 value that works for background and sprites alike.
        if self.out.tiles_used + count > 256:
            table = "\n".join(
                f"    {name}: {n}개 (인덱스 {start})"
                for name, start, n in self.out.tile_owners
            )
            raise self.err(
                "E0507",
                f"CHR 타일 256개를 넘었습니다 ({self.out.tiles_used}개 사용 중, {count}개 추가 요청)",
                decl,
                hint="현재 사용 내역:\n" + table + "\n타일을 재사용하거나 asset tile 을 줄이세요.",
            )
        start = self.out.tiles_used
        self.out.tiles_used += count
        self.out.tile_owners.append((owner, start, count))
        return start

    # -- per-kind ----------------------------------------------------------

    def compile_tiles(self, decl: ast.AssetDecl) -> None:
        rows: List[str] = list(decl.body or [])
        count = decl.count if decl.kind == "tiles" else 1
        if decl.kind == "tile" and decl.count:
            raise self.err(
                "E0502",
                "asset tile 에는 [n] 을 붙일 수 없습니다",
                decl,
                hint=f"여러 장이면 `asset tiles {decl.name}[{decl.count}]` 를 쓰세요.",
            )
        if count < 1:
            raise self.err("E0502", "asset tiles 의 개수는 1 이상이어야 합니다", decl)
        if len(rows) != count * 8:
            raise self.err(
                "E0502",
                f"{decl.name}: 그림 줄 수가 {len(rows)}인데 {count * 8}줄이어야 합니다",
                decl,
                hint="타일 하나에 정확히 8줄, 각 줄 8글자입니다.",
            )
        for i, row in enumerate(rows):
            if len(row) != 8:
                raise self.err(
                    "E0502",
                    f"{decl.name}: {i + 1}번째 줄이 {len(row)}글자입니다 (8글자여야 함)",
                    decl,
                    hint=f'문제 줄: "{row}"',
                )
        start = self.alloc_tiles(count, decl.name, decl)
        for i in range(count):
            self.put_tile(start + i, rows[i * 8 : i * 8 + 8], decl)
        self.declare(decl.name, start, decl.kind, decl)

    def install_font(self) -> None:
        decl = ast.AssetDecl(kind="tile", name="__font")
        base = self.alloc_tiles(len(FONT_ORDER), "내장 폰트", decl)
        self.out.font_base = base
        for offset, ch in enumerate(FONT_ORDER):
            glyph = FONT_5x7[ch]
            rows = []
            for r in range(8):
                if r < 7:
                    rows.append("." + "".join("3" if b == "1" else "." for b in glyph[r]) + "..")
                else:
                    rows.append("........")
            self.put_tile(base + offset, rows, decl)
            self.out.font_map[ch] = base + offset

    def compile_palette(self, decl: ast.AssetDecl) -> None:
        values = [self.resolve_atom(v, decl) for v in self._flat(decl.body)]
        if len(values) != 32:
            raise self.err(
                "E0503",
                f"{decl.name}: 팔레트는 32바이트여야 합니다 ({len(values)}개 받음)",
                decl,
                hint="배경 팔레트 4개 x 4바이트 + 스프라이트 팔레트 4개 x 4바이트 = 32.",
            )
        for v in values:
            if not 0 <= v <= 0x3F:
                raise self.err(
                    "E0503",
                    f"{decl.name}: 색 값 {v} 가 범위를 벗어났습니다",
                    decl,
                    hint="NES 색은 0x00~0x3F 입니다. 0x0F 가 검정입니다.",
                )
        backdrop = values[0]
        for slot in (4, 8, 12, 16, 20, 24, 28):
            if values[slot] != backdrop:
                self.warnings.warn(
                    "W0903",
                    f"{decl.name}: {slot}번 색을 배경색 0x{backdrop:02X} 로 맞췄습니다",
                    decl.line,
                    decl.col,
                    hint="NES는 팔레트 첫 칸을 전부 같은 배경색으로 공유합니다.",
                )
                values[slot] = backdrop
        self.declare(decl.name, len(self.out.palettes), "palette", decl)
        self.out.palettes.append(values)

    def compile_metasprite(self, decl: ast.AssetDecl) -> None:
        entries = decl.body or []
        flat: List[int] = []
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 4:
                raise self.err(
                    "E0504",
                    f"{decl.name}: 항목은 {{dx, dy, tile, attr}} 4개여야 합니다",
                    decl,
                    hint="예: { 8, 0, T_HERO+1, SPR_PAL0 }",
                )
            dx, dy, tile, attr = (self.resolve_atom(v, decl) for v in entry)
            if not -128 <= dx <= 127 or not -128 <= dy <= 127:
                raise self.err(
                    "E0504", f"{decl.name}: dx/dy 는 -128~127 이어야 합니다", decl
                )
            flat.extend([dx & 0xFF, dy & 0xFF, tile & 0xFF, attr & 0xFF])
        if not flat:
            raise self.err("E0504", f"{decl.name}: 비어 있는 메타스프라이트", decl)
        if len(flat) // 4 > 64:
            raise self.err(
                "E0504",
                f"{decl.name}: 스프라이트 {len(flat) // 4}개는 너무 많습니다 (하드웨어 한계 64)",
                decl,
            )
        flat.append(0x80)  # terminator in the dx slot
        self.declare(decl.name, len(self.out.metasprites), "metasprite", decl)
        self.out.metasprites.append(flat)

    def compile_metatile(self, decl: ast.AssetDecl) -> None:
        values = [self.resolve_atom(v, decl) for v in self._flat(decl.body)]
        if len(values) != 5:
            raise self.err(
                "E0505",
                f"{decl.name}: {{tl, tr, bl, br, pal}} 5개가 필요합니다 ({len(values)}개 받음)",
                decl,
                hint="예: asset metatile MT_GROUND = { T_GRASS, T_GRASS, T_DIRT, T_DIRT, 1 };",
            )
        if not 0 <= values[4] <= 3:
            raise self.err(
                "E0505", f"{decl.name}: 팔레트 번호는 0~3 입니다 ({values[4]} 받음)", decl
            )
        if len(self.out.metatiles) >= 256:
            raise self.err("E0505", "메타타일은 256개까지입니다", decl)
        self.declare(decl.name, len(self.out.metatiles), "metatile", decl)
        self.out.metatiles.append(tuple(v & 0xFF for v in values))  # type: ignore[arg-type]

    def compile_map(self, decl: ast.AssetDecl) -> None:
        values = [self.resolve_atom(v, decl) for v in self._flat(decl.body)]
        if len(values) < 2:
            raise self.err(
                "E0506",
                f"{decl.name}: 맵은 w, h 로 시작해야 합니다",
                decl,
                hint="예: asset map M = { 16, 15, MT_SKY, ... };",
            )
        w, h = values[0], values[1]
        cells = values[2:]
        if not 1 <= w <= 16 or not 1 <= h <= 15:
            raise self.err(
                "E0506",
                f"{decl.name}: 크기 {w}x{h} 가 범위를 벗어났습니다",
                decl,
                hint="화면은 16x15 셀(16x16 픽셀)입니다.",
            )
        if len(cells) != w * h:
            raise self.err(
                "E0506",
                f"{decl.name}: 셀이 {len(cells)}개인데 {w}x{h}={w * h}개여야 합니다",
                decl,
                hint="줄마다 정확히 w개씩 쓰세요.",
            )
        for value in cells:
            if not 0 <= value < max(1, len(self.out.metatiles)):
                raise self.err(
                    "E0506",
                    f"{decl.name}: 메타타일 번호 {value} 가 없습니다",
                    decl,
                    hint="맵보다 먼저 asset metatile 을 선언하세요.",
                )
        self.declare(decl.name, len(self.out.maps), "map", decl)
        self.out.maps.append((w, h, [c & 0xFF for c in cells]))

    def compile_sfx(self, decl: ast.AssetDecl) -> None:
        frames: List[Tuple[int, int]] = []
        for entry in decl.body or []:
            if not isinstance(entry, list) or len(entry) != 2:
                raise self.err(
                    "E0508",
                    f"{decl.name}: 항목은 {{vol, note}} 2개여야 합니다",
                    decl,
                    hint="예: { 12, N_C5 }   /* vol 0~15, note 는 N_* 또는 0(무음) */",
                )
            vol, note = (self.resolve_atom(v, decl) for v in entry)
            if not 0 <= vol <= 15:
                raise self.err("E0508", f"{decl.name}: 볼륨은 0~15 입니다 ({vol})", decl)
            if not 0 <= note < len(NOTE_PERIODS):
                raise self.err(
                    "E0508",
                    f"{decl.name}: 음 번호 {note} 를 모릅니다",
                    decl,
                    hint=f"N_C1 ~ N_B7 사이의 상수를 쓰세요 (0 은 무음).",
                )
            frames.append((vol, note))
        if not frames:
            raise self.err("E0508", f"{decl.name}: 비어 있는 효과음", decl)
        if len(frames) > 120:
            raise self.err(
                "E0508",
                f"{decl.name}: 효과음이 {len(frames)}프레임입니다 (최대 120)",
                decl,
                hint="2초가 넘는 소리는 효과음이 아니라 곡으로 만드세요.",
            )
        if len(self.out.sfx) >= 32:
            raise self.err("E0508", "효과음은 32개까지입니다", decl)
        self.declare(decl.name, len(self.out.sfx), "sfx", decl)
        self.out.sfx.append(frames)

    def compile_song(self, decl: ast.AssetDecl) -> None:
        body = list(decl.body or [])
        if not body or isinstance(body[0], list):
            raise self.err(
                "E0509",
                f"{decl.name}: 첫 항목은 행당 프레임 수(speed)여야 합니다",
                decl,
                hint="예: asset song S = { 8, { N_C4, 0, N_C3, 0 }, ... };",
            )
        speed = self.resolve_atom(body[0], decl)
        if not 1 <= speed <= 60:
            raise self.err(
                "E0509", f"{decl.name}: speed 는 1~60 입니다 ({speed})", decl,
                hint="60프레임=1초. speed 8 이면 초당 7.5행입니다.",
            )
        rows: List[Tuple[int, int, int, int]] = []
        for entry in body[1:]:
            if not isinstance(entry, list) or len(entry) != 4:
                raise self.err(
                    "E0509",
                    f"{decl.name}: 행은 {{pulse1, pulse2, triangle, noise}} 4개여야 합니다",
                    decl,
                    hint="예: { N_C4, N_E5, N_C3, 1 }   /* 0=쉼, HOLD=유지 */",
                )
            values = [self.resolve_atom(v, decl) for v in entry]
            for i, value in enumerate(values):
                limit = 16 if i == 3 else len(NOTE_PERIODS)
                if not 0 <= value < limit:
                    raise self.err(
                        "E0509",
                        f"{decl.name}: {i + 1}번째 채널 값 {value} 가 범위를 벗어났습니다",
                        decl,
                        hint=(
                            "노이즈 채널은 0(쉼), 1(유지), 2~15(음색) 입니다."
                            if i == 3
                            else "N_C1 ~ N_B7, 0(쉼), HOLD(유지) 중 하나여야 합니다."
                        ),
                    )
            rows.append(tuple(values))  # type: ignore[arg-type]
        if not rows:
            raise self.err("E0509", f"{decl.name}: 행이 하나도 없습니다", decl)
        if len(rows) > 1024:
            raise self.err(
                "E0509",
                f"{decl.name}: {len(rows)}행은 너무 깁니다 (최대 1024)",
                decl,
                hint="반복되는 부분은 곡을 나눠 이어 재생하세요.",
            )
        if len(self.out.songs) >= 16:
            raise self.err("E0509", "곡은 16개까지입니다", decl)
        self.declare(decl.name, len(self.out.songs), "song", decl)
        self.out.songs.append((speed, rows))

    @staticmethod
    def _flat(value: object) -> List[object]:
        out: List[object] = []
        if isinstance(value, list):
            for item in value:
                out.extend(AssetCompiler._flat(item))
        else:
            out.append(value)
        return out


NOTE_PERIODS = note_periods()
NOTE_LOOKUP = dict(note_constants())
