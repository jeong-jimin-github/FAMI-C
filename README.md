<div align="center">

<img src="docs/logo.svg" alt="FAMI-C — 6502 어셈블리 컴파일러" width="600">

### LLM 에이전트를 위한 패미컴(NES) C 컴파일러

C 파일 한 장을 넣으면 실제로 돌아가는 카트리지 ROM이 나옵니다.<br>
설치할 것도, 설정할 것도 없습니다. 파이썬 표준 라이브러리만 있으면 됩니다.

<img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.8+">
<img src="https://img.shields.io/badge/dependencies-none-brightgreen?style=flat-square" alt="의존성 없음">
<img src="https://img.shields.io/badge/target-NES%20%2F%20iNES%20mapper%200-E8202A?style=flat-square" alt="대상: NES mapper 0">
<img src="https://img.shields.io/badge/emulator-built--in%20headless-17469E?style=flat-square" alt="내장 헤드리스 에뮬레이터">

**[브라우저에서 플레이](https://jeong-jimin-github.github.io/FAMI-C/#play)** ·
[에이전트 가이드](AGENTS.md) ·
[문서](#-문서) ·
[예제](#-예제)

</div>

---

## 이런 걸 만들 수 있습니다

```c
#include <fami.h>
/* 팔레트와 변수 선언은 생략했습니다. 전체 코드는 AGENTS.md 1절에 있습니다. */

asset tile T_BALL = {
    "..3333.."  ".333333."  "33322333"  "33222233"
    "33222233"  "33322333"  ".333333."  "..3333.."
};

void main(void) {
    pal_load(PAL);
    while (1) {
        pad_poll();
        if (pad_held(0) & PAD_RIGHT) x = x + 1;
        spr_clear();
        spr(x, y, T_BALL, SPR_PAL0);
        wait_vblank();
    }
}
```

```bash
python famic.py build game.c -o build/game.nes
```

타일 인덱스도, OAM 전송도, VRAM 타이밍도 신경 쓰지 않습니다.
필요한 일은 전부 런타임이 대신 합니다.

## 🚀 시작하기

```bash
git clone https://github.com/jeong-jimin-github/FAMI-C.git
cd FAMI-C

# 예제 하나를 빌드해 봅니다
python famic.py build examples/platformer.c -o build/platformer.nes

# 화면을 텍스트로 확인합니다
python famic.py screen build/platformer.nes --frames 30

# 실제로 조작해 보고, 변수 값까지 들여다봅니다
python famic.py run build/platformer.nes --frames 200 \
    --input "10:START, 40:RIGHT*60" --sym "_g_hero__x,_g_score:16"
```

만들어진 `.nes` 파일은 실제 에뮬레이터나 실기에서 그대로 돌아갑니다.

## ✨ 특징

|  | 보통의 NES 툴체인 | FAMI-C |
|---|---|---|
| **그래픽** | 별도 타일 편집기 + 수동 인덱스 관리 | `asset tile`로 소스 안에 선언, 인덱스는 컴파일러가 배정 |
| **기능 켜기** | 헤더 선언 / 링커 설정 / 빌드 플래그 | **호출하면 켜집니다** |
| **에러** | 어셈블러 메시지, 행 번호 없음 | 안정적인 진단 코드 + 행·열 + 해결 방법, `--json` 지원 |
| **검증** | GUI 에뮬레이터를 사람이 눈으로 확인 | 내장 헤드리스 NES — 입력 스크립트, **심볼 이름으로 RAM 조회**, 화면 텍스트 덤프 |
| **어셈블리** | 직접 작성 | OAM 전송·VRAM 타이밍·스크롤·사운드 전부 런타임이 처리 |
| **의존성** | cc65, 어셈블러, 빌드 스크립트 | 파이썬 표준 라이브러리만 |

## 🔍 사람 없이 검증하기

FAMI-C의 설계 기준은 사람의 편의가 아니라
**에이전트가 사람 없이 만들고, 스스로 검증하고, 스스로 고칠 수 있는가**입니다.
그래서 에뮬레이터가 툴체인 안에 들어 있습니다.

```bash
# 60프레임 굴린 뒤 화면을 아스키로 덤프
python famic.py screen build/game.nes --frames 60

# 입력을 넣고 돌린 뒤, 심볼 이름으로 RAM을 읽습니다
python famic.py run build/game.nes --frames 300 \
    --input "60:START, 90:RIGHT*40" --sym "hero_x,score:16"

# 게임플레이 시나리오를 회귀 테스트로 고정
python famic.py test tests/specs/*.spec.json
```

컴파일에 성공했다고 게임이 동작하는 것은 아닙니다.
`run`과 `screen`으로 눈이 아니라 값으로 확인하세요.

## 📚 문서

| 문서 | 내용 |
|------|------|
| **[`AGENTS.md`](AGENTS.md)** | **에이전트 진입점. 이 파일 하나로 게임 하나를 완성할 수 있습니다** |
| [`docs/agent/LANGUAGE.md`](docs/agent/LANGUAGE.md) | 지원하는 C 문법, 타입, 메모리 배치 |
| [`docs/agent/API.md`](docs/agent/API.md) | 런타임 API 전체 (자동 생성) |
| [`docs/agent/ASSETS.md`](docs/agent/ASSETS.md) | `asset` 선언 문법 (자동 생성) |
| [`docs/agent/ERRORS.md`](docs/agent/ERRORS.md) | 진단 코드 표 (자동 생성) |
| [`docs/agent/VERIFY.md`](docs/agent/VERIFY.md) | 헤드리스 검증 워크플로 |
| [`docs/agent/HARDWARE.md`](docs/agent/HARDWARE.md) | NES 하드웨어 제약 |
| [`docs/agent/RECIPES.md`](docs/agent/RECIPES.md) | 게임 유형별 골격 코드 |
| [`docs/agent/PLAN.md`](docs/agent/PLAN.md) | 왜 이렇게 설계했는가 |

## 🎮 예제

| 예제 | 설명 |
|------|------|
| [`examples/platformer.c`](examples/platformer.c) | 스프라이트, 고정소수점 물리, 메타타일 스테이지 4개, 순찰병, 보석, 가시, BGM/효과음 |
| [`examples/tetris.c`](examples/tetris.c) | 배경 전용. 7-bag, 벽 차기, 락 딜레이, 레벨, 줄 지우기 연출, 최고 점수 이름 입력, 4분 26초 BGM ([`tetris_song.c`](examples/tetris_song.c), 2448행) |

둘 다 [브라우저에서 바로 플레이](https://jeong-jimin-github.github.io/FAMI-C/#play)할 수 있습니다.

## 🛠 개발

```bash
python -m unittest discover -s tests -t .    # 단위 테스트 + 예제 게임플레이 시나리오
python famic.py test tests/specs/*.spec.json # 게임플레이 시나리오만
python tools/gen_docs.py                     # 생성 문서와 include/fami.h 갱신
python tools/gen_docs.py --check             # 생성물이 코드와 어긋났는지 확인
python tools/build_pages.py                  # docs/ 의 예제 ROM 갱신
```

`include/fami.h`와 `docs/agent/{API,ASSETS,ERRORS}.md`는 생성물입니다.
직접 고치지 말고 `famic/api.py`, `famic/assets.py`, `famic/diagnostics.py`를 고친 뒤
`python tools/gen_docs.py`를 실행하세요. 자세한 규칙은 [`AGENTS.md`](AGENTS.md)에 있습니다.

## 🎯 대상 하드웨어

NROM-256 (iNES mapper 0) — PRG 32KB, CHR 8KB, 세로 미러링, NTSC.

## 📄 라이선스

`web-emulator/`는 [JSNES](https://github.com/bfirsh/jsnes)를 벤더링한 것으로
각자의 라이선스를 따릅니다 (`web-emulator/LICENSE`).

로고(`docs/logo.svg`)의 「화미-씨」는 원본 그림에서 그대로 벡터로 따냈습니다.
「FAMI-C」와 부제만 [Archivo Black](https://fonts.google.com/specimen/Archivo+Black),
[Black Han Sans](https://fonts.google.com/specimen/Black+Han+Sans)의 글리프를
아웃라인으로 변환해 썼습니다 (SIL Open Font License 1.1).
