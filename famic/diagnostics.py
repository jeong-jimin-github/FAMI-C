"""Machine-readable diagnostics.

Every failure the toolchain can produce carries a stable code, a source
position, and a hint that says what to write instead.  Agents act on the
hint; the prose message is secondary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Stable error codes.  The number never changes once published; docs/agent/ERRORS.md
# is generated from this table, so adding an entry here is the only place a new
# code has to be registered.
#
# E01xx  lexer / preprocessor
# E02xx  parser / syntax
# E03xx  declarations and storage
# E04xx  types and expressions
# E05xx  assets (tiles, palettes, maps, sound)
# E06xx  runtime API misuse
# E07xx  assembler / ROM layout
# W09xx  warnings
ERRORS: Dict[str, str] = {
    "E0101": "알 수 없는 문자",
    "E0102": "닫히지 않은 문자열",
    "E0103": "닫히지 않은 문자 상수",
    "E0104": "지원하지 않는 이스케이프 시퀀스",
    "E0105": "전처리기 지시문 오류",
    "E0106": "#include 파일을 찾을 수 없음",
    "E0107": "매크로 재귀 한계 초과",
    "E0201": "예상하지 못한 토큰",
    "E0202": "닫히지 않은 괄호/중괄호",
    "E0203": "지원하지 않는 문법",
    "E0204": "선언 형식 오류",
    "E0205": "초기화식 형식 오류",
    "E0301": "지역 배열은 지원하지만 크기가 필요합니다",
    "E0302": "중복 선언",
    "E0303": "알 수 없는 식별자",
    "E0304": "main 함수가 없습니다",
    "E0305": "const 값에 대입",
    "E0306": "배열이 아닌 값에 첨자 사용",
    "E0307": "함수 인자 개수 불일치",
    "E0308": "알 수 없는 함수",
    "E0309": "RAM 부족",
    "E0310": "구조체 정의를 찾을 수 없음",
    "E0311": "구조체 멤버를 찾을 수 없음",
    "E0312": "지원하지 않는 저장 종류",
    "E0401": "지원하지 않는 연산자",
    "E0402": "타입 불일치",
    "E0403": "void 값 사용",
    "E0404": "상수식이 아님",
    "E0405": "값 범위 초과",
    "E0406": "나눗셈 상수가 0",
    "E0407": "대입 대상이 좌변값이 아님",
    "E0501": "알 수 없는 asset 종류",
    "E0502": "타일 그림 형식 오류",
    "E0503": "팔레트 형식 오류",
    "E0504": "메타스프라이트 형식 오류",
    "E0505": "메타타일 형식 오류",
    "E0506": "맵 형식 오류",
    "E0507": "CHR 타일 공간 초과",
    "E0508": "효과음 형식 오류",
    "E0509": "곡 형식 오류",
    "E0510": "알 수 없는 asset 참조",
    "E0601": "런타임 API 사용 오류",
    "E0602": "지원하지 않는 인자",
    "E0701": "어셈블리 오류",
    "E0702": "PRG ROM 초과",
    "E0703": "분기 거리 초과",
    "E0704": "알 수 없는 심볼",
    "W0901": "사용하지 않는 asset",
    "W0902": "값이 잘릴 수 있음",
    "W0903": "팔레트 배경색 자동 통일",
}


@dataclass
class Diagnostic:
    code: str
    message: str
    line: int = 0
    col: int = 0
    hint: str = ""
    severity: str = "error"
    file: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "title": ERRORS.get(self.code, ""),
            "message": self.message,
            "hint": self.hint,
        }

    def format(self) -> str:
        where = self.file or "<source>"
        head = f"{where}:{self.line}:{self.col}: {self.severity} {self.code}: {self.message}"
        return head + (f"\n  힌트: {self.hint}" if self.hint else "")


class CompileError(Exception):
    """A fatal diagnostic.  Carries the structured record, not just text."""

    def __init__(
        self,
        code: str,
        message: str,
        line: int = 0,
        col: int = 0,
        hint: str = "",
        file: str = "",
    ):
        if code not in ERRORS:
            raise KeyError(f"unregistered diagnostic code {code}")
        self.diagnostic = Diagnostic(code, message, line, col, hint, "error", file)
        super().__init__(self.diagnostic.format())


@dataclass
class DiagnosticBag:
    """Warnings collected during a build that do not stop it."""

    items: List[Diagnostic] = field(default_factory=list)

    def warn(
        self, code: str, message: str, line: int = 0, col: int = 0, hint: str = ""
    ) -> None:
        if code not in ERRORS:
            raise KeyError(f"unregistered diagnostic code {code}")
        self.items.append(Diagnostic(code, message, line, col, hint, "warning"))

    def to_list(self) -> List[Dict[str, object]]:
        return [item.to_dict() for item in self.items]


def at(node: Optional[object]) -> tuple:
    """Best-effort (line, col) for any AST node that carries a position."""

    line = getattr(node, "line", 0) or 0
    col = getattr(node, "col", 0) or 0
    return line, col
