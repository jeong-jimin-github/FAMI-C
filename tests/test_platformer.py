"""Checks for the platformer example and the tiles it draws itself with."""

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
    build_rom,
    compile_c_to_asm,
    make_chr,
)


ROOT = Path(__file__).resolve().parents[1]


def platformer_source():
    return (ROOT / "examples" / "platformer.c").read_text(encoding="utf-8")


def macros(source):
    return {
        match.group(1): int(match.group(2))
        for match in re.finditer(r"^#define (\w+) (\d+)$", source, re.M)
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
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.S)
    values = []
    for item in body.split(","):
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
        if cx < 0 or cx >= self.w or cy >= self.h:
            return 0
        return self.cells[cy * self.w + cx]

    def solid(self, cx, cy):
        if cx < 0 or cx >= self.w:
            return 1
        if cy == 0:
            return 1
        if cy >= self.h:
            return 0
        return self.solid_kinds[self.cells[cy * self.w + cx]]


def reachable_targets(source, names, index):
    """Replay the game's own physics and report which prizes can be reached.

    The state is exactly what tick_play() carries - cell, vertical mode, and
    every step timer - so a cell counted here is a cell the hero can really
    stand in.  Only the d-pad and A are offered, never the B run modifier, so
    the answer stays a subset of what a player can do.  Patrols are left out:
    they never occupy a cell permanently, they only have to be timed around.

    The frontier is ordered by distance to the nearest prize still missing,
    which finds the route quickly without ever skipping a state: if a prize
    were unreachable the search would still drain the whole state space
    before saying so.
    """

    stage = Stage(source, names, index)
    jump_delay = const_array(source, "JUMP_DELAY", names)
    fall_delay = const_array(source, "FALL_DELAY", names)
    walk_delay = names["WALK_DELAY"]
    gem, spike, goal = names["C_GEM"], names["C_SPIKE"], names["C_GOAL"]

    wanted = {
        (i % stage.w, i // stage.w)
        for i, kind in enumerate(stage.cells)
        if kind in (gem, goal)
    }
    found = set()

    # px:4 py:4 vstate:2 jump_phase:2 jump_timer:4 fall_phase:3 fall_timer:4
    # walk_timer:4 a_held:1
    start = stage.spawn[0] | (stage.spawn[1] << 4)
    seen = {start}
    order = 0
    frontier = [(0, 0, start)]

    while frontier and wanted - found:
        _, _, packed = heapq.heappop(frontier)
        px = packed & 15
        py = (packed >> 4) & 15
        vstate = (packed >> 8) & 3
        jump_phase = (packed >> 10) & 3
        jump_timer = (packed >> 12) & 15
        fall_phase = (packed >> 16) & 7
        fall_timer = (packed >> 19) & 15
        walk_timer = (packed >> 23) & 15
        a_held = (packed >> 27) & 1

        for action in (0, 1, 2, 4, 5, 6):  # 1 right, 2 left, 4 jump
            x, y = px, py
            mode, phase, timer = vstate, jump_phase, jump_timer
            drop_phase, drop_timer, walk = fall_phase, fall_timer, walk_timer
            jump_held = action & 4
            stop = False

            if mode == 0 and jump_held and not a_held:
                mode, phase, timer = 1, 0, jump_delay[0]

            move = action & 3
            if move:
                if walk:
                    walk -= 1
                else:
                    walk = walk_delay
                    nx = x + 1 if move == 1 else x - 1
                    if not stage.solid(nx, y):
                        x = nx
                        kind = stage.kind(x, y)
                        if kind == spike:
                            stop = True
                        else:
                            if kind in (gem, goal):
                                found.add((x, y))
                            if kind == goal:
                                stop = True
                            elif mode == 0 and not stage.solid(x, y + 1):
                                mode, drop_phase, drop_timer = 2, 0, fall_delay[0]
                            elif mode == 2 and stage.solid(x, y + 1):
                                mode = 0
            else:
                walk = 0

            if not stop:
                if mode == 1:
                    if phase and not jump_held:
                        mode, drop_phase, drop_timer = 2, 0, fall_delay[0]
                    elif timer:
                        timer -= 1
                    elif stage.solid(x, y - 1):
                        mode, drop_phase, drop_timer = 2, 0, fall_delay[0]
                    else:
                        y -= 1
                        phase += 1
                        if jump_delay[phase] == 0:
                            mode, drop_phase, drop_timer = 2, 0, fall_delay[0]
                        else:
                            timer = jump_delay[phase]
                        kind = stage.kind(x, y)
                        if kind in (gem, goal):
                            found.add((x, y))
                        stop = kind in (spike, goal)
                elif mode == 2:
                    if drop_timer:
                        drop_timer -= 1
                    elif stage.solid(x, y + 1):
                        mode = 0
                    else:
                        y += 1
                        kind = stage.kind(x, y)
                        if kind in (gem, goal):
                            found.add((x, y))
                        stop = y >= stage.h or kind in (spike, goal)
                        if drop_phase < len(fall_delay) - 1:
                            drop_phase += 1
                        drop_timer = fall_delay[drop_phase]
                elif not stage.solid(x, y + 1):
                    mode, drop_phase, drop_timer = 2, 0, fall_delay[0]

            if stop:
                continue
            packed_next = (
                x
                | (y << 4)
                | (mode << 8)
                | (phase << 10)
                | (timer << 12)
                | (drop_phase << 16)
                | (drop_timer << 19)
                | (walk << 23)
                | ((1 if jump_held else 0) << 27)
            )
            if packed_next in seen:
                continue
            seen.add(packed_next)
            missing = wanted - found
            distance = (
                min(abs(x - gx) + abs(y - gy) for gx, gy in missing) if missing else 0
            )
            order += 1
            heapq.heappush(frontier, (distance, order, packed_next))

    return wanted, found


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
                wanted, found = reachable_targets(self.source, self.names, index)
                self.assertTrue(wanted, "a stage needs an exit to reach")
                self.assertEqual(
                    sorted(wanted - found),
                    [],
                    "these cells cannot be reached with the game's own physics",
                )

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

    def test_hero_and_patrol_art_is_palette_independent(self):
        """Colour 3 is $30 in every background palette, so actors stay white."""

        chr_rom = make_chr()
        for name in ("HERO_IDLE_R", "HERO_IDLE_L", "HERO_WALK_R", "HERO_WALK_L",
                     "HERO_JUMP_R", "HERO_JUMP_L", "FOE_TILE_A", "FOE_TILE_B"):
            base = self.names[name]
            colours = {
                pixel for row in metatile_pixels(chr_rom, base) for pixel in row
            }
            self.assertLessEqual(colours, {0, 3}, name)
            self.assertIn(3, colours, name)

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
        """One frame may queue a patrol, four stomps, the hero and the HUD."""

        per_vblank = self.names["TILES_PER_VBLANK"]
        self.assertLessEqual(per_vblank, 8)
        worst = 4 + 4 * self.names["MAX_FOES"] + 8 + 8
        self.assertGreaterEqual(self.names["QUEUE_MAX"], worst)


if __name__ == "__main__":
    unittest.main()
