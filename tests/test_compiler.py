"""Compiler tests.

These are deliberately end-to-end: compile a program, run it on the bundled
headless NES, and read the answer out of RAM by symbol name.  A test that only
inspected the generated assembly would pass while the ROM did the wrong thing,
which is the failure mode this toolchain exists to make impossible.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from famic.assembler import CHR_SIZE, PRG_SIZE
from famic.compiler import compile_source
from famic.diagnostics import CompileError
from famic.emu import NES, BUTTONS


PALETTE = """
asset palette PAL = {
    0x0F,0x11,0x21,0x31,  0x0F,0x06,0x16,0x26,
    0x0F,0x09,0x19,0x29,  0x0F,0x00,0x10,0x30,
    0x0F,0x12,0x22,0x32,  0x0F,0x06,0x16,0x36,
    0x0F,0x08,0x18,0x28,  0x0F,0x14,0x24,0x34
};
"""


def build(source: str):
    return compile_source(source, "<test>")


def run(source: str, frames: int = 4, pad_script=None):
    result = build(source)
    nes = NES(result.rom, result.symbols)
    for frame in range(frames):
        nes.set_pad(0, (pad_script or {}).get(frame, 0))
        nes.run_frame()
    return nes, result


def peek(nes, result, name: str, width: int = 1) -> int:
    addr = result.symbols[name]
    if width == 2:
        return nes.read(addr) | (nes.read(addr + 1) << 8)
    return nes.read(addr)


class RomShapeTests(unittest.TestCase):
    def test_ines_header_and_sizes(self):
        result = build("void main(void) { while (1) { } }")
        self.assertEqual(result.rom[:4], b"NES\x1a")
        self.assertEqual(len(result.rom), 16 + PRG_SIZE + CHR_SIZE)
        self.assertEqual(result.rom[4], PRG_SIZE // 0x4000)
        self.assertEqual(result.rom[5], 1)
        self.assertEqual(result.rom[6] & 0xF0, 0x00, "mapper 0")

    def test_vectors_point_into_prg(self):
        result = build("void main(void) { while (1) { } }")
        prg = result.rom[16 : 16 + PRG_SIZE]
        for offset, name in ((0x7FFA, "nmi"), (0x7FFC, "reset"), (0x7FFE, "irq")):
            addr = prg[offset] | (prg[offset + 1] << 8)
            self.assertGreaterEqual(addr, 0x8000, f"{name} vector")
            self.assertLessEqual(addr, 0xFFFF, f"{name} vector")

    def test_tile_zero_is_blank(self):
        result = build("void main(void) { while (1) { } }")
        chr_rom = result.rom[16 + PRG_SIZE :]
        self.assertEqual(chr_rom[:16], b"\x00" * 16)


class ArithmeticTests(unittest.TestCase):
    """The one thing that must never be quietly wrong."""

    def test_widening_multiply(self):
        source = """
u8 a;
u16 out;
void main(void) { a = 30; out = a * 100; while (1) { } }
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out", 2), 3000)

    def test_eight_bit_add_widens(self):
        source = """
u8 a;
u8 b;
u16 out;
void main(void) { a = 200; b = 100; out = a + b; while (1) { } }
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out", 2), 300)

    def test_byte_context_still_wraps(self):
        source = """
u8 a;
u8 b;
u8 out;
void main(void) { a = 200; b = 100; out = a + b; while (1) { } }
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out", 1), 44)

    def test_sixteen_bit_ops(self):
        source = """
u16 a;
u16 b;
u16 mul;
u16 div;
u16 mod;
u16 sub;
void main(void) {
    a = 1000; b = 7;
    mul = a * 3;
    div = a / b;
    mod = a % b;
    sub = 65535 - a;
    while (1) { }
}
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_mul", 2), 3000)
        self.assertEqual(peek(nes, result, "_g_div", 2), 142)
        self.assertEqual(peek(nes, result, "_g_mod", 2), 6)
        self.assertEqual(peek(nes, result, "_g_sub", 2), 64535)

    def test_unsigned_and_signed_comparisons(self):
        source = """
u16 big;
i8 neg;
u8 r0;
u8 r1;
u8 r2;
u8 r3;
void main(void) {
    big = 40000; neg = -5;
    r0 = big > 1000;
    r1 = big < 1000;
    r2 = neg < 0;
    r3 = neg > -10;
    while (1) { }
}
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_r0"), 1)
        self.assertEqual(peek(nes, result, "_g_r1"), 0)
        self.assertEqual(peek(nes, result, "_g_r2"), 1)
        self.assertEqual(peek(nes, result, "_g_r3"), 1)

    def test_shifts_and_bitwise(self):
        source = """
u16 out0;
u8 out1;
u8 out2;
void main(void) {
    out0 = 1000 << 2;
    out1 = 0xF0 | 0x0C;
    out2 = 0xFF ^ 0x0F;
    while (1) { }
}
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out0", 2), 4000)
        self.assertEqual(peek(nes, result, "_g_out1"), 0xFC)
        self.assertEqual(peek(nes, result, "_g_out2"), 0xF0)


class LanguageTests(unittest.TestCase):
    def test_struct_lowered_to_parallel_arrays(self):
        source = """
struct Actor { u8 x; u8 y; };
struct Actor foes[4];
u8 total;
u8 i;
void main(void) {
    for (i = 0; i < 4; i++) { foes[i].x = i * 3; foes[i].y = 1; }
    total = foes[3].x + foes[0].y;
    while (1) { }
}
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_total"), 10)
        self.assertIn("_g_foes__x", result.symbols)
        self.assertIn("_g_foes__y", result.symbols)

    def test_two_dimensional_array(self):
        source = """
u8 grid[3][8];
u8 out;
u8 i;
u8 j;
void main(void) {
    for (i = 0; i < 3; i++) { for (j = 0; j < 8; j++) { grid[i][j] = i * 10 + j; } }
    out = grid[2][5];
    while (1) { }
}
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out"), 25)

    def test_switch_and_do_while(self):
        source = """
u8 out;
u8 i;
void main(void) {
    i = 0;
    do { i++; } while (i < 3);
    switch (i) {
    case 2: out = 20; break;
    case 3: out = 30; break;
    default: out = 99; break;
    }
    while (1) { }
}
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out"), 30)

    def test_const_table_lives_in_rom(self):
        source = """
const u8 table[5] = { 9, 8, 7, 6, 5 };
u8 out;
void main(void) { out = table[3]; while (1) { } }
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out"), 6)
        self.assertGreaterEqual(result.symbols["_r_table"], 0x8000)

    def test_global_initialiser_runs(self):
        source = """
u8 lives = 3;
u16 score = 5000;
u8 seq[4] = { 4, 3, 2, 1 };
u8 out;
void main(void) { out = seq[1]; while (1) { } }
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_lives"), 3)
        self.assertEqual(peek(nes, result, "_g_score", 2), 5000)
        self.assertEqual(peek(nes, result, "_g_out"), 3)

    def test_nested_calls_do_not_clobber_arguments(self):
        source = """
u8 out;
u8 add(u8 a, u8 b) { return a + b; }
u8 twice(u8 v) { return v + v; }
void main(void) { out = add(twice(3), add(1, 2)); while (1) { } }
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out"), 9)

    def test_function_like_macro(self):
        source = """
#define DOUBLE(v) ((v) * 2)
#define SUM(a, b) ((a) + (b))
u8 out;
void main(void) { out = SUM(DOUBLE(3), 4); while (1) { } }
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out"), 10)

    def test_enum_and_local_array(self):
        source = """
enum { A = 5, B, C = 20 };
u8 out;
void main(void) {
    u8 buf[4];
    buf[0] = A; buf[1] = B; buf[2] = C;
    out = buf[0] + buf[1] + buf[2];
    while (1) { }
}
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out"), 5 + 6 + 20)


class DiagnosticTests(unittest.TestCase):
    """Every rejection must name a line and say what to write instead."""

    def assert_error(self, source: str, code: str):
        with self.assertRaises(CompileError) as ctx:
            build(source)
        diag = ctx.exception.diagnostic
        self.assertEqual(diag.code, code, diag.message)
        self.assertGreater(diag.line, 0, f"{code} has no line number")
        self.assertTrue(diag.hint, f"{code} has no hint")
        return diag

    def test_missing_main(self):
        with self.assertRaises(CompileError) as ctx:
            build("u8 x;")
        self.assertEqual(ctx.exception.diagnostic.code, "E0304")
        self.assertTrue(ctx.exception.diagnostic.hint)

    def test_pointer_is_rejected_with_a_hint(self):
        diag = self.assert_error("void main(void) { u8 v; v = *v; }", "E0203")
        self.assertIn("배열", diag.hint)

    def test_unknown_identifier(self):
        self.assert_error("void main(void) { nope = 1; }", "E0303")

    def test_unknown_function_suggests_a_name(self):
        diag = self.assert_error("void main(void) { wait_vblnk(); }", "E0308")
        self.assertIn("wait_vblank", diag.hint)

    def test_wrong_argument_count_shows_signature(self):
        diag = self.assert_error("void main(void) { bg_tile(1, 2); }", "E0307")
        self.assertIn("bg_tile", diag.hint)

    def test_const_assignment(self):
        self.assert_error(
            "const u8 t[2] = { 1, 2 };\nvoid main(void) { t[0] = 5; }", "E0305"
        )

    def test_tile_row_length(self):
        diag = self.assert_error(
            'asset tile T = { "1234567" "11111111" "11111111" "11111111"'
            ' "11111111" "11111111" "11111111" "11111111" };\nvoid main(void) { }',
            "E0502",
        )
        self.assertIn("8", diag.message)

    def test_palette_length(self):
        self.assert_error(
            "asset palette P = { 0x0F, 0x01 };\nvoid main(void) { }", "E0503"
        )

    def test_bg_text_requires_a_literal(self):
        self.assert_error(
            "u8 msg;\nvoid main(void) { bg_text(0, 0, msg); }", "E0602"
        )

    def test_signed_division_is_refused_not_silently_wrong(self):
        diag = self.assert_error(
            "i8 a;\nu8 out;\nvoid main(void) { a = -9; out = a / 3; }", "E0402"
        )
        self.assertIn("abs8", diag.hint)

    def test_signed_division_by_power_of_two_is_allowed(self):
        source = """
i8 a;
i8 out;
void main(void) { a = -8; out = a / 2; while (1) { } }
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_out"), 0xFC)  # -4


class RuntimeTests(unittest.TestCase):
    def test_background_text_reaches_the_nametable(self):
        source = PALETTE + """
void main(void) {
    pal_load(PAL);
    bg_text(3, 5, "HELLO");
    while (1) { wait_vblank(); }
}
"""
        nes, result = run(source, frames=6)
        base = nes.symbols["__font_base"]
        from famic.assets import FONT_ORDER

        read = "".join(
            FONT_ORDER[nes.ppu.read_vram(0x2000 + 5 * 32 + 3 + i) - base] for i in range(5)
        )
        self.assertEqual(read, "HELLO")

    def test_sprites_only_render_when_used(self):
        no_sprites = build("void main(void) { while (1) { wait_vblank(); } }")
        nes = NES(no_sprites.rom, no_sprites.symbols)
        for _ in range(3):
            nes.run_frame()
        self.assertEqual(nes.ppu.mask & 0x10, 0, "sprites enabled without an OAM")

    def test_metasprite_fills_oam(self):
        source = "#include <fami.h>\n" + PALETTE + """
asset tiles T[4] = {
    "11111111" "11111111" "11111111" "11111111"
    "11111111" "11111111" "11111111" "11111111"
    "11111111" "11111111" "11111111" "11111111"
    "11111111" "11111111" "11111111" "11111111"
    "11111111" "11111111" "11111111" "11111111"
    "11111111" "11111111" "11111111" "11111111"
    "11111111" "11111111" "11111111" "11111111"
    "11111111" "11111111" "11111111" "11111111"
};
asset metasprite MS = {
    { 0, 0, T + 0, SPR_PAL0 }, { 8, 0, T + 1, SPR_PAL0 },
    { 0, 8, T + 2, SPR_PAL0 }, { 8, 8, T + 3, SPR_PAL0 }
};
void main(void) {
    pal_load(PAL);
    while (1) { spr_clear(); spr_meta(64, 80, MS); wait_vblank(); }
}
"""
        nes, result = run(source, frames=6)
        visible = [i for i in range(64) if nes.ppu.oam[i * 4] < 0xEF]
        self.assertEqual(len(visible), 4)
        self.assertEqual(nes.ppu.oam[3], 64)       # first sprite x
        self.assertEqual(nes.ppu.oam[0], 80 - 1)   # first sprite y (OAM is y-1)
        self.assertEqual(nes.ppu.oam[7], 72)       # second sprite x = 64 + 8

    def test_pad_edges(self):
        source = """
u8 held;
u8 pressed;
u8 released;
u8 seen_press;
u8 seen_release;
void main(void) {
    while (1) {
        pad_poll();
        held = pad_held(0);
        pressed = pad_pressed(0);
        released = pad_released(0);
        if (pressed & PAD_A) seen_press = seen_press + 1;
        if (released & PAD_A) seen_release = seen_release + 1;
        wait_vblank();
    }
}
"""
        script = {5: BUTTONS["A"], 6: BUTTONS["A"], 7: BUTTONS["A"]}
        nes, result = run(source, frames=14, pad_script=script)
        self.assertEqual(peek(nes, result, "_g_seen_press"), 1, "A pressed once")
        self.assertEqual(peek(nes, result, "_g_seen_release"), 1, "A released once")

    def test_palette_upload(self):
        source = PALETTE + """
void main(void) { pal_load(PAL); while (1) { wait_vblank(); } }
"""
        nes, result = run(source, frames=6)
        self.assertEqual(nes.ppu.palette[1], 0x11)
        self.assertEqual(nes.ppu.palette[17], 0x12)

    def test_music_and_sfx_drive_the_apu(self):
        source = """
asset sfx S = { {12, N_C5}, {8, N_E5} };
asset song G = { 4, { N_C4, N_E4, N_C3, 2 }, { N_G4, N_C5, HOLD, 0 } };
void main(void) {
    music_play(G);
    sfx_play(S);
    while (1) { wait_vblank(); }
}
"""
        nes, result = run(source, frames=20)
        registers = {addr for _, addr, _ in nes.apu.writes}
        for expected in (0x4000, 0x4002, 0x4004, 0x4008, 0x400C, 0x4015):
            self.assertIn(expected, registers, f"${expected:04X} never written")

    def test_bg_tile_survives_a_full_queue(self):
        """bg_rect writes far more cells than one vblank can drain."""

        source = PALETTE + """
void main(void) {
    pal_load(PAL);
    bg_rect(0, 0, 32, 30, 1);
    while (1) { wait_vblank(); }
}
"""
        nes, result = run(source, frames=60)
        filled = sum(1 for i in range(960) if nes.ppu.read_vram(0x2000 + i) == 1)
        self.assertEqual(filled, 960, "queued writes were dropped")

    def test_rand_range_stays_in_bounds(self):
        source = """
u8 seen[8];
u8 i;
u8 bad;
void main(void) {
    rand_seed(1234);
    for (i = 0; i < 200; i++) {
        u8 v;
        v = rand_range(7);
        if (v >= 7) bad = 1;
        seen[v] = 1;
    }
    while (1) { }
}
"""
        nes, result = run(source, frames=6)
        self.assertEqual(peek(nes, result, "_g_bad"), 0, "rand_range escaped its bound")
        hits = sum(peek(nes, result, "_g_seen") for _ in range(1))
        base = result.symbols["_g_seen"]
        covered = sum(1 for i in range(7) if nes.read(base + i))
        self.assertGreaterEqual(covered, 6, "distribution is degenerate")

    def test_box_hit(self):
        source = """
u8 a;
u8 b;
void main(void) {
    a = box_hit(10, 10, 8, 8, 14, 14, 8, 8);
    b = box_hit(10, 10, 8, 8, 40, 40, 8, 8);
    while (1) { }
}
"""
        nes, result = run(source)
        self.assertEqual(peek(nes, result, "_g_a"), 1)
        self.assertEqual(peek(nes, result, "_g_b"), 0)


class BudgetTests(unittest.TestCase):
    def test_ram_and_tile_budgets_are_reported(self):
        result = build("void main(void) { while (1) { } }")
        for key in ("ram_used", "ram_free", "zp_used", "zp_free", "tiles_used", "prg_used"):
            self.assertIn(key, result.info)

    def test_chr_overflow_names_the_offenders(self):
        tile = '"11111111" ' * 8
        source = "\n".join(f"asset tile T{i} = {{ {tile} }};" for i in range(300))
        source += "\nvoid main(void) { while (1) { } }"
        with self.assertRaises(CompileError) as ctx:
            build(source)
        diag = ctx.exception.diagnostic
        self.assertEqual(diag.code, "E0507")
        self.assertIn("T0", diag.hint)


if __name__ == "__main__":
    unittest.main()
