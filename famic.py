#!/usr/bin/env python3
"""
FAMI-C: a small self-contained C-to-NES compiler.

The compiler intentionally targets the programming model that is practical on
the NES: 8-bit unsigned arithmetic, static storage, no recursion, and native
helpers for PPU/controller access. It parses C syntax, emits 6502 assembly,
assembles that assembly, and packages an iNES ROM.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


class CompileError(Exception):
    pass


# ROMs are NROM-256: a single 32K PRG bank mapped at $8000, one 8K CHR bank,
# and the 6502 vectors in the last six bytes.  NROM-256 is still iNES mapper 0,
# so the packaging stays as portable as the older 16K layout while leaving room
# for the example game's music, sound effects, and menus.
PRG_BASE = 0x8000
PRG_SIZE = 0x8000
PRG_VECTORS = PRG_BASE + PRG_SIZE - 6
PRG_BANKS = PRG_SIZE // 0x4000
CHR_SIZE = 0x2000

# Sound-effect slot count.  Slot zero is reserved as "stop the current effect",
# so a program can define up to fifteen distinct effects.
SFX_SLOTS = 16


@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int

    def text(self) -> str:
        return str(self.value)


KEYWORDS = {
    "break",
    "char",
    "const",
    "continue",
    "else",
    "extern",
    "for",
    "if",
    "int",
    "return",
    "unsigned",
    "void",
    "while",
}

MULTI_OPS = (
    "==",
    "!=",
    "<=",
    ">=",
    "&&",
    "||",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "++",
    "--",
    "<<",
    ">>",
)


def strip_comments(source: str) -> str:
    out: List[str] = []
    i = 0
    in_block = False
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if ch == "/" and nxt == "*":
            in_block = True
            out.append(" ")
            out.append(" ")
            i += 2
            continue
        if ch == "/" and nxt == "/":
            while i < len(source) and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.i = 0
        self.line = 1
        self.col = 1

    def peek(self, n: int = 0) -> str:
        j = self.i + n
        return self.source[j] if j < len(self.source) else ""

    def advance(self) -> str:
        ch = self.peek()
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while self.i < len(self.source):
            ch = self.peek()
            if ch.isspace():
                self.advance()
                continue
            line, col = self.line, self.col
            if ch.isalpha() or ch == "_":
                text = self.read_identifier()
                kind = "kw" if text in KEYWORDS else "id"
                tokens.append(Token(kind, text, line, col))
                continue
            if ch.isdigit():
                tokens.append(Token("num", self.read_number(), line, col))
                continue
            if ch == "'":
                tokens.append(Token("num", self.read_char_literal(), line, col))
                continue
            two = self.source[self.i : self.i + 2]
            if two in MULTI_OPS:
                self.advance()
                self.advance()
                tokens.append(Token("sym", two, line, col))
                continue
            if ch in "{}()[];,:+-*/%<>=!~&|^":
                self.advance()
                tokens.append(Token("sym", ch, line, col))
                continue
            raise CompileError(f"{line}:{col}: unexpected character {ch!r}")
        tokens.append(Token("eof", "EOF", self.line, self.col))
        return tokens

    def read_identifier(self) -> str:
        start = self.i
        while self.peek().isalnum() or self.peek() == "_":
            self.advance()
        return self.source[start : self.i]

    def read_number(self) -> int:
        if self.peek() == "0" and self.peek(1).lower() == "x":
            self.advance()
            self.advance()
            start = self.i
            while self.peek().isdigit() or self.peek().lower() in "abcdef":
                self.advance()
            return int(self.source[start : self.i], 16)
        start = self.i
        while self.peek().isdigit():
            self.advance()
        return int(self.source[start : self.i], 10)

    def read_char_literal(self) -> int:
        self.advance()
        ch = self.advance()
        if ch == "\\":
            esc = self.advance()
            table = {"n": 10, "r": 13, "t": 9, "0": 0, "\\": 92, "'": 39}
            val = table.get(esc)
            if val is None:
                raise CompileError(f"{self.line}:{self.col}: unsupported escape \\{esc}")
        else:
            val = ord(ch)
        if self.advance() != "'":
            raise CompileError(f"{self.line}:{self.col}: unterminated character literal")
        return val


def preprocess(source: str) -> Tuple[str, Dict[str, str]]:
    source = strip_comments(source)
    macros: Dict[str, str] = {}
    kept: List[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#define"):
            parts = stripped.split(None, 2)
            if len(parts) == 3 and "(" not in parts[1]:
                macros[parts[1]] = parts[2]
            continue
        if stripped.startswith("#"):
            continue
        kept.append(line)
    return "\n".join(kept) + "\n", macros


def lex_c(source: str) -> List[Token]:
    clean, macros = preprocess(source)
    raw = Lexer(clean).tokenize()
    if not macros:
        return raw

    def expand_token(tok: Token, depth: int = 0) -> List[Token]:
        if depth > 8 or tok.kind != "id" or tok.value not in macros:
            return [tok]
        replacement = Lexer(macros[str(tok.value)]).tokenize()[:-1]
        expanded: List[Token] = []
        for repl in replacement:
            repl.line, repl.col = tok.line, tok.col
            expanded.extend(expand_token(repl, depth + 1))
        return expanded

    out: List[Token] = []
    for tok in raw[:-1]:
        out.extend(expand_token(tok))
    out.append(raw[-1])
    return out


@dataclass
class TypeSpec:
    name: str
    is_unsigned: bool = False
    is_const: bool = False
    is_extern: bool = False

    @property
    def is_void(self) -> bool:
        return self.name == "void"


@dataclass
class Param:
    type: TypeSpec
    name: str


@dataclass
class VarDecl:
    type: TypeSpec
    name: str
    array_size: int = 0
    init: Optional[object] = None
    is_global: bool = False


@dataclass
class FuncDecl:
    ret_type: TypeSpec
    name: str
    params: List[Param]
    body: Optional["Block"]
    is_extern: bool = False


@dataclass
class Program:
    globals: List[VarDecl]
    functions: List[FuncDecl]


class Expr:
    pass


@dataclass
class Num(Expr):
    value: int


@dataclass
class Var(Expr):
    name: str


@dataclass
class ArrayRef(Expr):
    array: Expr
    index: Expr


@dataclass
class Call(Expr):
    name: str
    args: List[Expr]


@dataclass
class Unary(Expr):
    op: str
    expr: Expr


@dataclass
class Binary(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass
class Assign(Expr):
    op: str
    target: Expr
    value: Expr


class Stmt:
    pass


@dataclass
class Block(Stmt):
    statements: List[Stmt]


@dataclass
class If(Stmt):
    cond: Expr
    then_branch: Stmt
    else_branch: Optional[Stmt]


@dataclass
class While(Stmt):
    cond: Expr
    body: Stmt


@dataclass
class For(Stmt):
    init: Optional[Stmt]
    cond: Optional[Expr]
    post: Optional[Expr]
    body: Stmt


@dataclass
class Return(Stmt):
    expr: Optional[Expr]


@dataclass
class Break(Stmt):
    pass


@dataclass
class Continue(Stmt):
    pass


@dataclass
class ExprStmt(Stmt):
    expr: Optional[Expr]


@dataclass
class VarStmt(Stmt):
    decl: VarDecl


PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6,
    "!=": 6,
    "<": 7,
    "<=": 7,
    ">": 7,
    ">=": 7,
    "+": 8,
    "-": 8,
    "*": 9,
    "/": 9,
    "%": 9,
}


class Parser:
    def __init__(self, tokens: Sequence[Token]):
        self.tokens = list(tokens)
        self.i = 0

    def peek(self, n: int = 0) -> Token:
        j = self.i + n
        if j >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[j]

    def match(self, value: str) -> bool:
        if self.peek().value == value:
            self.i += 1
            return True
        return False

    def match_kw(self, value: str) -> bool:
        if self.peek().kind == "kw" and self.peek().value == value:
            self.i += 1
            return True
        return False

    def expect(self, value: str) -> Token:
        tok = self.peek()
        if tok.value != value:
            self.error(tok, f"expected {value!r}, got {tok.value!r}")
        self.i += 1
        return tok

    def expect_id(self) -> str:
        tok = self.peek()
        if tok.kind != "id":
            self.error(tok, f"expected identifier, got {tok.value!r}")
        self.i += 1
        return str(tok.value)

    def error(self, tok: Token, msg: str) -> None:
        raise CompileError(f"{tok.line}:{tok.col}: {msg}")

    def parse(self) -> Program:
        globals_: List[VarDecl] = []
        functions: List[FuncDecl] = []
        while self.peek().kind != "eof":
            t = self.parse_type()
            name = self.expect_id()
            if self.match("("):
                params = self.parse_params()
                is_extern = t.is_extern
                if self.match(";"):
                    functions.append(FuncDecl(t, name, params, None, True))
                else:
                    body = self.parse_block()
                    functions.append(FuncDecl(t, name, params, body, is_extern))
                continue
            decls = self.parse_var_decl_tail(t, name, is_global=True)
            globals_.extend(decls)
            self.expect(";")
        return Program(globals_, functions)

    def parse_type(self) -> TypeSpec:
        is_extern = False
        is_const = False
        is_unsigned = False
        while True:
            if self.match_kw("extern"):
                is_extern = True
                continue
            if self.match_kw("const"):
                is_const = True
                continue
            if self.match_kw("unsigned"):
                is_unsigned = True
                continue
            break
        tok = self.peek()
        if tok.kind != "kw" or tok.value not in ("void", "char", "int"):
            self.error(tok, "expected a C type")
        self.i += 1
        return TypeSpec(str(tok.value), is_unsigned, is_const, is_extern)

    def parse_params(self) -> List[Param]:
        params: List[Param] = []
        if self.match(")"):
            return params
        if self.peek().kind == "kw" and self.peek().value == "void" and self.peek(1).value == ")":
            self.i += 1
            self.expect(")")
            return params
        while True:
            t = self.parse_type()
            name = self.expect_id() if self.peek().kind == "id" else f"p{len(params)}"
            params.append(Param(t, name))
            if self.match(")"):
                return params
            self.expect(",")

    def parse_var_decl_tail(self, t: TypeSpec, first_name: str, is_global: bool) -> List[VarDecl]:
        decls: List[VarDecl] = []
        name = first_name
        while True:
            array_size = 0
            if self.match("["):
                if not self.match("]"):
                    tok = self.peek()
                    if tok.kind != "num":
                        self.error(tok, "array size must be a number")
                    array_size = int(tok.value)
                    self.i += 1
                    self.expect("]")
                else:
                    array_size = -1
            init = None
            if self.match("="):
                init = self.parse_initializer()
                if array_size == -1:
                    if not isinstance(init, list):
                        self.error(self.peek(), "unsized array needs a list initializer")
                    array_size = len(init)
            if array_size == -1:
                self.error(self.peek(), "array size is required without an initializer")
            decls.append(VarDecl(t, name, array_size, init, is_global))
            if not self.match(","):
                return decls
            name = self.expect_id()

    def parse_initializer(self) -> object:
        if self.match("{"):
            values: List[Expr] = []
            if self.match("}"):
                return values
            while True:
                values.append(self.parse_expression())
                if self.match("}"):
                    return values
                self.expect(",")
                if self.match("}"):
                    return values
        return self.parse_expression()

    def is_type_start(self) -> bool:
        tok = self.peek()
        return tok.kind == "kw" and tok.value in {"extern", "const", "unsigned", "void", "char", "int"}

    def parse_block(self) -> Block:
        self.expect("{")
        statements: List[Stmt] = []
        while not self.match("}"):
            if self.peek().kind == "eof":
                self.error(self.peek(), "unterminated block")
            statements.append(self.parse_statement())
        return Block(statements)

    def parse_statement(self) -> Stmt:
        if self.match(";"):
            return ExprStmt(None)
        if self.peek().value == "{":
            return self.parse_block()
        if self.match_kw("if"):
            self.expect("(")
            cond = self.parse_expression()
            self.expect(")")
            then_branch = self.parse_statement()
            else_branch = self.parse_statement() if self.match_kw("else") else None
            return If(cond, then_branch, else_branch)
        if self.match_kw("while"):
            self.expect("(")
            cond = self.parse_expression()
            self.expect(")")
            return While(cond, self.parse_statement())
        if self.match_kw("for"):
            self.expect("(")
            init: Optional[Stmt] = None
            if not self.match(";"):
                if self.is_type_start():
                    init = self.parse_local_decl(expect_semicolon=True)
                else:
                    init = ExprStmt(self.parse_expression())
                    self.expect(";")
            cond: Optional[Expr] = None
            if not self.match(";"):
                cond = self.parse_expression()
                self.expect(";")
            post: Optional[Expr] = None
            if not self.match(")"):
                post = self.parse_expression()
                self.expect(")")
            return For(init, cond, post, self.parse_statement())
        if self.match_kw("return"):
            expr = None if self.peek().value == ";" else self.parse_expression()
            self.expect(";")
            return Return(expr)
        if self.match_kw("break"):
            self.expect(";")
            return Break()
        if self.match_kw("continue"):
            self.expect(";")
            return Continue()
        if self.is_type_start():
            return self.parse_local_decl(expect_semicolon=True)
        expr = self.parse_expression()
        self.expect(";")
        return ExprStmt(expr)

    def parse_local_decl(self, expect_semicolon: bool) -> VarStmt:
        t = self.parse_type()
        name = self.expect_id()
        decls = self.parse_var_decl_tail(t, name, is_global=False)
        if len(decls) != 1:
            self.error(self.peek(), "local declarations must declare one name at a time")
        if expect_semicolon:
            self.expect(";")
        return VarStmt(decls[0])

    def parse_expression(self) -> Expr:
        return self.parse_assignment()

    def parse_assignment(self) -> Expr:
        left = self.parse_binary(1)
        tok = self.peek()
        if tok.value in ("=", "+=", "-=", "*=", "/=", "%="):
            self.i += 1
            value = self.parse_assignment()
            return Assign(str(tok.value), left, value)
        return left

    def parse_binary(self, min_prec: int) -> Expr:
        left = self.parse_unary()
        while True:
            tok = self.peek()
            op = str(tok.value)
            prec = PRECEDENCE.get(op, 0)
            if prec < min_prec:
                break
            self.i += 1
            right = self.parse_binary(prec + 1)
            left = Binary(op, left, right)
        return left

    def parse_unary(self) -> Expr:
        tok = self.peek()
        if tok.value in ("!", "-", "~", "+"):
            self.i += 1
            return Unary(str(tok.value), self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            if self.match("("):
                if not isinstance(expr, Var):
                    self.error(self.peek(), "only direct function calls are supported")
                args: List[Expr] = []
                if not self.match(")"):
                    while True:
                        args.append(self.parse_expression())
                        if self.match(")"):
                            break
                        self.expect(",")
                expr = Call(expr.name, args)
                continue
            if self.match("["):
                idx = self.parse_expression()
                self.expect("]")
                expr = ArrayRef(expr, idx)
                continue
            break
        return expr

    def parse_primary(self) -> Expr:
        tok = self.peek()
        if tok.kind == "num":
            self.i += 1
            return Num(int(tok.value))
        if tok.kind == "id":
            self.i += 1
            return Var(str(tok.value))
        if self.match("("):
            expr = self.parse_expression()
            self.expect(")")
            return expr
        self.error(tok, f"expected expression, got {tok.value!r}")
        raise AssertionError


def eval_const(expr: Expr) -> int:
    if isinstance(expr, Num):
        return expr.value & 0xFF
    if isinstance(expr, Unary):
        v = eval_const(expr.expr)
        if expr.op == "+":
            return v & 0xFF
        if expr.op == "-":
            return (-v) & 0xFF
        if expr.op == "~":
            return (~v) & 0xFF
        if expr.op == "!":
            return 0 if v else 1
    if isinstance(expr, Binary):
        a = eval_const(expr.left)
        b = eval_const(expr.right)
        if expr.op == "+":
            return (a + b) & 0xFF
        if expr.op == "-":
            return (a - b) & 0xFF
        if expr.op == "*":
            return (a * b) & 0xFF
        if expr.op == "/":
            return 0 if b == 0 else (a // b) & 0xFF
        if expr.op == "%":
            return 0 if b == 0 else (a % b) & 0xFF
        if expr.op == "&":
            return a & b
        if expr.op == "|":
            return a | b
        if expr.op == "^":
            return a ^ b
        if expr.op == "==":
            return 1 if a == b else 0
        if expr.op == "!=":
            return 1 if a != b else 0
        if expr.op == "<":
            return 1 if a < b else 0
        if expr.op == "<=":
            return 1 if a <= b else 0
        if expr.op == ">":
            return 1 if a > b else 0
        if expr.op == ">=":
            return 1 if a >= b else 0
        if expr.op == "&&":
            return 1 if a and b else 0
        if expr.op == "||":
            return 1 if a or b else 0
    raise CompileError("global initializers must be constant")


@dataclass
class Symbol:
    name: str
    label: str
    array_size: int = 0
    is_const: bool = False


# NTSC 2A03 timer periods for MIDI notes 29 through 95.  The pulse
# channels cannot represent notes below MIDI 33, so their first four entries
# are clamped to the lowest available pulse frequency.  Triangle uses a
# different divider and therefore needs its own table.
MUSIC_PULSE_TIMERS = (
    2047, 2047, 2047, 2047, 2033, 1919, 1811, 1709, 1613, 1523, 1437,
    1356, 1280, 1208, 1140, 1076, 1016, 959, 905, 854, 806, 761, 718,
    678, 640, 604, 570, 538, 507, 479, 452, 427, 403, 380, 359, 338,
    319, 301, 284, 268, 253, 239, 225, 213, 201, 189, 179, 169, 159,
    150, 142, 134, 126, 119, 112, 106, 100, 94, 89, 84, 79, 75, 70,
    66, 63, 59, 56,
)

MUSIC_TRIANGLE_TIMERS = (
    1280, 1208, 1140, 1076, 1016, 959, 905, 854, 806, 761, 718, 678,
    640, 604, 570, 538, 507, 479, 452, 427, 403, 380, 359, 338, 319,
    301, 284, 268, 253, 239, 225, 213, 201, 189, 179, 169, 159, 150,
    142, 134, 126, 119, 112, 106, 100, 94, 89, 84, 79, 75, 70, 66,
    63, 59, 56, 52, 49, 47, 44, 41, 39, 37, 35, 33, 31, 29, 27,
)


class CodeGenerator:
    def __init__(self, program: Program):
        self.program = program
        self.lines: List[str] = []
        self.globals: Dict[str, Symbol] = {}
        self.functions: Dict[str, FuncDecl] = {}
        self.func_symbols: Dict[str, Dict[str, Symbol]] = {}
        self.label_id = 0
        self.current_func: Optional[FuncDecl] = None
        self.return_label = ""
        self.break_stack: List[str] = []
        self.continue_stack: List[str] = []
        self.music_runtime = False
        self.music_compressed = False
        self.preview_runtime = False
        self.board_runtime = False
        self.board_runtime_param = ""
        self.sfx_runtime = False
        self.sfx_runtime_param = ""

    def generate(self) -> str:
        self.index_program()
        self.emit("; generated by FAMI-C")
        self.emit_ram()
        self.emit("")
        self.emit(".org $8000")
        self.emit_runtime_start()
        self.emit_rodata()
        for fn in self.program.functions:
            if fn.body is not None and not fn.is_extern:
                self.emit_function(fn)
        self.emit_runtime_helpers()
        self.emit("")
        self.emit(f".org ${PRG_VECTORS:04X}")
        self.emit(".word _nmi")
        self.emit(".word _reset")
        self.emit(".word _irq")
        return "\n".join(self.lines) + "\n"

    def index_program(self) -> None:
        for g in self.program.globals:
            if g.name in self.globals:
                raise CompileError(f"duplicate global {g.name}")
            self.globals[g.name] = Symbol(g.name, self.mangle(g.name), g.array_size, g.type.is_const)
        for fn in self.program.functions:
            if fn.name in self.functions:
                prev = self.functions[fn.name]
                if prev.body is not None and fn.body is not None:
                    raise CompileError(f"duplicate function {fn.name}")
            self.functions[fn.name] = fn
        if "main" not in self.functions:
            raise CompileError("program needs a main function")
        self.music_runtime = any(
            fn.name == "music_init"
            and fn.body is None
            and fn.is_extern
            and fn.ret_type.is_extern
            and fn.ret_type.is_void
            and not fn.params
            for fn in self.program.functions
        )
        if self.music_runtime:
            legacy_sizes = {
                "MUSIC_PULSE1": 256,
                "MUSIC_PULSE2": 256,
                "MUSIC_TRIANGLE": 256,
                "MUSIC_NOISE": 256,
            }
            compressed_sizes = {
                "MUSIC_PULSE1_BASE": 77,
                "MUSIC_PULSE1_PAIR0": 77,
                "MUSIC_PULSE1_PAIR1": 77,
                "MUSIC_PULSE1_PAIR2": 77,
                "MUSIC_PULSE1_PAIR3": 77,
                "MUSIC_PULSE2_BASE": 30,
                "MUSIC_PULSE2_PAIR0": 30,
                "MUSIC_PULSE2_PAIR1": 30,
                "MUSIC_PULSE2_PAIR2": 30,
                "MUSIC_PULSE2_PAIR3": 30,
                "MUSIC_TRIANGLE_BASE": 47,
                "MUSIC_TRIANGLE_PAIR0": 47,
                "MUSIC_TRIANGLE_PAIR1": 47,
                "MUSIC_TRIANGLE_PAIR2": 47,
                "MUSIC_TRIANGLE_PAIR3": 47,
                "MUSIC_NOISE_PAIR0": 70,
                "MUSIC_NOISE_PAIR1": 70,
                "MUSIC_NOISE_PAIR2": 70,
                "MUSIC_NOISE_PAIR3": 70,
                "MUSIC_TUPLE_PULSE1": 156,
                "MUSIC_TUPLE_PULSE2": 156,
                "MUSIC_TUPLE_TRIANGLE": 156,
                "MUSIC_TUPLE_NOISE": 156,
                "MUSIC_ORDER0": 256,
                "MUSIC_ORDER1": 50,
            }

            def has_music_arrays(sizes: Dict[str, int]) -> bool:
                return all(
                    (sym := self.globals.get(name)) is not None
                    and sym.is_const
                    and sym.array_size == size
                    for name, size in sizes.items()
                )

            if has_music_arrays(compressed_sizes):
                self.music_compressed = True
            elif not has_music_arrays(legacy_sizes):
                raise CompileError(
                    "music runtime needs four const MUSIC_*[256] arrays or the "
                    "compressed v2 pattern/order arrays"
                )
        else:
            for name in ("music_pause", "music_resume"):
                if any(
                    fn.name == name and fn.body is None and fn.is_extern
                    for fn in self.program.functions
                ):
                    raise CompileError(f"{name} needs the music runtime; declare music_init")
        self.preview_runtime = any(
            fn.name == "ppu_write_preview"
            and fn.body is None
            and fn.is_extern
            and fn.ret_type.is_extern
            and fn.ret_type.is_void
            and not fn.params
            for fn in self.program.functions
        )
        if self.preview_runtime:
            preview = self.globals.get("preview_tiles")
            if preview is None or preview.is_const or preview.array_size != 16:
                raise CompileError("ppu_write_preview needs unsigned char preview_tiles[16]")
        board_runtime_fn = next(
            (
                fn
                for fn in self.program.functions
                if fn.name == "ppu_write_board_half"
                and fn.body is None
                and fn.is_extern
                and fn.ret_type.is_extern
                and fn.ret_type.is_void
                and len(fn.params) == 1
            ),
            None,
        )
        self.board_runtime = board_runtime_fn is not None
        if board_runtime_fn is not None:
            board = self.globals.get("board")
            if board is None or board.is_const or board.array_size != 200:
                raise CompileError("ppu_write_board_half needs unsigned char board[200]")
            self.board_runtime_param = self.param_label(
                board_runtime_fn.name, board_runtime_fn.params[0].name
            )
        sfx_runtime_fn = next(
            (
                fn
                for fn in self.program.functions
                if fn.name == "sfx_play"
                and fn.body is None
                and fn.is_extern
                and fn.ret_type.is_extern
                and fn.ret_type.is_void
                and len(fn.params) == 1
            ),
            None,
        )
        self.sfx_runtime = sfx_runtime_fn is not None
        if sfx_runtime_fn is not None:
            self.check_sfx_tables()
            self.sfx_runtime_param = self.param_label(
                sfx_runtime_fn.name, sfx_runtime_fn.params[0].name
            )
        for fn in self.program.functions:
            scope: Dict[str, Symbol] = {}
            for p in fn.params:
                scope[p.name] = Symbol(p.name, self.param_label(fn.name, p.name))
            if fn.body is not None:
                for decl in self.collect_locals(fn.body):
                    if decl.array_size:
                        raise CompileError("local arrays are not supported on the NES backend")
                    if decl.name in scope:
                        raise CompileError(f"duplicate local {decl.name} in {fn.name}")
                    scope[decl.name] = Symbol(decl.name, self.local_label(fn.name, decl.name))
            self.func_symbols[fn.name] = scope

    def check_sfx_tables(self) -> None:
        """Validate the const tables the sound-effect driver indexes."""

        for name in ("SFX_START", "SFX_LENGTH"):
            sym = self.globals.get(name)
            if sym is None or not sym.is_const or sym.array_size != SFX_SLOTS:
                raise CompileError(
                    f"sfx_play needs const unsigned char {name}[{SFX_SLOTS}]"
                )
        frame_sizes = []
        for name in ("SFX_CTRL", "SFX_TIMER_LO", "SFX_TIMER_HI"):
            sym = self.globals.get(name)
            if sym is None or not sym.is_const or not sym.array_size:
                raise CompileError(f"sfx_play needs a const unsigned char {name}[] table")
            frame_sizes.append(sym.array_size)
        if len(set(frame_sizes)) != 1:
            raise CompileError(
                "SFX_CTRL, SFX_TIMER_LO and SFX_TIMER_HI must have the same length"
            )
        if frame_sizes[0] > 256:
            raise CompileError("sound-effect frame tables are limited to 256 entries")

    def collect_locals(self, stmt: Stmt) -> List[VarDecl]:
        out: List[VarDecl] = []
        if isinstance(stmt, VarStmt):
            out.append(stmt.decl)
        elif isinstance(stmt, Block):
            for child in stmt.statements:
                out.extend(self.collect_locals(child))
        elif isinstance(stmt, If):
            out.extend(self.collect_locals(stmt.then_branch))
            if stmt.else_branch:
                out.extend(self.collect_locals(stmt.else_branch))
        elif isinstance(stmt, While):
            out.extend(self.collect_locals(stmt.body))
        elif isinstance(stmt, For):
            if stmt.init:
                out.extend(self.collect_locals(stmt.init))
            out.extend(self.collect_locals(stmt.body))
        return out

    def emit_ram(self) -> None:
        for name in (
            "__tmp0",
            "__tmp1",
            "__tmp2",
            "__tmp3",
            "__ppu_rendering",
            "_nmi_flag",
            "_pad_state",
            "_rng_state",
            "_rng_state_hi",
        ):
            self.emit(f".ram {name} 1")
        if self.music_runtime:
            music_ram = [
                "__music_enabled",
                "__music_step",
                "__music_last_pulse1",
                "__music_last_pulse2",
                "__music_last_triangle",
            ]
            if self.music_compressed:
                music_ram.extend(
                    [
                        "__music_phase_lo",
                        "__music_phase_hi",
                        "__music_phase_inc_lo",
                        "__music_phase_inc_hi",
                        "__music_order_lo",
                        "__music_order_page",
                        "__music_pattern_step",
                        "__music_pattern_pulse1",
                        "__music_pattern_pulse2",
                        "__music_pattern_triangle",
                        "__music_pattern_noise",
                        "__music_note_base",
                    ]
                )
            else:
                music_ram.extend(["__music_frames", "__music_phase"])
            for name in music_ram:
                self.emit(f".ram {name} 1")
        if self.sfx_runtime:
            for name in ("__sfx_pos", "__sfx_left", "__sfx_hi"):
                self.emit(f".ram {name} 1")
        for g in self.program.globals:
            if not g.type.is_const:
                size = g.array_size if g.array_size else 1
                self.emit(f".ram {self.mangle(g.name)} {size}")
        for fn in self.program.functions:
            for p in fn.params:
                self.emit(f".ram {self.param_label(fn.name, p.name)} 1")
            if fn.body is not None:
                for decl in self.collect_locals(fn.body):
                    self.emit(f".ram {self.local_label(fn.name, decl.name)} 1")

    def emit_rodata(self) -> None:
        for g in self.program.globals:
            if not g.type.is_const:
                continue
            self.emit("")
            self.emit(f"{self.mangle(g.name)}:")
            values: List[int]
            if isinstance(g.init, list):
                values = [eval_const(v) for v in g.init]
            elif g.init is None:
                values = [0] * (g.array_size if g.array_size else 1)
            else:
                values = [eval_const(g.init)]
            if g.array_size and len(values) < g.array_size:
                values.extend([0] * (g.array_size - len(values)))
            for i in range(0, len(values), 16):
                self.emit(".byte " + ", ".join(f"${v & 0xFF:02X}" for v in values[i : i + 16]))

    def emit_function(self, fn: FuncDecl) -> None:
        self.current_func = fn
        self.return_label = self.new_label(f"{fn.name}_return")
        self.emit("")
        self.emit(f"{self.mangle(fn.name)}:")
        assert fn.body is not None
        self.emit_stmt(fn.body)
        self.emit("LDA #$00")
        self.emit(f"{self.return_label}:")
        self.emit("RTS")
        self.current_func = None

    def emit_stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, Block):
            for child in stmt.statements:
                self.emit_stmt(child)
            return
        if isinstance(stmt, VarStmt):
            if stmt.decl.init is not None:
                self.emit_assign(Var(stmt.decl.name), "=", stmt.decl.init)  # type: ignore[arg-type]
            return
        if isinstance(stmt, ExprStmt):
            if stmt.expr is not None:
                self.emit_expr(stmt.expr)
            return
        if isinstance(stmt, Return):
            if stmt.expr is None:
                self.emit("LDA #$00")
            else:
                self.emit_expr(stmt.expr)
            self.emit(f"JMP {self.return_label}")
            return
        if isinstance(stmt, If):
            then_label = self.new_label("then")
            else_label = self.new_label("else")
            end_label = self.new_label("endif")
            self.emit_expr(stmt.cond)
            self.emit("CMP #$00")
            self.emit(f"BNE {then_label}")
            self.emit(f"JMP {else_label}")
            self.emit(f"{then_label}:")
            self.emit_stmt(stmt.then_branch)
            self.emit(f"JMP {end_label}")
            self.emit(f"{else_label}:")
            if stmt.else_branch:
                self.emit_stmt(stmt.else_branch)
            self.emit(f"{end_label}:")
            return
        if isinstance(stmt, While):
            start = self.new_label("while")
            body_label = self.new_label("while_body")
            end = self.new_label("wend")
            self.break_stack.append(end)
            self.continue_stack.append(start)
            self.emit(f"{start}:")
            self.emit_expr(stmt.cond)
            self.emit("CMP #$00")
            self.emit(f"BNE {body_label}")
            self.emit(f"JMP {end}")
            self.emit(f"{body_label}:")
            self.emit_stmt(stmt.body)
            self.emit(f"JMP {start}")
            self.emit(f"{end}:")
            self.break_stack.pop()
            self.continue_stack.pop()
            return
        if isinstance(stmt, For):
            start = self.new_label("for")
            body_label = self.new_label("for_body")
            post_label = self.new_label("forpost")
            end = self.new_label("forend")
            if stmt.init:
                self.emit_stmt(stmt.init)
            self.break_stack.append(end)
            self.continue_stack.append(post_label)
            self.emit(f"{start}:")
            if stmt.cond:
                self.emit_expr(stmt.cond)
                self.emit("CMP #$00")
                self.emit(f"BNE {body_label}")
                self.emit(f"JMP {end}")
                self.emit(f"{body_label}:")
            self.emit_stmt(stmt.body)
            self.emit(f"{post_label}:")
            if stmt.post:
                self.emit_expr(stmt.post)
            self.emit(f"JMP {start}")
            self.emit(f"{end}:")
            self.break_stack.pop()
            self.continue_stack.pop()
            return
        if isinstance(stmt, Break):
            if not self.break_stack:
                raise CompileError("break outside loop")
            self.emit(f"JMP {self.break_stack[-1]}")
            return
        if isinstance(stmt, Continue):
            if not self.continue_stack:
                raise CompileError("continue outside loop")
            self.emit(f"JMP {self.continue_stack[-1]}")
            return
        raise CompileError(f"unsupported statement {stmt!r}")

    def emit_expr(self, expr: Expr) -> None:
        if isinstance(expr, Num):
            self.emit(f"LDA #${expr.value & 0xFF:02X}")
            return
        if isinstance(expr, Var):
            sym = self.resolve(expr.name)
            self.emit(f"LDA {sym.label}")
            return
        if isinstance(expr, ArrayRef):
            label = self.array_label(expr.array)
            self.emit_expr(expr.index)
            self.emit("TAX")
            self.emit(f"LDA {label},X")
            return
        if isinstance(expr, Call):
            self.emit_call(expr)
            return
        if isinstance(expr, Unary):
            self.emit_unary(expr)
            return
        if isinstance(expr, Binary):
            self.emit_binary(expr)
            return
        if isinstance(expr, Assign):
            self.emit_assign(expr.target, expr.op, expr.value)
            return
        raise CompileError(f"unsupported expression {expr!r}")

    def emit_unary(self, expr: Unary) -> None:
        self.emit_expr(expr.expr)
        if expr.op == "+":
            return
        if expr.op == "-":
            self.emit("EOR #$FF")
            self.emit("CLC")
            self.emit("ADC #$01")
            return
        if expr.op == "~":
            self.emit("EOR #$FF")
            return
        if expr.op == "!":
            true_label = self.new_label("not_true")
            end_label = self.new_label("not_end")
            self.emit("CMP #$00")
            self.emit(f"BEQ {true_label}")
            self.emit("LDA #$00")
            self.emit(f"JMP {end_label}")
            self.emit(f"{true_label}:")
            self.emit("LDA #$01")
            self.emit(f"{end_label}:")
            return
        raise CompileError(f"unsupported unary operator {expr.op}")

    def emit_binary(self, expr: Binary) -> None:
        if expr.op == "&&":
            self.emit_logical_and(expr.left, expr.right)
            return
        if expr.op == "||":
            self.emit_logical_or(expr.left, expr.right)
            return
        self.emit_expr(expr.left)
        self.emit("PHA")
        self.emit_expr(expr.right)
        self.emit("STA __tmp0")
        self.emit("PLA")
        if expr.op == "+":
            self.emit("CLC")
            self.emit("ADC __tmp0")
            return
        if expr.op == "-":
            self.emit("SEC")
            self.emit("SBC __tmp0")
            return
        if expr.op == "*":
            self.emit("JSR __mul8")
            return
        if expr.op == "/":
            self.emit("JSR __divmod8")
            return
        if expr.op == "%":
            self.emit("JSR __divmod8")
            self.emit("LDA __tmp1")
            return
        if expr.op == "&":
            self.emit("AND __tmp0")
            return
        if expr.op == "|":
            self.emit("ORA __tmp0")
            return
        if expr.op == "^":
            self.emit("EOR __tmp0")
            return
        if expr.op in ("==", "!=", "<", "<=", ">", ">="):
            self.emit_compare(expr.op)
            return
        raise CompileError(f"unsupported binary operator {expr.op}")

    def emit_compare(self, op: str) -> None:
        true_label = self.new_label("cmp_true")
        false_label = self.new_label("cmp_false")
        end_label = self.new_label("cmp_end")
        self.emit("CMP __tmp0")
        if op == "==":
            self.emit(f"BEQ {true_label}")
            self.emit(f"JMP {false_label}")
        elif op == "!=":
            self.emit(f"BNE {true_label}")
            self.emit(f"JMP {false_label}")
        elif op == "<":
            self.emit(f"BCC {true_label}")
            self.emit(f"JMP {false_label}")
        elif op == "<=":
            self.emit(f"BCC {true_label}")
            self.emit(f"BEQ {true_label}")
            self.emit(f"JMP {false_label}")
        elif op == ">":
            self.emit(f"BEQ {false_label}")
            self.emit(f"BCC {false_label}")
            self.emit(f"JMP {true_label}")
        elif op == ">=":
            self.emit(f"BCS {true_label}")
            self.emit(f"JMP {false_label}")
        self.emit(f"{true_label}:")
        self.emit("LDA #$01")
        self.emit(f"JMP {end_label}")
        self.emit(f"{false_label}:")
        self.emit("LDA #$00")
        self.emit(f"{end_label}:")

    def emit_logical_and(self, left: Expr, right: Expr) -> None:
        false_label = self.new_label("and_false")
        end_label = self.new_label("and_end")
        self.emit_expr(left)
        self.emit("CMP #$00")
        self.emit(f"BEQ {false_label}")
        self.emit_expr(right)
        self.emit("CMP #$00")
        self.emit(f"BEQ {false_label}")
        self.emit("LDA #$01")
        self.emit(f"JMP {end_label}")
        self.emit(f"{false_label}:")
        self.emit("LDA #$00")
        self.emit(f"{end_label}:")

    def emit_logical_or(self, left: Expr, right: Expr) -> None:
        true_label = self.new_label("or_true")
        end_label = self.new_label("or_end")
        self.emit_expr(left)
        self.emit("CMP #$00")
        self.emit(f"BNE {true_label}")
        self.emit_expr(right)
        self.emit("CMP #$00")
        self.emit(f"BNE {true_label}")
        self.emit("LDA #$00")
        self.emit(f"JMP {end_label}")
        self.emit(f"{true_label}:")
        self.emit("LDA #$01")
        self.emit(f"{end_label}:")

    def emit_assign(self, target: Expr, op: str, value: Expr) -> None:
        if op != "=":
            self.emit_compound_assign(target, op, value)
            return
        if isinstance(target, Var):
            sym = self.resolve(target.name)
            self.emit_expr(value)
            self.emit(f"STA {sym.label}")
            return
        if isinstance(target, ArrayRef):
            label = self.array_label(target.array)
            self.emit_expr(target.index)
            self.emit("PHA")
            self.emit_expr(value)
            self.emit("STA __tmp0")
            self.emit("PLA")
            self.emit("TAX")
            self.emit("LDA __tmp0")
            self.emit(f"STA {label},X")
            return
        raise CompileError("assignment target must be a variable or array element")

    def emit_compound_assign(self, target: Expr, op: str, value: Expr) -> None:
        plain = op[0]
        if not isinstance(target, Var):
            raise CompileError("compound assignment is only supported for scalar variables")
        sym = self.resolve(target.name)
        self.emit(f"LDA {sym.label}")
        self.emit("PHA")
        self.emit_expr(value)
        self.emit("STA __tmp0")
        self.emit("PLA")
        if plain == "+":
            self.emit("CLC")
            self.emit("ADC __tmp0")
        elif plain == "-":
            self.emit("SEC")
            self.emit("SBC __tmp0")
        elif plain == "*":
            self.emit("JSR __mul8")
        elif plain == "/":
            self.emit("JSR __divmod8")
        elif plain == "%":
            self.emit("JSR __divmod8")
            self.emit("LDA __tmp1")
        else:
            raise CompileError(f"unsupported compound assignment {op}")
        self.emit(f"STA {sym.label}")

    def emit_call(self, call: Call) -> None:
        fn = self.functions.get(call.name)
        if fn is None:
            raise CompileError(f"unknown function {call.name}")
        if len(call.args) != len(fn.params):
            raise CompileError(f"{call.name} expects {len(fn.params)} args, got {len(call.args)}")
        for param, arg in zip(fn.params, call.args):
            self.emit_expr(arg)
            self.emit(f"STA {self.param_label(fn.name, param.name)}")
        self.emit(f"JSR {self.mangle(call.name)}")

    def resolve(self, name: str) -> Symbol:
        if self.current_func is not None:
            scope = self.func_symbols.get(self.current_func.name, {})
            if name in scope:
                return scope[name]
        if name in self.globals:
            return self.globals[name]
        raise CompileError(f"unknown variable {name}")

    def array_label(self, expr: Expr) -> str:
        if not isinstance(expr, Var):
            raise CompileError("only direct arrays are supported")
        sym = self.resolve(expr.name)
        if not sym.array_size:
            raise CompileError(f"{expr.name} is not an array")
        return sym.label

    def emit_runtime_start(self) -> None:
        self.emit("_reset:")
        self.emit("SEI")
        self.emit("CLD")
        self.emit("LDX #$40")
        self.emit("STX $4017")
        self.emit("LDX #$FF")
        self.emit("TXS")
        self.emit("INX")
        self.emit("STX $2000")
        self.emit("STX $2001")
        self.emit("STX $4010")
        self.emit("_vblank_wait_1:")
        self.emit("BIT $2002")
        self.emit("BPL _vblank_wait_1")
        self.emit("_vblank_wait_2:")
        self.emit("BIT $2002")
        self.emit("BPL _vblank_wait_2")
        self.emit("LDA #$00")
        self.emit("STA _nmi_flag")
        self.emit("LDA #$5A")
        self.emit("STA _rng_state")
        self.emit("LDA #$A5")
        self.emit("STA _rng_state_hi")
        self.emit("LDA #$01")
        self.emit("STA __ppu_rendering")
        if self.music_runtime:
            self.emit("LDA #$00")
            self.emit("STA __music_enabled")
            self.emit("STA $4015")
        if self.sfx_runtime:
            self.emit("LDA #$00")
            self.emit("STA __sfx_left")
            self.emit("STA __sfx_pos")
            self.emit("STA __sfx_hi")
            # Effects have to be audible even before music_init() runs.
            self.emit("LDA #$0F")
            self.emit("STA $4015")
            self.emit("LDA #$30")
            self.emit("STA $4004")
        self.emit("JSR _clear_nametable")
        self.emit("JSR _load_palettes")
        self.emit("LDA #$80")
        self.emit("STA $2000")
        self.emit("LDA #$0A")
        self.emit("STA $2001")
        self.emit("JSR _main")
        self.emit("_forever:")
        self.emit("JMP _forever")

    def emit_runtime_helpers(self) -> None:
        self.emit("")
        self.emit("_nmi:")
        self.emit("PHA")
        self.emit("TXA")
        self.emit("PHA")
        self.emit("TYA")
        self.emit("PHA")
        self.emit("LDA #$01")
        self.emit("STA _nmi_flag")
        self.emit("LDA __ppu_rendering")
        self.emit("BEQ __nmi_scroll_done")
        self.emit("LDA #$00")
        self.emit("STA $2005")
        self.emit("STA $2005")
        self.emit("__nmi_scroll_done:")
        if self.music_runtime:
            self.emit("JSR _music_tick")
        # Effects run after the song so a triggered effect always owns pulse 2
        # for the frames it lasts.
        if self.sfx_runtime:
            self.emit("JSR _sfx_tick")
        self.emit("PLA")
        self.emit("TAY")
        self.emit("PLA")
        self.emit("TAX")
        self.emit("PLA")
        self.emit("RTI")
        self.emit("")
        self.emit("_irq:")
        self.emit("RTI")
        self.emit("")
        self.emit("_wait_vblank:")
        self.emit("LDA #$00")
        self.emit("STA _nmi_flag")
        self.emit("_wait_vblank_loop:")
        self.emit("LDA _nmi_flag")
        self.emit("BEQ _wait_vblank_loop")
        self.emit("RTS")
        self.emit("")
        self.emit("_ppu_put:")
        self.emit("LDA $2002")
        self.emit("LDA _ppu_put_y")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("CLC")
        self.emit("ADC #$20")
        self.emit("STA $2006")
        self.emit("LDA _ppu_put_y")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("CLC")
        self.emit("ADC _ppu_put_x")
        self.emit("STA $2006")
        self.emit("LDA _ppu_put_tile")
        self.emit("STA $2007")
        self.emit("LDA #$00")
        self.emit("STA $2005")
        self.emit("STA $2005")
        self.emit("RTS")
        self.emit("")
        self.emit("_ppu_off:")
        self.emit("LDA #$00")
        self.emit("STA $2001")
        self.emit("STA __ppu_rendering")
        self.emit("RTS")
        self.emit("")
        self.emit("_ppu_on:")
        self.emit("LDA #$01")
        self.emit("STA __ppu_rendering")
        self.emit("LDA #$0A")
        self.emit("STA $2001")
        self.emit("RTS")
        self.emit("")
        self.emit("_read_pad:")
        self.emit("LDA #$01")
        self.emit("STA $4016")
        self.emit("LDA #$00")
        self.emit("STA $4016")
        self.emit("STA _pad_state")
        self.emit("LDX #$08")
        self.emit("_read_pad_loop:")
        self.emit("LDA $4016")
        self.emit("LSR A")
        self.emit("ROL _pad_state")
        self.emit("DEX")
        self.emit("BNE _read_pad_loop")
        self.emit("LDA _pad_state")
        self.emit("RTS")
        self.emit("")
        self.emit("_rand8:")
        self.emit("LDA _rng_state_hi")
        self.emit("LSR A")
        self.emit("STA _rng_state_hi")
        self.emit("LDA _rng_state")
        self.emit("ROR A")
        self.emit("STA _rng_state")
        self.emit("BCC _rand8_no_xor")
        self.emit("LDA _rng_state_hi")
        self.emit("EOR #$B4")
        self.emit("STA _rng_state_hi")
        self.emit("_rand8_no_xor:")
        self.emit("LDA _rng_state")
        self.emit("RTS")
        self.emit("")
        self.emit("_clear_nametable:")
        self.emit("LDA $2002")
        self.emit("LDA #$20")
        self.emit("STA $2006")
        self.emit("LDA #$00")
        self.emit("STA $2006")
        self.emit("LDX #$04")
        self.emit("_clear_nt_page:")
        self.emit("LDY #$00")
        self.emit("_clear_nt_loop:")
        self.emit("LDA #$00")
        self.emit("STA $2007")
        self.emit("INY")
        self.emit("BNE _clear_nt_loop")
        self.emit("DEX")
        self.emit("BNE _clear_nt_page")
        self.emit("RTS")
        self.emit("")
        self.emit("_load_palettes:")
        self.emit("LDA $2002")
        self.emit("LDA #$3F")
        self.emit("STA $2006")
        self.emit("LDA #$00")
        self.emit("STA $2006")
        self.emit("LDX #$00")
        self.emit("_load_palette_loop:")
        self.emit("LDA _palette_data,X")
        self.emit("STA $2007")
        self.emit("INX")
        self.emit("CPX #$20")
        self.emit("BNE _load_palette_loop")
        self.emit("RTS")
        self.emit("_palette_data:")
        self.emit(".byte $0F, $01, $21, $30, $0F, $06, $16, $30")
        self.emit(".byte $0F, $09, $19, $30, $0F, $04, $24, $30")
        self.emit(".byte $0F, $01, $21, $30, $0F, $06, $16, $30")
        self.emit(".byte $0F, $09, $19, $30, $0F, $04, $24, $30")
        if self.music_runtime:
            self.emit_music_runtime()
        if self.sfx_runtime:
            self.emit_sfx_runtime()
        if self.preview_runtime:
            self.emit_preview_runtime()
        if self.board_runtime:
            self.emit_board_runtime()
        if "render_queue" in self.functions:
            self.emit_render_queue_helper()
        self.emit("")
        self.emit("__mul8:")
        self.emit("STA __tmp1")
        self.emit("LDA #$00")
        self.emit("STA __tmp2")
        self.emit("LDX #$08")
        self.emit("__mul8_loop:")
        self.emit("LSR __tmp0")
        self.emit("BCC __mul8_skip")
        self.emit("CLC")
        self.emit("ADC __tmp1")
        self.emit("__mul8_skip:")
        self.emit("ASL __tmp1")
        self.emit("DEX")
        self.emit("BNE __mul8_loop")
        self.emit("RTS")
        self.emit("")
        self.emit("__divmod8:")
        self.emit("STA __tmp1")
        self.emit("LDA #$00")
        self.emit("STA __tmp2")
        self.emit("LDA __tmp0")
        self.emit("CMP #$00")
        self.emit("BEQ __divmod_done")
        self.emit("__divmod_loop:")
        self.emit("LDA __tmp1")
        self.emit("CMP __tmp0")
        self.emit("BCC __divmod_done")
        self.emit("SEC")
        self.emit("SBC __tmp0")
        self.emit("STA __tmp1")
        self.emit("INC __tmp2")
        self.emit("JMP __divmod_loop")
        self.emit("__divmod_done:")
        self.emit("LDA __tmp2")
        self.emit("RTS")

    def emit_compressed_music_runtime(self) -> None:
        self.emit("")
        self.emit("_music_init:")
        self.emit("LDA #$00")
        self.emit("STA __music_enabled")
        self.emit("STA __music_step")
        self.emit("STA __music_order_lo")
        self.emit("STA __music_order_page")
        self.emit("STA __music_pattern_step")
        # Start one increment before overflow so step zero is heard on the
        # first NMI after music_init().  $2730 is 138 BPM at NTSC cadence.
        self.emit("LDA #$D0")
        self.emit("STA __music_phase_lo")
        self.emit("LDA #$D8")
        self.emit("STA __music_phase_hi")
        self.emit("LDA #$30")
        self.emit("STA __music_phase_inc_lo")
        self.emit("LDA #$27")
        self.emit("STA __music_phase_inc_hi")
        self.emit("LDA #$FF")
        self.emit("STA __music_last_pulse1")
        self.emit("STA __music_last_pulse2")
        self.emit("STA __music_last_triangle")
        self.emit("LDA #$70")
        self.emit("STA $4000")
        self.emit("LDA #$08")
        self.emit("STA $4001")
        self.emit("LDA #$30")
        self.emit("STA $4004")
        self.emit("LDA #$08")
        self.emit("STA $4005")
        self.emit("LDA #$80")
        self.emit("STA $4008")
        self.emit("LDA #$30")
        self.emit("STA $400C")
        self.emit("LDA #$0F")
        self.emit("STA $4015")
        self.emit("LDA #$01")
        self.emit("STA __music_enabled")
        self.emit("RTS")

        self.emit_music_transport()

        self.emit("")
        self.emit("_music_tick:")
        self.emit("LDA __music_enabled")
        self.emit("BNE __music_tick_compressed_active")
        self.emit("RTS")
        self.emit("__music_tick_compressed_active:")
        self.emit("CLC")
        self.emit("LDA __music_phase_lo")
        self.emit("ADC __music_phase_inc_lo")
        self.emit("STA __music_phase_lo")
        self.emit("LDA __music_phase_hi")
        self.emit("ADC __music_phase_inc_hi")
        self.emit("STA __music_phase_hi")
        self.emit("BCS __music_compressed_step_due")
        self.emit("RTS")
        self.emit("__music_compressed_step_due:")
        self.emit("LDA __music_pattern_step")
        self.emit("BNE __music_compressed_patterns_ready")
        self.emit("JSR __music_load_pattern")
        self.emit("__music_compressed_patterns_ready:")

        # Pulse 1: 25 percent duty, constant volume 11.
        self.emit("JSR __music_decode_pulse1")
        self.emit("CMP __music_last_pulse1")
        self.emit("BEQ __music_compressed_pulse1_done")
        self.emit("STA __music_last_pulse1")
        self.emit("CMP #$1D")
        self.emit("BCC __music_compressed_pulse1_rest")
        self.emit("CMP #$60")
        self.emit("BCS __music_compressed_pulse1_rest")
        self.emit("SEC")
        self.emit("SBC #$1D")
        self.emit("TAX")
        self.emit("LDA #$7B")
        self.emit("STA $4000")
        self.emit("LDA __music_pulse_timer_lo,X")
        self.emit("STA $4002")
        self.emit("LDA __music_pulse_timer_hi,X")
        self.emit("ORA #$F8")
        self.emit("STA $4003")
        self.emit("JMP __music_compressed_pulse1_done")
        self.emit("__music_compressed_pulse1_rest:")
        self.emit("LDA #$70")
        self.emit("STA $4000")
        self.emit("__music_compressed_pulse1_done:")

        # Pulse 2: 12.5 percent duty, constant volume 6.
        self.emit("JSR __music_decode_pulse2")
        self.emit("CMP __music_last_pulse2")
        self.emit("BEQ __music_compressed_pulse2_done")
        self.emit("STA __music_last_pulse2")
        self.emit("CMP #$1D")
        self.emit("BCC __music_compressed_pulse2_rest")
        self.emit("CMP #$60")
        self.emit("BCS __music_compressed_pulse2_rest")
        self.emit("SEC")
        self.emit("SBC #$1D")
        self.emit("TAX")
        self.emit("LDA #$36")
        self.emit("STA $4004")
        self.emit("LDA __music_pulse_timer_lo,X")
        self.emit("STA $4006")
        self.emit("LDA __music_pulse_timer_hi,X")
        self.emit("ORA #$F8")
        self.emit("STA $4007")
        self.emit("JMP __music_compressed_pulse2_done")
        self.emit("__music_compressed_pulse2_rest:")
        self.emit("LDA #$30")
        self.emit("STA $4004")
        self.emit("__music_compressed_pulse2_done:")

        # Triangle has a divide-by-32 timer, unlike the pulse channels.
        self.emit("JSR __music_decode_triangle")
        self.emit("CMP __music_last_triangle")
        self.emit("BEQ __music_compressed_triangle_done")
        self.emit("STA __music_last_triangle")
        self.emit("CMP #$1D")
        self.emit("BCC __music_compressed_triangle_rest")
        self.emit("CMP #$60")
        self.emit("BCS __music_compressed_triangle_rest")
        self.emit("SEC")
        self.emit("SBC #$1D")
        self.emit("TAX")
        self.emit("LDA #$FF")
        self.emit("STA $4008")
        self.emit("LDA __music_triangle_timer_lo,X")
        self.emit("STA $400A")
        self.emit("LDA __music_triangle_timer_hi,X")
        self.emit("ORA #$F8")
        self.emit("STA $400B")
        self.emit("JMP __music_compressed_triangle_done")
        self.emit("__music_compressed_triangle_rest:")
        self.emit("LDA #$80")
        self.emit("STA $4008")
        self.emit("LDA #$00")
        self.emit("STA $400A")
        self.emit("STA $400B")
        self.emit("__music_compressed_triangle_done:")

        # Noise is retriggered on every percussion step.
        self.emit("JSR __music_decode_noise")
        self.emit("CMP #$01")
        self.emit("BEQ __music_compressed_noise_closed_hat")
        self.emit("CMP #$02")
        self.emit("BEQ __music_compressed_noise_open_hat")
        self.emit("CMP #$03")
        self.emit("BEQ __music_compressed_noise_kick")
        self.emit("CMP #$04")
        self.emit("BEQ __music_compressed_noise_snare")
        self.emit("CMP #$05")
        self.emit("BEQ __music_compressed_noise_tom")
        self.emit("CMP #$06")
        self.emit("BEQ __music_compressed_noise_cymbal")
        self.emit("LDA #$30")
        self.emit("STA $400C")
        self.emit("JMP __music_compressed_noise_done")
        self.emit("__music_compressed_noise_closed_hat:")
        self.emit("LDA #$34")
        self.emit("STA $400C")
        self.emit("LDA #$82")
        self.emit("STA $400E")
        self.emit("JMP __music_compressed_noise_trigger")
        self.emit("__music_compressed_noise_open_hat:")
        self.emit("LDA #$35")
        self.emit("STA $400C")
        self.emit("LDA #$84")
        self.emit("STA $400E")
        self.emit("JMP __music_compressed_noise_trigger")
        self.emit("__music_compressed_noise_kick:")
        self.emit("LDA #$3F")
        self.emit("STA $400C")
        self.emit("LDA #$0E")
        self.emit("STA $400E")
        self.emit("JMP __music_compressed_noise_trigger")
        self.emit("__music_compressed_noise_snare:")
        self.emit("LDA #$3C")
        self.emit("STA $400C")
        self.emit("LDA #$06")
        self.emit("STA $400E")
        self.emit("JMP __music_compressed_noise_trigger")
        self.emit("__music_compressed_noise_tom:")
        self.emit("LDA #$3A")
        self.emit("STA $400C")
        self.emit("LDA #$0B")
        self.emit("STA $400E")
        self.emit("JMP __music_compressed_noise_trigger")
        self.emit("__music_compressed_noise_cymbal:")
        self.emit("LDA #$37")
        self.emit("STA $400C")
        self.emit("LDA #$83")
        self.emit("STA $400E")
        self.emit("__music_compressed_noise_trigger:")
        self.emit("LDA #$F8")
        self.emit("STA $400F")
        self.emit("__music_compressed_noise_done:")

        self.emit("INC __music_step")
        self.emit("INC __music_pattern_step")
        self.emit("LDA __music_pattern_step")
        self.emit("CMP #$08")
        self.emit("BCC __music_compressed_tick_done")
        self.emit("LDA #$00")
        self.emit("STA __music_pattern_step")
        self.emit("INC __music_order_lo")
        self.emit("BNE __music_compressed_order_advanced")
        self.emit("INC __music_order_page")
        self.emit("__music_compressed_order_advanced:")
        # The order is 306 patterns: page zero plus 50 entries on page one.
        self.emit("LDA __music_order_page")
        self.emit("CMP #$01")
        self.emit("BCC __music_compressed_tick_done")
        self.emit("BNE __music_compressed_loop_song")
        self.emit("LDA __music_order_lo")
        self.emit("CMP #$32")
        self.emit("BCC __music_compressed_tick_done")
        self.emit("__music_compressed_loop_song:")
        self.emit("LDA #$00")
        self.emit("STA __music_order_lo")
        self.emit("STA __music_order_page")
        self.emit("__music_compressed_tick_done:")
        self.emit("RTS")

        self.emit("")
        self.emit("__music_load_pattern:")
        self.emit("LDY __music_order_lo")
        self.emit("LDA __music_order_page")
        self.emit("BEQ __music_load_order0")
        self.emit("LDA _MUSIC_ORDER1,Y")
        self.emit("JMP __music_load_tuple")
        self.emit("__music_load_order0:")
        self.emit("LDA _MUSIC_ORDER0,Y")
        self.emit("__music_load_tuple:")
        self.emit("TAY")
        self.emit("LDA _MUSIC_TUPLE_PULSE1,Y")
        self.emit("STA __music_pattern_pulse1")
        self.emit("LDA _MUSIC_TUPLE_PULSE2,Y")
        self.emit("STA __music_pattern_pulse2")
        self.emit("LDA _MUSIC_TUPLE_TRIANGLE,Y")
        self.emit("STA __music_pattern_triangle")
        self.emit("LDA _MUSIC_TUPLE_NOISE,Y")
        self.emit("STA __music_pattern_noise")
        # The accumulator has already crossed the step-zero boundary when
        # this runs, so changing the increment here applies the new tempo to
        # the interval *after* MIDI beats 492 and 494, not one step early.
        self.emit("LDA __music_order_page")
        self.emit("BNE __music_load_tempo_done")
        self.emit("LDA __music_order_lo")
        self.emit("CMP #$F2")
        self.emit("BEQ __music_load_slow_tempo")
        self.emit("CMP #$F3")
        self.emit("BNE __music_load_tempo_done")
        self.emit("LDA #$30")
        self.emit("STA __music_phase_inc_lo")
        self.emit("LDA #$27")
        self.emit("STA __music_phase_inc_hi")
        self.emit("RTS")
        self.emit("__music_load_slow_tempo:")
        self.emit("LDA #$7C")
        self.emit("STA __music_phase_inc_lo")
        self.emit("LDA #$25")
        self.emit("STA __music_phase_inc_hi")
        self.emit("RTS")
        self.emit("__music_load_tempo_done:")
        self.emit("RTS")

        def emit_tonal_decoder(label: str, stem: str, pattern_ram: str) -> None:
            self.emit("")
            self.emit(f"__music_decode_{label}:")
            self.emit(f"LDX {pattern_ram}")
            self.emit(f"LDA _MUSIC_{stem}_BASE,X")
            self.emit("STA __music_note_base")
            self.emit("LDA __music_pattern_step")
            self.emit("CMP #$02")
            self.emit(f"BCC __music_decode_{label}_pair0")
            self.emit("CMP #$04")
            self.emit(f"BCC __music_decode_{label}_pair1")
            self.emit("CMP #$06")
            self.emit(f"BCC __music_decode_{label}_pair2")
            self.emit(f"LDA _MUSIC_{stem}_PAIR3,X")
            self.emit(f"JMP __music_decode_{label}_packed")
            for pair in range(3):
                self.emit(f"__music_decode_{label}_pair{pair}:")
                self.emit(f"LDA _MUSIC_{stem}_PAIR{pair},X")
                self.emit(f"JMP __music_decode_{label}_packed")
            self.emit(f"__music_decode_{label}_packed:")
            self.emit("TAX")
            self.emit("LDA __music_pattern_step")
            self.emit("AND #$01")
            self.emit(f"BNE __music_decode_{label}_low")
            self.emit("TXA")
            self.emit("LSR A")
            self.emit("LSR A")
            self.emit("LSR A")
            self.emit("LSR A")
            self.emit(f"JMP __music_decode_{label}_note")
            self.emit(f"__music_decode_{label}_low:")
            self.emit("TXA")
            self.emit("AND #$0F")
            self.emit(f"__music_decode_{label}_note:")
            self.emit(f"BEQ __music_decode_{label}_rest")
            self.emit("CLC")
            self.emit("ADC __music_note_base")
            self.emit("SEC")
            self.emit("SBC #$01")
            self.emit("RTS")
            self.emit(f"__music_decode_{label}_rest:")
            self.emit("LDA #$00")
            self.emit("RTS")

        emit_tonal_decoder("pulse1", "PULSE1", "__music_pattern_pulse1")
        emit_tonal_decoder("pulse2", "PULSE2", "__music_pattern_pulse2")
        emit_tonal_decoder("triangle", "TRIANGLE", "__music_pattern_triangle")

        self.emit("")
        self.emit("__music_decode_noise:")
        self.emit("LDX __music_pattern_noise")
        self.emit("LDA __music_pattern_step")
        self.emit("CMP #$02")
        self.emit("BCC __music_decode_noise_pair0")
        self.emit("CMP #$04")
        self.emit("BCC __music_decode_noise_pair1")
        self.emit("CMP #$06")
        self.emit("BCC __music_decode_noise_pair2")
        self.emit("LDA _MUSIC_NOISE_PAIR3,X")
        self.emit("JMP __music_decode_noise_packed")
        for pair in range(3):
            self.emit(f"__music_decode_noise_pair{pair}:")
            self.emit(f"LDA _MUSIC_NOISE_PAIR{pair},X")
            self.emit("JMP __music_decode_noise_packed")
        self.emit("__music_decode_noise_packed:")
        self.emit("TAX")
        self.emit("LDA __music_pattern_step")
        self.emit("AND #$01")
        self.emit("BNE __music_decode_noise_low")
        self.emit("TXA")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("RTS")
        self.emit("__music_decode_noise_low:")
        self.emit("TXA")
        self.emit("AND #$0F")
        self.emit("RTS")

        self.emit_music_timer_table("__music_pulse_timer_lo", MUSIC_PULSE_TIMERS, False)
        self.emit_music_timer_table("__music_pulse_timer_hi", MUSIC_PULSE_TIMERS, True)
        self.emit_music_timer_table("__music_triangle_timer_lo", MUSIC_TRIANGLE_TIMERS, False)
        self.emit_music_timer_table("__music_triangle_timer_hi", MUSIC_TRIANGLE_TIMERS, True)

    def emit_music_transport(self) -> None:
        """Pause and resume the song without losing its position.

        Both drivers gate on __music_enabled and keep every bit of song state
        in RAM, so pausing only has to clear the flag and silence the four
        channels the driver owns.  The cached notes are invalidated so the
        first step after a resume retriggers the channels instead of assuming
        they are still sounding.  Sound effects keep playing while paused:
        _sfx_tick rewrites pulse 2 every frame regardless of this flag.
        """

        self.emit("")
        self.emit("_music_pause:")
        self.emit("LDA __music_enabled")
        self.emit("BNE __music_pause_active")
        self.emit("RTS")
        self.emit("__music_pause_active:")
        self.emit("LDA #$00")
        self.emit("STA __music_enabled")
        # The same silent register values the driver writes for a rest.
        self.emit("LDA #$70")
        self.emit("STA $4000")
        self.emit("LDA #$30")
        self.emit("STA $4004")
        self.emit("LDA #$80")
        self.emit("STA $4008")
        self.emit("LDA #$00")
        self.emit("STA $400A")
        self.emit("STA $400B")
        self.emit("LDA #$30")
        self.emit("STA $400C")
        self.emit("LDA #$FF")
        self.emit("STA __music_last_pulse1")
        self.emit("STA __music_last_pulse2")
        self.emit("STA __music_last_triangle")
        self.emit("RTS")

        self.emit("")
        self.emit("_music_resume:")
        self.emit("LDA __music_enabled")
        self.emit("BEQ __music_resume_paused")
        self.emit("RTS")
        self.emit("__music_resume_paused:")
        self.emit("LDA #$FF")
        self.emit("STA __music_last_pulse1")
        self.emit("STA __music_last_pulse2")
        self.emit("STA __music_last_triangle")
        self.emit("LDA #$0F")
        self.emit("STA $4015")
        self.emit("LDA #$01")
        self.emit("STA __music_enabled")
        self.emit("RTS")

    def emit_music_runtime(self) -> None:
        if self.music_compressed:
            self.emit_compressed_music_runtime()
            return
        self.emit("")
        self.emit("_music_init:")
        self.emit("LDA #$00")
        self.emit("STA __music_enabled")
        self.emit("STA __music_step")
        self.emit("STA __music_phase")
        self.emit("LDA #$01")
        self.emit("STA __music_frames")
        self.emit("LDA #$FF")
        self.emit("STA __music_last_pulse1")
        self.emit("STA __music_last_pulse2")
        self.emit("STA __music_last_triangle")
        self.emit("LDA #$70")
        self.emit("STA $4000")
        self.emit("LDA #$08")
        self.emit("STA $4001")
        self.emit("LDA #$30")
        self.emit("STA $4004")
        self.emit("LDA #$08")
        self.emit("STA $4005")
        self.emit("LDA #$80")
        self.emit("STA $4008")
        self.emit("LDA #$30")
        self.emit("STA $400C")
        self.emit("LDA #$0F")
        self.emit("STA $4015")
        self.emit("LDA #$01")
        self.emit("STA __music_enabled")
        self.emit("RTS")

        self.emit_music_transport()

        self.emit("")
        self.emit("_music_tick:")
        self.emit("LDA __music_enabled")
        self.emit("BNE __music_tick_active")
        self.emit("RTS")
        self.emit("__music_tick_active:")
        self.emit("DEC __music_frames")
        self.emit("BEQ __music_step_due")
        self.emit("RTS")
        self.emit("__music_step_due:")
        self.emit("LDA __music_phase")
        self.emit("BEQ __music_use_seven_frames")
        self.emit("LDA #$06")
        self.emit("STA __music_frames")
        self.emit("LDA #$00")
        self.emit("STA __music_phase")
        self.emit("JMP __music_play_step")
        self.emit("__music_use_seven_frames:")
        self.emit("LDA #$07")
        self.emit("STA __music_frames")
        self.emit("LDA #$01")
        self.emit("STA __music_phase")
        self.emit("__music_play_step:")

        # Pulse 1: 25 percent duty, constant volume 11.
        self.emit("LDX __music_step")
        self.emit("LDA _MUSIC_PULSE1,X")
        self.emit("CMP __music_last_pulse1")
        self.emit("BEQ __music_pulse1_done")
        self.emit("STA __music_last_pulse1")
        self.emit("CMP #$1D")
        self.emit("BCC __music_pulse1_rest")
        self.emit("CMP #$60")
        self.emit("BCS __music_pulse1_rest")
        self.emit("SEC")
        self.emit("SBC #$1D")
        self.emit("TAX")
        self.emit("LDA #$7B")
        self.emit("STA $4000")
        self.emit("LDA __music_pulse_timer_lo,X")
        self.emit("STA $4002")
        self.emit("LDA __music_pulse_timer_hi,X")
        self.emit("ORA #$F8")
        self.emit("STA $4003")
        self.emit("JMP __music_pulse1_done")
        self.emit("__music_pulse1_rest:")
        self.emit("LDA #$70")
        self.emit("STA $4000")
        self.emit("__music_pulse1_done:")

        # Pulse 2: 12.5 percent duty, constant volume 6.
        self.emit("LDX __music_step")
        self.emit("LDA _MUSIC_PULSE2,X")
        self.emit("CMP __music_last_pulse2")
        self.emit("BEQ __music_pulse2_done")
        self.emit("STA __music_last_pulse2")
        self.emit("CMP #$1D")
        self.emit("BCC __music_pulse2_rest")
        self.emit("CMP #$60")
        self.emit("BCS __music_pulse2_rest")
        self.emit("SEC")
        self.emit("SBC #$1D")
        self.emit("TAX")
        self.emit("LDA #$36")
        self.emit("STA $4004")
        self.emit("LDA __music_pulse_timer_lo,X")
        self.emit("STA $4006")
        self.emit("LDA __music_pulse_timer_hi,X")
        self.emit("ORA #$F8")
        self.emit("STA $4007")
        self.emit("JMP __music_pulse2_done")
        self.emit("__music_pulse2_rest:")
        self.emit("LDA #$30")
        self.emit("STA $4004")
        self.emit("__music_pulse2_done:")

        # Triangle has a divide-by-32 timer, unlike the pulse channels.
        self.emit("LDX __music_step")
        self.emit("LDA _MUSIC_TRIANGLE,X")
        self.emit("CMP __music_last_triangle")
        self.emit("BEQ __music_triangle_done")
        self.emit("STA __music_last_triangle")
        self.emit("CMP #$1D")
        self.emit("BCC __music_triangle_rest")
        self.emit("CMP #$60")
        self.emit("BCS __music_triangle_rest")
        self.emit("SEC")
        self.emit("SBC #$1D")
        self.emit("TAX")
        self.emit("LDA #$FF")
        self.emit("STA $4008")
        self.emit("LDA __music_triangle_timer_lo,X")
        self.emit("STA $400A")
        self.emit("LDA __music_triangle_timer_hi,X")
        self.emit("ORA #$F8")
        self.emit("STA $400B")
        self.emit("JMP __music_triangle_done")
        self.emit("__music_triangle_rest:")
        self.emit("LDA #$80")
        self.emit("STA $4008")
        self.emit("LDA #$00")
        self.emit("STA $400A")
        self.emit("STA $400B")
        self.emit("__music_triangle_done:")

        # Noise is intentionally retriggered every step, even when two
        # adjacent percussion codes match.
        self.emit("LDX __music_step")
        self.emit("LDA _MUSIC_NOISE,X")
        self.emit("CMP #$01")
        self.emit("BEQ __music_noise_closed_hat")
        self.emit("CMP #$02")
        self.emit("BEQ __music_noise_open_hat")
        self.emit("CMP #$03")
        self.emit("BEQ __music_noise_kick")
        self.emit("CMP #$04")
        self.emit("BEQ __music_noise_snare")
        self.emit("CMP #$05")
        self.emit("BEQ __music_noise_tom")
        self.emit("CMP #$06")
        self.emit("BEQ __music_noise_cymbal")
        self.emit("LDA #$30")
        self.emit("STA $400C")
        self.emit("JMP __music_noise_done")
        self.emit("__music_noise_closed_hat:")
        self.emit("LDA #$34")
        self.emit("STA $400C")
        self.emit("LDA #$82")
        self.emit("STA $400E")
        self.emit("JMP __music_noise_trigger")
        self.emit("__music_noise_open_hat:")
        self.emit("LDA #$35")
        self.emit("STA $400C")
        self.emit("LDA #$84")
        self.emit("STA $400E")
        self.emit("JMP __music_noise_trigger")
        self.emit("__music_noise_kick:")
        self.emit("LDA #$3F")
        self.emit("STA $400C")
        self.emit("LDA #$0E")
        self.emit("STA $400E")
        self.emit("JMP __music_noise_trigger")
        self.emit("__music_noise_snare:")
        self.emit("LDA #$3C")
        self.emit("STA $400C")
        self.emit("LDA #$06")
        self.emit("STA $400E")
        self.emit("JMP __music_noise_trigger")
        self.emit("__music_noise_tom:")
        self.emit("LDA #$3A")
        self.emit("STA $400C")
        self.emit("LDA #$0B")
        self.emit("STA $400E")
        self.emit("JMP __music_noise_trigger")
        self.emit("__music_noise_cymbal:")
        self.emit("LDA #$37")
        self.emit("STA $400C")
        self.emit("LDA #$83")
        self.emit("STA $400E")
        self.emit("__music_noise_trigger:")
        self.emit("LDA #$F8")
        self.emit("STA $400F")
        self.emit("__music_noise_done:")
        self.emit("INC __music_step")
        self.emit("RTS")

        self.emit_music_timer_table("__music_pulse_timer_lo", MUSIC_PULSE_TIMERS, False)
        self.emit_music_timer_table("__music_pulse_timer_hi", MUSIC_PULSE_TIMERS, True)
        self.emit_music_timer_table("__music_triangle_timer_lo", MUSIC_TRIANGLE_TIMERS, False)
        self.emit_music_timer_table("__music_triangle_timer_hi", MUSIC_TRIANGLE_TIMERS, True)

    def emit_music_timer_table(self, label: str, timers: Sequence[int], high: bool) -> None:
        self.emit(f"{label}:")
        values = [((timer >> 8) if high else timer) & 0xFF for timer in timers]
        for i in range(0, len(values), 16):
            self.emit(".byte " + ", ".join(f"${value:02X}" for value in values[i : i + 16]))

    def emit_sfx_runtime(self) -> None:
        """Frame-driven sound effects that borrow pulse 2 from the song.

        Each effect is a run of frames in SFX_CTRL/SFX_TIMER_LO/SFX_TIMER_HI;
        SFX_START and SFX_LENGTH locate that run by effect id.  While an effect
        plays it overwrites whatever the music driver put on pulse 2 in the same
        NMI, and when it finishes the channel is released back to the song.
        """

        self.emit("")
        self.emit("_sfx_play:")
        self.emit(f"LDA {self.sfx_runtime_param}")
        self.emit("BEQ __sfx_play_stop")
        self.emit(f"CMP #${SFX_SLOTS:02X}")
        self.emit("BCS __sfx_play_stop")
        self.emit("TAX")
        self.emit("LDA _SFX_LENGTH,X")
        self.emit("BEQ __sfx_play_stop")
        # Park the driver before repointing it so an NMI landing mid-update
        # cannot play one effect's frames with another effect's length.
        self.emit("LDY #$00")
        self.emit("STY __sfx_left")
        self.emit("TAY")
        self.emit("LDA _SFX_START,X")
        self.emit("STA __sfx_pos")
        self.emit("LDA #$FF")
        self.emit("STA __sfx_hi")
        self.emit("STY __sfx_left")
        self.emit("RTS")
        self.emit("__sfx_play_stop:")
        self.emit("LDA #$00")
        self.emit("STA __sfx_left")
        self.emit("JMP __sfx_release")
        self.emit("")
        self.emit("_sfx_tick:")
        self.emit("LDA __sfx_left")
        self.emit("BNE __sfx_tick_active")
        self.emit("RTS")
        self.emit("__sfx_tick_active:")
        self.emit("LDX __sfx_pos")
        self.emit("LDA _SFX_CTRL,X")
        self.emit("STA $4004")
        self.emit("LDA _SFX_TIMER_LO,X")
        self.emit("STA $4006")
        # $4007 restarts the phase, so it is only rewritten when the high timer
        # bits actually change.  Sustained effect tones stay clean that way.
        self.emit("LDA _SFX_TIMER_HI,X")
        self.emit("CMP __sfx_hi")
        self.emit("BEQ __sfx_tick_advance")
        self.emit("STA __sfx_hi")
        self.emit("ORA #$F8")
        self.emit("STA $4007")
        self.emit("__sfx_tick_advance:")
        self.emit("INC __sfx_pos")
        self.emit("DEC __sfx_left")
        self.emit("BNE __sfx_tick_done")
        self.emit("JMP __sfx_release")
        self.emit("__sfx_tick_done:")
        self.emit("RTS")
        self.emit("")
        self.emit("__sfx_release:")
        self.emit("LDA #$30")
        self.emit("STA $4004")
        if self.music_runtime:
            # Invalidate the cached note so the next song step retriggers the
            # channel instead of assuming it is still sounding.
            self.emit("LDA #$FF")
            self.emit("STA __music_last_pulse2")
        self.emit("RTS")

    def emit_render_queue_helper(self) -> None:
        self.emit("")
        self.emit("_render_queue:")
        self.emit("LDX #$00")
        self.emit("_render_queue_erase_loop:")
        self.emit("CPX _erase_count")
        self.emit("BEQ _render_queue_draw_start")
        self.emit("LDA $2002")
        self.emit("LDA _erase_y,X")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("CLC")
        self.emit("ADC #$20")
        self.emit("STA $2006")
        self.emit("LDA _erase_y,X")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("CLC")
        self.emit("ADC _erase_x,X")
        self.emit("STA $2006")
        self.emit("LDA #$00")
        self.emit("STA $2007")
        self.emit("INX")
        self.emit("JMP _render_queue_erase_loop")
        self.emit("_render_queue_draw_start:")
        self.emit("LDA _piece_t")
        self.emit("CLC")
        self.emit("ADC #$01")
        self.emit("STA __tmp3")
        self.emit("LDX #$00")
        self.emit("_render_queue_draw_loop:")
        self.emit("CPX _draw_count")
        self.emit("BEQ _render_queue_done")
        self.emit("LDA $2002")
        self.emit("LDA _draw_y,X")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("LSR A")
        self.emit("CLC")
        self.emit("ADC #$20")
        self.emit("STA $2006")
        self.emit("LDA _draw_y,X")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("ASL A")
        self.emit("CLC")
        self.emit("ADC _draw_x,X")
        self.emit("STA $2006")
        self.emit("LDA __tmp3")
        self.emit("STA $2007")
        self.emit("INX")
        self.emit("JMP _render_queue_draw_loop")
        self.emit("_render_queue_done:")
        self.emit("LDA #$00")
        self.emit("STA $2005")
        self.emit("STA $2005")
        self.emit("LDA #$00")
        self.emit("STA _erase_count")
        self.emit("STA _draw_count")
        self.emit("RTS")

    def emit_preview_runtime(self) -> None:
        self.emit("")
        self.emit("_ppu_write_preview:")
        self.emit("LDA $2002")
        self.emit("LDX #$00")
        for high, low in ((0x20, 0xF7), (0x21, 0x17), (0x21, 0x37), (0x21, 0x57)):
            self.emit(f"LDA #${high:02X}")
            self.emit("STA $2006")
            self.emit(f"LDA #${low:02X}")
            self.emit("STA $2006")
            for _ in range(4):
                self.emit("LDA _preview_tiles,X")
                self.emit("STA $2007")
                self.emit("INX")
        self.emit("LDA #$00")
        self.emit("STA $2005")
        self.emit("STA $2005")
        self.emit("RTS")

    def emit_board_runtime(self) -> None:
        self.emit("")
        self.emit("_ppu_write_board_half:")
        self.emit("LDA $2002")
        self.emit(f"LDA {self.board_runtime_param}")
        self.emit("CMP #$03")
        self.emit("BNE __ppu_write_board_check_two")
        self.emit("JMP __ppu_write_board_quarter_three")
        self.emit("__ppu_write_board_check_two:")
        self.emit("CMP #$02")
        self.emit("BNE __ppu_write_board_check_one")
        self.emit("JMP __ppu_write_board_quarter_two")
        self.emit("__ppu_write_board_check_one:")
        self.emit("CMP #$01")
        self.emit("BEQ __ppu_write_board_select_one")
        self.emit("JMP __ppu_write_board_quarter_zero")
        self.emit("__ppu_write_board_select_one:")
        self.emit("JMP __ppu_write_board_quarter_one")

        # Five rows per vblank leave ample time for a simultaneous full music
        # decoder tick.  The public helper keeps its historical name so older
        # source remains source-compatible; its selector now accepts 0..3.
        for quarter in (3, 2, 1, 0):
            self.emit(f"__ppu_write_board_quarter_{('zero', 'one', 'two', 'three')[quarter]}:")
            self.emit(f"LDX #${quarter * 50:02X}")
            for row in range(4 + quarter * 5, 9 + quarter * 5):
                address = 0x2000 + (row * 32) + 10
                self.emit(f"LDA #${(address >> 8) & 0xFF:02X}")
                self.emit("STA $2006")
                self.emit(f"LDA #${address & 0xFF:02X}")
                self.emit("STA $2006")
                self.emit("JSR __ppu_write_board_row")
            self.emit("JMP __ppu_write_board_done")
        self.emit("__ppu_write_board_done:")
        self.emit("LDA #$00")
        self.emit("STA $2005")
        self.emit("STA $2005")
        self.emit("RTS")
        self.emit("__ppu_write_board_row:")
        for _ in range(10):
            self.emit("LDA _board,X")
            self.emit("STA $2007")
            self.emit("INX")
        self.emit("RTS")

    def emit(self, line: str) -> None:
        self.lines.append(line)

    def mangle(self, name: str) -> str:
        return f"_{name}"

    def param_label(self, fn: str, param: str) -> str:
        return f"_{fn}_{param}"

    def local_label(self, fn: str, local: str) -> str:
        return f"_{fn}_{local}"

    def new_label(self, prefix: str) -> str:
        self.label_id += 1
        safe = prefix.replace(" ", "_")
        return f"__{safe}_{self.label_id}"


OPCODES: Dict[Tuple[str, str], int] = {
    ("ADC", "imm"): 0x69,
    ("ADC", "abs"): 0x6D,
    ("ADC", "absx"): 0x7D,
    ("ADC", "absy"): 0x79,
    ("AND", "imm"): 0x29,
    ("AND", "abs"): 0x2D,
    ("AND", "absx"): 0x3D,
    ("AND", "absy"): 0x39,
    ("ASL", "acc"): 0x0A,
    ("ASL", "abs"): 0x0E,
    ("BCC", "rel"): 0x90,
    ("BCS", "rel"): 0xB0,
    ("BEQ", "rel"): 0xF0,
    ("BIT", "abs"): 0x2C,
    ("BMI", "rel"): 0x30,
    ("BNE", "rel"): 0xD0,
    ("BPL", "rel"): 0x10,
    ("BVC", "rel"): 0x50,
    ("BVS", "rel"): 0x70,
    ("CMP", "imm"): 0xC9,
    ("CMP", "abs"): 0xCD,
    ("CMP", "absx"): 0xDD,
    ("CMP", "absy"): 0xD9,
    ("CPX", "imm"): 0xE0,
    ("CPX", "abs"): 0xEC,
    ("CPY", "imm"): 0xC0,
    ("CPY", "abs"): 0xCC,
    ("DEC", "abs"): 0xCE,
    ("EOR", "imm"): 0x49,
    ("EOR", "abs"): 0x4D,
    ("EOR", "absx"): 0x5D,
    ("EOR", "absy"): 0x59,
    ("INC", "abs"): 0xEE,
    ("JMP", "abs"): 0x4C,
    ("JSR", "abs"): 0x20,
    ("LDA", "imm"): 0xA9,
    ("LDA", "abs"): 0xAD,
    ("LDA", "absx"): 0xBD,
    ("LDA", "absy"): 0xB9,
    ("LDX", "imm"): 0xA2,
    ("LDX", "abs"): 0xAE,
    ("LDX", "absy"): 0xBE,
    ("LDY", "imm"): 0xA0,
    ("LDY", "abs"): 0xAC,
    ("LDY", "absx"): 0xBC,
    ("LSR", "acc"): 0x4A,
    ("LSR", "abs"): 0x4E,
    ("ORA", "imm"): 0x09,
    ("ORA", "abs"): 0x0D,
    ("ORA", "absx"): 0x1D,
    ("ORA", "absy"): 0x19,
    ("ROL", "acc"): 0x2A,
    ("ROL", "abs"): 0x2E,
    ("ROR", "acc"): 0x6A,
    ("ROR", "abs"): 0x6E,
    ("SBC", "imm"): 0xE9,
    ("SBC", "abs"): 0xED,
    ("SBC", "absx"): 0xFD,
    ("SBC", "absy"): 0xF9,
    ("STA", "abs"): 0x8D,
    ("STA", "absx"): 0x9D,
    ("STA", "absy"): 0x99,
    ("STX", "abs"): 0x8E,
    ("STY", "abs"): 0x8C,
}

IMPLIED = {
    "CLC": 0x18,
    "CLD": 0xD8,
    "CLI": 0x58,
    "DEX": 0xCA,
    "DEY": 0x88,
    "INX": 0xE8,
    "INY": 0xC8,
    "NOP": 0xEA,
    "PHA": 0x48,
    "PLA": 0x68,
    "RTI": 0x40,
    "RTS": 0x60,
    "SEC": 0x38,
    "SED": 0xF8,
    "SEI": 0x78,
    "TAX": 0xAA,
    "TAY": 0xA8,
    "TSX": 0xBA,
    "TXA": 0x8A,
    "TXS": 0x9A,
    "TYA": 0x98,
}

BRANCHES = {"BCC", "BCS", "BEQ", "BMI", "BNE", "BPL", "BVC", "BVS"}


@dataclass
class AsmLine:
    label: Optional[str]
    op: Optional[str]
    operand: str
    source_line: int


class Assembler:
    def __init__(self):
        self.symbols: Dict[str, int] = {}
        self.ram_pc = 0x0200
        self.pc = PRG_BASE

    def assemble(self, asm: str) -> bytes:
        lines = self.parse_lines(asm)
        self.pass1(lines)
        return self.pass2(lines)

    def parse_lines(self, asm: str) -> List[AsmLine]:
        out: List[AsmLine] = []
        for num, raw in enumerate(asm.splitlines(), 1):
            text = raw.split(";", 1)[0].strip()
            if not text:
                continue
            label = None
            if ":" in text:
                before, after = text.split(":", 1)
                if before.strip():
                    label = before.strip()
                    text = after.strip()
                else:
                    raise CompileError(f"asm {num}: empty label")
            if not text:
                out.append(AsmLine(label, None, "", num))
                continue
            parts = text.split(None, 1)
            op = parts[0].upper()
            operand = parts[1].strip() if len(parts) > 1 else ""
            out.append(AsmLine(label, op, operand, num))
        return out

    def pass1(self, lines: Sequence[AsmLine]) -> None:
        self.pc = PRG_BASE
        for line in lines:
            if line.op == ".RAM":
                parts = line.operand.split()
                if len(parts) != 2:
                    raise CompileError(f"asm {line.source_line}: .ram name size")
                name, size_s = parts
                size = self.eval_value(size_s)
                if name in self.symbols:
                    raise CompileError(f"asm {line.source_line}: duplicate symbol {name}")
                if self.ram_pc + size > 0x0800:
                    raise CompileError(f"asm {line.source_line}: NES internal RAM exhausted")
                self.symbols[name] = self.ram_pc
                self.ram_pc += size
                continue
            if line.label:
                if line.label in self.symbols:
                    raise CompileError(f"asm {line.source_line}: duplicate symbol {line.label}")
                self.symbols[line.label] = self.pc
            if line.op is None:
                continue
            if line.op == ".ORG":
                self.pc = self.eval_value(line.operand)
            elif line.op == ".BYTE":
                self.pc += len(self.split_operands(line.operand))
            elif line.op == ".WORD":
                self.pc += 2 * len(self.split_operands(line.operand))
            elif line.op == ".RAM":
                pass
            else:
                self.pc += self.instruction_size(line)

    def pass2(self, lines: Sequence[AsmLine]) -> bytes:
        self.pc = PRG_BASE
        prg = bytearray([0xEA] * PRG_SIZE)
        for line in lines:
            if line.op is None or line.op == ".RAM":
                continue
            if line.op == ".ORG":
                self.pc = self.eval_value(line.operand)
            elif line.op == ".BYTE":
                for operand in self.split_operands(line.operand):
                    self.write_byte(prg, self.eval_value(operand) & 0xFF)
            elif line.op == ".WORD":
                for operand in self.split_operands(line.operand):
                    value = self.eval_value(operand) & 0xFFFF
                    self.write_byte(prg, value & 0xFF)
                    self.write_byte(prg, (value >> 8) & 0xFF)
            else:
                self.write_instruction(prg, line)
        return bytes(prg)

    def instruction_size(self, line: AsmLine) -> int:
        mnemonic = line.op or ""
        if mnemonic in IMPLIED:
            return 1
        if mnemonic in BRANCHES:
            return 2
        mode, _ = self.addressing_mode(line.operand)
        return 2 if mode == "imm" else 3 if mode in {"abs", "absx", "absy"} else 1

    def write_instruction(self, prg: bytearray, line: AsmLine) -> None:
        mnemonic = line.op or ""
        if mnemonic in IMPLIED:
            self.write_byte(prg, IMPLIED[mnemonic])
            return
        if mnemonic in BRANCHES:
            opcode = OPCODES[(mnemonic, "rel")]
            target = self.eval_value(line.operand)
            offset = target - (self.pc + 2)
            if not -128 <= offset <= 127:
                raise CompileError(f"asm {line.source_line}: branch target out of range")
            self.write_byte(prg, opcode)
            self.write_byte(prg, offset & 0xFF)
            return
        mode, operand = self.addressing_mode(line.operand)
        key = (mnemonic, mode)
        if key not in OPCODES:
            raise CompileError(f"asm {line.source_line}: unsupported instruction {mnemonic} {line.operand}")
        opcode = OPCODES[key]
        self.write_byte(prg, opcode)
        if mode == "imm":
            self.write_byte(prg, self.eval_value(operand) & 0xFF)
        elif mode in {"abs", "absx", "absy"}:
            value = self.eval_value(operand) & 0xFFFF
            self.write_byte(prg, value & 0xFF)
            self.write_byte(prg, (value >> 8) & 0xFF)

    def addressing_mode(self, operand: str) -> Tuple[str, str]:
        operand = operand.strip()
        if operand == "A":
            return "acc", ""
        if operand.startswith("#"):
            return "imm", operand[1:].strip()
        upper = operand.upper()
        if upper.endswith(",X"):
            return "absx", operand[:-2].strip()
        if upper.endswith(",Y"):
            return "absy", operand[:-2].strip()
        return "abs", operand

    def split_operands(self, operand: str) -> List[str]:
        return [part.strip() for part in operand.split(",") if part.strip()]

    def eval_value(self, text: str) -> int:
        text = text.strip()
        if text.startswith("<"):
            return self.eval_value(text[1:]) & 0xFF
        if text.startswith(">"):
            return (self.eval_value(text[1:]) >> 8) & 0xFF
        if text.startswith("$"):
            return int(text[1:], 16)
        if text.startswith("%"):
            return int(text[1:], 2)
        if text.lower().startswith("0x"):
            return int(text, 16)
        if text.startswith("-") and text[1:].isdigit():
            return int(text, 10)
        if text.isdigit():
            return int(text, 10)
        if text in self.symbols:
            return self.symbols[text]
        raise CompileError(f"unknown assembly symbol or value {text!r}")

    def write_byte(self, prg: bytearray, value: int) -> None:
        if not PRG_BASE <= self.pc <= PRG_BASE + PRG_SIZE - 1:
            raise CompileError(f"assembly writes outside 32K PRG ROM at ${self.pc:04X}")
        prg[self.pc - PRG_BASE] = value & 0xFF
        self.pc += 1


def make_chr() -> bytes:
    chr_rom = bytearray([0x00] * 0x2000)

    def put_tile(tile: int, pixels: List[List[int]]) -> None:
        base = tile * 16
        for row in range(8):
            lo = 0
            hi = 0
            for col in range(8):
                value = pixels[row][col] & 0x03
                bit = 1 << (7 - col)
                if value & 1:
                    lo |= bit
                if value & 2:
                    hi |= bit
            chr_rom[base + row] = lo
            chr_rom[base + 8 + row] = hi

    # Seven polished block faces with a one-pixel grid gap and NES-style bevel.
    for tile in range(1, 8):
        pixels = [[0 for _ in range(8)] for _ in range(8)]
        for row in range(7):
            for col in range(7):
                if row == 0 or col == 0:
                    pixels[row][col] = 3
                elif row == 6 or col == 6:
                    pixels[row][col] = 1
                else:
                    pixels[row][col] = 2

        # A tiny embossed mark makes all seven pieces readable in monochrome.
        mark_col = 2 + ((tile - 1) % 3)
        mark_row = 2 + (((tile - 1) // 3) % 2)
        pixels[mark_row][mark_col] = 3
        pixels[mark_row + 1][mark_col + 1] = 1
        put_tile(tile, pixels)

    frame = [[0 for _ in range(8)] for _ in range(8)]
    for row in range(8):
        for col in range(8):
            if row in (0, 7) or col in (0, 7):
                frame[row][col] = 1
    put_tile(8, frame)

    # Keep the legacy utility tiles used by the other examples.
    for tile in range(9, 16):
        color = ((tile - 1) % 3) + 1
        pixels = [[color for _ in range(8)] for _ in range(8)]
        put_tile(tile, pixels)

    font_5x7 = {
        "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
        "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
        "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
        "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
        "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
        "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
        "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
        "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
        "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
        "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
        "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
        "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
        "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
        "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
        "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
        "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
        "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
        "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
        "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
        "J": ("00001", "00001", "00001", "00001", "10001", "10001", "01110"),
        "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
        "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
        "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
        "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
        "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
        "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
        "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
        "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
        "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
        "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
        "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
        "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
        "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
        "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
        "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
        "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
        "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
        ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    }

    def put_glyph(tile: int, rows: Sequence[str]) -> None:
        pixels = [[0 for _ in range(8)] for _ in range(8)]
        for row, bits in enumerate(rows):
            for col, bit in enumerate(bits):
                if bit == "1":
                    pixels[row][col + 1] = 3
        put_tile(tile, pixels)

    for value in range(10):
        put_glyph(16 + value, font_5x7[str(value)])
    for value in range(26):
        put_glyph(26 + value, font_5x7[chr(ord("A") + value)])
    put_glyph(52, font_5x7["-"])
    put_glyph(53, font_5x7[":"])

    def rail_tile(horizontal: bool, vertical: bool, right: bool, bottom: bool) -> List[List[int]]:
        pixels = [[0 for _ in range(8)] for _ in range(8)]
        if horizontal:
            start = (0 if right else 2) if vertical else 0
            end = (6 if right else 8) if vertical else 8
            for col in range(start, end):
                pixels[2][col] = 3
                pixels[3][col] = 2
                pixels[4][col] = 2
                pixels[5][col] = 1
        if vertical:
            start = (0 if bottom else 2) if horizontal else 0
            end = (6 if bottom else 8) if horizontal else 8
            for row in range(start, end):
                pixels[row][2] = 3
                pixels[row][3] = 2
                pixels[row][4] = 2
                pixels[row][5] = 1
        return pixels

    put_tile(54, rail_tile(True, True, False, False))
    put_tile(55, rail_tile(True, False, True, True))
    put_tile(56, rail_tile(True, True, True, False))
    put_tile(57, rail_tile(False, True, True, True))
    put_tile(58, rail_tile(False, True, True, True))
    put_tile(59, rail_tile(True, True, False, True))
    put_tile(60, rail_tile(True, False, True, True))
    put_tile(61, rail_tile(True, True, True, True))

    sparkle = [[0 for _ in range(8)] for _ in range(8)]
    for row, col in ((1, 3), (2, 3), (3, 1), (3, 2), (3, 3), (3, 4), (3, 5), (4, 3), (5, 3)):
        sparkle[row][col] = 3 if row == 3 or col == 3 else 2
    put_tile(62, sparkle)

    flash = [[0 for _ in range(8)] for _ in range(8)]
    for row in range(1, 7):
        for col in range(1, 7):
            flash[row][col] = 3 if (row + col) % 2 == 0 else 2
    put_tile(63, flash)

    # Six 16x16 beveled glyphs, split into four tiles each, form the title logo.
    for letter_index, letter in enumerate("TETRIS"):
        mask = [[False for _ in range(16)] for _ in range(16)]
        for row, bits in enumerate(font_5x7[letter]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    for dy in range(2):
                        for dx in range(2):
                            mask[1 + row * 2 + dy][3 + col * 2 + dx] = True
        canvas = [[0 for _ in range(16)] for _ in range(16)]
        for row in range(16):
            for col in range(16):
                if not mask[row][col]:
                    continue
                top_or_left = (
                    row == 0
                    or col == 0
                    or not mask[row - 1][col]
                    or not mask[row][col - 1]
                )
                bottom_or_right = (
                    row == 15
                    or col == 15
                    or not mask[row + 1][col]
                    or not mask[row][col + 1]
                )
                canvas[row][col] = 3 if top_or_left else (1 if bottom_or_right else 2)
        base_tile = 64 + letter_index * 4
        for tile_row in range(2):
            for tile_col in range(2):
                pixels = [
                    canvas[tile_row * 8 + row][tile_col * 8 : tile_col * 8 + 8]
                    for row in range(8)
                ]
                put_tile(base_tile + tile_row * 2 + tile_col, pixels)

    # Preserve deterministic filler tiles for programs that use raw tile IDs.
    for tile in range(88, 256):
        color = ((tile - 1) % 3) + 1
        pixels = [[color for _ in range(8)] for _ in range(8)]
        put_tile(tile, pixels)

    # Menu furniture: selector arrows, an entry caret, and a name-slot rule.
    menu_glyphs = {
        88: ("........", "....2...", "...23...", "..233...", "...23...", "....2...", "........", "........"),
        89: ("........", "...2....", "...32...", "...332..", "...32...", "...2....", "........", "........"),
        90: ("........", "...33...", "..3223..", ".32..23.", "........", "........", "........", "........"),
        91: ("........", "........", "........", "........", "........", "........", ".111111.", "........"),
    }
    for tile, rows in menu_glyphs.items():
        pixels = [[0 for _ in range(8)] for _ in range(8)]
        for row, bits in enumerate(rows):
            for col, bit in enumerate(bits):
                if bit != ".":
                    pixels[row][col] = int(bit)
        put_tile(tile, pixels)

    def put_cell(base: int, rows: Sequence[str]) -> None:
        """Split one 16x16 drawing into the four tiles of a metatile.

        Tiles land in reading order - top-left, top-right, bottom-left,
        bottom-right - which is the order the platformer example writes them
        into the nametable.
        """

        if len(rows) != 16 or any(len(row) != 16 for row in rows):
            raise CompileError("a metatile drawing must be 16 rows of 16 columns")
        canvas = [
            [0 if bit == "." else int(bit) for bit in row] for row in rows
        ]
        for half_row in range(2):
            for half_col in range(2):
                pixels = [
                    canvas[half_row * 8 + row][half_col * 8 : half_col * 8 + 8]
                    for row in range(8)
                ]
                put_tile(base + half_row * 2 + half_col, pixels)

    # Platformer actors are drawn in colour 3 only.  Colour 3 is $30 in all
    # four background palettes, so the hero and the enemies stay the same
    # bright white wherever the level's attribute map puts them.
    hero_idle = (
        "................",
        ".....333333.....",
        "....33333333....",
        "....33333333....",
        "....3.3333.3....",
        "....33333333....",
        ".....333333.....",
        "......3333......",
        "...33333333333..",
        "..333333333333..",
        "..3...333333....",
        "......3333......",
        ".....333333.....",
        ".....33..33.....",
        "....333..333....",
        "...333....333...",
    )
    hero_walk = (
        "................",
        ".....333333.....",
        "....33333333....",
        "....33333333....",
        "....3.3333.3....",
        "....33333333....",
        ".....333333.....",
        "......3333......",
        "..333333333333..",
        "...33333333333..",
        "....333333...3..",
        "......3333......",
        ".....333333.....",
        "....33....33....",
        "...333.....333..",
        "..333.......333.",
    )
    hero_jump = (
        "..3..........3..",
        "..33........33..",
        "...33333333333..",
        "....33333333....",
        "....3.3333.3....",
        "....33333333....",
        ".....333333.....",
        "......3333......",
        "....33333333....",
        "...3333333333...",
        "....33333333....",
        ".....333333.....",
        "....333..333....",
        "...333....333...",
        "...33......33...",
        "................",
    )
    enemy_a = (
        "................",
        "................",
        "................",
        "...3..3..3..3...",
        "...3..3..3..3...",
        "..333333333333..",
        ".33333333333333.",
        ".33.333333.3333.",
        ".33333333333333.",
        ".333.3333.33333.",
        ".33333333333333.",
        "..333333333333..",
        "...3.3....3.3...",
        "...3.3....3.3...",
        "................",
        "................",
    )
    enemy_b = (
        "................",
        "................",
        "................",
        "................",
        "...3..3..3..3...",
        "..333333333333..",
        ".33333333333333.",
        ".33.333333.3333.",
        ".33333333333333.",
        ".333.3333.33333.",
        ".33333333333333.",
        "..333333333333..",
        "..33......33....",
        "..3.3....3..3...",
        "................",
        "................",
    )
    gem = (
        "................",
        "................",
        ".....333333.....",
        "....32222223....",
        "...3222222223...",
        "..322222222223..",
        "..322222222223..",
        "..312222222213..",
        "...3122222213...",
        "....31222213....",
        ".....312213.....",
        "......3113......",
        ".......33.......",
        "................",
        "................",
        "................",
    )
    spikes = (
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "..3...3...3...3.",
        "..3...3...3...3.",
        ".333.333.333.333",
        ".333.333.333.333",
        "3333333333333333",
        "3333333333333333",
        "2222222222222222",
        "1111111111111111",
    )
    door = (
        "................",
        "..333333333333..",
        "..311111111113..",
        "..312222222213..",
        "..312333333213..",
        "..312322223213..",
        "..312322223213..",
        "..312322223213..",
        "..312322223213..",
        "..312322223213..",
        "..312322223213..",
        "..312322223213..",
        "..312322223213..",
        "..312333333213..",
        "..311111111113..",
        "..333333333333..",
    )

    def mirrored(rows: Sequence[str]) -> Tuple[str, ...]:
        return tuple(row[::-1] for row in rows)

    put_cell(92, hero_idle)
    put_cell(96, mirrored(hero_idle))
    put_cell(100, hero_walk)
    put_cell(104, mirrored(hero_walk))
    put_cell(108, hero_jump)
    put_cell(112, mirrored(hero_jump))
    put_cell(116, enemy_a)
    put_cell(120, enemy_b)
    put_cell(124, gem)
    put_cell(128, spikes)
    put_cell(132, door)

    # Terrain is drawn from single 8x8 tiles that tile seamlessly, so a level
    # cell only needs one repeated pattern plus a grass cap.
    terrain_tiles = {
        136: (
            "11111111",
            "12111121",
            "11111111",
            "11121111",
            "21111112",
            "11111111",
            "11211111",
            "11111111",
        ),
        137: (
            "22222222",
            "23222322",
            "22222222",
            "12121121",
            "11111111",
            "12111121",
            "11111111",
            "11121111",
        ),
        138: (
            "11111111",
            "22222221",
            "32222221",
            "22222221",
            "11111111",
            "22213222",
            "22212222",
            "22212222",
        ),
    }
    for tile, rows in terrain_tiles.items():
        pixels = [[int(bit) for bit in row] for row in rows]
        put_tile(tile, pixels)
    return bytes(chr_rom)


def make_ines(prg: bytes, chr_rom: bytes) -> bytes:
    if len(prg) != PRG_SIZE:
        raise CompileError("expected one 32K PRG image")
    if len(chr_rom) != CHR_SIZE:
        raise CompileError("expected one 8K CHR bank")
    header = bytearray(b"NES\x1A")
    header.extend([PRG_BANKS, 1, 0, 0])
    header.extend([0] * 8)
    return bytes(header) + prg + chr_rom


def compile_c_to_asm(source: str) -> str:
    tokens = lex_c(source)
    program = Parser(tokens).parse()
    return CodeGenerator(program).generate()


def build_rom(source_path: Path, out_path: Path, asm_path: Optional[Path]) -> None:
    source = source_path.read_text(encoding="utf-8")
    asm = compile_c_to_asm(source)
    if asm_path is not None:
        asm_path.parent.mkdir(parents=True, exist_ok=True)
        asm_path.write_text(asm, encoding="utf-8")
    prg = Assembler().assemble(asm)
    rom = make_ines(prg, make_chr())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(rom)


def cmd_build(args: argparse.Namespace) -> int:
    build_rom(Path(args.source), Path(args.output), Path(args.asm) if args.asm else None)
    print(f"built {args.output}")
    if args.asm:
        print(f"wrote {args.asm}")
    return 0


def cmd_asm(args: argparse.Namespace) -> int:
    asm = Path(args.source).read_text(encoding="utf-8")
    prg = Assembler().assemble(asm)
    rom = make_ines(prg, make_chr())
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rom)
    print(f"built {args.output}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    source = Path(args.source).read_text(encoding="utf-8")
    asm = compile_c_to_asm(source)
    prg = Assembler().assemble(asm)
    print(f"ok: {args.source} -> {len(prg)} PRG bytes")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="FAMI-C C compiler for NES/Famicom")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="compile C and write an iNES ROM")
    p_build.add_argument("source")
    p_build.add_argument("-o", "--output", default="build/a.nes")
    p_build.add_argument("--asm", default=None)
    p_build.set_defaults(func=cmd_build)

    p_asm = sub.add_parser("asm", help="assemble FAMI-C assembly and write an iNES ROM")
    p_asm.add_argument("source")
    p_asm.add_argument("-o", "--output", default="build/a.nes")
    p_asm.set_defaults(func=cmd_asm)

    p_check = sub.add_parser("check", help="parse, compile, and assemble without writing a ROM")
    p_check.add_argument("source")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CompileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
