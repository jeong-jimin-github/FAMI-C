"""Parser for the FAMI-C dialect.

The dialect is C with two deliberate departures:

  * `asset` declarations, which put graphics, palettes, maps and sound in the
    same file as the code that uses them;
  * no pointers, so `*` and `&` are only ever operators.

Everything else an agent is likely to write -- structs, enums, switch,
multi-dimensional arrays, local arrays, string literals -- parses.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from . import ast
from .diagnostics import CompileError
from .lexer import Token
from .types import (
    ArrayType,
    C_TYPE_NAMES,
    Member,
    Scalar,
    StructType,
    U8,
    U16,
    VOID,
)


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
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "%": 10,
}

ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}

TYPE_KEYWORDS = {"void", "char", "int", "short", "unsigned", "signed"}

ASSET_KINDS = {"tile", "tiles", "palette", "metasprite", "metatile", "map", "sfx", "song"}


class Parser:
    def __init__(self, tokens: Sequence[Token], file: str = ""):
        self.tokens = list(tokens)
        self.pos = 0
        self.file = file
        self.structs: Dict[str, StructType] = {}
        self.enums: Dict[str, int] = {}
        self.typedefs: Dict[str, object] = {}

    # -- token helpers -----------------------------------------------------

    def peek(self, n: int = 0) -> Token:
        j = min(self.pos + n, len(self.tokens) - 1)
        return self.tokens[j]

    def next(self) -> Token:
        tok = self.peek()
        if tok.kind != "eof":
            self.pos += 1
        return tok

    def at_sym(self, s: str) -> bool:
        return self.peek().is_sym(s)

    def at_kw(self, s: str) -> bool:
        return self.peek().is_kw(s)

    def accept_sym(self, s: str) -> bool:
        if self.at_sym(s):
            self.pos += 1
            return True
        return False

    def accept_kw(self, s: str) -> bool:
        if self.at_kw(s):
            self.pos += 1
            return True
        return False

    def expect_sym(self, s: str, what: str = "") -> Token:
        tok = self.peek()
        if not tok.is_sym(s):
            raise self.error(
                "E0201",
                f"'{s}' 가 필요한데 '{tok.text()}' 를 만났습니다" + (f" ({what})" if what else ""),
                tok,
            )
        return self.next()

    def expect_id(self, what: str = "이름") -> Token:
        tok = self.peek()
        if tok.kind != "id":
            raise self.error("E0201", f"{what}이(가) 필요한데 '{tok.text()}' 를 만났습니다", tok)
        return self.next()

    def error(self, code: str, message: str, tok: Optional[Token] = None, hint: str = "") -> CompileError:
        tok = tok or self.peek()
        return CompileError(code, message, tok.line, tok.col, hint, self.file)

    # -- program -----------------------------------------------------------

    def parse_program(self) -> ast.Program:
        program = ast.Program()
        while self.peek().kind != "eof":
            if self.at_kw("asset"):
                program.assets.append(self.parse_asset())
                continue
            if self.at_kw("typedef"):
                self.parse_typedef()
                continue
            if self.at_kw("enum") and self.peek(1).kind in ("id", "sym") and self._is_enum_definition():
                self.parse_enum()
                continue
            if self.at_kw("struct") and self._is_struct_definition():
                self.parse_struct_definition()
                continue
            self.parse_top_level_declaration(program)
        program.structs = dict(self.structs)
        program.enums = dict(self.enums)
        return program

    def _is_enum_definition(self) -> bool:
        j = 1
        if self.peek(j).kind == "id":
            j += 1
        return self.peek(j).is_sym("{")

    def _is_struct_definition(self) -> bool:
        j = 1
        if self.peek(j).kind == "id":
            j += 1
        return self.peek(j).is_sym("{")

    def parse_typedef(self) -> None:
        self.next()  # typedef
        if self.at_kw("struct") and self._is_struct_definition():
            struct = self.parse_struct_definition(consume_semicolon=False)
            name = self.expect_id("typedef 이름").value
            self.typedefs[str(name)] = struct
            self.expect_sym(";")
            return
        if self.at_kw("enum") and self._is_enum_definition():
            self.parse_enum(consume_semicolon=False)
            name = self.expect_id("typedef 이름").value
            self.typedefs[str(name)] = U8
            self.expect_sym(";")
            return
        base = self.parse_type()
        name = self.expect_id("typedef 이름").value
        self.typedefs[str(name)] = base
        self.expect_sym(";")

    def parse_enum(self, consume_semicolon: bool = True) -> None:
        self.next()  # enum
        if self.peek().kind == "id":
            self.next()
        self.expect_sym("{", "enum 본문")
        value = 0
        while not self.at_sym("}"):
            name_tok = self.expect_id("enum 상수 이름")
            if self.accept_sym("="):
                value = self.parse_constant_expression()
            self.enums[str(name_tok.value)] = value
            value += 1
            if not self.accept_sym(","):
                break
        self.expect_sym("}", "enum 본문")
        if consume_semicolon:
            self.expect_sym(";")

    def parse_struct_definition(self, consume_semicolon: bool = True) -> StructType:
        start = self.next()  # struct
        name = ""
        if self.peek().kind == "id":
            name = str(self.next().value)
        self.expect_sym("{", "struct 본문")
        members: List[Member] = []
        while not self.at_sym("}"):
            mtype = self.parse_type()
            if not isinstance(mtype, Scalar):
                raise self.error(
                    "E0203",
                    "구조체 멤버는 스칼라 타입만 됩니다",
                    start,
                    hint="중첩 구조체 대신 멤버를 펼쳐 쓰세요. 예: `u8 pos_x; u8 pos_y;`",
                )
            while True:
                mname = str(self.expect_id("멤버 이름").value)
                count = 0
                if self.accept_sym("["):
                    count = self.parse_constant_expression()
                    self.expect_sym("]")
                members.append(Member(mname, mtype, count))
                if not self.accept_sym(","):
                    break
            self.expect_sym(";", "멤버 끝")
        self.expect_sym("}", "struct 본문")
        if not name:
            name = f"__anon{len(self.structs)}"
        struct = StructType(name, members)
        self.structs[name] = struct
        if consume_semicolon:
            self.expect_sym(";")
        return struct

    # -- types -------------------------------------------------------------

    def at_type(self) -> bool:
        tok = self.peek()
        if tok.kind == "kw" and (
            tok.value in TYPE_KEYWORDS or tok.value in ("const", "extern", "static", "struct")
        ):
            return True
        if tok.kind == "id" and tok.value in self.typedefs:
            return True
        if tok.kind == "id" and tok.value in C_TYPE_NAMES:
            return True
        return False

    def parse_type(self) -> object:
        """Parse a declaration specifier; returns Scalar or StructType."""

        is_const = False
        is_extern = False
        while True:
            if self.accept_kw("const"):
                is_const = True
                continue
            if self.accept_kw("extern"):
                is_extern = True
                continue
            if self.accept_kw("static"):
                continue
            break
        tok = self.peek()
        if self.at_kw("struct"):
            self.next()
            name_tok = self.expect_id("구조체 이름")
            struct = self.structs.get(str(name_tok.value))
            if struct is None:
                raise self.error(
                    "E0310",
                    f"struct {name_tok.value} 정의를 찾을 수 없습니다",
                    name_tok,
                    hint="사용하기 전에 struct 를 정의하세요.",
                )
            self._last_const = is_const
            self._last_extern = is_extern
            return struct
        if tok.kind == "id" and tok.value in self.typedefs:
            self.next()
            self._last_const = is_const
            self._last_extern = is_extern
            return self.typedefs[str(tok.value)]

        words: List[str] = []
        while True:
            t = self.peek()
            if t.kind == "kw" and t.value in TYPE_KEYWORDS:
                words.append(str(self.next().value))
                continue
            if t.kind == "id" and t.value in C_TYPE_NAMES and not words:
                words.append(str(self.next().value))
                break
            break
        if not words:
            raise self.error(
                "E0204",
                f"타입이 필요한데 '{tok.text()}' 를 만났습니다",
                tok,
                hint="쓸 수 있는 타입: u8 i8 u16 i16 void (또는 unsigned char / int 등)",
            )
        key = " ".join(words)
        scalar = C_TYPE_NAMES.get(key)
        if scalar is None:
            # `unsigned`/`signed` alone, and `long` variants, land here.
            if words == ["unsigned"]:
                scalar = U16
            else:
                raise self.error(
                    "E0204",
                    f"지원하지 않는 타입 '{key}'",
                    tok,
                    hint="쓸 수 있는 타입: u8 i8 u16 i16 void",
                )
        self._last_const = is_const
        self._last_extern = is_extern
        return scalar

    # -- top level ---------------------------------------------------------

    def parse_top_level_declaration(self, program: ast.Program) -> None:
        start = self.peek()
        if self.at_sym("*") or self.at_sym("&"):
            raise self.error(
                "E0203",
                "포인터는 지원하지 않습니다",
                start,
                hint="배열과 인덱스를 쓰세요. 예: `u8 tiles[64];` 와 `tiles[i]`.",
            )
        base = self.parse_type()
        is_const = getattr(self, "_last_const", False)
        is_extern = getattr(self, "_last_extern", False)

        if self.at_sym(";"):  # a bare `struct Foo;`
            self.next()
            return

        if self.at_sym("*"):
            raise self.error(
                "E0203",
                "포인터는 지원하지 않습니다",
                self.peek(),
                hint="배열과 인덱스를 쓰세요. 예: `u8 tiles[64];` 와 `tiles[i]`.",
            )

        name_tok = self.expect_id("선언 이름")
        name = str(name_tok.value)

        if self.at_sym("("):
            program.functions.append(
                self.parse_function(base, name, name_tok, is_extern)
            )
            return

        # One or more variable declarators.
        while True:
            decl = self.finish_var_decl(base, name, name_tok, is_const, is_extern, True)
            program.globals.append(decl)
            if self.accept_sym(","):
                name_tok = self.expect_id("선언 이름")
                name = str(name_tok.value)
                continue
            break
        self.expect_sym(";", "전역 선언 끝")

    def finish_var_decl(
        self,
        base: object,
        name: str,
        name_tok: Token,
        is_const: bool,
        is_extern: bool,
        is_global: bool,
    ) -> ast.VarDecl:
        dims: List[int] = []
        while self.accept_sym("["):
            if self.at_sym("]"):
                dims.append(-1)  # inferred from the initialiser
            else:
                dims.append(self.parse_constant_expression())
            self.expect_sym("]")
        init: object = None
        if self.accept_sym("="):
            init = self.parse_initializer()
        if dims and dims[0] == -1:
            if isinstance(init, list):
                inner = 1
                for d in dims[1:]:
                    inner *= d
                dims[0] = max(1, (len(self._flatten(init)) + inner - 1) // inner)
            elif isinstance(init, str):
                dims[0] = len(init) + 1
            else:
                raise self.error(
                    "E0204",
                    f"{name} 의 배열 크기를 알 수 없습니다",
                    name_tok,
                    hint="`u8 t[8] = {...};` 처럼 크기를 쓰거나 초기값을 주세요.",
                )
        decl = ast.VarDecl(
            line=name_tok.line,
            col=name_tok.col,
            name=name,
            type=base,
            struct_name=base.name if isinstance(base, StructType) else "",
            dims=dims,
            is_const=is_const,
            is_extern=is_extern,
            is_global=is_global,
            init=init,
        )
        return decl

    def _flatten(self, value: object) -> List[object]:
        out: List[object] = []
        if isinstance(value, list):
            for item in value:
                out.extend(self._flatten(item))
        else:
            out.append(value)
        return out

    def parse_initializer(self) -> object:
        if self.at_sym("{"):
            self.next()
            items: List[object] = []
            while not self.at_sym("}"):
                items.append(self.parse_initializer())
                if not self.accept_sym(","):
                    break
            self.expect_sym("}", "초기화식")
            return items
        if self.peek().kind == "str":
            # Adjacent string literals concatenate, as in C.
            text = ""
            while self.peek().kind == "str":
                text += str(self.next().value)
            return text
        return self.parse_constant_expression()

    def parse_function(
        self, ret_type: object, name: str, name_tok: Token, is_extern: bool
    ) -> ast.FuncDecl:
        self.expect_sym("(")
        params: List[ast.Param] = []
        if not self.at_sym(")"):
            if self.at_kw("void") and self.peek(1).is_sym(")"):
                self.next()
            else:
                while True:
                    ptype = self.parse_type()
                    if not isinstance(ptype, Scalar):
                        raise self.error(
                            "E0203",
                            "구조체는 함수 인자로 넘길 수 없습니다",
                            self.peek(),
                            hint="전역 구조체를 두고 인덱스만 넘기세요.",
                        )
                    ptok = self.expect_id("매개변수 이름")
                    if self.accept_sym("["):
                        raise self.error(
                            "E0203",
                            "배열 매개변수는 지원하지 않습니다",
                            ptok,
                            hint="전역 배열을 직접 참조하세요. NES에는 포인터가 없습니다.",
                        )
                    params.append(
                        ast.Param(line=ptok.line, col=ptok.col, name=str(ptok.value), type=ptype)
                    )
                    if not self.accept_sym(","):
                        break
        self.expect_sym(")", "매개변수 목록")
        body: Optional[ast.Block] = None
        if self.at_sym("{"):
            body = self.parse_block()
        else:
            self.expect_sym(";", "함수 선언 끝")
        return ast.FuncDecl(
            line=name_tok.line,
            col=name_tok.col,
            name=name,
            ret_type=ret_type,
            params=params,
            body=body,
            is_extern=is_extern,
        )

    # -- assets ------------------------------------------------------------

    def parse_asset(self) -> ast.AssetDecl:
        start = self.next()  # asset
        kind_tok = self.peek()
        kind = str(kind_tok.value)
        if kind not in ASSET_KINDS:
            raise self.error(
                "E0501",
                f"알 수 없는 asset 종류 '{kind}'",
                kind_tok,
                hint="사용 가능: " + " ".join(sorted(ASSET_KINDS)),
            )
        self.next()
        name_tok = self.expect_id("asset 이름")
        count = 0
        if self.accept_sym("["):
            count = self.parse_constant_expression()
            self.expect_sym("]")
        self.expect_sym("=", "asset 정의")
        body = self.parse_asset_body(kind, kind_tok)
        self.expect_sym(";", "asset 끝")
        return ast.AssetDecl(
            line=start.line,
            col=start.col,
            kind=kind,
            name=str(name_tok.value),
            count=count,
            body=body,
        )

    def parse_asset_body(self, kind: str, kind_tok: Token) -> object:
        if kind in ("tile", "tiles"):
            rows: List[str] = []
            self.expect_sym("{", f"asset {kind} 본문")
            while not self.at_sym("}"):
                tok = self.peek()
                if tok.kind != "str":
                    raise self.error(
                        "E0502",
                        f"타일 그림은 문자열 8줄이어야 합니다 ('{tok.text()}' 를 만남)",
                        tok,
                        hint='예: asset tile T = { "........" "..1111.." ... }; (8줄, 각 8글자, . 0 1 2 3)',
                    )
                rows.append(str(self.next().value))
                self.accept_sym(",")
            self.expect_sym("}", f"asset {kind} 본문")
            return rows
        # Everything else is a (possibly nested) list of integers / names.
        return self.parse_asset_list(kind_tok)

    def parse_asset_list(self, kind_tok: Token) -> List[object]:
        self.expect_sym("{", "asset 본문")
        items: List[object] = []
        while not self.at_sym("}"):
            if self.at_sym("{"):
                items.append(self.parse_asset_list(kind_tok))
            elif self.peek().kind == "str":
                items.append(str(self.next().value))
            else:
                items.append(self.parse_asset_atom())
            if not self.accept_sym(","):
                break
        self.expect_sym("}", "asset 본문")
        return items

    def parse_asset_atom(self) -> object:
        """A number, an identifier (asset/enum reference), or `name + n`."""

        tok = self.peek()
        if tok.kind == "num":
            self.next()
            return int(tok.value)
        if tok.kind == "sym" and tok.value == "-":
            self.next()
            inner = self.parse_asset_atom()
            if isinstance(inner, int):
                return -inner
            return ("neg", inner)
        if tok.kind == "id":
            self.next()
            base: object = ("ref", str(tok.value))
            while self.at_sym("+") or self.at_sym("-"):
                op = str(self.next().value)
                rhs = self.parse_asset_atom()
                base = ("add", base, rhs) if op == "+" else ("sub", base, rhs)
            return base
        raise self.error(
            "E0205",
            f"asset 항목에 '{tok.text()}' 는 쓸 수 없습니다",
            tok,
            hint="숫자, 다른 asset 이름, enum 상수만 쓸 수 있습니다.",
        )

    # -- statements --------------------------------------------------------

    def parse_block(self) -> ast.Block:
        start = self.expect_sym("{", "블록")
        stmts: List[ast.Stmt] = []
        while not self.at_sym("}"):
            if self.peek().kind == "eof":
                raise self.error(
                    "E0202", "'}' 가 없습니다", start, hint="블록을 닫으세요."
                )
            stmts.append(self.parse_statement())
        self.expect_sym("}", "블록")
        return ast.Block(line=start.line, col=start.col, statements=stmts)

    def parse_statement(self) -> ast.Stmt:
        tok = self.peek()
        if tok.is_sym("{"):
            return self.parse_block()
        if tok.is_sym(";"):
            self.next()
            return ast.ExprStmt(line=tok.line, col=tok.col, expr=None)
        if tok.is_kw("if"):
            return self.parse_if()
        if tok.is_kw("while"):
            return self.parse_while()
        if tok.is_kw("do"):
            return self.parse_do_while()
        if tok.is_kw("for"):
            return self.parse_for()
        if tok.is_kw("switch"):
            return self.parse_switch()
        if tok.is_kw("return"):
            self.next()
            expr = None if self.at_sym(";") else self.parse_expression()
            self.expect_sym(";", "return")
            return ast.Return(line=tok.line, col=tok.col, expr=expr)
        if tok.is_kw("break"):
            self.next()
            self.expect_sym(";", "break")
            return ast.Break(line=tok.line, col=tok.col)
        if tok.is_kw("continue"):
            self.next()
            self.expect_sym(";", "continue")
            return ast.Continue(line=tok.line, col=tok.col)
        if tok.is_kw("goto"):
            raise self.error(
                "E0203",
                "goto 는 지원하지 않습니다",
                tok,
                hint="상태 변수를 두고 switch 로 분기하세요.",
            )
        if tok.is_kw("struct") and self._is_struct_definition():
            self.parse_struct_definition()
            return ast.ExprStmt(line=tok.line, col=tok.col, expr=None)
        if tok.is_kw("enum") and self._is_enum_definition():
            self.parse_enum()
            return ast.ExprStmt(line=tok.line, col=tok.col, expr=None)
        if tok.is_kw("typedef"):
            self.parse_typedef()
            return ast.ExprStmt(line=tok.line, col=tok.col, expr=None)
        if self.at_type():
            return self.parse_local_declaration()
        expr = self.parse_expression()
        self.expect_sym(";", "문장 끝")
        return ast.ExprStmt(line=tok.line, col=tok.col, expr=expr)

    def parse_local_declaration(self) -> ast.Stmt:
        start = self.peek()
        base = self.parse_type()
        is_const = getattr(self, "_last_const", False)
        decls: List[ast.VarDecl] = []
        while True:
            name_tok = self.expect_id("변수 이름")
            decls.append(
                self.finish_var_decl(
                    base, str(name_tok.value), name_tok, is_const, False, False
                )
            )
            if not self.accept_sym(","):
                break
        self.expect_sym(";", "지역 선언 끝")
        if len(decls) == 1:
            return ast.VarStmt(line=start.line, col=start.col, decl=decls[0])
        return ast.Block(
            line=start.line,
            col=start.col,
            statements=[ast.VarStmt(line=d.line, col=d.col, decl=d) for d in decls],
        )

    def parse_if(self) -> ast.Stmt:
        tok = self.next()
        self.expect_sym("(", "if 조건")
        cond = self.parse_expression()
        self.expect_sym(")", "if 조건")
        then_branch = self.parse_statement()
        else_branch = None
        if self.accept_kw("else"):
            else_branch = self.parse_statement()
        return ast.If(
            line=tok.line, col=tok.col, cond=cond, then_branch=then_branch, else_branch=else_branch
        )

    def parse_while(self) -> ast.Stmt:
        tok = self.next()
        self.expect_sym("(", "while 조건")
        cond = self.parse_expression()
        self.expect_sym(")", "while 조건")
        return ast.While(line=tok.line, col=tok.col, cond=cond, body=self.parse_statement())

    def parse_do_while(self) -> ast.Stmt:
        tok = self.next()
        body = self.parse_statement()
        if not self.accept_kw("while"):
            raise self.error("E0201", "do 뒤에는 while 이 필요합니다", self.peek())
        self.expect_sym("(", "do-while 조건")
        cond = self.parse_expression()
        self.expect_sym(")", "do-while 조건")
        self.expect_sym(";", "do-while 끝")
        return ast.DoWhile(line=tok.line, col=tok.col, body=body, cond=cond)

    def parse_for(self) -> ast.Stmt:
        tok = self.next()
        self.expect_sym("(", "for")
        init: Optional[ast.Stmt] = None
        if not self.at_sym(";"):
            if self.at_type():
                init = self.parse_local_declaration()
            else:
                e = self.parse_expression()
                self.expect_sym(";", "for 초기화")
                init = ast.ExprStmt(line=tok.line, col=tok.col, expr=e)
        else:
            self.next()
        cond = None if self.at_sym(";") else self.parse_expression()
        self.expect_sym(";", "for 조건")
        post = None if self.at_sym(")") else self.parse_expression()
        self.expect_sym(")", "for")
        return ast.For(
            line=tok.line, col=tok.col, init=init, cond=cond, post=post, body=self.parse_statement()
        )

    def parse_switch(self) -> ast.Stmt:
        tok = self.next()
        self.expect_sym("(", "switch")
        value = self.parse_expression()
        self.expect_sym(")", "switch")
        self.expect_sym("{", "switch 본문")
        cases: List[ast.SwitchCase] = []
        current: Optional[ast.SwitchCase] = None
        while not self.at_sym("}"):
            if self.accept_kw("case"):
                label = self.parse_constant_expression()
                self.expect_sym(":", "case")
                current = ast.SwitchCase(label, [])
                cases.append(current)
                continue
            if self.accept_kw("default"):
                self.expect_sym(":", "default")
                current = ast.SwitchCase(None, [])
                cases.append(current)
                continue
            if current is None:
                raise self.error(
                    "E0203",
                    "switch 본문은 case 로 시작해야 합니다",
                    self.peek(),
                    hint="`switch (x) { case 0: ... break; default: ... }`",
                )
            current.body.append(self.parse_statement())
        self.expect_sym("}", "switch 본문")
        return ast.Switch(line=tok.line, col=tok.col, value=value, cases=cases)

    # -- expressions -------------------------------------------------------

    def parse_expression(self) -> ast.Expr:
        return self.parse_assignment()

    def parse_assignment(self) -> ast.Expr:
        left = self.parse_ternary()
        tok = self.peek()
        if tok.kind == "sym" and tok.value in ASSIGN_OPS:
            self.next()
            value = self.parse_assignment()
            return ast.Assign(
                line=tok.line, col=tok.col, op=str(tok.value), target=left, value=value
            )
        return left

    def parse_ternary(self) -> ast.Expr:
        cond = self.parse_binary(0)
        if self.at_sym("?"):
            tok = self.next()
            then_expr = self.parse_expression()
            self.expect_sym(":", "삼항 연산자")
            else_expr = self.parse_ternary()
            return ast.Ternary(
                line=tok.line, col=tok.col, cond=cond, then_expr=then_expr, else_expr=else_expr
            )
        return cond

    def parse_binary(self, min_prec: int) -> ast.Expr:
        left = self.parse_unary()
        while True:
            tok = self.peek()
            if tok.kind != "sym":
                break
            prec = PRECEDENCE.get(str(tok.value))
            if prec is None or prec < min_prec:
                break
            self.next()
            right = self.parse_binary(prec + 1)
            left = ast.Binary(
                line=tok.line, col=tok.col, op=str(tok.value), left=left, right=right
            )
        return left

    def parse_unary(self) -> ast.Expr:
        tok = self.peek()
        if tok.kind == "sym" and tok.value in ("+", "-", "!", "~"):
            self.next()
            return ast.Unary(line=tok.line, col=tok.col, op=str(tok.value), expr=self.parse_unary())
        if tok.is_sym("*"):
            raise self.error(
                "E0203",
                "역참조(*)는 지원하지 않습니다",
                tok,
                hint="배열 인덱스를 쓰세요. 예: `tiles[i]`.",
            )
        if tok.is_sym("&"):
            raise self.error(
                "E0203",
                "주소 연산자(&)는 지원하지 않습니다",
                tok,
                hint="비트 AND는 두 값 사이에만 쓸 수 있습니다. 주소가 필요하면 배열 인덱스로 바꾸세요.",
            )
        if tok.kind == "sym" and tok.value in ("++", "--"):
            self.next()
            target = self.parse_unary()
            one = ast.Num(line=tok.line, col=tok.col, value=1)
            return ast.Assign(
                line=tok.line,
                col=tok.col,
                op="+=" if tok.value == "++" else "-=",
                target=target,
                value=one,
            )
        if tok.is_kw("sizeof"):
            self.next()
            self.expect_sym("(", "sizeof")
            if self.at_type():
                t = self.parse_type()
                self.expect_sym(")")
                return ast.Num(line=tok.line, col=tok.col, value=getattr(t, "size", 1))
            inner = self.parse_expression()
            self.expect_sym(")")
            return ast.SizeOf(line=tok.line, col=tok.col, target=inner)
        if tok.is_sym("(") and self.peek(1).kind in ("kw", "id") and self._is_cast():
            self.next()
            target = self.parse_type()
            self.expect_sym(")", "캐스트")
            if not isinstance(target, Scalar):
                raise self.error("E0402", "구조체로는 캐스트할 수 없습니다", tok)
            return ast.Cast(line=tok.line, col=tok.col, to=target, expr=self.parse_unary())
        return self.parse_postfix()

    def _is_cast(self) -> bool:
        save = self.pos
        self.pos += 1
        try:
            if not self.at_type():
                return False
            self.parse_type()
            return self.at_sym(")")
        except CompileError:
            return False
        finally:
            self.pos = save

    def parse_postfix(self) -> ast.Expr:
        expr = self.parse_primary()
        while True:
            tok = self.peek()
            if tok.is_sym("["):
                self.next()
                index = self.parse_expression()
                self.expect_sym("]", "배열 첨자")
                expr = ast.Index(line=tok.line, col=tok.col, base=expr, index=index)
                continue
            if tok.is_sym("."):
                self.next()
                name = self.expect_id("멤버 이름")
                expr = ast.Field(
                    line=tok.line, col=tok.col, base=expr, name=str(name.value)
                )
                continue
            if tok.is_sym("->"):
                raise self.error(
                    "E0203",
                    "-> 는 지원하지 않습니다 (포인터 없음)",
                    tok,
                    hint="`.` 을 쓰세요. 예: `actors[i].x`.",
                )
            if tok.kind == "sym" and tok.value in ("++", "--"):
                self.next()
                expr = ast.PostIncDec(
                    line=tok.line, col=tok.col, op=str(tok.value), target=expr
                )
                continue
            break
        return expr

    def parse_primary(self) -> ast.Expr:
        tok = self.next()
        if tok.kind == "num":
            return ast.Num(line=tok.line, col=tok.col, value=int(tok.value))
        if tok.kind == "str":
            text = str(tok.value)
            while self.peek().kind == "str":
                text += str(self.next().value)
            return ast.StrLit(line=tok.line, col=tok.col, value=text)
        if tok.kind == "id":
            name = str(tok.value)
            if name in self.enums:
                return ast.Num(line=tok.line, col=tok.col, value=self.enums[name])
            if self.at_sym("("):
                self.next()
                args: List[ast.Expr] = []
                if not self.at_sym(")"):
                    while True:
                        args.append(self.parse_expression())
                        if not self.accept_sym(","):
                            break
                self.expect_sym(")", f"{name} 호출")
                return ast.Call(line=tok.line, col=tok.col, name=name, args=args)
            return ast.Var(line=tok.line, col=tok.col, name=name)
        if tok.is_sym("("):
            inner = self.parse_expression()
            self.expect_sym(")", "괄호식")
            return inner
        raise self.error(
            "E0201",
            f"식에 '{tok.text()}' 는 올 수 없습니다",
            tok,
            hint="숫자, 변수, 함수 호출, 괄호식만 올 수 있습니다.",
        )

    # -- constant folding for declarations ---------------------------------

    def parse_constant_expression(self) -> int:
        expr = self.parse_ternary()
        return self.fold(expr)

    def fold(self, expr: ast.Expr) -> int:
        if isinstance(expr, ast.Num):
            return expr.value
        if isinstance(expr, ast.Var):
            if expr.name in self.enums:
                return self.enums[expr.name]
            raise CompileError(
                "E0404",
                f"'{expr.name}' 은(는) 컴파일 시각 상수가 아닙니다",
                expr.line,
                expr.col,
                hint="배열 크기와 case 라벨에는 숫자, enum, #define 상수만 쓸 수 있습니다.",
                file=self.file,
            )
        if isinstance(expr, ast.Unary):
            v = self.fold(expr.expr)
            return {"+": v, "-": -v, "~": ~v, "!": int(not v)}[expr.op]
        if isinstance(expr, ast.Binary):
            a, b = self.fold(expr.left), self.fold(expr.right)
            ops = {
                "+": lambda: a + b,
                "-": lambda: a - b,
                "*": lambda: a * b,
                "/": lambda: a // b if b else 0,
                "%": lambda: a % b if b else 0,
                "<<": lambda: a << b,
                ">>": lambda: a >> b,
                "&": lambda: a & b,
                "|": lambda: a | b,
                "^": lambda: a ^ b,
                "==": lambda: int(a == b),
                "!=": lambda: int(a != b),
                "<": lambda: int(a < b),
                "<=": lambda: int(a <= b),
                ">": lambda: int(a > b),
                ">=": lambda: int(a >= b),
                "&&": lambda: int(bool(a) and bool(b)),
                "||": lambda: int(bool(a) or bool(b)),
            }
            if expr.op == "/" and b == 0:
                raise CompileError(
                    "E0406", "0으로 나눌 수 없습니다", expr.line, expr.col, file=self.file
                )
            return ops[expr.op]()
        if isinstance(expr, ast.Ternary):
            return self.fold(expr.then_expr) if self.fold(expr.cond) else self.fold(expr.else_expr)
        if isinstance(expr, ast.Cast):
            return self.fold(expr.expr)
        raise CompileError(
            "E0404",
            "상수식이 필요합니다",
            getattr(expr, "line", 0),
            getattr(expr, "col", 0),
            hint="배열 크기와 case 라벨은 컴파일 시각에 값이 정해져야 합니다.",
            file=self.file,
        )


def parse(tokens: Sequence[Token], file: str = "") -> ast.Program:
    return Parser(tokens, file).parse_program()
