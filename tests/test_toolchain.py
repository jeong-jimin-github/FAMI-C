import tempfile
import unittest
from pathlib import Path

from famic import Assembler, build_rom, compile_c_to_asm, make_chr, make_ines


ROOT = Path(__file__).resolve().parents[1]


class ToolchainTests(unittest.TestCase):
    def test_smoke_compiles_to_prg(self):
        source = (ROOT / "tests" / "smoke.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(source)
        assembler = Assembler()
        prg = assembler.assemble(asm)

        self.assertEqual(len(prg), 0x4000)
        reset = prg[0x3FFC] | (prg[0x3FFD] << 8)
        self.assertEqual(reset, 0x8000)
        ram_symbols = [addr for addr in assembler.symbols.values() if addr < 0x0800]
        self.assertTrue(ram_symbols)
        self.assertTrue(all(not 0x0100 <= addr < 0x0200 for addr in ram_symbols))

    def test_tetris_builds_mapper0_ines_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tetris.nes"
            asm = Path(tmp) / "tetris.asm"
            build_rom(ROOT / "examples" / "tetris.c", out, asm)
            rom = out.read_bytes()

        self.assertEqual(rom[:4], b"NES\x1A")
        self.assertEqual(rom[4], 1)
        self.assertEqual(rom[5], 1)
        self.assertEqual(rom[6], 0)
        self.assertEqual(rom[7], 0)
        self.assertEqual(len(rom), 16 + 0x4000 + 0x2000)

    def test_tetris_ram_does_not_overlap_6502_stack(self):
        source = (ROOT / "examples" / "tetris.c").read_text(encoding="utf-8")
        asm = compile_c_to_asm(source)
        assembler = Assembler()
        assembler.assemble(asm)

        stack_page_symbols = [
            name
            for name, addr in assembler.symbols.items()
            if 0x0100 <= addr < 0x0200
        ]
        self.assertEqual(stack_page_symbols, [])

    def test_packager_rejects_wrong_bank_sizes(self):
        with self.assertRaises(Exception):
            make_ines(b"", make_chr())


if __name__ == "__main__":
    unittest.main()
