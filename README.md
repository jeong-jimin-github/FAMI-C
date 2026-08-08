# FAMI-C

**LLM 에이전트를 위한 패미컴(NES) C 컴파일러.**

C 소스 한 장을 받아 6502 어셈블리를 만들고, 어셈블한 뒤, NES 런타임을 붙여
mapper 0 iNES ROM을 낸다. 파이썬 표준 라이브러리 말고는 아무것도 필요 없다.

이 프로젝트의 설계 기준은 사람의 편의가 아니라 **에이전트가 사람 없이 게임을
만들고, 스스로 검증하고, 스스로 고칠 수 있는가**다.

## 에이전트라면

**[`AGENTS.md`](AGENTS.md)를 읽어라.** 그 파일 하나로 게임 하나를 완성할 수 있다.

## 사람이라면

```bash
python famic.py build examples/platformer.c -o build/platformer.nes
python famic.py screen build/platformer.nes --frames 30
python famic.py run build/platformer.nes --frames 200 \
    --input "10:START, 40:RIGHT*60" --sym "_g_hero__x,_g_score:16"
```

브라우저에서 예제 플레이: <https://jeong-jimin-github.github.io/FAMI-C/#play>

## 무엇이 다른가

| | 보통의 NES 툴체인 | FAMI-C |
|---|---|---|
| 그래픽 | 별도 타일 편집기 + 수동 인덱스 관리 | `asset tile`로 소스 안에 선언, 인덱스는 컴파일러가 배정 |
| 기능 켜기 | 헤더 선언 / 링커 설정 / 빌드 플래그 | **호출하면 켜진다** |
| 에러 | 어셈블러 메시지, 행 번호 없음 | 안정적 코드 + 행·열 + 고치는 방법, `--json` 지원 |
| 검증 | GUI 에뮬레이터에서 사람이 본다 | 내장 헤드리스 NES. 입력 스크립트, **심볼 이름으로 RAM 조회**, 화면 텍스트 덤프 |
| 어셈블리 | 직접 쓴다 | OAM 전송·VRAM 타이밍·스크롤·사운드 전부 런타임이 처리 |

```c
#include <fami.h>

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

## 문서

| 문서 | 내용 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | 에이전트 진입점. 여기부터 |
| [`docs/agent/LANGUAGE.md`](docs/agent/LANGUAGE.md) | 지원하는 C 문법, 타입, 메모리 배치 |
| [`docs/agent/API.md`](docs/agent/API.md) | 런타임 API 전체 (생성물) |
| [`docs/agent/ASSETS.md`](docs/agent/ASSETS.md) | `asset` 선언 문법 (생성물) |
| [`docs/agent/ERRORS.md`](docs/agent/ERRORS.md) | 진단 코드 표 (생성물) |
| [`docs/agent/VERIFY.md`](docs/agent/VERIFY.md) | 헤드리스 검증 워크플로 |
| [`docs/agent/HARDWARE.md`](docs/agent/HARDWARE.md) | NES 하드웨어 제약 |
| [`docs/agent/RECIPES.md`](docs/agent/RECIPES.md) | 게임 유형별 골격 코드 |
| [`docs/agent/PLAN.md`](docs/agent/PLAN.md) | 왜 이렇게 설계했는가 |

## 예제

- [`examples/platformer.c`](examples/platformer.c) — 스프라이트, 고정소수점 물리,
  메타타일 스테이지 4개, 순찰병, 보석, 가시, BGM/효과음
- [`examples/tetris.c`](examples/tetris.c) — 배경 전용. 7-bag, 벽 차기, 락 딜레이,
  레벨, 줄 지우기 연출, 최고 점수 이름 입력

## 개발

```bash
python -m unittest discover -s tests -t .   # 단위 테스트 + 예제 게임플레이 시나리오
python famic.py test tests/specs/*.spec.json # 게임플레이 시나리오만
python tools/gen_docs.py                     # 생성 문서와 include/fami.h 갱신
python tools/gen_docs.py --check             # 생성물이 코드와 어긋났는지 확인
python tools/build_pages.py                  # docs/ 의 예제 ROM 갱신
```

## 대상

NROM-256 (iNES mapper 0): PRG 32KB, CHR 8KB, 세로 미러링, NTSC.

## 라이선스

`web-emulator/`는 [JSNES](https://github.com/bfirsh/jsnes)를 벤더링한 것으로
각자의 라이선스를 따른다 (`web-emulator/LICENSE`).
