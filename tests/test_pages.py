"""Checks for the GitHub Pages site and the browser emulator it ships."""

import re
import unittest
from pathlib import Path

from famic.assembler import CHR_SIZE, PRG_SIZE

from tools import build_pages


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "index.html"


def index_html():
    return INDEX.read_text(encoding="utf-8")


def local_references(html):
    """Return every same-origin URL the page asks the browser to fetch."""

    attributes = re.findall(r'(?:src|href|data-rom)="([^"]+)"', html)
    return [
        url
        for url in attributes
        if not url.startswith(("http://", "https://", "#", "data:", "mailto:"))
    ]


def module_imports(source):
    return re.findall(r'(?:from|import)\s+"([^"]+)"', source)


class GeneratedAssetTest(unittest.TestCase):
    def test_published_assets_match_their_sources(self):
        """docs/ must hold the ROMs this compiler builds and the bundled JSNES."""

        problems = build_pages.differences(build_pages.planned_files())
        self.assertEqual(problems, [], "run: python tools/build_pages.py")

    def test_published_roms_are_ines_images(self):
        for name in build_pages.EXAMPLES:
            with self.subTest(rom=name):
                rom = (build_pages.ROM_DIR / f"{name}.nes").read_bytes()
                self.assertEqual(rom[:4], b"NES\x1a")
                self.assertEqual(len(rom), 16 + PRG_SIZE + CHR_SIZE)
                self.assertEqual(rom[6] >> 4, 0, "examples are mapper 0")
                self.assertEqual(rom[7] >> 4, 0)

    def test_vendored_licence_travels_with_the_code(self):
        licence = (build_pages.VENDOR_DIR / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Apache License", licence)
        self.assertIn("vendor/jsnes/LICENSE", index_html())


class PageTest(unittest.TestCase):
    def test_local_references_exist(self):
        """Every stylesheet, script and ROM the page names must be published."""

        for url in local_references(index_html()):
            with self.subTest(url=url):
                self.assertTrue((DOCS / url).is_file(), f"docs/{url} is missing")

    def test_emulator_module_graph_resolves(self):
        """The page loads JSNES unbundled, so every import must resolve on disk."""

        pending = [DOCS / "emulator.js"]
        seen = set()
        while pending:
            module = pending.pop().resolve()
            if module in seen:
                continue
            seen.add(module)
            self.assertTrue(module.is_file(), f"{module} is missing")
            for target in module_imports(module.read_text(encoding="utf-8")):
                self.assertTrue(
                    target.startswith("."),
                    f"{module.name} imports {target} from the network",
                )
                pending.append(module.parent / target)

        self.assertIn((build_pages.VENDOR_DIR / "nes.js").resolve(), seen)

    def test_emulator_markup_is_wired_to_the_script(self):
        html = index_html()
        self.assertIn('<script type="module" src="emulator.js">', html)
        for hook in (
            "data-emulator",
            'data-role="stage"',
            'data-role="overlay"',
            'data-role="status"',
            'data-role="volume"',
            'data-role="file"',
            'data-action="pause"',
            'data-action="reset"',
            'data-action="fullscreen"',
        ):
            with self.subTest(hook=hook):
                self.assertIn(hook, html)

    def test_every_published_rom_has_a_button(self):
        html = index_html()
        for name in build_pages.EXAMPLES:
            with self.subTest(rom=name):
                self.assertIn(f'data-rom="roms/{name}.nes"', html)

    def test_touch_pad_covers_the_whole_controller(self):
        html = index_html()
        for button in ("up", "down", "left", "right", "a", "b", "start", "select"):
            with self.subTest(button=button):
                self.assertIn(f'data-button="{button}"', html)


if __name__ == "__main__":
    unittest.main()
