# 설치와 사용법

## 요구 사항

- Python 3.10 이상
- Git
- NES 에뮬레이터. Windows에서는 Mesen 2.2.1로 검증했습니다.

## 저장소 받기

```powershell
git clone https://github.com/jeong-jimin-github/FAMI-C.git
cd FAMI-C
```

## 예제 ROM 빌드

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
python .\famic.py build .\examples\platformer.c -o .\build\platformer.nes --asm .\build\platformer.asm
```

Windows에서는 편의 스크립트도 사용할 수 있습니다.

```powershell
.\build.ps1
```

## 브라우저에서 실행

[GitHub Pages 사이트](https://jeong-jimin-github.github.io/FAMI-C/#play)에서
[JSNES](https://github.com/bfirsh/jsnes)로 두 예제 ROM을 바로 실행할 수 있어,
설치 없이 결과를 확인할 수 있습니다. 직접 빌드한 `.nes` 파일도 열 수 있으며,
파일은 브라우저 밖으로 나가지 않습니다.

방향키가 D-패드, `X`가 A, `Z`가 B, `Enter`가 Start, 오른쪽 `Ctrl`이 Select입니다.
키 입력은 화면에 포커스가 있을 때만 게임으로 전달됩니다. 게임패드도 동작하고,
터치 기기에서는 화면 조작 패드가 나타납니다.

예제나 에뮬레이터를 수정했다면 사이트가 서비스하는 파일을 다시 생성합니다.

```powershell
python .\tools\build_pages.py
```

## 컴파일러 확인

```powershell
python .\famic.py check .\tests\smoke.c
```

전체 테스트:

```powershell
python -m unittest discover -s tests
```

## 명령어

### `build`

C 소스를 컴파일하고 iNES ROM을 만듭니다.

```powershell
python .\famic.py build source.c -o build/game.nes --asm build/game.asm
```

### `check`

ROM 파일을 쓰지 않고 파싱, 코드 생성, 어셈블까지 확인합니다.

```powershell
python .\famic.py check source.c
```

### `asm`

FAMI-C 어셈블리 파일을 직접 ROM으로 패키징합니다.

```powershell
python .\famic.py asm build/game.asm -o build/game.nes
```

