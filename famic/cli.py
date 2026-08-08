"""Command line interface.

Every command takes `--json`, and with it stdout carries JSON and nothing
else.  That is the contract an agent codes against: run a command, parse the
result, decide the next edit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import api
from .assets import FONT_ORDER
from .compiler import BuildResult, build_file, compile_source, load_symbols
from .diagnostics import CompileError, ERRORS
from .emu import NES, Crash, frame_digest, frame_to_png, nametable_text, parse_input_script


ROOT = Path(__file__).resolve().parent.parent


def _fail(diag_dict: Dict[str, object], as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ok": False, "diagnostics": [diag_dict]}, ensure_ascii=False, indent=2))
    else:
        code = diag_dict["code"]
        where = f"{diag_dict['file']}:{diag_dict['line']}:{diag_dict['col']}"
        print(f"{where}: error {code}: {diag_dict['message']}", file=sys.stderr)
        if diag_dict.get("hint"):
            print(f"  힌트: {diag_dict['hint']}", file=sys.stderr)
        print(f"  자세히: docs/agent/ERRORS.md#{str(code).lower()}", file=sys.stderr)
    return 1


def _report(result: BuildResult, as_json: bool, extra: Optional[Dict[str, object]] = None) -> int:
    payload = result.to_dict()
    if extra:
        payload.update(extra)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    for warning in result.warnings:
        print(warning.format(), file=sys.stderr)
    used = payload.get("prg_used", 0)
    print(
        f"OK  PRG {used}/32768 바이트  타일 {payload['tiles_used']}/256  "
        f"RAM {payload['ram_used']}/{payload['ram_used'] + payload['ram_free']}  "
        f"ZP {payload['zp_used']}/{payload['zp_used'] + payload['zp_free']}"
    )
    if extra and extra.get("output"):
        print(f"    -> {extra['output']}")
    return 0


# --------------------------------------------------------------------------
# build / check / asm
# --------------------------------------------------------------------------


def cmd_build(args: argparse.Namespace) -> int:
    source = Path(args.source)
    out = Path(args.output) if args.output else Path("build") / (source.stem + ".nes")
    asm = Path(args.asm) if args.asm else None
    try:
        result = build_file(source, out, asm)
    except CompileError as exc:
        return _fail(exc.diagnostic.to_dict(), args.json)
    return _report(result, args.json, {"output": str(out), "symbols": str(out.with_suffix(".sym"))})


def cmd_check(args: argparse.Namespace) -> int:
    source = Path(args.source)
    try:
        result = compile_source(source.read_text(), str(source))
    except CompileError as exc:
        return _fail(exc.diagnostic.to_dict(), args.json)
    return _report(result, args.json)


def cmd_asm(args: argparse.Namespace) -> int:
    source = Path(args.source)
    try:
        result = compile_source(source.read_text(), str(source))
    except CompileError as exc:
        return _fail(exc.diagnostic.to_dict(), args.json)
    if args.output:
        Path(args.output).write_text(result.asm)
        return _report(result, args.json, {"output": args.output})
    print(result.asm)
    return 0


# --------------------------------------------------------------------------
# api / header / errors
# --------------------------------------------------------------------------


def cmd_api(args: argparse.Namespace) -> int:
    manifest = api.manifest()
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    for group, title in api.GROUPS.items():
        members = [b for b in api.BUILTINS if b.group == group]
        if not members:
            continue
        print(f"\n== {title} ==")
        for b in members:
            print(f"  {b.signature()}")
            print(f"      {b.summary}")
    print("\n== 상수 ==")
    for name, value, summary, _ in api.CONSTANTS:
        print(f"  {name:<16} {value:<5} {summary}")
    return 0


def cmd_header(args: argparse.Namespace) -> int:
    path = ROOT / "include" / "fami.h"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(api.generate_header())
    if args.json:
        print(json.dumps({"ok": True, "output": str(path)}, ensure_ascii=False))
    else:
        print(f"wrote {path}")
    return 0


def cmd_errors(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps([{"code": c, "title": t} for c, t in sorted(ERRORS.items())],
                         ensure_ascii=False, indent=2))
        return 0
    for code, title in sorted(ERRORS.items()):
        print(f"{code}  {title}")
    return 0


# --------------------------------------------------------------------------
# run / screen / watch / test
# --------------------------------------------------------------------------


def _load_machine(rom_path: Path) -> NES:
    symbols = load_symbols(rom_path.with_suffix(".sym"))
    return NES(rom_path.read_bytes(), symbols)


def _run_frames(nes: NES, frames: int, schedule: Dict[int, int]) -> Optional[str]:
    for frame in range(frames):
        nes.set_pad(0, schedule.get(frame, 0))
        try:
            nes.run_frame()
        except Crash as exc:
            return str(exc)
    return None


def cmd_run(args: argparse.Namespace) -> int:
    rom_path = Path(args.rom)
    nes = _load_machine(rom_path)
    schedule = parse_input_script(args.input) if args.input else {}
    crash = _run_frames(nes, args.frames, schedule)
    frame = nes.ppu.render()
    watches: Dict[str, int] = {}
    for spec in _watch_names(args.sym):
        name, width = (spec[:-3], 2) if spec.endswith(":16") else (spec, 1)
        try:
            watches[spec] = nes.peek(name, width)
        except KeyError:
            watches[spec] = -1
    payload: Dict[str, object] = {
        "ok": crash is None,
        "frames": args.frames,
        "crash": crash,
        "screen_digest": frame_digest(frame),
        "rendering": nes.ppu.rendering,
        "sprites": (
            sum(1 for i in range(64) if nes.ppu.oam[i * 4] < 0xEF)
            if nes.ppu.mask & 0x10
            else 0
        ),
        "watch": watches,
    }
    if args.screenshot:
        Path(args.screenshot).write_bytes(frame_to_png(frame, args.scale))
        payload["screenshot"] = args.screenshot
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"frames={args.frames} sprites={payload['sprites']} digest={payload['screen_digest']}")
        for name, value in watches.items():
            print(f"  {name} = {value}")
        if crash:
            print(f"CRASH: {crash}", file=sys.stderr)
    return 0 if crash is None else 1


def _watch_names(spec: Optional[str]) -> List[str]:
    if not spec:
        return []
    return [s.strip() for s in spec.split(",") if s.strip()]


def cmd_screen(args: argparse.Namespace) -> int:
    rom_path = Path(args.rom)
    nes = _load_machine(rom_path)
    schedule = parse_input_script(args.input) if args.input else {}
    crash = _run_frames(nes, args.frames, schedule)
    font_base = nes.symbols.get("__font_base", -1)
    rows = nametable_text(nes, font_base, FONT_ORDER)
    if args.json:
        print(json.dumps({"ok": crash is None, "crash": crash, "rows": rows},
                         ensure_ascii=False, indent=2))
    else:
        print("+" + "-" * 32 + "+")
        for row in rows:
            print("|" + row + "|")
        print("+" + "-" * 32 + "+")
        if crash:
            print(f"CRASH: {crash}", file=sys.stderr)
    return 0 if crash is None else 1


def cmd_test(args: argparse.Namespace) -> int:
    """Run a declarative `.spec.json` scenario against a ROM."""

    failures: List[str] = []
    results: List[Dict[str, object]] = []
    for spec_path in args.specs:
        spec = json.loads(Path(spec_path).read_text())
        name = spec.get("name", Path(spec_path).stem)
        rom_path = Path(spec["rom"])
        if not rom_path.is_absolute():
            rom_path = Path(spec_path).parent / rom_path
        try:
            nes = _load_machine(rom_path)
        except FileNotFoundError:
            failures.append(f"{name}: ROM {rom_path} 이(가) 없습니다")
            continue
        frame_no = 0
        problems: List[str] = []
        for step in spec.get("steps", []):
            buttons = 0
            for button in step.get("input", []):
                from .emu import BUTTONS

                if button.upper() not in BUTTONS:
                    problems.append(f"알 수 없는 버튼 {button}")
                    continue
                buttons |= BUTTONS[button.upper()]
            for _ in range(step.get("frames", 1)):
                nes.set_pad(0, buttons)
                try:
                    nes.run_frame()
                except Crash as exc:
                    problems.append(f"frame {frame_no}: {exc}")
                    break
                frame_no += 1
            for symbol, condition in step.get("assert", {}).items():
                problems.extend(_check(nes, symbol, condition, frame_no))
        results.append({"name": name, "ok": not problems, "problems": problems, "frames": frame_no})
        if problems:
            failures.append(name)
    payload = {"ok": not failures, "results": results}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in results:
            mark = "PASS" if result["ok"] else "FAIL"
            print(f"[{mark}] {result['name']} ({result['frames']} frames)")
            for problem in result["problems"]:
                print(f"        {problem}")
    return 0 if not failures else 1


def _check(nes: NES, symbol: str, condition: object, frame_no: int) -> List[str]:
    width = 1
    name = symbol
    if symbol.endswith(":16"):
        name, width = symbol[:-3], 2
    try:
        value = nes.peek(name, width)
    except KeyError:
        return [f"frame {frame_no}: 심볼 {name} 을(를) 찾을 수 없습니다"]
    if not isinstance(condition, dict):
        condition = {"eq": condition}
    problems: List[str] = []
    for op, expected in condition.items():
        ok = {
            "eq": value == expected,
            "ne": value != expected,
            "gt": value > expected,
            "ge": value >= expected,
            "lt": value < expected,
            "le": value <= expected,
        }.get(op)
        if ok is None:
            problems.append(f"알 수 없는 조건 {op}")
        elif not ok:
            problems.append(f"frame {frame_no}: {name} = {value}, 기대: {op} {expected}")
    return problems


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="famic",
        description="FAMI-C: LLM 에이전트용 패미컴 C 컴파일러",
    )
    parser.add_argument("--json", action="store_true", help="stdout 을 JSON 으로만 출력")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build", help=".c 를 .nes 로 빌드")
    p.add_argument("source")
    p.add_argument("-o", "--output")
    p.add_argument("--asm", help="생성된 어셈블리를 저장할 경로")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="ROM 을 쓰지 않고 컴파일만 확인")
    p.add_argument("source")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("asm", help="생성된 6502 어셈블리 출력")
    p.add_argument("source")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_asm)

    p = sub.add_parser("api", help="런타임 API 목록")
    p.set_defaults(func=cmd_api)

    p = sub.add_parser("header", help="include/fami.h 재생성")
    p.set_defaults(func=cmd_header)

    p = sub.add_parser("errors", help="에러 코드 목록")
    p.set_defaults(func=cmd_errors)

    p = sub.add_parser("run", help="ROM 을 헤드리스로 실행하고 상태를 보고")
    p.add_argument("rom")
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--input", help='예: "60:START, 90:RIGHT*30"')
    p.add_argument("--sym", help="쉼표로 구분한 심볼 이름 (16비트는 name:16)")
    p.add_argument("--screenshot", help="PNG 저장 경로")
    p.add_argument("--scale", type=int, default=2)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("screen", help="화면을 텍스트로 출력")
    p.add_argument("rom")
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--input")
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("test", help=".spec.json 시나리오 실행")
    p.add_argument("specs", nargs="+")
    p.set_defaults(func=cmd_test)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CompileError as exc:
        return _fail(exc.diagnostic.to_dict(), args.json)
    except FileNotFoundError as exc:
        return _fail(
            {
                "code": "E0106",
                "file": str(exc.filename),
                "line": 0,
                "col": 0,
                "message": f"파일을 찾을 수 없습니다: {exc.filename}",
                "hint": "경로를 확인하세요.",
            },
            args.json,
        )
    except ValueError as exc:
        return _fail(
            {
                "code": "E0602",
                "file": "",
                "line": 0,
                "col": 0,
                "message": str(exc),
                "hint": "",
            },
            args.json,
        )
