"""Checks for the platformer example, its tiles, and the sprite runtime."""

import heapq
import re
import tempfile
import unittest
from pathlib import Path

from famic import (
    CHR_SIZE,
    PRG_BANKS,
    PRG_SIZE,
    PRG_VECTORS,
    Assembler,
    CompileError,
    build_rom,
    compile_c_to_asm,
    make_chr,
)


ROOT = Path(__file__).resolve().parents[1]


def platformer_source():
    return (ROOT / "examples" / "platformer.c").read_text(encoding="utf-8")


def strip_comments(source):
    return re.sub(r"/\*.*?\*/", "", source, flags=re.S)


def macros(source):
    return {
        match.group(1): int(match.group(2))
        for match in re.finditer(
            r"^#define (\w+) (\d+)\s*$", strip_comments(source), re.M
        )
    }


def const_array(source, name, names):
    """Return `const unsigned char name[...]`, resolving #define references."""

    match = re.search(
        r"const unsigned char " + re.escape(name) + r"\[\d*\]\s*=\s*\{(.*?)\}\s*;",
        source,
        re.S,
    )
    if match is None:
        raise AssertionError(f"{name} is missing from the source")
    values = []
    for item in strip_comments(match.group(1)).split(","):
        item = item.strip()
        if not item:
            continue
        expr = re.sub(r"[A-Za-z_]\w*", lambda m: str(names[m.group(0)]), item)
        values.append(eval(expr, {"__builtins__": {}}) & 0xFF)  # noqa: S307
    return values


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


def metatile_pixels(chr_rom, base):
    """Re-join the four tiles of a metatile into one 16x16 drawing."""

    rows = []
    for half_row in range(2):
        left = chr_tile_pixels(chr_rom, base + half_row * 2)
        right = chr_tile_pixels(chr_rom, base + half_row * 2 + 1)
        for row in range(8):
            rows.append(left[row] + right[row])
    return rows


class Stage:
    """The pieces of one stage the movement model needs."""

    def __init__(self, source, names, index):
        self.w = names["GRID_W"]
        self.h = names["GRID_H"]
        self.cell = names["CELL_PX"]
        self.solid_kinds = const_array(source, "CELL_SOLID", names)
        raw = const_array(source, f"LEVEL{index + 1}", names)
        self.foes = [
            (i % self.w, i // self.w)
            for i, kind in enumerate(raw)
            if kind == names["C_FOE"]
        ]
        # Patrol markers are replaced with open air when the stage loads.
        self.cells = [0 if kind == names["C_FOE"] else kind for kind in raw]
        self.spawn = (
            const_array(source, "SPAWN_X", names)[index],
            const_array(source, "SPAWN_Y", names)[index],
        )

    def kind(self, cx, cy):
        if cx >= self.w or cy >= self.h:
            return 0
        return self.cells[cy * self.w + cx]

    def solid(self, cx, cy):
        if cx >= self.w:
            return 1
        if cy == 0:
            return 1
        if cy >= self.h:
            return 0
        return self.solid_kinds[self.cells[cy * self.w + cx]]


def reachable_targets(source, names, index):
    """Replay the game's own pixel physics and report the prizes it can touch.

    Every state carries exactly what tick_play() carries - pixel position,
    both subpixel accumulators and the biased vertical speed - so a cell
    touched here is a cell the hero really can touch.  Duplicate states are
    dropped on a coarser key than the full state, which can only make the
    search miss routes, never invent one; the frontier is ordered by distance
    to the nearest prize still missing so the real routes turn up first.

    Patrols are left out: they never occupy a cell permanently, they only
    have to be timed around.
    """

    stage = Stage(source, names, index)
    cell = names["CELL_PX"]
    sub = names["SUB_PX"]
    box_l, box_r, box_b = names["BOX_L"], names["BOX_R"], names["BOX_B"]
    gem, spike, goal = names["C_GEM"], names["C_SPIKE"], names["C_GOAL"]

    def blocked(x, y):
        left, right = (x + box_l) // cell, (x + box_r) // cell
        top, bottom = y // cell, (y + box_b) // cell
        return (
            stage.solid(left, top)
            or stage.solid(right, top)
            or stage.solid(left, bottom)
            or stage.solid(right, bottom)
        )

    targets = {
        (i % stage.w, i // stage.w)
        for i, kind in enumerate(stage.cells)
        if kind in (gem, goal)
    }
    found = set()

    def touch(x, y):
        """Collect anything the hitbox overlaps; report whether play stops."""

        left, right = (x + box_l) // cell, (x + box_r) // cell
        top, bottom = y // cell, (y + box_b) // cell
        stop = False
        for cx, cy in ((left, top), (right, top), (left, bottom), (right, bottom)):
            kind = stage.kind(cx, cy)
            if kind in (gem, goal):
                found.add((cx, cy))
                if kind == goal:
                    stop = True
            elif kind == spike:
                stop = True
        return stop

    # right 1, left 2, jump 4, run 8
    actions = (0, 1, 2, 4, 5, 6, 9, 10, 13, 14)
    start = (stage.spawn[0] * cell, stage.spawn[1] * cell, 0, 0, names["VY_REST"], 0)
    seen = {(start[0], start[1], start[4] // 6, 0)}
    frontier = [(0, 0, start)]
    order = 0

    while frontier and targets - found:
        _, _, (hx, hy, hxs, hys, vy, a_held) = heapq.heappop(frontier)
        for action in actions:
            x, y, xs, ys, speed = hx, hy, hxs, hys, vy
            jump = action & 4

            grounded = 0 if y >= names["PIT_Y"] else blocked(x, y + 1)
            if grounded and jump and not a_held:
                speed = names["VY_JUMP"]
            elif grounded:
                speed = names["VY_REST"]
            if not jump and speed < names["VY_CUT"]:
                speed = names["VY_CUT"]
            if speed < names["VY_MAX_FALL"]:
                speed = min(speed + names["GRAVITY"], names["VY_MAX_FALL"])

            move = action & 3
            if move:
                xs += names["RUN_SPEED"] if action & 8 else names["WALK_SPEED"]
                steps, xs = divmod(xs, sub)
                for _ in range(steps):
                    if move == 1:
                        if x >= names["MAX_X"] or blocked(x + 1, y):
                            xs = 0
                            break
                        x += 1
                    else:
                        if x == 0 or blocked(x - 1, y):
                            xs = 0
                            break
                        x -= 1
            else:
                xs = 0

            rising = speed < names["VY_ZERO"]
            ys += (names["VY_ZERO"] - speed) if rising else (speed - names["VY_ZERO"])
            steps, ys = divmod(ys, sub)
            fell_out = False
            for _ in range(steps):
                if rising:
                    if blocked(x, y - 1):
                        speed, ys = names["VY_ZERO"], 0
                        break
                    y -= 1
                else:
                    if blocked(x, y + 1):
                        speed, ys = names["VY_ZERO"], 0
                        break
                    y += 1
                    if y >= names["PIT_Y"]:
                        fell_out = True
                        break

            if fell_out or touch(x, y):
                continue
            key = (x, y, speed // 6, 1 if jump else 0)
            if key in seen:
                continue
            seen.add(key)
            missing = targets - found
            distance = (
                min(
                    abs(x - gx * cell) + abs(y - gy * cell)
                    for gx, gy in missing
                )
                if missing
                else 0
            )
            order += 1
            heapq.heappush(frontier, (distance, order, (x, y, xs, ys, speed, 1 if jump else 0)))

    return targets, found


SPRITE_PROGRAM = """
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void oam_reset(void);
extern void oam_sprite(unsigned char x, unsigned char y, unsigned char tile,
                       unsigned char attr);

void main(void)
{
    oam_reset();
    oam_sprite(64, 100, 92, 0);
}
"""


class SpriteRuntimeTests(unittest.TestCase):
    def test_shadow_oam_is_page_aligned_and_dma_reads_that_page(self):
        assembler = Assembler()
        asm = compile_c_to_asm(SPRITE_PROGRAM)
        assembler.assemble(asm)
        oam = assembler.symbols["__oam"]
        self.assertEqual(oam, 0x0200, "OAM DMA can only read a whole page")
        self.assertEqual(oam & 0xFF, 0)

        lines = [line.strip() for line in asm.splitlines()]
        nmi = lines[lines.index("_nmi:") :]
        nmi = nmi[: nmi.index("RTI")]
        self.assertIn("STA $2003", nmi)
        self.assertIn("STA $4014", nmi)
        # The value stored to $4014 is the high byte of the shadow OAM.
        page = nmi[nmi.index("STA $4014") - 1]
        self.assertEqual(page, f"LDA #${oam >> 8:02X}")

    def test_sprite_runtime_enables_sprites_in_the_mask(self):
        asm = compile_c_to_asm(SPRITE_PROGRAM)
        self.assertIn("LDA #$1E", asm)
        self.assertNotIn("LDA #$0A", asm)

    def test_programs_without_sprites_keep_the_background_only_mask(self):
        source = (ROOT / "tests" / "smoke.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(source)
        self.assertIn("LDA #$0A", asm)
        self.assertNotIn("STA $4014", asm)
        self.assertNotIn("__oam", asm)

    def test_oam_sprite_needs_the_sprite_runtime(self):
        lonely = SPRITE_PROGRAM.replace("extern void oam_reset(void);\n", "").replace(
            "    oam_reset();\n", ""
        )
        with self.assertRaises(CompileError):
            compile_c_to_asm(lonely)

    def test_oam_reset_needs_oam_sprite(self):
        lonely = re.sub(
            r"extern void oam_sprite.*?;\n", "", SPRITE_PROGRAM, flags=re.S
        ).replace("    oam_sprite(64, 100, 92, 0);\n", "")
        with self.assertRaises(CompileError):
            compile_c_to_asm(lonely)


class PlatformerTests(unittest.TestCase):
    def setUp(self):
        self.source = platformer_source()
        self.names = macros(self.source)

    def stages(self):
        return [Stage(self.source, self.names, index) for index in range(4)]

    def test_platformer_builds_mapper0_ines_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "platformer.nes"
            build_rom(ROOT / "examples" / "platformer.c", out, None)
            rom = out.read_bytes()

        self.assertEqual(rom[:4], b"NES\x1a")
        self.assertEqual(rom[4], PRG_BANKS)
        self.assertEqual(rom[5], 1)
        self.assertEqual(rom[6], 0)
        self.assertEqual(len(rom), 16 + PRG_SIZE + CHR_SIZE)

        vectors = rom[16 + PRG_SIZE - 6 : 16 + PRG_SIZE]
        self.assertEqual(len(vectors), 6)
        for offset in (0, 2, 4):
            address = vectors[offset] | (vectors[offset + 1] << 8)
            self.assertGreaterEqual(address, 0x8000)
            self.assertLess(address, PRG_VECTORS)

    def test_platformer_ram_stays_out_of_the_stack(self):
        assembler = Assembler()
        assembler.assemble(compile_c_to_asm(self.source))
        for name, address in assembler.symbols.items():
            if address < 0x0800:
                self.assertGreaterEqual(address, 0x0200, name)
        self.assertLessEqual(assembler.ram_pc, 0x0800)

    def test_stage_maps_are_well_formed(self):
        size = self.names["LEVEL_SIZE"]
        kinds = len(const_array(self.source, "CELL_SOLID", self.names))
        for index, stage in enumerate(self.stages(), start=1):
            with self.subTest(stage=index):
                self.assertEqual(len(stage.cells), size)
                self.assertEqual(size, stage.w * stage.h)
                self.assertTrue(all(0 <= kind < kinds for kind in stage.cells))
                # Cell row 0 is the status bar and is never part of the stage.
                self.assertEqual(stage.cells[: stage.w], [0] * stage.w)
                goals = stage.cells.count(self.names["C_GOAL"])
                self.assertEqual(goals, 1, "a stage needs exactly one exit")
                self.assertLessEqual(len(stage.foes), self.names["MAX_FOES"])

    def test_spawn_and_patrols_start_on_solid_ground(self):
        for index, stage in enumerate(self.stages(), start=1):
            with self.subTest(stage=index):
                x, y = stage.spawn
                self.assertEqual(stage.kind(x, y), 0, "the hero spawns in open air")
                self.assertTrue(stage.solid(x, y + 1), "the hero spawns on a floor")
                self.assertFalse(
                    any(foe == stage.spawn for foe in stage.foes),
                    "a patrol may not start on top of the hero",
                )
                for foe in stage.foes:
                    self.assertEqual(stage.kind(*foe), 0)
                    self.assertTrue(
                        stage.solid(foe[0], foe[1] + 1),
                        f"patrol at {foe} has no floor",
                    )

    def test_prizes_and_hazards_are_not_solid(self):
        solid = const_array(self.source, "CELL_SOLID", self.names)
        for name in ("C_EMPTY", "C_GEM", "C_SPIKE", "C_GOAL", "C_FOE"):
            self.assertEqual(solid[self.names[name]], 0, name)
        for name in ("C_DIRT", "C_GRASS", "C_BRICK"):
            self.assertEqual(solid[self.names[name]], 1, name)

    def test_every_stage_exit_and_gem_can_be_reached(self):
        for index in range(4):
            with self.subTest(stage=index + 1):
                targets, found = reachable_targets(self.source, self.names, index)
                self.assertTrue(targets, "a stage needs an exit to reach")
                self.assertEqual(
                    sorted(targets - found),
                    [],
                    "these cells cannot be reached with the game's own physics",
                )

    def test_biased_vertical_speeds_agree_with_the_motion_constants(self):
        names = self.names
        self.assertEqual(names["VY_REST"], names["VY_ZERO"])
        self.assertEqual(names["VY_JUMP"], names["VY_ZERO"] - names["JUMP_SPEED"])
        self.assertEqual(names["VY_CUT"], names["VY_ZERO"] - names["JUMP_CUT"])
        self.assertEqual(names["VY_MAX_FALL"], names["VY_ZERO"] + names["MAX_FALL"])
        # Every biased speed has to survive in one unsigned byte.
        self.assertGreater(names["VY_JUMP"], 0)
        self.assertLess(names["VY_MAX_FALL"], 256)
        self.assertLess(names["JUMP_CUT"], names["JUMP_SPEED"])

    def test_a_full_jump_clears_three_cells(self):
        """The stages are laid out around a jump of three cells of rise."""

        names = self.names
        speed = names["JUMP_SPEED"]
        rise = 0
        while speed > 0:
            rise += speed
            speed -= names["GRAVITY"]
        rise = rise // names["SUB_PX"]
        self.assertGreaterEqual(rise, 3 * names["CELL_PX"])
        self.assertLess(rise, 5 * names["CELL_PX"], "a jump this high trivialises the stages")

    def test_pixel_maths_never_wraps_a_byte(self):
        names = self.names
        # The rightmost sprite column still fits a 16 pixel wide actor.
        self.assertEqual(names["MAX_X"] + names["CELL_PX"], 256)
        # Collision probes read PIXEL_CELL[y + BOX_B] and [x + BOX_R].
        self.assertLess(names["PIT_Y"] + names["BOX_B"], 256)
        self.assertLess(names["MAX_X"] + names["BOX_R"], 256)
        # The hitbox is narrower than a cell, so a one cell gap is passable.
        self.assertLess(names["BOX_R"] - names["BOX_L"] + 1, names["CELL_PX"])
        self.assertEqual(len(const_array(self.source, "PIXEL_CELL", self.names)), 256)

    def test_pixel_cell_table_is_a_divide_by_sixteen(self):
        table = const_array(self.source, "PIXEL_CELL", self.names)
        cell = self.names["CELL_PX"]
        self.assertEqual(table, [value // cell for value in range(256)])

    def test_cell_tables_draw_real_tiles(self):
        chr_rom = make_chr()
        empty = self.names["C_EMPTY"]
        foe = self.names["C_FOE"]
        tables = [
            const_array(self.source, name, self.names)
            for name in ("CELL_TL", "CELL_TR", "CELL_BL", "CELL_BR")
        ]
        palettes = const_array(self.source, "CELL_PAL", self.names)
        kinds = len(const_array(self.source, "CELL_SOLID", self.names))
        for table in tables + [palettes]:
            self.assertEqual(len(table), kinds)
        for kind in range(kinds):
            tiles = [table[kind] for table in tables]
            if kind in (empty, foe):
                self.assertEqual(tiles, [0, 0, 0, 0], kind)
                continue
            # Spikes only fill the lower half of their cell, so it is the
            # whole cell that has to carry ink rather than every tile.
            ink = any(
                chr_rom[tile * 16 : (tile + 1) * 16] != bytes(16) for tile in tiles
            )
            self.assertTrue(ink, f"cell kind {kind} draws nothing")
        for palette in palettes:
            self.assertLess(palette, 4)

    def test_actor_art_is_shaded_and_keeps_a_transparent_edge(self):
        """Actors are sprites now, so they carry their own shaded palette."""

        chr_rom = make_chr()
        for name in ("HERO_IDLE_R", "HERO_IDLE_L", "HERO_WALK_R", "HERO_WALK_L",
                     "HERO_JUMP_R", "HERO_JUMP_L", "FOE_TILE_A", "FOE_TILE_B"):
            base = self.names[name]
            colours = {
                pixel for row in metatile_pixels(chr_rom, base) for pixel in row
            }
            # Colour 0 is transparent for a sprite, so it has to be present.
            self.assertIn(0, colours, name)
            self.assertEqual(colours, {0, 1, 2, 3}, name)

    def test_hero_poses_face_both_ways(self):
        chr_rom = make_chr()
        for right, left in (
            ("HERO_IDLE_R", "HERO_IDLE_L"),
            ("HERO_WALK_R", "HERO_WALK_L"),
            ("HERO_JUMP_R", "HERO_JUMP_L"),
        ):
            facing = metatile_pixels(chr_rom, self.names[right])
            away = metatile_pixels(chr_rom, self.names[left])
            self.assertEqual([row[::-1] for row in facing], away, right)

    def test_terrain_tiles_are_distinct_and_filled(self):
        chr_rom = make_chr()
        seen = {}
        for name in ("DIRT_TILE", "GRASS_TILE", "BRICK_TILE"):
            tile = self.names[name]
            pixels = chr_tile_pixels(chr_rom, tile)
            colours = {pixel for row in pixels for pixel in row}
            # Terrain fills its cell edge to edge so platforms have no seams.
            self.assertNotIn(0, colours, name)
            key = bytes(chr_rom[tile * 16 : (tile + 1) * 16])
            self.assertNotIn(key, seen, f"{name} duplicates {seen.get(key)}")
            seen[key] = name

    def test_text_table_offsets_stay_inside_the_data(self):
        data = const_array(self.source, "TEXT_DATA", self.names)
        starts = const_array(self.source, "TEXT_START", self.names)
        lengths = const_array(self.source, "TEXT_LEN", self.names)
        self.assertEqual(len(starts), len(lengths))
        for start, length in zip(starts, lengths):
            self.assertLessEqual(start + length, len(data))
        for tile in data:
            # Blank, digits, letters, '-' and ':' are the only glyphs drawn.
            self.assertTrue(tile == 0 or 16 <= tile <= 53, tile)

    def test_sfx_tables_are_in_range(self):
        starts = const_array(self.source, "SFX_START", self.names)
        lengths = const_array(self.source, "SFX_LENGTH", self.names)
        ctrl = const_array(self.source, "SFX_CTRL", self.names)
        lo = const_array(self.source, "SFX_TIMER_LO", self.names)
        hi = const_array(self.source, "SFX_TIMER_HI", self.names)
        self.assertEqual(len(starts), 16)
        self.assertEqual(len(lengths), 16)
        self.assertEqual(len(ctrl), len(lo))
        self.assertEqual(len(ctrl), len(hi))
        self.assertEqual(lengths[0], 0, "slot 0 is reserved as 'stop'")
        for start, length in zip(starts, lengths):
            self.assertLessEqual(start + length, len(ctrl))
        for value in hi:
            # Only the low three bits reach $4007.
            self.assertLess(value, 8)
        used = {
            self.names[name]
            for name in ("SFX_JUMP", "SFX_GEM", "SFX_STOMP", "SFX_HURT",
                         "SFX_CLEAR", "SFX_OVER", "SFX_LAND")
        }
        for slot in used:
            self.assertGreater(lengths[slot], 0, slot)

    def test_vblank_budget_covers_the_worst_frame(self):
        """Actors are sprites, so only a taken gem and the HUD are redrawn."""

        self.assertLessEqual(self.names["TILES_PER_VBLANK"], 6)
        worst = 4 + 8
        self.assertGreaterEqual(self.names["QUEUE_MAX"], worst)

    def test_every_actor_row_stays_inside_the_sprite_limit(self):
        """Four 16x16 actors abreast is eight sprites, the per-line maximum."""

        for index, stage in enumerate(self.stages(), start=1):
            with self.subTest(stage=index):
                rows = {}
                for _cx, cy in stage.foes:
                    rows[cy] = rows.get(cy, 0) + 1
                for cy, count in rows.items():
                    # The hero can always join the busiest row.
                    self.assertLessEqual(count + 1, 4, f"row {cy} has {count} patrols")


if __name__ == "__main__":
    unittest.main()
