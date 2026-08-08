"""The generated documentation must match the code it describes.

`docs/agent/API.md`, `ASSETS.md`, `ERRORS.md` and `include/fami.h` come from
`famic/api.py`, `famic/assets.py` and `famic/diagnostics.py`.  If they drift,
an agent reading the docs is told something the compiler will not do.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from famic import api
from famic.diagnostics import ERRORS
from tools import gen_docs


class GeneratedDocTests(unittest.TestCase):
    def test_generated_docs_are_current(self):
        stale = gen_docs.main(["--check"])
        self.assertEqual(stale, 0, "python tools/gen_docs.py 를 실행하세요")


class ManifestTests(unittest.TestCase):
    def test_every_builtin_has_a_summary_and_example(self):
        for builtin in api.BUILTINS:
            with self.subTest(name=builtin.name):
                self.assertTrue(builtin.summary, "요약이 없습니다")
                self.assertTrue(builtin.example, "예시가 없습니다")
                self.assertIn(builtin.group, api.GROUPS)

    def test_manifest_is_json_serialisable(self):
        import json

        payload = json.loads(json.dumps(api.manifest(), ensure_ascii=False))
        self.assertIn("functions", payload)
        self.assertIn("assets", payload)
        self.assertIn("diagnostics", payload)
        self.assertEqual(len(payload["functions"]), len(api.BUILTINS))

    def test_every_runtime_routine_exists(self):
        """Each builtin's label must actually be emitted by some module set."""

        from famic.assets import CompiledAssets
        from famic.runtime import MODULE_DEPS, Runtime, resolve_modules

        everything = resolve_modules(set(MODULE_DEPS))
        runtime = Runtime(everything, CompiledAssets())
        text = "\n".join(runtime.routines())
        for builtin in api.BUILTINS:
            with self.subTest(name=builtin.name):
                self.assertIn(f"{builtin.label}:", text, "런타임 루틴이 없습니다")


class DiagnosticTableTests(unittest.TestCase):
    def test_codes_are_well_formed(self):
        for code in ERRORS:
            self.assertRegex(code, r"^[EW]\d{4}$")

    def test_docs_reference_every_code(self):
        text = (ROOT / "docs" / "agent" / "ERRORS.md").read_text()
        for code in ERRORS:
            self.assertIn(code, text, f"{code} 가 문서에 없습니다")


class AgentDocTests(unittest.TestCase):
    def test_agents_md_points_at_files_that_exist(self):
        import re

        text = (ROOT / "AGENTS.md").read_text()
        for path in re.findall(r"`(docs/agent/[A-Za-z]+\.md|examples/[a-z]+\.c|include/fami\.h)`", text):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).exists(), f"{path} 가 없습니다")


if __name__ == "__main__":
    unittest.main()
