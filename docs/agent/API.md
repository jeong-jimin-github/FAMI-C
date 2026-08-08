<!-- 이 파일은 tools/gen_docs.py 가 생성합니다. 직접 고치지 마세요. -->

# 런타임 API 레퍼런스

`#include <fami.h>` 후 그냥 호출한다. **따로 선언하지 않는다.**
호출하면 해당 런타임이 ROM에 포함된다.

기계 판독 형식: `python famic.py api --json`

## 목차

- **시스템 / 프레임** — `wait_vblank`, `frame_count`, `ppu_on`, `ppu_off`
- **컨트롤러** — `pad_poll`, `pad_held`, `pad_pressed`, `pad_released`
- **배경 (네임테이블)** — `bg_tile`, `bg_rect`, `bg_text`, `bg_char`, `bg_number`, `bg_attr`, `bg_meta`, `bg_map`, `bg_clear`, `bg_flush`
- **스프라이트 (OAM)** — `spr_clear`, `spr`, `spr_meta`, `spr_meta_flip`, `spr_count`
- **스크롤** — `scroll_set`
- **팔레트** — `pal_load`, `pal_set`, `pal_bright`
- **수학** — `mul8`, `mul16`, `div8`, `mod8`, `abs8`, `min8`, `max8`, `rand`, `rand_range`, `rand_seed`
- **충돌** — `box_hit`
- **사운드** — `sfx_play`, `music_play`, `music_stop`, `music_pause`, `music_resume`

## 시스템 / 프레임

### `void wait_vblank(void)`

다음 NMI(vblank)까지 대기한다. 게임 루프의 프레임 경계.

```c
while (1) { update(); draw(); wait_vblank(); }
```

> 루프마다 정확히 한 번 부르세요. 두 번 부르면 30fps가 됩니다.

### `u8 frame_count(void)`

전원 투입 후 지난 프레임 수의 하위 8비트.

```c
if ((frame_count() & 7) == 0) animate();
```

### `void ppu_on(void)`

배경/스프라이트 렌더링을 켠다.

```c
ppu_on();
```

### `void ppu_off(void)`

렌더링을 끈다. 끈 동안에는 VRAM에 마음껏 쓸 수 있다.

```c
ppu_off(); bg_map(LEVEL1); ppu_on();
```

> 화면 전체를 새로 그릴 때만 쓰세요. 켜고 끄면 한 프레임 검은 화면이 보입니다.

## 컨트롤러

### `void pad_poll(void)`

컨트롤러 1·2를 읽고 눌림/떼임 상태를 갱신한다. 프레임당 한 번.

```c
pad_poll();
```

> pad_held/pressed/released 를 쓰기 전에 반드시 먼저 부르세요.

### `u8 pad_held(u8 player)`

지금 눌려 있는 버튼 비트마스크.

| 인자 | 타입 |
|------|------|
| `player` | `u8` |

```c
if (pad_held(0) & PAD_RIGHT) x++;
```

### `u8 pad_pressed(u8 player)`

이번 프레임에 새로 눌린 버튼 (엣지).

| 인자 | 타입 |
|------|------|
| `player` | `u8` |

```c
if (pad_pressed(0) & PAD_A) jump();
```

### `u8 pad_released(u8 player)`

이번 프레임에 떼어진 버튼 (엣지).

| 인자 | 타입 |
|------|------|
| `player` | `u8` |

```c
if (pad_released(0) & PAD_A) cut_jump();
```

## 배경 (네임테이블)

### `void bg_tile(u8 x, u8 y, u8 tile)`

네임테이블 (x,y)에 타일 하나. x는 0~31, y는 0~29.

| 인자 | 타입 |
|------|------|
| `x` | `u8` |
| `y` | `u8` |
| `tile` | `u8` |

```c
bg_tile(4, 6, T_BRICK);
```

> 렌더링 중이면 자동으로 큐에 들어가 다음 vblank에 반영됩니다. 타이밍을 신경 쓸 필요 없습니다.

### `void bg_rect(u8 x, u8 y, u8 w, u8 h, u8 tile)`

타일 하나로 사각형을 채운다.

| 인자 | 타입 |
|------|------|
| `x` | `u8` |
| `y` | `u8` |
| `w` | `u8` |
| `h` | `u8` |
| `tile` | `u8` |

```c
bg_rect(0, 0, 32, 2, T_BLANK);
```

### `void bg_text(u8 x, u8 y, const char *text)`

내장 폰트로 문자열을 찍는다. 인자는 반드시 문자열 리터럴.

| 인자 | 타입 |
|------|------|
| `x` | `u8` |
| `y` | `u8` |
| `text` | 문자열 리터럴 |

```c
bg_text(11, 4, "GAME OVER");
```

> A-Z 0-9 와 공백 . , : - ! ? + / ( ) 만 있습니다. 소문자는 대문자로 바뀝니다.

### `void bg_char(u8 x, u8 y, u8 code)`

ASCII 코드 한 글자를 찍는다. 문자열 리터럴이 아닌 글자를 그릴 때.

| 인자 | 타입 |
|------|------|
| `x` | `u8` |
| `y` | `u8` |
| `code` | `u8` |

```c
bg_char(4, 6, 'A' + letter_index);
```

> 폰트에 없는 글자는 공백으로 나옵니다. 소문자는 대문자로 바뀝니다.

### `void bg_number(u8 x, u8 y, u16 value, u8 digits)`

값을 digits 자리 10진수로 찍는다 (앞자리 0 채움).

| 인자 | 타입 |
|------|------|
| `x` | `u8` |
| `y` | `u8` |
| `value` | `u16` |
| `digits` | `u8` |

```c
bg_number(24, 2, score, 6);
```

### `void bg_attr(u8 cx, u8 cy, u8 pal)`

16x16 셀 (cx,cy)의 배경 팔레트를 고른다. cx 0~15, cy 0~14.

| 인자 | 타입 |
|------|------|
| `cx` | `u8` |
| `cy` | `u8` |
| `pal` | `u8` |

```c
bg_attr(3, 5, 2);
```

### `void bg_meta(u8 cx, u8 cy, u8 metatile)`

16x16 메타타일 하나를 그린다 (타일 4개 + 팔레트).

| 인자 | 타입 |
|------|------|
| `cx` | `u8` |
| `cy` | `u8` |
| `metatile` | `u8` |

```c
bg_meta(3, 5, MT_GRASS);
```

### `void bg_map(u8 map)`

asset map 전체를 화면에 그린다.

| 인자 | 타입 |
|------|------|
| `map` | `u8` |

```c
ppu_off(); bg_map(MAP_STAGE1); ppu_on();
```

> 화면 한 장 분량이라 렌더링을 끄고 부르는 편이 안전합니다.

### `void bg_clear(u8 tile)`

네임테이블 전체를 한 타일로 채우고 속성을 0으로 만든다.

| 인자 | 타입 |
|------|------|
| `tile` | `u8` |

```c
bg_clear(T_BLANK);
```

### `void bg_flush(void)`

큐에 남은 배경 갱신을 즉시 전부 반영한다.

```c
bg_flush();
```

> 렌더링이 켜져 있으면 화면이 잠깐 흔들릴 수 있습니다. 보통 부를 필요가 없습니다.

## 스프라이트 (OAM)

### `void spr_clear(void)`

스프라이트 목록을 비운다. 매 프레임 그리기 전에 부른다.

```c
spr_clear();
```

### `void spr(u8 x, u8 y, u8 tile, u8 attr)`

8x8 스프라이트 하나를 목록에 추가한다.

| 인자 | 타입 |
|------|------|
| `x` | `u8` |
| `y` | `u8` |
| `tile` | `u8` |
| `attr` | `u8` |

```c
spr(hero_x, hero_y, T_HERO, 0);
```

> attr: 하위 2비트 팔레트, bit5 배경 뒤, bit6 좌우반전, bit7 상하반전.

### `void spr_meta(u8 x, u8 y, u8 metasprite)`

asset metasprite 를 (x,y) 기준으로 한 번에 추가한다.

| 인자 | 타입 |
|------|------|
| `x` | `u8` |
| `y` | `u8` |
| `metasprite` | `u8` |

```c
spr_meta(hero_x, hero_y, MS_HERO_IDLE);
```

### `void spr_meta_flip(u8 x, u8 y, u8 metasprite, u8 flip)`

메타스프라이트를 좌우반전(flip=1)해서 추가한다.

| 인자 | 타입 |
|------|------|
| `x` | `u8` |
| `y` | `u8` |
| `metasprite` | `u8` |
| `flip` | `u8` |

```c
spr_meta_flip(hero_x, hero_y, MS_HERO_WALK, facing_left);
```

### `u8 spr_count(void)`

이번 프레임에 지금까지 추가된 스프라이트 수 (최대 64).

```c
if (spr_count() < 60) spr(x, y, t, 0);
```

## 스크롤

### `void scroll_set(u16 x, u8 y)`

배경 스크롤 위치. x는 0~511 (네임테이블 2장), y는 0~239.

| 인자 | 타입 |
|------|------|
| `x` | `u16` |
| `y` | `u8` |

```c
scroll_set(camera_x, 0);
```

> scroll_set 을 한 번이라도 부르면 런타임이 매 NMI마다 스크롤을 다시 씁니다.

## 팔레트

### `void pal_load(u8 palette)`

asset palette 32바이트를 통째로 올린다.

| 인자 | 타입 |
|------|------|
| `palette` | `u8` |

```c
pal_load(PAL_GAME);
```

### `void pal_set(u8 index, u8 color)`

팔레트 한 칸만 바꾼다. index 0~31.

| 인자 | 타입 |
|------|------|
| `index` | `u8` |
| `color` | `u8` |

```c
pal_set(1, 0x16);
```

### `void pal_bright(u8 level)`

화면 밝기 0(암전)~4(원본). 페이드 인/아웃에 쓴다.

| 인자 | 타입 |
|------|------|
| `level` | `u8` |

```c
for (i = 4; i > 0; i--) { pal_bright(i - 1); wait_vblank(); }
```

## 수학

### `u8 mul8(u8 a, u8 b)`

8x8 곱셈의 하위 8비트. `a * b` 와 같지만 명시적.

| 인자 | 타입 |
|------|------|
| `a` | `u8` |
| `b` | `u8` |

```c
index = mul8(row, 16);
```

### `u16 mul16(u8 a, u8 b)`

8x8 곱셈의 16비트 결과.

| 인자 | 타입 |
|------|------|
| `a` | `u8` |
| `b` | `u8` |

```c
offset = mul16(y, 32);
```

### `u8 div8(u8 a, u8 b)`

8비트 나눗셈 몫.

| 인자 | 타입 |
|------|------|
| `a` | `u8` |
| `b` | `u8` |

```c
cell = div8(pixel_x, 16);
```

### `u8 mod8(u8 a, u8 b)`

8비트 나머지.

| 인자 | 타입 |
|------|------|
| `a` | `u8` |
| `b` | `u8` |

```c
phase = mod8(frame, 60);
```

### `u8 abs8(i8 value)`

부호 있는 8비트의 절댓값.

| 인자 | 타입 |
|------|------|
| `value` | `i8` |

```c
distance = abs8(a_x - b_x);
```

### `u8 min8(u8 a, u8 b)`

둘 중 작은 값.

| 인자 | 타입 |
|------|------|
| `a` | `u8` |
| `b` | `u8` |

```c
speed = min8(speed + 1, MAX_SPEED);
```

### `u8 max8(u8 a, u8 b)`

둘 중 큰 값.

| 인자 | 타입 |
|------|------|
| `a` | `u8` |
| `b` | `u8` |

```c
hp = max8(hp - damage, 0);
```

### `u8 rand(void)`

0~255 의사난수. 16비트 LFSR.

```c
enemy_x = rand();
```

### `u8 rand_range(u8 n)`

0 이상 n 미만의 난수. n이 0이면 0.

| 인자 | 타입 |
|------|------|
| `n` | `u8` |

```c
piece = rand_range(7);
```

### `void rand_seed(u16 seed)`

난수 씨앗을 정한다. 0이면 무시된다.

| 인자 | 타입 |
|------|------|
| `seed` | `u16` |

```c
rand_seed(frame_count() + 1);
```

> 타이틀 화면에서 입력이 들어온 프레임 수로 씨를 뿌리면 매번 다른 판이 됩니다.

## 충돌

### `u8 box_hit(u8 ax, u8 ay, u8 aw, u8 ah, u8 bx, u8 by, u8 bw, u8 bh)`

두 AABB가 겹치면 1, 아니면 0.

| 인자 | 타입 |
|------|------|
| `ax` | `u8` |
| `ay` | `u8` |
| `aw` | `u8` |
| `ah` | `u8` |
| `bx` | `u8` |
| `by` | `u8` |
| `bw` | `u8` |
| `bh` | `u8` |

```c
if (box_hit(hero_x, hero_y, 12, 15, foe_x, foe_y, 14, 14)) hurt();
```

## 사운드

### `void sfx_play(u8 sfx)`

asset sfx 를 재생한다. 재생 중에는 펄스2 채널을 빌린다.

| 인자 | 타입 |
|------|------|
| `sfx` | `u8` |

```c
sfx_play(SFX_JUMP);
```

### `void music_play(u8 song)`

asset song 을 처음부터 재생한다.

| 인자 | 타입 |
|------|------|
| `song` | `u8` |

```c
music_play(SONG_MAIN);
```

### `void music_stop(void)`

음악을 멈추고 채널을 끈다.

```c
music_stop();
```

### `void music_pause(void)`

음악을 그 자리에서 멈춘다.

```c
music_pause();
```

### `void music_resume(void)`

music_pause() 한 자리에서 다시 재생한다.

```c
music_resume();
```

## 상수

| 이름 | 값 | 설명 |
|------|-----|------|
| `PAD_A` | `0x80` | A 버튼 |
| `PAD_B` | `0x40` | B 버튼 |
| `PAD_SELECT` | `0x20` | Select |
| `PAD_START` | `0x10` | Start |
| `PAD_UP` | `0x08` | 십자키 위 |
| `PAD_DOWN` | `0x04` | 십자키 아래 |
| `PAD_LEFT` | `0x02` | 십자키 왼쪽 |
| `PAD_RIGHT` | `0x01` | 십자키 오른쪽 |
| `SPR_PAL0` | `0x00` | 스프라이트 팔레트 0 |
| `SPR_PAL1` | `0x01` | 스프라이트 팔레트 1 |
| `SPR_PAL2` | `0x02` | 스프라이트 팔레트 2 |
| `SPR_PAL3` | `0x03` | 스프라이트 팔레트 3 |
| `SPR_BEHIND` | `0x20` | 배경 뒤에 그림 |
| `SPR_FLIP_X` | `0x40` | 좌우 반전 |
| `SPR_FLIP_Y` | `0x80` | 상하 반전 |
| `NOISE_HAT` | `2` | asset song 노이즈: 닫은 하이햇 |
| `NOISE_HAT_OPEN` | `3` | asset song 노이즈: 열린 하이햇 |
| `NOISE_KICK` | `4` | asset song 노이즈: 킥 |
| `NOISE_SNARE` | `5` | asset song 노이즈: 스네어 |
| `NOISE_TOM` | `6` | asset song 노이즈: 톰 |
| `NOISE_CYMBAL` | `7` | asset song 노이즈: 심벌 |
| `SCREEN_TILES_W` | `32` | 네임테이블 가로 타일 수 |
| `SCREEN_TILES_H` | `30` | 네임테이블 세로 타일 수 |
| `SCREEN_CELLS_W` | `16` | 16x16 셀 가로 개수 |
| `SCREEN_CELLS_H` | `15` | 16x16 셀 세로 개수 |
| `MAX_SPRITES` | `64` | 하드웨어 스프라이트 총 개수 |

## 음 이름

`asset sfx` 와 `asset song` 에서 쓴다. `0` 은 쉼표, `HOLD` 는 앞 음 유지.

```
N_C1 N_CS1 N_D1 N_DS1 N_E1 N_F1 N_FS1 N_G1 N_GS1 N_A1 N_AS1 N_B1
N_C2 N_CS2 N_D2 N_DS2 N_E2 N_F2 N_FS2 N_G2 N_GS2 N_A2 N_AS2 N_B2
N_C3 N_CS3 N_D3 N_DS3 N_E3 N_F3 N_FS3 N_G3 N_GS3 N_A3 N_AS3 N_B3
N_C4 N_CS4 N_D4 N_DS4 N_E4 N_F4 N_FS4 N_G4 N_GS4 N_A4 N_AS4 N_B4
N_C5 N_CS5 N_D5 N_DS5 N_E5 N_F5 N_FS5 N_G5 N_GS5 N_A5 N_AS5 N_B5
N_C6 N_CS6 N_D6 N_DS6 N_E6 N_F6 N_FS6 N_G6 N_GS6 N_A6 N_AS6 N_B6
N_C7 N_CS7 N_D7 N_DS7 N_E7 N_F7 N_FS7 N_G7 N_GS7 N_A7 N_AS7 N_B7
```
