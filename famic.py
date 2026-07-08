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
        self.emit(".org $BFFA")
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
        for name in ("__tmp0", "__tmp1", "__tmp2", "__tmp3", "_nmi_flag", "_pad_state", "_rng_state"):
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
        self.emit("JSR _clear_nametable")
        self.emit("JSR _load_palettes")
        self.emit("LDA #$80")
        self.emit("STA $2000")
        self.emit("LDA #$1E")
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
        self.emit("LDA #$00")
        self.emit("STA $2005")
        self.emit("STA $2005")
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
        self.emit("RTS")
        self.emit("")
        self.emit("_ppu_on:")
        self.emit("LDA #$1E")
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
        self.emit("LDA _rng_state")
        self.emit("ASL A")
        self.emit("BCC _rand8_no_xor")
        self.emit("EOR #$1D")
        self.emit("_rand8_no_xor:")
        self.emit("ADC _nmi_flag")
        self.emit("STA _rng_state")
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
        self.emit(".byte $0F, $30, $21, $11, $0F, $30, $27, $17")
        self.emit(".byte $0F, $30, $2A, $1A, $0F, $30, $24, $14")
        self.emit(".byte $0F, $30, $21, $11, $0F, $30, $27, $17")
        self.emit(".byte $0F, $30, $2A, $1A, $0F, $30, $24, $14")
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
        self.pc = 0x8000

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
        self.pc = 0x8000
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
        self.pc = 0x8000
        prg = bytearray([0xEA] * 0x4000)
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
        if not 0x8000 <= self.pc <= 0xBFFF:
            raise CompileError(f"assembly writes outside 16K PRG ROM at ${self.pc:04X}")
        prg[self.pc - 0x8000] = value & 0xFF
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

    for tile in range(1, 8):
        color = ((tile - 1) % 3) + 1
        pixels = [[0 for _ in range(8)] for _ in range(8)]
        for row in range(1, 7):
            for col in range(1, 7):
                pixels[row][col] = color
        put_tile(tile, pixels)

    frame = [[0 for _ in range(8)] for _ in range(8)]
    for row in range(8):
        for col in range(8):
            if row in (0, 7) or col in (0, 7):
                frame[row][col] = 1
    put_tile(8, frame)

    for tile in range(9, 256):
        color = ((tile - 1) % 3) + 1
        pixels = [[color for _ in range(8)] for _ in range(8)]
        put_tile(tile, pixels)
    return bytes(chr_rom)


def make_ines(prg: bytes, chr_rom: bytes) -> bytes:
    if len(prg) != 0x4000:
        raise CompileError("expected one 16K PRG bank")
    if len(chr_rom) != 0x2000:
        raise CompileError("expected one 8K CHR bank")
    header = bytearray(b"NES\x1A")
    header.extend([1, 1, 0, 0])
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
