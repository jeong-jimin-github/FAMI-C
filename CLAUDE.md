# CLAUDE.md

이 저장소의 에이전트 지침은 **[`AGENTS.md`](AGENTS.md)** 에 있다. 먼저 그것을 읽어라.

빠른 참조:

```bash
python famic.py build game.c -o build/game.nes   # 빌드 (.sym 도 같이)
python famic.py screen build/game.nes            # 화면을 텍스트로
python famic.py run build/game.nes --sym "_g_x"  # 굴려 보고 RAM 확인
python famic.py api --json                       # API 전체 (기계 판독)
python famic.py errors                           # 진단 코드 표
```

작업할 때 지킬 것:

- **`include/fami.h`, `docs/agent/API.md`, `docs/agent/ASSETS.md`,
  `docs/agent/ERRORS.md` 는 생성물이다.** 직접 고치지 말고
  `famic/api.py`, `famic/assets.py`, `famic/diagnostics.py` 를 고친 뒤
  `python tools/gen_docs.py` 를 실행하라.
- 런타임 API를 추가하려면 `famic/api.py` 에 항목 하나, `famic/runtime.py` 에
  루틴 하나. 등록할 곳은 그 둘뿐이다.
- 예제(`examples/*.c`)를 고쳤으면 `python tools/build_pages.py` 로
  `docs/roms/` 를 다시 만들어라. `tests/test_pages.py` 가 어긋남을 잡는다.
- 컴파일러를 고쳤으면 `python -m unittest discover -s tests -t .` 를 돌려라.
  게임플레이 시나리오(`tests/specs/`)까지 포함된다.
- 컴파일이 됐다고 동작하는 게 아니다. `famic run` / `famic screen` 으로
  실제로 확인하라.
- `web-emulator/` 는 벤더링된 외부 프로젝트(JSNES)다. 그 안의 문서와
  라이선스는 건드리지 않는다.
