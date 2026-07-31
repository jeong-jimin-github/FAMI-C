extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void ppu_off(void);
extern void ppu_on(void);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
extern void render_queue(void);
extern void ppu_write_preview(void);
/* Legacy helper name; the selector now identifies one of four 5-row chunks. */
extern void ppu_write_board_half(unsigned char quarter);
extern void music_init(void);
extern void music_pause(void);
extern void music_resume(void);
extern void sfx_play(unsigned char effect);

/* MUSIC_DATA_START */
const unsigned char MUSIC_PULSE1_BASE[77] = {
    61, 85, 85, 85, 85, 84, 89, 84, 0, 73, 73, 73, 72, 68, 72, 72,
    68, 73, 72, 72, 73, 73, 73, 75, 73, 77, 75, 73, 75, 73, 70, 73,
    73, 75, 77, 74, 79, 79, 79, 77, 79, 74, 81, 79, 77, 79, 74, 77,
    86, 82, 81, 77, 77, 82, 77, 84, 76, 74, 79, 81, 80, 87, 79, 77,
    77, 75, 79, 82, 84, 82, 84, 81, 81, 55, 58, 55, 62,
};

const unsigned char MUSIC_PULSE1_PAIR0[77] = {
    17, 17, 17, 85, 17, 17, 17, 17, 0, 17, 51, 51, 17, 102, 34, 17,
    85, 0, 68, 17, 17, 51, 51, 17, 85, 68, 17, 0, 17, 170, 68, 221,
    17, 221, 17, 0, 17, 17, 51, 102, 102, 68, 34, 17, 136, 17, 187, 136,
    17, 85, 68, 85, 102, 17, 51, 17, 68, 102, 51, 102, 51, 17, 68, 102,
    17, 17, 17, 17, 51, 85, 51, 17, 17, 209, 31, 209, 20,
};

const unsigned char MUSIC_PULSE1_PAIR1[77] = {
    17, 19, 51, 83, 17, 18, 17, 18, 0, 17, 17, 17, 17, 85, 17, 17,
    83, 17, 34, 18, 17, 49, 51, 19, 85, 66, 19, 0, 19, 170, 65, 221,
    19, 17, 17, 17, 17, 19, 49, 102, 99, 68, 34, 17, 129, 20, 187, 136,
    17, 85, 66, 81, 102, 17, 49, 17, 65, 97, 49, 17, 49, 17, 65, 97,
    22, 19, 16, 19, 17, 83, 49, 18, 18, 31, 51, 20, 68,
};

const unsigned char MUSIC_PULSE1_PAIR2[77] = {
    17, 51, 17, 51, 17, 34, 17, 34, 0, 51, 16, 16, 34, 80, 16, 17,
    51, 51, 32, 34, 16, 17, 51, 51, 17, 34, 51, 17, 51, 17, 17, 17,
    51, 17, 17, 17, 17, 51, 17, 102, 51, 68, 34, 136, 17, 68, 187, 136,
    17, 17, 34, 17, 102, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17,
    102, 51, 17, 51, 51, 51, 17, 34, 34, 51, 85, 68, 0,
};

const unsigned char MUSIC_PULSE1_PAIR3[77] = {
    17, 17, 51, 17, 17, 68, 17, 17, 0, 17, 17, 0, 17, 17, 0, 17,
    17, 17, 17, 68, 17, 51, 17, 52, 17, 17, 48, 17, 51, 17, 68, 17,
    17, 17, 17, 68, 17, 68, 51, 17, 17, 20, 33, 136, 17, 136, 20, 17,
    17, 17, 17, 133, 81, 17, 136, 17, 153, 187, 136, 17, 136, 17, 153, 187,
    136, 102, 17, 85, 17, 17, 51, 68, 17, 68, 136, 136, 0,
};

const unsigned char MUSIC_PULSE2_BASE[30] = {
    0, 58, 58, 58, 58, 58, 58, 56, 54, 56, 53, 58, 56, 51, 55, 51,
    53, 57, 48, 50, 53, 54, 51, 58, 55, 39, 55, 55, 55, 55,
};

const unsigned char MUSIC_PULSE2_PAIR0[30] = {
    0, 16, 29, 16, 208, 208, 208, 208, 209, 209, 209, 209, 243, 209, 209, 209,
    209, 226, 209, 209, 209, 209, 209, 209, 0, 209, 16, 29, 16, 208,
};

const unsigned char MUSIC_PULSE2_PAIR1[30] = {
    0, 208, 13, 208, 13, 0, 221, 221, 221, 221, 221, 221, 255, 221, 221, 221,
    221, 238, 221, 221, 221, 221, 221, 221, 0, 221, 208, 13, 208, 13,
};

const unsigned char MUSIC_PULSE2_PAIR2[30] = {
    0, 208, 208, 208, 16, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29,
    29, 209, 29, 29, 46, 29, 243, 209, 29, 29, 208, 208, 208, 16,
};

const unsigned char MUSIC_PULSE2_PAIR3[30] = {
    0, 221, 208, 16, 0, 13, 208, 208, 221, 221, 221, 221, 221, 221, 209, 209,
    209, 221, 209, 209, 226, 209, 255, 221, 209, 209, 221, 208, 16, 0,
};

const unsigned char MUSIC_TRIANGLE_BASE[47] = {
    0, 34, 30, 32, 36, 37, 30, 34, 32, 29, 30, 32, 29, 34, 32, 39,
    41, 38, 31, 33, 36, 38, 29, 29, 45, 46, 36, 43, 38, 45, 34, 31,
    29, 41, 42, 44, 41, 42, 38, 31, 39, 50, 45, 38, 33, 29, 36,
};

const unsigned char MUSIC_TRIANGLE_PAIR0[47] = {
    0, 17, 17, 17, 34, 17, 1, 17, 17, 17, 17, 17, 17, 17, 51, 17,
    17, 0, 17, 34, 17, 17, 17, 187, 34, 17, 17, 17, 17, 17, 17, 17,
    17, 17, 17, 17, 17, 17, 17, 0, 1, 102, 100, 102, 100, 51, 49,
};

const unsigned char MUSIC_TRIANGLE_PAIR1[47] = {
    0, 17, 17, 17, 34, 17, 17, 221, 221, 221, 221, 221, 221, 221, 255, 17,
    0, 17, 221, 238, 17, 17, 221, 187, 34, 17, 17, 17, 17, 17, 17, 17,
    17, 17, 17, 17, 17, 17, 0, 0, 17, 100, 68, 100, 68, 49, 17,
};

const unsigned char MUSIC_TRIANGLE_PAIR2[47] = {
    0, 17, 17, 17, 17, 17, 17, 29, 29, 29, 17, 17, 17, 17, 17, 17,
    17, 17, 17, 17, 17, 17, 34, 17, 17, 17, 17, 17, 17, 17, 17, 17,
    17, 17, 17, 17, 17, 17, 17, 17, 17, 68, 34, 68, 34, 17, 68,
};

const unsigned char MUSIC_TRIANGLE_PAIR3[47] = {
    0, 17, 17, 17, 17, 17, 17, 221, 221, 221, 221, 221, 221, 221, 221, 17,
    0, 68, 221, 221, 17, 17, 238, 221, 17, 17, 136, 17, 136, 17, 221, 221,
    221, 17, 51, 17, 102, 17, 0, 221, 17, 17, 17, 17, 17, 170, 68,
};

const unsigned char MUSIC_NOISE_PAIR0[70] = {
    0, 96, 16, 16, 96, 48, 48, 96, 52, 97, 49, 49, 49, 65, 97, 49,
    49, 96, 48, 96, 52, 48, 52, 52, 52, 96, 48, 64, 97, 49, 49, 49,
    49, 49, 49, 49, 49, 96, 48, 68, 48, 17, 49, 22, 49, 17, 97, 49,
    65, 4, 64, 52, 49, 68, 97, 53, 68, 53, 52, 49, 22, 97, 49, 49,
    49, 97, 101, 85, 100, 68,
};

const unsigned char MUSIC_NOISE_PAIR1[70] = {
    0, 17, 17, 96, 96, 17, 96, 17, 65, 33, 33, 33, 32, 65, 33, 33,
    33, 81, 81, 81, 81, 81, 81, 81, 81, 81, 81, 65, 81, 81, 81, 82,
    82, 82, 81, 82, 82, 22, 17, 65, 81, 17, 17, 17, 17, 17, 17, 17,
    17, 68, 0, 50, 68, 68, 81, 17, 68, 18, 50, 17, 17, 32, 32, 32,
    51, 17, 85, 85, 68, 68,
};

const unsigned char MUSIC_NOISE_PAIR2[70] = {
    0, 64, 16, 16, 48, 48, 48, 48, 64, 65, 65, 65, 65, 65, 49, 49,
    68, 48, 48, 64, 64, 64, 64, 64, 64, 64, 64, 64, 65, 65, 65, 65,
    65, 68, 97, 65, 68, 49, 48, 68, 68, 65, 65, 97, 17, 17, 49, 49,
    97, 68, 97, 65, 65, 68, 97, 65, 65, 65, 65, 17, 68, 65, 65, 65,
    68, 17, 85, 85, 68, 97,
};

const unsigned char MUSIC_NOISE_PAIR3[70] = {
    0, 17, 17, 96, 17, 17, 96, 68, 68, 33, 33, 36, 33, 65, 33, 33,
    65, 81, 81, 84, 81, 84, 84, 86, 68, 81, 81, 65, 81, 65, 81, 84,
    81, 84, 81, 68, 68, 96, 16, 68, 65, 17, 49, 68, 49, 17, 17, 17,
    17, 68, 81, 84, 83, 68, 81, 81, 51, 81, 68, 54, 68, 32, 32, 36,
    64, 49, 53, 85, 68, 96,
};

const unsigned char MUSIC_TUPLE_PULSE1[156] = {
    0, 1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 1, 7, 4, 1, 2,
    3, 4, 1, 5, 6, 1, 2, 7, 4, 8, 8, 8, 9, 10, 9, 11,
    12, 13, 14, 15, 16, 17, 18, 9, 11, 12, 13, 14, 9, 11, 15, 19,
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 21, 34,
    35, 36, 37, 38, 39, 36, 37, 40, 41, 42, 43, 44, 45, 46, 47, 48,
    49, 50, 51, 52, 50, 53, 8, 8, 8, 8, 8, 8, 18, 15, 19, 28,
    53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 61, 63, 61, 64, 6, 20,
    21, 22, 26, 27, 25, 65, 29, 30, 31, 32, 33, 21, 34, 34, 35, 66,
    41, 42, 46, 36, 37, 48, 50, 52, 50, 53, 53, 53, 67, 68, 69, 53,
    70, 71, 48, 67, 72, 73, 74, 73, 74, 75, 76, 8,
};

const unsigned char MUSIC_TUPLE_PULSE2[156] = {
    0, 1, 2, 3, 4, 3, 5, 1, 2, 3, 4, 1, 3, 5, 1, 2,
    3, 4, 1, 3, 5, 1, 2, 3, 5, 0, 0, 0, 6, 6, 6, 6,
    7, 7, 7, 7, 7, 6, 6, 6, 6, 7, 7, 7, 6, 6, 7, 7,
    8, 9, 10, 11, 8, 10, 11, 8, 12, 8, 8, 10, 10, 13, 13, 0,
    0, 14, 15, 16, 14, 14, 15, 16, 17, 14, 18, 19, 15, 20, 16, 21,
    15, 16, 19, 14, 22, 17, 1, 2, 3, 4, 2, 5, 6, 7, 7, 11,
    23, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 8, 8, 10, 10, 13, 13, 0, 0, 0, 24,
    17, 14, 20, 14, 15, 21, 16, 14, 25, 25, 25, 25, 26, 27, 28, 29,
    26, 28, 29, 26, 28, 0, 0, 0, 0, 0, 0, 0,
};

const unsigned char MUSIC_TUPLE_TRIANGLE[156] = {
    0, 1, 2, 3, 4, 3, 5, 1, 2, 3, 4, 1, 3, 5, 1, 6,
    3, 4, 1, 3, 4, 1, 6, 3, 4, 1, 1, 1, 7, 7, 7, 7,
    8, 8, 8, 8, 8, 7, 7, 7, 7, 8, 8, 8, 7, 7, 9, 9,
    10, 11, 12, 13, 10, 12, 13, 10, 14, 10, 10, 12, 12, 15, 15, 16,
    17, 18, 15, 12, 18, 18, 15, 12, 19, 18, 20, 21, 15, 22, 12, 10,
    15, 12, 21, 18, 23, 24, 1, 2, 3, 4, 2, 4, 7, 9, 9, 13,
    25, 26, 27, 26, 26, 28, 29, 30, 25, 31, 27, 15, 15, 32, 33, 34,
    35, 36, 25, 34, 36, 25, 37, 37, 33, 33, 15, 15, 38, 21, 0, 39,
    19, 18, 22, 18, 15, 10, 12, 18, 15, 15, 15, 15, 27, 40, 33, 24,
    27, 33, 24, 27, 33, 41, 42, 43, 44, 45, 46, 15,
};

const unsigned char MUSIC_TUPLE_NOISE[156] = {
    0, 1, 2, 2, 3, 2, 3, 4, 5, 6, 5, 5, 7, 8, 9, 10,
    10, 11, 10, 10, 10, 12, 12, 10, 13, 14, 15, 16, 17, 18, 18, 18,
    18, 18, 18, 18, 18, 19, 20, 21, 22, 21, 20, 23, 19, 20, 21, 24,
    25, 26, 26, 26, 26, 26, 26, 25, 26, 26, 26, 26, 26, 26, 26, 25,
    27, 28, 29, 30, 31, 30, 30, 30, 32, 33, 30, 32, 34, 33, 30, 35,
    30, 32, 30, 32, 28, 36, 5, 5, 5, 37, 38, 39, 18, 18, 40, 26,
    36, 41, 41, 41, 41, 41, 41, 41, 41, 41, 41, 41, 41, 42, 43, 44,
    45, 44, 45, 44, 44, 45, 46, 47, 47, 47, 46, 47, 48, 13, 49, 50,
    51, 52, 53, 54, 55, 56, 57, 58, 44, 45, 59, 60, 61, 62, 62, 63,
    62, 62, 62, 62, 64, 65, 45, 66, 67, 68, 69, 0,
};

const unsigned char MUSIC_ORDER0[256] = {
    0, 0, 1, 2, 3, 4, 1, 2, 5, 6, 7, 8, 9, 10, 11, 8,
    12, 13, 14, 15, 16, 17, 18, 15, 19, 20, 18, 15, 16, 17, 21, 22,
    23, 24, 25, 26, 26, 27, 28, 29, 30, 31, 32, 33, 32, 34, 30, 29,
    30, 31, 32, 33, 35, 36, 37, 38, 39, 40, 41, 42, 41, 43, 44, 38,
    39, 45, 41, 42, 46, 47, 48, 49, 50, 51, 52, 49, 53, 54, 55, 49,
    50, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70,
    71, 72, 65, 66, 67, 73, 74, 75, 76, 77, 65, 70, 67, 68, 69, 70,
    78, 79, 80, 81, 82, 83, 74, 75, 84, 85, 86, 87, 88, 89, 86, 90,
    88, 91, 14, 15, 16, 17, 18, 15, 23, 24, 28, 92, 30, 31, 32, 33,
    32, 34, 28, 92, 30, 31, 32, 33, 93, 94, 48, 49, 50, 51, 52, 49,
    53, 95, 55, 49, 50, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66,
    67, 68, 69, 70, 71, 72, 65, 66, 67, 73, 74, 75, 76, 77, 65, 70,
    67, 68, 69, 70, 78, 79, 80, 81, 82, 83, 74, 75, 84, 96, 97, 98,
    99, 98, 100, 98, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112,
    113, 114, 115, 112, 116, 114, 115, 112, 113, 117, 118, 119, 120, 121, 122, 123,
    124, 125, 126, 127, 66, 67, 68, 69, 70, 71, 128, 65, 66, 67, 129, 74,
};

const unsigned char MUSIC_ORDER1[50] = {
    75, 76, 130, 131, 70, 67, 68, 69, 132, 78, 133, 80, 134, 82, 135, 74,
    75, 136, 137, 138, 139, 140, 141, 142, 143, 144, 141, 145, 146, 140, 141, 142,
    143, 147, 141, 148, 149, 150, 151, 152, 153, 154, 155, 155, 155, 155, 155, 155,
    155, 155,
};
/* MUSIC_DATA_END */

#define BOARD_W 10
#define BOARD_H 20
#define BOARD_SIZE 200
#define BOARD_X 10
#define BOARD_Y 4

#define STATE_TITLE 0
#define STATE_PLAYING 1
#define STATE_PAUSED 2
#define STATE_GAMEOVER 3
#define STATE_ENTRY 4

#define STATUS_NONE 0
#define STATUS_HELP 1
#define STATUS_PAUSED 2
#define STATUS_GAMEOVER 3
#define STATUS_LEVEL 4
#define STATUS_NAME 5

#define PAD_A 128
#define PAD_B 64
#define PAD_START 16
#define PAD_UP 8
#define PAD_DOWN 4
#define PAD_LEFT 2
#define PAD_RIGHT 1

#define DAS_DELAY 12
#define DAS_REPEAT 3
#define LOCK_DELAY 18

/* Level select spans the ten single-digit levels plus a second row of ten. */
#define MAX_LEVEL_PICK 19

#define HI_COUNT 3
#define NAME_LEN 3
#define HI_NAME_SIZE 9
#define HI_SCORE_SIZE 18
#define LAST_LETTER 26

#define TILE_DIGIT0 16
#define TILE_LETTER_A 26
#define TILE_FRAME_TL 54
#define TILE_FRAME_TOP 55
#define TILE_FRAME_TR 56
#define TILE_FRAME_LEFT 57
#define TILE_FRAME_RIGHT 58
#define TILE_FRAME_BL 59
#define TILE_FRAME_BOTTOM 60
#define TILE_FRAME_BR 61
#define TILE_SPARKLE 62
#define TILE_FLASH 63
#define TILE_LOGO 64
#define TILE_ARROW_LEFT 88
#define TILE_ARROW_RIGHT 89
#define TILE_CARET 90
#define TILE_SLOT 91

/* Sound-effect slots; slot zero is reserved by the driver as "stop". */
#define SFX_MOVE 1
#define SFX_ROTATE 2
#define SFX_SOFT 3
#define SFX_LAND 4
#define SFX_DROP 5
#define SFX_LINE 6
#define SFX_TETRIS 7
#define SFX_LEVELUP 8
#define SFX_GAMEOVER 9
#define SFX_MENU 10
#define SFX_CONFIRM 11

/* String ids into TEXT_DATA.  The first eight are exactly eight tiles wide so
 * a status line always overwrites whatever the previous message left behind. */
#define TXT_ROT 0
#define TXT_UP_DROP 1
#define TXT_DN_SOFT 2
#define TXT_PAUSED 3
#define TXT_GAME 4
#define TXT_OVER 5
#define TXT_START 6
#define TXT_BLANK 7
#define TXT_PRESS_START 8
#define TXT_START_LEVEL 9
#define TXT_BEST_PLAYERS 10
#define TXT_SCORE 11
#define TXT_LINES 12
#define TXT_LEVEL 13
#define TXT_NEXT 14
#define TXT_TOP 15
#define TXT_NEW_RECORD 16
#define TXT_ENTER_NAME 17
#define TXT_TETRIS 18
#define TXT_FAMI_C 19
#define TXT_RANK 20
#define TXT_UD_LETTER 21
#define TXT_LR_MOVE 22
#define TXT_START_OK 23
#define TXT_A_CW_B_CCW 24
#define TXT_HARD_DROP 25
#define TXT_SOFT_DROP 26
#define TXT_LR_UD 27

const unsigned char MASKS[4] = { 8, 4, 2, 1 };

/* The next-piece box is four rows tall; three-wide pieces drop one row so they
 * sit level with the I and O previews. */
const unsigned char PREVIEW_SHIFT[7] = { 0, 0, 1, 1, 1, 1, 1 };

/* Rotation kicks, tried in order: in place, one left, one right, two left, two
 * right.  The two-cell kicks are what let a vertical I leave either wall. */
const unsigned char KICKS[5] = { 0, 255, 1, 254, 2 };

const unsigned char GAME_ATTRIBUTES[64] = {
    95, 95, 31, 15, 15, 175, 175, 175,
    85, 85, 17, 0, 0, 170, 170, 170,
    85, 85, 17, 0, 0, 170, 170, 170,
    85, 85, 17, 0, 0, 170, 170, 170,
    85, 85, 17, 0, 0, 170, 170, 170,
    85, 85, 17, 0, 0, 170, 170, 170,
    85, 85, 17, 0, 0, 170, 170, 170,
    0, 0, 0, 0, 0, 0, 0, 0
};

/* Menu screens use one background palette per eight tile rows: the logo band,
 * the level picker, the best-player table, and the footer.  Panels are laid
 * out inside a single band so a frame never changes colour halfway down.
 * Glyph ink is colour 3 in every palette, so text is free to sit anywhere. */
const unsigned char MENU_ATTRIBUTES[64] = {
    255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255,
    170, 170, 170, 170, 170, 170, 170, 170,
    170, 170, 170, 170, 170, 170, 170, 170,
    85, 85, 85, 85, 85, 85, 85, 85,
    85, 85, 85, 85, 85, 85, 85, 85,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0
};

/* Four rows of four cells per rotation, one nibble per row, MSB is column 0.
 * Every state is a true rotation of state zero about a fixed centre, so a
 * rotation never mirrors a piece and never nudges it off its pivot.  I, S and
 * Z use the classic two-state cycle; T, J and L use all four. */
const unsigned char SHAPES[112] = {
    /* I */
     0, 15,  0,  0,
     2,  2,  2,  2,
     0, 15,  0,  0,
     2,  2,  2,  2,

    /* O */
     0,  6,  6,  0,
     0,  6,  6,  0,
     0,  6,  6,  0,
     0,  6,  6,  0,

    /* T */
     4, 14,  0,  0,
     4,  6,  4,  0,
     0, 14,  4,  0,
     4, 12,  4,  0,

    /* Z */
    12,  6,  0,  0,
     2,  6,  4,  0,
    12,  6,  0,  0,
     2,  6,  4,  0,

    /* S */
     6, 12,  0,  0,
     4,  6,  2,  0,
     6, 12,  0,  0,
     4,  6,  2,  0,

    /* J */
    14,  2,  0,  0,
     2,  2,  6,  0,
     0,  8, 14,  0,
    12,  8,  8,  0,

    /* L */
    14,  8,  0,  0,
     6,  2,  2,  0,
     0,  2, 14,  0,
     8,  8, 12,  0,
};

const unsigned char GRAVITY[30] = {
    48, 43, 38, 33, 28, 23, 18, 13, 8, 6,
    5, 5, 5, 4, 4, 4, 3, 3, 3, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 1
};

/* Tile ids for every on-screen string, packed end to end. */
const unsigned char TEXT_DATA[227] = {
    26, 52, 27, 0, 43, 40, 45, 0, 46, 41, 0, 29, 43, 40, 41, 0,
    29, 39, 0, 44, 40, 31, 45, 0, 0, 41, 26, 46, 44, 30, 29, 0,
    0, 0, 32, 26, 38, 30, 0, 0, 0, 0, 40, 47, 30, 43, 0, 0,
    52, 44, 45, 26, 43, 45, 52, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    41, 43, 30, 44, 44, 0, 44, 45, 26, 43, 45, 44, 45, 26, 43, 45,
    0, 37, 30, 47, 30, 37, 27, 30, 44, 45, 0, 41, 37, 26, 50, 30,
    43, 44, 44, 28, 40, 43, 30, 37, 34, 39, 30, 44, 37, 30, 47, 30,
    37, 39, 30, 49, 45, 45, 40, 41, 39, 30, 48, 0, 43, 30, 28, 40,
    43, 29, 30, 39, 45, 30, 43, 0, 39, 26, 38, 30, 45, 30, 45, 43,
    34, 44, 31, 26, 38, 34, 52, 28, 43, 26, 39, 36, 46, 29, 0, 37,
    30, 45, 45, 30, 43, 37, 43, 0, 38, 40, 47, 30, 44, 45, 26, 43,
    45, 0, 40, 36, 26, 52, 28, 48, 0, 0, 27, 52, 28, 28, 48, 46,
    41, 0, 33, 26, 43, 29, 0, 29, 43, 40, 41, 29, 40, 48, 39, 0,
    44, 40, 31, 45, 0, 29, 43, 40, 41, 37, 43, 52, 17, 0, 0, 46,
    29, 52, 21,
};

const unsigned char TEXT_START[28] = {
    0, 8, 16, 24, 32, 40, 48, 56, 64, 75, 86, 98, 103, 108, 113, 117,
    120, 130, 140, 146, 152, 156, 165, 172, 180, 191, 203, 217,
};

const unsigned char TEXT_LEN[28] = {
    8, 8, 8, 8, 8, 8, 8, 8, 11, 11, 12, 5, 5, 5, 4, 3,
    10, 10, 6, 6, 4, 9, 7, 8, 11, 12, 14, 10,
};

/* Sound effects: SFX_START/SFX_LENGTH locate a run of one-frame steps inside
 * the SFX_CTRL/SFX_TIMER_LO/SFX_TIMER_HI tables.  The driver replays those
 * steps on pulse 2 and hands the channel back to the song afterwards. */
const unsigned char SFX_START[16] = {
    0, 0, 2, 5, 6, 10, 16, 25, 41, 49, 71, 73, 0, 0, 0, 0,
};

const unsigned char SFX_LENGTH[16] = {
    0, 2, 3, 1, 4, 6, 9, 16, 8, 22, 2, 6, 0, 0, 0, 0,
};

const unsigned char SFX_CTRL[79] = {
    179, 179, 117, 117, 117, 50, 54, 54, 54, 54, 120, 120, 120, 120, 120, 120,
    184, 184, 184, 184, 184, 184, 184, 184, 184, 185, 185, 185, 185, 185, 185, 185,
    185, 185, 185, 185, 185, 185, 185, 185, 185, 248, 248, 248, 248, 248, 248, 248,
    248, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 244, 244, 182, 182, 182, 182, 182, 182,
};

const unsigned char SFX_TIMER_LO[79] = {
    28, 28, 213, 142, 142, 58, 223, 126, 85, 85, 126, 169, 225, 45, 170, 170,
    213, 213, 169, 169, 142, 142, 106, 106, 106, 213, 213, 169, 169, 142, 142, 106,
    106, 142, 142, 106, 106, 84, 84, 84, 84, 169, 169, 126, 126, 84, 84, 84,
    84, 253, 253, 253, 28, 28, 28, 64, 64, 64, 123, 123, 123, 196, 196, 196,
    196, 58, 58, 58, 58, 58, 58, 112, 112, 169, 169, 112, 112, 112, 112,
};

const unsigned char SFX_TIMER_HI[79] = {
    1, 1, 0, 0, 0, 2, 1, 2, 3, 3, 0, 0, 0, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0,
};

/* Letters are stored as 0 for blank and 1..26 for A..Z. */
const unsigned char DEFAULT_NAMES[9] = {
    6, 13, 3,
    14, 5, 19,
    20, 15, 16
};

/* Six digits per entry, least significant first: 010000, 005000, 002500. */
const unsigned char DEFAULT_SCORES[18] = {
    0, 0, 0, 0, 1, 0,
    0, 0, 0, 5, 0, 0,
    0, 0, 5, 2, 0, 0
};

unsigned char board[BOARD_SIZE];
unsigned char bag[7];
unsigned char bag_pos;
unsigned char next_piece;

unsigned char score_digits[6];
unsigned char line_digits[3];
unsigned char level;
unsigned char start_level;
unsigned char level_up;

unsigned char game_state;
unsigned char status_action;
unsigned char pad;
unsigned char prev_pad;

unsigned char piece_x;
unsigned char piece_y;
unsigned char piece_t;
unsigned char piece_r;
unsigned char old_piece_x;
unsigned char old_piece_y;
unsigned char old_piece_r;
unsigned char piece_dirty;
unsigned char lock_pending;
unsigned char drop_tick;
unsigned char lock_tick;
unsigned char das_direction;
unsigned char das_tick;

unsigned char erase_x[4];
unsigned char erase_y[4];
unsigned char draw_x[4];
unsigned char draw_y[4];
unsigned char erase_count;
unsigned char draw_count;
unsigned char preview_tiles[16];

unsigned char clear_rows[4];
unsigned char clear_count;

unsigned char hi_name[HI_NAME_SIZE];
unsigned char hi_score[HI_SCORE_SIZE];
unsigned char entry_name[NAME_LEN];
unsigned char entry_pos;
unsigned char entry_rank;

unsigned char shape_cell(unsigned char t, unsigned char r, unsigned char x, unsigned char y)
{
    unsigned char row;
    row = SHAPES[((t * 4) + r) * 4 + y];
    return row & MASKS[x];
}

unsigned char letter_tile(unsigned char c)
{
    if (c == 0) {
        return 0;
    }
    return TILE_LETTER_A - 1 + c;
}

/* Safe only while rendering is disabled: no vblank budget is respected. */
void draw_text(unsigned char x, unsigned char y, unsigned char id)
{
    unsigned char i;
    unsigned char base;
    unsigned char count;

    base = TEXT_START[id];
    count = TEXT_LEN[id];
    i = 0;
    while (i < count) {
        ppu_put(x + i, y, TEXT_DATA[base + i]);
        i = i + 1;
    }
}

void clear_screen_off(void)
{
    unsigned char x;
    unsigned char y;

    y = 0;
    while (y < 30) {
        x = 0;
        while (x < 32) {
            ppu_put(x, y, 0);
            x = x + 1;
        }
        y = y + 1;
    }
}

void draw_box_off(unsigned char x0, unsigned char y0, unsigned char x1, unsigned char y1)
{
    unsigned char x;
    unsigned char y;

    ppu_put(x0, y0, TILE_FRAME_TL);
    ppu_put(x1, y0, TILE_FRAME_TR);
    ppu_put(x0, y1, TILE_FRAME_BL);
    ppu_put(x1, y1, TILE_FRAME_BR);

    x = x0 + 1;
    while (x < x1) {
        ppu_put(x, y0, TILE_FRAME_TOP);
        ppu_put(x, y1, TILE_FRAME_BOTTOM);
        x = x + 1;
    }

    y = y0 + 1;
    while (y < y1) {
        ppu_put(x0, y, TILE_FRAME_LEFT);
        ppu_put(x1, y, TILE_FRAME_RIGHT);
        y = y + 1;
    }
}

void draw_menu_attributes_off(void)
{
    unsigned char i;
    i = 0;
    while (i < 32) {
        ppu_put(i, 30, MENU_ATTRIBUTES[i]);
        ppu_put(i, 31, MENU_ATTRIBUTES[32 + i]);
        i = i + 1;
    }
}

void draw_game_attributes_off(void)
{
    unsigned char i;
    i = 0;
    while (i < 32) {
        ppu_put(i, 30, GAME_ATTRIBUTES[i]);
        ppu_put(i, 31, GAME_ATTRIBUTES[32 + i]);
        i = i + 1;
    }
}

void draw_logo_off(void)
{
    unsigned char letter;
    unsigned char tile;
    unsigned char x;

    letter = 0;
    while (letter < 6) {
        tile = TILE_LOGO + (letter * 4);
        x = 10 + (letter * 2);
        ppu_put(x, 2, tile);
        ppu_put(x + 1, 2, tile + 1);
        ppu_put(x, 3, tile + 2);
        ppu_put(x + 1, 3, tile + 3);
        letter = letter + 1;
    }
}

/* One eight-tile status line, split across two vblanks so the writes always
 * finish before rendering resumes. */
void draw_status_line(unsigned char y, unsigned char id)
{
    unsigned char i;
    unsigned char base;

    base = TEXT_START[id];
    wait_vblank();
    i = 0;
    while (i < 4) {
        ppu_put(22 + i, y, TEXT_DATA[base + i]);
        i = i + 1;
    }
    wait_vblank();
    while (i < 8) {
        ppu_put(22 + i, y, TEXT_DATA[base + i]);
        i = i + 1;
    }
}

void draw_help(void)
{
    draw_status_line(20, TXT_ROT);
    draw_status_line(21, TXT_UP_DROP);
    draw_status_line(22, TXT_DN_SOFT);
}

void draw_status_paused(void)
{
    draw_status_line(20, TXT_BLANK);
    draw_status_line(21, TXT_PAUSED);
    draw_status_line(22, TXT_BLANK);
}

void draw_status_gameover(void)
{
    draw_status_line(20, TXT_GAME);
    draw_status_line(21, TXT_OVER);
    draw_status_line(22, TXT_START);
}

void draw_score_at(unsigned char x, unsigned char y)
{
    unsigned char i;
    i = 0;
    while (i < 6) {
        ppu_put(x + i, y, TILE_DIGIT0 + score_digits[5 - i]);
        i = i + 1;
    }
}

void draw_top_value(void)
{
    unsigned char i;
    i = 0;
    while (i < 6) {
        ppu_put(22 + i, 16, TILE_DIGIT0 + hi_score[5 - i]);
        i = i + 1;
    }
}

void draw_hi_row(unsigned char slot, unsigned char y)
{
    unsigned char i;
    unsigned char base;

    ppu_put(8, y, TILE_DIGIT0 + 1 + slot);
    base = slot * NAME_LEN;
    i = 0;
    while (i < NAME_LEN) {
        ppu_put(11 + i, y, letter_tile(hi_name[base + i]));
        i = i + 1;
    }
    base = slot * 6;
    i = 0;
    while (i < 6) {
        ppu_put(16 + i, y, TILE_DIGIT0 + hi_score[base + 5 - i]);
        i = i + 1;
    }
}

void draw_level_pick(void)
{
    ppu_put(15, 11, TILE_DIGIT0 + (start_level / 10));
    ppu_put(16, 11, TILE_DIGIT0 + (start_level % 10));
}

void init_high_scores(void)
{
    unsigned char i;

    i = 0;
    while (i < HI_NAME_SIZE) {
        hi_name[i] = DEFAULT_NAMES[i];
        i = i + 1;
    }
    i = 0;
    while (i < HI_SCORE_SIZE) {
        hi_score[i] = DEFAULT_SCORES[i];
        i = i + 1;
    }
}

void show_title(void)
{
    wait_vblank();
    ppu_off();
    clear_screen_off();
    draw_menu_attributes_off();
    draw_logo_off();
    draw_text(13, 5, TXT_FAMI_C);

    draw_box_off(4, 8, 27, 13);
    draw_text(10, 9, TXT_START_LEVEL);
    ppu_put(13, 11, TILE_ARROW_LEFT);
    ppu_put(18, 11, TILE_ARROW_RIGHT);
    draw_level_pick();
    draw_text(11, 12, TXT_LR_UD);

    draw_box_off(4, 16, 27, 21);
    draw_text(10, 17, TXT_BEST_PLAYERS);
    draw_hi_row(0, 18);
    draw_hi_row(1, 19);
    draw_hi_row(2, 20);

    draw_text(10, 23, TXT_PRESS_START);
    draw_text(10, 25, TXT_A_CW_B_CCW);
    draw_text(10, 26, TXT_HARD_DROP);
    draw_text(9, 27, TXT_SOFT_DROP);

    ppu_put(6, 9, TILE_SPARKLE);
    ppu_put(25, 9, TILE_SPARKLE);
    ppu_put(6, 17, TILE_SPARKLE);
    ppu_put(25, 17, TILE_SPARKLE);

    game_state = STATE_TITLE;
    status_action = STATUS_NONE;
    wait_vblank();
    ppu_on();
}

void draw_entry_letters(void)
{
    unsigned char i;

    wait_vblank();
    i = 0;
    while (i < NAME_LEN) {
        ppu_put(13 + (i * 2), 18, letter_tile(entry_name[i]));
        i = i + 1;
    }
    wait_vblank();
    i = 0;
    while (i < NAME_LEN) {
        ppu_put(13 + (i * 2), 19, TILE_SLOT);
        i = i + 1;
    }
    ppu_put(13 + (entry_pos * 2), 19, TILE_CARET);
}

void reset_entry_name(void)
{
    unsigned char i;
    i = 0;
    while (i < NAME_LEN) {
        entry_name[i] = 1;
        i = i + 1;
    }
    entry_pos = 0;
}

void show_name_entry(void)
{
    reset_entry_name();

    wait_vblank();
    ppu_off();
    clear_screen_off();
    draw_menu_attributes_off();

    draw_box_off(4, 2, 27, 7);
    draw_text(11, 3, TXT_NEW_RECORD);
    draw_text(11, 5, TXT_RANK);
    ppu_put(17, 5, TILE_DIGIT0 + 1 + entry_rank);
    draw_text(11, 6, TXT_SCORE);
    draw_score_at(17, 6);
    ppu_put(6, 3, TILE_SPARKLE);
    ppu_put(25, 3, TILE_SPARKLE);

    draw_text(11, 13, TXT_ENTER_NAME);

    draw_box_off(10, 16, 21, 21);
    draw_text(11, 23, TXT_UD_LETTER);
    draw_text(12, 24, TXT_LR_MOVE);
    draw_text(12, 25, TXT_START_OK);

    game_state = STATE_ENTRY;
    status_action = STATUS_NONE;
    draw_entry_letters();
    wait_vblank();
    ppu_on();
}

void clear_board(void)
{
    unsigned char i;
    i = 0;
    while (i < BOARD_SIZE) {
        board[i] = 0;
        i = i + 1;
    }
}

void clear_score(void)
{
    unsigned char i;
    i = 0;
    while (i < 6) {
        score_digits[i] = 0;
        i = i + 1;
    }
    i = 0;
    while (i < 3) {
        line_digits[i] = 0;
        i = i + 1;
    }
    level = 0;
    level_up = 0;
}

void draw_frame_off(void)
{
    draw_box_off(9, 3, 20, 24);
}

/* Every panel leaves a blank row between it and its neighbour so the rails
 * read as separate boxes instead of one doubled line. */
void draw_game_panels_off(void)
{
    draw_box_off(0, 3, 8, 8);
    draw_box_off(0, 10, 8, 14);
    draw_box_off(0, 16, 8, 20);
    draw_box_off(21, 3, 30, 11);
    draw_box_off(21, 13, 30, 17);
    draw_box_off(21, 19, 30, 24);
}

void draw_board_off(void)
{
    unsigned char x;
    unsigned char y;

    y = 0;
    while (y < BOARD_H) {
        x = 0;
        while (x < BOARD_W) {
            ppu_put(BOARD_X + x, BOARD_Y + y, board[(y * BOARD_W) + x]);
            x = x + 1;
        }
        y = y + 1;
    }
}

void draw_board(void)
{
    /* Five rows per vblank remain safe even when a full BGM step decodes. */
    wait_vblank();
    ppu_write_board_half(3);
    wait_vblank();
    ppu_write_board_half(2);
    wait_vblank();
    ppu_write_board_half(1);
    wait_vblank();
    ppu_write_board_half(0);
}

void draw_score_values(void)
{
    ppu_put(1, 7, TILE_DIGIT0 + score_digits[5]);
    ppu_put(2, 7, TILE_DIGIT0 + score_digits[4]);
    ppu_put(3, 7, TILE_DIGIT0 + score_digits[3]);
    ppu_put(4, 7, TILE_DIGIT0 + score_digits[2]);
    ppu_put(5, 7, TILE_DIGIT0 + score_digits[1]);
    ppu_put(6, 7, TILE_DIGIT0 + score_digits[0]);

    ppu_put(3, 13, TILE_DIGIT0 + line_digits[2]);
    ppu_put(4, 13, TILE_DIGIT0 + line_digits[1]);
    ppu_put(5, 13, TILE_DIGIT0 + line_digits[0]);

    ppu_put(3, 19, TILE_DIGIT0 + (level / 10));
    ppu_put(4, 19, TILE_DIGIT0 + (level % 10));
}

void draw_static_game_ui(void)
{
    draw_text(12, 1, TXT_TETRIS);
    draw_text(1, 5, TXT_SCORE);
    draw_text(1, 11, TXT_LINES);
    draw_text(1, 17, TXT_LEVEL);
    draw_text(23, 5, TXT_NEXT);
    draw_text(23, 14, TXT_TOP);
    draw_top_value();
    draw_score_values();
    draw_help();
}

void refill_bag(void)
{
    unsigned char i;
    unsigned char j;
    unsigned char temp;

    i = 0;
    while (i < 7) {
        bag[i] = i;
        i = i + 1;
    }

    i = 6;
    while (i > 0) {
        j = rand8() % (i + 1);
        temp = bag[i];
        bag[i] = bag[j];
        bag[j] = temp;
        i = i - 1;
    }
    bag_pos = 0;
}

unsigned char take_bag_piece(void)
{
    unsigned char result;
    if (bag_pos >= 7) {
        refill_bag();
    }
    result = bag[bag_pos];
    bag_pos = bag_pos + 1;
    return result;
}

unsigned char collides(unsigned char nx, unsigned char ny, unsigned char nr)
{
    unsigned char x;
    unsigned char y;
    unsigned char bx;
    unsigned char by;

    y = 0;
    while (y < 4) {
        x = 0;
        while (x < 4) {
            if (shape_cell(piece_t, nr, x, y)) {
                bx = nx + x;
                by = ny + y;
                if (bx >= BOARD_W) {
                    return 1;
                }
                if (by >= BOARD_H) {
                    return 1;
                }
                if (board[(by * BOARD_W) + bx]) {
                    return 1;
                }
            }
            x = x + 1;
        }
        y = y + 1;
    }
    return 0;
}

void capture_erase_at(unsigned char t, unsigned char r, unsigned char px, unsigned char py)
{
    unsigned char x;
    unsigned char y;

    erase_count = 0;
    y = 0;
    while (y < 4) {
        x = 0;
        while (x < 4) {
            if (shape_cell(t, r, x, y)) {
                erase_x[erase_count] = BOARD_X + px + x;
                erase_y[erase_count] = BOARD_Y + py + y;
                erase_count = erase_count + 1;
            }
            x = x + 1;
        }
        y = y + 1;
    }
}

void capture_draw_current(void)
{
    unsigned char x;
    unsigned char y;

    draw_count = 0;
    y = 0;
    while (y < 4) {
        x = 0;
        while (x < 4) {
            if (shape_cell(piece_t, piece_r, x, y)) {
                draw_x[draw_count] = BOARD_X + piece_x + x;
                draw_y[draw_count] = BOARD_Y + piece_y + y;
                draw_count = draw_count + 1;
            }
            x = x + 1;
        }
        y = y + 1;
    }
}

void mark_dirty(void)
{
    if (!piece_dirty) {
        old_piece_x = piece_x;
        old_piece_y = piece_y;
        old_piece_r = piece_r;
        piece_dirty = 1;
    }
}

void build_next_preview(void)
{
    unsigned char x;
    unsigned char y;
    unsigned char preview_y;

    y = 0;
    while (y < 4) {
        x = 0;
        while (x < 4) {
            preview_tiles[(y * 4) + x] = 0;
            x = x + 1;
        }
        y = y + 1;
    }

    y = 0;
    while (y < 4) {
        x = 0;
        while (x < 4) {
            if (shape_cell(next_piece, 0, x, y)) {
                preview_y = y + PREVIEW_SHIFT[next_piece];
                preview_tiles[(preview_y * 4) + x] = next_piece + 1;
            }
            x = x + 1;
        }
        y = y + 1;
    }
}

void draw_next_preview_off(void)
{
    build_next_preview();
    ppu_write_preview();
}

void draw_next_preview(void)
{
    build_next_preview();
    wait_vblank();
    ppu_write_preview();
}

void spawn_piece(void)
{
    piece_t = next_piece;
    next_piece = take_bag_piece();
    piece_r = 0;
    piece_x = 3;
    piece_y = 0;
    drop_tick = 0;
    lock_tick = 0;
    das_direction = 0;
    das_tick = 0;
    piece_dirty = 0;
    lock_pending = 0;
    erase_count = 0;
    draw_count = 0;

    if (collides(piece_x, piece_y, piece_r)) {
        game_state = STATE_GAMEOVER;
    }
}

void start_game(void)
{
    wait_vblank();
    ppu_off();
    clear_screen_off();
    clear_board();
    clear_score();
    level = start_level;
    refill_bag();
    next_piece = take_bag_piece();
    game_state = STATE_PLAYING;
    status_action = STATUS_NONE;
    erase_count = 0;
    draw_count = 0;
    clear_count = 0;
    spawn_piece();
    draw_game_attributes_off();
    draw_frame_off();
    draw_game_panels_off();
    draw_board_off();
    draw_static_game_ui();
    draw_next_preview_off();
    capture_draw_current();
    render_queue();
    wait_vblank();
    ppu_on();
}

void try_move_left(void)
{
    /* 255 and 254 act as -1 and -2 for padded 4x4 shapes. */
    if (!collides(piece_x - 1, piece_y, piece_r)) {
        mark_dirty();
        piece_x = piece_x - 1;
        lock_tick = 0;
        sfx_play(SFX_MOVE);
    }
}

void try_move_right(void)
{
    if (!collides(piece_x + 1, piece_y, piece_r)) {
        mark_dirty();
        piece_x = piece_x + 1;
        lock_tick = 0;
        sfx_play(SFX_MOVE);
    }
}

void try_rotate(unsigned char nr)
{
    unsigned char i;
    unsigned char nx;

    i = 0;
    while (i < 5) {
        nx = piece_x + KICKS[i];
        if (!collides(nx, piece_y, nr)) {
            mark_dirty();
            piece_x = nx;
            piece_r = nr;
            lock_tick = 0;
            sfx_play(SFX_ROTATE);
            return;
        }
        i = i + 1;
    }
}

void rotate_cw(void)
{
    unsigned char nr;
    nr = piece_r + 1;
    if (nr >= 4) {
        nr = 0;
    }
    try_rotate(nr);
}

void rotate_ccw(void)
{
    unsigned char nr;
    if (piece_r == 0) {
        nr = 3;
    } else {
        nr = piece_r - 1;
    }
    try_rotate(nr);
}

void handle_horizontal(void)
{
    if (pad & PAD_LEFT) {
        if (!(prev_pad & PAD_LEFT) || das_direction != 1) {
            das_direction = 1;
            das_tick = 0;
            try_move_left();
        } else {
            das_tick = das_tick + 1;
            if (das_tick >= DAS_DELAY) {
                try_move_left();
                das_tick = DAS_DELAY - DAS_REPEAT;
            }
        }
    } else if (pad & PAD_RIGHT) {
        if (!(prev_pad & PAD_RIGHT) || das_direction != 2) {
            das_direction = 2;
            das_tick = 0;
            try_move_right();
        } else {
            das_tick = das_tick + 1;
            if (das_tick >= DAS_DELAY) {
                try_move_right();
                das_tick = DAS_DELAY - DAS_REPEAT;
            }
        }
    } else {
        das_direction = 0;
        das_tick = 0;
    }
}

void hard_drop(void)
{
    mark_dirty();
    while (!collides(piece_x, piece_y + 1, piece_r)) {
        piece_y = piece_y + 1;
    }
    lock_pending = 1;
    lock_tick = 0;
    sfx_play(SFX_DROP);
}

unsigned char gravity_delay(void)
{
    if (level < 30) {
        return GRAVITY[level];
    }
    return 1;
}

void tick_playing(void)
{
    unsigned char fall_now;
    unsigned char did_hard_drop;

    piece_dirty = 0;
    lock_pending = 0;

    if ((pad & PAD_START) && !(prev_pad & PAD_START)) {
        game_state = STATE_PAUSED;
        status_action = STATUS_PAUSED;
        /* Park the song first so the menu blip is the only thing left on the
         * APU while the game is held. */
        music_pause();
        sfx_play(SFX_MENU);
        return;
    }

    handle_horizontal();

    if ((pad & PAD_A) && !(prev_pad & PAD_A)) {
        rotate_cw();
    } else if ((pad & PAD_B) && !(prev_pad & PAD_B)) {
        rotate_ccw();
    }

    did_hard_drop = 0;
    if ((pad & PAD_UP) && !(prev_pad & PAD_UP)) {
        hard_drop();
        did_hard_drop = 1;
    }

    if (!did_hard_drop) {
        if ((pad & PAD_DOWN) && !(prev_pad & PAD_DOWN)) {
            sfx_play(SFX_SOFT);
        }

        fall_now = 0;
        drop_tick = drop_tick + 1;
        if (pad & PAD_DOWN) {
            if (drop_tick >= 2) {
                fall_now = 1;
            }
        } else {
            if (drop_tick >= gravity_delay()) {
                fall_now = 1;
            }
        }

        if (fall_now) {
            drop_tick = 0;
            if (!collides(piece_x, piece_y + 1, piece_r)) {
                mark_dirty();
                piece_y = piece_y + 1;
                lock_tick = 0;
            }
        }

        if (collides(piece_x, piece_y + 1, piece_r)) {
            lock_tick = lock_tick + 1;
            if (lock_tick >= LOCK_DELAY) {
                mark_dirty();
                lock_pending = 1;
            }
        } else {
            lock_tick = 0;
        }
    }

    if (piece_dirty) {
        capture_erase_at(piece_t, old_piece_r, old_piece_x, old_piece_y);
        capture_draw_current();
    }
}

void tick_paused(void)
{
    if ((pad & PAD_START) && !(prev_pad & PAD_START)) {
        game_state = STATE_PLAYING;
        status_action = STATUS_HELP;
        /* The song picks up on the step it was parked on. */
        music_resume();
        sfx_play(SFX_MENU);
    }
}

void tick_title(void)
{
    unsigned char moved;

    moved = 0;
    if ((pad & PAD_RIGHT) && !(prev_pad & PAD_RIGHT)) {
        if (start_level < MAX_LEVEL_PICK) {
            start_level = start_level + 1;
        } else {
            start_level = 0;
        }
        moved = 1;
    } else if ((pad & PAD_LEFT) && !(prev_pad & PAD_LEFT)) {
        if (start_level > 0) {
            start_level = start_level - 1;
        } else {
            start_level = MAX_LEVEL_PICK;
        }
        moved = 1;
    } else if ((pad & PAD_UP) && !(prev_pad & PAD_UP)) {
        if (start_level < 15) {
            start_level = start_level + 5;
        } else {
            start_level = start_level - 15;
        }
        moved = 1;
    } else if ((pad & PAD_DOWN) && !(prev_pad & PAD_DOWN)) {
        if (start_level >= 5) {
            start_level = start_level - 5;
        } else {
            start_level = start_level + 15;
        }
        moved = 1;
    }

    if (moved) {
        status_action = STATUS_LEVEL;
        sfx_play(SFX_MENU);
        return;
    }

    if ((pad & PAD_START) && !(prev_pad & PAD_START)) {
        sfx_play(SFX_CONFIRM);
        start_game();
    }
}

unsigned char score_beats(unsigned char slot)
{
    unsigned char i;
    unsigned char base;

    base = slot * 6;
    i = 6;
    while (i > 0) {
        i = i - 1;
        if (score_digits[i] > hi_score[base + i]) {
            return 1;
        }
        if (score_digits[i] < hi_score[base + i]) {
            return 0;
        }
    }
    return 0;
}

unsigned char find_rank(void)
{
    unsigned char i;
    i = 0;
    while (i < HI_COUNT) {
        if (score_beats(i)) {
            return i;
        }
        i = i + 1;
    }
    return HI_COUNT;
}

void insert_high_score(void)
{
    unsigned char i;
    unsigned char j;

    i = HI_COUNT - 1;
    while (i > entry_rank) {
        j = 0;
        while (j < NAME_LEN) {
            hi_name[(i * NAME_LEN) + j] = hi_name[((i - 1) * NAME_LEN) + j];
            j = j + 1;
        }
        j = 0;
        while (j < 6) {
            hi_score[(i * 6) + j] = hi_score[((i - 1) * 6) + j];
            j = j + 1;
        }
        i = i - 1;
    }

    j = 0;
    while (j < NAME_LEN) {
        hi_name[(entry_rank * NAME_LEN) + j] = entry_name[j];
        j = j + 1;
    }
    j = 0;
    while (j < 6) {
        hi_score[(entry_rank * 6) + j] = score_digits[j];
        j = j + 1;
    }
}

void tick_entry(void)
{
    unsigned char moved;
    unsigned char c;

    moved = 0;
    if ((pad & PAD_UP) && !(prev_pad & PAD_UP)) {
        c = entry_name[entry_pos];
        if (c >= LAST_LETTER) {
            c = 0;
        } else {
            c = c + 1;
        }
        entry_name[entry_pos] = c;
        moved = 1;
    } else if ((pad & PAD_DOWN) && !(prev_pad & PAD_DOWN)) {
        c = entry_name[entry_pos];
        if (c == 0) {
            c = LAST_LETTER;
        } else {
            c = c - 1;
        }
        entry_name[entry_pos] = c;
        moved = 1;
    } else if ((pad & PAD_RIGHT) && !(prev_pad & PAD_RIGHT)) {
        if (entry_pos < 2) {
            entry_pos = entry_pos + 1;
        } else {
            entry_pos = 0;
        }
        moved = 1;
    } else if ((pad & PAD_LEFT) && !(prev_pad & PAD_LEFT)) {
        if (entry_pos > 0) {
            entry_pos = entry_pos - 1;
        } else {
            entry_pos = 2;
        }
        moved = 1;
    } else if ((pad & PAD_A) && !(prev_pad & PAD_A)) {
        if (entry_pos < 2) {
            entry_pos = entry_pos + 1;
        } else {
            entry_pos = 0;
        }
        moved = 1;
    }

    if (moved) {
        status_action = STATUS_NAME;
        sfx_play(SFX_MENU);
        return;
    }

    if ((pad & PAD_START) && !(prev_pad & PAD_START)) {
        sfx_play(SFX_CONFIRM);
        insert_high_score();
        show_title();
    }
}

void tick_gameover(void)
{
    if ((pad & PAD_START) && !(prev_pad & PAD_START)) {
        entry_rank = find_rank();
        if (entry_rank < HI_COUNT) {
            sfx_play(SFX_CONFIRM);
            show_name_entry();
        } else {
            sfx_play(SFX_MENU);
            show_title();
        }
    }
}

void lock_piece(void)
{
    unsigned char x;
    unsigned char y;
    unsigned char bx;
    unsigned char by;

    y = 0;
    while (y < 4) {
        x = 0;
        while (x < 4) {
            if (shape_cell(piece_t, piece_r, x, y)) {
                bx = piece_x + x;
                by = piece_y + y;
                board[(by * BOARD_W) + bx] = piece_t + 1;
            }
            x = x + 1;
        }
        y = y + 1;
    }
}

unsigned char find_full_rows(void)
{
    unsigned char x;
    unsigned char y;
    unsigned char full;

    clear_count = 0;
    y = 0;
    while (y < BOARD_H) {
        full = 1;
        x = 0;
        while (x < BOARD_W) {
            if (board[(y * BOARD_W) + x] == 0) {
                full = 0;
            }
            x = x + 1;
        }
        if (full) {
            clear_rows[clear_count] = y;
            clear_count = clear_count + 1;
        }
        y = y + 1;
    }
    return clear_count;
}

/* Rows are recorded top to bottom, so collapsing them in order never disturbs
 * a row that has not been handled yet. */
void collapse_cleared_rows(void)
{
    unsigned char i;
    unsigned char x;
    unsigned char yy;

    i = 0;
    while (i < clear_count) {
        yy = clear_rows[i];
        while (yy > 0) {
            x = 0;
            while (x < BOARD_W) {
                board[(yy * BOARD_W) + x] = board[((yy - 1) * BOARD_W) + x];
                x = x + 1;
            }
            yy = yy - 1;
        }
        x = 0;
        while (x < BOARD_W) {
            board[x] = 0;
            x = x + 1;
        }
        i = i + 1;
    }
}

void flash_row(unsigned char row, unsigned char tile)
{
    unsigned char x;

    wait_vblank();
    x = 0;
    while (x < 5) {
        ppu_put(BOARD_X + x, BOARD_Y + row, tile);
        x = x + 1;
    }
    wait_vblank();
    while (x < BOARD_W) {
        ppu_put(BOARD_X + x, BOARD_Y + row, tile);
        x = x + 1;
    }
}

void flash_cleared_rows(void)
{
    unsigned char phase;
    unsigned char i;
    unsigned char tile;

    phase = 0;
    while (phase < 4) {
        tile = TILE_FLASH;
        if (phase & 1) {
            tile = 0;
        }
        i = 0;
        while (i < clear_count) {
            flash_row(clear_rows[i], tile);
            i = i + 1;
        }
        phase = phase + 1;
    }
}

void increment_score_digit(unsigned char position)
{
    unsigned char i;
    unsigned char full;

    full = 1;
    i = position;
    while (i < 6) {
        if (score_digits[i] != 9) {
            full = 0;
        }
        i = i + 1;
    }

    if (full) {
        i = 0;
        while (i < 6) {
            score_digits[i] = 9;
            i = i + 1;
        }
        return;
    }

    while (position < 6) {
        if (score_digits[position] < 9) {
            score_digits[position] = score_digits[position] + 1;
            return;
        }
        score_digits[position] = 0;
        position = position + 1;
    }
}

void add_score_step(unsigned char cleared)
{
    unsigned char i;

    if (cleared == 1) {
        i = 0;
        while (i < 4) {
            increment_score_digit(1);
            i = i + 1;
        }
    } else if (cleared == 2) {
        increment_score_digit(2);
    } else if (cleared == 3) {
        i = 0;
        while (i < 3) {
            increment_score_digit(2);
            i = i + 1;
        }
    } else if (cleared == 4) {
        increment_score_digit(2);
        increment_score_digit(2);
        increment_score_digit(3);
    }
}

void add_line_score(unsigned char cleared)
{
    unsigned char times;
    times = level + 1;
    while (times > 0) {
        add_score_step(cleared);
        times = times - 1;
    }
}

void add_one_line(void)
{
    if (line_digits[2] == 9 && line_digits[1] == 9 && line_digits[0] == 9) {
        return;
    }

    line_digits[0] = line_digits[0] + 1;
    if (line_digits[0] >= 10) {
        line_digits[0] = 0;
        line_digits[1] = line_digits[1] + 1;
        if (line_digits[1] >= 10) {
            line_digits[1] = 0;
            line_digits[2] = line_digits[2] + 1;
        }
        if (level < 99) {
            level = level + 1;
            level_up = 1;
        }
    }
}

void add_cleared_lines(unsigned char cleared)
{
    while (cleared > 0) {
        add_one_line();
        cleared = cleared - 1;
    }
}

void service_status(void)
{
    if (status_action == STATUS_HELP) {
        draw_help();
    } else if (status_action == STATUS_PAUSED) {
        draw_status_paused();
    } else if (status_action == STATUS_GAMEOVER) {
        draw_status_gameover();
    } else if (status_action == STATUS_LEVEL) {
        draw_level_pick();
    } else if (status_action == STATUS_NAME) {
        draw_entry_letters();
    }
    status_action = STATUS_NONE;
}

void render_changes(void)
{
    unsigned char cleared;

    if (piece_dirty) {
        render_queue();
    }

    if (lock_pending) {
        lock_piece();
        sfx_play(SFX_LAND);
        cleared = find_full_rows();
        if (cleared > 0) {
            if (cleared >= 4) {
                sfx_play(SFX_TETRIS);
            } else {
                sfx_play(SFX_LINE);
            }
            flash_cleared_rows();
            collapse_cleared_rows();
            add_line_score(cleared);
            add_cleared_lines(cleared);
            draw_board();
            wait_vblank();
            draw_score_values();
            if (level_up) {
                level_up = 0;
                sfx_play(SFX_LEVELUP);
            }
        }

        spawn_piece();
        draw_next_preview();

        if (game_state == STATE_PLAYING) {
            capture_draw_current();
            wait_vblank();
            render_queue();
        } else {
            sfx_play(SFX_GAMEOVER);
            /* Drawn by service_status() on the next frame so every
             * rendering-on write goes through the same helper. */
            status_action = STATUS_GAMEOVER;
        }

        piece_dirty = 0;
        lock_pending = 0;
    } else {
        piece_dirty = 0;
    }
}

void main(void)
{
    pad = 0;
    prev_pad = 0;
    game_state = STATE_TITLE;
    status_action = STATUS_NONE;
    erase_count = 0;
    draw_count = 0;
    clear_count = 0;
    start_level = 0;
    entry_rank = HI_COUNT;
    /* NES RAM powers up with garbage, so give every counter a value before
     * the title screen can read one. */
    clear_score();
    reset_entry_name();
    init_high_scores();

    music_init();
    show_title();

    while (1) {
        pad = read_pad();
        /* Human input timing advances the 16-bit RNG between every bag fill. */
        rand8();

        if (game_state == STATE_TITLE) {
            tick_title();
        } else if (game_state == STATE_PLAYING) {
            tick_playing();
        } else if (game_state == STATE_PAUSED) {
            tick_paused();
        } else if (game_state == STATE_ENTRY) {
            tick_entry();
        } else {
            tick_gameover();
        }

        wait_vblank();
        service_status();

        if (game_state == STATE_PLAYING) {
            render_changes();
        }

        prev_pad = pad;
    }
}
