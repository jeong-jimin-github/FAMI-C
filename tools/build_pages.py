#!/usr/bin/env python3
"""Generate the assets the GitHub Pages emulator serves.

GitHub Pages publishes `docs/` verbatim, so everything the page loads has to
live inside it: the example ROMs, and the JSNES sources kept in
`web-emulator/`. This script regenerates both. `--check` compares the
committed copies against freshly generated ones instead of writing, which is
what `tests/test_pages.py` uses to keep the published site from drifting away
from the compiler and the emulator it is built from.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from famic import build_file  # noqa: E402

DOCS = PROJECT_ROOT / "docs"
ROM_DIR = DOCS / "roms"
VENDOR_DIR = DOCS / "vendor" / "jsnes"
EMULATOR_ROOT = PROJECT_ROOT / "web-emulator"

#: Examples published on the site, in the order the page lists them.
EXAMPLES = ("tetris", "platformer")

#: Files copied next to the vendored sources so the Apache-2.0 notice and the
#: JSNES authorship travel with the code.
VENDOR_NOTICES = ("LICENSE", "AUTHORS.md")


def build_roms() -> dict[Path, bytes]:
    """Compile every published example and return its ROM image."""

    roms: dict[Path, bytes] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name in EXAMPLES:
            out = Path(tmp) / f"{name}.nes"
            build_file(PROJECT_ROOT / "examples" / f"{name}.c", out)
            roms[ROM_DIR / f"{name}.nes"] = out.read_bytes()
    return roms


def vendor_files() -> dict[Path, bytes]:
    """Return the JSNES files the browser loads, keyed by destination."""

    files: dict[Path, bytes] = {}
    for source in sorted((EMULATOR_ROOT / "src").rglob("*.js")):
        files[VENDOR_DIR / source.relative_to(EMULATOR_ROOT / "src")] = (
            source.read_bytes()
        )
    for name in VENDOR_NOTICES:
        files[VENDOR_DIR / name] = (EMULATOR_ROOT / name).read_bytes()
    return files


def planned_files() -> dict[Path, bytes]:
    return {**build_roms(), **vendor_files()}


def write(files: dict[Path, bytes]) -> list[Path]:
    """Write `files`, dropping stale leftovers, and return what changed."""

    changed = []
    for stale in sorted(existing_outputs() - set(files)):
        stale.unlink()
        changed.append(stale)
    for path, data in sorted(files.items()):
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        changed.append(path)
    return changed


def existing_outputs() -> set[Path]:
    """Return every file currently living in a generated directory."""

    found: set[Path] = set()
    for directory in (ROM_DIR, VENDOR_DIR):
        if directory.is_dir():
            found.update(path for path in directory.rglob("*") if path.is_file())
    return found


def differences(files: dict[Path, bytes]) -> list[str]:
    """Return one message per generated file that is missing or out of date."""

    problems = []
    for path in sorted(existing_outputs() - set(files)):
        problems.append(f"{path.relative_to(PROJECT_ROOT)} is no longer generated")
    for path, data in sorted(files.items()):
        relative = path.relative_to(PROJECT_ROOT)
        if not path.is_file():
            problems.append(f"{relative} is missing")
        elif path.read_bytes() != data:
            problems.append(f"{relative} is out of date")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed assets are up to date instead of writing them",
    )
    args = parser.parse_args(argv)

    if not (EMULATOR_ROOT / "src").is_dir():
        print(f"missing JSNES sources at {EMULATOR_ROOT / 'src'}", file=sys.stderr)
        return 1

    files = planned_files()

    if args.check:
        problems = differences(files)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            print("run: python tools/build_pages.py", file=sys.stderr)
            return 1
        print(f"{len(files)} generated files are up to date")
        return 0

    changed = write(files)
    for path in changed:
        print(f"wrote {path.relative_to(PROJECT_ROOT)}")
    print(f"{len(files)} generated files, {len(changed)} changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
