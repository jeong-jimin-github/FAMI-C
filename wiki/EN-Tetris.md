# Tetris Example

The example game is `examples/tetris.c`.

## Build

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

## Controls

### Title screen

- Left / Right: change the starting level by one (0-19, wrapping)
- Up / Down: change the starting level by five
- Start: begin a game at the selected level

### Playing

- Left / Right: move (with delayed auto shift)
- Down: soft drop
- Up: hard drop
- A: rotate clockwise
- B: rotate counter-clockwise
- Start: pause/resume (the BGM stops with the game and picks up where it left off)

### Name entry

Reached after a game that beats one of the three best scores.

- Up / Down: change the highlighted letter (blank, A-Z)
- Left / Right, or A: move between the three letters
- Start: confirm and return to the title screen

## What It Demonstrates

- A polished NES interface with multiple palettes, beveled blocks, directional
  borders, framed HUD panels, and a large title logo
- ROM lookup tables for piece shapes and a fair randomized 7-bag
- A 16-bit LFSR advanced every frame so controller/input timing influences the
  piece sequence instead of every cold boot producing the same opening bag
- Board arrays and collision checks
- Rotation states that are true rotations about a fixed pivot: T, J and L cycle
  through four orientations, I, S and Z flip between two, and O never changes
- Wall kicks of one or two columns, lock delay, and line clearing with a flash
- A start-level picker and a three-entry best-player table with name entry
- Sound effects for movement, rotation, drops, locking, line clears, level ups,
  menus and game over, mixed over the running BGM
- NEXT preview, score, lines, levels, a TOP panel, and level-based gravity
- Title, playing, pause, game-over, and name-entry states
- Controller input
- vblank-safe PPU updates
- Native queued rendering for fast active-piece updates
- A four-channel 2A03 arrangement covering the MIDI's complete 4:26.127
  musical section. The source lasts 4:29.605 including its initial silence.

## Rotation Model

`SHAPES` stores four rows per rotation, one nibble per row, with the most
significant bit as column 0. Every state is the spawn state turned clockwise
about a fixed pivot, never mirrored, so a piece cannot change shape mid-spin
and rotating never nudges it off its pivot:

- T, J and L turn about the centre cell of their 3x3 box and use all four
  states.
- I, S and Z use the classic two-state cycle, so rotating twice returns the
  piece exactly where it started.
- O has a single state.

Rotation is attempted in place first, then one column left, one right, two
left, and two right. The two-column kicks are what let a vertical I leave
either wall.

## Sound Effects

`sfx_play(id)` drives the runtime effect player. Effects replay a run of
one-frame steps from `SFX_CTRL`, `SFX_TIMER_LO` and `SFX_TIMER_HI`, located by
`SFX_START` and `SFX_LENGTH`. They borrow pulse 2 from the song and hand the
channel back when they finish, so pulse 1, triangle and noise keep playing the
BGM uninterrupted. See [C Language](EN-C-Language) for the table contract.

## Best Scores

Three entries are kept in RAM, each with a three-letter name and a six-digit
score, seeded with `FMC 010000`, `NES 005000` and `TOP 002500`. There is no
battery-backed save, so the table resets on a power cycle. The leading score is
mirrored in the in-game TOP panel.

## Automated Coverage

The Mesen 2.2.1 headless runner is configured to exercise rendering, falling,
movement, rotation, drops, locking, spawning, line clearing, NEXT updates,
the TOP panel, the status column, pause/resume, music sequencing, and PPU
timing across the whole gameplay phase.
