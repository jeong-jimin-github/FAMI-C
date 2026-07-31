# FAMI-C

FAMI-C is a self-contained C compiler and ROM builder for the NES/Famicom
6502. It parses a practical 8-bit C subset, emits 6502 assembly, assembles it,
adds a small NES runtime, and writes a mapper-0 iNES ROM.

The repository includes a complete Tetris-style NES game in
`examples/tetris.c`, with a polished multi-palette interface, beveled blocks,
and a four-channel 2A03 chiptune arrangement.

## Documentation

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
- `tests/smoke.c` - tiny compiler smoke test
- `tests/test_toolchain.py` - automated ROM/header/vector tests
- `build.ps1` - convenience build command for the Tetris ROM
- `docs/` - GitHub Pages site
- `wiki/` - source Markdown for the GitHub Wiki pages
