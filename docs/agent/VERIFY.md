# 검증 워크플로

**컴파일 성공은 동작을 뜻하지 않는다.** 이 문서는 사람 없이 게임이 도는지
확인하는 방법이다. 여기가 이 툴체인의 존재 이유다.

FAMI-C에는 헤드리스 NES(6502 + PPU + 컨트롤러)가 내장되어 있다. 설치할 것이 없다.

---

## 1. 명령 요약

| 명령 | 무엇을 답해 주나 |
|------|-----------------|
| `famic check game.c` | 문법·에셋이 맞는가 (ROM은 쓰지 않는다, 가장 빠름) |
| `famic build game.c -o build/game.nes` | ROM과 심볼표를 만든다 |
| `famic screen build/game.nes` | 화면에 무엇이 보이는가 (텍스트) |
| `famic run build/game.nes --sym ...` | 변수가 어떻게 변했는가 |
| `famic test tests/specs/*.json` | 예전에 되던 것이 아직 되는가 |
| `famic asm game.c` | 실제로 무슨 6502가 나왔는가 (거의 볼 일 없다) |

모든 명령에 `--json`을 붙일 수 있고, 붙이면 stdout은 JSON만 낸다.

---

## 2. 화면을 텍스트로 읽는다

```bash
python famic.py screen build/game.nes --frames 60 --input "20:START"
```

```
+--------------------------------+
|................................|
|..SCORE.................LINES...|
|..00092...#..........#..000.....|
|..........#...##.....#..........|
|..NEXT....#....##....#..LEVEL...|
...
```

- 네임테이블 32x30을 그대로 찍는다.
- **폰트 타일은 실제 글자로 역매핑된다.** HUD를 눈으로 읽을 수 있다.
- `.` = 타일 0(빈칸), `#` = 그 외 타일.
- 스프라이트는 나오지 않는다. 스프라이트는 `run --sym`이나 스크린샷으로 확인하라.

무엇이 잘못됐는지 바로 보인다: 화면이 전부 `.`이면 아무것도 안 그린 것이고,
글자가 깨졌으면 좌표가 틀린 것이다.

---

## 3. RAM을 심볼 이름으로 읽는다

빌드하면 `build/game.sym`이 같이 나온다. 그래서 주소가 아니라 **변수 이름**으로 볼 수 있다.

```bash
python famic.py run build/game.nes --frames 300 \
    --input "20:START, 60:RIGHT*40, 110:A" \
    --sym "_g_hero__x,_g_hero__y,_g_score:16,_g_state"
```

```
frames=300 sprites=12 digest=1e27dfdb
  _g_hero__x = 88
  _g_hero__y = 176
  _g_score:16 = 300
  _g_state = 1
```

- 16비트 변수는 이름 뒤에 **`:16`**.
- 심볼 이름 규칙은 `docs/agent/LANGUAGE.md` §6.
- `digest`는 화면 해시다. "화면이 바뀌었나"를 값 하나로 비교할 때 쓴다.
- `sprites`는 이번 프레임에 화면에 있는 스프라이트 수.

### 프레임 경계

한 프레임은 **NMI 핸들러가 끝난 시점**에 끝난다. 즉 `run_frame` 뒤에 읽은 값은
게임이 그 프레임에 확정한 값이지, 다음 프레임 갱신 도중의 값이 아니다.
그래서 프레임 번호를 하나 옮겨도 값이 흔들리지 않는다.

---

## 4. 입력 스크립트

```
프레임:버튼[|버튼...][*반복프레임]   , 로 나열
```

```bash
--input "60:START"                       # 60프레임에 START 한 번
--input "60:RIGHT*90"                    # 60~149프레임 동안 RIGHT
--input "10:START, 40:RIGHT|B*60, 90:A"  # 달리면서 점프
```

버튼: `A B SELECT START UP DOWN LEFT RIGHT`. 조합은 `|` 또는 `+`.
지정하지 않은 프레임은 아무것도 누르지 않은 상태다.

`pad_pressed()`(엣지)를 테스트하려면 한 프레임만 누르면 된다.
`--input "40:A"`는 정확히 1프레임 눌림이므로 `pad_pressed`가 한 번 참이 된다.

---

## 5. 회귀 시나리오

동작을 확인했으면 `tests/specs/`에 굳혀 둔다. 그래야 다음 수정이 그걸 깨면 바로 안다.

`tests/specs/game.spec.json`:

```json
{
  "name": "점프하면 뜨고 다시 내려온다",
  "rom": "../../build/game.nes",
  "steps": [
    { "frames": 20, "assert": { "_g_state": 0 } },
    { "input": ["START"], "frames": 2 },
    { "frames": 20, "assert": { "_g_state": 1, "_g_hero__x": 16 } },
    { "input": ["RIGHT"], "frames": 20,
      "assert": { "_g_hero__x": { "gt": 30 }, "_g_on_ground": 1 } },
    { "input": ["A"], "frames": 12,
      "assert": { "_g_hero__y": { "lt": 170 } } },
    { "frames": 40, "assert": { "_g_on_ground": 1 } }
  ]
}
```

- `rom` 경로는 spec 파일 기준 상대 경로.
- `assert`의 값은 숫자(같음) 또는 `{"gt": n}` 형태.
  조건: `eq` `ne` `gt` `ge` `lt` `le`.
- 16비트는 `"_g_score:16"`.

```bash
python famic.py test tests/specs/*.spec.json
```

`tests/test_examples.py`가 `tests/specs/*.spec.json`을 전부 자동으로 돌리므로,
`python -m unittest discover -s tests -t .` 에도 포함된다.

---

## 6. 스크린샷

```bash
python famic.py run build/game.nes --frames 120 --screenshot shot.png --scale 3
```

실제 NES 색으로 PNG를 쓴다. 스프라이트도 포함된다. 볼 수 있는 상황이라면
`screen`보다 정확하다.

---

## 7. 크래시

```
CRASH: 정의되지 않은 opcode $FF (PC=$9A31)
CRASH: BRK 명령 실행 (보통 코드가 데이터로 넘어간 경우)
CRASH: 프레임이 끝나지 않습니다 (무한 루프로 보입니다) (PC=$8F02)
```

셋 다 원인은 대체로 같다:

- **무한 루프**: `while (1)` 안에 `wait_vblank()`가 없다.
- **데이터로 넘어감**: 배열 인덱스가 범위를 벗어나 다른 것을 덮어썼다.
  배열 접근 앞에 범위 검사를 넣어라. 컴파일러는 인덱스를 검사하지 않는다.
- **RTS 짝이 안 맞음**: 툴체인 버그일 수 있다. 그대로 보고하라.

---

## 8. 에뮬레이터의 한계

게임 로직을 검증하기에 충분하지만, 정밀 재현기는 아니다.

| 재현한다 | 재현하지 않는다 |
|----------|----------------|
| 6502 공식 명령어 전부 | 비공식 opcode (크래시로 보고) |
| 스캔라인 단위 PPU 타이밍 | 사이클 단위 버스 동작 |
| 배경·스프라이트 렌더링, 스크롤 | 래스터 분할(스캔라인 중간 스크롤 변경) |
| OAM DMA, 팔레트, 속성 | 스프라이트 한 줄 8개 제한 |
| 컨트롤러 1·2 | DMC 채널, 확장 오디오 |
| APU 레지스터 기록 (`nes.apu.writes`) | 실제 소리 |

스프라이트 8개 제한은 **재현하지 않으므로**, 실기에서 깜빡일 배치도 여기선 멀쩡해 보인다.
한 가로줄에 스프라이트가 8장을 넘지 않는지는 직접 설계로 지켜야 한다.

---

## 9. 파이썬에서 직접 쓰기

더 세밀한 검사가 필요하면 에뮬레이터를 직접 부르면 된다.

```python
import sys; sys.path.insert(0, ".")
from famic.compiler import compile_source
from famic.emu import NES, BUTTONS
from pathlib import Path

result = compile_source(Path("game.c").read_text(), "game.c")
nes = NES(result.rom, result.symbols)

for frame in range(200):
    nes.set_pad(0, BUTTONS["RIGHT"] if 60 <= frame < 100 else 0)
    nes.run_frame()
    if frame % 20 == 0:
        print(frame, nes.peek("_g_hero__x"), nes.peek("_g_score", 2))

print("APU:", {hex(a) for _, a, _ in nes.apu.writes})
print("OAM 0:", nes.ppu.oam[:4])
print("VRAM:", nes.ppu.read_vram(0x2000))
```
