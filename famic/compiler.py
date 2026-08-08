"""Build driver: source text in, ROM plus symbol table out."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .assembler import Assembler, make_ines
from .assets import AssetCompiler, CompiledAssets
from .codegen import CodeGenerator
from .diagnostics import CompileError, Diagnostic, DiagnosticBag
from .lexer import lex
from .parser import parse


INCLUDE_DIR = Path(__file__).resolve().parent.parent / "include"


@dataclass
class BuildResult:
    rom: bytes
    asm: str
    symbols: Dict[str, int]
    warnings: List[Diagnostic] = field(default_factory=list)
    info: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "ok": True,
            "diagnostics": [w.to_dict() for w in self.warnings],
            "rom_bytes": len(self.rom),
            **self.info,
        }


def compile_source(
    source: str,
    file: str = "<source>",
    include_dirs: Optional[Sequence[Path]] = None,
) -> BuildResult:
    dirs = list(include_dirs or [])
    dirs.append(INCLUDE_DIR)
    if file not in ("<source>", ""):
        dirs.insert(0, Path(file).resolve().parent)

    warnings = DiagnosticBag()
    tokens = lex(source, dirs, file)
    program = parse(tokens, file)

    # Assets first: the code generator needs tile indices and the font map
    # before it can fold `T_BRICK` or a string literal into constants.
    asset_compiler = AssetCompiler(program, warnings, file)
    needs_font = _mentions_text(source)
    assets = asset_compiler.compile(needs_font)

    generator = CodeGenerator(program, assets, warnings, file)
    asm, info = generator.generate()

    assembler = Assembler()
    prg = assembler.assemble(asm)
    rom = make_ines(prg, bytes(assets.chr_rom))

    info = dict(info)
    info.update(assembler.ram_usage())
    info["prg_used"] = _prg_used(prg)
    for item in warnings.items:
        item.file = file
    return BuildResult(rom, asm, assembler.symbol_table(), warnings.items, info)


def _mentions_text(source: str) -> bool:
    """Cheap pre-scan: does this program need the built-in font in CHR?

    Font tiles have to be allocated before code generation runs, and code
    generation is what discovers `bg_text` calls, so the decision is made from
    the source text.  Over-allocating costs 53 tiles; under-allocating would
    be a compile error, so the check errs toward including it.
    """

    return "bg_text" in source or "bg_number" in source or '"' in source


def _prg_used(prg: bytes) -> int:
    """Bytes of PRG that are not filler, as a rough size signal for agents."""

    tail = len(prg)
    while tail > 0 and prg[tail - 1] == 0xFF:
        tail -= 1
    return tail


def build_file(
    source_path: Path,
    out_path: Optional[Path] = None,
    asm_path: Optional[Path] = None,
    sym_path: Optional[Path] = None,
) -> BuildResult:
    source = source_path.read_text()
    result = compile_source(source, str(source_path))
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(result.rom)
        if sym_path is None:
            sym_path = out_path.with_suffix(".sym")
    if asm_path is not None:
        asm_path.parent.mkdir(parents=True, exist_ok=True)
        asm_path.write_text(result.asm)
    if sym_path is not None:
        sym_path.parent.mkdir(parents=True, exist_ok=True)
        sym_path.write_text(format_symbols(result.symbols))
    return result


def format_symbols(symbols: Dict[str, int]) -> str:
    lines = ["# FAMI-C symbol table: name address"]
    for name, addr in sorted(symbols.items(), key=lambda kv: (kv[1], kv[0])):
        lines.append(f"{name} ${addr:04X}")
    return "\n".join(lines) + "\n"


def load_symbols(path: Path) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        name, addr = parts
        out[name] = int(addr.lstrip("$"), 16)
    return out
