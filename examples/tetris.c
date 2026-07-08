extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
extern void render_queue(void);

const unsigned char MASKS[4] = { 8, 4, 2, 1 };

const unsigned char SHAPES[112] = {
    0, 15, 0, 0,
    2, 2, 2, 2,
    0, 15, 0, 0,
    2, 2, 2, 2,

    0, 6, 6, 0,
    0, 6, 6, 0,
    0, 6, 6, 0,
    0, 6, 6, 0,

    0, 7, 2, 0,
    0, 2, 6, 2,
    0, 2, 7, 0,
    0, 2, 3, 2,

    0, 6, 3, 0,
    0, 2, 6, 4,
    0, 6, 3, 0,
    0, 2, 6, 4,

    0, 3, 6, 0,
    0, 4, 6, 2,
    0, 3, 6, 0,
    0, 4, 6, 2,

    0, 7, 1, 0,
    0, 6, 2, 2,
    0, 4, 7, 0,
    0, 2, 2, 6,

    0, 7, 4, 0,
    0, 2, 2, 3,
    0, 1, 7, 0,
    0, 6, 2, 2
};

unsigned char board[200];
unsigned char piece_x;
unsigned char piece_y;
unsigned char piece_t;
unsigned char piece_r;
unsigned char pad;
unsigned char prev_pad;
unsigned char drop_tick;
unsigned char old_piece_x;
unsigned char old_piece_y;
unsigned char old_piece_r;
unsigned char piece_dirty;
unsigned char lock_pending;
unsigned char erase_x[4];
unsigned char erase_y[4];
unsigned char draw_x[4];
unsigned char draw_y[4];
unsigned char erase_count;
unsigned char draw_count;

unsigned char shape_cell(unsigned char t, unsigned char r, unsigned char x, unsigned char y)
{
    unsigned char row;
    row = SHAPES[((t * 4) + r) * 4 + y];
    return row & MASKS[x];
}

void clear_board(void)
{
    unsigned char i;
    i = 0;
    while (i < 200) {
        board[i] = 0;
        i = i + 1;
    }
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
                if (bx >= 10) {
                    return 1;
                }
                if (by >= 20) {
                    return 1;
                }
                if (board[(by * 10) + bx]) {
                    return 1;
                }
            }
            x = x + 1;
        }
        y = y + 1;
    }
    return 0;
}

void draw_piece_at(unsigned char t, unsigned char r, unsigned char px, unsigned char py, unsigned char tile)
{
    unsigned char x;
    unsigned char y;
    unsigned char bx;
    unsigned char by;

    y = 0;
    while (y < 4) {
        x = 0;
        while (x < 4) {
            if (shape_cell(t, r, x, y)) {
                bx = 10 + px + x;
                by = 4 + py + y;
                ppu_put(bx, by, tile);
            }
            x = x + 1;
        }
        y = y + 1;
    }
}

void draw_piece(unsigned char tile)
{
    draw_piece_at(piece_t, piece_r, piece_x, piece_y, tile);
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
                erase_x[erase_count] = 10 + px + x;
                erase_y[erase_count] = 4 + py + y;
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
                draw_x[draw_count] = 10 + piece_x + x;
                draw_y[draw_count] = 4 + piece_y + y;
                draw_count = draw_count + 1;
            }
            x = x + 1;
        }
        y = y + 1;
    }
}

void render_queued_cells(void)
{
    render_queue();
}

void draw_board(void)
{
    unsigned char x;
    unsigned char y;

    y = 0;
    while (y < 20) {
        x = 0;
        while (x < 10) {
            wait_vblank();
            ppu_put(10 + x, 4 + y, board[(y * 10) + x]);
            x = x + 1;
        }
        y = y + 1;
    }
}

void draw_frame(void)
{
    unsigned char x;
    unsigned char y;

    wait_vblank();
    x = 0;
    while (x < 12) {
        wait_vblank();
        ppu_put(9 + x, 3, 8);
        ppu_put(9 + x, 24, 8);
        x = x + 1;
    }

    y = 0;
    while (y < 22) {
        wait_vblank();
        ppu_put(9, 3 + y, 8);
        ppu_put(20, 3 + y, 8);
        y = y + 1;
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
                board[(by * 10) + bx] = piece_t + 1;
            }
            x = x + 1;
        }
        y = y + 1;
    }
}

unsigned char clear_lines(void)
{
    unsigned char y;
    unsigned char x;
    unsigned char yy;
    unsigned char full;
    unsigned char cleared;

    cleared = 0;
    y = 20;
    while (y > 0) {
        y = y - 1;
        full = 1;
        x = 0;
        while (x < 10) {
            if (board[(y * 10) + x] == 0) {
                full = 0;
            }
            x = x + 1;
        }

        if (full) {
            cleared = 1;
            yy = y;
            while (yy > 0) {
                x = 0;
                while (x < 10) {
                    board[(yy * 10) + x] = board[((yy - 1) * 10) + x];
                    x = x + 1;
                }
                yy = yy - 1;
            }
            x = 0;
            while (x < 10) {
                board[x] = 0;
                x = x + 1;
            }
            y = y + 1;
        }
    }
    return cleared;
}

void spawn_piece(void)
{
    piece_t = rand8() % 7;
    piece_r = 0;
    piece_x = 3;
    piece_y = 0;
    drop_tick = 0;
    piece_dirty = 0;
    lock_pending = 0;
    if (collides(piece_x, piece_y, piece_r)) {
        clear_board();
        draw_board();
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

void tick(void)
{
    unsigned char nr;

    piece_dirty = 0;
    lock_pending = 0;

    if ((pad & 2) && !(prev_pad & 2)) {
        if (piece_x > 0) {
            if (!collides(piece_x - 1, piece_y, piece_r)) {
                mark_dirty();
                piece_x = piece_x - 1;
            }
        }
    }

    if ((pad & 1) && !(prev_pad & 1)) {
        if (!collides(piece_x + 1, piece_y, piece_r)) {
            mark_dirty();
            piece_x = piece_x + 1;
        }
    }

    if ((pad & 128) && !(prev_pad & 128)) {
        nr = piece_r + 1;
        if (nr >= 4) {
            nr = 0;
        }
        if (!collides(piece_x, piece_y, nr)) {
            mark_dirty();
            piece_r = nr;
        }
    }

    drop_tick = drop_tick + 1;
    if ((pad & 4) || (drop_tick >= 30)) {
        drop_tick = 0;
        if (!collides(piece_x, piece_y + 1, piece_r)) {
            mark_dirty();
            piece_y = piece_y + 1;
        } else {
            mark_dirty();
            lock_pending = 1;
        }
    }

    if (piece_dirty) {
        capture_erase_at(piece_t, old_piece_r, old_piece_x, old_piece_y);
        capture_draw_current();
    }
}

void render_changes(void)
{
    render_queued_cells();

    if (lock_pending) {
        lock_piece();
        if (clear_lines()) {
            draw_board();
        }
        spawn_piece();
        capture_draw_current();
        wait_vblank();
        render_queued_cells();
        piece_dirty = 0;
        lock_pending = 0;
        return;
    }

    if (piece_dirty) {
        piece_dirty = 0;
    }
}

void main(void)
{
    pad = 0;
    prev_pad = 0;
    piece_dirty = 0;
    lock_pending = 0;
    clear_board();
    draw_frame();
    draw_board();
    spawn_piece();
    capture_draw_current();
    wait_vblank();
    render_queued_cells();

    while (1) {
        pad = read_pad();
        tick();
        wait_vblank();
        render_changes();
        prev_pad = pad;
    }
}
