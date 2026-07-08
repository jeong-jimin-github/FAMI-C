# Supported C Model

FAMI-C does not attempt to implement all hosted ISO C. It implements a small C subset that maps predictably to NES 6502 programs.

## Supported

- `char`, `unsigned char`, `int`, `unsigned int`, and `void`
- Global scalar variables and arrays
- `const unsigned char` ROM tables
- Function declarations and calls
- Static local variables
- Array indexing
- `if`, `else`, `while`, `for`, `break`, `continue`, and `return`
- 8-bit arithmetic, comparisons, logical operators
- Simple object-like `#define`

## Limits

- Arithmetic ABI is 8-bit.
- Locals are statically allocated.
- Recursion is not supported.
- Pointers, structs, unions, casts, varargs, and the C standard library are not implemented.
- ROM output targets NROM-128 / mapper 0 / 16 KB PRG + 8 KB CHR.

## Runtime API

```c
extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
```

