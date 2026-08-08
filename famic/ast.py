"""AST nodes.

Every node carries a source position so diagnostics can point at a line the
agent can edit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import Scalar


@dataclass
class Node:
    line: int = 0
    col: int = 0


# --------------------------------------------------------------------------
# Expressions
# --------------------------------------------------------------------------


@dataclass
class Expr(Node):
    pass


@dataclass
class Num(Expr):
    value: int = 0
    suffix_type: Optional[Scalar] = None


@dataclass
class StrLit(Expr):
    """A string literal.  Only valid as a bg_text()/asset argument."""

    value: str = ""


@dataclass
class Var(Expr):
    name: str = ""


@dataclass
class Index(Expr):
    base: Optional[Expr] = None
    index: Optional[Expr] = None


@dataclass
class Field(Expr):
    base: Optional[Expr] = None
    name: str = ""


@dataclass
class Call(Expr):
    name: str = ""
    args: List[Expr] = field(default_factory=list)


@dataclass
class Unary(Expr):
    op: str = ""
    expr: Optional[Expr] = None


@dataclass
class PostIncDec(Expr):
    op: str = ""
    target: Optional[Expr] = None


@dataclass
class Binary(Expr):
    op: str = ""
    left: Optional[Expr] = None
    right: Optional[Expr] = None


@dataclass
class Assign(Expr):
    op: str = "="
    target: Optional[Expr] = None
    value: Optional[Expr] = None


@dataclass
class Cast(Expr):
    to: Optional[Scalar] = None
    expr: Optional[Expr] = None


@dataclass
class Ternary(Expr):
    cond: Optional[Expr] = None
    then_expr: Optional[Expr] = None
    else_expr: Optional[Expr] = None


@dataclass
class SizeOf(Expr):
    target: object = None


# --------------------------------------------------------------------------
# Statements
# --------------------------------------------------------------------------


@dataclass
class Stmt(Node):
    pass


@dataclass
class Block(Stmt):
    statements: List[Stmt] = field(default_factory=list)


@dataclass
class If(Stmt):
    cond: Optional[Expr] = None
    then_branch: Optional[Stmt] = None
    else_branch: Optional[Stmt] = None


@dataclass
class While(Stmt):
    cond: Optional[Expr] = None
    body: Optional[Stmt] = None


@dataclass
class DoWhile(Stmt):
    body: Optional[Stmt] = None
    cond: Optional[Expr] = None


@dataclass
class For(Stmt):
    init: Optional[Stmt] = None
    cond: Optional[Expr] = None
    post: Optional[Expr] = None
    body: Optional[Stmt] = None


@dataclass
class SwitchCase:
    value: Optional[int]  # None = default
    body: List[Stmt] = field(default_factory=list)


@dataclass
class Switch(Stmt):
    value: Optional[Expr] = None
    cases: List[SwitchCase] = field(default_factory=list)


@dataclass
class Return(Stmt):
    expr: Optional[Expr] = None


@dataclass
class Break(Stmt):
    pass


@dataclass
class Continue(Stmt):
    pass


@dataclass
class ExprStmt(Stmt):
    expr: Optional[Expr] = None


@dataclass
class VarStmt(Stmt):
    decl: Optional["VarDecl"] = None


# --------------------------------------------------------------------------
# Declarations
# --------------------------------------------------------------------------


@dataclass
class VarDecl(Node):
    name: str = ""
    type: object = None          # Scalar / ArrayType / StructType
    struct_name: str = ""        # non-empty when the base type is a struct
    dims: List[int] = field(default_factory=list)
    is_const: bool = False
    is_extern: bool = False
    is_global: bool = False
    init: object = None          # int, list, str, or None


@dataclass
class Param(Node):
    name: str = ""
    type: object = None


@dataclass
class FuncDecl(Node):
    name: str = ""
    ret_type: object = None
    params: List[Param] = field(default_factory=list)
    body: Optional[Block] = None
    is_extern: bool = False


@dataclass
class AssetDecl(Node):
    kind: str = ""               # tile, tiles, palette, metasprite, metatile, map, sfx, song
    name: str = ""
    count: int = 0               # for `asset tiles NAME[N]`
    body: object = None          # raw parsed payload (list of str / list of list of int)
    options: Dict[str, object] = field(default_factory=dict)


@dataclass
class Program(Node):
    globals: List[VarDecl] = field(default_factory=list)
    functions: List[FuncDecl] = field(default_factory=list)
    assets: List[AssetDecl] = field(default_factory=list)
    structs: Dict[str, object] = field(default_factory=dict)
    enums: Dict[str, int] = field(default_factory=dict)
