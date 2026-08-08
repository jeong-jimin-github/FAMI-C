"""The runtime API manifest.

This table is the single source of truth for the FAMI-C runtime.  It drives:

  * the code generator (which names are builtins, and their signatures);
  * `include/fami.h` (generated, never hand-edited);
  * `famic api --json` (what an agent reads to discover the API);
  * docs/agent/API.md (generated).

Adding a runtime call means adding one row here and one assembly routine in
runtime.py.  There is nowhere else to register it, and nothing an agent has to
declare to "turn it on" -- calling a function pulls its routine into the ROM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .assets import note_constants
from .types import I8, I16, Scalar, U8, U16, VOID


# A pseudo-type for parameters that must be a string literal at the call site.
STR = Scalar("str", 0, False)


@dataclass
class Builtin:
    name: str
    ret: Scalar
    params: List[Tuple[str, Scalar]]
    group: str
    summary: str
    example: str
    # Runtime modules this call drags into the ROM.  Modules are emitted once,
    # in dependency order, and only when something references them.
    needs: Tuple[str, ...] = ()
    label: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            self.label = "_" + self.name

    def signature(self) -> str:
        if not self.params:
            args = "void"
        else:
            args = ", ".join(
                (f"const char *{n}" if t is STR else f"{t} {n}") for n, t in self.params
            )
        return f"{self.ret} {self.name}({args})"

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "group": self.group,
            "signature": self.signature(),
            "returns": str(self.ret),
            "params": [{"name": n, "type": str(t)} for n, t in self.params],
            "summary": self.summary,
            "example": self.example,
            "notes": self.notes,
        }


def _b(*args, **kwargs) -> Builtin:
    return Builtin(*args, **kwargs)


BUILTINS: List[Builtin] = [
    # -- system ------------------------------------------------------------
    _b(
        "wait_vblank",
        VOID,
        [],
        "system",
        "다음 NMI(vblank)까지 대기한다. 게임 루프의 프레임 경계.",
        "while (1) { update(); draw(); wait_vblank(); }",
        notes="루프마다 정확히 한 번 부르세요. 두 번 부르면 30fps가 됩니다.",
    ),
    _b(
        "frame_count",
        U8,
        [],
        "system",
        "전원 투입 후 지난 프레임 수의 하위 8비트.",
        "if ((frame_count() & 7) == 0) animate();",
    ),
    _b(
        "ppu_on",
        VOID,
        [],
        "system",
        "배경/스프라이트 렌더링을 켠다.",
        "ppu_on();",
    ),
    _b(
        "ppu_off",
        VOID,
        [],
        "system",
        "렌더링을 끈다. 끈 동안에는 VRAM에 마음껏 쓸 수 있다.",
        "ppu_off(); bg_map(LEVEL1); ppu_on();",
        notes="화면 전체를 새로 그릴 때만 쓰세요. 켜고 끄면 한 프레임 검은 화면이 보입니다.",
    ),
    # -- input -------------------------------------------------------------
    _b(
        "pad_poll",
        VOID,
        [],
        "input",
        "컨트롤러 1·2를 읽고 눌림/떼임 상태를 갱신한다. 프레임당 한 번.",
        "pad_poll();",
        needs=("pad",),
        notes="pad_held/pressed/released 를 쓰기 전에 반드시 먼저 부르세요.",
    ),
    _b(
        "pad_held",
        U8,
        [("player", U8)],
        "input",
        "지금 눌려 있는 버튼 비트마스크.",
        "if (pad_held(0) & PAD_RIGHT) x++;",
        needs=("pad",),
    ),
    _b(
        "pad_pressed",
        U8,
        [("player", U8)],
        "input",
        "이번 프레임에 새로 눌린 버튼 (엣지).",
        "if (pad_pressed(0) & PAD_A) jump();",
        needs=("pad",),
    ),
    _b(
        "pad_released",
        U8,
        [("player", U8)],
        "input",
        "이번 프레임에 떼어진 버튼 (엣지).",
        "if (pad_released(0) & PAD_A) cut_jump();",
        needs=("pad",),
    ),
    # -- background --------------------------------------------------------
    _b(
        "bg_tile",
        VOID,
        [("x", U8), ("y", U8), ("tile", U8)],
        "background",
        "네임테이블 (x,y)에 타일 하나. x는 0~31, y는 0~29.",
        "bg_tile(4, 6, T_BRICK);",
        needs=("vram",),
        notes="렌더링 중이면 자동으로 큐에 들어가 다음 vblank에 반영됩니다. 타이밍을 신경 쓸 필요 없습니다.",
    ),
    _b(
        "bg_rect",
        VOID,
        [("x", U8), ("y", U8), ("w", U8), ("h", U8), ("tile", U8)],
        "background",
        "타일 하나로 사각형을 채운다.",
        "bg_rect(0, 0, 32, 2, T_BLANK);",
        needs=("vram",),
    ),
    _b(
        "bg_text",
        VOID,
        [("x", U8), ("y", U8), ("text", STR)],
        "background",
        "내장 폰트로 문자열을 찍는다. 인자는 반드시 문자열 리터럴.",
        'bg_text(11, 4, "GAME OVER");',
        needs=("vram", "font"),
        notes="A-Z 0-9 와 공백 . , : - ! ? + / ( ) 만 있습니다. 소문자는 대문자로 바뀝니다.",
    ),
    _b(
        "bg_char",
        VOID,
        [("x", U8), ("y", U8), ("code", U8)],
        "background",
        "ASCII 코드 한 글자를 찍는다. 문자열 리터럴이 아닌 글자를 그릴 때.",
        "bg_char(4, 6, 'A' + letter_index);",
        needs=("vram", "font"),
        notes="폰트에 없는 글자는 공백으로 나옵니다. 소문자는 대문자로 바뀝니다.",
    ),
    _b(
        "bg_number",
        VOID,
        [("x", U8), ("y", U8), ("value", U16), ("digits", U8)],
        "background",
        "값을 digits 자리 10진수로 찍는다 (앞자리 0 채움).",
        "bg_number(24, 2, score, 6);",
        needs=("vram", "font", "bcd"),
    ),
    _b(
        "bg_attr",
        VOID,
        [("cx", U8), ("cy", U8), ("pal", U8)],
        "background",
        "16x16 셀 (cx,cy)의 배경 팔레트를 고른다. cx 0~15, cy 0~14.",
        "bg_attr(3, 5, 2);",
        needs=("vram", "attr"),
    ),
    _b(
        "bg_meta",
        VOID,
        [("cx", U8), ("cy", U8), ("metatile", U8)],
        "background",
        "16x16 메타타일 하나를 그린다 (타일 4개 + 팔레트).",
        "bg_meta(3, 5, MT_GRASS);",
        needs=("vram", "attr", "metatile"),
    ),
    _b(
        "bg_map",
        VOID,
        [("map", U8)],
        "background",
        "asset map 전체를 화면에 그린다.",
        "ppu_off(); bg_map(MAP_STAGE1); ppu_on();",
        needs=("vram", "attr", "metatile", "map"),
        notes="화면 한 장 분량이라 렌더링을 끄고 부르는 편이 안전합니다.",
    ),
    _b(
        "bg_clear",
        VOID,
        [("tile", U8)],
        "background",
        "네임테이블 전체를 한 타일로 채우고 속성을 0으로 만든다.",
        "bg_clear(T_BLANK);",
        needs=("vram",),
    ),
    _b(
        "bg_flush",
        VOID,
        [],
        "background",
        "큐에 남은 배경 갱신을 즉시 전부 반영한다.",
        "bg_flush();",
        needs=("vram",),
        notes="렌더링이 켜져 있으면 화면이 잠깐 흔들릴 수 있습니다. 보통 부를 필요가 없습니다.",
    ),
    # -- sprites -----------------------------------------------------------
    _b(
        "spr_clear",
        VOID,
        [],
        "sprite",
        "스프라이트 목록을 비운다. 매 프레임 그리기 전에 부른다.",
        "spr_clear();",
        needs=("oam",),
    ),
    _b(
        "spr",
        VOID,
        [("x", U8), ("y", U8), ("tile", U8), ("attr", U8)],
        "sprite",
        "8x8 스프라이트 하나를 목록에 추가한다.",
        "spr(hero_x, hero_y, T_HERO, 0);",
        needs=("oam",),
        notes="attr: 하위 2비트 팔레트, bit5 배경 뒤, bit6 좌우반전, bit7 상하반전.",
    ),
    _b(
        "spr_meta",
        VOID,
        [("x", U8), ("y", U8), ("metasprite", U8)],
        "sprite",
        "asset metasprite 를 (x,y) 기준으로 한 번에 추가한다.",
        "spr_meta(hero_x, hero_y, MS_HERO_IDLE);",
        needs=("oam", "metasprite"),
    ),
    _b(
        "spr_meta_flip",
        VOID,
        [("x", U8), ("y", U8), ("metasprite", U8), ("flip", U8)],
        "sprite",
        "메타스프라이트를 좌우반전(flip=1)해서 추가한다.",
        "spr_meta_flip(hero_x, hero_y, MS_HERO_WALK, facing_left);",
        needs=("oam", "metasprite"),
    ),
    _b(
        "spr_count",
        U8,
        [],
        "sprite",
        "이번 프레임에 지금까지 추가된 스프라이트 수 (최대 64).",
        "if (spr_count() < 60) spr(x, y, t, 0);",
        needs=("oam",),
    ),
    # -- scroll ------------------------------------------------------------
    _b(
        "scroll_set",
        VOID,
        [("x", U16), ("y", U8)],
        "scroll",
        "배경 스크롤 위치. x는 0~511 (네임테이블 2장), y는 0~239.",
        "scroll_set(camera_x, 0);",
        needs=("scroll",),
        notes="scroll_set 을 한 번이라도 부르면 런타임이 매 NMI마다 스크롤을 다시 씁니다.",
    ),
    # -- palette -----------------------------------------------------------
    _b(
        "pal_load",
        VOID,
        [("palette", U8)],
        "palette",
        "asset palette 32바이트를 통째로 올린다.",
        "pal_load(PAL_GAME);",
        needs=("palette",),
    ),
    _b(
        "pal_set",
        VOID,
        [("index", U8), ("color", U8)],
        "palette",
        "팔레트 한 칸만 바꾼다. index 0~31.",
        "pal_set(1, 0x16);",
        needs=("palette",),
    ),
    _b(
        "pal_bright",
        VOID,
        [("level", U8)],
        "palette",
        "화면 밝기 0(암전)~4(원본). 페이드 인/아웃에 쓴다.",
        "for (i = 4; i > 0; i--) { pal_bright(i - 1); wait_vblank(); }",
        needs=("palette",),
    ),
    # -- math --------------------------------------------------------------
    _b(
        "mul8",
        U8,
        [("a", U8), ("b", U8)],
        "math",
        "8x8 곱셈의 하위 8비트. `a * b` 와 같지만 명시적.",
        "index = mul8(row, 16);",
        needs=("mul",),
    ),
    _b(
        "mul16",
        U16,
        [("a", U8), ("b", U8)],
        "math",
        "8x8 곱셈의 16비트 결과.",
        "offset = mul16(y, 32);",
        needs=("mul",),
    ),
    _b(
        "div8",
        U8,
        [("a", U8), ("b", U8)],
        "math",
        "8비트 나눗셈 몫.",
        "cell = div8(pixel_x, 16);",
        needs=("div",),
    ),
    _b(
        "mod8",
        U8,
        [("a", U8), ("b", U8)],
        "math",
        "8비트 나머지.",
        "phase = mod8(frame, 60);",
        needs=("div",),
    ),
    _b(
        "abs8",
        U8,
        [("value", I8)],
        "math",
        "부호 있는 8비트의 절댓값.",
        "distance = abs8(a_x - b_x);",
    ),
    _b(
        "min8",
        U8,
        [("a", U8), ("b", U8)],
        "math",
        "둘 중 작은 값.",
        "speed = min8(speed + 1, MAX_SPEED);",
    ),
    _b(
        "max8",
        U8,
        [("a", U8), ("b", U8)],
        "math",
        "둘 중 큰 값.",
        "hp = max8(hp - damage, 0);",
    ),
    _b(
        "rand",
        U8,
        [],
        "math",
        "0~255 의사난수. 16비트 LFSR.",
        "enemy_x = rand();",
        needs=("rand",),
    ),
    _b(
        "rand_range",
        U8,
        [("n", U8)],
        "math",
        "0 이상 n 미만의 난수. n이 0이면 0.",
        "piece = rand_range(7);",
        needs=("rand", "div"),
    ),
    _b(
        "rand_seed",
        VOID,
        [("seed", U16)],
        "math",
        "난수 씨앗을 정한다. 0이면 무시된다.",
        "rand_seed(frame_count() + 1);",
        needs=("rand",),
        notes="타이틀 화면에서 입력이 들어온 프레임 수로 씨를 뿌리면 매번 다른 판이 됩니다.",
    ),
    # -- collision ---------------------------------------------------------
    _b(
        "box_hit",
        U8,
        [
            ("ax", U8),
            ("ay", U8),
            ("aw", U8),
            ("ah", U8),
            ("bx", U8),
            ("by", U8),
            ("bw", U8),
            ("bh", U8),
        ],
        "collision",
        "두 AABB가 겹치면 1, 아니면 0.",
        "if (box_hit(hero_x, hero_y, 12, 15, foe_x, foe_y, 14, 14)) hurt();",
        needs=("collision",),
    ),
    # -- sound -------------------------------------------------------------
    _b(
        "sfx_play",
        VOID,
        [("sfx", U8)],
        "sound",
        "asset sfx 를 재생한다. 재생 중에는 펄스2 채널을 빌린다.",
        "sfx_play(SFX_JUMP);",
        needs=("sfx",),
    ),
    _b(
        "music_play",
        VOID,
        [("song", U8)],
        "sound",
        "asset song 을 처음부터 재생한다.",
        "music_play(SONG_MAIN);",
        needs=("music",),
    ),
    _b(
        "music_stop",
        VOID,
        [],
        "sound",
        "음악을 멈추고 채널을 끈다.",
        "music_stop();",
        needs=("music",),
    ),
    _b(
        "music_pause",
        VOID,
        [],
        "sound",
        "음악을 그 자리에서 멈춘다.",
        "music_pause();",
        needs=("music",),
    ),
    _b(
        "music_resume",
        VOID,
        [],
        "sound",
        "music_pause() 한 자리에서 다시 재생한다.",
        "music_resume();",
        needs=("music",),
    ),
]


BY_NAME: Dict[str, Builtin] = {b.name: b for b in BUILTINS}


# Constants fami.h exposes.  Keeping them here means `famic api --json` reports
# them too, so an agent never has to guess a bit value.
# (name, value, summary, hex?)
CONSTANTS: List[Tuple[str, int, str, bool]] = [
    ("PAD_A", 0x80, "A 버튼", True),
    ("PAD_B", 0x40, "B 버튼", True),
    ("PAD_SELECT", 0x20, "Select", True),
    ("PAD_START", 0x10, "Start", True),
    ("PAD_UP", 0x08, "십자키 위", True),
    ("PAD_DOWN", 0x04, "십자키 아래", True),
    ("PAD_LEFT", 0x02, "십자키 왼쪽", True),
    ("PAD_RIGHT", 0x01, "십자키 오른쪽", True),
    ("SPR_PAL0", 0x00, "스프라이트 팔레트 0", True),
    ("SPR_PAL1", 0x01, "스프라이트 팔레트 1", True),
    ("SPR_PAL2", 0x02, "스프라이트 팔레트 2", True),
    ("SPR_PAL3", 0x03, "스프라이트 팔레트 3", True),
    ("SPR_BEHIND", 0x20, "배경 뒤에 그림", True),
    ("SPR_FLIP_X", 0x40, "좌우 반전", True),
    ("SPR_FLIP_Y", 0x80, "상하 반전", True),
    ("SCREEN_TILES_W", 32, "네임테이블 가로 타일 수", False),
    ("SCREEN_TILES_H", 30, "네임테이블 세로 타일 수", False),
    ("SCREEN_CELLS_W", 16, "16x16 셀 가로 개수", False),
    ("SCREEN_CELLS_H", 15, "16x16 셀 세로 개수", False),
    ("MAX_SPRITES", 64, "하드웨어 스프라이트 총 개수", False),
]


GROUPS: Dict[str, str] = {
    "system": "시스템 / 프레임",
    "input": "컨트롤러",
    "background": "배경 (네임테이블)",
    "sprite": "스프라이트 (OAM)",
    "scroll": "스크롤",
    "palette": "팔레트",
    "math": "수학",
    "collision": "충돌",
    "sound": "사운드",
}


def manifest() -> Dict[str, object]:
    """The machine-readable API description behind `famic api --json`."""

    from .assets import ASSET_KIND_DOCS
    from .diagnostics import ERRORS

    return {
        "version": 2,
        "target": {
            "mapper": 0,
            "name": "NROM-256",
            "prg_bytes": 0x8000,
            "chr_bytes": 0x2000,
            "ram_bytes": 0x0800,
            "max_tiles": 512,
        },
        "types": [
            {"name": "u8", "bits": 8, "signed": False},
            {"name": "i8", "bits": 8, "signed": True},
            {"name": "u16", "bits": 16, "signed": False},
            {"name": "i16", "bits": 16, "signed": True},
        ],
        "groups": GROUPS,
        "functions": [b.to_dict() for b in BUILTINS],
        "constants": [
            {"name": n, "value": v, "summary": s} for n, v, s, _ in CONSTANTS
        ],
        "notes": [{"name": n, "value": v} for n, v in note_constants()],
        "assets": ASSET_KIND_DOCS,
        "diagnostics": [{"code": c, "title": t} for c, t in sorted(ERRORS.items())],
    }


def generate_header() -> str:
    """Produce include/fami.h from the manifest."""

    out: List[str] = []
    out.append("/* fami.h -- FAMI-C runtime API.")
    out.append(" *")
    out.append(" * 이 파일은 famic/api.py 에서 생성됩니다. 직접 고치지 마세요.")
    out.append(" * 다시 만들려면: python famic.py header")
    out.append(" */")
    out.append("")
    out.append("#ifndef FAMI_H")
    out.append("#define FAMI_H")
    out.append("")
    out.append("/* 폭이 이름에 보이는 타입을 쓰세요. int 는 i16, char 는 u8 입니다. */")
    out.append("typedef unsigned char  u8;")
    out.append("typedef signed char    i8;")
    out.append("typedef unsigned int   u16;")
    out.append("typedef int            i16;")
    out.append("")
    width = max(len(n) for n, _, _, _ in CONSTANTS)
    for name, value, summary, as_hex in CONSTANTS:
        pad = " " * (width - len(name))
        literal = f"0x{value:02X}" if as_hex else str(value)
        out.append(f"#define {name}{pad} {literal:<6} /* {summary} */")
    out.append("")
    out.append("/* ---- 음 이름 (asset sfx / asset song) ---- */")
    out.append("/* 0 = 쉼표, HOLD = 앞 행의 음을 유지 */")
    for name, value in note_constants():
        out.append(f"#define {name:<8} {value}")
    out.append("")
    # The runtime API is built into the compiler, so these are a reference
    # list rather than declarations.  Declaring them yourself is unnecessary
    # and, if the signature drifts, actively harmful -- so they stay comments.
    out.append("/* ========================================================")
    out.append(" * 런타임 API")
    out.append(" *")
    out.append(" * 아래 함수들은 컴파일러에 내장되어 있습니다.")
    out.append(" * 따로 선언하지 말고 그냥 호출하세요. 호출하면 켜집니다.")
    out.append(" * 전체 목록/예시: python famic.py api --json")
    out.append(" * ======================================================== */")
    for group, title in GROUPS.items():
        members = [b for b in BUILTINS if b.group == group]
        if not members:
            continue
        out.append("")
        out.append(f"/* -- {title} */")
        for b in members:
            out.append(f"/*   {b.signature():<52} {b.summary} */")
    out.append("")
    out.append("#endif /* FAMI_H */")
    return "\n".join(out) + "\n"
