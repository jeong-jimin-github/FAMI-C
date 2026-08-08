/* FAMI-C 예제: 플랫포머
 *
 * 이 파일은 에이전트가 참고할 표준 구현이다. 읽는 순서:
 *
 *   1. asset  - 팔레트, 타일, 메타스프라이트, 메타타일, 효과음, BGM
 *   2. 데이터 - 스테이지 맵(셀 종류), 물리 상수
 *   3. 상태   - 전역 변수 (지역 배열은 쓰지 않는다)
 *   4. 로직   - 갱신 함수들
 *   5. main   - 상태 기계 + 프레임 루프
 *
 * 좌표계
 *   화면은 16x16 픽셀 셀 16개 x 15줄. 셀 0줄은 HUD.
 *   주인공과 순찰병은 하드웨어 스프라이트라 픽셀 단위로 움직인다.
 *   위치는 12.4 고정소수점: 픽셀 1바이트 + 1/16픽셀 누산기 1바이트.
 *   그래서 "프레임당 1.25픽셀" 같은 속도가 정확히 표현된다.
 */

#include <fami.h>

/* ======================================================================
 * 1. 에셋
 * ==================================================================== */

asset palette PAL_GAME = {
    /* 배경 0: 하늘  1: 흙/풀  2: 벽돌/문  3: 가시/보석 */
    0x21, 0x0F, 0x27, 0x30,
    0x21, 0x1A, 0x18, 0x30,
    0x21, 0x07, 0x17, 0x37,
    0x21, 0x02, 0x12, 0x30,
    /* 스프라이트 0: 주인공  1: 순찰병  2: 예비  3: 예비 */
    0x21, 0x0F, 0x11, 0x30,
    0x21, 0x0F, 0x16, 0x27,
    0x21, 0x0F, 0x1A, 0x2A,
    0x21, 0x0F, 0x00, 0x10
};

asset palette PAL_TITLE = {
    0x0F, 0x11, 0x21, 0x30,   0x0F, 0x17, 0x27, 0x37,
    0x0F, 0x1A, 0x2A, 0x3A,   0x0F, 0x06, 0x16, 0x26,
    0x0F, 0x0F, 0x11, 0x30,   0x0F, 0x0F, 0x16, 0x27,
    0x0F, 0x0F, 0x1A, 0x2A,   0x0F, 0x0F, 0x00, 0x10
};

/* --- 배경 타일 --- */

asset tile T_DIRT = {
    "11111111"
    "12211221"
    "11111111"
    "21122112"
    "11111111"
    "12211221"
    "11111111"
    "21122112"
};

asset tile T_GRASS = {
    "33333333"
    "33333333"
    "31331331"
    "11311311"
    "11111111"
    "12211221"
    "11111111"
    "21122112"
};

asset tile T_BRICK = {
    "22222222"
    "21111112"
    "21111112"
    "22222222"
    "11122211"
    "11122211"
    "11122211"
    "22222222"
};

asset tile T_SPIKE = {
    "........"
    "...33..."
    "..3333.."
    "..3223.."
    ".332233."
    ".322223."
    "33222233"
    "11111111"
};

asset tile T_GEM = {
    "........"
    "...33..."
    "..3223.."
    ".322223."
    ".322223."
    "..3223.."
    "...33..."
    "........"
};

asset tile T_DOOR_T = {
    "22222222"
    "23333332"
    "23111132"
    "23111132"
    "23111132"
    "23111132"
    "23111132"
    "23111132"
};

asset tile T_DOOR_B = {
    "23111132"
    "23111132"
    "23111132"
    "23113132"
    "23111132"
    "23111132"
    "23333332"
    "22222222"
};

/* --- 주인공: 16x16 = 타일 4장씩, 서기 / 걷기 / 점프 --- */

asset tiles T_HERO[12] = {
    /* 서기 왼위 */
    "...2222."  "..222222"  "..233332"  "..233332"
    "..222222"  "..222222"  "...2222."  "....11.."
    /* 서기 오른위 */
    ".2222..."  "222222.."  "233332.."  "233332.."
    "222222.."  "222222.."  ".2222..."  "..11...."
    /* 서기 왼아래 */
    "...111.."  "..11111."  ".1111111"  ".1111111"
    ".1111111"  "..11111."  "...11..."  "..33...."
    /* 서기 오른아래 */
    "..111..."  ".11111.."  "1111111."  "1111111."
    "1111111."  ".11111.."  "...11..."  "....33.."
    /* 걷기 왼위 */
    "...2222."  "..222222"  "..233332"  "..233332"
    "..222222"  "..222222"  "...2222."  "...111.."
    /* 걷기 오른위 */
    ".2222..."  "222222.."  "233332.."  "233332.."
    "222222.."  "222222.."  ".2222..."  "..111..."
    /* 걷기 왼아래 */
    "..11111."  ".1111111"  ".1111111"  "..11111."
    "...111.."  "..33...."  ".33....."  "33......"
    /* 걷기 오른아래 */
    ".11111.."  "1111111."  "1111111."  ".11111.."
    "..111..."  "....33.."  ".....33."  "......33"
    /* 점프 왼위 */
    "......11"  "...2222."  "..222222"  "..233332"
    "..233332"  "..222222"  "..222222"  "...2222."
    /* 점프 오른위 */
    "11......"  ".2222..."  "222222.."  "233332.."
    "233332.."  "222222.."  "222222.."  ".2222..."
    /* 점프 왼아래 */
    "...111.."  "..11111."  ".1111111"  "..11111."
    "...11..."  "...33..."  "..33...."  ".33....."
    /* 점프 오른아래 */
    "..111..."  ".11111.."  "1111111."  ".11111.."
    "...11..."  "...33..."  "....33.."  ".....33."
};

/* --- 순찰병: 16x16, 두 프레임 --- */

asset tiles T_FOE[8] = {
    /* A 왼위 */
    "......11"  "....1111"  "..111111"  "..113111"
    "..111111"  ".1111111"  "11111111"  "11111111"
    /* A 오른위 */
    "11......"  "1111...."  "111111.."  "111311.."
    "111111.."  "11111111"  "11111111"  "11111111"
    /* A 왼아래 (발 모음) */
    "11111111"  "11111111"  ".1111111"  "..111111"
    "..11..11"  "..11..11"  ".111..11"  "........"
    /* A 오른아래 */
    "11111111"  "11111111"  "11111111"  "111111.."
    "11..11.."  "11..11.."  "11..111."  "........"
    /* B 왼위 */
    "......11"  "....1111"  "..111111"  "..113111"
    "..111111"  ".1111111"  "11111111"  "11111111"
    /* B 오른위 */
    "11......"  "1111...."  "111111.."  "111311.."
    "111111.."  "11111111"  "11111111"  "11111111"
    /* B 왼아래 (발 벌림) */
    "11111111"  "11111111"  ".1111111"  "..111111"
    ".11...11"  "11....11"  "11....11"  "........"
    /* B 오른아래 */
    "11111111"  "11111111"  "11111111"  "111111.."
    "11...11."  "11....11"  "11....11"  "........"
};

asset metasprite MS_HERO_IDLE = {
    { 0, 0, T_HERO + 0, SPR_PAL0 }, { 8, 0, T_HERO + 1, SPR_PAL0 },
    { 0, 8, T_HERO + 2, SPR_PAL0 }, { 8, 8, T_HERO + 3, SPR_PAL0 }
};
asset metasprite MS_HERO_WALK = {
    { 0, 0, T_HERO + 4, SPR_PAL0 }, { 8, 0, T_HERO + 5, SPR_PAL0 },
    { 0, 8, T_HERO + 6, SPR_PAL0 }, { 8, 8, T_HERO + 7, SPR_PAL0 }
};
asset metasprite MS_HERO_JUMP = {
    { 0, 0, T_HERO + 8, SPR_PAL0 }, { 8, 0, T_HERO + 9, SPR_PAL0 },
    { 0, 8, T_HERO + 10, SPR_PAL0 }, { 8, 8, T_HERO + 11, SPR_PAL0 }
};
asset metasprite MS_FOE_A = {
    { 0, 0, T_FOE + 0, SPR_PAL1 }, { 8, 0, T_FOE + 1, SPR_PAL1 },
    { 0, 8, T_FOE + 2, SPR_PAL1 }, { 8, 8, T_FOE + 3, SPR_PAL1 }
};
asset metasprite MS_FOE_B = {
    { 0, 0, T_FOE + 4, SPR_PAL1 }, { 8, 0, T_FOE + 5, SPR_PAL1 },
    { 0, 8, T_FOE + 6, SPR_PAL1 }, { 8, 8, T_FOE + 7, SPR_PAL1 }
};

/* --- 메타타일: 셀 하나 = 16x16 = 타일 4장 + 배경 팔레트 --- */

asset metatile MT_EMPTY = { 0, 0, 0, 0, 0 };
asset metatile MT_DIRT  = { T_DIRT, T_DIRT, T_DIRT, T_DIRT, 1 };
asset metatile MT_GRASS = { T_GRASS, T_GRASS, T_DIRT, T_DIRT, 1 };
asset metatile MT_BRICK = { T_BRICK, T_BRICK, T_BRICK, T_BRICK, 2 };
asset metatile MT_GEM   = { 0, 0, T_GEM, 0, 3 };
asset metatile MT_SPIKE = { 0, 0, T_SPIKE, T_SPIKE, 3 };
asset metatile MT_DOOR  = { T_DOOR_T, T_DOOR_T, T_DOOR_B, T_DOOR_B, 2 };

/* --- 효과음: {볼륨 0~15, 음} 을 프레임마다 --- */

asset sfx SFX_JUMP  = { {13, N_C5}, {12, N_E5}, {10, N_G5}, {7, N_C6}, {4, N_E6} };
asset sfx SFX_LAND  = { {8, N_C3}, {5, N_C3}, {2, N_C2} };
asset sfx SFX_GEM   = { {12, N_E6}, {12, N_G6}, {10, N_C7}, {6, N_C7}, {3, N_C7} };
asset sfx SFX_STOMP = { {13, N_G4}, {11, N_C4}, {8, N_G3}, {4, N_C3} };
asset sfx SFX_HURT  = { {14, N_G3}, {13, N_F3}, {11, N_E3}, {9, N_D3}, {6, N_C3},
                        {4, N_B2}, {2, N_A2} };
asset sfx SFX_CLEAR = { {12, N_C5}, {12, N_E5}, {12, N_G5}, {12, N_C6},
                        {10, N_G5}, {10, N_C6}, {8, N_E6}, {5, N_C6}, {2, N_C6} };
asset sfx SFX_OVER  = { {13, N_C4}, {13, N_B3}, {12, N_A3}, {11, N_G3}, {10, N_F3},
                        {8, N_E3}, {7, N_D3}, {5, N_C3}, {3, N_C2}, {1, N_C2} };

/* --- BGM: 한 행이 {펄스1, 펄스2, 삼각파, 노이즈}. speed = 행당 프레임 --- */

asset song SONG_STAGE = { 9,
    { N_C4, N_C5, N_C2, 4 },   { HOLD, N_E5, HOLD, 0 },
    { N_E4, N_G5, HOLD, 6 },   { HOLD, N_E5, HOLD, 0 },
    { N_G4, N_C6, N_G2, 4 },   { HOLD, N_G5, HOLD, 0 },
    { N_E4, N_E5, HOLD, 6 },   { HOLD, N_C5, HOLD, 0 },
    { N_F4, N_A5, N_F2, 4 },   { HOLD, N_C6, HOLD, 0 },
    { N_A4, N_F6, HOLD, 6 },   { HOLD, N_C6, HOLD, 0 },
    { N_G4, N_B5, N_G2, 4 },   { HOLD, N_D6, HOLD, 0 },
    { N_B4, N_G5, HOLD, 6 },   { 0,    0,    0,    0 }
};

asset song SONG_TITLE = { 14,
    { N_C5, N_E4, N_C3, 0 },   { N_G5, HOLD, HOLD, 0 },
    { N_E5, N_G4, HOLD, 0 },   { N_C5, HOLD, HOLD, 0 },
    { N_A4, N_F4, N_F2, 0 },   { N_E5, HOLD, HOLD, 0 },
    { N_C5, N_A4, HOLD, 0 },   { 0,    0,    0,    0 }
};

/* ======================================================================
 * 2. 상수와 스테이지 데이터
 * ==================================================================== */

/* 셀 종류. 스테이지 데이터에 들어가는 값이다. */
enum {
    C_EMPTY,
    C_DIRT,
    C_GRASS,
    C_BRICK,
    C_GEM,
    C_SPIKE,
    C_GOAL,
    C_FOE
};

/* 셀 종류 -> 메타타일. bg_meta() 에 그대로 넘긴다. */
const u8 CELL_META[8] = {
    MT_EMPTY, MT_DIRT, MT_GRASS, MT_BRICK, MT_GEM, MT_SPIKE, MT_DOOR, MT_EMPTY
};

/* 밟고 설 수 있는 셀인가. */
const u8 CELL_SOLID[8] = { 0, 1, 1, 1, 0, 0, 0, 0 };

#define GRID_W       16
#define GRID_H       15
#define CELL_PX      16
#define LEVEL_SIZE   240      /* GRID_W * GRID_H */
#define STAGE_COUNT  4
#define MAX_FOES     4
#define HUD_ROWS     1        /* 셀 0줄은 HUD */

#define MAX_X        240      /* 16픽셀 스프라이트가 시작할 수 있는 마지막 x */
#define PIT_Y        216      /* 이 아래로 떨어지면 낙사 */

/* 움직임은 1/16 픽셀 단위. SUB_PX 개가 1픽셀. */
#define SUB_PX       16
#define WALK_SPEED   20       /* 1.25 px/frame */
#define RUN_SPEED    32       /* 2.00 px/frame */
#define FOE_SPEED    8        /* 0.50 px/frame */
#define GRAVITY      3        /* 0.1875 px/frame^2 */
#define JUMP_SPEED   72       /* 4.5 px/frame 상승 = 약 54px 도약 */
#define JUMP_CUT     16       /* A를 놓으면 상승을 1 px/frame 으로 깎는다 */
#define MAX_FALL     64       /* 종단 속도 4 px/frame */

/* 히트박스는 16x16 스프라이트에서 안쪽으로 들여져 있다.
 * 그래야 한 칸 틈을 지나갈 때 픽셀 단위로 정확하지 않아도 된다. */
#define BOX_L        3
#define BOX_R        12
#define BOX_B        15

#define HIT_W        12       /* 액터끼리 닿는 폭 */
#define HIT_H        13
#define STOMP_Y      6        /* 이만큼 위에서 떨어지면 밟은 것 */

#define WALK_ANIM    7        /* 걷기 프레임 간격 */
#define FOE_ANIM     12
#define START_LIVES  3

enum { ST_TITLE, ST_PLAY, ST_DEAD, ST_CLEAR, ST_OVER };

/* 스테이지 4개. 한 글자가 아니라 셀 종류 값의 나열이다.
 * 0줄은 HUD 이므로 항상 C_EMPTY 로 둔다. */
const u8 STAGES[960] = {
    /* --- 스테이지 1 --- */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,
    0,0,0,0,0,0,0,0,0,0,0,3,3,3,3,3,
    0,0,0,0,4,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,3,3,3,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,4,0,0,0,0,0,0,
    0,0,0,0,0,0,0,3,3,3,3,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,6,0,
    0,0,0,0,7,0,0,0,0,0,0,0,7,0,0,0,
    2,2,2,2,2,2,0,0,5,5,0,2,2,2,2,2,
    1,1,1,1,1,1,0,0,1,1,0,1,1,1,1,1,
    1,1,1,1,1,1,0,0,1,1,0,1,1,1,1,1,

    /* --- 스테이지 2 --- */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,4,0,0,0,0,0,0,0,0,0,4,0,0,0,
    0,3,3,3,0,0,0,0,0,0,0,3,3,3,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,4,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,3,3,3,3,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,4,0,0,0,0,0,0,0,4,0,0,0,0,
    3,3,3,3,0,0,0,0,0,0,3,3,3,3,0,0,
    0,7,0,0,0,0,0,0,7,0,0,0,0,0,0,6,
    2,2,2,0,5,5,0,2,2,2,0,0,0,2,2,2,
    1,1,1,0,1,1,0,1,1,1,0,0,0,1,1,1,
    1,1,1,0,1,1,0,1,1,1,0,0,0,1,1,1,

    /* --- 스테이지 3 --- */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,4,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,3,3,3,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,4,0,0,0,0,0,0,0,0,0,0,0,4,0,0,
    3,3,3,0,0,0,0,0,0,0,0,3,3,3,3,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,4,0,4,0,0,0,0,0,0,0,0,
    0,0,0,3,3,3,3,3,3,3,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,7,0,0,0,0,0,0,0,0,7,0,0,0,0,
    0,2,2,2,0,0,0,0,0,0,2,2,2,2,0,6,
    0,0,0,0,0,5,5,0,5,5,0,0,0,0,0,2,
    1,1,1,1,0,1,1,0,1,1,0,1,1,1,1,1,
    1,1,1,1,0,1,1,0,1,1,0,1,1,1,1,1,

    /* --- 스테이지 4 --- */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,3,3,3,3,
    0,0,0,4,0,0,0,0,0,0,0,0,0,0,0,0,
    3,3,3,3,3,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,4,0,0,0,0,0,0,0,
    0,0,0,0,0,0,3,3,3,3,3,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,4,0,0,0,0,0,0,0,0,0,0,0,0,4,0,
    3,3,3,0,0,0,0,0,0,0,0,0,0,3,3,3,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,7,0,0,0,7,0,0,0,7,0,0,0,0,0,6,
    2,2,0,5,5,2,2,0,5,5,2,2,0,5,5,2,
    1,1,0,1,1,1,1,0,1,1,1,1,0,1,1,1,
    1,1,0,1,1,1,1,0,1,1,1,1,0,1,1,1
};

/* 스테이지별 시작 위치 (픽셀). */
const u8 START_X[STAGE_COUNT] = { 16, 16, 16, 16 };
const u8 START_Y[STAGE_COUNT] = { 176, 160, 176, 176 };

/* ======================================================================
 * 3. 상태
 * ==================================================================== */

/* 현재 스테이지의 셀. STAGES 에서 복사해 오고, 보석을 먹으면 지운다. */
u8 level[LEVEL_SIZE];

struct Actor {
    u8 x;        /* 픽셀 */
    u8 xsub;     /* 1/16 픽셀 */
    u8 y;
    u8 ysub;
    i8 vy;       /* 1/16 픽셀/프레임, 위가 음수 */
    u8 face;     /* 0 = 오른쪽, 1 = 왼쪽 */
    u8 alive;
};

struct Actor hero;
struct Actor foes[MAX_FOES];

u8 foe_count;
u8 on_ground;
u8 jump_held;
u8 walk_timer;
u8 walk_frame;
u8 stage;
u8 lives;
u8 state;
u8 state_timer;
u16 score;
u8 hud_dirty;

/* 임시 변수들. 지역 변수도 정적으로 잡히므로 전역과 비용이 같다. */
u8 i;
u8 cell_x;
u8 cell_y;

/* ======================================================================
 * 4. 로직
 * ==================================================================== */

u8 cell_at(u8 px, u8 py) {
    if (py >= 240) return C_EMPTY;
    cell_x = px / CELL_PX;
    cell_y = py / CELL_PX;
    if (cell_x >= GRID_W) return C_EMPTY;
    if (cell_y >= GRID_H) return C_EMPTY;
    return level[cell_y * GRID_W + cell_x];
}

u8 solid_at(u8 px, u8 py) {
    return CELL_SOLID[cell_at(px, py)];
}

void clear_cell(u8 cx, u8 cy) {
    level[cy * GRID_W + cx] = C_EMPTY;
    bg_meta(cx, cy, MT_EMPTY);
}

void draw_hud(void) {
    bg_text(1, 1, "STAGE");
    bg_number(7, 1, stage + 1, 1);
    bg_text(11, 1, "LIFE");
    bg_number(16, 1, lives, 1);
    bg_text(20, 1, "SCORE");
    bg_number(26, 1, score, 5);
}

void load_stage(void) {
    u8 index;
    u8 cx;
    u8 cy;

    ppu_off();
    bg_clear(0);
    pal_load(PAL_GAME);

    foe_count = 0;
    index = stage * LEVEL_SIZE;
    for (i = 0; i < LEVEL_SIZE; i++) {
        level[i] = STAGES[index + i];
    }

    for (cy = HUD_ROWS; cy < GRID_H; cy++) {
        for (cx = 0; cx < GRID_W; cx++) {
            if (level[cy * GRID_W + cx] == C_FOE) {
                /* 순찰병은 셀이 아니라 스프라이트다. 셀은 비워 둔다. */
                level[cy * GRID_W + cx] = C_EMPTY;
                if (foe_count < MAX_FOES) {
                    foes[foe_count].x = cx * CELL_PX;
                    foes[foe_count].xsub = 0;
                    foes[foe_count].y = cy * CELL_PX;
                    foes[foe_count].ysub = 0;
                    foes[foe_count].vy = 0;
                    foes[foe_count].face = 0;
                    foes[foe_count].alive = 1;
                    foe_count = foe_count + 1;
                }
            }
            bg_meta(cx, cy, CELL_META[level[cy * GRID_W + cx]]);
        }
    }

    hero.x = START_X[stage];
    hero.xsub = 0;
    hero.y = START_Y[stage];
    hero.ysub = 0;
    hero.vy = 0;
    hero.face = 0;
    hero.alive = 1;
    on_ground = 1;
    jump_held = 0;
    walk_timer = 0;
    walk_frame = 0;

    draw_hud();
    ppu_on();
    music_play(SONG_STAGE);
}

/* 주인공을 가로로 speed(1/16픽셀) 만큼 민다. 벽에 닿으면 멈춘다. */
void move_hero_x(u8 speed, u8 left) {
    u8 sub;
    u8 steps;
    u8 nx;

    sub = hero.xsub + speed;
    steps = sub / SUB_PX;
    hero.xsub = sub & 15;

    while (steps > 0) {
        steps = steps - 1;
        if (left) {
            if (hero.x == 0) { hero.xsub = 0; return; }
            nx = hero.x - 1;
            if (solid_at(nx + BOX_L, hero.y + 1) ||
                solid_at(nx + BOX_L, hero.y + 8) ||
                solid_at(nx + BOX_L, hero.y + BOX_B)) {
                hero.xsub = 0;
                return;
            }
        } else {
            if (hero.x >= MAX_X) { hero.xsub = 0; return; }
            nx = hero.x + 1;
            if (solid_at(nx + BOX_R, hero.y + 1) ||
                solid_at(nx + BOX_R, hero.y + 8) ||
                solid_at(nx + BOX_R, hero.y + BOX_B)) {
                hero.xsub = 0;
                return;
            }
        }
        hero.x = nx;
    }
}

void move_hero_y(void) {
    u8 steps;
    u8 sub;
    u8 down;
    u8 speed;
    u8 was_ground;

    /* 서 있을 때도 중력은 매 프레임 1픽셀 내리누르므로, 착지 판정은 계속
     * 참이 된다. 착지음은 "공중 -> 땅"으로 바뀐 순간에만 울려야 한다. */
    was_ground = on_ground;
    on_ground = 0;
    if (hero.vy < 0) {
        down = 0;
        speed = abs8(hero.vy);
    } else {
        down = 1;
        speed = hero.vy;
    }

    sub = hero.ysub + speed;
    steps = sub / SUB_PX;
    hero.ysub = sub & 15;

    while (steps > 0) {
        steps = steps - 1;
        if (down) {
            if (hero.y >= PIT_Y) { hero.y = PIT_Y; return; }
            if (solid_at(hero.x + BOX_L, hero.y + BOX_B + 1) ||
                solid_at(hero.x + BOX_R, hero.y + BOX_B + 1)) {
                hero.ysub = 0;
                hero.vy = 0;
                if (was_ground == 0) sfx_play(SFX_LAND);
                on_ground = 1;
                return;
            }
            hero.y = hero.y + 1;
        } else {
            if (hero.y <= CELL_PX) { hero.y = CELL_PX; hero.vy = 0; return; }
            if (solid_at(hero.x + BOX_L, hero.y - 1) ||
                solid_at(hero.x + BOX_R, hero.y - 1)) {
                hero.ysub = 0;
                hero.vy = 0;
                return;
            }
            hero.y = hero.y - 1;
        }
    }
    /* 발밑이 비어 있으면 공중이다. */
    if (solid_at(hero.x + BOX_L, hero.y + BOX_B + 1) ||
        solid_at(hero.x + BOX_R, hero.y + BOX_B + 1)) {
        on_ground = 1;
    }
}

void collect_and_hazards(void) {
    u8 kind;

    kind = cell_at(hero.x + 8, hero.y + 8);
    if (kind == C_GEM) {
        clear_cell(cell_x, cell_y);
        score = score + 100;
        hud_dirty = 1;
        sfx_play(SFX_GEM);
        return;
    }
    if (kind == C_SPIKE) {
        hero.alive = 0;
        return;
    }
    if (kind == C_GOAL) {
        state = ST_CLEAR;
        state_timer = 90;
        score = score + 1000;
        hud_dirty = 1;
        music_stop();
        sfx_play(SFX_CLEAR);
        return;
    }
    if (hero.y >= PIT_Y) hero.alive = 0;
}

void update_foes(void) {
    u8 sub;
    u8 nx;

    for (i = 0; i < foe_count; i++) {
        if (foes[i].alive == 0) continue;

        sub = foes[i].xsub + FOE_SPEED;
        foes[i].xsub = sub & 15;
        if (sub >= SUB_PX) {
            if (foes[i].face) {
                nx = foes[i].x - 1;
                /* 벽에 닿거나 발판 끝이면 돌아선다. */
                if (foes[i].x == 0 ||
                    solid_at(nx + 2, foes[i].y + 8) ||
                    solid_at(nx + 2, foes[i].y + 17) == 0) {
                    foes[i].face = 0;
                } else {
                    foes[i].x = nx;
                }
            } else {
                nx = foes[i].x + 1;
                if (foes[i].x >= MAX_X ||
                    solid_at(nx + 13, foes[i].y + 8) ||
                    solid_at(nx + 13, foes[i].y + 17) == 0) {
                    foes[i].face = 1;
                } else {
                    foes[i].x = nx;
                }
            }
        }

        if (box_hit(hero.x, hero.y, HIT_W, HIT_H,
                    foes[i].x, foes[i].y, HIT_W, HIT_H)) {
            /* 떨어지면서 위에서 닿았으면 밟은 것. */
            if (hero.vy > 0 && hero.y + STOMP_Y <= foes[i].y) {
                foes[i].alive = 0;
                score = score + 200;
                hud_dirty = 1;
                hero.vy = 0 - (JUMP_SPEED / 2);
                on_ground = 0;
                sfx_play(SFX_STOMP);
            } else {
                hero.alive = 0;
            }
        }
    }
}

void draw_actors(void) {
    u8 shape;

    spr_clear();

    if (on_ground == 0) {
        shape = MS_HERO_JUMP;
    } else if (walk_frame) {
        shape = MS_HERO_WALK;
    } else {
        shape = MS_HERO_IDLE;
    }
    spr_meta_flip(hero.x, hero.y, shape, hero.face);

    for (i = 0; i < foe_count; i++) {
        if (foes[i].alive == 0) continue;
        if (frame_count() & FOE_ANIM) {
            spr_meta_flip(foes[i].x, foes[i].y, MS_FOE_A, foes[i].face);
        } else {
            spr_meta_flip(foes[i].x, foes[i].y, MS_FOE_B, foes[i].face);
        }
    }
}

void update_play(void) {
    u8 pad;
    u8 speed;

    pad = pad_held(0);
    speed = 0;

    if (pad & PAD_LEFT) {
        hero.face = 1;
        speed = WALK_SPEED;
        if (pad & PAD_B) speed = RUN_SPEED;
        move_hero_x(speed, 1);
    } else if (pad & PAD_RIGHT) {
        hero.face = 0;
        speed = WALK_SPEED;
        if (pad & PAD_B) speed = RUN_SPEED;
        move_hero_x(speed, 0);
    }

    if (speed && on_ground) {
        walk_timer = walk_timer + 1;
        if (walk_timer >= WALK_ANIM) {
            walk_timer = 0;
            walk_frame = walk_frame ^ 1;
        }
    } else {
        walk_timer = 0;
        walk_frame = 0;
    }

    if ((pad_pressed(0) & PAD_A) && on_ground) {
        hero.vy = 0 - JUMP_SPEED;
        on_ground = 0;
        jump_held = 1;
        sfx_play(SFX_JUMP);
    }
    /* A를 놓으면 상승을 깎는다. 이게 "짧게 누르면 낮게 뛴다"의 전부다. */
    if (jump_held && (pad_released(0) & PAD_A)) {
        jump_held = 0;
        if (hero.vy < 0 - JUMP_CUT) hero.vy = 0 - JUMP_CUT;
    }
    if (hero.vy >= 0) jump_held = 0;

    if (hero.vy < MAX_FALL) hero.vy = hero.vy + GRAVITY;
    if (hero.vy > MAX_FALL) hero.vy = MAX_FALL;

    move_hero_y();
    collect_and_hazards();
    if (state != ST_PLAY) return;
    update_foes();

    if (hero.alive == 0) {
        state = ST_DEAD;
        state_timer = 70;
        music_stop();
        sfx_play(SFX_HURT);
    }
}

void show_title(void) {
    ppu_off();
    bg_clear(0);
    pal_load(PAL_TITLE);
    bg_text(11, 10, "FAMI-C");
    bg_text(8, 12, "PLATFORMER");
    bg_text(7, 17, "PRESS START");
    bg_text(4, 22, "LEFT RIGHT - MOVE");
    bg_text(4, 24, "B HOLD     - RUN");
    bg_text(4, 26, "A          - JUMP");
    ppu_on();
    music_play(SONG_TITLE);
}

void show_gameover(void) {
    ppu_off();
    bg_clear(0);
    pal_load(PAL_TITLE);
    bg_text(11, 12, "GAME OVER");
    bg_text(10, 15, "SCORE");
    bg_number(16, 15, score, 5);
    bg_text(7, 20, "PRESS START");
    ppu_on();
    music_stop();
}

/* ======================================================================
 * 5. main
 * ==================================================================== */

void main(void) {
    state = ST_TITLE;
    show_title();

    while (1) {
        pad_poll();

        switch (state) {

        case ST_TITLE:
            if (pad_pressed(0) & PAD_START) {
                rand_seed(frame_count() + 1);
                stage = 0;
                lives = START_LIVES;
                score = 0;
                state = ST_PLAY;
                load_stage();
            }
            break;

        case ST_PLAY:
            update_play();
            if (state == ST_PLAY) {
                draw_actors();
                if (hud_dirty) {
                    draw_hud();
                    hud_dirty = 0;
                }
            }
            break;

        case ST_DEAD:
            draw_actors();
            state_timer = state_timer - 1;
            if (state_timer == 0) {
                if (lives > 1) {
                    lives = lives - 1;
                    state = ST_PLAY;
                    load_stage();
                } else {
                    lives = 0;
                    state = ST_OVER;
                    sfx_play(SFX_OVER);
                    show_gameover();
                }
            }
            break;

        case ST_CLEAR:
            draw_actors();
            state_timer = state_timer - 1;
            if (state_timer == 0) {
                stage = stage + 1;
                if (stage >= STAGE_COUNT) {
                    state = ST_OVER;
                    show_gameover();
                } else {
                    state = ST_PLAY;
                    load_stage();
                }
            }
            break;

        default:
            spr_clear();
            if (pad_pressed(0) & PAD_START) {
                state = ST_TITLE;
                show_title();
            }
            break;
        }

        wait_vblank();
    }
}
