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
- ROM은 NROM-256, mapper 0, 32 KB PRG + 8 KB CHR로 생성됩니다.

## 런타임 API

```c
extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
```
### 효과음

프로그램이 `sfx_play`를 선언하고 드라이버가 참조하는 5개의 const 테이블을
제공하면 효과음을 사용할 수 있습니다.

```c
extern void sfx_play(unsigned char effect);

const unsigned char SFX_START[16];      /* 효과음별 시작 프레임 */
const unsigned char SFX_LENGTH[16];     /* 프레임 수, 0이면 미사용 슬롯 */
const unsigned char SFX_CTRL[N];        /* 프레임별 $4004 듀티/볼륨 */
const unsigned char SFX_TIMER_LO[N];    /* 프레임별 $4006 */
const unsigned char SFX_TIMER_HI[N];    /* 하위 3비트가 $4007로 전달 */
```

슬롯 0은 예약되어 있어 `sfx_play(0)`은 재생 중인 효과음을 정지합니다.
프레임 테이블 3개는 길이가 같아야 하며 최대 256개까지 가능합니다. 효과음이
재생되는 동안에는 음악 드라이버 다음에 펄스 2 채널을 덮어쓰고, 끝나면
채널을 BGM에 돌려줍니다.


## 패드 비트

- A: `128`
- B: `64`
- Select: `32`
- Start: `16`
- Up: `8`
- Down: `4`
- Left: `2`
- Right: `1`

