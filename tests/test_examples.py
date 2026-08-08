"""The example games must build and actually play.

`tests/specs/*.spec.json` are the same scenarios `python famic.py test` runs.
Keeping them in the unittest suite means a change to the compiler that breaks
gameplay fails here, not on someone's screen.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from famic.assets import FONT_ORDER
from famic.compiler import build_file
from famic.emu import NES, BUTTONS, Crash, nametable_text

BUILD = ROOT / "build"
EXAMPLES = ("platformer", "tetris")


def build_example(name: str):
    return build_file(ROOT / "examples" / f"{name}.c", BUILD / f"{name}.nes")


class ExampleBuildTests(unittest.TestCase):
    def test_examples_build_within_budget(self):
        for name in EXAMPLES:
            with self.subTest(example=name):
                result = build_example(name)
                self.assertLessEqual(result.info["tiles_used"], 256)
                self.assertGreater(result.info["ram_free"], 0)
                self.assertGreater(result.info["zp_free"], 0)
                self.assertEqual(result.warnings, [], "예제는 경고 없이 빌드되어야 합니다")

    def test_title_screens_are_readable(self):
        expected = {"platformer": "PLATFORMER", "tetris": "BLOCKS"}
        for name in EXAMPLES:
            with self.subTest(example=name):
                result = build_example(name)
                nes = NES(result.rom, result.symbols)
                for _ in range(30):
                    nes.run_frame()
                rows = nametable_text(nes, result.symbols["__font_base"], FONT_ORDER)
                screen = "\n".join(rows)
                self.assertIn(expected[name], screen)
                self.assertIn("PRESS START", screen)


class SpecTests(unittest.TestCase):
    """Run every declarative gameplay scenario."""

    def run_spec(self, path: Path):
        spec = json.loads(path.read_text())
        rom_path = (path.parent / spec["rom"]).resolve()
        if not rom_path.exists():
            build_example(rom_path.stem)
        symbols = {}
        sym_path = rom_path.with_suffix(".sym")
        if sym_path.exists():
            from famic.compiler import load_symbols

            symbols = load_symbols(sym_path)
        nes = NES(rom_path.read_bytes(), symbols)

        frame = 0
        for step in spec.get("steps", []):
            buttons = 0
            for name in step.get("input", []):
                buttons |= BUTTONS[name.upper()]
            for _ in range(step.get("frames", 1)):
                nes.set_pad(0, buttons)
                try:
                    nes.run_frame()
                except Crash as exc:
                    self.fail(f"{path.name} frame {frame}: {exc}")
                frame += 1
            for symbol, condition in step.get("assert", {}).items():
                name, width = (symbol[:-3], 2) if symbol.endswith(":16") else (symbol, 1)
                value = nes.peek(name, width)
                if not isinstance(condition, dict):
                    condition = {"eq": condition}
                for op, expected in condition.items():
                    ok = {
                        "eq": value == expected,
                        "ne": value != expected,
                        "gt": value > expected,
                        "ge": value >= expected,
                        "lt": value < expected,
                        "le": value <= expected,
                    }[op]
                    self.assertTrue(
                        ok, f"{path.name} frame {frame}: {name} = {value}, 기대 {op} {expected}"
                    )

    def test_specs(self):
        specs = sorted((ROOT / "tests" / "specs").glob("*.spec.json"))
        self.assertTrue(specs, "실행할 시나리오가 없습니다")
        for path in specs:
            with self.subTest(spec=path.name):
                self.run_spec(path)


if __name__ == "__main__":
    unittest.main()
