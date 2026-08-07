# Platformer Example

The example game is `examples/platformer.c`.

## Build

```powershell
python .\famic.py build .\examples\platformer.c -o .\build\platformer.nes --asm .\build\platformer.asm
```

## Controls

- Left / Right: walk
- B (held): run
- A: jump; releasing A during the rise cuts the jump short
- Start: begin a game from the title screen, or return to the title after a
  game over or an all-clear

## The Metatile Grid

The FAMI-C runtime draws backgrounds only - it never enables sprites - so the
platformer moves whole cells instead of pixels. The screen is 16 cells wide
and 15 cells tall, each cell being 2x2 tiles:

- Cell row 0 is the status bar; rows 1-14 are the stage.
- One cell is the unit of collision, so a stage map is 240 bytes and fits the
  8-bit array index the code generator emits.
- One cell is also one attribute quadrant, so every cell picks its own
  background palette without any extra bookkeeping.

Attribute bytes live at nametable rows 30 and 31 as far as `ppu_put` is
concerned, because its address maths is `$2000 + y * 32 + x`. The same helper
that writes tiles therefore writes palette selects too.

Cell kinds are open air, dirt, grass, brick, gem, spikes, exit door, and a
patrol spawn marker that becomes open air when the stage loads.

## Staying Readable In Any Palette

Colour 3 is `$30` in all four background palettes, which is why the built-in
font is drawn in colour 3 alone. The hero and the patrols use the same trick:
their art is colour 3 and transparency only, so they stay the same bright
white over green earth, red brick or purple treasure.

Terrain uses colours 1 and 2 and takes its hue from the attribute map: earth
is green, brick and spikes are red, gems and the exit are purple.

## Physics

Motion is frame-timed rather than sub-pixel, and the tables at the top of the
source are the entire model:

- `WALK_DELAY` is twelve frames per cell, `RUN_DELAY` eight while B is held.
- `JUMP_DELAY` rises three cells over sixteen frames, decelerating, and ends
  with a `0` sentinel. Releasing A after the first step switches to falling,
  which is what gives short hops.
- `FALL_DELAY` accelerates from ten frames per cell down to five. The first
  entry is the apex hang, and it is what lets a jump drift onto a ledge
  instead of dropping straight back down.

Walking off a ledge starts a fall, and drifting over one during a fall lands,
so a jump can be steered onto a platform edge in mid-air.

Patrols walk until a wall or a ledge turns them around. One patrol is
serviced per frame, so a single frame never queues more than one of them.

## Drawing

Only cells that actually changed are redrawn. A change is pushed onto a queue
of tile writes, and the queue is drained at most `TILES_PER_VBLANK` writes per
vblank, taking another vblank if more are pending. Eight writes is one
erase-and-redraw of a moving actor, which is the common case, and it leaves
headroom inside an NTSC vblank.

Full-screen work - the title, the stage intro, loading a stage, and the end
screens - runs with rendering switched off through `ppu_off()` / `ppu_on()`.

## Rules

Four stages of gems, patrols, spike pits, bottomless gaps and an exit door.

- Landing on a patrol while falling squashes it and bounces the hero.
- Touching a patrol any other way, entering spikes, or falling out of the
  stage costs one of three lives.
- A gem scores 100, a squashed patrol 200, and clearing a stage 1000.
- Clearing all four stages reaches the all-clear screen.

## Sound Effects

`sfx_play(id)` drives the runtime effect player: jump, land, gem, stomp,
damage, stage clear, and game over. Effects replay a run of one-frame steps
from `SFX_CTRL`, `SFX_TIMER_LO` and `SFX_TIMER_HI`, located by `SFX_START` and
`SFX_LENGTH`. See [C Language](EN-C-Language) for the table contract. The
platformer declares no music runtime, so effects have pulse 2 to themselves.

## Automated Coverage

`tests/test_platformer.py` builds the ROM and checks the stage maps, the CHR
art, the text and effect tables, and the vblank budget. It also replays the
game's own physics in Python - the same cell, vertical mode and step timers
that `tick_play()` carries - and proves that every gem and every exit can
still be reached, so a stage cannot be edited into an unwinnable one without
the tests noticing.
