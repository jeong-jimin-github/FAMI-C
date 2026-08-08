/* fami.h -- FAMI-C runtime API.
 *
 * 이 파일은 famic/api.py 에서 생성됩니다. 직접 고치지 마세요.
 * 다시 만들려면: python famic.py header
 */

#ifndef FAMI_H
#define FAMI_H

/* 폭이 이름에 보이는 타입을 쓰세요. int 는 i16, char 는 u8 입니다. */
typedef unsigned char  u8;
typedef signed char    i8;
typedef unsigned int   u16;
typedef int            i16;

#define PAD_A          0x80   /* A 버튼 */
#define PAD_B          0x40   /* B 버튼 */
#define PAD_SELECT     0x20   /* Select */
#define PAD_START      0x10   /* Start */
#define PAD_UP         0x08   /* 십자키 위 */
#define PAD_DOWN       0x04   /* 십자키 아래 */
#define PAD_LEFT       0x02   /* 십자키 왼쪽 */
#define PAD_RIGHT      0x01   /* 십자키 오른쪽 */
#define SPR_PAL0       0x00   /* 스프라이트 팔레트 0 */
#define SPR_PAL1       0x01   /* 스프라이트 팔레트 1 */
#define SPR_PAL2       0x02   /* 스프라이트 팔레트 2 */
#define SPR_PAL3       0x03   /* 스프라이트 팔레트 3 */
#define SPR_BEHIND     0x20   /* 배경 뒤에 그림 */
#define SPR_FLIP_X     0x40   /* 좌우 반전 */
#define SPR_FLIP_Y     0x80   /* 상하 반전 */
#define SCREEN_TILES_W 32     /* 네임테이블 가로 타일 수 */
#define SCREEN_TILES_H 30     /* 네임테이블 세로 타일 수 */
#define SCREEN_CELLS_W 16     /* 16x16 셀 가로 개수 */
#define SCREEN_CELLS_H 15     /* 16x16 셀 세로 개수 */
#define MAX_SPRITES    64     /* 하드웨어 스프라이트 총 개수 */

/* ---- 음 이름 (asset sfx / asset song) ---- */
/* 0 = 쉼표, HOLD = 앞 행의 음을 유지 */
#define HOLD     1
#define REST     0
#define N_C1     2
#define N_CS1    3
#define N_D1     4
#define N_DS1    5
#define N_E1     6
#define N_F1     7
#define N_FS1    8
#define N_G1     9
#define N_GS1    10
#define N_A1     11
#define N_AS1    12
#define N_B1     13
#define N_C2     14
#define N_CS2    15
#define N_D2     16
#define N_DS2    17
#define N_E2     18
#define N_F2     19
#define N_FS2    20
#define N_G2     21
#define N_GS2    22
#define N_A2     23
#define N_AS2    24
#define N_B2     25
#define N_C3     26
#define N_CS3    27
#define N_D3     28
#define N_DS3    29
#define N_E3     30
#define N_F3     31
#define N_FS3    32
#define N_G3     33
#define N_GS3    34
#define N_A3     35
#define N_AS3    36
#define N_B3     37
#define N_C4     38
#define N_CS4    39
#define N_D4     40
#define N_DS4    41
#define N_E4     42
#define N_F4     43
#define N_FS4    44
#define N_G4     45
#define N_GS4    46
#define N_A4     47
#define N_AS4    48
#define N_B4     49
#define N_C5     50
#define N_CS5    51
#define N_D5     52
#define N_DS5    53
#define N_E5     54
#define N_F5     55
#define N_FS5    56
#define N_G5     57
#define N_GS5    58
#define N_A5     59
#define N_AS5    60
#define N_B5     61
#define N_C6     62
#define N_CS6    63
#define N_D6     64
#define N_DS6    65
#define N_E6     66
#define N_F6     67
#define N_FS6    68
#define N_G6     69
#define N_GS6    70
#define N_A6     71
#define N_AS6    72
#define N_B6     73
#define N_C7     74
#define N_CS7    75
#define N_D7     76
#define N_DS7    77
#define N_E7     78
#define N_F7     79
#define N_FS7    80
#define N_G7     81
#define N_GS7    82
#define N_A7     83
#define N_AS7    84
#define N_B7     85

/* ========================================================
 * 런타임 API
 *
 * 아래 함수들은 컴파일러에 내장되어 있습니다.
 * 따로 선언하지 말고 그냥 호출하세요. 호출하면 켜집니다.
 * 전체 목록/예시: python famic.py api --json
 * ======================================================== */

/* -- 시스템 / 프레임 */
/*   void wait_vblank(void)                               다음 NMI(vblank)까지 대기한다. 게임 루프의 프레임 경계. */
/*   u8 frame_count(void)                                 전원 투입 후 지난 프레임 수의 하위 8비트. */
/*   void ppu_on(void)                                    배경/스프라이트 렌더링을 켠다. */
/*   void ppu_off(void)                                   렌더링을 끈다. 끈 동안에는 VRAM에 마음껏 쓸 수 있다. */

/* -- 컨트롤러 */
/*   void pad_poll(void)                                  컨트롤러 1·2를 읽고 눌림/떼임 상태를 갱신한다. 프레임당 한 번. */
/*   u8 pad_held(u8 player)                               지금 눌려 있는 버튼 비트마스크. */
/*   u8 pad_pressed(u8 player)                            이번 프레임에 새로 눌린 버튼 (엣지). */
/*   u8 pad_released(u8 player)                           이번 프레임에 떼어진 버튼 (엣지). */

/* -- 배경 (네임테이블) */
/*   void bg_tile(u8 x, u8 y, u8 tile)                    네임테이블 (x,y)에 타일 하나. x는 0~31, y는 0~29. */
/*   void bg_rect(u8 x, u8 y, u8 w, u8 h, u8 tile)        타일 하나로 사각형을 채운다. */
/*   void bg_text(u8 x, u8 y, const char *text)           내장 폰트로 문자열을 찍는다. 인자는 반드시 문자열 리터럴. */
/*   void bg_number(u8 x, u8 y, u16 value, u8 digits)     값을 digits 자리 10진수로 찍는다 (앞자리 0 채움). */
/*   void bg_attr(u8 cx, u8 cy, u8 pal)                   16x16 셀 (cx,cy)의 배경 팔레트를 고른다. cx 0~15, cy 0~14. */
/*   void bg_meta(u8 cx, u8 cy, u8 metatile)              16x16 메타타일 하나를 그린다 (타일 4개 + 팔레트). */
/*   void bg_map(u8 map)                                  asset map 전체를 화면에 그린다. */
/*   void bg_clear(u8 tile)                               네임테이블 전체를 한 타일로 채우고 속성을 0으로 만든다. */
/*   void bg_flush(void)                                  큐에 남은 배경 갱신을 즉시 전부 반영한다. */

/* -- 스프라이트 (OAM) */
/*   void spr_clear(void)                                 스프라이트 목록을 비운다. 매 프레임 그리기 전에 부른다. */
/*   void spr(u8 x, u8 y, u8 tile, u8 attr)               8x8 스프라이트 하나를 목록에 추가한다. */
/*   void spr_meta(u8 x, u8 y, u8 metasprite)             asset metasprite 를 (x,y) 기준으로 한 번에 추가한다. */
/*   void spr_meta_flip(u8 x, u8 y, u8 metasprite, u8 flip) 메타스프라이트를 좌우반전(flip=1)해서 추가한다. */
/*   u8 spr_count(void)                                   이번 프레임에 지금까지 추가된 스프라이트 수 (최대 64). */

/* -- 스크롤 */
/*   void scroll_set(u16 x, u8 y)                         배경 스크롤 위치. x는 0~511 (네임테이블 2장), y는 0~239. */

/* -- 팔레트 */
/*   void pal_load(u8 palette)                            asset palette 32바이트를 통째로 올린다. */
/*   void pal_set(u8 index, u8 color)                     팔레트 한 칸만 바꾼다. index 0~31. */
/*   void pal_bright(u8 level)                            화면 밝기 0(암전)~4(원본). 페이드 인/아웃에 쓴다. */

/* -- 수학 */
/*   u8 mul8(u8 a, u8 b)                                  8x8 곱셈의 하위 8비트. `a * b` 와 같지만 명시적. */
/*   u16 mul16(u8 a, u8 b)                                8x8 곱셈의 16비트 결과. */
/*   u8 div8(u8 a, u8 b)                                  8비트 나눗셈 몫. */
/*   u8 mod8(u8 a, u8 b)                                  8비트 나머지. */
/*   u8 abs8(i8 value)                                    부호 있는 8비트의 절댓값. */
/*   u8 min8(u8 a, u8 b)                                  둘 중 작은 값. */
/*   u8 max8(u8 a, u8 b)                                  둘 중 큰 값. */
/*   u8 rand(void)                                        0~255 의사난수. 16비트 LFSR. */
/*   u8 rand_range(u8 n)                                  0 이상 n 미만의 난수. n이 0이면 0. */
/*   void rand_seed(u16 seed)                             난수 씨앗을 정한다. 0이면 무시된다. */

/* -- 충돌 */
/*   u8 box_hit(u8 ax, u8 ay, u8 aw, u8 ah, u8 bx, u8 by, u8 bw, u8 bh) 두 AABB가 겹치면 1, 아니면 0. */

/* -- 사운드 */
/*   void sfx_play(u8 sfx)                                asset sfx 를 재생한다. 재생 중에는 펄스2 채널을 빌린다. */
/*   void music_play(u8 song)                             asset song 을 처음부터 재생한다. */
/*   void music_stop(void)                                음악을 멈추고 채널을 끈다. */
/*   void music_pause(void)                               음악을 그 자리에서 멈춘다. */
/*   void music_resume(void)                              music_pause() 한 자리에서 다시 재생한다. */

#endif /* FAMI_H */
