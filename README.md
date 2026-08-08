# FAMI-C

FAMI-C is a self-contained C compiler and ROM builder for the NES/Famicom
6502. It parses a practical 8-bit C subset, emits 6502 assembly, assembles it,
adds a small NES runtime, and writes a mapper-0 iNES ROM.

The repository includes two complete NES games. `examples/tetris.c` is a
Tetris-style game with a polished multi-palette interface, beveled blocks, and
a four-channel 2A03 chiptune arrangement. `examples/platformer.c` is a
four-stage metatile platformer with jumping, patrols, collectibles, spike pits
and sound effects.

## Documentation

- Play the examples in a browser: <https://jeong-jimin-github.github.io/FAMI-C/#play>
- GitHub Pages: <https://jeong-jimin-github.github.io/FAMI-C/>
- Wiki home: <https://github.com/jeong-jimin-github/FAMI-C/wiki>
- 한국어 Wiki: <https://github.com/jeong-jimin-github/FAMI-C/wiki/KO-Home>
- 日本語 Wiki: <https://github.com/jeong-jimin-github/FAMI-C/wiki/JA-Home>
- English Wiki: <https://github.com/jeong-jimin-github/FAMI-C/wiki/EN-Home>

## Quick Start

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

The output ROM is `build/tetris.nes`.

### Controls

On the title screen the D-pad picks the starting level: left/right steps by
one and up/down steps by five, over levels 0-19. Start begins the game.

While playing:

- D-pad left/right: move (with delayed auto shift)
- D-pad down: soft drop
- D-pad up: hard drop
- A: rotate clockwise
- B: rotate counter-clockwise
- Start: pause/resume

Beating one of the three best scores opens a name-entry screen: up/down picks
a letter, left/right (or A) moves between the three slots, and Start confirms.

The game includes a fair randomized 7-bag, next-piece preview, one- and
two-column wall kicks, lock delay, a line-clear flash, score, lines, levels,
increasing gravity, a start-level picker, a best-player table with name entry,
sound effects layered over the BGM, pause, and game-over states. Its 16-bit
LFSR advances continuously with controller/input timing, so ordinary play does
not repeat the same opening sequence on every run.

Every rotation state is a true rotation of the piece about a fixed pivot, so no
piece changes shape or drifts off its pivot as it spins: T, J and L cycle
through four orientations, I, S and Z flip between two, and O never changes.

### Music

The embedded BGM covers the MIDI's complete musical section: 4:26.127,
generated from the locally supplied `slaop88c.mid`. The source file is
4:29.605 including its initial silence. The arrangement is reduced to the NES
2A03's two pulse channels, triangle channel, and noise channel; the original
MIDI is not bundled.

The arrangement can be verified or re-embedded when `mido` is installed:

```powershell
python .\tools\arrange_midi.py --input "$HOME\Downloads\slaop88c.mid" --embed-c .\examples\tetris.c --check
```

See `assets/MUSIC.md` for the source hash, arrangement details, and usage
notice from the MIDI's embedded metadata.

## Platformer Example

```powershell
python .\famic.py build .\examples\platformer.c -o .\build\platformer.nes --asm .\build\platformer.asm
```

The stage is a grid of 16x16 cells drawn as background metatiles: 16 across
and 15 down, with cell row 0 as the status bar. One cell is at once the unit of
level storage - 240 bytes, inside the 8-bit array index the code generator
emits - and one attribute quadrant, so every cell picks its own background
palette.

The hero and the patrols are hardware sprites and move in pixels, not in
cells. Positions are 12.4 fixed point: a pixel byte plus a sixteenth-of-a-pixel
accumulator, so a speed like 1.25 px per frame is exact and the motion is
smooth. Vertical motion is a real velocity with gravity, which is what gives
the jump its arc - and holding A longer jumps higher, because releasing it
part way up trims the rise.

### Controls

- D-pad left/right: walk
- B (held): run
- A: jump; releasing A during the rise cuts the jump short

### Gameplay

Four stages of gems, patrols, spike pits, bottomless gaps and an exit door.
Landing on a patrol while falling squashes it and bounces the hero; touching
one any other way, or entering spikes, or falling out of the stage, costs one
of three lives. Gems score 100, a squashed patrol 200, and clearing a stage
1000. Sound effects cover jumping, landing, gems, stomps, damage, stage clears
and game over.

The hero walks at 1.25 px per frame, runs at 2, and a full jump rises about
54 pixels; its hitbox is inset from the 16x16 sprite so a one-cell gap is
comfortable rather than pixel-perfect. Because the actors are sprites, the
background is only redrawn for a collected gem and the HUD, through a queue
flushed at most six tiles per vblank - the NMI spends 513 cycles on the OAM
transfer first.

To run a compiler smoke test:

```powershell
python .\famic.py check .\tests\smoke.c
```

To run all automated checks:

```powershell
python -m unittest discover -s tests
```

To run the gameplay and music smoke test in Mesen 2.2.1:

```powershell
python .\tools\run_mesen_smoke.py
```

## Browser Demo

The GitHub Pages site runs both example ROMs in the browser on
[JSNES](https://github.com/bfirsh/jsnes), the JavaScript NES emulator vendored
in `web-emulator/`. It also opens a `.nes` file you built yourself, which never
leaves your machine. Keyboard, gamepad, and an on-screen pad on touch devices
all drive controller 1.

Pages serves `docs/` as it stands, so the ROMs and the emulator have to be
committed inside it. Regenerate them whenever an example or the emulator
changes:

```powershell
python .\tools\build_pages.py
```

That writes `docs/roms/*.nes` from `examples/*.c` and copies the JSNES sources
into `docs/vendor/jsnes/`. The page loads them as plain ES modules, so there is
no bundler and no install step. `--check` reports drift instead of writing, and
`tests/test_pages.py` runs the same check, so a stale ROM fails the test suite
rather than reaching the site.

## Supported C Model

The NES backend supports:

- `char`, `unsigned char`, `int`, `unsigned int`, and `void` syntax
- 8-bit arithmetic and comparisons
- global/static scalar and array storage
- `const unsigned char` ROM tables
- functions with fixed static parameter slots
- `if`, `else`, `while`, `for`, `break`, `continue`, and `return`
- array indexing, calls, unary operators, binary operators, and assignment
- simple object-like `#define` constants

Current target constraints:

- Arithmetic is 8-bit, matching the runtime ABI.
- Locals are statically allocated; recursion is not supported.
- Pointers, structs, unions, casts, varargs, and the C standard library are not
  implemented.
- Generated ROMs are NROM-256/iNES mapper 0 with a 32K PRG image and one 8K
  CHR bank.

## NES Runtime API

C programs can declare and call these native helpers:

```c
extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
```

Declaring `oam_reset` and `oam_sprite` together turns on the sprite runtime.
It reserves a page-aligned shadow OAM at `$0200`, copies it out with `$4014`
from the NMI, and enables sprites in `$2001`:

```c
extern void oam_reset(void);
extern void oam_sprite(unsigned char x, unsigned char y, unsigned char tile,
                       unsigned char attr);
```

`oam_reset()` parks all 64 hardware sprites below the visible area and rewinds
the write cursor; each `oam_sprite()` appends one 8x8 sprite at pixel `(x, y)`,
where `attr` is the usual OAM byte - palette in bits 0-1, priority in bit 5,
and flips in bits 6-7. Refill the whole list every frame; the transfer happens
in the next vblank, so the C side never has to time it. Up to 63 sprites are
kept, and the PPU still draws at most 8 on any one scanline.

Declaring `sfx_play` alongside five const tables enables the runtime's
sound-effect player, which borrows pulse 2 from the music driver for the
duration of an effect and releases it afterwards:

```c
extern void sfx_play(unsigned char effect);

const unsigned char SFX_START[16];      /* first frame of each effect */
const unsigned char SFX_LENGTH[16];     /* frame count, 0 for an unused slot */
const unsigned char SFX_CTRL[N];        /* $4004 duty/volume per frame */
const unsigned char SFX_TIMER_LO[N];    /* $4006 per frame */
const unsigned char SFX_TIMER_HI[N];    /* low three bits reach $4007 */
```

`read_pad()` returns the common NES serial controller order packed as:

- A: `128`
- B: `64`
- Select: `32`
- Start: `16`
- Up: `8`
- Down: `4`
- Left: `2`
- Right: `1`

## Files

- `famic.py` - compiler, 6502 assembler, runtime, and iNES packager
- `examples/tetris.c` - example NES/Famicom Tetris-style game
- `examples/platformer.c` - example NES/Famicom platformer
- `tests/smoke.c` - tiny compiler smoke test
- `tests/test_toolchain.py` - automated ROM/header/vector tests
- `tests/test_platformer.py` - platformer stage, tile and physics tests
- `tests/test_pages.py` - checks the published site and its generated assets
- `build.ps1` - convenience build command for the Tetris ROM
- `tools/build_pages.py` - regenerates the ROMs and emulator the site serves
- `docs/` - GitHub Pages site, including the in-browser emulator
- `web-emulator/` - JSNES sources the site is built from
- `wiki/` - source Markdown for the GitHub Wiki pages
