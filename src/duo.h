#ifndef RIVER_DUO_H
#define RIVER_DUO_H

/* First 19 bytes map to the native per-player registers in duo.asm.
 * Lives are decimal glyph offsets (8 per life), just like native scoring.
 * States: 0 eliminated, 1 flying, 2 waiting for bridge, 3 awaiting safe space. */
typedef struct {
    uint8_t missile_y, x, speed_x, speed_y, fuel_hi, fuel_lo;
    uint16_t shape;
    uint8_t lives, joystick, accel, reflect, missile_x, score[6];
    uint8_t state, timer, spawn_x, y;
} duo_player_t;
_Static_assert(sizeof(duo_player_t)==23, "DUO native register layout");
static duo_player_t duo_players[2];
uint8_t duo_call, duo_dead;
/* Screen Y of the current collision context; native modes always use 142. */
uint8_t player_y=142;
#define DUO_LEAD (4*18)
#define DUO_MAX_LIVES 10
/* Relative distance in 1/128 logical pixels; positive means P1 leads. */
static int16_t duo_gap;
static uint8_t duo_started, duo_bridge, duo_turn, duo_over, duo_restart;
static duo_player_t *duo_p;
extern const uint8_t rr_JetStraight[], rr_JetMove[], rr_JetExplode[];
void rr_duo_player(void);
void rr_duo_restart(void);
void __fastcall__ duo_load(duo_player_t *p);
void __fastcall__ duo_save(duo_player_t *p);
void __fastcall__ duo_fuel_row(const uint8_t *pixels);
void duo_tick(void);
void hud_clear(void);
static void duo_render(void);
static void duo_hud(void);
static void hud_layout(void);
static void update_high_score(void);
#endif
