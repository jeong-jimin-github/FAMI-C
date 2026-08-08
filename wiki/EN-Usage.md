# Installation and Usage

## Requirements

- Python 3.10 or newer
- Git
- NES emulator such as Mesen 2.2.1

## Clone

```powershell
git clone https://github.com/jeong-jimin-github/FAMI-C.git
cd FAMI-C
```

## Build The Example ROMs

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
python .\famic.py build .\examples\platformer.c -o .\build\platformer.nes --asm .\build\platformer.asm
```

Windows users can also run:

```powershell
.\build.ps1
```

## Play In The Browser

The [GitHub Pages site](https://jeong-jimin-github.github.io/FAMI-C/#play) runs
both example ROMs with [JSNES](https://github.com/bfirsh/jsnes), so you can try
them before installing anything. It also opens a `.nes` file you built
yourself; the file stays in your browser.

Arrow keys are the D-pad, `X` is A, `Z` is B, `Enter` is Start and right `Ctrl`
is Select. Keys reach the game only while the screen has focus. Gamepads work,
and touch devices get an on-screen pad.

After changing an example or the emulator, regenerate what the site serves:

```powershell
python .\tools\build_pages.py
```

## Test

```powershell
python -m unittest discover -s tests
```

## Commands

`build` compiles C and writes an iNES ROM.

```powershell
python .\famic.py build source.c -o build/game.nes --asm build/game.asm
```

`check` parses, compiles, and assembles without writing a ROM.

```powershell
python .\famic.py check source.c
```

`asm` assembles FAMI-C assembly into a ROM.

```powershell
python .\famic.py asm build/game.asm -o build/game.nes
```

