# 레시피

바로 복사해서 쓰는 골격들. 전부 실제로 빌드되는 코드다.

---

## 1. 게임 루프와 상태 기계

거의 모든 게임이 이 모양이다.

```c
#include <fami.h>

enum { ST_TITLE, ST_PLAY, ST_PAUSE, ST_OVER };

u8 state;
u8 state_timer;

void main(void) {
    state = ST_TITLE;
    show_title();

    while (1) {
        pad_poll();

        switch (state) {
        case ST_TITLE:
            if (pad_pressed(0) & PAD_START) {
                rand_seed(frame_count() + 1);   /* 매판 다른 난수 */
                state = ST_PLAY;
                start_game();
            }
            break;

        case ST_PLAY:
            update_play();
            draw_actors();
            break;

        case ST_PAUSE:
            if (pad_pressed(0) & PAD_START) state = ST_PLAY;
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
```

`rand_seed(frame_count() + 1)`이 요령이다. 플레이어가 타이틀에서 기다린
프레임 수가 씨앗이 되므로 매번 다른 판이 된다.

---

## 2. 화면 전환

```c
void show_title(void) {
    ppu_off();                   /* 통째로 그릴 땐 렌더링을 끈다 */
    bg_clear(0);
    pal_load(PAL_TITLE);
    bg_text(11, 10, "MY GAME");
    bg_text(7, 17, "PRESS START");
    ppu_on();
    music_play(SONG_TITLE);
}
```

---

## 3. 중력과 가변 점프 높이

"A를 짧게 누르면 낮게 뛴다"의 전부는 **상승 중에 A를 떼면 속도를 깎는 것**이다.

```c
#define GRAVITY     3
#define JUMP_SPEED 72
#define JUMP_CUT   16
#define MAX_FALL   64

i8 vy;
u8 on_ground;
u8 jump_held;

if ((pad_pressed(0) & PAD_A) && on_ground) {
    vy = 0 - JUMP_SPEED;
    on_ground = 0;
    jump_held = 1;
    sfx_play(SFX_JUMP);
}
if (jump_held && (pad_released(0) & PAD_A)) {
    jump_held = 0;
    if (vy < 0 - JUMP_CUT) vy = 0 - JUMP_CUT;
}
if (vy >= 0) jump_held = 0;

if (vy < MAX_FALL) vy = vy + GRAVITY;
if (vy > MAX_FALL) vy = MAX_FALL;
```

`0 - JUMP_SPEED`로 쓴다. `-72`도 되지만 `u8` 상수와 섞일 때 의도가 분명하다.

---

## 4. 타일맵 충돌

한 픽셀씩 움직이고 매번 검사한다. 여러 픽셀을 한 번에 더하면 벽을 통과한다.

```c
#define CELL_PX 16
#define GRID_W  16
#define GRID_H  15

u8 level[240];
const u8 CELL_SOLID[8] = { 0, 1, 1, 1, 0, 0, 0, 0 };

u8 cell_x;
u8 cell_y;

u8 cell_at(u8 px, u8 py) {
    cell_x = px / CELL_PX;
    cell_y = py / CELL_PX;
    if (cell_x >= GRID_W) return 0;
    if (cell_y >= GRID_H) return 0;
    return level[cell_y * GRID_W + cell_x];
}

u8 solid_at(u8 px, u8 py) {
    return CELL_SOLID[cell_at(px, py)];
}

/* 오른쪽으로 한 픽셀. 막히면 0을 돌려준다. */
u8 step_right(void) {
    u8 nx;
    nx = hero.x + 1;
    if (solid_at(nx + BOX_R, hero.y + 1) ||
        solid_at(nx + BOX_R, hero.y + 8) ||
        solid_at(nx + BOX_R, hero.y + BOX_B)) return 0;
    hero.x = nx;
    return 1;
}
```

히트박스는 스프라이트보다 **안쪽으로 들여라**(`BOX_L`=3, `BOX_R`=12 등).
그래야 한 칸 틈을 지나갈 때 픽셀 단위로 정확하지 않아도 된다.

---

## 5. 액터 배열

```c
struct Actor {
    u8 x;
    u8 y;
    i8 vx;
    u8 alive;
};

struct Actor foes[MAX_FOES];
u8 foe_count;
u8 i;

void update_foes(void) {
    for (i = 0; i < foe_count; i++) {
        if (foes[i].alive == 0) continue;

        foes[i].x = foes[i].x + foes[i].vx;
        if (foes[i].x < 8 || foes[i].x > 240) {
            foes[i].vx = 0 - foes[i].vx;
        }
        if (box_hit(hero.x, hero.y, 12, 13, foes[i].x, foes[i].y, 12, 13)) {
            hero.alive = 0;
        }
    }
}
```

반복문 변수 `i`는 전역으로 두는 편이 낫다. 지역이어도 정적 할당이지만,
전역이면 중첩 호출에서 겹치지 않게 관리하기 쉽다.

---

## 6. 애니메이션

```c
u8 walk_timer;
u8 walk_frame;

if (moving && on_ground) {
    walk_timer = walk_timer + 1;
    if (walk_timer >= 7) {
        walk_timer = 0;
        walk_frame = walk_frame ^ 1;    /* 0 <-> 1 토글 */
    }
} else {
    walk_timer = 0;
    walk_frame = 0;
}

/* 프레임 카운터로 간단히 처리해도 된다 */
if (frame_count() & 8) {
    spr_meta(x, y, MS_FOE_A);
} else {
    spr_meta(x, y, MS_FOE_B);
}
```

---

## 7. HUD

바뀔 때만 다시 그린다. 매 프레임 그리면 배경 갱신 큐를 낭비한다.

```c
u8 hud_dirty;

void draw_hud(void) {
    bg_text(1, 1, "SCORE");
    bg_number(7, 1, score, 5);
    bg_text(20, 1, "LIFE");
    bg_number(25, 1, lives, 1);
}

/* 점수가 바뀌는 곳에서 */
score = score + 100;
hud_dirty = 1;

/* 루프 끝에서 */
if (hud_dirty) {
    draw_hud();
    hud_dirty = 0;
}
```

---

## 8. 가로 스크롤

세로 미러링이라 네임테이블 두 장이 좌우로 붙어 있다. `bg_tile`의 x는 0~63.

```c
u16 camera;

/* 시작할 때 화면 두 장 분량을 미리 그려 둔다 */
void draw_world(void) {
    u8 cx;
    ppu_off();
    for (cx = 0; cx < 32; cx++) {       /* 셀 0~31 = 화면 두 장 */
        draw_column(cx);
    }
    ppu_on();
}

/* 매 프레임 */
camera = camera + 1;
if (camera >= 512) camera = 0;
scroll_set(camera, 0);
```

화면이 512픽셀보다 긴 스테이지는 카메라가 지나간 뒤쪽 열을 앞쪽에 다시 그리는
방식(열 단위 갱신)이 필요하다. 한 프레임에 배경 32장까지 반영되므로,
한 프레임에 한 열(30장)을 그리면 딱 맞는다.

---

## 9. 7-bag 셔플

같은 것이 몰려 나오지 않는 무작위.

```c
u8 bag[7];
u8 bag_pos;

void refill_bag(void) {
    u8 pick;
    u8 swap;
    for (i = 0; i < 7; i++) bag[i] = i;
    for (i = 6; i > 0; i--) {           /* 피셔-예이츠 */
        pick = rand_range(i + 1);
        swap = bag[i];
        bag[i] = bag[pick];
        bag[pick] = swap;
    }
    bag_pos = 0;
}

u8 take_piece(void) {
    if (bag_pos >= 7) refill_bag();
    bag_pos = bag_pos + 1;
    return bag[bag_pos - 1];
}
```

---

## 10. 페이드 인 / 아웃

```c
void fade_out(void) {
    u8 level;
    for (level = 4; level > 0; level--) {
        pal_bright(level - 1);
        wait_vblank();
        wait_vblank();
        wait_vblank();
    }
}

void fade_in(void) {
    u8 level;
    for (level = 0; level < 5; level++) {
        pal_bright(level);
        wait_vblank();
        wait_vblank();
        wait_vblank();
    }
}
```

---

## 11. 입력 자동 반복 (DAS)

방향키를 누르고 있을 때 처음엔 한 번, 잠시 뒤부터 빠르게 반복.

```c
#define DAS_DELAY 16
#define DAS_RATE   6

u8 das_timer;
u8 das_dir;

void handle_das(u8 pad) {
    u8 dir;
    dir = 0;
    if (pad & PAD_LEFT)  dir = 1;
    if (pad & PAD_RIGHT) dir = 2;

    if (dir == 0) { das_dir = 0; das_timer = 0; return; }

    if (dir != das_dir) {            /* 처음 눌림 */
        das_dir = dir;
        das_timer = DAS_DELAY;
        move(dir);
        return;
    }
    das_timer = das_timer - 1;
    if (das_timer == 0) {            /* 자동 반복 */
        das_timer = DAS_RATE;
        move(dir);
    }
}
```

---

## 12. 짧은 BGM 쓰기

```c
asset song SONG_MAIN = { 9,     /* 한 행이 9프레임 = 초당 6.7행 */
    /* 펄스1(멜로디), 펄스2(화음), 삼각파(베이스), 노이즈(타악) */
    { N_C5, N_E4, N_C2, NOISE_KICK  },
    { HOLD, HOLD, HOLD, 0           },   /* HOLD = 앞 음 유지 */
    { N_E5, N_G4, HOLD, NOISE_HAT   },
    { HOLD, HOLD, HOLD, 0           },
    { N_G5, N_C5, N_G2, NOISE_SNARE },
    { HOLD, HOLD, HOLD, 0           },
    { N_E5, N_G4, HOLD, NOISE_HAT   },
    { 0,    0,    0,    0           }    /* 0 = 쉼표 */
};
```

- 마디를 4행 또는 8행으로 맞추면 듣기에 자연스럽다.
- 베이스(삼각파)는 멜로디보다 2옥타브 아래에서 코드 근음을 짚으면 된다.
- 타악기: `NOISE_KICK`(1·3박) + `NOISE_SNARE`(2·4박) + 나머지에 `NOISE_HAT` 이면 기본이 된다.
  `NOISE_HAT_OPEN` `NOISE_TOM` `NOISE_CYMBAL` 도 있다.
- 곡은 끝나면 자동으로 처음으로 돌아간다.

### 정수가 아닌 템포

BPM 을 프레임으로 나누면 대개 딱 떨어지지 않는다. 두 번째 숫자가 1/256 프레임
단위 소수부다.

```
행당 프레임 = 3600 / (BPM * 행당박자분할)
예) 138 BPM, 16분음표(박당 4행) -> 3600 / (138*4) = 6.52 -> { 6, 134, ... }
```

### 긴 곡

행이 수백 개를 넘으면 별도 파일로 빼고 include 한다. asset 선언은 어느 파일에
있든 같다.

```c
#include "mysong.c"     /* asset song SONG_BGM = { ... }; 이 안에 있다 */
```

`examples/tetris_song.c` 가 2448행(4분 26초)짜리 실제 예다.

---

## 13. 효과음 만들기

```c
/* 올라가는 소리 = 점프, 획득 */
asset sfx SFX_JUMP = { {13, N_C5}, {12, N_E5}, {10, N_G5}, {7, N_C6}, {4, N_E6} };

/* 내려가는 소리 = 피격, 실패 */
asset sfx SFX_HURT = { {14, N_G3}, {12, N_E3}, {9, N_C3}, {5, N_A2}, {2, N_A2} };

/* 짧고 낮은 소리 = 착지, 고정 */
asset sfx SFX_LOCK = { {9, N_C3}, {6, N_G2}, {3, N_C2} };

/* 딸깍 = 커서 이동 */
asset sfx SFX_MOVE = { {6, N_C5}, {3, N_C5} };
```

볼륨을 끝으로 갈수록 줄이면 자연스럽게 사라진다. 한 항목이 한 프레임(1/60초)이니,
5항목이면 약 0.08초다.
