# 테트리스 예제

예제 파일은 `examples/tetris.c`입니다.

## 빌드

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

## 조작

- 왼쪽 / 오른쪽: 블록 이동
- 아래: 소프트 드롭
- A: 회전

## 예제에서 보여주는 기능

- ROM 테이블 기반 블록 모양 데이터
- 보드 배열과 충돌 판정
- 라인 삭제
- 패드 입력 처리
- vblank에 맞춘 PPU 업데이트
- 네이티브 큐 렌더러를 통한 빠른 활성 블록 갱신

## 검증

Mesen 2.2.1에서 다음 동작을 확인했습니다.

- 초기 화면 정상 표시
- 자연 낙하
- 좌우 이동
- 소프트 드롭
- 블록 락과 다음 블록 스폰
- 화면 밀림과 잔상 제거

