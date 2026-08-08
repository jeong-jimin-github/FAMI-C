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
- ROM output targets NROM-256 / mapper 0 / 32 KB PRG + 8 KB CHR.

## Runtime API

```c
extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
```

Declaring `oam_reset` and `oam_sprite` together turns on the sprite runtime:
a page-aligned shadow OAM at `$0200`, an `$4014` transfer from the NMI, and
sprites enabled in `$2001`.

```c
extern void oam_reset(void);
extern void oam_sprite(unsigned char x, unsigned char y, unsigned char tile,
                       unsigned char attr);
```

`oam_reset()` parks all 64 sprites below the visible area and rewinds the
write cursor; each `oam_sprite()` appends one 8x8 sprite, where `attr` is the
usual OAM byte. Refill the list every frame - up to 63 sprites are kept, and
the PPU still draws at most 8 on a scanline.

### Sound effects

`sfx_play(id)` is available when the program declares it and supplies the five
const tables the driver indexes:

```c
extern void sfx_play(unsigned char effect);

const unsigned char SFX_START[16];      /* first frame of each effect */
const unsigned char SFX_LENGTH[16];     /* frame count, 0 for an unused slot */
const unsigned char SFX_CTRL[N];        /* $4004 duty/volume per frame */
const unsigned char SFX_TIMER_LO[N];    /* $4006 per frame */
const unsigned char SFX_TIMER_HI[N];    /* low three bits reach $4007 */
```

Slot 0 is reserved: `sfx_play(0)` stops the current effect. The three frame
tables must be the same length and hold at most 256 entries. While an effect
plays it overwrites pulse 2 after the music driver has run, and releases the
channel back to the song when it ends.


