<!-- 이 파일은 tools/gen_docs.py 가 생성합니다. 직접 고치지 마세요. -->

# asset 선언 레퍼런스

그래픽·팔레트·맵·사운드를 게임 코드와 같은 `.c` 파일에 선언한다.
에셋 이름은 **컴파일 시각 `u8` 상수**가 되고, 값은 컴파일러가 정한다.

규칙 두 가지:

1. 에셋은 **자기보다 위에 선언된** 에셋만 참조할 수 있다.
2. 타일 인덱스는 배경과 스프라이트가 **공유**한다 (총 256장).

## `asset palette`

```c
asset palette NAME = { 32 bytes };
```

배경 팔레트 4개 + 스프라이트 팔레트 4개. 각 4바이트.

```c
asset palette PAL_GAME = {
    0x0F,0x11,0x21,0x31,  0x0F,0x06,0x16,0x26,
    0x0F,0x09,0x19,0x29,  0x0F,0x00,0x10,0x30,
    0x0F,0x12,0x22,0x32,  0x0F,0x06,0x16,0x36,
    0x0F,0x08,0x18,0x28,  0x0F,0x14,0x24,0x34
};
```

## `asset tile`

```c
asset tile NAME = { 8줄 x 8글자 };
```

타일 1개. '.'=투명, '0'~'3'=팔레트 색인.

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

## `asset tiles`

```c
asset tiles NAME[n] = { 8n줄 };
```

연속 n개 타일. NAME은 첫 타일의 인덱스.

```c
asset tiles T_HERO[4] = { /* 32줄 */ };  /* T_HERO+0 .. T_HERO+3 */
```

## `asset metasprite`

```c
asset metasprite NAME = { {dx,dy,tile,attr}, ... };
```

여러 스프라이트를 한 덩어리로. spr_meta(x,y,NAME) 으로 그린다.

```c
asset metasprite MS_HERO = {
    { 0, 0, T_HERO+0, SPR_PAL0 },
    { 8, 0, T_HERO+1, SPR_PAL0 },
    { 0, 8, T_HERO+2, SPR_PAL0 },
    { 8, 8, T_HERO+3, SPR_PAL0 }
};
```

## `asset metatile`

```c
asset metatile NAME = { tl, tr, bl, br, pal };
```

16x16 배경 블록. 타일 4개 + 배경 팔레트 번호(0~3).

```c
asset metatile MT_GROUND = { T_GRASS, T_GRASS, T_DIRT, T_DIRT, 1 };
```

## `asset map`

```c
asset map NAME = { w, h, 메타타일 이름들... };
```

메타타일로 그린 화면. bg_map(NAME) 이 통째로 그린다. w<=16, h<=15.

```c
asset map MAP_1 = { 4, 2,
    MT_SKY,   MT_SKY,    MT_SKY,   MT_SKY,
    MT_GROUND,MT_GROUND, MT_GROUND,MT_GROUND
};
```

## `asset sfx`

```c
asset sfx NAME = { {vol, note}, ... };
```

프레임 단위 효과음. vol 0~15, note 는 N_* 상수 (0이면 무음).

```c
asset sfx SFX_JUMP = { {12, N_C5}, {11, N_E5}, {9, N_G5}, {6, N_C6}, {3, N_C6} };
```

## `asset song`

```c
asset song NAME = { speed, {p1,p2,tri,noise}, ... };
```

행 단위 BGM. speed 는 행당 프레임 수. 0=쉼, HOLD=유지, N_* = 음.

```c
asset song SONG_MAIN = { 8,
    { N_C4, N_E5, N_C3, 1 },
    { HOLD, N_G5, HOLD, 0 }
};
```

## 내장 폰트

`bg_text` / `bg_number` / `bg_char` 를 쓰거나 소스에 문자열이 있으면
폰트 타일 53장이 자동으로 CHR에 들어간다. 쓸 수 있는 글자:

```
0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ .,:-!?+/()*=<>%'
```

소문자는 대문자로 바뀐다. 목록에 없는 글자는 컴파일 에러(`E0602`)다.
