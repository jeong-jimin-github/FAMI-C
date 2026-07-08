# 지원 C 모델

FAMI-C는 호스트 환경용 ISO C 전체를 목표로 하지 않습니다. NES 6502에서 예측 가능한 코드를 만들기 위해 작은 C 부분집합을 제공합니다.

## 지원하는 문법

- `char`, `unsigned char`, `int`, `unsigned int`, `void`
- 전역 변수와 전역 배열
- `const unsigned char` ROM 테이블
- 함수 선언과 함수 호출
- 정적 로컬 변수
- 배열 인덱싱
- `if`, `else`, `while`, `for`, `break`, `continue`, `return`
- 8비트 산술, 비교, 논리 연산
- 단순한 객체형 `#define`

## 제한

- 산술 ABI는 8비트입니다.
- 로컬 변수는 정적으로 할당됩니다.
- 재귀 호출은 지원하지 않습니다.
- 포인터, 구조체, 공용체, 캐스트, varargs, C 표준 라이브러리는 아직 없습니다.
- ROM은 NROM-128, mapper 0, 16 KB PRG + 8 KB CHR로 생성됩니다.

## 런타임 API

```c
extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
```

## 패드 비트

- A: `128`
- B: `64`
- Select: `32`
- Start: `16`
- Up: `8`
- Down: `4`
- Left: `2`
- Right: `1`

