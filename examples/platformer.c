/* FAMI-C example: a NES/Famicom platformer.
 *
 * The FAMI-C runtime draws backgrounds only - it never enables sprites - so
 * this game is built on a 16x16 metatile grid instead of free pixel motion.
 * The screen is 16 cells wide and 15 cells tall: cell row 0 is the status
 * bar and rows 1..14 are the stage.  Every actor occupies one whole cell,
 * which means one cell is also the unit of collision, of level storage and
 * of the attribute table, so a cell can pick its own background palette.
 *
 * The hero and the patrols are drawn in colour 3 only.  Colour 3 is $30 in
 * all four background palettes, so they stay white wherever they walk while
 * the terrain around them changes colour with the attribute map.
 *
 * Motion is frame-timed rather than sub-pixel: a walk step, a rise step and
 * a fall step each take a whole number of frames, and the tables below are
 * the entire physics model.  Only the cells that actually changed are
 * redrawn, and those writes go through a queue that is flushed at most
 * TILES_PER_VBLANK tiles per vblank so the PPU is never touched late.
 */

extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern void ppu_off(void);
extern void ppu_on(void);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
extern void sfx_play(unsigned char effect);

#define PAD_A 128
#define PAD_B 64
#define PAD_SELECT 32
#define PAD_START 16
#define PAD_UP 8
#define PAD_DOWN 4
#define PAD_LEFT 2
#define PAD_RIGHT 1

/* Tiles the CHR generator reserves for the platformer. */
#define TILE_BLANK 0
#define TILE_DIGIT0 16
#define TILE_RULE 55
#define HERO_IDLE_R 92
#define HERO_IDLE_L 96
#define HERO_WALK_R 100
#define HERO_WALK_L 104
#define HERO_JUMP_R 108
#define HERO_JUMP_L 112
#define FOE_TILE_A 116
#define FOE_TILE_B 120
#define GEM_TILE 124
#define SPIKE_TILE 128
#define DOOR_TILE 132
#define DIRT_TILE 136
#define GRASS_TILE 137
#define BRICK_TILE 138

/* Cell kinds stored in the level map. */
#define C_EMPTY 0
#define C_DIRT 1
#define C_GRASS 2
#define C_BRICK 3
#define C_GEM 4
#define C_SPIKE 5
#define C_GOAL 6
#define C_FOE 7

#define GRID_W 16
#define GRID_H 15
#define LEVEL_SIZE 240
#define STAGE_COUNT 4
#define MAX_FOES 4

/* Frame budget.  One queued write costs about 200 cycles - the ppu_put call
 * itself plus the loop that feeds it from the queue - so eight of them fit
 * inside an NTSC vblank with room to spare.  Eight is also exactly one
 * erase-and-redraw of a moving actor, which is the common case. */
#define TILES_PER_VBLANK 8
#define QUEUE_MAX 40

/* Physics, in frames per cell. */
#define WALK_DELAY 12
#define RUN_DELAY 8
#define FOE_DELAY 6

#define VS_GROUND 0
#define VS_JUMP 1
#define VS_FALL 2

#define ST_TITLE 0
#define ST_INTRO 1
#define ST_PLAY 2
#define ST_DEAD 3
#define ST_CLEAR 4
#define ST_OVER 5
#define ST_WIN 6

#define INTRO_FRAMES 80
#define DEAD_FRAMES 80
#define CLEAR_FRAMES 100

#define SFX_JUMP 1
#define SFX_GEM 2
#define SFX_STOMP 3
#define SFX_HURT 4
#define SFX_CLEAR 5
#define SFX_OVER 6
#define SFX_LAND 7

#define START_LIVES 3

/* The four tiles of every cell kind, in nametable reading order. */
const unsigned char CELL_TL[8] = {
    TILE_BLANK, DIRT_TILE, GRASS_TILE, BRICK_TILE,
    GEM_TILE, SPIKE_TILE, DOOR_TILE, TILE_BLANK,
};

const unsigned char CELL_TR[8] = {
    TILE_BLANK, DIRT_TILE, GRASS_TILE, BRICK_TILE,
    GEM_TILE + 1, SPIKE_TILE + 1, DOOR_TILE + 1, TILE_BLANK,
};

const unsigned char CELL_BL[8] = {
    TILE_BLANK, DIRT_TILE, DIRT_TILE, BRICK_TILE,
    GEM_TILE + 2, SPIKE_TILE + 2, DOOR_TILE + 2, TILE_BLANK,
};

const unsigned char CELL_BR[8] = {
    TILE_BLANK, DIRT_TILE, DIRT_TILE, BRICK_TILE,
    GEM_TILE + 3, SPIKE_TILE + 3, DOOR_TILE + 3, TILE_BLANK,
};

/* Background palette per cell kind: 0 sky, 1 brick/spike red, 2 earth green,
 * 3 treasure purple.  One attribute quadrant covers exactly one cell. */
const unsigned char CELL_PAL[8] = { 0, 2, 2, 1, 3, 1, 3, 0 };

const unsigned char CELL_SOLID[8] = { 0, 1, 1, 1, 0, 0, 0, 0 };

/* Rise steps, in frames, ending with the 0 sentinel: three cells up over
 * sixteen frames.  Releasing A after the first step cuts the jump short. */
const unsigned char JUMP_DELAY[4] = { 4, 5, 7, 0 };

/* Fall steps, in frames.  The first entry is the apex hang, which is what
 * lets a jump drift onto a ledge instead of dropping straight down. */
const unsigned char FALL_DELAY[8] = { 10, 7, 6, 5, 5, 5, 5, 5 };

/* STAGE 1 - a walk, a two-cell pit, and a short climb */
const unsigned char LEVEL1[240] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 3, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 6, 0,
    0, 0, 3, 3, 3, 0, 0, 0, 0, 3, 3, 3, 2, 2, 2, 2,
    0, 0, 4, 0, 0, 0, 7, 0, 0, 0, 0, 0, 7, 0, 0, 0,
    2, 2, 2, 2, 2, 2, 2, 0, 0, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1,
};

/* STAGE 2 - a zig-zag tower over a spike pit */
const unsigned char LEVEL2[240] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 6, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    3, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 3, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0,
    0, 0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 7, 0, 0, 0, 0,
    2, 2, 2, 2, 2, 2, 5, 5, 2, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

/* STAGE 3 - three spike pits guarded by patrols */
const unsigned char LEVEL3[240] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0,
    0, 0, 0, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0,
    0, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 0,
    0, 0, 0, 0, 0, 7, 0, 0, 0, 7, 0, 0, 0, 7, 0, 6,
    2, 2, 2, 5, 5, 2, 2, 5, 5, 2, 2, 5, 5, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

/* STAGE 4 - the full tower, three patrols and two spike pits */
const unsigned char LEVEL4[240] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 6, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 7, 0, 0, 0, 0, 0, 7, 0, 0, 0, 7, 0, 0,
    2, 2, 2, 2, 2, 5, 5, 2, 2, 2, 2, 5, 5, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

const unsigned char SPAWN_X[4] = { 1, 8, 0, 0 };
const unsigned char SPAWN_Y[4] = { 12, 12, 12, 12 };

#define TXT_LIFE 0
#define TXT_GEM 1
#define TXT_SCORE 2
#define TXT_FAMIC 3
#define TXT_TITLE 4
#define TXT_PRESS_START 5
#define TXT_MOVE 6
#define TXT_JUMP 7
#define TXT_RUN 8
#define TXT_STAGE 9
#define TXT_READY 10
#define TXT_CLEAR 11
#define TXT_GAME_OVER 12
#define TXT_CONGRATS 13
#define TXT_ALL_CLEAR 14

/* Every on-screen string, stored as ready-made tile ids. */
const unsigned char TEXT_DATA[135] = {
    37, 34, 31, 30, 53, 32, 30, 38, 53, 44, 28, 40, 43, 30, 53, 31,
    26, 38, 34, 52, 28, 41, 37, 26, 45, 31, 40, 43, 38, 30, 43, 41,
    43, 30, 44, 44, 0, 44, 45, 26, 43, 45, 29, 52, 41, 26, 29, 0,
    0, 38, 40, 47, 30, 26, 0, 0, 0, 0, 0, 0, 35, 46, 38, 41,
    27, 0, 0, 0, 0, 0, 0, 43, 46, 39, 44, 45, 26, 32, 30, 43,
    30, 26, 29, 50, 44, 45, 26, 32, 30, 0, 28, 37, 30, 26, 43, 32,
    26, 38, 30, 0, 40, 47, 30, 43, 28, 40, 39, 32, 43, 26, 45, 46,
    37, 26, 45, 34, 40, 39, 44, 26, 37, 37, 0, 44, 45, 26, 32, 30,
    44, 0, 28, 37, 30, 26, 43,
};

const unsigned char TEXT_START[15] = {
    0, 5, 9, 15, 21, 31, 42, 53, 64, 74, 79, 84, 95, 104, 119,
};

const unsigned char TEXT_LEN[15] = {
    5, 4, 6, 6, 10, 11, 11, 11, 10, 5, 5, 11, 9, 15, 16,
};

/* Sound effects: SFX_START/SFX_LENGTH locate a run of one-frame steps inside
 * the SFX_CTRL/SFX_TIMER_LO/SFX_TIMER_HI tables, which the runtime replays on
 * pulse 2.  Slot 0 is reserved by the driver as "stop the current effect". */
const unsigned char SFX_START[16] = {
    0, 0, 6, 13, 18, 34, 56, 80, 0, 0, 0, 0, 0, 0, 0, 0,
};

const unsigned char SFX_LENGTH[16] = {
    0, 6, 7, 5, 16, 22, 24, 3, 0, 0, 0, 0, 0, 0, 0, 0,
};

const unsigned char SFX_CTRL[83] = {
    24, 25, 26, 24, 21, 18, 155, 155, 156, 156, 156, 151, 147, 92, 91, 89,
    86, 83, 92, 92, 92, 92, 91, 91, 90, 90, 88, 88, 86, 86, 84, 84,
    82, 82, 154, 154, 154, 155, 155, 155, 156, 156, 156, 157, 157, 157, 157, 157,
    157, 153, 153, 153, 149, 149, 146, 146, 155, 155, 155, 155, 155, 155, 155, 155,
    154, 154, 154, 154, 153, 153, 153, 153, 153, 150, 150, 150, 150, 147, 147, 147,
    87, 84, 82,
};

const unsigned char SFX_TIMER_LO[83] = {
    253, 189, 150, 126, 126, 126, 84, 84, 63, 63, 63, 63, 63, 213, 82, 251,
    249, 248, 169, 169, 225, 225, 45, 45, 147, 147, 26, 26, 206, 206, 191, 191,
    0, 0, 213, 213, 213, 169, 169, 169, 142, 142, 142, 106, 106, 106, 106, 106,
    106, 106, 106, 106, 106, 106, 106, 106, 253, 253, 253, 253, 63, 63, 63, 63,
    124, 124, 124, 124, 251, 251, 251, 251, 251, 128, 128, 128, 128, 249, 249, 249,
    248, 0, 243,
};

const unsigned char SFX_TIMER_HI[83] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1,
    2, 3, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3,
    5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2,
    3, 5, 5,
};

unsigned char level[LEVEL_SIZE];

unsigned char q_x[QUEUE_MAX];
unsigned char q_y[QUEUE_MAX];
unsigned char q_tile[QUEUE_MAX];
unsigned char q_count;

unsigned char foe_x[MAX_FOES];
unsigned char foe_y[MAX_FOES];
unsigned char foe_dir[MAX_FOES];
unsigned char foe_live[MAX_FOES];
unsigned char foe_timer[MAX_FOES];
unsigned char foe_frame[MAX_FOES];
unsigned char foe_count;

unsigned char score_digits[5];

unsigned char game_state;
unsigned char stage;
unsigned char lives;
unsigned char gems_left;
unsigned char pause_timer;
unsigned char frame;
unsigned char pad;
unsigned char prev_pad;
unsigned char hud_dirty;

unsigned char px;
unsigned char py;
unsigned char facing;
unsigned char walk_frame;
unsigned char walk_timer;
unsigned char vstate;
unsigned char jump_phase;
unsigned char jump_timer;
unsigned char fall_phase;
unsigned char fall_timer;

unsigned char hero_px;
unsigned char hero_py;
unsigned char hero_pose;
unsigned char hero_dirty;

/* ---------------------------------------------------------------- level */

unsigned char level_byte(unsigned char which, unsigned char index)
{
    if (which == 0) {
        return LEVEL1[index];
    }
    if (which == 1) {
        return LEVEL2[index];
    }
    if (which == 2) {
        return LEVEL3[index];
    }
    return LEVEL4[index];
}

unsigned char cell_at(unsigned char cx, unsigned char cy)
{
    if (cx >= GRID_W) {
        return C_EMPTY;
    }
    if (cy >= GRID_H) {
        return C_EMPTY;
    }
    return level[cy * GRID_W + cx];
}

/* Off the sides is wall, the status bar is ceiling, and below the last row
 * is open air so a missed jump falls out of the stage. */
unsigned char is_solid(unsigned char cx, unsigned char cy)
{
    if (cx >= GRID_W) {
        return 1;
    }
    if (cy == 0) {
        return 1;
    }
    if (cy >= GRID_H) {
        return 0;
    }
    return CELL_SOLID[level[cy * GRID_W + cx]];
}

unsigned char cell_palette(unsigned char cx, unsigned char cy)
{
    if (cy == 0) {
        return 0;
    }
    return CELL_PAL[cell_at(cx, cy)];
}

/* ----------------------------------------------------------- tile queue */

void push_tile(unsigned char x, unsigned char y, unsigned char tile)
{
    if (q_count >= QUEUE_MAX) {
        return;
    }
    q_x[q_count] = x;
    q_y[q_count] = y;
    q_tile[q_count] = tile;
    q_count = q_count + 1;
}

void push_cell(unsigned char cx, unsigned char cy)
{
    unsigned char kind;
    unsigned char tx;
    unsigned char ty;

    if (cy == 0 || cy >= GRID_H) {
        return;
    }
    kind = cell_at(cx, cy);
    tx = cx + cx;
    ty = cy + cy;
    push_tile(tx, ty, CELL_TL[kind]);
    push_tile(tx + 1, ty, CELL_TR[kind]);
    push_tile(tx, ty + 1, CELL_BL[kind]);
    push_tile(tx + 1, ty + 1, CELL_BR[kind]);
}

void push_actor(unsigned char cx, unsigned char cy, unsigned char base)
{
    unsigned char tx;
    unsigned char ty;

    if (cy == 0 || cy >= GRID_H) {
        return;
    }
    tx = cx + cx;
    ty = cy + cy;
    push_tile(tx, ty, base);
    push_tile(tx + 1, ty, base + 1);
    push_tile(tx, ty + 1, base + 2);
    push_tile(tx + 1, ty + 1, base + 3);
}

/* Drain the queue, pausing for a fresh vblank every TILES_PER_VBLANK writes.
 * The caller enters this already inside vblank. */
void flush_tiles(void)
{
    unsigned char i;
    unsigned char budget;

    i = 0;
    budget = 0;
    while (i < q_count) {
        if (budget == TILES_PER_VBLANK) {
            wait_vblank();
            budget = 0;
        }
        ppu_put(q_x[i], q_y[i], q_tile[i]);
        i = i + 1;
        budget = budget + 1;
    }
    q_count = 0;
}

/* ------------------------------------------------- rendering-off drawing */

void clear_screen_off(void)
{
    unsigned char x;
    unsigned char y;

    y = 0;
    while (y < 30) {
        x = 0;
        while (x < 32) {
            ppu_put(x, y, TILE_BLANK);
            x = x + 1;
        }
        y = y + 1;
    }
}

/* Rows 30 and 31 of ppu_put's address maths land on the attribute table, so
 * the same helper that writes tiles also writes palette selects. */
void fill_attributes_off(unsigned char pal)
{
    unsigned char i;
    unsigned char value;

    value = pal + pal * 4 + pal * 16 + pal * 64;
    i = 0;
    while (i < 32) {
        ppu_put(i, 30, value);
        ppu_put(i, 31, value);
        i = i + 1;
    }
}

/* One attribute byte covers a 2x2 block of cells, one quadrant each. */
void draw_attributes_off(void)
{
    unsigned char ax;
    unsigned char ay;
    unsigned char cx;
    unsigned char cy;
    unsigned char value;

    ay = 0;
    while (ay < 8) {
        ax = 0;
        while (ax < 8) {
            cx = ax + ax;
            cy = ay + ay;
            value = cell_palette(cx, cy);
            value = value + cell_palette(cx + 1, cy) * 4;
            value = value + cell_palette(cx, cy + 1) * 16;
            value = value + cell_palette(cx + 1, cy + 1) * 64;
            if (ay < 4) {
                ppu_put(ay * 8 + ax, 30, value);
            } else {
                ppu_put((ay - 4) * 8 + ax, 31, value);
            }
            ax = ax + 1;
        }
        ay = ay + 1;
    }
}

void draw_text_off(unsigned char x, unsigned char y, unsigned char id)
{
    unsigned char i;
    unsigned char base;
    unsigned char len;

    base = TEXT_START[id];
    len = TEXT_LEN[id];
    i = 0;
    while (i < len) {
        ppu_put(x + i, y, TEXT_DATA[base + i]);
        i = i + 1;
    }
}

void draw_level_off(void)
{
    unsigned char cx;
    unsigned char cy;
    unsigned char kind;
    unsigned char tx;
    unsigned char ty;

    cy = 1;
    while (cy < GRID_H) {
        cx = 0;
        while (cx < GRID_W) {
            kind = level[cy * GRID_W + cx];
            tx = cx + cx;
            ty = cy + cy;
            ppu_put(tx, ty, CELL_TL[kind]);
            ppu_put(tx + 1, ty, CELL_TR[kind]);
            ppu_put(tx, ty + 1, CELL_BL[kind]);
            ppu_put(tx + 1, ty + 1, CELL_BR[kind]);
            cx = cx + 1;
        }
        cy = cy + 1;
    }
}

void draw_actor_off(unsigned char cx, unsigned char cy, unsigned char base)
{
    unsigned char tx;
    unsigned char ty;

    tx = cx + cx;
    ty = cy + cy;
    ppu_put(tx, ty, base);
    ppu_put(tx + 1, ty, base + 1);
    ppu_put(tx, ty + 1, base + 2);
    ppu_put(tx + 1, ty + 1, base + 3);
}

/* -------------------------------------------------------------- the HUD */

void draw_hud_values_off(void)
{
    ppu_put(6, 0, TILE_DIGIT0 + lives);
    ppu_put(14, 0, TILE_DIGIT0 + gems_left / 10);
    ppu_put(15, 0, TILE_DIGIT0 + gems_left % 10);
    ppu_put(26, 0, TILE_DIGIT0 + score_digits[4]);
    ppu_put(27, 0, TILE_DIGIT0 + score_digits[3]);
    ppu_put(28, 0, TILE_DIGIT0 + score_digits[2]);
    ppu_put(29, 0, TILE_DIGIT0 + score_digits[1]);
    ppu_put(30, 0, TILE_DIGIT0 + score_digits[0]);
}

void draw_hud_off(void)
{
    unsigned char x;

    x = 0;
    while (x < 32) {
        ppu_put(x, 0, TILE_BLANK);
        ppu_put(x, 1, TILE_RULE);
        x = x + 1;
    }
    draw_text_off(1, 0, TXT_LIFE);
    draw_text_off(10, 0, TXT_GEM);
    draw_text_off(20, 0, TXT_SCORE);
    draw_hud_values_off();
}

void push_hud_values(void)
{
    push_tile(6, 0, TILE_DIGIT0 + lives);
    push_tile(14, 0, TILE_DIGIT0 + gems_left / 10);
    push_tile(15, 0, TILE_DIGIT0 + gems_left % 10);
    push_tile(26, 0, TILE_DIGIT0 + score_digits[4]);
    push_tile(27, 0, TILE_DIGIT0 + score_digits[3]);
    push_tile(28, 0, TILE_DIGIT0 + score_digits[2]);
    push_tile(29, 0, TILE_DIGIT0 + score_digits[1]);
    push_tile(30, 0, TILE_DIGIT0 + score_digits[0]);
}

/* Score is kept as five digits, least significant first, and counted in
 * hundreds so a gem is worth 100 and a stomped patrol 200. */
void add_points(unsigned char hundreds)
{
    unsigned char i;

    score_digits[2] = score_digits[2] + hundreds;
    i = 2;
    while (i < 5) {
        if (score_digits[i] < 10) {
            i = 5;
        } else {
            score_digits[i] = score_digits[i] - 10;
            if (i < 4) {
                score_digits[i + 1] = score_digits[i + 1] + 1;
            }
            i = i + 1;
        }
    }
    hud_dirty = 1;
}

void clear_score(void)
{
    unsigned char i;

    i = 0;
    while (i < 5) {
        score_digits[i] = 0;
        i = i + 1;
    }
}

/* ------------------------------------------------------------- the hero */

unsigned char hero_pose_tile(void)
{
    if (vstate != VS_GROUND) {
        if (facing) {
            return HERO_JUMP_R;
        }
        return HERO_JUMP_L;
    }
    if (walk_frame) {
        if (facing) {
            return HERO_WALK_R;
        }
        return HERO_WALK_L;
    }
    if (facing) {
        return HERO_IDLE_R;
    }
    return HERO_IDLE_L;
}

void begin_fall(void)
{
    vstate = VS_FALL;
    fall_phase = 0;
    fall_timer = FALL_DELAY[0];
    hero_dirty = 1;
}

void begin_jump(void)
{
    vstate = VS_JUMP;
    jump_phase = 0;
    jump_timer = JUMP_DELAY[0];
    hero_dirty = 1;
    sfx_play(SFX_JUMP);
}

void land_hero(void)
{
    vstate = VS_GROUND;
    hero_dirty = 1;
    sfx_play(SFX_LAND);
}

void lose_life(void)
{
    sfx_play(SFX_HURT);
    game_state = ST_DEAD;
    pause_timer = DEAD_FRAMES;
}

void stage_cleared(void)
{
    sfx_play(SFX_CLEAR);
    add_points(10);
    game_state = ST_CLEAR;
    pause_timer = CLEAR_FRAMES;
}

/* Whatever the hero just stepped into. */
void touch_cell(void)
{
    unsigned char kind;

    if (py >= GRID_H) {
        lose_life();
        return;
    }
    kind = cell_at(px, py);
    if (kind == C_GEM) {
        level[py * GRID_W + px] = C_EMPTY;
        gems_left = gems_left - 1;
        add_points(1);
        sfx_play(SFX_GEM);
        return;
    }
    if (kind == C_SPIKE) {
        lose_life();
        return;
    }
    if (kind == C_GOAL) {
        stage_cleared();
    }
}

/* Walking off a ledge starts a fall; drifting over one during a fall lands. */
void settle_hero(void)
{
    if (vstate == VS_GROUND) {
        if (!is_solid(px, py + 1)) {
            begin_fall();
        }
        return;
    }
    if (vstate == VS_FALL) {
        if (is_solid(px, py + 1)) {
            land_hero();
        }
    }
}

void step_walk(void)
{
    unsigned char nx;
    unsigned char want_right;
    unsigned char moving;

    moving = 0;
    want_right = 0;
    if (pad & PAD_RIGHT) {
        moving = 1;
        want_right = 1;
    } else if (pad & PAD_LEFT) {
        moving = 1;
    }

    if (!moving) {
        walk_timer = 0;
        return;
    }

    if (want_right != facing) {
        facing = want_right;
        hero_dirty = 1;
    }

    if (walk_timer > 0) {
        walk_timer = walk_timer - 1;
        return;
    }
    if (pad & PAD_B) {
        walk_timer = RUN_DELAY;
    } else {
        walk_timer = WALK_DELAY;
    }

    if (want_right) {
        nx = px + 1;
    } else {
        nx = px - 1;
    }
    if (is_solid(nx, py)) {
        return;
    }
    px = nx;
    walk_frame = !walk_frame;
    hero_dirty = 1;
    touch_cell();
    if (game_state != ST_PLAY) {
        return;
    }
    settle_hero();
}

void step_vertical(void)
{
    if (vstate == VS_JUMP) {
        /* Letting go of A after the first rise step cuts the arc short. */
        if (jump_phase > 0 && !(pad & PAD_A)) {
            begin_fall();
            return;
        }
        if (jump_timer > 0) {
            jump_timer = jump_timer - 1;
            return;
        }
        if (is_solid(px, py - 1)) {
            begin_fall();
            return;
        }
        py = py - 1;
        hero_dirty = 1;
        jump_phase = jump_phase + 1;
        if (JUMP_DELAY[jump_phase] == 0) {
            begin_fall();
        } else {
            jump_timer = JUMP_DELAY[jump_phase];
        }
        touch_cell();
        return;
    }
    if (vstate == VS_FALL) {
        if (fall_timer > 0) {
            fall_timer = fall_timer - 1;
            return;
        }
        if (is_solid(px, py + 1)) {
            land_hero();
            return;
        }
        py = py + 1;
        hero_dirty = 1;
        if (fall_phase < 7) {
            fall_phase = fall_phase + 1;
        }
        fall_timer = FALL_DELAY[fall_phase];
        touch_cell();
        return;
    }
    if (!is_solid(px, py + 1)) {
        begin_fall();
    }
}

/* ----------------------------------------------------------- the patrols */

void push_foe(unsigned char i)
{
    if (foe_frame[i]) {
        push_actor(foe_x[i], foe_y[i], FOE_TILE_B);
    } else {
        push_actor(foe_x[i], foe_y[i], FOE_TILE_A);
    }
}

/* Patrols walk until a wall or a ledge turns them around.  One patrol is
 * serviced per frame so a single frame never queues more than one of them. */
void step_foe(unsigned char i)
{
    unsigned char nx;

    if (!foe_live[i]) {
        return;
    }
    if (foe_timer[i] > 0) {
        foe_timer[i] = foe_timer[i] - 1;
        return;
    }
    foe_timer[i] = FOE_DELAY;

    if (foe_dir[i]) {
        nx = foe_x[i] + 1;
    } else {
        nx = foe_x[i] - 1;
    }
    if (is_solid(nx, foe_y[i]) || !is_solid(nx, foe_y[i] + 1)) {
        foe_dir[i] = !foe_dir[i];
        return;
    }
    push_cell(foe_x[i], foe_y[i]);
    foe_x[i] = nx;
    foe_frame[i] = !foe_frame[i];
    push_foe(i);
}

void check_foes(void)
{
    unsigned char i;

    i = 0;
    while (i < MAX_FOES) {
        if (foe_live[i] && foe_x[i] == px && foe_y[i] == py) {
            if (vstate == VS_FALL) {
                foe_live[i] = 0;
                push_cell(foe_x[i], foe_y[i]);
                add_points(2);
                sfx_play(SFX_STOMP);
                /* Bounce off the squashed patrol. */
                vstate = VS_JUMP;
                jump_phase = 1;
                jump_timer = JUMP_DELAY[1];
                hero_dirty = 1;
            } else {
                lose_life();
                return;
            }
        }
        i = i + 1;
    }
}

/* --------------------------------------------------------- stage set-up */

void load_stage(void)
{
    unsigned char i;
    unsigned char kind;

    q_count = 0;
    foe_count = 0;
    i = 0;
    while (i < MAX_FOES) {
        foe_live[i] = 0;
        i = i + 1;
    }

    gems_left = 0;
    i = 0;
    while (i < LEVEL_SIZE) {
        kind = level_byte(stage, i);
        if (kind == C_FOE) {
            kind = C_EMPTY;
            if (foe_count < MAX_FOES) {
                foe_x[foe_count] = i % GRID_W;
                foe_y[foe_count] = i / GRID_W;
                foe_dir[foe_count] = foe_count & 1;
                foe_live[foe_count] = 1;
                foe_timer[foe_count] = FOE_DELAY;
                foe_frame[foe_count] = 0;
                foe_count = foe_count + 1;
            }
        }
        if (kind == C_GEM) {
            gems_left = gems_left + 1;
        }
        level[i] = kind;
        i = i + 1;
    }

    px = SPAWN_X[stage];
    py = SPAWN_Y[stage];
    facing = 1;
    walk_frame = 0;
    walk_timer = 0;
    vstate = VS_GROUND;
    jump_phase = 0;
    jump_timer = 0;
    fall_phase = 0;
    fall_timer = 0;
    hero_px = px;
    hero_py = py;
    hero_pose = HERO_IDLE_R;
    hero_dirty = 0;
    hud_dirty = 0;

    wait_vblank();
    ppu_off();
    draw_hud_off();
    draw_level_off();
    draw_attributes_off();
    draw_actor_off(px, py, hero_pose);
    i = 0;
    while (i < MAX_FOES) {
        if (foe_live[i]) {
            draw_actor_off(foe_x[i], foe_y[i], FOE_TILE_A);
        }
        i = i + 1;
    }
    game_state = ST_PLAY;
    wait_vblank();
    ppu_on();
}

/* ------------------------------------------------------------- screens */

void show_title(void)
{
    wait_vblank();
    ppu_off();
    clear_screen_off();
    fill_attributes_off(3);

    draw_text_off(13, 4, TXT_FAMIC);
    draw_text_off(11, 6, TXT_TITLE);

    /* A cast line so the title screen shows what the tiles look like. */
    draw_actor_off(5, 6, HERO_IDLE_R);
    draw_actor_off(8, 6, GEM_TILE);
    draw_actor_off(11, 6, FOE_TILE_A);

    draw_text_off(10, 17, TXT_MOVE);
    draw_text_off(10, 18, TXT_JUMP);
    draw_text_off(10, 19, TXT_RUN);
    draw_text_off(10, 23, TXT_PRESS_START);

    game_state = ST_TITLE;
    wait_vblank();
    ppu_on();
}

void show_stage_intro(void)
{
    wait_vblank();
    ppu_off();
    clear_screen_off();
    fill_attributes_off(0);
    draw_text_off(12, 13, TXT_STAGE);
    ppu_put(18, 13, TILE_DIGIT0 + stage + 1);
    draw_text_off(13, 16, TXT_READY);
    game_state = ST_INTRO;
    pause_timer = INTRO_FRAMES;
    wait_vblank();
    ppu_on();
}

void show_stage_clear(void)
{
    wait_vblank();
    ppu_off();
    clear_screen_off();
    fill_attributes_off(2);
    draw_text_off(10, 13, TXT_CLEAR);
    draw_text_off(10, 16, TXT_SCORE);
    ppu_put(16, 16, TILE_DIGIT0 + score_digits[4]);
    ppu_put(17, 16, TILE_DIGIT0 + score_digits[3]);
    ppu_put(18, 16, TILE_DIGIT0 + score_digits[2]);
    ppu_put(19, 16, TILE_DIGIT0 + score_digits[1]);
    ppu_put(20, 16, TILE_DIGIT0 + score_digits[0]);
    wait_vblank();
    ppu_on();
}

void show_game_over(void)
{
    wait_vblank();
    ppu_off();
    clear_screen_off();
    fill_attributes_off(1);
    draw_text_off(11, 12, TXT_GAME_OVER);
    draw_text_off(10, 16, TXT_SCORE);
    ppu_put(16, 16, TILE_DIGIT0 + score_digits[4]);
    ppu_put(17, 16, TILE_DIGIT0 + score_digits[3]);
    ppu_put(18, 16, TILE_DIGIT0 + score_digits[2]);
    ppu_put(19, 16, TILE_DIGIT0 + score_digits[1]);
    ppu_put(20, 16, TILE_DIGIT0 + score_digits[0]);
    draw_text_off(10, 21, TXT_PRESS_START);
    game_state = ST_OVER;
    sfx_play(SFX_OVER);
    wait_vblank();
    ppu_on();
}

void show_win(void)
{
    wait_vblank();
    ppu_off();
    clear_screen_off();
    fill_attributes_off(3);
    draw_text_off(8, 10, TXT_CONGRATS);
    draw_text_off(8, 13, TXT_ALL_CLEAR);
    draw_text_off(10, 17, TXT_SCORE);
    ppu_put(16, 17, TILE_DIGIT0 + score_digits[4]);
    ppu_put(17, 17, TILE_DIGIT0 + score_digits[3]);
    ppu_put(18, 17, TILE_DIGIT0 + score_digits[2]);
    ppu_put(19, 17, TILE_DIGIT0 + score_digits[1]);
    ppu_put(20, 17, TILE_DIGIT0 + score_digits[0]);
    draw_text_off(10, 21, TXT_PRESS_START);
    game_state = ST_WIN;
    sfx_play(SFX_CLEAR);
    wait_vblank();
    ppu_on();
}

/* ----------------------------------------------------------- game ticks */

void tick_title(void)
{
    if (pad & PAD_START) {
        if (!(prev_pad & PAD_START)) {
            stage = 0;
            lives = START_LIVES;
            clear_score();
            show_stage_intro();
        }
    }
}

void tick_intro(void)
{
    if (pause_timer > 0) {
        pause_timer = pause_timer - 1;
        return;
    }
    load_stage();
}

void tick_dead(void)
{
    if (pause_timer > 0) {
        pause_timer = pause_timer - 1;
        return;
    }
    if (lives > 0) {
        lives = lives - 1;
    }
    if (lives == 0) {
        show_game_over();
        return;
    }
    show_stage_intro();
}

void tick_clear(void)
{
    if (pause_timer > 0) {
        pause_timer = pause_timer - 1;
        if (pause_timer == CLEAR_FRAMES - 1) {
            show_stage_clear();
        }
        return;
    }
    stage = stage + 1;
    if (stage >= STAGE_COUNT) {
        show_win();
        return;
    }
    show_stage_intro();
}

void tick_end_screen(void)
{
    if (pad & PAD_START) {
        if (!(prev_pad & PAD_START)) {
            show_title();
        }
    }
}

void tick_play(void)
{
    unsigned char pose;

    if (vstate == VS_GROUND && (pad & PAD_A) && !(prev_pad & PAD_A)) {
        begin_jump();
    }

    step_walk();
    if (game_state != ST_PLAY) {
        return;
    }

    step_vertical();
    if (game_state != ST_PLAY) {
        return;
    }

    step_foe(frame & 3);
    check_foes();
    if (game_state != ST_PLAY) {
        return;
    }

    pose = hero_pose_tile();
    if (px != hero_px || py != hero_py) {
        push_cell(hero_px, hero_py);
        hero_px = px;
        hero_py = py;
        push_actor(px, py, pose);
        hero_pose = pose;
        hero_dirty = 0;
    } else if (hero_dirty || pose != hero_pose) {
        push_actor(px, py, pose);
        hero_pose = pose;
        hero_dirty = 0;
    }

    if (hud_dirty) {
        push_hud_values();
        hud_dirty = 0;
    }
}

void main(void)
{
    /* NES RAM powers up with garbage, so nothing may be read before it has
     * been written at least once. */
    pad = 0;
    prev_pad = 0;
    frame = 0;
    stage = 0;
    lives = START_LIVES;
    gems_left = 0;
    pause_timer = 0;
    q_count = 0;
    foe_count = 0;
    hud_dirty = 0;
    hero_dirty = 0;
    hero_px = 0;
    hero_py = 0;
    hero_pose = HERO_IDLE_R;
    px = 0;
    py = 0;
    facing = 1;
    walk_frame = 0;
    walk_timer = 0;
    vstate = VS_GROUND;
    jump_phase = 0;
    jump_timer = 0;
    fall_phase = 0;
    fall_timer = 0;
    clear_score();

    show_title();

    while (1) {
        pad = read_pad();
        /* Human input timing keeps the 16-bit LFSR from repeating. */
        rand8();

        if (game_state == ST_TITLE) {
            tick_title();
        } else if (game_state == ST_INTRO) {
            tick_intro();
        } else if (game_state == ST_PLAY) {
            tick_play();
        } else if (game_state == ST_DEAD) {
            tick_dead();
        } else if (game_state == ST_CLEAR) {
            tick_clear();
        } else {
            tick_end_screen();
        }

        wait_vblank();
        flush_tiles();
        prev_pad = pad;
        frame = frame + 1;
    }
}
