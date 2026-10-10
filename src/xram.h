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
#define XRAM_PALETTE 0x0100
#define XRAM_PSG 0x0180
#define XRAM_BITMAP_CONFIG 0x0200
#define XRAM_HUD_CONFIG 0x0220
#define XRAM_SPRITES 0x0300
#define XRAM_BITMAP 0x0800
#define XRAM_IMAGES 0x8000
#define XRAM_SPRITE_PALETTES 0x0400
#define XRAM_JET_PALETTE 0x0580
#define XRAM_HUD_BITMAP_CONFIG 0x0240
#define XRAM_HUD 0xA000

#define RIVER_WIDTH 160
#define RIVER_HEIGHT 160
#define RIVER_RING 192
#define SPRITE_COUNT 10
#define IMAGE_BYTES 512
#define HUD_BYTES (160 * 64)

_Static_assert(sizeof(bitmap_config_t) == 14, "PIX bitmap layout");
_Static_assert(sizeof(character_config_t) == 16, "PIX text layout");
_Static_assert(sizeof(sprite_t) == 10, "PIX sprite layout");
_Static_assert(sizeof(oscillator_t) == 8, "PIX PSG layout");
_Static_assert(XRAM_PSG % 256 + 64 <= 256, "PSG page boundary");
_Static_assert(XRAM_BITMAP + RIVER_WIDTH * (unsigned)RIVER_RING <= XRAM_IMAGES, "Bitmap overlaps sprites");
_Static_assert(XRAM_IMAGES + 11 * IMAGE_BYTES + 96 + 1024 <= XRAM_HUD, "Sprite image overlap");
_Static_assert(XRAM_HUD + HUD_BYTES <= 65536UL, "XRAM overflow");
#endif
