# FAMI-C

FAMI-C is a self-contained C compiler and ROM builder for the NES/Famicom
6502. It parses a practical 8-bit C subset, emits 6502 assembly, assembles it,
adds a small NES runtime, and writes a mapper-0 iNES ROM.

The repository includes a playable Tetris-style example in
`examples/tetris.c`.

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

To run a compiler smoke test:

```powershell
python .\famic.py check .\tests\smoke.c
```

To run all automated checks:

```powershell
python -m unittest discover -s tests
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
- Generated ROMs are NROM-128/iNES mapper 0 with one 16K PRG bank and one 8K
  CHR bank.

## NES Runtime API

C programs can declare and call these native helpers:

```c
extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
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
