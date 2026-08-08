#!/usr/bin/env python3
"""Generate the reference docs that must not drift from the code.

`docs/agent/API.md`, `docs/agent/ASSETS.md` and `docs/agent/ERRORS.md` are
produced from `famic/api.py`, `famic/assets.py` and `famic/diagnostics.py`.
Hand-editing them would let the documentation and the compiler disagree, and
an agent has no way to tell which one is lying.

    python tools/gen_docs.py            # write
    python tools/gen_docs.py --check    # fail if the committed copies drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from famic import api
from famic.assets import ASSET_KIND_DOCS, FONT_ORDER, note_constants
from famic.diagnostics import ERRORS

OUT = ROOT / "docs" / "agent"

HEADER = "<!-- 이 파일은 tools/gen_docs.py 가 생성합니다. 직접 고치지 마세요. -->\n"


def api_md() -> str:
    lines = [HEADER, "# 런타임 API 레퍼런스", ""]
    lines.append("`#include <fami.h>` 후 그냥 호출한다. **따로 선언하지 않는다.**")
    lines.append("호출하면 해당 런타임이 ROM에 포함된다.")
    lines.append("")
    lines.append("기계 판독 형식: `python famic.py api --json`")
    lines.append("")

    lines.append("## 목차")
    lines.append("")
    for group, title in api.GROUPS.items():
        members = [b for b in api.BUILTINS if b.group == group]
        if members:
            names = ", ".join(f"`{b.name}`" for b in members)
            lines.append(f"- **{title}** — {names}")
    lines.append("")

    for group, title in api.GROUPS.items():
        members = [b for b in api.BUILTINS if b.group == group]
        if not members:
            continue
        lines.append(f"## {title}")
        lines.append("")
        for b in members:
            lines.append(f"### `{b.signature()}`")
            lines.append("")
            lines.append(b.summary)
            lines.append("")
            if b.params:
                lines.append("| 인자 | 타입 |")
                lines.append("|------|------|")
                for name, ptype in b.params:
                    shown = "문자열 리터럴" if ptype is api.STR else f"`{ptype}`"
                    lines.append(f"| `{name}` | {shown} |")
                lines.append("")
            lines.append("```c")
            lines.append(b.example)
            lines.append("```")
            lines.append("")
            if b.notes:
                lines.append(f"> {b.notes}")
                lines.append("")

    lines.append("## 상수")
    lines.append("")
    lines.append("| 이름 | 값 | 설명 |")
    lines.append("|------|-----|------|")
    for name, value, summary, as_hex in api.CONSTANTS:
        shown = f"`0x{value:02X}`" if as_hex else f"`{value}`"
        lines.append(f"| `{name}` | {shown} | {summary} |")
    lines.append("")

    lines.append("## 음 이름")
    lines.append("")
    lines.append("`asset sfx` 와 `asset song` 에서 쓴다. `0` 은 쉼표, `HOLD` 는 앞 음 유지.")
    lines.append("")
    notes = [n for n, _ in note_constants() if n.startswith("N_")]
    lines.append("```")
    for i in range(0, len(notes), 12):
        lines.append(" ".join(notes[i : i + 12]))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def assets_md() -> str:
    lines = [HEADER, "# asset 선언 레퍼런스", ""]
    lines.append("그래픽·팔레트·맵·사운드를 게임 코드와 같은 `.c` 파일에 선언한다.")
    lines.append("에셋 이름은 **컴파일 시각 `u8` 상수**가 되고, 값은 컴파일러가 정한다.")
    lines.append("")
    lines.append("규칙 두 가지:")
    lines.append("")
    lines.append("1. 에셋은 **자기보다 위에 선언된** 에셋만 참조할 수 있다.")
    lines.append("2. 타일 인덱스는 배경과 스프라이트가 **공유**한다 (총 256장).")
    lines.append("")
    for doc in ASSET_KIND_DOCS:
        lines.append(f"## `asset {doc['kind']}`")
        lines.append("")
        lines.append(f"```c\n{doc['syntax']}\n```")
        lines.append("")
        lines.append(doc["summary"])
        lines.append("")
        lines.append("```c")
        lines.append(doc["example"])
        lines.append("```")
        lines.append("")

    lines.append("## 내장 폰트")
    lines.append("")
    lines.append("`bg_text` / `bg_number` / `bg_char` 를 쓰거나 소스에 문자열이 있으면")
    lines.append(f"폰트 타일 {len(FONT_ORDER)}장이 자동으로 CHR에 들어간다. 쓸 수 있는 글자:")
    lines.append("")
    lines.append("```")
    lines.append(FONT_ORDER)
    lines.append("```")
    lines.append("")
    lines.append("소문자는 대문자로 바뀐다. 목록에 없는 글자는 컴파일 에러(`E0602`)다.")
    lines.append("")
    return "\n".join(lines)


def errors_md() -> str:
    groups = {
        "E01": "렉서 / 전처리기",
        "E02": "문법",
        "E03": "선언과 저장",
        "E04": "타입과 식",
        "E05": "asset",
        "E06": "런타임 API 사용",
        "E07": "어셈블러 / ROM 크기",
        "W09": "경고 (빌드는 계속된다)",
    }
    lines = [HEADER, "# 진단 코드", ""]
    lines.append("모든 진단은 **코드 · 파일 · 행 · 열 · 힌트**를 가진다.")
    lines.append("힌트를 그대로 따르면 고쳐진다. 힌트가 틀렸다면 그건 툴체인의 버그다.")
    lines.append("")
    lines.append("`--json` 을 붙이면 stdout 은 다음 형태의 JSON 만 낸다:")
    lines.append("")
    lines.append("```json")
    lines.append('{"ok": false, "diagnostics": [{"code":"E0301","severity":"error",')
    lines.append(' "file":"game.c","line":42,"col":12,"title":"...","message":"...","hint":"..."}]}')
    lines.append("```")
    lines.append("")
    for prefix, title in groups.items():
        rows = [(c, t) for c, t in sorted(ERRORS.items()) if c.startswith(prefix)]
        if not rows:
            continue
        lines.append(f"## {prefix}xx — {title}")
        lines.append("")
        lines.append("| 코드 | 뜻 |")
        lines.append("|------|-----|")
        for code, text in rows:
            lines.append(f"| <a id=\"{code.lower()}\"></a>`{code}` | {text} |")
        lines.append("")
    return "\n".join(lines)


TARGETS = {
    "API.md": api_md,
    "ASSETS.md": assets_md,
    "ERRORS.md": errors_md,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="쓰지 않고 차이만 보고")
    args = parser.parse_args(argv)

    stale = []
    for name, render in TARGETS.items():
        path = OUT / name
        text = render()
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote docs/agent/{name}")

    header_path = ROOT / "include" / "fami.h"
    header_text = api.generate_header()
    if args.check:
        if not header_path.exists() or header_path.read_text() != header_text:
            stale.append("include/fami.h")
    else:
        header_path.write_text(header_text)
        print("wrote include/fami.h")

    if stale:
        print("stale: " + ", ".join(stale), file=sys.stderr)
        print("실행: python tools/gen_docs.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
