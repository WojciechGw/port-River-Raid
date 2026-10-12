#ifndef XRAM_H
#define XRAM_H
#include <stdint.h>
/* Packed PIX layouts from the VGA and RIA datasheets. */
typedef struct {
    uint8_t x_wrap, y_wrap;
    int16_t x_pos_px, y_pos_px, width_px, height_px;
    uint16_t data, palette;
} bitmap_config_t;
typedef struct {
    uint8_t x_wrap, y_wrap;
    int16_t x_pos_px, y_pos_px, width_tiles, height_tiles;
    uint16_t data, palette, tiles;
} tile_config_t;
typedef struct {
    uint8_t x_wrap, y_wrap;
    int16_t x_pos_px, y_pos_px, width_chars, height_chars;
    uint16_t data, palette, font;
} character_config_t;
typedef struct {
    int16_t x, y;
    uint16_t image, palette;
    uint8_t size, options;
} sprite_t;
typedef struct {
    uint16_t freq;
    uint8_t duty, attack, decay, release_wave, pan_gate, reserved;
} oscillator_t;

#define XRAM_KEYBOARD 0x0000
#define XRAM_GAMEPADS 0x0020
/* Observable state for scripted emulator checks; see tests/README.md. */
#define XRAM_STATE 0x0080
/* Optional RIVER_PROFILE maxima; see tests/README.md. */
#define XRAM_TIMING 0x00A0
/* Startup-only state: phase (0 game, 1 in, 2 wait, 3 out, 4 black), level 0..63.
 * The cover uses $0280 config, $0400 palette, $0600 staging and $1000..$F0FF
 * pixels before game initialization. Game graphics reuse these regions. */
#define XRAM_COVER_STATE 0x00B0
/* Startup-only prompt, before the game reuses these XRAM regions. */
#define XRAM_COVER_PROMPT_CONFIG 0x02A0
#define XRAM_COVER_PROMPT_IMAGE 0x0800
#define XRAM_COVER_PROMPT_PALETTE 0x0850
#define XRAM_PALETTE 0x0100
#define XRAM_PSG 0x0180
#define XRAM_TERRAIN_CONFIG 0x0200
#define XRAM_HUD_CONFIG 0x0220
#define XRAM_SPRITES 0x0300
#define XRAM_HUD_SPRITES 0x0600
#define XRAM_LOGO_PALETTE 0x0700
#define XRAM_DEMO_FOOTER_PALETTE 0x0720
#define XRAM_HUD_BLACK_PALETTE 0x05A0
#define XRAM_TERRAIN 0x0800
#define XRAM_TILES 0x2700
#define XRAM_LOGO_IMAGE 0x3400
#define XRAM_SMALL_MOUNTAIN 0x3600
#define XRAM_MEDIUM_MOUNTAIN 0x5800
#define XRAM_IMAGES 0x8000
#define XRAM_SPRITE_PALETTES 0x0400
#define XRAM_JET_PALETTE 0x0580
#define XRAM_HUD_BITMAP_CONFIG 0x0240
#define XRAM_DEMO_FOOTER_CONFIG 0x0260
#define XRAM_DEMO_FOOTER_IMAGE 0x3800
#define XRAM_HUD 0xA000
#define XRAM_HUD_DIGITS 0x9B00
#define XRAM_BALLOON_IMAGE 0x9D00
#define XRAM_TANK_IMAGE 0x9D80
#define XRAM_SCORE_DIGITS 0x9E00
#define XRAM_GAME_DIGITS (XRAM_SCORE_DIGITS + 12 * 32)
#define XRAM_BALLOON_PALETTE 0x05C0
#define XRAM_TANK_PALETTE 0x05E0

#define RIVER_WIDTH 160
#define RIVER_HEIGHT 160
#define RIVER_TOP 21
#define HUD_TOP (RIVER_TOP + RIVER_HEIGHT + 1)
#define HUD_PANEL_HEIGHT 37
#define HUD_HEIGHT 48
#define RIVER_RING 192
#define TERRAIN_COLUMNS (RIVER_WIDTH / 4)
#define TERRAIN_TILE_COUNT 98
#define TERRAIN_BANK_SOLID 7
#define HUD_SPRITE_COUNT 19
#define XRAM_RESERVE_IMAGE (XRAM_HUD_DIGITS + 12 * 32)
#define SPRITE_COUNT 16
#define OBJECT_IMAGE_COUNT 13
#define BALLOON_ID 11
#define TANK_ID 12
#define IMAGE_BYTES 512
#define HUD_BYTES (RIVER_WIDTH * HUD_HEIGHT)

_Static_assert(sizeof(bitmap_config_t) == 14, "PIX bitmap layout");
_Static_assert(sizeof(tile_config_t) == 16, "PIX tile layout");
_Static_assert(sizeof(character_config_t) == 16, "PIX text layout");
_Static_assert(sizeof(sprite_t) == 10, "PIX sprite layout");
_Static_assert(sizeof(oscillator_t) == 8, "PIX PSG layout");
_Static_assert(XRAM_PSG % 256 + 64 <= 256, "PSG page boundary");
_Static_assert(XRAM_TERRAIN + TERRAIN_COLUMNS * RIVER_RING <= XRAM_TILES, "Terrain overlaps tiles");
_Static_assert(XRAM_TILES + TERRAIN_TILE_COUNT * 32 <= XRAM_IMAGES, "Tiles overlap sprites");
_Static_assert(XRAM_TILES + TERRAIN_TILE_COUNT * 32 <= XRAM_LOGO_IMAGE, "Tiles overlap logo");
_Static_assert(XRAM_LOGO_IMAGE + 240 <= XRAM_IMAGES, "Logo overlaps sprites");
_Static_assert(XRAM_LOGO_IMAGE + 240 <= XRAM_SMALL_MOUNTAIN, "Logo overlaps mountain");
_Static_assert(XRAM_SMALL_MOUNTAIN + IMAGE_BYTES <= XRAM_IMAGES, "Mountain overlaps sprites");
_Static_assert(XRAM_SMALL_MOUNTAIN + IMAGE_BYTES <= XRAM_DEMO_FOOTER_IMAGE, "Mountain overlaps demo footer");
_Static_assert(XRAM_MEDIUM_MOUNTAIN + IMAGE_BYTES <= XRAM_IMAGES, "Medium mountain overlaps sprites");
_Static_assert(XRAM_IMAGES + 11 * IMAGE_BYTES + 96 + 1024 <= XRAM_HUD, "Sprite image overlap");
_Static_assert(XRAM_IMAGES + 11 * IMAGE_BYTES + 96 + 1024 <= XRAM_HUD_DIGITS, "Digit image overlap");
_Static_assert(XRAM_RESERVE_IMAGE + 32 <= XRAM_HUD, "Digits overlap HUD");
_Static_assert(XRAM_RESERVE_IMAGE + 32 <= XRAM_BALLOON_IMAGE, "Reserve overlaps balloon");
_Static_assert(XRAM_BALLOON_IMAGE + 128 <= XRAM_TANK_IMAGE, "Balloon overlaps tank");
_Static_assert(XRAM_TANK_IMAGE + 128 <= XRAM_SCORE_DIGITS, "Tank overlaps score digits");
_Static_assert(XRAM_GAME_DIGITS + 2 * 32 <= XRAM_HUD, "Game digits overlap HUD");
_Static_assert(XRAM_SPRITES + SPRITE_COUNT * 10 <= XRAM_SPRITE_PALETTES, "Sprites overlap palettes");
_Static_assert(XRAM_TANK_PALETTE + 32 <= XRAM_HUD_SPRITES, "Tank palette overlaps HUD sprites");
_Static_assert(XRAM_HUD_SPRITES + HUD_SPRITE_COUNT * 10 <= XRAM_TERRAIN, "HUD sprites overlap terrain");
_Static_assert(XRAM_HUD_SPRITES + HUD_SPRITE_COUNT * 10 <= XRAM_LOGO_PALETTE, "HUD sprites overlap logo palette");
_Static_assert(XRAM_LOGO_PALETTE + 14 <= XRAM_TERRAIN, "Logo palette overlaps terrain");
_Static_assert(XRAM_LOGO_PALETTE + 14 <= XRAM_DEMO_FOOTER_PALETTE, "Logo overlaps demo palette");
_Static_assert(XRAM_DEMO_FOOTER_PALETTE + 14 <= XRAM_TERRAIN, "Demo palette overlaps terrain");
_Static_assert(XRAM_HUD + HUD_BYTES <= 65536UL, "XRAM overflow");
#endif
