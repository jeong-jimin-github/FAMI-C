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

## Build The Tetris ROM

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

Windows users can also run:

```powershell
.\build.ps1
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

