"""Two-pass 6502 assembler and iNES packager.

Beyond the original abs/imm subset this now covers zero page and the indirect
modes, which the runtime needs to walk variable-length tables (maps, songs,
metasprites) without unrolling them into code.

It also publishes a symbol table.  That table is what makes `famic watch
rom.nes --sym hero_x` possible, and that command is how an agent sees whether
its game actually works.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .diagnostics import CompileError


PRG_BASE = 0x8000
PRG_SIZE = 0x8000
PRG_VECTORS = PRG_BASE + PRG_SIZE - 6
CHR_SIZE = 0x2000

# Zero page $00-$0F is left to the runtime's pointer scratch; $10 upward is
# handed out to `.zp` requests.  $0100-$01FF is the hardware stack and
# $0200-$02FF is the shadow OAM, so general RAM starts at $0300.
ZP_BASE = 0x10
ZP_TOP = 0x100
OAM_BASE = 0x0200
RAM_BASE = 0x0300
RAM_TOP = 0x0800


MODES = ("imm", "zp", "zpx", "zpy", "abs", "absx", "absy", "ind", "indx", "indy", "acc", "rel")

OPCODES: Dict[Tuple[str, str], int] = {
    ("ADC", "imm"): 0x69, ("ADC", "zp"): 0x65, ("ADC", "zpx"): 0x75,
    ("ADC", "abs"): 0x6D, ("ADC", "absx"): 0x7D, ("ADC", "absy"): 0x79,
    ("ADC", "indx"): 0x61, ("ADC", "indy"): 0x71,
    ("AND", "imm"): 0x29, ("AND", "zp"): 0x25, ("AND", "zpx"): 0x35,
    ("AND", "abs"): 0x2D, ("AND", "absx"): 0x3D, ("AND", "absy"): 0x39,
    ("AND", "indx"): 0x21, ("AND", "indy"): 0x31,
    ("ASL", "acc"): 0x0A, ("ASL", "zp"): 0x06, ("ASL", "zpx"): 0x16,
    ("ASL", "abs"): 0x0E, ("ASL", "absx"): 0x1E,
    ("BIT", "zp"): 0x24, ("BIT", "abs"): 0x2C,
    ("BCC", "rel"): 0x90, ("BCS", "rel"): 0xB0, ("BEQ", "rel"): 0xF0,
    ("BMI", "rel"): 0x30, ("BNE", "rel"): 0xD0, ("BPL", "rel"): 0x10,
    ("BVC", "rel"): 0x50, ("BVS", "rel"): 0x70,
    ("CMP", "imm"): 0xC9, ("CMP", "zp"): 0xC5, ("CMP", "zpx"): 0xD5,
    ("CMP", "abs"): 0xCD, ("CMP", "absx"): 0xDD, ("CMP", "absy"): 0xD9,
    ("CMP", "indx"): 0xC1, ("CMP", "indy"): 0xD1,
    ("CPX", "imm"): 0xE0, ("CPX", "zp"): 0xE4, ("CPX", "abs"): 0xEC,
    ("CPY", "imm"): 0xC0, ("CPY", "zp"): 0xC4, ("CPY", "abs"): 0xCC,
    ("DEC", "zp"): 0xC6, ("DEC", "zpx"): 0xD6, ("DEC", "abs"): 0xCE, ("DEC", "absx"): 0xDE,
    ("EOR", "imm"): 0x49, ("EOR", "zp"): 0x45, ("EOR", "zpx"): 0x55,
    ("EOR", "abs"): 0x4D, ("EOR", "absx"): 0x5D, ("EOR", "absy"): 0x59,
    ("EOR", "indx"): 0x41, ("EOR", "indy"): 0x51,
    ("INC", "zp"): 0xE6, ("INC", "zpx"): 0xF6, ("INC", "abs"): 0xEE, ("INC", "absx"): 0xFE,
    ("JMP", "abs"): 0x4C, ("JMP", "ind"): 0x6C,
    ("JSR", "abs"): 0x20,
    ("LDA", "imm"): 0xA9, ("LDA", "zp"): 0xA5, ("LDA", "zpx"): 0xB5,
    ("LDA", "abs"): 0xAD, ("LDA", "absx"): 0xBD, ("LDA", "absy"): 0xB9,
    ("LDA", "indx"): 0xA1, ("LDA", "indy"): 0xB1,
    ("LDX", "imm"): 0xA2, ("LDX", "zp"): 0xA6, ("LDX", "zpy"): 0xB6,
    ("LDX", "abs"): 0xAE, ("LDX", "absy"): 0xBE,
    ("LDY", "imm"): 0xA0, ("LDY", "zp"): 0xA4, ("LDY", "zpx"): 0xB4,
    ("LDY", "abs"): 0xAC, ("LDY", "absx"): 0xBC,
    ("LSR", "acc"): 0x4A, ("LSR", "zp"): 0x46, ("LSR", "zpx"): 0x56,
    ("LSR", "abs"): 0x4E, ("LSR", "absx"): 0x5E,
    ("ORA", "imm"): 0x09, ("ORA", "zp"): 0x05, ("ORA", "zpx"): 0x15,
    ("ORA", "abs"): 0x0D, ("ORA", "absx"): 0x1D, ("ORA", "absy"): 0x19,
    ("ORA", "indx"): 0x01, ("ORA", "indy"): 0x11,
    ("ROL", "acc"): 0x2A, ("ROL", "zp"): 0x26, ("ROL", "zpx"): 0x36,
    ("ROL", "abs"): 0x2E, ("ROL", "absx"): 0x3E,
    ("ROR", "acc"): 0x6A, ("ROR", "zp"): 0x66, ("ROR", "zpx"): 0x76,
    ("ROR", "abs"): 0x6E, ("ROR", "absx"): 0x7E,
    ("SBC", "imm"): 0xE9, ("SBC", "zp"): 0xE5, ("SBC", "zpx"): 0xF5,
    ("SBC", "abs"): 0xED, ("SBC", "absx"): 0xFD, ("SBC", "absy"): 0xF9,
    ("SBC", "indx"): 0xE1, ("SBC", "indy"): 0xF1,
    ("STA", "zp"): 0x85, ("STA", "zpx"): 0x95, ("STA", "abs"): 0x8D,
    ("STA", "absx"): 0x9D, ("STA", "absy"): 0x99,
    ("STA", "indx"): 0x81, ("STA", "indy"): 0x91,
    ("STX", "zp"): 0x86, ("STX", "zpy"): 0x96, ("STX", "abs"): 0x8E,
    ("STY", "zp"): 0x84, ("STY", "zpx"): 0x94, ("STY", "abs"): 0x8C,
}

IMPLIED = {
    "BRK": 0x00, "CLC": 0x18, "CLD": 0xD8, "CLI": 0x58, "CLV": 0xB8,
    "DEX": 0xCA, "DEY": 0x88, "INX": 0xE8, "INY": 0xC8, "NOP": 0xEA,
    "PHA": 0x48, "PHP": 0x08, "PLA": 0x68, "PLP": 0x28, "RTI": 0x40,
    "RTS": 0x60, "SEC": 0x38, "SED": 0xF8, "SEI": 0x78, "TAX": 0xAA,
    "TAY": 0xA8, "TSX": 0xBA, "TXA": 0x8A, "TXS": 0x9A, "TYA": 0x98,
}

BRANCHES = {"BCC", "BCS", "BEQ", "BMI", "BNE", "BPL", "BVC", "BVS"}

# Instructions with no zero-page form; a symbol in low memory still has to be
# encoded as absolute.
NO_ZP = {"JMP", "JSR"}


@dataclass
class AsmLine:
    label: Optional[str]
    op: Optional[str]
    operand: str
    source_line: int


class Assembler:
    def __init__(self) -> None:
        self.symbols: Dict[str, int] = {}
        self.ram_symbols: Dict[str, int] = {}
        self.zp_pc = ZP_BASE
        self.ram_pc = RAM_BASE
        self.pc = PRG_BASE
        self.bytes_written = 0

    # -- driver ------------------------------------------------------------

    def assemble(self, asm: str) -> bytes:
        lines = self.parse_lines(asm)
        self.allocate_ram(lines)
        self.pass1(lines)
        return self.pass2(lines)

    def parse_lines(self, asm: str) -> List[AsmLine]:
        out: List[AsmLine] = []
        for num, raw in enumerate(asm.splitlines(), 1):
            text = raw.split(";", 1)[0].strip()
            if not text:
                continue
            label = None
            if ":" in text and not text.startswith("."):
                before, after = text.split(":", 1)
                if before.strip():
                    label = before.strip()
                    text = after.strip()
                else:
                    raise CompileError("E0701", f"asm {num}: 빈 라벨")
            if not text:
                out.append(AsmLine(label, None, "", num))
                continue
            parts = text.split(None, 1)
            op = parts[0].upper()
            operand = parts[1].strip() if len(parts) > 1 else ""
            out.append(AsmLine(label, op, operand, num))
        return out

    def allocate_ram(self, lines: Sequence[AsmLine]) -> None:
        """Assign every `.zp`/`.ram` name up front.

        Doing this before sizing means an operand's zero-page-ness is already
        known in pass 1, so the two passes cannot disagree about an
        instruction's length.
        """

        for line in lines:
            if line.op == ".SET":
                # A pure symbol definition; used to publish compile-time facts
                # (the font's CHR base, for one) into the symbol table so the
                # emulator tooling can read them back.
                parts = line.operand.split()
                if len(parts) != 2:
                    raise CompileError("E0701", f"asm {line.source_line}: .set 이름 값")
                self.symbols[parts[0]] = int(parts[1], 0)
                continue
            if line.op not in (".ZP", ".RAM"):
                continue
            parts = line.operand.split()
            if len(parts) != 2:
                raise CompileError("E0701", f"asm {line.source_line}: {line.op.lower()} 이름 크기")
            name, size_s = parts
            size = int(size_s, 0)
            if name in self.symbols:
                raise CompileError("E0701", f"asm {line.source_line}: 중복 심볼 {name}")
            if line.op == ".ZP":
                if self.zp_pc + size > ZP_TOP:
                    raise CompileError(
                        "E0309",
                        "제로페이지가 가득 찼습니다",
                        hint="런타임 내부 문제입니다. 사용하는 기능을 줄여 보세요.",
                    )
                self.symbols[name] = self.zp_pc
                self.zp_pc += size
            else:
                if self.ram_pc + size > RAM_TOP:
                    used = self.ram_pc - RAM_BASE
                    raise CompileError(
                        "E0309",
                        f"NES 내부 RAM {RAM_TOP - RAM_BASE}바이트를 넘었습니다 ({used}바이트 사용, {size}바이트 추가 요청: {name})",
                        hint=(
                            "전역 배열을 줄이거나, u16 를 u8 로 바꾸거나, "
                            "동시에 쓰지 않는 배열을 하나로 합치세요."
                        ),
                    )
                self.symbols[name] = self.ram_pc
                self.ram_pc += size
            self.ram_symbols[name] = self.symbols[name]

    def pass1(self, lines: Sequence[AsmLine]) -> None:
        self.pc = PRG_BASE
        for line in lines:
            if line.op in (".ZP", ".RAM", ".SET"):
                continue
            if line.label:
                if line.label in self.symbols:
                    raise CompileError("E0701", f"asm {line.source_line}: 중복 심볼 {line.label}")
                self.symbols[line.label] = self.pc
            if line.op is None:
                continue
            if line.op == ".ORG":
                self.pc = self.eval_value(line.operand, line)
            elif line.op == ".BYTE":
                self.pc += len(self.split_operands(line.operand))
            elif line.op == ".WORD":
                self.pc += 2 * len(self.split_operands(line.operand))
            else:
                self.pc += self.instruction_size(line)

    def pass2(self, lines: Sequence[AsmLine]) -> bytes:
        self.pc = PRG_BASE
        self.bytes_written = 0
        prg = bytearray([0xFF] * PRG_SIZE)
        for line in lines:
            if line.op is None or line.op in (".ZP", ".RAM", ".SET"):
                continue
            if line.op == ".ORG":
                self.pc = self.eval_value(line.operand, line)
            elif line.op == ".BYTE":
                for operand in self.split_operands(line.operand):
                    self.write_byte(prg, self.eval_value(operand, line) & 0xFF, line)
            elif line.op == ".WORD":
                for operand in self.split_operands(line.operand):
                    value = self.eval_value(operand, line) & 0xFFFF
                    self.write_byte(prg, value & 0xFF, line)
                    self.write_byte(prg, (value >> 8) & 0xFF, line)
            else:
                self.write_instruction(prg, line)
        return bytes(prg)

    # -- encoding ----------------------------------------------------------

    def instruction_size(self, line: AsmLine) -> int:
        mnemonic = line.op or ""
        if mnemonic in IMPLIED:
            return 1
        if mnemonic in BRANCHES:
            return 2
        mode, _ = self.addressing_mode(mnemonic, line.operand, line)
        if mode == "acc":
            return 1
        if mode in ("imm", "zp", "zpx", "zpy", "indx", "indy"):
            return 2
        return 3

    def write_instruction(self, prg: bytearray, line: AsmLine) -> None:
        mnemonic = line.op or ""
        if mnemonic in IMPLIED:
            self.write_byte(prg, IMPLIED[mnemonic], line)
            return
        if mnemonic in BRANCHES:
            opcode = OPCODES[(mnemonic, "rel")]
            target = self.eval_value(line.operand, line)
            offset = target - (self.pc + 2)
            if not -128 <= offset <= 127:
                raise CompileError(
                    "E0703",
                    f"asm {line.source_line}: 분기 거리 {offset} 가 -128~127 을 벗어났습니다",
                    hint="런타임 내부 문제입니다. 이 메시지를 그대로 보고하세요.",
                )
            self.write_byte(prg, opcode, line)
            self.write_byte(prg, offset & 0xFF, line)
            return
        mode, operand = self.addressing_mode(mnemonic, line.operand, line)
        key = (mnemonic, mode)
        if key not in OPCODES:
            raise CompileError(
                "E0701",
                f"asm {line.source_line}: {mnemonic} 에 {mode} 주소지정은 없습니다 ({line.operand})",
            )
        self.write_byte(prg, OPCODES[key], line)
        if mode == "acc":
            return
        value = self.eval_value(operand, line)
        if mode in ("imm", "zp", "zpx", "zpy", "indx", "indy"):
            self.write_byte(prg, value & 0xFF, line)
        else:
            self.write_byte(prg, value & 0xFF, line)
            self.write_byte(prg, (value >> 8) & 0xFF, line)

    def addressing_mode(self, mnemonic: str, operand: str, line: AsmLine) -> Tuple[str, str]:
        operand = operand.strip()
        if operand == "" or operand.upper() == "A":
            return "acc", ""
        if operand.startswith("#"):
            return "imm", operand[1:].strip()
        if operand.startswith("("):
            body = operand
            if body.upper().endswith("),Y"):
                return "indy", body[1:-3].strip()
            if body.upper().endswith(",X)"):
                return "indx", body[1:-3].strip()
            if body.endswith(")"):
                return "ind", body[1:-1].strip()
            raise CompileError("E0701", f"asm {line.source_line}: 잘못된 간접 주소지정 {operand}")
        upper = operand.upper()
        if upper.endswith(",X"):
            inner = operand[:-2].strip()
            return ("zpx" if self.is_zero_page(mnemonic, inner) else "absx"), inner
        if upper.endswith(",Y"):
            inner = operand[:-2].strip()
            return ("zpy" if self.is_zero_page(mnemonic, inner, "zpy") else "absy"), inner
        return ("zp" if self.is_zero_page(mnemonic, operand) else "abs"), operand

    def is_zero_page(self, mnemonic: str, operand: str, mode: str = "zp") -> bool:
        if mnemonic in NO_ZP:
            return False
        name = operand.strip()
        if name.startswith(("<", ">")):
            return False
        value: Optional[int] = None
        if name in self.ram_symbols:
            value = self.ram_symbols[name]
        elif name.startswith("$"):
            try:
                value = int(name[1:], 16)
            except ValueError:
                return False
        elif name.isdigit():
            value = int(name, 10)
        if value is None or value >= 0x100:
            return False
        variant = {"zp": "zp", "zpy": "zpy"}[mode]
        if variant == "zp" and operand.strip().upper().endswith(",X"):
            variant = "zpx"
        return (mnemonic, variant) in OPCODES or (mnemonic, "zp") in OPCODES

    # -- values ------------------------------------------------------------

    def split_operands(self, operand: str) -> List[str]:
        return [part.strip() for part in operand.split(",") if part.strip()]

    def eval_value(self, text: str, line: Optional[AsmLine] = None) -> int:
        text = text.strip()
        if text.startswith("<"):
            return self.eval_value(text[1:], line) & 0xFF
        if text.startswith(">"):
            return (self.eval_value(text[1:], line) >> 8) & 0xFF
        for op in ("+", "-"):
            # Only split on a trailing `sym + n` form; labels never contain these.
            idx = text.rfind(op)
            if idx > 0:
                left, right = text[:idx].strip(), text[idx + 1 :].strip()
                if left and right and not left.endswith(("<", ">", "+", "-")):
                    a = self.eval_value(left, line)
                    b = self.eval_value(right, line)
                    return a + b if op == "+" else a - b
        if text.startswith("$"):
            return int(text[1:], 16)
        if text.startswith("%"):
            return int(text[1:], 2)
        if text.lower().startswith("0x"):
            return int(text, 16)
        if text.lstrip("-").isdigit():
            return int(text, 10)
        if text in self.symbols:
            return self.symbols[text]
        where = f"asm {line.source_line}: " if line else ""
        raise CompileError(
            "E0704",
            f"{where}알 수 없는 심볼 {text!r}",
            hint="런타임 내부 문제입니다. 이 메시지를 그대로 보고하세요.",
        )

    def write_byte(self, prg: bytearray, value: int, line: Optional[AsmLine] = None) -> None:
        if not PRG_BASE <= self.pc <= PRG_BASE + PRG_SIZE - 1:
            raise CompileError(
                "E0702",
                f"코드가 32K PRG ROM 밖(${self.pc:04X})으로 넘쳤습니다",
                hint=(
                    "프로그램이 32KB를 넘었습니다. asset 데이터(맵/곡/타일)를 줄이거나 "
                    "함수를 합치세요."
                ),
            )
        prg[self.pc - PRG_BASE] = value & 0xFF
        self.pc += 1
        self.bytes_written += 1

    # -- output ------------------------------------------------------------

    def symbol_table(self) -> Dict[str, int]:
        return dict(self.symbols)

    def ram_usage(self) -> Dict[str, int]:
        return {
            "prg_used": self.bytes_written,
            "prg_free": PRG_SIZE - self.bytes_written,
            "zp_used": self.zp_pc - ZP_BASE,
            "zp_free": ZP_TOP - self.zp_pc,
            "ram_used": self.ram_pc - RAM_BASE,
            "ram_free": RAM_TOP - self.ram_pc,
        }


def make_ines(prg: bytes, chr_rom: bytes) -> bytes:
    """NROM-256, vertical mirroring, one 8K CHR bank."""

    if len(prg) != PRG_SIZE:
        raise CompileError("E0702", f"PRG 크기가 {len(prg)} 입니다 ({PRG_SIZE} 이어야 함)")
    if len(chr_rom) != CHR_SIZE:
        raise CompileError("E0702", f"CHR 크기가 {len(chr_rom)} 입니다 ({CHR_SIZE} 이어야 함)")
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4] = PRG_SIZE // 0x4000
    header[5] = CHR_SIZE // 0x2000
    header[6] = 0x01  # vertical mirroring, mapper 0 low nibble
    return bytes(header) + prg + chr_rom
