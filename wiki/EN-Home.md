# FAMI-C English Wiki

FAMI-C is a self-contained toolchain for writing NES / Famicom 6502 programs in C and building them into `.nes` ROM files.

## Pages

- [[Installation and Usage|EN-Usage]]
- [[Supported C Model|EN-C-Language]]
- [[Compiler Architecture|EN-Architecture]]
- [[Tetris Example|EN-Tetris]]

## Highlights

- C parser, 6502 code generator, assembler, runtime, and iNES packager in one Python file.
- 8-bit ABI and static memory model designed for NES constraints.
- Runtime functions for vblank waiting, PPU writes, controller input, and random values.
- Tetris-style example game in `examples/tetris.c`.
- Verified in Mesen 2.2.1.

