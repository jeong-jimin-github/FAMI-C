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

## 테트리스 ROM 빌드

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

Windows에서는 편의 스크립트도 사용할 수 있습니다.

```powershell
.\build.ps1
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

