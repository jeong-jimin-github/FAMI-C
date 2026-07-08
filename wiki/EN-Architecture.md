# Compiler Architecture

FAMI-C uses this pipeline:

```text
C source -> lexer/parser -> AST -> 6502 assembly -> PRG ROM -> iNES ROM
```

## Lexer And Parser

The compiler strips comments, expands simple object-like `#define` constants, tokenizes C, and parses declarations, statements, and expressions with a recursive descent parser.

## Code Generator

The generator emits 8-bit accumulator-oriented 6502 assembly.

- RAM variables start at `$0200`.
- The `$0100-$01FF` 6502 stack page is reserved for the CPU stack.
- Function parameters use static slots.
- PPU and controller access goes through native runtime helpers.

## Assembler And ROM Packager

The built-in assembler resolves labels and emits a 16 KB PRG bank. The packager adds an iNES header and an 8 KB CHR bank.

