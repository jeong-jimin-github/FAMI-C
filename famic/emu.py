"""A headless NES: 6502 CPU, PPU, controllers.

This exists so an agent can answer "does my game work?" without a human
looking at a screen.  It runs the ROM, feeds a scripted controller trace, and
reports the framebuffer, the nametable as text, the sprite list, and -- the
part that matters most -- named RAM locations read straight out of the symbol
table the compiler emitted.

Accuracy target: enough for game logic.  Scanline-granular PPU timing, no
cycle-exact bus behaviour, no DMC.  A game that depends on raster tricks will
not be reproduced faithfully; a game that reads the pad, moves an actor, and
draws is.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------
# Opcode table
# --------------------------------------------------------------------------

# name mode cycles, indexed by opcode.  Only the official instruction set;
# an unofficial opcode is reported as a crash, which is what an agent wants to
# hear when its program has run off into data.
_OPCODE_TEXT = """
00 BRK imp 7 | 01 ORA izx 6 | 05 ORA zp 3 | 06 ASL zp 5 | 08 PHP imp 3
09 ORA imm 2 | 0A ASL acc 2 | 0D ORA abs 4 | 0E ASL abs 6 | 10 BPL rel 2
11 ORA izy 5 | 15 ORA zpx 4 | 16 ASL zpx 6 | 18 CLC imp 2 | 19 ORA aby 4
1D ORA abx 4 | 1E ASL abx 7 | 20 JSR abs 6 | 21 AND izx 6 | 24 BIT zp 3
25 AND zp 3 | 26 ROL zp 5 | 28 PLP imp 4 | 29 AND imm 2 | 2A ROL acc 2
2C BIT abs 4 | 2D AND abs 4 | 2E ROL abs 6 | 30 BMI rel 2 | 31 AND izy 5
35 AND zpx 4 | 36 ROL zpx 6 | 38 SEC imp 2 | 39 AND aby 4 | 3D AND abx 4
3E ROL abx 7 | 40 RTI imp 6 | 41 EOR izx 6 | 45 EOR zp 3 | 46 LSR zp 5
48 PHA imp 3 | 49 EOR imm 2 | 4A LSR acc 2 | 4C JMP abs 3 | 4D EOR abs 4
4E LSR abs 6 | 50 BVC rel 2 | 51 EOR izy 5 | 55 EOR zpx 4 | 56 LSR zpx 6
58 CLI imp 2 | 59 EOR aby 4 | 5D EOR abx 4 | 5E LSR abx 7 | 60 RTS imp 6
61 ADC izx 6 | 65 ADC zp 3 | 66 ROR zp 5 | 68 PLA imp 4 | 69 ADC imm 2
6A ROR acc 2 | 6C JMP ind 5 | 6D ADC abs 4 | 6E ROR abs 6 | 70 BVS rel 2
71 ADC izy 5 | 75 ADC zpx 4 | 76 ROR zpx 6 | 78 SEI imp 2 | 79 ADC aby 4
7D ADC abx 4 | 7E ROR abx 7 | 81 STA izx 6 | 84 STY zp 3 | 85 STA zp 3
86 STX zp 3 | 88 DEY imp 2 | 8A TXA imp 2 | 8C STY abs 4 | 8D STA abs 4
8E STX abs 4 | 90 BCC rel 2 | 91 STA izy 6 | 94 STY zpx 4 | 95 STA zpx 4
96 STX zpy 4 | 98 TYA imp 2 | 99 STA aby 5 | 9A TXS imp 2 | 9D STA abx 5
A0 LDY imm 2 | A1 LDA izx 6 | A2 LDX imm 2 | A4 LDY zp 3 | A5 LDA zp 3
A6 LDX zp 3 | A8 TAY imp 2 | A9 LDA imm 2 | AA TAX imp 2 | AC LDY abs 4
AD LDA abs 4 | AE LDX abs 4 | B0 BCS rel 2 | B1 LDA izy 5 | B4 LDY zpx 4
B5 LDA zpx 4 | B6 LDX zpy 4 | B8 CLV imp 2 | B9 LDA aby 4 | BA TSX imp 2
BC LDY abx 4 | BD LDA abx 4 | BE LDX aby 4 | C0 CPY imm 2 | C1 CMP izx 6
C4 CPY zp 3 | C5 CMP zp 3 | C6 DEC zp 5 | C8 INY imp 2 | C9 CMP imm 2
CA DEX imp 2 | CC CPY abs 4 | CD CMP abs 4 | CE DEC abs 6 | D0 BNE rel 2
D1 CMP izy 5 | D5 CMP zpx 4 | D6 DEC zpx 6 | D8 CLD imp 2 | D9 CMP aby 4
DD CMP abx 4 | DE DEC abx 7 | E0 CPX imm 2 | E1 SBC izx 6 | E4 CPX zp 3
E5 SBC zp 3 | E6 INC zp 5 | E8 INX imp 2 | E9 SBC imm 2 | EA NOP imp 2
EC CPX abs 4 | ED SBC abs 4 | EE INC abs 6 | F0 BEQ rel 2 | F1 SBC izy 5
F5 SBC zpx 4 | F6 INC zpx 6 | F8 SED imp 2 | F9 SBC aby 4 | FD SBC abx 4
FE INC abx 7
"""


def _build_opcodes() -> Dict[int, Tuple[str, str, int]]:
    table: Dict[int, Tuple[str, str, int]] = {}
    tokens = _OPCODE_TEXT.replace("|", " ").split()
    if len(tokens) % 4:
        raise RuntimeError("opcode table is malformed")
    for i in range(0, len(tokens), 4):
        code, name, mode, cycles = tokens[i : i + 4]
        table[int(code, 16)] = (name, mode, int(cycles))
    return table


OPCODES = _build_opcodes()


# NES master palette, as RGB.
NES_PALETTE = [
    (0x66, 0x66, 0x66), (0x00, 0x2A, 0x88), (0x14, 0x12, 0xA7), (0x3B, 0x00, 0xA4),
    (0x5C, 0x00, 0x7E), (0x6E, 0x00, 0x40), (0x6C, 0x06, 0x00), (0x56, 0x1D, 0x00),
    (0x33, 0x35, 0x00), (0x0B, 0x48, 0x00), (0x00, 0x52, 0x00), (0x00, 0x4F, 0x08),
    (0x00, 0x40, 0x4D), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xAD, 0xAD, 0xAD), (0x15, 0x5F, 0xD9), (0x42, 0x40, 0xFF), (0x75, 0x27, 0xFE),
    (0xA0, 0x1A, 0xCC), (0xB7, 0x1E, 0x7B), (0xB5, 0x31, 0x20), (0x99, 0x4E, 0x00),
    (0x6B, 0x6D, 0x00), (0x38, 0x87, 0x00), (0x0C, 0x93, 0x00), (0x00, 0x8F, 0x32),
    (0x00, 0x7C, 0x8D), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xFF, 0xFE, 0xFF), (0x64, 0xB0, 0xFF), (0x92, 0x90, 0xFF), (0xC6, 0x76, 0xFF),
    (0xF3, 0x6A, 0xFF), (0xFE, 0x6E, 0xCC), (0xFE, 0x81, 0x70), (0xEA, 0x9E, 0x22),
    (0xBC, 0xBE, 0x00), (0x88, 0xD8, 0x00), (0x5C, 0xE4, 0x30), (0x45, 0xE0, 0x82),
    (0x48, 0xCD, 0xDE), (0x4F, 0x4F, 0x4F), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xFF, 0xFE, 0xFF), (0xC0, 0xDF, 0xFF), (0xD3, 0xD2, 0xFF), (0xE8, 0xC8, 0xFF),
    (0xFB, 0xC2, 0xFF), (0xFE, 0xC4, 0xEA), (0xFE, 0xCC, 0xC5), (0xF7, 0xD8, 0xA5),
    (0xE4, 0xE5, 0x94), (0xCF, 0xEF, 0x96), (0xBD, 0xF4, 0xAB), (0xB3, 0xF3, 0xCC),
    (0xB5, 0xEB, 0xF2), (0xB8, 0xB8, 0xB8), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
]


BUTTONS = {
    "A": 0x80,
    "B": 0x40,
    "SELECT": 0x20,
    "START": 0x10,
    "UP": 0x08,
    "DOWN": 0x04,
    "LEFT": 0x02,
    "RIGHT": 0x01,
}


class Crash(Exception):
    def __init__(self, message: str, pc: int):
        super().__init__(f"{message} (PC=${pc:04X})")
        self.pc = pc


# --------------------------------------------------------------------------
# PPU
# --------------------------------------------------------------------------


class PPU:
    def __init__(self, chr_rom: bytes, vertical_mirroring: bool = True):
        self.chr = bytearray(chr_rom)
        self.vram = bytearray(0x800)
        self.palette = bytearray(32)
        self.oam = bytearray(256)
        self.vertical = vertical_mirroring

        self.ctrl = 0
        self.mask = 0
        self.status = 0
        self.oam_addr = 0
        self.v = 0
        self.t = 0
        self.x_fine = 0
        self.write_latch = 0
        self.read_buffer = 0
        self.scroll_x = 0
        self.scroll_y = 0
        self.nmi_pending = False

    # -- address mapping ---------------------------------------------------

    def mirror(self, addr: int) -> int:
        addr &= 0x0FFF
        table = addr >> 10
        offset = addr & 0x3FF
        if self.vertical:
            # NT0/NT2 share, NT1/NT3 share.
            index = table & 1
        else:
            index = (table >> 1) & 1
        return index * 0x400 + offset

    def read_vram(self, addr: int) -> int:
        addr &= 0x3FFF
        if addr < 0x2000:
            return self.chr[addr]
        if addr < 0x3F00:
            return self.vram[self.mirror(addr)]
        return self.palette[self._pal_index(addr)]

    def write_vram(self, addr: int, value: int) -> None:
        addr &= 0x3FFF
        if addr < 0x2000:
            return  # CHR ROM
        if addr < 0x3F00:
            self.vram[self.mirror(addr)] = value
            return
        self.palette[self._pal_index(addr)] = value & 0x3F

    @staticmethod
    def _pal_index(addr: int) -> int:
        index = addr & 0x1F
        if index in (0x10, 0x14, 0x18, 0x1C):
            index -= 0x10
        return index

    # -- register interface ------------------------------------------------

    def read_register(self, index: int) -> int:
        if index == 2:
            value = self.status
            self.status &= 0x7F
            self.write_latch = 0
            return value
        if index == 4:
            return self.oam[self.oam_addr]
        if index == 7:
            addr = self.v & 0x3FFF
            if addr >= 0x3F00:
                value = self.read_vram(addr)
                self.read_buffer = self.read_vram(addr - 0x1000)
            else:
                value = self.read_buffer
                self.read_buffer = self.read_vram(addr)
            self.v = (self.v + (32 if self.ctrl & 0x04 else 1)) & 0x7FFF
            return value
        return 0

    def write_register(self, index: int, value: int) -> None:
        value &= 0xFF
        if index == 0:
            self.ctrl = value
            self.t = (self.t & 0xF3FF) | ((value & 0x03) << 10)
        elif index == 1:
            self.mask = value
        elif index == 3:
            self.oam_addr = value
        elif index == 4:
            self.oam[self.oam_addr] = value
            self.oam_addr = (self.oam_addr + 1) & 0xFF
        elif index == 5:
            if self.write_latch == 0:
                self.scroll_x = value
                self.t = (self.t & 0xFFE0) | (value >> 3)
                self.x_fine = value & 7
                self.write_latch = 1
            else:
                self.scroll_y = value
                self.t = (self.t & 0x8FFF) | ((value & 0x07) << 12)
                self.t = (self.t & 0xFC1F) | ((value & 0xF8) << 2)
                self.write_latch = 0
        elif index == 6:
            if self.write_latch == 0:
                self.t = (self.t & 0x00FF) | ((value & 0x3F) << 8)
                self.write_latch = 1
            else:
                self.t = (self.t & 0xFF00) | value
                self.v = self.t
                self.write_latch = 0
        elif index == 7:
            self.write_vram(self.v & 0x3FFF, value)
            self.v = (self.v + (32 if self.ctrl & 0x04 else 1)) & 0x7FFF

    # -- rendering ---------------------------------------------------------

    @property
    def rendering(self) -> bool:
        return bool(self.mask & 0x18)

    def nametable_base(self) -> int:
        return 0x2000 + (self.ctrl & 0x03) * 0x400

    def tile_at(self, nt_base: int, tx: int, ty: int) -> int:
        return self.read_vram(nt_base + ty * 32 + tx)

    def attr_at(self, nt_base: int, tx: int, ty: int) -> int:
        byte = self.read_vram(nt_base + 0x3C0 + (ty // 4) * 8 + (tx // 4))
        shift = ((ty & 2) << 1) | (tx & 2)
        return (byte >> shift) & 3

    def render(self) -> List[List[int]]:
        """Compose a 240x256 frame of NES colour indices."""

        frame = [[self.palette[0] & 0x3F for _ in range(256)] for _ in range(240)]
        if not self.rendering:
            return frame
        bg_pattern = 0x1000 if self.ctrl & 0x10 else 0x0000
        spr_pattern = 0x1000 if self.ctrl & 0x08 else 0x0000
        base = self.nametable_base()
        opaque = [[False] * 256 for _ in range(240)]

        if self.mask & 0x08:
            for py in range(240):
                sy = (py + self.scroll_y) % 480
                for px in range(256):
                    sx = (px + self.scroll_x) % 512
                    nt = base
                    if sx >= 256:
                        nt ^= 0x400
                    if sy >= 240:
                        nt ^= 0x800
                    tx, ty = (sx % 256) // 8, (sy % 240) // 8
                    tile = self.tile_at(nt, tx, ty)
                    pal = self.attr_at(nt, tx, ty)
                    fine_x, fine_y = sx & 7, sy & 7
                    addr = bg_pattern + tile * 16 + fine_y
                    lo = self.read_vram(addr)
                    hi = self.read_vram(addr + 8)
                    bit = 7 - fine_x
                    value = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)
                    if value:
                        frame[py][px] = self.palette[pal * 4 + value] & 0x3F
                        opaque[py][px] = True

        if self.mask & 0x10:
            # Back to front, so sprite 0 wins ties like the hardware does.
            for i in range(63, -1, -1):
                y = self.oam[i * 4]
                if y >= 0xEF:
                    continue
                tile = self.oam[i * 4 + 1]
                attr = self.oam[i * 4 + 2]
                x = self.oam[i * 4 + 3]
                pal = 4 + (attr & 3)
                behind = bool(attr & 0x20)
                flip_x = bool(attr & 0x40)
                flip_y = bool(attr & 0x80)
                for row in range(8):
                    py = y + 1 + row
                    if not 0 <= py < 240:
                        continue
                    src_row = 7 - row if flip_y else row
                    addr = spr_pattern + tile * 16 + src_row
                    lo = self.read_vram(addr)
                    hi = self.read_vram(addr + 8)
                    for col in range(8):
                        px = x + col
                        if not 0 <= px < 256:
                            continue
                        bit = col if flip_x else 7 - col
                        value = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)
                        if not value:
                            continue
                        if behind and opaque[py][px]:
                            continue
                        frame[py][px] = self.palette[pal * 4 + value] & 0x3F
        return frame


# --------------------------------------------------------------------------
# Machine
# --------------------------------------------------------------------------


@dataclass
class APULog:
    """Every APU register write, so audio can be asserted on without ears."""

    writes: List[Tuple[int, int, int]] = field(default_factory=list)  # frame, reg, value

    def channel_active(self, channel: str) -> bool:
        reg = {"pulse1": 0x4000, "pulse2": 0x4004, "triangle": 0x4008, "noise": 0x400C}[channel]
        last = None
        for _, addr, value in self.writes:
            if addr == reg:
                last = value
        if last is None:
            return False
        if channel == "triangle":
            return last != 0
        return (last & 0x0F) != 0


class NES:
    def __init__(self, rom: bytes, symbols: Optional[Dict[str, int]] = None):
        if rom[:4] != b"NES\x1a":
            raise ValueError("iNES 헤더가 아닙니다")
        prg_banks = rom[4]
        chr_banks = rom[5]
        flags6 = rom[6]
        prg_size = prg_banks * 0x4000
        chr_size = chr_banks * 0x2000
        self.prg = rom[16 : 16 + prg_size]
        self.chr = rom[16 + prg_size : 16 + prg_size + chr_size]
        self.ram = bytearray(0x800)
        self.ppu = PPU(self.chr, vertical_mirroring=bool(flags6 & 1))
        self.apu = APULog()
        self.symbols = dict(symbols or {})

        self.pads = [0, 0]
        self.pad_shift = [0, 0]
        self.pad_strobe = False

        self.a = self.x = self.y = 0
        self.sp = 0xFD
        self.pc = 0
        self.flags = 0x24
        self.cycles = 0
        self.frame = 0
        self.stall = 0
        self.reset()

    # -- memory ------------------------------------------------------------

    def read(self, addr: int) -> int:
        addr &= 0xFFFF
        if addr < 0x2000:
            return self.ram[addr & 0x7FF]
        if addr < 0x4000:
            return self.ppu.read_register(addr & 7)
        if addr == 0x4016:
            return self._read_pad(0)
        if addr == 0x4017:
            return self._read_pad(1)
        if addr < 0x4020:
            return 0
        if addr >= 0x8000:
            if len(self.prg) == 0x4000:
                return self.prg[(addr - 0x8000) & 0x3FFF]
            return self.prg[addr - 0x8000]
        return 0

    def write(self, addr: int, value: int) -> None:
        addr &= 0xFFFF
        value &= 0xFF
        if addr < 0x2000:
            self.ram[addr & 0x7FF] = value
            return
        if addr < 0x4000:
            self.ppu.write_register(addr & 7, value)
            return
        if addr == 0x4014:
            base = value << 8
            for i in range(256):
                self.ppu.oam[i] = self.read(base + i)
            self.stall += 513
            return
        if addr == 0x4016:
            strobe = bool(value & 1)
            if self.pad_strobe and not strobe:
                self.pad_shift = list(self.pads)
            self.pad_strobe = strobe
            if strobe:
                self.pad_shift = list(self.pads)
            return
        if 0x4000 <= addr <= 0x4017:
            self.apu.writes.append((self.frame, addr, value))
            return

    def _read_pad(self, index: int) -> int:
        if self.pad_strobe:
            return (self.pads[index] >> 7) & 1
        bit = (self.pad_shift[index] >> 7) & 1
        self.pad_shift[index] = (self.pad_shift[index] << 1) & 0xFF
        return bit

    # -- CPU ---------------------------------------------------------------

    def reset(self) -> None:
        self.pc = self.read(0xFFFC) | (self.read(0xFFFD) << 8)
        self.sp = 0xFD
        self.flags = 0x24

    @property
    def carry(self) -> int:
        return self.flags & 1

    def set_flag(self, bit: int, on: bool) -> None:
        if on:
            self.flags |= bit
        else:
            self.flags &= ~bit & 0xFF

    def set_zn(self, value: int) -> int:
        value &= 0xFF
        self.set_flag(0x02, value == 0)
        self.set_flag(0x80, bool(value & 0x80))
        return value

    def push(self, value: int) -> None:
        self.ram[0x100 + self.sp] = value & 0xFF
        self.sp = (self.sp - 1) & 0xFF

    def pop(self) -> int:
        self.sp = (self.sp + 1) & 0xFF
        return self.ram[0x100 + self.sp]

    def read16(self, addr: int) -> int:
        return self.read(addr) | (self.read(addr + 1) << 8)

    def operand(self, mode: str) -> Tuple[int, int, bool]:
        """Return (address, immediate_value, page_crossed)."""

        pc = self.pc
        if mode == "imp" or mode == "acc":
            return 0, 0, False
        if mode == "imm":
            self.pc = (pc + 1) & 0xFFFF
            return pc, self.read(pc), False
        if mode == "zp":
            self.pc = (pc + 1) & 0xFFFF
            return self.read(pc), 0, False
        if mode == "zpx":
            self.pc = (pc + 1) & 0xFFFF
            return (self.read(pc) + self.x) & 0xFF, 0, False
        if mode == "zpy":
            self.pc = (pc + 1) & 0xFFFF
            return (self.read(pc) + self.y) & 0xFF, 0, False
        if mode == "abs":
            self.pc = (pc + 2) & 0xFFFF
            return self.read16(pc), 0, False
        if mode == "abx":
            self.pc = (pc + 2) & 0xFFFF
            base = self.read16(pc)
            addr = (base + self.x) & 0xFFFF
            return addr, 0, (base & 0xFF00) != (addr & 0xFF00)
        if mode == "aby":
            self.pc = (pc + 2) & 0xFFFF
            base = self.read16(pc)
            addr = (base + self.y) & 0xFFFF
            return addr, 0, (base & 0xFF00) != (addr & 0xFF00)
        if mode == "ind":
            self.pc = (pc + 2) & 0xFFFF
            ptr = self.read16(pc)
            # The 6502's page-wrap bug on JMP ($xxFF) is real; reproduce it.
            lo = self.read(ptr)
            hi = self.read((ptr & 0xFF00) | ((ptr + 1) & 0xFF))
            return lo | (hi << 8), 0, False
        if mode == "izx":
            self.pc = (pc + 1) & 0xFFFF
            zp = (self.read(pc) + self.x) & 0xFF
            return self.read(zp) | (self.read((zp + 1) & 0xFF) << 8), 0, False
        if mode == "izy":
            self.pc = (pc + 1) & 0xFFFF
            zp = self.read(pc)
            base = self.read(zp) | (self.read((zp + 1) & 0xFF) << 8)
            addr = (base + self.y) & 0xFFFF
            return addr, 0, (base & 0xFF00) != (addr & 0xFF00)
        if mode == "rel":
            self.pc = (pc + 1) & 0xFFFF
            offset = self.read(pc)
            if offset & 0x80:
                offset -= 256
            return (self.pc + offset) & 0xFFFF, 0, False
        raise Crash(f"알 수 없는 주소지정 {mode}", self.pc)

    def step(self) -> int:
        if self.stall > 0:
            self.stall -= 1
            return 1
        opcode = self.read(self.pc)
        entry = OPCODES.get(opcode)
        if entry is None:
            raise Crash(f"정의되지 않은 opcode ${opcode:02X}", self.pc)
        name, mode, cycles = entry
        self.pc = (self.pc + 1) & 0xFFFF
        addr, imm, crossed = self.operand(mode)
        extra = 0

        def load() -> int:
            return imm if mode == "imm" else self.read(addr)

        if name == "LDA":
            self.a = self.set_zn(load())
            extra = crossed
        elif name == "LDX":
            self.x = self.set_zn(load())
            extra = crossed
        elif name == "LDY":
            self.y = self.set_zn(load())
            extra = crossed
        elif name == "STA":
            self.write(addr, self.a)
        elif name == "STX":
            self.write(addr, self.x)
        elif name == "STY":
            self.write(addr, self.y)
        elif name == "TAX":
            self.x = self.set_zn(self.a)
        elif name == "TAY":
            self.y = self.set_zn(self.a)
        elif name == "TXA":
            self.a = self.set_zn(self.x)
        elif name == "TYA":
            self.a = self.set_zn(self.y)
        elif name == "TSX":
            self.x = self.set_zn(self.sp)
        elif name == "TXS":
            self.sp = self.x
        elif name == "PHA":
            self.push(self.a)
        elif name == "PHP":
            self.push(self.flags | 0x30)
        elif name == "PLA":
            self.a = self.set_zn(self.pop())
        elif name == "PLP":
            self.flags = (self.pop() & 0xEF) | 0x20
        elif name in ("AND", "ORA", "EOR"):
            value = load()
            self.a = self.set_zn(
                {"AND": self.a & value, "ORA": self.a | value, "EOR": self.a ^ value}[name]
            )
            extra = crossed
        elif name == "ADC":
            self._adc(load())
            extra = crossed
        elif name == "SBC":
            self._adc(load() ^ 0xFF)
            extra = crossed
        elif name in ("CMP", "CPX", "CPY"):
            reg = {"CMP": self.a, "CPX": self.x, "CPY": self.y}[name]
            value = load()
            diff = (reg - value) & 0xFF
            self.set_flag(0x01, reg >= value)
            self.set_zn(diff)
            extra = crossed if name == "CMP" else 0
        elif name == "BIT":
            value = self.read(addr)
            self.set_flag(0x02, (self.a & value) == 0)
            self.set_flag(0x40, bool(value & 0x40))
            self.set_flag(0x80, bool(value & 0x80))
        elif name in ("INC", "DEC"):
            value = (self.read(addr) + (1 if name == "INC" else -1)) & 0xFF
            self.write(addr, value)
            self.set_zn(value)
        elif name == "INX":
            self.x = self.set_zn(self.x + 1)
        elif name == "INY":
            self.y = self.set_zn(self.y + 1)
        elif name == "DEX":
            self.x = self.set_zn(self.x - 1)
        elif name == "DEY":
            self.y = self.set_zn(self.y - 1)
        elif name in ("ASL", "LSR", "ROL", "ROR"):
            self._shift(name, mode, addr)
        elif name == "JMP":
            self.pc = addr
        elif name == "JSR":
            ret = (self.pc - 1) & 0xFFFF
            self.push(ret >> 8)
            self.push(ret & 0xFF)
            self.pc = addr
        elif name == "RTS":
            lo = self.pop()
            hi = self.pop()
            self.pc = ((hi << 8) | lo) + 1 & 0xFFFF
        elif name == "RTI":
            self.flags = (self.pop() & 0xEF) | 0x20
            lo = self.pop()
            hi = self.pop()
            self.pc = (hi << 8) | lo
        elif name in ("BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ"):
            take = {
                "BPL": not self.flags & 0x80,
                "BMI": bool(self.flags & 0x80),
                "BVC": not self.flags & 0x40,
                "BVS": bool(self.flags & 0x40),
                "BCC": not self.flags & 0x01,
                "BCS": bool(self.flags & 0x01),
                "BNE": not self.flags & 0x02,
                "BEQ": bool(self.flags & 0x02),
            }[name]
            if take:
                extra = 1 + ((self.pc & 0xFF00) != (addr & 0xFF00))
                self.pc = addr
        elif name == "CLC":
            self.set_flag(0x01, False)
        elif name == "SEC":
            self.set_flag(0x01, True)
        elif name == "CLI":
            self.set_flag(0x04, False)
        elif name == "SEI":
            self.set_flag(0x04, True)
        elif name == "CLV":
            self.set_flag(0x40, False)
        elif name == "CLD":
            self.set_flag(0x08, False)
        elif name == "SED":
            self.set_flag(0x08, True)
        elif name == "NOP":
            pass
        elif name == "BRK":
            raise Crash("BRK 명령 실행 (보통 코드가 데이터로 넘어간 경우)", self.pc)
        else:
            raise Crash(f"구현되지 않은 명령 {name}", self.pc)
        return cycles + extra

    def _adc(self, value: int) -> None:
        total = self.a + value + self.carry
        self.set_flag(0x01, total > 0xFF)
        result = total & 0xFF
        self.set_flag(0x40, bool((~(self.a ^ value) & (self.a ^ result)) & 0x80))
        self.a = self.set_zn(result)

    def _shift(self, name: str, mode: str, addr: int) -> None:
        value = self.a if mode == "acc" else self.read(addr)
        carry_in = self.carry
        if name == "ASL":
            self.set_flag(0x01, bool(value & 0x80))
            value = (value << 1) & 0xFF
        elif name == "LSR":
            self.set_flag(0x01, bool(value & 0x01))
            value >>= 1
        elif name == "ROL":
            self.set_flag(0x01, bool(value & 0x80))
            value = ((value << 1) | carry_in) & 0xFF
        else:
            self.set_flag(0x01, bool(value & 0x01))
            value = (value >> 1) | (carry_in << 7)
        value = self.set_zn(value)
        if mode == "acc":
            self.a = value
        else:
            self.write(addr, value)

    def nmi(self) -> None:
        self.push(self.pc >> 8)
        self.push(self.pc & 0xFF)
        self.push(self.flags & 0xEF)
        self.set_flag(0x04, True)
        self.pc = self.read16(0xFFFA)

    # -- frame loop --------------------------------------------------------

    CYCLES_PER_SCANLINE = 114
    SCANLINES = 262
    VBLANK_LINE = 241

    def _scanline(self, budget: List[int]) -> None:
        used = 0
        while used < self.CYCLES_PER_SCANLINE:
            used += self.step()
            budget[0] -= 1
            if budget[0] <= 0:
                raise Crash("프레임이 끝나지 않습니다 (무한 루프로 보입니다)", self.pc)

    def run_frame(self, budget: int = 400000) -> None:
        """Advance one frame, stopping where the game thinks a frame ends.

        A frame here runs from just after one vblank to the end of the next
        vblank's NMI handler.  That matters for tooling: it means every value
        read after `run_frame()` is the state the game settled on for that
        frame, not a snapshot taken partway through the next frame's update
        while the main loop happened to be running ahead of the NMI.
        """

        left = [budget]
        # Tail of the previous frame (post-vblank), then the visible frame.
        for line in range(self.VBLANK_LINE + 1, self.SCANLINES):
            if line == 261:
                self.ppu.status &= 0x3F  # clear vblank and sprite 0
            self._scanline(left)
        for line in range(0, self.VBLANK_LINE):
            if line == 30 and self.ppu.rendering and self.ppu.oam[0] < 0xEF:
                # Approximate sprite 0 hit so a game that waits on it proceeds.
                self.ppu.status |= 0x40
            self._scanline(left)

        self.ppu.status |= 0x80
        if self.ppu.ctrl & 0x80:
            resume_sp = self.sp
            self.nmi()
            # Run the handler to completion so the OAM transfer, the VRAM
            # queue drain and the sound tick have all happened.
            while self.sp != resume_sp:
                self.step()
                left[0] -= 1
                if left[0] <= 0:
                    raise Crash("NMI 핸들러가 끝나지 않습니다", self.pc)
        self.frame += 1

    # -- inspection --------------------------------------------------------

    def peek(self, name_or_addr: object, size: int = 1) -> int:
        if isinstance(name_or_addr, str):
            if name_or_addr not in self.symbols:
                raise KeyError(name_or_addr)
            addr = self.symbols[name_or_addr]
        else:
            addr = int(name_or_addr)
        if size == 2:
            return self.read(addr) | (self.read(addr + 1) << 8)
        return self.read(addr)

    def set_pad(self, player: int, buttons: int) -> None:
        self.pads[player] = buttons & 0xFF


# --------------------------------------------------------------------------
# Input scripts
# --------------------------------------------------------------------------


def parse_input_script(text: str) -> Dict[int, int]:
    """Parse `60:START, 120:RIGHT|A*90` into a per-frame button map.

    `frame:BUTTONS` holds those buttons for one frame; `*n` repeats for n
    frames.  Buttons combine with `|` or `+`.
    """

    schedule: Dict[int, int] = {}
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError(f"입력 스크립트 형식 오류: {chunk!r} (frame:BUTTONS 형식)")
        frame_s, rest = chunk.split(":", 1)
        repeat = 1
        if "*" in rest:
            rest, repeat_s = rest.rsplit("*", 1)
            repeat = int(repeat_s)
        mask = 0
        for name in rest.replace("+", "|").split("|"):
            name = name.strip().upper()
            if not name or name == "NONE":
                continue
            if name not in BUTTONS:
                raise ValueError(
                    f"알 수 없는 버튼 {name!r}. 사용 가능: " + " ".join(BUTTONS)
                )
            mask |= BUTTONS[name]
        start = int(frame_s.strip())
        for i in range(repeat):
            schedule[start + i] = schedule.get(start + i, 0) | mask
    return schedule


# --------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------


def nametable_text(nes: NES, font_base: int = -1, font_order: str = "") -> List[str]:
    """The visible nametable as 30 rows of 32 characters.

    Font tiles map back to their letters, so an agent can literally read the
    HUD.  Everything else shows as a hex-ish glyph.
    """

    base = nes.ppu.nametable_base()
    rows: List[str] = []
    for ty in range(30):
        row = []
        for tx in range(32):
            tile = nes.ppu.read_vram(base + ty * 32 + tx)
            if font_base >= 0 and font_base <= tile < font_base + len(font_order):
                row.append(font_order[tile - font_base])
            elif tile == 0:
                row.append(".")
            else:
                row.append("#")
        rows.append("".join(row))
    return rows


def frame_to_png(frame: Sequence[Sequence[int]], scale: int = 1) -> bytes:
    height = len(frame) * scale
    width = len(frame[0]) * scale
    raw = bytearray()
    for row in frame:
        line = bytearray()
        for value in row:
            r, g, b = NES_PALETTE[value & 0x3F]
            line.extend((r, g, b) * scale)
        for _ in range(scale):
            raw.append(0)
            raw.extend(line)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def frame_digest(frame: Sequence[Sequence[int]]) -> str:
    """Stable hash of a frame, for 'did the screen change?' assertions."""

    data = bytearray()
    for row in frame:
        data.extend(bytes(v & 0x3F for v in row))
    return f"{zlib.crc32(bytes(data)) & 0xFFFFFFFF:08x}"
