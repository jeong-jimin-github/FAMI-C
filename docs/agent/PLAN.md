# FAMI-C LLM-First 전환 계획

이 문서는 FAMI-C를 **LLM 에이전트가 직접 패미컴 게임을 만드는 도구**로 재설계하는
전체 계획이다. 사람이 쓰기 편한지는 판단 기준이 아니다. 기준은 하나다:

> **에이전트가 사람의 개입 없이 게임을 만들고, 스스로 검증하고, 스스로 고칠 수 있는가.**

---

## 1. 기존 설계의 문제 (전환의 근거)

전환 전 `famic.py`(3408줄, 단일 파일)를 에이전트 관점에서 감사한 결과다.

| # | 문제 | 에이전트에 미치는 영향 |
|---|------|----------------------|
| P1 | `int`가 조용히 8비트로 절단됨 | **가장 치명적.** 컴파일도 되고 ROM도 나오는데 점수가 255에서 멈춘다. 에이전트는 원인을 찾을 단서가 없다 |
| P2 | CHR(그래픽)이 컴파일러에 하드코딩 (`make_chr()`, 456줄) | 새 게임의 그래픽을 **만들 방법 자체가 없다**. 테트리스/플랫포머 전용 타일만 존재 |
| P3 | 팔레트 32바이트가 컴파일러에 하드코딩 | 게임이 색을 정할 수 없다 |
| P4 | 런타임 기능이 "매직 선언 감지"로 켜짐 | `extern void oam_reset(void);`를 **정확히** 그 시그니처로 써야 스프라이트가 켜진다. 인자 하나만 달라도 조용히 비활성. 발견 불가능 |
| P5 | 음악 런타임이 `MUSIC_PULSE1_BASE[77]` 같은 **매직 배열 크기**를 요구 | 77, 30, 47, 70, 156, 50이라는 숫자의 출처가 코드 어디에도 없다 |
| P6 | `ppu_write_board_half`는 `board[200]`, `ppu_write_preview`는 `preview_tiles[16]`을 요구 | 테트리스 전용 해킹이 컴파일러 본체에 박혀 있다. 다른 게임엔 무용지물 |
| P7 | 포인터/구조체/지역배열/switch/2차원배열/문자열 없음 | 에이전트가 자연스럽게 쓰는 C가 전부 실패한다 |
| P8 | 에러가 `CompileError("...")` 문자열 하나, 행 번호 없음 | 에이전트가 어느 줄을 고쳐야 하는지 모른다 |
| P9 | 검증 수단이 Mesen(Windows GUI) 또는 사람의 눈 | **에이전트의 피드백 루프가 닫히지 않는다.** 만든 게임이 도는지 알 수 없다 |
| P10 | 문서가 4개 언어 위키로 흩어진 사람용 산문 | 에이전트가 API 표면을 한 번에 파악할 수 없다 |

P9가 근본 문제다. 나머지를 다 고쳐도 **에이전트가 결과를 볼 수 없으면** 게임을 만들 수 없다.

---

## 2. 설계 원칙

1. **한 게임 = 한 `.c` 파일.** 별도 에셋 파이프라인, 빌드 설정, 링커 스크립트 없음.
   코드·그래픽·팔레트·맵·사운드가 전부 같은 파일에 선언된다.
2. **매직 없음.** 기능은 *선언 시그니처를 맞춰서*가 아니라 *호출해서* 켜진다.
   API 표면은 `famic api --json`으로 기계가 통째로 읽을 수 있다.
3. **실패는 시끄럽게.** 조용한 절단·조용한 비활성화 금지. 모든 에러는
   안정적 코드(`E0301`), 행·열, 그리고 **고치는 방법**을 가진다.
4. **에이전트가 스스로 본다.** 순수 파이썬 헤드리스 NES 에뮬레이터를 내장한다.
   ROM을 돌리고, 입력을 넣고, 화면·OAM·RAM을 **심볼 이름으로** 덤프한다.
5. **어셈블리를 쓰게 하지 않는다.** 6502가 필요한 부분(OAM 전송, VRAM 타이밍,
   고정소수점, 스크롤, 메타스프라이트, 사운드 드라이버)은 전부 런타임이 갖는다.

---

## 3. 목표 산출물

```
famic/                      # 컴파일러 패키지 (단일 파일 → 모듈 분리)
  diagnostics.py            # 에러 코드 + 행/열 + 힌트
  lexer.py  ast.py  parser.py
  types.py                  # u8/u16/i8/i16/배열/구조체 타입 모델
  assets.py                 # asset 선언 → CHR/팔레트/맵/사운드 바이트
  codegen.py                # 타입 인식 6502 코드 생성
  runtime.py                # 6502 런타임 라이브러리 (asm 텍스트)
  api.py                    # ★ API 매니페스트 (단일 진실 공급원)
  assembler.py  ines.py
  emu/                      # 헤드리스 6502 + PPU
  cli.py
famic.py                    # `python famic.py ...` 호환 shim
include/fami.h              # api.py에서 생성되는 헤더
AGENTS.md  CLAUDE.md        # 에이전트 진입점 (한국어)
docs/agent/*.md             # 레퍼런스 (한국어)
examples/*.c                # 새 API로 재작성
```

---

## 4. 단계별 계획

### 단계 1 — 패키지 분리 + 진단 시스템 (P8)

`famic.py`를 `famic/` 패키지로 나눈다. 에이전트는 3400줄 파일을 통째로 읽을 필요 없이
고칠 모듈만 연다.

진단은 구조체로 바꾼다.

```json
{"ok": false, "diagnostics": [
  {"code": "E0301", "severity": "error", "line": 42, "col": 12,
   "message": "지역 배열은 함수 밖으로 옮겨야 합니다",
   "hint": "`unsigned char buf[8];`를 전역으로 옮기세요. 재귀가 없으므로 동작이 같습니다."}
]}
```

`--json`이 붙으면 stdout은 **JSON만** 낸다. 에이전트가 파싱해서 바로 다음 편집을 결정한다.

### 단계 2 — 타입 모델과 언어 확장 (P1, P7)

**우선순위 1: `int`의 조용한 절단 제거.** 진짜 16비트를 구현한다.

- 8비트 값은 지금처럼 A 레지스터 경로(빠름).
- 16비트 값은 `__acc_lo/__acc_hi` 제로페이지 쌍 + 하드웨어 스택 push/pop.
- 타입 승격 규칙을 명시하고, 축소 대입은 **경고**가 아니라 명시적 캐스트 요구.

추가 언어 기능 (에이전트가 실제로 쓰는 순서대로):

| 기능 | 이유 |
|------|------|
| `u8/u16/i8/i16` 별칭 | 폭이 이름에 보이면 에이전트가 틀리지 않는다 |
| 지역 배열 | 재귀가 없으므로 함수별 정적 할당으로 안전하게 지원 |
| `struct` (SoA 자동 변환) | `actors[i].x` → `actors__x[i]`. 에이전트는 구조체로 쓰고 컴파일러가 NES에 맞게 편다 |
| 2차원 배열 `map[y][x]` | 타일맵의 자연스러운 표현 |
| `switch/case/default` | 상태 기계에 필수 |
| `do..while` | |
| `enum`, `typedef` | 상태 상수를 `#define` 더미로 안 만들어도 됨 |
| 문자열 리터럴 | `bg_text(2, 3, "SCORE")` |
| 함수형 `#define`, `#include`, `#ifdef` | |

### 단계 3 — 에셋 시스템 (P2, P3, P5, P6)

`make_chr()`를 **삭제**하고 C 소스에서 그래픽을 선언한다. `asset` 키워드 하나만 추가한다.

```c
asset tile T_BRICK = {
    "33333333"
    "32222221"
    "32222221"
    "32222221"
    "32222221"
    "32222221"
    "31111111"
    "11111111"
};
```

`.`=색0(투명), `0..3`=팔레트 색인. `T_BRICK`은 **컴파일러가 자동 할당한 CHR 인덱스**를
값으로 갖는 `u8` 상수가 된다. `#define HERO_IDLE_R 92` 같은 수동 번호 맞추기가 사라진다.

지원 종류:

| 선언 | 산출물 |
|------|--------|
| `asset palette P = { 32바이트 }` | $3F00 팔레트. 배경색 미러링 자동 |
| `asset tile T = { 8줄 }` | CHR 타일 1개 + 인덱스 상수 |
| `asset tiles T[N] = { 8N줄 }` | 연속 N타일 + 시작 인덱스 상수 |
| `asset metasprite M = { {dx,dy,tile,attr}, ... }` | `spr_meta(x,y,M)` |
| `asset metatile MT = { tl,tr,bl,br,pal }` | `bg_meta(cx,cy,MT)` |
| `asset map MAP = { w, h, 메타타일 id 나열 }` | `bg_map(MAP)` |
| `asset sfx S = { {vol,period}, ... }` | `sfx_play(S)` |
| `asset song G = { rows... }` | `music_play(G)` |

8x8 ASCII 폰트는 내장한다. `bg_text()`나 문자열을 쓰면 컴파일러가 자동으로 CHR에 심는다.
CHR 256타일이 넘치면 **어떤 에셋이 몇 타일 썼는지 표**와 함께 에러를 낸다.

테트리스 전용 해킹(`ppu_write_board_half`, `ppu_write_preview`)은 삭제하고,
범용 `bg_rect`/`bg_column`/`bg_flush`로 대체한다.

### 단계 4 — 런타임 API (P4)

매직 선언 감지를 전부 없앤다. `famic.h`가 선언하고, **호출하면 켜진다.**

핵심은 **VRAM 업데이트 큐 자동화**다. NES에서 에이전트가 가장 많이 내는 버그는
렌더링 중에 $2007에 쓰는 것(화면 깨짐)인데, 이건 증상이 "화면이 이상함"이라
에이전트가 원인을 추론할 수 없다. 그래서 `bg_tile()`은:

- 렌더링 중이면 → 큐에 넣고, 다음 NMI가 vblank 예산 안에서 흘려보낸다
- vblank/렌더링 off면 → 즉시 쓴다

에이전트는 타이밍을 **몰라도 된다**.

API 그룹:

```
시스템   wait_vblank, frame_count, ppu_on, ppu_off
입력     pad_poll, pad_held, pad_pressed, pad_released       ← 엣지 감지 내장
배경     bg_tile, bg_rect, bg_text, bg_number, bg_attr,
         bg_meta, bg_map, bg_clear, bg_flush
스프라이트 spr_clear, spr, spr_meta, spr_count
스크롤   scroll_set (16비트), scroll_x, scroll_y
팔레트   pal_load, pal_set, pal_fade
수학     mul8, div8, mod8, abs8, min8, max8, rand, rand_range,
         fx_add, fx_px  (12.4 고정소수점)
충돌     box_hit (AABB)
사운드   sfx_play, music_play, music_stop, music_pause, music_resume
```

### 단계 5 — 헤드리스 검증 (P9) ★ 핵심

순수 파이썬 NES 에뮬레이터를 내장한다(의존성 0). 6502 공식 명령어 전체 +
PPU(배경/스프라이트 렌더링) + 컨트롤러 입력 + APU 레지스터 캡처.

```bash
famic run game.nes --frames 600 --input "60:START, 120:RIGHT*90" --json
famic screen game.nes --frames 300 --ascii      # 화면을 텍스트로 출력
famic watch game.nes --frames 300 --sym hero_x,hero_y,score
famic test game.spec.json
```

빌드 시 **심볼 테이블**(`game.sym`)을 함께 낸다. 그래서:

```
$ famic watch build/platformer.nes --frames 120 --sym hero_x,lives
frame 120: hero_x=72 lives=3
```

에이전트가 `hero_x`가 안 움직인다는 걸 **직접 관측**한다. 이게 없으면 나머지가 무의미하다.

`famic screen --ascii`는 네임테이블을 타일 인덱스 기준 문자로 찍어 준다.
폰트 타일은 실제 글자로 역매핑하므로 에이전트가 HUD 텍스트를 읽을 수 있다.

`.spec.json`은 선언적 회귀 테스트다.

```json
{"rom": "build/platformer.nes", "steps": [
  {"frames": 60},
  {"input": ["RIGHT"], "frames": 30},
  {"assert": {"hero_x": {"gt": 60}}}
]}
```

### 단계 6 — 예제 재작성

`examples/tetris.c`, `examples/platformer.c`를 새 에셋 시스템과 API로 전환한다.
예제는 **에이전트의 참조 구현**이므로, 예제가 낡은 관용구를 쓰면 에이전트가 그걸 베낀다.

- 하드코딩 타일 번호(`#define HERO_IDLE_R 92`) → `asset tile`
- 수동 OAM 채우기 → `spr_meta`
- 수동 메타타일 그리기 → `asset metatile` + `bg_meta`
- 테트리스 전용 컴파일러 훅 → 범용 `bg_rect`
- 기존 4:26 MIDI 편곡은 **압축 포맷 그대로 보존**하되 `asset song packed`로 감싼다
  (에이전트가 손으로 쓸 데이터가 아니므로 도구 생성 계층으로 분리)

### 단계 7 — 문서 (P10)

기존 `README.md`와 `wiki/` 12개 파일을 **삭제**하고 한국어 에이전트 문서로 대체한다.
(`web-emulator/`의 문서는 벤더링된 외부 프로젝트이므로 보존)

```
AGENTS.md              에이전트 진입점. 여기만 읽어도 게임 1개를 완성할 수 있어야 함
CLAUDE.md              AGENTS.md를 가리킴
README.md              짧은 한국어 개요 + AGENTS.md로 유도
docs/agent/
  LANGUAGE.md          지원 C 문법과 타입 (지원하지 않는 것도 명시)
  API.md               런타임 API 전체 레퍼런스
  ASSETS.md            asset 선언 문법
  ERRORS.md            에러 코드 표 + 각 코드의 해결법
  VERIFY.md            헤드리스 검증 워크플로
  HARDWARE.md          NES 하드웨어 제약 (에이전트가 자주 어기는 것들)
  RECIPES.md           게임 유형별 골격 코드
  PLAN.md              이 문서
```

문서 작성 규칙:
- 산문 최소화, **표와 코드 블록** 위주
- "하지 말 것"을 먼저 쓰고 이유는 뒤에
- 모든 API에 최소 1개 호출 예시
- 사람용 설치 안내·스크린샷·마케팅 문구 없음

---

## 5. 검증 기준 (완료 조건)

1. `python famic.py build examples/tetris.c -o build/tetris.nes` 성공
2. `python famic.py build examples/platformer.c -o build/platformer.nes` 성공
3. `python famic.py test tests/specs/*.json` 전부 통과 (헤드리스 에뮬레이터로 실제 플레이 검증)
4. `python -m unittest discover -s tests` 전부 통과
5. `famic api --json`이 모든 API를 기계 판독 형식으로 출력
6. AGENTS.md만 읽고 새 게임을 만들 수 있는지 — 새 예제 1개로 검증

---

## 6. 의도적으로 하지 않는 것

| 항목 | 이유 |
|------|------|
| 포인터 | 6502에서 인다이렉트 접근은 제로페이지 압박이 크고, 에이전트가 잘못 쓰면 디버그 불가. 배열+인덱스로 충분 |
| 재귀 | 6502 스택은 256바이트. 정적 할당이 유일하게 안전한 선택 |
| 부동소수점 | 12.4 고정소수점 헬퍼로 대체 |
| 매퍼 0 외 | NROM-256 32K PRG로 고정. 뱅크 스위칭은 에이전트 실수 비용이 너무 큼 |
| 사람용 IDE 연동 | 목표가 아님 |
