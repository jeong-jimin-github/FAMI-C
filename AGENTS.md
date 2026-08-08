# AGENTS.md — FAMI-C

**이 파일 하나만 읽고 패미컴 게임 1개를 완성할 수 있어야 한다.** 부족하면 이 파일을 고쳐라.

FAMI-C는 LLM 에이전트가 NES/패미컴 게임을 만들기 위한 C 컴파일러다.
사람의 편의는 설계 기준이 아니다. 기준은 하나다: **에이전트가 사람 없이
만들고, 스스로 검증하고, 스스로 고칠 수 있는가.**

---

## 0. 30초 요약

```bash
python famic.py build game.c -o build/game.nes    # 빌드 (.sym 심볼표도 같이 생성)
python famic.py screen build/game.nes --frames 60 # 화면을 텍스트로 확인
python famic.py run build/game.nes --frames 300 \
    --input "60:START, 90:RIGHT*40" --sym "hero_x,score:16"   # 실제로 굴려 보고 RAM 확인
python famic.py api --json                        # API 전체를 기계 판독 형식으로
```

- 게임 하나 = `.c` 파일 하나. 코드·그래픽·팔레트·맵·사운드가 전부 그 안에 있다.
- 어셈블리는 쓰지 않는다. 6502가 필요한 일은 전부 런타임이 한다.
- **기능은 호출하면 켜진다.** 켜기 위해 선언할 것은 없다.
- 모든 에러는 코드·행·열·해결법을 가진다. `--json`을 붙이면 stdout이 JSON만 낸다.

---

## 1. 가장 작은 완성 게임

이대로 복사해서 시작하라. 빌드되고, 돌아가고, 조작된다.

```c
#include <fami.h>

asset palette PAL = {
    /* 배경 팔레트 4개 */
    0x21, 0x0F, 0x27, 0x30,   0x21, 0x1A, 0x18, 0x30,
    0x21, 0x07, 0x17, 0x37,   0x21, 0x02, 0x12, 0x30,
    /* 스프라이트 팔레트 4개 */
    0x21, 0x0F, 0x11, 0x30,   0x21, 0x0F, 0x16, 0x27,
    0x21, 0x0F, 0x1A, 0x2A,   0x21, 0x0F, 0x00, 0x10
};

asset tile T_BALL = {
    "..3333.."
    ".333333."
    "33322333"
    "33222233"
    "33222233"
    "33322333"
    ".333333."
    "..3333.."
};

u8 x;
u8 y;
u16 score;

void main(void) {
    pal_load(PAL);
    bg_text(2, 2, "SCORE");
    x = 120;
    y = 110;

    while (1) {
        pad_poll();
        if (pad_held(0) & PAD_LEFT)  x = x - 1;
        if (pad_held(0) & PAD_RIGHT) x = x + 1;
        if (pad_held(0) & PAD_UP)    y = y - 1;
        if (pad_held(0) & PAD_DOWN)  y = y + 1;
        if (pad_pressed(0) & PAD_A)  score = score + 10;

        spr_clear();
        spr(x, y, T_BALL, SPR_PAL0);
        bg_number(8, 2, score, 5);

        wait_vblank();
    }
}
```

구조는 항상 이렇다:

1. `#include <fami.h>`
2. `asset` 선언들 (팔레트 → 타일 → 메타스프라이트/메타타일 → 맵 → 사운드 순서로)
3. 전역 상태
4. 함수들
5. `void main(void)` — 초기화 후 `while (1) { ... wait_vblank(); }`

`wait_vblank()`는 루프마다 **정확히 한 번**. 빠뜨리면 게임이 폭주하고,
두 번 부르면 30fps가 된다.

---

## 2. 반드시 지킬 것 / 하지 말 것

| 하지 말 것 | 대신 |
|-----------|------|
| 포인터 `*`, 주소 `&`, `->` | 배열 + 인덱스. `tiles[i]` |
| 재귀 | 반복문. 지역 변수는 정적 할당이라 재귀하면 덮어쓴다 |
| `malloc`, 표준 라이브러리, `printf` | 없다. `bg_text` / `bg_number` |
| 부동소수점 | 고정소수점. §7 참고 |
| 지역 배열에 초기값 | `const u8 이름[] = {...}` 전역으로 (ROM에 들어가 RAM을 안 쓴다) |
| 구조체를 함수 인자로 | 전역 배열 + 인덱스를 넘겨라 |
| 부호 있는 값의 `/` `%` (2의 거듭제곱 제외) | `abs8()`로 절댓값 후 나누고 부호 복원 |
| `wait_vblank()` 없는 무한 루프 | 항상 프레임마다 한 번 |
| 렌더링 중 화면 전체 다시 그리기 | `ppu_off(); ...; ppu_on();` |

| 반드시 | 이유 |
|--------|------|
| `pad_poll()`을 `pad_held/pressed/released` 앞에 | 안 부르면 입력이 갱신되지 않는다 |
| 프레임마다 `spr_clear()` 후 스프라이트를 전부 다시 그리기 | OAM은 매 프레임 새로 채운다 |
| 점수·좌표 누적처럼 255를 넘길 값은 `u16` | `u8`이면 조용히 감긴다 |
| 빌드 후 `famic run`으로 실제 확인 | 컴파일 성공 ≠ 동작 |

---

## 3. 타입

| 타입 | 폭 | 범위 | 쓰는 곳 |
|------|----|------|---------|
| `u8` | 8 | 0..255 | 좌표, 타일, 인덱스, 플래그 — **기본값** |
| `i8` | 8 | -128..127 | 속도, 방향 |
| `u16` | 16 | 0..65535 | 점수, 프레임 카운터, 큰 합계 |
| `i16` | 16 | -32768..32767 | 부호 있는 큰 값 |

C 표기도 받는다: `unsigned char`=`u8`, `char`=`u8`, `int`=`i16`, `unsigned int`=`u16`.
**폭이 이름에 보이는 `u8/i8/u16/i16`을 쓰라.** 그래야 틀리지 않는다.

산술은 C와 같이 승격된다. `u8 a = 30; u16 s = a * 100;` → **3000** (8비트로 잘리지 않는다).
결과를 `u8`에 넣으면 그때 잘린다: `u8 t = a * 100;` → 184. 이건 C와 같은 동작이다.

지원 문법: `struct`(멤버는 스칼라만), `enum`, `typedef`, 다차원 배열, 지역 배열,
`switch/case/default`, `do..while`, 삼항 `?:`, 캐스트, `sizeof`,
`#define`(함수형 포함), `#include`, `#if/#ifdef/#else/#endif`.

`struct`는 컴파일러가 배열의 배열(SoA)로 펴 준다. 그냥 자연스럽게 쓰면 된다:

```c
struct Actor { u8 x; u8 y; i8 vy; u8 alive; };
struct Actor foes[8];
foes[i].x = foes[i].x + 1;      /* 내부적으로 foes__x[i] 가 된다 */
```

---

## 4. asset — 그래픽·사운드 선언

에셋 이름은 **컴파일 시각 `u8` 상수**가 된다. 타일 번호를 손으로 맞출 일이 없다.
에셋은 자기보다 **위에 선언된** 에셋만 참조할 수 있다.

### 팔레트

```c
asset palette PAL_GAME = {
    0x0F,0x11,0x21,0x31,  0x0F,0x06,0x16,0x26,   /* 배경 0,1 */
    0x0F,0x09,0x19,0x29,  0x0F,0x00,0x10,0x30,   /* 배경 2,3 */
    0x0F,0x12,0x22,0x32,  0x0F,0x06,0x16,0x36,   /* 스프라이트 0,1 */
    0x0F,0x08,0x18,0x28,  0x0F,0x14,0x24,0x34    /* 스프라이트 2,3 */
};
```

32바이트 고정. 색은 `0x00`~`0x3F`. 각 4바이트 묶음의 첫 칸은 전부 같은
배경색이어야 하며, 다르면 컴파일러가 맞추고 경고한다(`W0903`).

### 타일

```c
asset tile T_BRICK = {
    "22222222"
    "21111112"
    "21111112"
    "22222222"
    "11122211"
    "11122211"
    "11122211"
    "22222222"
};
```

정확히 8줄, 각 줄 8글자. `.`=색0(투명/배경색), `0`~`3`=팔레트 색인.

여러 장은 `tiles`:

```c
asset tiles T_HERO[4] = { /* 8*4 = 32줄 */ };
/* T_HERO+0, T_HERO+1, T_HERO+2, T_HERO+3 */
```

16x16 캐릭터는 타일 4장이고, 순서는 **좌상 → 우상 → 좌하 → 우하**로 두는 게 편하다.

배경과 스프라이트가 **같은 256장을 공유**한다. 타일 인덱스 하나가 양쪽에서 같은 그림이다.
글자를 쓰면 내장 폰트 53장이 자동으로 들어간다. 넘치면 `E0507`이 무엇이 몇 장 썼는지 표로 알려준다.

### 메타스프라이트 (스프라이트 묶음)

```c
asset metasprite MS_HERO = {
    { 0, 0, T_HERO+0, SPR_PAL0 },   /* {dx, dy, 타일, 속성} */
    { 8, 0, T_HERO+1, SPR_PAL0 },
    { 0, 8, T_HERO+2, SPR_PAL0 },
    { 8, 8, T_HERO+3, SPR_PAL0 }
};
```

`spr_meta(x, y, MS_HERO)` 한 줄로 전부 그린다.
`spr_meta_flip(x, y, MS_HERO, 1)`은 좌우 반전 — 좌표 보정까지 런타임이 한다.

### 메타타일 + 맵 (배경 16x16 블록)

```c
asset metatile MT_GROUND = { T_GRASS, T_GRASS, T_DIRT, T_DIRT, 1 };
/*                           좌상      우상      좌하    우하   팔레트 */

asset map MAP_1 = { 4, 2,           /* 가로, 세로 (셀 단위) */
    MT_SKY,    MT_SKY,    MT_SKY,    MT_SKY,
    MT_GROUND, MT_GROUND, MT_GROUND, MT_GROUND
};
```

`bg_meta(cx, cy, MT_GROUND)`가 한 칸, `bg_map(MAP_1)`이 전체를 그린다.
16x16 칸 = NES 속성 1칸이라, 칸마다 배경 팔레트를 따로 고를 수 있다.

### 효과음

```c
asset sfx SFX_JUMP = { {13, N_C5}, {12, N_E5}, {10, N_G5}, {7, N_C6} };
/*                      볼륨0~15  음이름                            */
```

한 항목이 한 프레임. 최대 120프레임(2초). `sfx_play(SFX_JUMP)`로 재생.
재생 중에는 펄스2 채널을 빌리고, 끝나면 곡에 돌려준다.

### BGM

```c
asset song SONG_MAIN = { 9,                       /* 행당 프레임 수 */
    { N_C4, N_C5, N_C2, NOISE_KICK },   /* {펄스1, 펄스2, 삼각파, 노이즈} */
    { HOLD, N_E5, HOLD, 0          },   /* HOLD = 앞 음 유지, 0 = 쉼표   */
    { N_E4, N_G5, HOLD, NOISE_HAT  }
};
```

노이즈 채널은 `0`(쉼) `HOLD`(유지) 그리고 타악기 음색을 받는다:
`NOISE_HAT` `NOISE_HAT_OPEN` `NOISE_KICK` `NOISE_SNARE` `NOISE_TOM` `NOISE_CYMBAL`
(`8`~`15`는 생 노이즈 주기 0~7).

곡은 끝나면 처음으로 돌아간다.
음 이름은 `N_C1` ~ `N_B7` (`N_CS4`는 C#4). 전체 목록은 `include/fami.h`.

**정수 프레임으로 안 떨어지는 템포**는 두 번째 숫자에 1/256 프레임 단위 소수부를 준다.
138 BPM 16분음표는 행당 6.53프레임이므로:

```c
asset song SONG_BGM = { 6, 136,   /* 6 + 136/256 = 6.53 프레임/행 */
    { N_CS4, 0, 0, 0 },
    ...
};
```

긴 곡은 별도 파일에 두고 `#include "song.c"` 하면 된다
(`examples/tetris_song.c`가 2448행짜리 예다).

---

## 5. 런타임 API

전부 `#include <fami.h>` 후 그냥 호출한다. **선언하지 마라.**
전체 목록·시그니처·예시는 `python famic.py api --json`.

### 시스템
```c
wait_vblank();          /* 프레임 경계. 루프마다 한 번 */
u8 f = frame_count();   /* 프레임 수 하위 8비트 */
ppu_off();  ppu_on();   /* 렌더링 끄기/켜기 */
```

### 입력
```c
pad_poll();                             /* 먼저 호출 (프레임당 1회) */
if (pad_held(0)     & PAD_RIGHT) ...    /* 누르고 있는 중 */
if (pad_pressed(0)  & PAD_A) ...        /* 이번 프레임에 새로 눌림 */
if (pad_released(0) & PAD_A) ...        /* 이번 프레임에 떼어짐 */
```
플레이어는 `0` 또는 `1`. 비트: `PAD_A B SELECT START UP DOWN LEFT RIGHT`.

### 배경
```c
bg_tile(x, y, tile);           /* x 0~63, y 0~29. x>=32 는 오른쪽 화면 */
bg_rect(x, y, w, h, tile);
bg_text(2, 3, "SCORE");        /* 문자열 리터럴만 */
bg_char(4, 6, 'A' + n);        /* 계산한 글자 하나 */
bg_number(8, 3, score, 5);     /* 10진수, 앞자리 0 채움 */
bg_attr(cx, cy, pal);          /* 16x16 칸의 배경 팔레트 (cx 0~31, cy 0~14) */
bg_meta(cx, cy, MT_GROUND);
bg_map(MAP_1);
bg_clear(0);                   /* 화면 전체 + 속성 초기화 */
```

**배경 갱신 타이밍은 신경 쓰지 마라.** `bg_tile()`은 렌더링 중이면 큐에 넣고
다음 vblank에 반영하며, 큐가 차면 NMI가 비울 때까지 알아서 기다린다.
`bg_clear()`와 `bg_map()`은 내부에서 렌더링을 껐다 되돌린다.

### 스프라이트
```c
spr_clear();                       /* 매 프레임 먼저 */
spr(x, y, tile, SPR_PAL0);
spr_meta(x, y, MS_HERO);
spr_meta_flip(x, y, MS_HERO, facing_left);
u8 n = spr_count();                /* 최대 63장까지 들어간다 */
```
속성 비트: `SPR_PAL0..3`, `SPR_BEHIND`(배경 뒤), `SPR_FLIP_X`, `SPR_FLIP_Y`.

### 스크롤 / 팔레트 / 수학 / 충돌 / 사운드
```c
scroll_set(camera_x, 0);           /* x는 u16, 0~511 */

pal_load(PAL_GAME);
pal_set(index, color);             /* index 0~31 */
pal_bright(level);                 /* 0=암전 .. 4=원본. 페이드에 */

mul8(a,b)  mul16(a,b)  div8(a,b)  mod8(a,b)
abs8(v)  min8(a,b)  max8(a,b)
rand()  rand_range(n)  rand_seed(seed);

if (box_hit(ax,ay,aw,ah, bx,by,bw,bh)) ...   /* AABB 겹침 */

sfx_play(SFX_JUMP);
music_play(SONG_MAIN);  music_stop();  music_pause();  music_resume();
```

---

## 6. 검증 — 여기가 핵심

컴파일이 되는 것과 게임이 도는 것은 다르다. **매번 실제로 굴려서 확인하라.**

### 화면을 텍스트로 본다
```bash
python famic.py screen build/game.nes --frames 60 --input "20:START"
```
네임테이블 32x30을 문자로 찍는다. 폰트 타일은 실제 글자로 역매핑되므로
HUD 텍스트를 그대로 읽을 수 있다. `.`=빈 타일, `#`=그 외.

### RAM을 심볼 이름으로 본다
빌드하면 `build/game.sym`이 같이 생긴다. 전역 `hero_x`의 심볼은 `_g_hero_x`,
구조체 멤버 `hero.x`는 `_g_hero__x`, `const` 테이블은 `_r_이름`이다.

```bash
python famic.py run build/game.nes --frames 300 \
    --input "20:START, 60:RIGHT*40, 110:A" \
    --sym "_g_hero__x,_g_hero__y,_g_score:16,_g_state"
```
16비트 변수는 이름 뒤에 `:16`을 붙인다.

입력 스크립트 문법: `프레임:버튼[|버튼...][*반복]`을 쉼표로 나열.
예) `"60:START, 90:RIGHT|B*30, 150:A"`

### 회귀 시나리오로 굳힌다
`tests/specs/*.spec.json`:
```json
{ "name": "점프", "rom": "../../build/game.nes", "steps": [
    { "frames": 20, "assert": { "_g_state": 0 } },
    { "input": ["START"], "frames": 2 },
    { "input": ["A"], "frames": 12, "assert": { "_g_hero__y": { "lt": 170 } } }
]}
```
조건: `eq ne gt ge lt le`. 실행: `python famic.py test tests/specs/*.spec.json`.

### 스크린샷 (눈으로 볼 수 있을 때)
```bash
python famic.py run build/game.nes --frames 120 --screenshot shot.png --scale 3
```

### 크래시는 크래시라고 말한다
정의되지 않은 opcode, `BRK`, 끝나지 않는 프레임은 전부 PC와 함께 보고된다.
보통 코드가 데이터 영역으로 넘어갔다는 뜻이다.

---

## 7. NES에서 자주 틀리는 것

**고정소수점.** 부동소수점이 없으니 1/16픽셀 단위를 쓴다.
```c
u8 x;  u8 xsub;            /* 12.4 고정소수점 */
#define SUB_PX 16
#define SPEED  20          /* 1.25 px/frame */

sub = xsub + SPEED;
x = x + sub / SUB_PX;      /* 정수부만 픽셀에 반영 */
xsub = sub & 15;           /* 나머지는 다음 프레임으로 */
```

**속성(팔레트) 해상도.** 색은 8x8이 아니라 **16x16 칸 단위**로만 정할 수 있다.
인접한 8x8 타일 4장은 같은 배경 팔레트를 쓴다. 조각마다 색을 다르게 하고 싶으면
색이 아니라 **무늬**로 구분하라 (`examples/tetris.c` 참고).

**스프라이트 한계.** 한 화면 64장, **한 가로줄에 8장**. 9번째부터는 깜빡이거나 사라진다.
16x16 캐릭터 하나가 스프라이트 4장을 먹는다.

**예산.** PRG 32KB, CHR 256타일, RAM 1280바이트(+제로페이지 240).
빌드 결과가 매번 사용량을 찍는다. `--json`이면 `prg_used/ram_used/tiles_used`로 나온다.

**vblank는 짧다.** 한 프레임에 배경 타일 32장까지만 반영된다(큐 자동 처리).
화면 전체를 바꾸려면 `ppu_off()` 후 하라.

**게임 로직은 NMI가 아니라 main에서.** NMI는 런타임 것이다.

---

## 8. 진단 읽는 법

```
examples/game.c:42:12: error E0301: 지역 배열에는 초기값을 줄 수 없습니다
  힌트: `const u8 이름[] = {...};` 로 파일 맨 위(전역)에 두세요. ROM에 들어가 RAM을 쓰지 않습니다.
  자세히: docs/agent/ERRORS.md#e0301
```

- `E01xx` 렉서/전처리기 · `E02xx` 문법 · `E03xx` 선언/저장 · `E04xx` 타입/식
- `E05xx` asset · `E06xx` API 사용 · `E07xx` 어셈블러/ROM 크기 · `W09xx` 경고

전체 표: `python famic.py errors` 또는 `docs/agent/ERRORS.md`.
**힌트는 그대로 따르면 고쳐진다.** 힌트가 틀렸으면 그건 툴체인의 버그다.

JSON이 필요하면 어느 명령에나 `--json`:
```json
{"ok": false, "diagnostics": [
  {"code":"E0301","severity":"error","file":"game.c","line":42,"col":12,
   "title":"지역 배열은 지원하지만 크기가 필요합니다",
   "message":"...","hint":"..."}]}
```

---

## 9. 작업 순서 (권장 루프)

1. `examples/platformer.c`(스프라이트/물리) 또는 `examples/tetris.c`(배경 전용)를
   가장 가까운 쪽으로 골라 골격을 잡는다.
2. asset부터 쓴다. 팔레트 → 타일 → 메타스프라이트/메타타일 → 사운드.
3. `python famic.py check game.c` — 문법·에셋만 빠르게 확인.
4. `python famic.py build game.c -o build/game.nes`
5. `python famic.py screen build/game.nes --frames 60` — 화면이 나오는지.
6. `python famic.py run ... --sym ...` — 변수가 의도대로 움직이는지.
7. 동작이 확정되면 `tests/specs/`에 시나리오를 추가해 굳힌다.
8. 예제를 바꿨으면 `python tools/build_pages.py`로 `docs/roms/`를 갱신한다.

막히면 `docs/agent/`에 주제별 상세 문서가 있다:
`LANGUAGE.md` `API.md` `ASSETS.md` `ERRORS.md` `VERIFY.md` `HARDWARE.md`
`RECIPES.md` `PLAN.md`(설계 근거).

---

## 10. 저장소 지도

```
famic.py              진입점 (얇은 래퍼)
famic/                컴파일러
  api.py              ★ API 매니페스트 — 런타임 함수의 단일 진실 공급원
  assets.py           asset 선언 -> CHR/팔레트/맵/사운드 바이트
  lexer.py parser.py ast.py types.py
  codegen.py          타입 인식 6502 코드 생성
  runtime.py          6502 런타임 라이브러리 (모듈은 호출되면 포함)
  assembler.py        2패스 6502 어셈블러 + iNES 패키징
  emu.py              헤드리스 NES (CPU + PPU + 컨트롤러)
  diagnostics.py      에러 코드 + 힌트
  cli.py              명령줄
include/fami.h        생성물. 고치지 말 것 (`python famic.py header`로 재생성)
examples/             참조 구현 2개
tests/                단위 테스트 + specs/ 게임플레이 시나리오
docs/agent/           주제별 상세 문서
docs/                 GitHub Pages (브라우저 에뮬레이터 + 예제 ROM)
web-emulator/         벤더링된 JSNES (외부 프로젝트, 문서 포함 보존)
```

**API를 추가하려면** `famic/api.py`에 한 줄, `famic/runtime.py`에 루틴 하나.
등록할 곳은 그 두 군데뿐이고, `fami.h`와 문서는 거기서 생성된다.
