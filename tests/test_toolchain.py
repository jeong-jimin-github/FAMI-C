import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

from famic import (
    CHR_SIZE,
    PRG_BANKS,
    PRG_BASE,
    PRG_SIZE,
    PRG_VECTORS,
    Assembler,
    build_rom,
    compile_c_to_asm,
    make_chr,
    make_ines,
)


ROOT = Path(__file__).resolve().parents[1]


MUSIC_ARRAY_NAMES = (
    *(
        f"MUSIC_PULSE1_{suffix}"
        for suffix in ("BASE", "PAIR0", "PAIR1", "PAIR2", "PAIR3")
    ),
    *(
        f"MUSIC_PULSE2_{suffix}"
        for suffix in ("BASE", "PAIR0", "PAIR1", "PAIR2", "PAIR3")
    ),
    *(
        f"MUSIC_TRIANGLE_{suffix}"
        for suffix in ("BASE", "PAIR0", "PAIR1", "PAIR2", "PAIR3")
    ),
    *(f"MUSIC_NOISE_PAIR{pair}" for pair in range(4)),
    *(f"MUSIC_TUPLE_{channel}" for channel in ("PULSE1", "PULSE2", "TRIANGLE", "NOISE")),
    "MUSIC_ORDER0",
    "MUSIC_ORDER1",
)


def load_music_arrangement():
    return json.loads(
        (ROOT / "assets" / "tetris_music.json").read_text(encoding="utf-8")
    )


def music_c_arrays(arrangement):
    """Return the fixed v2 C ABI without importing the optional MIDI package."""

    patterns = arrangement["patterns"]
    tuples = arrangement["tuples"]
    arrays = []
    for channel, stem in (
        ("pulse1", "PULSE1"),
        ("pulse2", "PULSE2"),
        ("triangle", "TRIANGLE"),
    ):
        arrays.append((f"MUSIC_{stem}_BASE", patterns[channel]["base"]))
        arrays.extend(
            (f"MUSIC_{stem}_PAIR{index}", values)
            for index, values in enumerate(patterns[channel]["pairs"])
        )
    arrays.extend(
        (f"MUSIC_NOISE_PAIR{index}", values)
        for index, values in enumerate(patterns["noise"]["pairs"])
    )
    arrays.extend(
        (f"MUSIC_TUPLE_{stem}", tuples[channel])
        for channel, stem in (
            ("pulse1", "PULSE1"),
            ("pulse2", "PULSE2"),
            ("triangle", "TRIANGLE"),
            ("noise", "NOISE"),
        )
    )
    arrays.extend(
        (f"MUSIC_ORDER{index}", values)
        for index, values in enumerate(arrangement["order_pages"])
    )
    return arrays


def render_music_c_arrays(arrangement):
    blocks = []
    for name, values in music_c_arrays(arrangement):
        lines = [f"const unsigned char {name}[{len(values)}] = {{"]
        for offset in range(0, len(values), 16):
            lines.append(
                "    "
                + ", ".join(str(value) for value in values[offset : offset + 16])
                + ","
            )
        lines.append("};")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def chr_tile_pixels(chr_rom, tile):
    base = tile * 16
    pixels = []
    for row in range(8):
        low = chr_rom[base + row]
        high = chr_rom[base + 8 + row]
        pixels.append(
            [
                ((low >> (7 - col)) & 1) | (((high >> (7 - col)) & 1) << 1)
                for col in range(8)
            ]
        )
    return pixels


def lfsr16_step(state):
    return ((state >> 1) ^ (0xB400 if state & 1 else 0)) & 0xFFFF


def tetris_source():
    return (ROOT / "examples" / "tetris.c").read_text(encoding="utf-8")


def const_array(source, name):
    """Return the integers initialising `const unsigned char name[...]`."""

    match = re.search(
        r"const unsigned char " + re.escape(name) + r"\[\d*\]\s*=\s*\{(.*?)\}\s*;",
        source,
        re.S,
    )
    if match is None:
        raise AssertionError(f"{name} is missing from the source")
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.S)
    return [int(value) for value in re.findall(r"-?\d+", body)]


SHAPE_MASKS = (8, 4, 2, 1)


def shape_cells(shapes, piece, rotation):
    base = ((piece * 4) + rotation) * 4
    return frozenset(
        (x, y)
        for y in range(4)
        for x in range(4)
        if shapes[base + y] & SHAPE_MASKS[x]
    )


def normalise(cells):
    left = min(x for x, _y in cells)
    top = min(y for _x, y in cells)
    return frozenset((x - left, y - top) for x, y in cells)


def rotate_cw(cells):
    """Clockwise on screen, where y grows downwards."""

    return frozenset((-y, x) for x, y in cells)


class ToolchainTests(unittest.TestCase):
    def test_smoke_compiles_to_prg(self):
        source = (ROOT / "tests" / "smoke.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(source)
        assembler = Assembler()
        prg = assembler.assemble(asm)

        self.assertEqual(len(prg), PRG_SIZE)
        reset_offset = PRG_VECTORS + 2 - PRG_BASE
        reset = prg[reset_offset] | (prg[reset_offset + 1] << 8)
        self.assertEqual(reset, PRG_BASE)
        ram_symbols = [addr for addr in assembler.symbols.values() if addr < 0x0800]
        self.assertTrue(ram_symbols)
        self.assertTrue(all(not 0x0100 <= addr < 0x0200 for addr in ram_symbols))
        self.assertNotIn("_music_init:", asm)
        self.assertNotIn("JSR _music_tick", asm)
        self.assertNotIn("STA $4015", asm)

    def test_music_runtime_assembles_and_ticks_from_nmi(self):
        source = """
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void music_init(void);

const unsigned char MUSIC_PULSE1[256] = { 69 };
const unsigned char MUSIC_PULSE2[256] = { 72 };
const unsigned char MUSIC_TRIANGLE[256] = { 45 };
const unsigned char MUSIC_NOISE[256] = { 3 };

void main(void)
{
    music_init();
    while (1) { }
}
"""
        asm = compile_c_to_asm(source)
        prg = Assembler().assemble(asm)

        self.assertEqual(len(prg), PRG_SIZE)
        self.assertIn("_music_init:", asm)
        self.assertIn("_music_tick:", asm)
        self.assertIn("STA $4000", asm)
        self.assertIn("STA $4015", asm)
        nmi = asm.split("_nmi:", 1)[1].split("_irq:", 1)[0]
        self.assertIn("JSR _music_tick", nmi)

    def test_music_pause_silences_the_song_and_resume_retriggers_it(self):
        source = """
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void music_init(void);
extern void music_pause(void);
extern void music_resume(void);

const unsigned char MUSIC_PULSE1[256] = { 69 };
const unsigned char MUSIC_PULSE2[256] = { 72 };
const unsigned char MUSIC_TRIANGLE[256] = { 45 };
const unsigned char MUSIC_NOISE[256] = { 3 };

void main(void)
{
    music_init();
    music_pause();
    music_resume();
    while (1) { }
}
"""
        asm = compile_c_to_asm(source)
        prg = Assembler().assemble(asm)
        self.assertEqual(len(prg), PRG_SIZE)

        pause = asm.split("_music_pause:", 1)[1].split("_music_resume:", 1)[0]
        self.assertIn("LDA #$00\nSTA __music_enabled", pause)
        # Every channel the song owns has to go quiet, or the last note would
        # sustain for as long as the game is held.
        self.assertIn("LDA #$70\nSTA $4000", pause)
        self.assertIn("LDA #$30\nSTA $4004", pause)
        self.assertIn("LDA #$80\nSTA $4008", pause)
        self.assertIn("LDA #$30\nSTA $400C", pause)
        # The song position itself is untouched, so a resume picks up where it
        # left off instead of restarting.
        for state in ("__music_step", "__music_phase"):
            self.assertNotIn(f"STA {state}", pause)

        resume = asm.split("_music_resume:", 1)[1].split("_music_tick:", 1)[0]
        for cached in ("__music_last_pulse1", "__music_last_pulse2", "__music_last_triangle"):
            self.assertIn(f"STA {cached}", resume)
        self.assertIn("LDA #$01\nSTA __music_enabled", resume)

    def test_music_transport_needs_the_music_runtime(self):
        source = """
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void music_pause(void);

void main(void)
{
    music_pause();
    while (1) { }
}
"""
        with self.assertRaises(Exception) as caught:
            compile_c_to_asm(source)
        self.assertIn("music_init", str(caught.exception))

    def test_tetris_pause_parks_the_song_and_resume_restarts_it(self):
        source = tetris_source()

        playing = source.split("void tick_playing(void)", 1)[1].split("\n}", 1)[0]
        self.assertIn("music_pause();", playing)
        paused = source.split("void tick_paused(void)", 1)[1].split("\n}", 1)[0]
        self.assertIn("music_resume();", paused)
        self.assertNotIn("music_pause();", paused)

        asm = compile_c_to_asm(source)
        self.assertIn("_music_pause:", asm)
        self.assertIn("_music_resume:", asm)
        self.assertIn("JSR _music_pause", asm)
        self.assertIn("JSR _music_resume", asm)

    def test_compressed_music_v2_data_abi_and_full_length(self):
        arrangement = load_music_arrangement()
        metadata = arrangement["metadata"]
        arrays = music_c_arrays(arrangement)

        self.assertEqual(metadata["format"], "fami-c-nes-arrangement-v2")
        self.assertEqual(metadata["source_beats"], [8, 620])
        self.assertGreater(metadata["source_duration_seconds"], 266.0)
        self.assertEqual(metadata["steps_per_beat"], 4)
        self.assertEqual(metadata["step_count"], 2448)
        self.assertEqual(metadata["pattern_steps"], 8)
        self.assertEqual(metadata["order_count"], 306)
        self.assertEqual(metadata["order_page_lengths"], [256, 50])
        self.assertEqual(
            metadata["pattern_counts"],
            {
                "pulse1": 77,
                "pulse2": 30,
                "triangle": 47,
                "noise": 70,
            },
        )
        self.assertEqual(metadata["tuple_count"], 156)

        self.assertEqual(tuple(name for name, _values in arrays), MUSIC_ARRAY_NAMES)
        self.assertEqual(len(arrays), 25)
        self.assertEqual(sum(len(values) for _name, values in arrays), 1980)
        self.assertEqual(metadata["compressed_bytes"], 1980)
        self.assertEqual(metadata["uncompressed_bytes"], 9792)
        self.assertLess(
            metadata["compressed_bytes"], metadata["uncompressed_bytes"] // 4
        )

        pattern_counts = metadata["pattern_counts"]
        for name, values in arrays:
            self.assertTrue(values, name)
            self.assertTrue(
                all(type(value) is int and 0 <= value <= 255 for value in values),
                name,
            )
            if "_PAIR" in name:
                channel = next(
                    channel
                    for channel in ("pulse1", "pulse2", "triangle", "noise")
                    if channel.upper() in name
                )
                self.assertEqual(len(values), pattern_counts[channel], name)

        tuple_count = metadata["tuple_count"]
        for channel in ("pulse1", "pulse2", "triangle", "noise"):
            tuple_values = arrangement["tuples"][channel]
            self.assertEqual(len(tuple_values), tuple_count)
            self.assertTrue(
                all(value < pattern_counts[channel] for value in tuple_values)
            )
        self.assertEqual(
            [len(page) for page in arrangement["order_pages"]], [256, 50]
        )
        self.assertTrue(
            all(
                tuple_id < tuple_count
                for page in arrangement["order_pages"]
                for tuple_id in page
            )
        )

        noise_pairs = arrangement["patterns"]["noise"]["pairs"]
        self.assertTrue(
            all(
                (value >> 4) <= 6 and (value & 0x0F) <= 6
                for pair in noise_pairs
                for value in pair
            )
        )

    def test_compressed_music_generator_and_tetris_embedding_are_current(self):
        if importlib.util.find_spec("mido") is None:
            self.skipTest("optional mido dependency is not installed")

        from tools import arrange_midi

        arrangement = load_music_arrangement()
        arrange_midi.validate_arrangement(arrangement)
        self.assertEqual(
            arrange_midi.c_array_values(arrangement),
            music_c_arrays(arrangement),
        )
        decoded = arrange_midi.decode_arrangement(arrangement)
        self.assertEqual(set(decoded), {"pulse1", "pulse2", "triangle", "noise"})
        self.assertTrue(all(len(values) == 2448 for values in decoded.values()))
        self.assertTrue(all(0 <= note <= 95 for note in decoded["pulse1"]))
        self.assertTrue(all(0 <= note <= 95 for note in decoded["pulse2"]))
        self.assertTrue(all(0 <= note <= 95 for note in decoded["triangle"]))
        self.assertTrue(all(0 <= code <= 6 for code in decoded["noise"]))

        source = (ROOT / "examples" / "tetris.c").read_text(encoding="utf-8")
        self.assertEqual(arrange_midi.replace_c_music_data(source, arrangement), source)

    def test_compressed_music_runtime_assembles_with_16_bit_song_state(self):
        arrangement = load_music_arrangement()
        source = """
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void music_init(void);

%s

void main(void)
{
    music_init();
    while (1) { }
}
""" % render_music_c_arrays(arrangement)

        asm = compile_c_to_asm(source)
        prg = Assembler().assemble(asm)

        self.assertEqual(len(prg), PRG_SIZE)
        nmi = asm.split("_nmi:", 1)[1].split("_irq:", 1)[0]
        self.assertIn("JSR _music_tick", nmi)
        driver = asm.split("_music_init:", 1)[1]
        for name in MUSIC_ARRAY_NAMES:
            self.assertRegex(driver, rf"LDA _{name},[XY]")

        # The v2 ABI stores the even step in the high nibble and odd step in
        # the low nibble.  All three tonal decoders and noise must branch to
        # the low-nibble path only when bit zero is set.
        high_nibble_first = re.compile(
            r"LDA __music_pattern_step\n"
            r"AND #\$01\n"
            r"BNE [^\n]+\n"
            r"TXA\n"
            r"(?:LSR A\n){4}"
        )
        self.assertEqual(len(high_nibble_first.findall(driver)), 4)

        music_ram = re.findall(
            r"^\.ram (__music_[A-Za-z0-9_]+) 1$", asm, re.MULTILINE
        )
        self.assertGreaterEqual(sum("phase" in name for name in music_ram), 2)
        self.assertGreaterEqual(
            sum("increment" in name or "_inc" in name for name in music_ram),
            2,
        )
        self.assertGreaterEqual(sum("order" in name for name in music_ram), 2)
        self.assertTrue(any("pattern" in name and "step" in name for name in music_ram))
        current_patterns = [
            name
            for name in music_ram
            if "pattern" in name and "step" not in name
        ]
        self.assertGreaterEqual(len(current_patterns), 4)

        # 138 BPM and the two-beat 132 BPM passage use 16-bit NMI phase increments.
        for immediate in ("#$30", "#$27", "#$7C", "#$25"):
            self.assertIn(immediate, driver)
        self.assertIn("CMP #$08", driver)
        self.assertIn("CMP #$32", driver)

    def test_tetris_builds_mapper0_ines_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tetris.nes"
            asm = Path(tmp) / "tetris.asm"
            build_rom(ROOT / "examples" / "tetris.c", out, asm)
            rom = out.read_bytes()
            vectors = asm.read_text(encoding="utf-8").rsplit(".org", 1)[1]

        self.assertEqual(rom[:4], b"NES\x1A")
        self.assertEqual(rom[4], PRG_BANKS)
        self.assertEqual(rom[4], 2)
        self.assertEqual(rom[5], 1)
        self.assertEqual(rom[6], 0)
        self.assertEqual(rom[7], 0)
        self.assertEqual(len(rom), 16 + PRG_SIZE + CHR_SIZE)

        # NROM-256 keeps mapper 0 while placing the vectors at the top of a
        # single 32K bank rather than the 16K NROM-128 mirror.
        self.assertEqual(PRG_VECTORS, 0xFFFA)
        self.assertTrue(vectors.lstrip().startswith("$FFFA"), vectors[:32])
        reset_offset = 16 + PRG_VECTORS + 2 - PRG_BASE
        self.assertEqual(rom[reset_offset] | (rom[reset_offset + 1] << 8), PRG_BASE)

    def test_tetris_ram_does_not_overlap_6502_stack(self):
        source = (ROOT / "examples" / "tetris.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(source)
        assembler = Assembler()
        assembler.assemble(asm)

        stack_page_symbols = [
            name
            for name, addr in assembler.symbols.items()
            if 0x0100 <= addr < 0x0200
        ]
        self.assertEqual(stack_page_symbols, [])

    def test_rng_is_maximal_16_bit_lfsr_and_advances_with_input_timing(self):
        seed = 0xA55A
        state = seed
        states = set()
        for _ in range(0xFFFF):
            states.add(state)
            state = lfsr16_step(state)

        self.assertEqual(len(states), 0xFFFF)
        self.assertNotIn(0, states)
        self.assertEqual(state, seed)

        smoke = (ROOT / "tests" / "smoke.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(smoke)
        rand8 = asm.split("_rand8:", 1)[1].split("_clear_nametable:", 1)[0]
        self.assertIn("LDA #$5A\nSTA _rng_state", asm)
        self.assertIn("LDA #$A5\nSTA _rng_state_hi", asm)
        self.assertIn("LDA _rng_state_hi", rand8)
        self.assertIn("EOR #$B4", rand8)
        self.assertIn("ROR A", rand8)
        self.assertNotIn("ADC _nmi_flag", rand8)

        tetris = (ROOT / "examples" / "tetris.c").read_text(encoding="utf-8")
        main_loop = tetris.split("while (1)", 1)[1]
        self.assertLess(
            main_loop.index("pad = read_pad();"), main_loop.index("rand8();")
        )
        refill = tetris.split("void refill_bag(void)", 1)[1].split(
            "unsigned char take_bag_piece", 1
        )[0]
        self.assertIn("bag[i] = i;", refill)
        self.assertIn("j = rand8() % (i + 1);", refill)
        self.assertIn("bag[i] = bag[j];", refill)
        self.assertIn("bag[j] = temp;", refill)

    def test_tetris_preview_is_flushed_atomically(self):
        source = (ROOT / "examples" / "tetris.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(source)

        draw_preview = asm.split("_draw_next_preview:", 1)[1].split(
            "_spawn_piece:", 1
        )[0]
        preview_writer = asm.split("_ppu_write_preview:", 1)[1].split(
            "_ppu_write_board_half:", 1
        )[0]

        self.assertIn("JSR _build_next_preview", draw_preview)
        self.assertIn("JSR _wait_vblank", draw_preview)
        self.assertIn("JSR _ppu_write_preview", draw_preview)
        self.assertNotIn("JSR _ppu_put", draw_preview)
        self.assertEqual(preview_writer.count("STA $2007"), 16)
        self.assertEqual(preview_writer.count("STA $2006"), 8)

    def test_tetris_board_redraw_uses_vblank_quarters(self):
        source = (ROOT / "examples" / "tetris.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(source)

        draw_board = asm.split("_draw_board:", 1)[1].split(
            "_draw_score_values:", 1
        )[0]
        board_writer = asm.split("_ppu_write_board_half:", 1)[1].split(
            "_render_queue:", 1
        )[0]
        row_writer = board_writer.split("__ppu_write_board_row:", 1)[1]

        self.assertEqual(draw_board.count("JSR _wait_vblank"), 4)
        self.assertEqual(draw_board.count("JSR _ppu_write_board_half"), 4)
        self.assertNotIn("JSR _ppu_put", draw_board)
        self.assertNotIn("JSR __mul8", draw_board)
        self.assertEqual(board_writer.count("JSR __ppu_write_board_row"), 20)
        self.assertEqual(row_writer.count("STA $2007"), 10)

    def test_tetris_rotation_states_are_true_rotations(self):
        """Every state has to be the piece turned, never mirrored.

        The J and L tables used to hold a state that belonged to the mirrored
        piece, so rotating those two changed their shape mid-spin.
        """

        shapes = const_array(tetris_source(), "SHAPES")
        self.assertEqual(len(shapes), 112)

        names = ("I", "O", "T", "Z", "S", "J", "L")
        for piece, name in enumerate(names):
            spawn = shape_cells(shapes, piece, 0)
            self.assertEqual(len(spawn), 4, name)

            turns = set()
            cells = spawn
            for _ in range(4):
                turns.add(normalise(cells))
                cells = rotate_cw(cells)

            for rotation in range(4):
                state = shape_cells(shapes, piece, rotation)
                self.assertEqual(len(state), 4, f"{name} r{rotation}")
                self.assertIn(
                    normalise(state),
                    turns,
                    f"{name} r{rotation} is not a rotation of its spawn state",
                )

    def test_tetris_rotation_never_shifts_a_piece_off_its_pivot(self):
        """T, J and L turn about their centre cell; I, S and Z flip in place."""

        shapes = const_array(tetris_source(), "SHAPES")

        def turn_about_centre(cells):
            return frozenset((1 - (y - 1), 1 + (x - 1)) for x, y in cells)

        for piece in (2, 5, 6):
            for rotation in range(4):
                self.assertEqual(
                    shape_cells(shapes, piece, (rotation + 1) % 4),
                    turn_about_centre(shape_cells(shapes, piece, rotation)),
                    f"piece {piece} r{rotation} does not turn about (1,1)",
                )

        # Two-state pieces must land back exactly where they started, otherwise
        # repeated rotation would walk them across the well.
        for piece in (0, 1, 3, 4):
            for rotation in range(4):
                self.assertEqual(
                    shape_cells(shapes, piece, rotation),
                    shape_cells(shapes, piece, (rotation + 2) % 4),
                    f"piece {piece} drifts over a two-state cycle",
                )

        # The I piece flips about the centre of its 4x4 grid.
        self.assertEqual(
            shape_cells(shapes, 0, 1),
            frozenset((3 - y, x) for x, y in shape_cells(shapes, 0, 0)),
        )

        # Spawn states start at the left of the grid, so every piece appears in
        # board columns 3..6 from the shared spawn origin.
        for piece in range(7):
            columns = {x for x, _y in shape_cells(shapes, piece, 0)}
            self.assertLessEqual(max(columns), 3)

    def test_tetris_rotation_kicks_cover_two_columns(self):
        source = tetris_source()
        self.assertEqual(const_array(source, "KICKS"), [0, 255, 1, 254, 2])
        rotate = source.split("void try_rotate(", 1)[1].split("\n}", 1)[0]
        self.assertIn("nx = piece_x + KICKS[i];", rotate)
        self.assertIn("sfx_play(SFX_ROTATE);", rotate)

    def test_tetris_preview_shift_moves_three_wide_pieces_down(self):
        source = tetris_source()
        self.assertEqual(
            const_array(source, "PREVIEW_SHIFT"), [0, 0, 1, 1, 1, 1, 1]
        )
        build = source.split("void build_next_preview(", 1)[1].split("\n}", 1)[0]
        self.assertIn("preview_y = y + PREVIEW_SHIFT[next_piece];", build)

        shapes = const_array(source, "SHAPES")
        shift = const_array(source, "PREVIEW_SHIFT")
        for piece in range(7):
            rows = {y + shift[piece] for _x, y in shape_cells(shapes, piece, 0)}
            self.assertLessEqual(max(rows), 3, f"piece {piece} overflows the preview")

    def test_tetris_text_table_offsets_stay_inside_the_data(self):
        source = tetris_source()
        data = const_array(source, "TEXT_DATA")
        starts = const_array(source, "TEXT_START")
        lengths = const_array(source, "TEXT_LEN")

        self.assertEqual(len(starts), len(lengths))
        self.assertLessEqual(len(data), 256)
        cursor = 0
        for index, (start, length) in enumerate(zip(starts, lengths)):
            self.assertEqual(start, cursor, f"string {index} is not packed")
            self.assertLessEqual(start + length, len(data), index)
            cursor += length
        self.assertEqual(cursor, len(data))

        # The status column overwrites itself in place, so those strings must
        # all be exactly the eight tiles the panel is wide.
        self.assertTrue(all(length == 8 for length in lengths[:8]))

    def test_tetris_sfx_tables_are_in_range(self):
        source = tetris_source()
        start = const_array(source, "SFX_START")
        length = const_array(source, "SFX_LENGTH")
        ctrl = const_array(source, "SFX_CTRL")
        timer_lo = const_array(source, "SFX_TIMER_LO")
        timer_hi = const_array(source, "SFX_TIMER_HI")

        self.assertEqual(len(start), 16)
        self.assertEqual(len(length), 16)
        self.assertEqual(len(ctrl), len(timer_lo))
        self.assertEqual(len(ctrl), len(timer_hi))
        self.assertLessEqual(len(ctrl), 256)

        # Slot zero is the driver's "stop" request and must stay empty.
        self.assertEqual(length[0], 0)
        used = 0
        for slot in range(1, 16):
            if length[slot] == 0:
                continue
            used += 1
            self.assertLessEqual(start[slot] + length[slot], len(ctrl), slot)
        self.assertGreaterEqual(used, 8)

        # Constant volume with the length counter halted, so a step sustains
        # until the next one replaces it.
        for value in ctrl:
            self.assertEqual(value & 0x30, 0x30)
        for value in timer_hi:
            self.assertLessEqual(value, 7)

    def test_sfx_runtime_borrows_pulse_two_and_hands_it_back(self):
        asm = compile_c_to_asm(tetris_source())

        self.assertIn("_sfx_play:", asm)
        self.assertIn("_sfx_tick:", asm)

        nmi = asm.split("_nmi:", 1)[1].split("_irq:", 1)[0]
        self.assertIn("JSR _music_tick", nmi)
        self.assertIn("JSR _sfx_tick", nmi)
        # Effects run last so a triggered effect wins the frame it plays.
        self.assertLess(nmi.index("JSR _music_tick"), nmi.index("JSR _sfx_tick"))

        driver = asm.split("_sfx_play:", 1)[1].split("_ppu_write_preview:", 1)[0]
        for table in ("_SFX_START", "_SFX_LENGTH", "_SFX_CTRL", "_SFX_TIMER_LO", "_SFX_TIMER_HI"):
            self.assertRegex(driver, rf"LDA {table},X")
        # Effects own pulse 2 only; the song keeps pulse 1, triangle and noise.
        self.assertIn("STA $4004", driver)
        self.assertIn("STA $4006", driver)
        self.assertIn("STA $4007", driver)
        for register in ("$4000", "$4002", "$4003", "$4008", "$400C", "$400F"):
            self.assertNotIn(f"STA {register}", driver)

        release = driver.split("__sfx_release:", 1)[1]
        self.assertIn("LDA #$30\nSTA $4004", release)
        self.assertIn("LDA #$FF\nSTA __music_last_pulse2", release)

    def test_sfx_runtime_requires_its_tables(self):
        source = """
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void sfx_play(unsigned char effect);

void main(void)
{
    sfx_play(1);
    while (1) { }
}
"""
        with self.assertRaises(Exception) as caught:
            compile_c_to_asm(source)
        self.assertIn("SFX_START", str(caught.exception))

    def test_sfx_runtime_rejects_mismatched_frame_tables(self):
        source = """
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void sfx_play(unsigned char effect);

const unsigned char SFX_START[16] = { 0 };
const unsigned char SFX_LENGTH[16] = { 0 };
const unsigned char SFX_CTRL[2] = { 48, 48 };
const unsigned char SFX_TIMER_LO[3] = { 1, 2, 3 };
const unsigned char SFX_TIMER_HI[2] = { 0, 0 };

void main(void)
{
    sfx_play(1);
    while (1) { }
}
"""
        with self.assertRaises(Exception) as caught:
            compile_c_to_asm(source)
        self.assertIn("same length", str(caught.exception))

    def test_tetris_level_select_seeds_the_starting_level(self):
        source = tetris_source()

        self.assertIn("#define MAX_LEVEL_PICK 19", source)
        start = source.split("void start_game(void)", 1)[1].split("\n}", 1)[0]
        self.assertIn("clear_score();", start)
        self.assertIn("level = start_level;", start)
        # The level has to be seeded after clear_score(), which zeroes it.
        self.assertLess(start.index("clear_score();"), start.index("level = start_level;"))

        title = source.split("void tick_title(void)", 1)[1].split("\n}\n", 1)[0]
        for button in ("PAD_LEFT", "PAD_RIGHT", "PAD_UP", "PAD_DOWN", "PAD_START"):
            self.assertIn(button, title)
        self.assertIn("start_game();", title)
        self.assertIn("sfx_play(SFX_MENU);", title)

    def test_tetris_high_score_table_records_a_name(self):
        source = tetris_source()

        self.assertIn("unsigned char hi_name[HI_NAME_SIZE];", source)
        self.assertIn("unsigned char hi_score[HI_SCORE_SIZE];", source)
        self.assertIn("unsigned char entry_name[NAME_LEN];", source)
        self.assertIn("#define HI_COUNT 3", source)
        self.assertIn("#define NAME_LEN 3", source)
        self.assertEqual(len(const_array(source, "DEFAULT_NAMES")), 9)
        self.assertEqual(len(const_array(source, "DEFAULT_SCORES")), 18)

        # Seeded names are letter indices, 0 for blank and 1..26 for A..Z.
        for value in const_array(source, "DEFAULT_NAMES"):
            self.assertTrue(0 <= value <= 26)
        for value in const_array(source, "DEFAULT_SCORES"):
            self.assertTrue(0 <= value <= 9)

        # The seeded table has to be sorted, otherwise find_rank() would place
        # a new score above an entry that already beats it.
        scores = const_array(source, "DEFAULT_SCORES")
        entries = [scores[base : base + 6][::-1] for base in (0, 6, 12)]
        self.assertEqual(entries, sorted(entries, reverse=True))

        beats = source.split("unsigned char score_beats(", 1)[1].split("\n}", 1)[0]
        self.assertIn("if (score_digits[i] > hi_score[base + i]) {", beats)
        self.assertIn("if (score_digits[i] < hi_score[base + i]) {", beats)

        insert = source.split("void insert_high_score(void)", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hi_name[(i * NAME_LEN) + j] = hi_name[((i - 1) * NAME_LEN) + j];", insert)
        self.assertIn("hi_score[(entry_rank * 6) + j] = score_digits[j];", insert)

        over = source.split("void tick_gameover(void)", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("entry_rank = find_rank();", over)
        self.assertIn("show_name_entry();", over)
        self.assertIn("show_title();", over)

    def test_tetris_status_and_flash_draws_respect_the_vblank_budget(self):
        source = tetris_source()

        # Each helper that draws while rendering is on splits its writes across
        # vblanks; more than about eight tiles will not fit in one.
        status = source.split("void draw_status_line(", 1)[1].split("\n}", 1)[0]
        self.assertEqual(status.count("wait_vblank();"), 2)
        self.assertIn("while (i < 4) {", status)
        self.assertIn("while (i < 8) {", status)

        flash = source.split("void flash_row(", 1)[1].split("\n}", 1)[0]
        self.assertEqual(flash.count("wait_vblank();"), 2)
        self.assertIn("while (x < 5) {", flash)
        self.assertIn("while (x < BOARD_W) {", flash)

        letters = source.split("void draw_entry_letters(void)", 1)[1].split("\n}", 1)[0]
        self.assertEqual(letters.count("wait_vblank();"), 2)

    def test_chr_contains_menu_glyphs(self):
        chr_rom = make_chr()

        # Arrows, caret and name slot replace filler tiles 88..91.
        filler = {}
        for tile in range(88, 92):
            color = ((tile - 1) % 3) + 1
            filler[tile] = [[color] * 8 for _ in range(8)]
        for tile in range(88, 92):
            pixels = chr_tile_pixels(chr_rom, tile)
            self.assertNotEqual(pixels, filler[tile], tile)
            self.assertIn(0, {pixel for row in pixels for pixel in row}, tile)
            self.assertTrue(any(pixel for row in pixels for pixel in row), tile)

        # The two arrows are mirror images of one another.
        left = chr_tile_pixels(chr_rom, 88)
        right = chr_tile_pixels(chr_rom, 89)
        self.assertEqual(
            [sum(1 for p in row if p) for row in left],
            [sum(1 for p in row if p) for row in right],
        )

    def test_packager_rejects_wrong_bank_sizes(self):
        with self.assertRaises(Exception):
            make_ines(b"", make_chr())

    def test_chr_contains_scoreboard_font(self):
        chr_rom = make_chr()

        self.assertEqual(len(chr_rom), 0x2000)
        for tile in range(16, 54):
            tile_bytes = chr_rom[tile * 16 : (tile + 1) * 16]
            self.assertNotEqual(tile_bytes, bytes(16))

    def test_chr_uses_beveled_blocks_and_decorative_ui_tiles(self):
        chr_rom = make_chr()

        for tile in range(1, 8):
            pixels = chr_tile_pixels(chr_rom, tile)
            self.assertEqual(pixels[7], [0] * 8)
            self.assertEqual([row[7] for row in pixels], [0] * 8)
            self.assertEqual(pixels[0][:7], [3] * 7)
            self.assertEqual([pixels[row][0] for row in range(7)], [3] * 7)
            self.assertEqual(pixels[6][1:7], [1] * 6)
            self.assertEqual([pixels[row][6] for row in range(1, 7)], [1] * 6)
            self.assertIn(2, {pixel for row in pixels for pixel in row})

        # Font ink is palette index 3, which stays bright in every HUD palette.
        for tile in range(16, 54):
            colors = {
                pixel for row in chr_tile_pixels(chr_rom, tile) for pixel in row
            }
            self.assertLessEqual(colors, {0, 3})
            self.assertIn(3, colors)

        # Directional rails, sparkle/flash, and six 16x16 logo glyphs occupy 54..87.
        for tile in range(54, 88):
            self.assertNotEqual(
                chr_rom[tile * 16 : (tile + 1) * 16], bytes(16), tile
            )

    def test_runtime_loads_four_background_palettes_and_hides_sprites(self):
        source = (ROOT / "tests" / "smoke.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(source)
        assembler = Assembler()
        prg = assembler.assemble(asm)
        palette_address = assembler.symbols["_palette_data"]
        palette_offset = palette_address - 0x8000
        palette = prg[palette_offset : palette_offset + 32]
        expected_background = bytes(
            (
                0x0F,
                0x01,
                0x21,
                0x30,
                0x0F,
                0x06,
                0x16,
                0x30,
                0x0F,
                0x09,
                0x19,
                0x30,
                0x0F,
                0x04,
                0x24,
                0x30,
            )
        )
        self.assertEqual(palette, expected_background * 2)

        ppu_on = asm.split("_ppu_on:", 1)[1].split("_read_pad:", 1)[0]
        ppu_off = asm.split("_ppu_off:", 1)[1].split("_ppu_on:", 1)[0]
        nmi = asm.split("_nmi:", 1)[1].split("_irq:", 1)[0]
        self.assertIn("LDA #$0A\nSTA $2001", ppu_on)
        self.assertNotIn("#$1E", ppu_on)
        self.assertIn("STA __ppu_rendering", ppu_off)
        self.assertIn("LDA __ppu_rendering\nBEQ __nmi_scroll_done", nmi)


if __name__ == "__main__":
    unittest.main()
