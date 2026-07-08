# Tetris Example

The example game is `examples/tetris.c`.

## Build

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

## Controls

- Left / Right: move
- Down: soft drop
- A: rotate

## What It Demonstrates

- ROM lookup tables for piece shapes
- Board arrays and collision checks
- Line clearing
- Controller input
- vblank-safe PPU updates
- Native queued rendering for fast active-piece updates

## Verification

The ROM has been tested in Mesen 2.2.1 for startup rendering, falling, movement, soft drop, locking, spawning, and scroll stability.

