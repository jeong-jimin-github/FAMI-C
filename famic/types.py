"""The FAMI-C type model.

The NES backend has four scalar types plus arrays and structs.  The point of
carrying real types (instead of the old "everything is a byte" model) is that
`int score;` must not silently wrap at 255 -- an agent has no way to diagnose
that from the outside.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .diagnostics import CompileError


@dataclass(frozen=True)
class Scalar:
    name: str
    size: int
    signed: bool

    @property
    def is_void(self) -> bool:
        return self.size == 0

    def __str__(self) -> str:
        return self.name


VOID = Scalar("void", 0, False)
U8 = Scalar("u8", 1, False)
I8 = Scalar("i8", 1, True)
U16 = Scalar("u16", 2, False)
I16 = Scalar("i16", 2, True)


# C spellings the parser accepts, and what they mean here.  `char` is unsigned
# because every NES value an agent touches (tiles, pad bits, colours) is.
C_TYPE_NAMES: Dict[str, Scalar] = {
    "void": VOID,
    "char": U8,
    "unsigned char": U8,
    "signed char": I8,
    "int": I16,
    "unsigned int": U16,
    "unsigned": U16,
    "signed int": I16,
    "short": I16,
    "unsigned short": U16,
    # Explicit width aliases.  These are the spellings AGENTS.md tells agents to
    # use, because the width is visible at the point of declaration.
    "u8": U8,
    "i8": I8,
    "u16": U16,
    "i16": I16,
    "bool": U8,
}


@dataclass
class StructType:
    name: str
    members: List["Member"] = field(default_factory=list)

    def member(self, name: str) -> Optional["Member"]:
        for m in self.members:
            if m.name == name:
                return m
        return None

    @property
    def size(self) -> int:
        return sum(m.type.size * max(1, m.count) for m in self.members)

    def __str__(self) -> str:
        return f"struct {self.name}"


@dataclass
class Member:
    name: str
    type: Scalar
    count: int = 0  # 0 = scalar member, >0 = fixed array member


@dataclass
class ArrayType:
    element: object  # Scalar or StructType
    dims: List[int]

    @property
    def count(self) -> int:
        total = 1
        for d in self.dims:
            total *= d
        return total

    @property
    def size(self) -> int:
        return self.count * self.element.size

    def __str__(self) -> str:
        dims = "".join(f"[{d}]" for d in self.dims)
        return f"{self.element}{dims}"


def is_scalar(t: object) -> bool:
    return isinstance(t, Scalar)


def width(t: object) -> int:
    """Byte width of a scalar type; structs and arrays are not values."""

    if isinstance(t, Scalar):
        return t.size
    raise CompileError(
        "E0402",
        f"{t} 은(는) 값으로 쓸 수 없습니다",
        hint="배열은 첨자를, 구조체는 멤버를 붙여 스칼라로 만든 뒤 사용하세요.",
    )


def promote(a: Scalar, b: Scalar) -> Scalar:
    """Usual arithmetic conversion, narrowed to what the backend implements.

    Mixing widths promotes to 16 bits; mixing signedness at the same width
    prefers unsigned, matching C.
    """

    if a.is_void or b.is_void:
        raise CompileError(
            "E0403",
            "void 값은 연산에 쓸 수 없습니다",
            hint="void를 반환하는 함수의 결과를 식에 넣지 마세요.",
        )
    size = max(a.size, b.size)
    signed = a.signed and b.signed
    if size == 1:
        return I8 if signed else U8
    return I16 if signed else U16


def widen(t: Scalar) -> Scalar:
    return I16 if t.signed else U16


def fits(value: int, t: Scalar) -> bool:
    if t.size == 1:
        return -128 <= value <= 255 if not t.signed else -128 <= value <= 127
    return -32768 <= value <= 65535 if not t.signed else -32768 <= value <= 32767


def mask(value: int, t: Scalar) -> int:
    if t.size == 1:
        return value & 0xFF
    return value & 0xFFFF
