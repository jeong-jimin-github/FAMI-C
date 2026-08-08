# Platformer Example

The example game is `examples/platformer.c`.

## Build

```powershell
python .\famic.py build .\examples\platformer.c -o .\build\platformer.nes --asm .\build\platformer.asm
```

## Controls

- Left / Right: walk
- B (held): run
- A: jump; the longer A is held during the rise, the higher the jump
- Start: begin a game from the title screen, or return to the title after a
  game over or an all-clear

## The Metatile Grid

The stage is drawn as background metatiles while the actors on top of it are
hardware sprites. The screen is 16 cells wide and 15 cells tall, each cell
being 2x2 tiles:

- Cell row 0 is the status bar; rows 1-14 are the stage.
- One cell is the unit of level storage, so a stage map is 240 bytes and fits
  the 8-bit array index the code generator emits.
- One cell is also one attribute quadrant, so every cell picks its own
  background palette without any extra bookkeeping.

Attribute bytes live at nametable rows 30 and 31 as far as `ppu_put` is
concerned, because its address maths is `$2000 + y * 32 + x`. The same helper
that writes tiles therefore writes palette selects too.

Cell kinds are open air, dirt, grass, brick, gem, spikes, exit door, and a
patrol spawn marker that becomes open air when the stage loads.

## Colour

Terrain uses colours 1 and 2 and takes its hue from the attribute map: earth
is green, brick and spikes are red, gems and the exit are purple. The actors
are sprites, so they carry their own palettes instead - the hero uses sprite
palette 0, which is blue, and the patrols sprite palette 1, which is red.

The actor drawings in `make_chr()` are plain silhouettes; the generator lights
them from the top left, colour 3 on the rim, 2 for the body and 1 in shadow,
the same way the block faces are lit.

## Subpixel Motion

Positions are 12.4 fixed point: a pixel byte plus a sixteenth-of-a-pixel
accumulator. `advance_sub()` adds a speed to the accumulator and hands back
how many whole pixels it carried, so a speed of 1.25 px per frame is exact
rather than rounded, and the hero moves smoothly instead of a cell at a time.

- The hero walks at `WALK_SPEED` (1.25 px per frame) and runs at `RUN_SPEED`
  (2 px per frame) while B is held. Patrols move at `FOE_SPEED`, half a pixel
  per frame.
- Vertical motion is a real velocity. `hero_vy` is biased by `VY_ZERO` so one
  unsigned byte holds both directions: a jump sets it to `VY_JUMP`, `GRAVITY`
  is added every frame, and `MAX_FALL` caps the descent. A full jump rises
  about 54 pixels.
- Releasing A part way up clamps the rise to `VY_CUT`, so a tap is a short hop
  and a held button is a full jump.
- The hero keeps full control in mid-air, so a jump can be steered onto a
  ledge.

Movement resolves one pixel at a time against `box_blocked()`, which probes
the four corners of the hitbox. That hitbox is inset from the 16x16 sprite -
`BOX_L` to `BOX_R`, ten pixels wide - so a one-cell gap is comfortable to walk
and jump through instead of pixel-perfect.

Patrols walk until a wall or a ledge turns them around, probing the cell in
front of their leading edge and the cell under it.

## Drawing

`oam_reset()` parks all 64 sprites off-screen and rewinds the shadow OAM, then
`oam_sprite()` appends four 8x8 sprites for each 16x16 actor. The NMI copies
the buffer out with `$4014`, so the C side never has to time it. Four actors
abreast is eight sprites on a scanline, which is exactly what the PPU can draw.

That leaves the background almost static, so the tile queue only carries a
collected gem and the HUD digits. It is drained at most `TILES_PER_VBLANK`
writes per vblank, taking another vblank if more are pending, and it keeps a
smaller slice than it used to because the OAM transfer spends 513 cycles of
vblank first.

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
art, the text and effect tables, the sprite runtime's page-aligned OAM and its
DMA, and the vblank budget. It also replays the game's own pixel physics in
Python - the same position, subpixel accumulators and biased vertical speed
that `tick_play()` carries - and shows that every gem and every exit can still
be reached, so a stage cannot be edited into an unwinnable one without the
tests noticing.
