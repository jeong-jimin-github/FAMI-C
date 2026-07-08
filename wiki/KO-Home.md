# FAMI-C 한국어 Wiki

FAMI-C는 NES 및 패미컴용 6502 프로그램을 C로 작성하고 `.nes` ROM으로 빌드하기 위한 작은 자체 완결형 툴체인입니다.

## 문서 목록

- [[설치와 사용법|KO-Usage]]
- [[지원 C 모델|KO-C-Language]]
- [[컴파일러 아키텍처|KO-Architecture]]
- [[테트리스 예제|KO-Tetris]]

## 핵심 특징

- C 소스 파싱, 6502 어셈블리 생성, 어셈블, iNES 패키징을 하나의 Python 파일에서 처리합니다.
- NES에 맞춘 8비트 ABI와 정적 메모리 모델을 사용합니다.
- `wait_vblank`, `ppu_put`, `read_pad`, `rand8` 같은 기본 런타임 함수를 제공합니다.
- 예제 테트리스 게임을 `examples/tetris.c`에서 제공합니다.
- Mesen 2.2.1에서 실제 구동 검증했습니다.

## 빠른 시작

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

생성된 `build/tetris.nes`를 Mesen 같은 NES 에뮬레이터에서 열면 됩니다.

