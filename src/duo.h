#ifndef RIVER_DUO_H
#define RIVER_DUO_H

/* First 19 bytes map to the native per-player registers in duo.asm.
 * Lives are decimal glyph offsets (8 per life), just like native scoring.
 * States: 0 eliminated, 1 flying, 2 waiting for bridge, 3 awaiting safe space. */
typedef struct {
    uint8_t missile_y, x, speed_x, speed_y, fuel_hi, fuel_lo;
    uint16_t shape;
    uint8_t lives, joystick, accel, reflect, missile_x, score[6];
    uint8_t state, timer, spawn_x;
} duo_player_t;
_Static_assert(sizeof(duo_player_t)==22, "DUO native register layout");
static duo_player_t duo_players[2];
uint8_t duo_call, duo_dead;
static uint8_t duo_started, duo_bridge, duo_turn, duo_over;
static duo_player_t *duo_p;
extern const uint8_t rr_JetStraight[], rr_JetMove[], rr_JetExplode[];
void rr_duo_player(void);
void __fastcall__ duo_load(duo_player_t *p);
void __fastcall__ duo_save(duo_player_t *p);
void duo_tick(void);
void hud_clear(void);
static void duo_render(void);
static void duo_hud(void);
static void hud_layout(void);
static void update_high_score(void);
#endif
