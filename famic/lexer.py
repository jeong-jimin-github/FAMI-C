"""Lexer and preprocessor.

The preprocessor supports object-like and function-like `#define`, `#include`,
and `#if`/`#ifdef` conditionals.  Agents reach for all three; silently dropping
them (as the old preprocessor did for anything it did not recognise) produced
programs that compiled to the wrong thing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .diagnostics import CompileError


KEYWORDS = {
    "asset",
    "break",
    "case",
    "char",
    "const",
    "continue",
    "default",
    "do",
    "else",
    "enum",
    "extern",
    "for",
    "goto",
    "if",
    "int",
    "return",
    "short",
    "signed",
    "sizeof",
    "static",
    "struct",
    "switch",
    "typedef",
    "unsigned",
    "void",
    "while",
}

MULTI_OPS = (
    "<<=",
    ">>=",
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
    "&=",
    "|=",
    "^=",
    "++",
    "--",
    "<<",
    ">>",
    "->",
)

SINGLE_OPS = "{}()[];,:?.+-*/%<>=!~&|^"

ESCAPES = {
    "n": 10,
    "r": 13,
    "t": 9,
    "0": 0,
    "\\": 92,
    "'": 39,
    '"': 34,
    "a": 7,
    "b": 8,
    "f": 12,
    "v": 11,
}


@dataclass
class Token:
    kind: str  # kw, id, num, str, sym, eof
    value: object
    line: int
    col: int

    def text(self) -> str:
        return str(self.value)

    def is_sym(self, s: str) -> bool:
        return self.kind == "sym" and self.value == s

    def is_kw(self, s: str) -> bool:
        return self.kind == "kw" and self.value == s


def strip_comments(source: str) -> str:
    """Blank out comments, preserving line structure so positions stay true."""

    out: List[str] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if ch == '"':
            out.append(ch)
            i += 1
            while i < n and source[i] != '"':
                if source[i] == "\\" and i + 1 < n:
                    out.append(source[i])
                    i += 1
                out.append(source[i])
                i += 1
            if i < n:
                out.append('"')
                i += 1
            continue
        if ch == "'":
            out.append(ch)
            i += 1
            while i < n and source[i] != "'":
                if source[i] == "\\" and i + 1 < n:
                    out.append(source[i])
                    i += 1
                out.append(source[i])
                i += 1
            if i < n:
                out.append("'")
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            out.append("  ")
            while i < n and not (source[i] == "*" and i + 1 < n and source[i + 1] == "/"):
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            i = min(i + 2, n)
            out.append("  ")
            continue
        if ch == "/" and nxt == "/":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class Lexer:
    def __init__(self, source: str, line: int = 1, file: str = ""):
        self.source = source
        self.i = 0
        self.line = line
        self.col = 1
        self.file = file

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
                tokens.append(Token("kw" if text in KEYWORDS else "id", text, line, col))
                continue
            if ch.isdigit():
                tokens.append(Token("num", self.read_number(), line, col))
                continue
            if ch == "'":
                tokens.append(Token("num", self.read_char_literal(), line, col))
                continue
            if ch == '"':
                tokens.append(Token("str", self.read_string(), line, col))
                continue
            three = self.source[self.i : self.i + 3]
            if three in MULTI_OPS:
                for _ in range(3):
                    self.advance()
                tokens.append(Token("sym", three, line, col))
                continue
            two = self.source[self.i : self.i + 2]
            if two in MULTI_OPS:
                self.advance()
                self.advance()
                tokens.append(Token("sym", two, line, col))
                continue
            if ch in SINGLE_OPS:
                self.advance()
                tokens.append(Token("sym", ch, line, col))
                continue
            raise CompileError(
                "E0101",
                f"예상하지 못한 문자 {ch!r}",
                line,
                col,
                hint="FAMI-C는 ASCII 소스만 받습니다. 주석 밖의 한글/특수문자를 지우세요.",
                file=self.file,
            )
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
            while self.peek().isalnum():
                self.advance()
            return int(self.source[start : self.i], 16)
        if self.peek() == "0" and self.peek(1).lower() == "b":
            self.advance()
            self.advance()
            start = self.i
            while self.peek() and self.peek() in "01":
                self.advance()
            return int(self.source[start : self.i], 2)
        start = self.i
        while self.peek().isdigit():
            self.advance()
        value = int(self.source[start : self.i], 10)
        # Accept and ignore C integer suffixes (`10u`, `1000UL`).
        while self.peek() and self.peek().lower() in "ul":
            self.advance()
        return value

    def read_char_literal(self) -> int:
        line, col = self.line, self.col
        self.advance()
        ch = self.advance()
        if ch == "\\":
            esc = self.advance()
            val = ESCAPES.get(esc)
            if val is None:
                raise CompileError(
                    "E0104",
                    f"지원하지 않는 이스케이프 \\{esc}",
                    line,
                    col,
                    hint="지원 목록: " + " ".join("\\" + k for k in ESCAPES),
                    file=self.file,
                )
        else:
            val = ord(ch)
        if self.advance() != "'":
            raise CompileError(
                "E0103",
                "문자 상수가 닫히지 않았습니다",
                line,
                col,
                hint="'A' 처럼 한 글자만 넣으세요. 여러 글자는 \"...\" 문자열입니다.",
                file=self.file,
            )
        return val

    def read_string(self) -> str:
        line, col = self.line, self.col
        self.advance()
        out: List[str] = []
        while True:
            if self.i >= len(self.source):
                raise CompileError(
                    "E0102",
                    "문자열이 닫히지 않았습니다",
                    line,
                    col,
                    hint='줄 끝에서 "를 닫으세요. 여러 줄 문자열은 "..." "..." 로 이어 붙입니다.',
                    file=self.file,
                )
            ch = self.advance()
            if ch == '"':
                break
            if ch == "\\":
                esc = self.advance()
                val = ESCAPES.get(esc)
                if val is None:
                    raise CompileError(
                        "E0104",
                        f"지원하지 않는 이스케이프 \\{esc}",
                        line,
                        col,
                        hint="지원 목록: " + " ".join("\\" + k for k in ESCAPES),
                        file=self.file,
                    )
                out.append(chr(val))
                continue
            out.append(ch)
        return "".join(out)


# --------------------------------------------------------------------------
# Preprocessor
# --------------------------------------------------------------------------


@dataclass
class Macro:
    name: str
    params: Optional[List[str]]
    body: str
    line: int


class Preprocessor:
    """Handles #define / #undef / #include / #ifdef / #ifndef / #if / #else / #endif."""

    def __init__(self, include_dirs: Sequence[Path], file: str = ""):
        self.include_dirs = [Path(d) for d in include_dirs]
        self.macros: Dict[str, Macro] = {}
        self.file = file
        self.included: List[str] = []

    def run(self, source: str, file: str = "") -> str:
        out_lines: List[str] = []
        self._process(strip_comments(source), file or self.file, out_lines, depth=0)
        return "\n".join(out_lines) + "\n"

    # -- directive handling ------------------------------------------------

    def _process(self, source: str, file: str, out: List[str], depth: int) -> None:
        if depth > 16:
            raise CompileError(
                "E0106",
                "#include 중첩이 너무 깊습니다",
                hint="순환 include가 있는지 확인하세요.",
                file=file,
            )
        # Stack of (currently_taken, any_branch_taken)
        cond: List[Tuple[bool, bool]] = []
        lines = source.splitlines()
        i = 0
        while i < len(lines):
            raw = lines[i]
            i += 1
            # Line continuations belong to the directive that started them.
            while raw.rstrip().endswith("\\") and i < len(lines):
                raw = raw.rstrip()[:-1] + " " + lines[i]
                i += 1
                out.append("")
            stripped = raw.strip()
            active = all(c[0] for c in cond)

            if not stripped.startswith("#"):
                out.append(raw if active else "")
                continue

            parts = stripped[1:].strip().split(None, 1)
            if not parts:
                out.append("")
                continue
            directive = parts[0]
            rest = parts[1].strip() if len(parts) > 1 else ""
            out.append("")

            if directive in ("ifdef", "ifndef"):
                name = rest.split()[0] if rest else ""
                taken = (name in self.macros) == (directive == "ifdef")
                cond.append((active and taken, taken))
                continue
            if directive == "if":
                taken = self._eval_condition(rest, file)
                cond.append((active and taken, taken))
                continue
            if directive == "elif":
                if not cond:
                    raise CompileError("E0105", "#elif 앞에 #if가 없습니다", file=file)
                _, any_taken = cond[-1]
                outer = all(c[0] for c in cond[:-1])
                taken = (not any_taken) and self._eval_condition(rest, file)
                cond[-1] = (outer and taken, any_taken or taken)
                continue
            if directive == "else":
                if not cond:
                    raise CompileError("E0105", "#else 앞에 #if가 없습니다", file=file)
                _, any_taken = cond[-1]
                outer = all(c[0] for c in cond[:-1])
                cond[-1] = (outer and not any_taken, True)
                continue
            if directive == "endif":
                if not cond:
                    raise CompileError("E0105", "#endif 앞에 #if가 없습니다", file=file)
                cond.pop()
                continue
            if not active:
                continue
            if directive == "define":
                self._define(rest, file)
                continue
            if directive == "undef":
                self.macros.pop(rest.split()[0] if rest else "", None)
                continue
            if directive == "include":
                self._include(rest, file, out, depth)
                continue
            if directive == "pragma":
                continue
            if directive == "error":
                raise CompileError("E0105", f"#error {rest}", file=file)
            # Unknown directives are an error, not a silent skip: a dropped
            # directive changes program meaning without any signal.
            raise CompileError(
                "E0105",
                f"지원하지 않는 전처리기 지시문 #{directive}",
                file=file,
                hint="지원: #define #undef #include #if #ifdef #ifndef #elif #else #endif #pragma #error",
            )
        if cond:
            raise CompileError(
                "E0105", "#endif 가 없습니다", file=file, hint="#if/#ifdef 마다 #endif를 닫으세요."
            )

    def _define(self, rest: str, file: str) -> None:
        if not rest:
            raise CompileError("E0105", "#define 에 이름이 없습니다", file=file)
        # Function-like when '(' immediately follows the name.
        j = 0
        while j < len(rest) and (rest[j].isalnum() or rest[j] == "_"):
            j += 1
        name = rest[:j]
        if not name:
            raise CompileError("E0105", "#define 이름이 올바르지 않습니다", file=file)
        if j < len(rest) and rest[j] == "(":
            depth = 0
            k = j
            while k < len(rest):
                if rest[k] == "(":
                    depth += 1
                elif rest[k] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            if depth != 0:
                raise CompileError("E0105", f"#define {name} 의 괄호가 닫히지 않았습니다", file=file)
            params = [p.strip() for p in rest[j + 1 : k].split(",") if p.strip()]
            body = rest[k + 1 :].strip()
            self.macros[name] = Macro(name, params, body, 0)
            return
        self.macros[name] = Macro(name, None, rest[j:].strip(), 0)

    def _include(self, rest: str, file: str, out: List[str], depth: int) -> None:
        rest = rest.strip()
        if len(rest) < 2 or rest[0] not in '"<':
            raise CompileError(
                "E0105",
                "#include 형식이 잘못되었습니다",
                file=file,
                hint='#include <fami.h> 또는 #include "other.c" 형식만 받습니다.',
            )
        name = rest[1:].split('"' if rest[0] == '"' else ">", 1)[0]
        for base in self.include_dirs:
            path = base / name
            if path.is_file():
                if str(path) in self.included:
                    return
                self.included.append(str(path))
                self._process(strip_comments(path.read_text()), str(path), out, depth + 1)
                return
        raise CompileError(
            "E0106",
            f"{name} 파일을 찾을 수 없습니다",
            file=file,
            hint="탐색 경로: " + ", ".join(str(d) for d in self.include_dirs),
        )

    def _eval_condition(self, text: str, file: str) -> bool:
        expanded = self.expand_text(text)
        expanded = expanded.replace("defined", " defined ")
        tokens = expanded.split()
        parts: List[str] = []
        i = 0
        while i < len(tokens):
            if tokens[i] == "defined":
                target = tokens[i + 1].strip("()") if i + 1 < len(tokens) else ""
                parts.append("1" if target in self.macros else "0")
                i += 2
                continue
            parts.append(tokens[i])
            i += 1
        expr = " ".join(parts)
        expr = expr.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
        # Any identifier that survived expansion is 0, as in C.
        safe: List[str] = []
        for tok in expr.replace("(", " ( ").replace(")", " ) ").split():
            if tok[0].isalpha() or tok[0] == "_":
                safe.append(tok if tok in ("and", "or", "not") else "0")
            else:
                safe.append(tok)
        try:
            return bool(eval(" ".join(safe), {"__builtins__": {}}, {}))  # noqa: S307
        except Exception:
            raise CompileError(
                "E0105",
                f"#if 조건을 계산할 수 없습니다: {text}",
                file=file,
                hint="#if 에는 상수식만 쓰세요.",
            )

    # -- macro expansion ---------------------------------------------------

    def expand_text(self, text: str) -> str:
        toks = Lexer(text).tokenize()[:-1]
        return " ".join(str(t.value) for t in self.expand(toks))

    def expand(self, tokens: Sequence[Token]) -> List[Token]:
        out: List[Token] = []
        i = 0
        toks = list(tokens)
        guard = 0
        while i < len(toks):
            tok = toks[i]
            if tok.kind != "id" or tok.value not in self.macros:
                out.append(tok)
                i += 1
                continue
            guard += 1
            if guard > 200000:
                raise CompileError(
                    "E0107",
                    "매크로 전개가 끝나지 않습니다",
                    tok.line,
                    tok.col,
                    hint="자기 자신을 부르는 #define 이 있는지 확인하세요.",
                )
            macro = self.macros[str(tok.value)]
            if macro.params is None:
                body = Lexer(macro.body).tokenize()[:-1]
                toks[i : i + 1] = self._reposition(body, tok)
                continue
            if i + 1 >= len(toks) or not toks[i + 1].is_sym("("):
                out.append(tok)
                i += 1
                continue
            args, end = self._collect_args(toks, i + 1, tok)
            if len(args) != len(macro.params):
                raise CompileError(
                    "E0107",
                    f"매크로 {macro.name} 은(는) 인자 {len(macro.params)}개가 필요합니다 ({len(args)}개 받음)",
                    tok.line,
                    tok.col,
                    hint=f"#define {macro.name}({', '.join(macro.params)}) ...",
                )
            body = Lexer(macro.body).tokenize()[:-1]
            expanded: List[Token] = []
            for bt in body:
                if bt.kind == "id" and bt.value in macro.params:
                    idx = macro.params.index(str(bt.value))
                    # Parenthesise substituted arguments so precedence survives.
                    expanded.append(Token("sym", "(", tok.line, tok.col))
                    expanded.extend(self._reposition(args[idx], tok))
                    expanded.append(Token("sym", ")", tok.line, tok.col))
                else:
                    expanded.append(bt)
            toks[i : end + 1] = self._reposition(expanded, tok)
        return out

    def _collect_args(
        self, toks: List[Token], open_idx: int, origin: Token
    ) -> Tuple[List[List[Token]], int]:
        depth = 0
        args: List[List[Token]] = []
        current: List[Token] = []
        j = open_idx
        while j < len(toks):
            t = toks[j]
            if t.is_sym("("):
                depth += 1
                if depth == 1:
                    j += 1
                    continue
            elif t.is_sym(")"):
                depth -= 1
                if depth == 0:
                    if current or args:
                        args.append(current)
                    return args, j
            elif t.is_sym(",") and depth == 1:
                args.append(current)
                current = []
                j += 1
                continue
            current.append(t)
            j += 1
        raise CompileError(
            "E0202",
            "매크로 인자 괄호가 닫히지 않았습니다",
            origin.line,
            origin.col,
        )

    @staticmethod
    def _reposition(tokens: Sequence[Token], origin: Token) -> List[Token]:
        return [Token(t.kind, t.value, origin.line, origin.col) for t in tokens]


def lex(source: str, include_dirs: Sequence[Path] = (), file: str = "") -> List[Token]:
    pre = Preprocessor(include_dirs, file)
    text = pre.run(source, file)
    raw = Lexer(text, file=file).tokenize()
    expanded = pre.expand(raw[:-1])
    expanded.append(raw[-1])
    return expanded
