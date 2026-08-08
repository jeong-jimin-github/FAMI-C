/* FAMI-C 예제: 낙하 블록 퍼즐
 *
 * 플랫포머가 스프라이트/물리의 표준 구현이라면, 이쪽은 배경 전용 게임의
 * 표준 구현이다. 스프라이트를 하나도 쓰지 않고 네임테이블만 갱신한다.
 *
 * 배경 갱신 규칙 (중요)
 *   bg_tile() 은 렌더링 중이면 큐에 넣고 다음 vblank 에 반영한다. 큐가 차면
 *   NMI 가 비울 때까지 기다린다. 그래서 줄 지우기처럼 200칸을 한 번에 다시
 *   그려도 화면이 깨지지 않고, 몇 프레임에 걸쳐 반영될 뿐이다.
 *   타이밍을 직접 맞출 필요가 없다.
 */

#include <fami.h>

/* ======================================================================
 * 1. 에셋
 * ==================================================================== */

asset palette PAL_GAME = {
    /* 0: HUD 글자  1: 블록  2: 우물 테두리  3: 예비 */
    0x0F, 0x30, 0x10, 0x00,
    0x0F, 0x30, 0x21, 0x11,
    0x0F, 0x2D, 0x00, 0x10,
    0x0F, 0x16, 0x27, 0x37,
    0x0F, 0x30, 0x21, 0x11,   0x0F, 0x30, 0x21, 0x11,
    0x0F, 0x30, 0x21, 0x11,   0x0F, 0x30, 0x21, 0x11
};

/* 레벨이 오를 때마다 블록 색만 바꾼다. NES 는 16x16 칸마다 팔레트를
 * 하나씩 고르므로, 8x8 블록에 조각별 색을 주려면 색이 번져 버린다.
 * 그래서 색은 레벨을 따라가고, 조각은 무늬로 구분한다. */
const u8 LEVEL_COLOR[10] = { 0x21, 0x2A, 0x25, 0x27, 0x2C, 0x24, 0x28, 0x23, 0x26, 0x2B };

/* 7개 조각 얼굴. 무늬가 서로 달라서 흑백으로 봐도 구분된다. */
asset tiles T_BLOCK[7] = {
    "2222222." "2111111." "2111111." "2111111." "2111111." "2111111." "2111111." "........"
    "2222222." "2133311." "2133311." "2111111." "2111111." "2111111." "2111111." "........"
    "2222222." "2111111." "2111111." "2113311." "2113311." "2111111." "2111111." "........"
    "2222222." "2111111." "2111111." "2111111." "2111111." "2113331." "2113331." "........"
    "2222222." "2311111." "2311111." "2311111." "2311111." "2311111." "2311111." "........"
    "2222222." "2111113." "2111113." "2111113." "2111113." "2111113." "2111113." "........"
    "2222222." "2333333." "2111111." "2111111." "2111111." "2333333." "2111111." "........"
};

asset tile T_WALL = {
    "22222222"
    "23333332"
    "23222232"
    "23233232"
    "23233232"
    "23222232"
    "23333332"
    "22222222"
};

asset tile T_FLOOR = {
    "22222222"
    "23232323"
    "22222222"
    "32323232"
    "22222222"
    "23232323"
    "22222222"
    "32323232"
};

/* --- 효과음 --- */

asset sfx SFX_MOVE   = { {6, N_C5}, {3, N_C5} };
asset sfx SFX_ROTATE = { {8, N_G5}, {6, N_C6}, {3, N_C6} };
asset sfx SFX_LOCK   = { {9, N_C3}, {7, N_G2}, {4, N_C2} };
asset sfx SFX_DROP   = { {11, N_C4}, {9, N_G3}, {7, N_E3}, {4, N_C3}, {2, N_C2} };
asset sfx SFX_LINE   = { {12, N_C5}, {12, N_E5}, {12, N_G5}, {11, N_C6},
                         {10, N_E6}, {8, N_G6}, {5, N_C7}, {2, N_C7} };
asset sfx SFX_TETRIS = { {13, N_C5}, {13, N_G5}, {13, N_C6}, {13, N_G6},
                         {12, N_C7}, {11, N_G6}, {10, N_C7}, {8, N_E7},
                         {6, N_G7}, {4, N_G7}, {2, N_G7} };
asset sfx SFX_LEVEL  = { {12, N_C6}, {12, N_D6}, {12, N_E6}, {12, N_G6}, {9, N_C7},
                         {6, N_C7}, {3, N_C7} };
asset sfx SFX_OVER   = { {13, N_C4}, {12, N_B3}, {12, N_AS3}, {11, N_A3}, {10, N_GS3},
                         {9, N_G3}, {8, N_FS3}, {7, N_F3}, {5, N_E3}, {4, N_DS3},
                         {3, N_D3}, {2, N_CS3}, {1, N_C3} };

/* --- BGM: 32행 루프 --- */

asset song SONG_MAIN = { 8,
    { N_E5, N_E4, N_E2, 4 },  { N_B4, HOLD, HOLD, 0 },
    { N_C5, N_A4, N_A2, 3 },  { N_D5, HOLD, HOLD, 0 },
    { N_E5, N_GS4, N_E2, 4 }, { N_D5, HOLD, HOLD, 0 },
    { N_C5, N_A4, N_A2, 3 },  { N_B4, HOLD, HOLD, 0 },
    { N_A4, N_A4, N_A2, 4 },  { HOLD, HOLD, HOLD, 0 },
    { N_C5, N_C5, N_E2, 3 },  { N_E5, HOLD, HOLD, 0 },
    { N_A5, N_E5, N_A2, 4 },  { N_GS5, HOLD, HOLD, 0 },
    { N_E5, N_B4, N_E2, 3 },  { 0, 0, 0, 0 },

    { N_D5, N_D4, N_D2, 4 },  { N_F5, HOLD, HOLD, 0 },
    { N_A5, N_A4, N_A2, 3 },  { N_G5, HOLD, HOLD, 0 },
    { N_F5, N_C5, N_F2, 4 },  { N_E5, HOLD, HOLD, 0 },
    { N_C5, N_A4, N_A2, 3 },  { N_E5, HOLD, HOLD, 0 },
    { N_D5, N_D5, N_D2, 4 },  { N_C5, HOLD, HOLD, 0 },
    { N_B4, N_B4, N_E2, 3 },  { N_C5, HOLD, HOLD, 0 },
    { N_D5, N_D5, N_GS2, 4 }, { N_E5, HOLD, HOLD, 0 },
    { N_C5, N_C5, N_A2, 3 },  { 0, 0, 0, 0 }
};

asset song SONG_TITLE = { 12,
    { N_A4, N_A3, N_A2, 0 }, { N_C5, HOLD, HOLD, 0 },
    { N_E5, N_E4, HOLD, 0 }, { N_A5, HOLD, HOLD, 0 },
    { N_G5, N_G3, N_G2, 0 }, { N_E5, HOLD, HOLD, 0 },
    { N_C5, N_C4, HOLD, 0 }, { 0, 0, 0, 0 }
};

/* ======================================================================
 * 2. 상수
 * ==================================================================== */

#define WELL_W       10
#define WELL_H       20
#define BOARD_SIZE   200        /* WELL_W * WELL_H */

/* 우물의 왼쪽 위 타일 좌표. 우물 한 칸 = 타일 한 장(8x8). */
#define WELL_X       11
#define WELL_Y       4

#define PIECE_COUNT  7
#define SPAWN_X      3
#define SPAWN_Y      0

#define DAS_DELAY    16         /* 처음 눌림 -> 자동 반복까지 */
#define DAS_RATE     6          /* 자동 반복 간격 */
#define LOCK_DELAY   30         /* 바닥에 닿고 굳기까지 */
#define CLEAR_FLASH  4          /* 줄 지우기 깜빡임 횟수 */
#define CLEAR_TIME   6          /* 깜빡임 한 번의 프레임 수 */
#define MAX_LEVEL    19
#define BEST_COUNT   3

enum { ST_TITLE, ST_PLAY, ST_CLEARING, ST_PAUSE, ST_NAME, ST_OVER };

/* 조각 모양. 조각 7개 x 회전 4개 x 칸 4개.
 * 한 바이트가 4x4 상자 안의 좌표 하나: (y << 2) | x.
 * 회전은 전부 고정된 중심에 대한 진짜 회전이라, 돌려도 모양이 변하거나
 * 옆으로 밀리지 않는다. */
const u8 SHAPES[112] = {
    /* I */  4, 5, 6, 7,    2, 6, 10, 14,   4, 5, 6, 7,    2, 6, 10, 14,
    /* J */  0, 4, 5, 6,    1, 2, 5, 9,     4, 5, 6, 10,   1, 5, 8, 9,
    /* L */  2, 4, 5, 6,    1, 5, 9, 10,    4, 5, 6, 8,    0, 1, 5, 9,
    /* O */  1, 2, 5, 6,    1, 2, 5, 6,     1, 2, 5, 6,    1, 2, 5, 6,
    /* S */  1, 2, 4, 5,    1, 5, 6, 10,    1, 2, 4, 5,    1, 5, 6, 10,
    /* T */  1, 4, 5, 6,    1, 5, 6, 9,     4, 5, 6, 9,    1, 4, 5, 9,
    /* Z */  0, 1, 5, 6,    2, 5, 6, 9,     0, 1, 5, 6,    2, 5, 6, 9
};

/* 미리보기에서 조각을 가운데로 옮기는 보정. */
const u8 PREVIEW_SHIFT[PIECE_COUNT] = { 0, 0, 0, 0, 0, 0, 0 };

/* 벽 차기: 회전이 막혔을 때 시도할 가로 이동. 0 은 제자리. */
const u8 KICKS[5] = { 0, 255, 1, 254, 2 };

/* 레벨별 낙하 간격(프레임). NES 원작의 곡선을 따른다. */
const u8 GRAVITY[20] = {
    48, 43, 38, 33, 28, 23, 18, 13, 8, 6,
    5, 5, 5, 4, 4, 4, 3, 3, 3, 2
};

/* 한 번에 지운 줄 수별 점수 배수. (레벨+1) 을 곱한다. */
const u16 LINE_SCORE[5] = { 0, 40, 100, 300, 1200 };

const u8 DEFAULT_BEST[BEST_COUNT] = { 30, 20, 10 };   /* x100 점 */

/* ======================================================================
 * 3. 상태
 * ==================================================================== */

u8 board[BOARD_SIZE];      /* 0 = 빈칸, 1..7 = 조각 종류 + 1 */
u8 bag[PIECE_COUNT];
u8 bag_pos;
u8 next_piece;

u8 piece_t;                /* 지금 조각 종류 0..6 */
u8 piece_r;                /* 회전 0..3 */
u8 piece_x;
u8 piece_y;

u8 state;
u8 level;
u8 start_level;
u16 score;
u16 lines;
u8 drop_timer;
u8 lock_timer;
u8 grounded;
u8 das_timer;
u8 das_dir;
u8 clear_timer;
u8 clear_step;
u8 clear_rows[4];
u8 clear_count;

u16 best_score[BEST_COUNT];
u8 best_name[BEST_COUNT * 3];
u8 name_slot;
u8 name_pos;
u8 name_char[3];

u8 i;
u8 j;
u8 k;

/* ======================================================================
 * 4. 우물 그리기
 * ==================================================================== */

u8 cell_tile(u8 value) {
    if (value == 0) return 0;
    return T_BLOCK + value - 1;
}

void draw_cell(u8 cx, u8 cy) {
    bg_tile(WELL_X + cx, WELL_Y + cy, cell_tile(board[cy * WELL_W + cx]));
}

void draw_board(void) {
    for (i = 0; i < WELL_H; i++) {
        for (j = 0; j < WELL_W; j++) {
            draw_cell(j, i);
        }
    }
}

/* 지금 조각의 네 칸을 그리거나(value != 0) 지운다(value == 0). */
void stamp_piece(u8 value) {
    u8 cell;
    u8 cx;
    u8 cy;

    for (k = 0; k < 4; k++) {
        cell = SHAPES[piece_t * 16 + piece_r * 4 + k];
        cx = piece_x + (cell & 3);
        cy = piece_y + (cell >> 2);
        if (cy >= WELL_H) continue;
        if (cx >= WELL_W) continue;
        bg_tile(WELL_X + cx, WELL_Y + cy, cell_tile(value));
    }
}

/* 조각이 (px, py, pr) 위치에 놓일 수 있는가. */
u8 fits(u8 px, u8 py, u8 pr) {
    u8 cell;
    u8 cx;
    u8 cy;

    for (k = 0; k < 4; k++) {
        cell = SHAPES[piece_t * 16 + pr * 4 + k];
        cx = px + (cell & 3);
        cy = py + (cell >> 2);
        if (cx >= WELL_W) return 0;      /* 255 로 감싸 돌아도 여기서 걸린다 */
        if (cy >= WELL_H) return 0;
        if (board[cy * WELL_W + cx]) return 0;
    }
    return 1;
}

void lock_piece(void) {
    u8 cell;
    u8 cx;
    u8 cy;

    for (k = 0; k < 4; k++) {
        cell = SHAPES[piece_t * 16 + piece_r * 4 + k];
        cx = piece_x + (cell & 3);
        cy = piece_y + (cell >> 2);
        if (cx < WELL_W && cy < WELL_H) {
            board[cy * WELL_W + cx] = piece_t + 1;
        }
    }
}

/* ======================================================================
 * 5. HUD
 * ==================================================================== */

void draw_preview(void) {
    u8 cell;
    u8 cx;
    u8 cy;

    for (i = 0; i < 4; i++) {
        for (j = 0; j < 4; j++) {
            bg_tile(3 + j, 8 + i, 0);
        }
    }
    for (k = 0; k < 4; k++) {
        cell = SHAPES[next_piece * 16];
        cell = SHAPES[next_piece * 16 + k];
        cx = cell & 3;
        cy = cell >> 2;
        bg_tile(3 + cx, 8 + cy, T_BLOCK + next_piece);
    }
}

void draw_hud(void) {
    bg_text(2, 3, "SCORE");
    bg_number(2, 4, score, 5);
    bg_text(2, 6, "NEXT");
    bg_text(24, 3, "LINES");
    bg_number(24, 4, lines, 3);
    bg_text(24, 6, "LEVEL");
    bg_number(24, 7, level, 2);
}

void apply_level_color(void) {
    u8 tone;

    tone = LEVEL_COLOR[level % 10];
    pal_set(6, tone);          /* 배경 팔레트 1 의 두 번째 색 */
    pal_set(7, tone - 0x10);
}

void draw_frame(void) {
    /* 우물 테두리. 좌우 한 줄씩, 바닥 한 줄. */
    for (i = 0; i < WELL_H; i++) {
        bg_tile(WELL_X - 1, WELL_Y + i, T_WALL);
        bg_tile(WELL_X + WELL_W, WELL_Y + i, T_WALL);
    }
    for (j = 0; j < WELL_W + 2; j++) {
        bg_tile(WELL_X - 1 + j, WELL_Y + WELL_H, T_FLOOR);
    }
    /* 우물과 테두리가 들어가는 16x16 칸의 팔레트를 정한다. */
    for (i = 1; i < 12; i++) {
        for (j = 5; j < 11; j++) {
            bg_attr(j, i, 1);
        }
    }
}

/* ======================================================================
 * 6. 조각 공급 (7-bag)
 * ==================================================================== */

void refill_bag(void) {
    u8 pick;
    u8 swap;

    for (i = 0; i < PIECE_COUNT; i++) {
        bag[i] = i;
    }
    /* 피셔-예이츠 셔플. 7개가 한 번씩 나오므로 같은 조각이 몰리지 않는다. */
    for (i = PIECE_COUNT - 1; i > 0; i--) {
        pick = rand_range(i + 1);
        swap = bag[i];
        bag[i] = bag[pick];
        bag[pick] = swap;
    }
    bag_pos = 0;
}

u8 take_piece(void) {
    u8 value;

    if (bag_pos >= PIECE_COUNT) refill_bag();
    value = bag[bag_pos];
    bag_pos = bag_pos + 1;
    return value;
}

u8 spawn_piece(void) {
    piece_t = next_piece;
    next_piece = take_piece();
    piece_r = 0;
    piece_x = SPAWN_X;
    piece_y = SPAWN_Y;
    drop_timer = GRAVITY[level];
    lock_timer = 0;
    grounded = 0;
    draw_preview();
    if (fits(piece_x, piece_y, piece_r) == 0) return 0;
    stamp_piece(piece_t + 1);
    return 1;
}

/* ======================================================================
 * 7. 줄 지우기
 * ==================================================================== */

u8 find_full_rows(void) {
    u8 full;

    clear_count = 0;
    for (i = 0; i < WELL_H; i++) {
        full = 1;
        for (j = 0; j < WELL_W; j++) {
            if (board[i * WELL_W + j] == 0) {
                full = 0;
                break;
            }
        }
        if (full && clear_count < 4) {
            clear_rows[clear_count] = i;
            clear_count = clear_count + 1;
        }
    }
    return clear_count;
}

void collapse_rows(void) {
    u8 src;
    u8 dst;
    u8 keep;

    dst = WELL_H;
    src = WELL_H;
    while (src > 0) {
        src = src - 1;
        keep = 1;
        for (k = 0; k < clear_count; k++) {
            if (clear_rows[k] == src) keep = 0;
        }
        if (keep) {
            dst = dst - 1;
            if (dst != src) {
                for (j = 0; j < WELL_W; j++) {
                    board[dst * WELL_W + j] = board[src * WELL_W + j];
                }
            }
        }
    }
    while (dst > 0) {
        dst = dst - 1;
        for (j = 0; j < WELL_W; j++) {
            board[dst * WELL_W + j] = 0;
        }
    }
}

void award_lines(void) {
    u16 gain;
    u8 new_level;

    gain = LINE_SCORE[clear_count] * (level + 1);
    score = score + gain;
    lines = lines + clear_count;

    new_level = start_level + lines / 10;
    if (new_level > MAX_LEVEL) new_level = MAX_LEVEL;
    if (new_level != level) {
        level = new_level;
        apply_level_color();
        sfx_play(SFX_LEVEL);
    }
}

/* ======================================================================
 * 8. 최고 점수
 * ==================================================================== */

void reset_best(void) {
    for (i = 0; i < BEST_COUNT; i++) {
        best_score[i] = DEFAULT_BEST[i] * 100;
        best_name[i * 3 + 0] = 'A';
        best_name[i * 3 + 1] = 'A';
        best_name[i * 3 + 2] = 'A';
    }
}

/* 새 기록이면 들어갈 자리를, 아니면 BEST_COUNT 를 돌려준다. */
u8 best_slot_for(u16 value) {
    for (i = 0; i < BEST_COUNT; i++) {
        if (value > best_score[i]) return i;
    }
    return BEST_COUNT;
}

void insert_best(u8 slot, u16 value) {
    u8 pos;

    pos = BEST_COUNT - 1;
    while (pos > slot) {
        best_score[pos] = best_score[pos - 1];
        best_name[pos * 3 + 0] = best_name[(pos - 1) * 3 + 0];
        best_name[pos * 3 + 1] = best_name[(pos - 1) * 3 + 1];
        best_name[pos * 3 + 2] = best_name[(pos - 1) * 3 + 2];
        pos = pos - 1;
    }
    best_score[slot] = value;
    best_name[slot * 3 + 0] = 'A';
    best_name[slot * 3 + 1] = 'A';
    best_name[slot * 3 + 2] = 'A';
}

void draw_best_table(u8 top) {
    bg_text(9, top, "BEST PLAYERS");
    for (i = 0; i < BEST_COUNT; i++) {
        bg_number(9, top + 2 + i * 2, i + 1, 1);
        for (j = 0; j < 3; j++) {
            bg_char(12 + j, top + 2 + i * 2, best_name[i * 3 + j]);
        }
        bg_number(17, top + 2 + i * 2, best_score[i], 5);
    }
}

/* ======================================================================
 * 9. 화면 전환
 * ==================================================================== */

void show_title(void) {
    ppu_off();
    bg_clear(0);
    pal_load(PAL_GAME);
    bg_text(12, 2, "FAMI-C");
    bg_text(11, 4, "BLOCKS");
    bg_text(8, 8, "LEVEL");
    bg_number(14, 8, start_level, 2);
    bg_text(6, 10, "UP DOWN    +- 5");
    bg_text(6, 11, "LEFT RIGHT +- 1");
    draw_best_table(15);
    bg_text(10, 25, "PRESS START");
    ppu_on();
    music_play(SONG_TITLE);
}

void start_game(void) {
    ppu_off();
    bg_clear(0);
    pal_load(PAL_GAME);

    for (i = 0; i < BOARD_SIZE; i++) {
        board[i] = 0;
    }
    level = start_level;
    score = 0;
    lines = 0;
    das_timer = 0;
    das_dir = 0;
    clear_count = 0;

    draw_frame();
    draw_hud();
    apply_level_color();

    refill_bag();
    next_piece = take_piece();
    ppu_on();
    music_play(SONG_MAIN);
    spawn_piece();
}

void show_gameover(void) {
    ppu_off();
    bg_clear(0);
    pal_load(PAL_GAME);
    bg_text(11, 6, "GAME OVER");
    bg_text(9, 9, "SCORE");
    bg_number(16, 9, score, 5);
    bg_text(9, 11, "LINES");
    bg_number(16, 11, lines, 3);
    draw_best_table(15);
    bg_text(10, 25, "PRESS START");
    ppu_on();
    music_stop();
    sfx_play(SFX_OVER);
}

void show_name_entry(void) {
    ppu_off();
    bg_clear(0);
    pal_load(PAL_GAME);
    bg_text(9, 6, "NEW BEST SCORE");
    bg_number(13, 8, score, 5);
    bg_text(6, 13, "UP DOWN    LETTER");
    bg_text(6, 14, "LEFT RIGHT SLOT");
    bg_text(6, 15, "START      OK");
    ppu_on();
    music_stop();
}

void draw_name_entry(void) {
    for (i = 0; i < 3; i++) {
        bg_char(14 + i * 2, 11, name_char[i]);
        if (i == name_pos) {
            bg_char(14 + i * 2, 12, '-');
        } else {
            bg_char(14 + i * 2, 12, ' ');
        }
    }
}

/* ======================================================================
 * 10. 조작
 * ==================================================================== */

void try_move(u8 dx) {
    u8 nx;

    nx = piece_x + dx;
    stamp_piece(0);
    if (fits(nx, piece_y, piece_r)) {
        piece_x = nx;
        if (grounded) lock_timer = 0;
        sfx_play(SFX_MOVE);
    }
    stamp_piece(piece_t + 1);
}

void try_rotate(u8 dir) {
    u8 nr;
    u8 kick;

    nr = (piece_r + dir) & 3;
    stamp_piece(0);
    for (k = 0; k < 5; k++) {
        kick = KICKS[k];
        if (fits(piece_x + kick, piece_y, nr)) {
            piece_x = piece_x + kick;
            piece_r = nr;
            if (grounded) lock_timer = 0;
            sfx_play(SFX_ROTATE);
            break;
        }
    }
    stamp_piece(piece_t + 1);
}

/* 한 칸 내린다. 내려갔으면 1, 바닥이면 0. */
u8 step_down(void) {
    stamp_piece(0);
    if (fits(piece_x, piece_y + 1, piece_r)) {
        piece_y = piece_y + 1;
        stamp_piece(piece_t + 1);
        return 1;
    }
    stamp_piece(piece_t + 1);
    return 0;
}

void hard_drop(void) {
    stamp_piece(0);
    while (fits(piece_x, piece_y + 1, piece_r)) {
        piece_y = piece_y + 1;
        score = score + 2;
    }
    stamp_piece(piece_t + 1);
    sfx_play(SFX_DROP);
    lock_timer = LOCK_DELAY;
    grounded = 1;
}

void handle_das(u8 pad, u8 pressed) {
    u8 dir;

    dir = 0;
    if (pad & PAD_LEFT) dir = 1;
    if (pad & PAD_RIGHT) dir = 2;

    if (dir == 0) {
        das_dir = 0;
        das_timer = 0;
        return;
    }
    if (dir != das_dir) {
        das_dir = dir;
        das_timer = DAS_DELAY;
        if (dir == 1) try_move(255); else try_move(1);
        return;
    }
    das_timer = das_timer - 1;
    if (das_timer == 0) {
        das_timer = DAS_RATE;
        if (dir == 1) try_move(255); else try_move(1);
    }
}

/* ======================================================================
 * 11. 상태별 갱신
 * ==================================================================== */

void update_play(void) {
    u8 pad;
    u8 pressed;

    pad = pad_held(0);
    pressed = pad_pressed(0);

    if (pressed & PAD_START) {
        state = ST_PAUSE;
        music_pause();
        bg_text(13, 14, "PAUSE");
        return;
    }
    if (pressed & PAD_A) try_rotate(1);
    if (pressed & PAD_B) try_rotate(3);
    if (pressed & PAD_UP) {
        hard_drop();
    }
    handle_das(pad, pressed);

    if (pad & PAD_DOWN) {
        drop_timer = 1;
        score = score + 1;
    }

    drop_timer = drop_timer - 1;
    if (drop_timer == 0) {
        drop_timer = GRAVITY[level];
        if (step_down()) {
            grounded = 0;
            lock_timer = 0;
        } else {
            grounded = 1;
        }
    }

    if (grounded) {
        lock_timer = lock_timer + 1;
        if (lock_timer >= LOCK_DELAY) {
            lock_piece();
            sfx_play(SFX_LOCK);
            if (find_full_rows()) {
                if (clear_count >= 4) sfx_play(SFX_TETRIS); else sfx_play(SFX_LINE);
                state = ST_CLEARING;
                clear_step = 0;
                clear_timer = CLEAR_TIME;
                return;
            }
            if (spawn_piece() == 0) {
                name_slot = best_slot_for(score);
                if (name_slot < BEST_COUNT) {
                    insert_best(name_slot, score);
                    name_pos = 0;
                    name_char[0] = 'A';
                    name_char[1] = 'A';
                    name_char[2] = 'A';
                    state = ST_NAME;
                    show_name_entry();
                    draw_name_entry();
                } else {
                    state = ST_OVER;
                    show_gameover();
                }
            }
            draw_hud();
        }
    }
}

void update_clearing(void) {
    u8 row;

    clear_timer = clear_timer - 1;
    if (clear_timer) return;
    clear_timer = CLEAR_TIME;

    if (clear_step < CLEAR_FLASH) {
        /* 지워질 줄을 번갈아 비웠다 채우며 깜빡인다. */
        for (k = 0; k < clear_count; k++) {
            row = clear_rows[k];
            for (j = 0; j < WELL_W; j++) {
                if (clear_step & 1) {
                    bg_tile(WELL_X + j, WELL_Y + row, cell_tile(board[row * WELL_W + j]));
                } else {
                    bg_tile(WELL_X + j, WELL_Y + row, 0);
                }
            }
        }
        clear_step = clear_step + 1;
        return;
    }

    collapse_rows();
    award_lines();
    draw_board();
    draw_hud();
    clear_count = 0;
    if (spawn_piece() == 0) {
        name_slot = best_slot_for(score);
        if (name_slot < BEST_COUNT) {
            insert_best(name_slot, score);
            name_pos = 0;
            name_char[0] = 'A';
            name_char[1] = 'A';
            name_char[2] = 'A';
            state = ST_NAME;
            show_name_entry();
            draw_name_entry();
        } else {
            state = ST_OVER;
            show_gameover();
        }
        return;
    }
    state = ST_PLAY;
}

void update_title(void) {
    u8 pressed;
    u8 changed;

    pressed = pad_pressed(0);
    changed = 0;

    if ((pressed & PAD_RIGHT) && start_level < MAX_LEVEL) {
        start_level = start_level + 1;
        changed = 1;
    }
    if ((pressed & PAD_LEFT) && start_level > 0) {
        start_level = start_level - 1;
        changed = 1;
    }
    if (pressed & PAD_UP) {
        start_level = start_level + 5;
        if (start_level > MAX_LEVEL) start_level = MAX_LEVEL;
        changed = 1;
    }
    if (pressed & PAD_DOWN) {
        if (start_level >= 5) start_level = start_level - 5; else start_level = 0;
        changed = 1;
    }
    if (changed) {
        bg_number(14, 8, start_level, 2);
        sfx_play(SFX_MOVE);
    }
    if (pressed & PAD_START) {
        /* 타이틀에서 기다린 프레임 수로 씨를 뿌린다. 매판 다른 순서가 된다. */
        rand_seed(frame_count() + 1);
        state = ST_PLAY;
        start_game();
    }
}

void update_name(void) {
    u8 pressed;

    pressed = pad_pressed(0);

    if (pressed & PAD_UP) {
        if (name_char[name_pos] >= 'Z') {
            name_char[name_pos] = 'A';
        } else {
            name_char[name_pos] = name_char[name_pos] + 1;
        }
        sfx_play(SFX_MOVE);
    }
    if (pressed & PAD_DOWN) {
        if (name_char[name_pos] <= 'A') {
            name_char[name_pos] = 'Z';
        } else {
            name_char[name_pos] = name_char[name_pos] - 1;
        }
        sfx_play(SFX_MOVE);
    }
    if ((pressed & PAD_RIGHT) || (pressed & PAD_A)) {
        name_pos = name_pos + 1;
        if (name_pos >= 3) name_pos = 0;
        sfx_play(SFX_MOVE);
    }
    if (pressed & PAD_LEFT) {
        if (name_pos == 0) name_pos = 2; else name_pos = name_pos - 1;
        sfx_play(SFX_MOVE);
    }
    if (pressed & PAD_START) {
        for (i = 0; i < 3; i++) {
            best_name[name_slot * 3 + i] = name_char[i];
        }
        state = ST_OVER;
        show_gameover();
        return;
    }
    draw_name_entry();
}

/* ======================================================================
 * 12. main
 * ==================================================================== */

void main(void) {
    reset_best();
    start_level = 0;
    state = ST_TITLE;
    show_title();

    while (1) {
        pad_poll();

        switch (state) {

        case ST_TITLE:
            update_title();
            break;

        case ST_PLAY:
            update_play();
            break;

        case ST_CLEARING:
            update_clearing();
            break;

        case ST_PAUSE:
            if (pad_pressed(0) & PAD_START) {
                bg_text(13, 14, "     ");
                music_resume();
                state = ST_PLAY;
            }
            break;

        case ST_NAME:
            update_name();
            break;

        default:
            if (pad_pressed(0) & PAD_START) {
                state = ST_TITLE;
                show_title();
            }
            break;
        }

        wait_vblank();
    }
}
