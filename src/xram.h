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
/* Cover/manual/outro state: phase (0 game, 1 in, 2 wait, 3 out, 4 black), level 0..63.
 * The cover uses $0280 config, $0400 palette, $0600 staging and $1000..$F0FF
 * pixels before game initialization and after audio stops on exit. */
#define XRAM_COVER_STATE 0x00B0
/* Only on the startup cover: OPL register page at $0100, score at $F100.
 * Both are released before the manual/game uses these regions. The player
 * and shared screen helpers temporarily occupy reset_tiles in CPU RAM. */
#define XRAM_INTRO_OPL 0x0100
#define XRAM_INTRO_SCORE 0xF100
/* Scene: 0 cover, 1 outro, 2 manual. */
#define XRAM_COVER_SCENE 0x00B4
/* F1 return data, above the last manual pixel ($F0FF). */
#define XRAM_HELP_TERRAIN_COLORS 0xF100
#define XRAM_HELP_VIDEO 0xF200
#define HELP_VIDEO_BYTES 0x700
_Static_assert(XRAM_HELP_TERRAIN_COLORS + 192 <= XRAM_HELP_VIDEO, "Help backup overlaps");
_Static_assert(XRAM_HELP_VIDEO + HELP_VIDEO_BYTES <= 65536UL, "Help backup exceeds XRAM");
/* Game fade: level 0 black .. 32 full, then VSYNC; startup-only scratch. */
#define XRAM_GAME_FADE_LEVEL 0x00B2
#define XRAM_GAME_FADE_SOURCE 0xD000
#define XRAM_GAME_FADE_STAGING 0xD300
/* Cover/manual/outro text; these regions hold terrain during gameplay. */
#define XRAM_COVER_PROMPT_CONFIG 0x02A0
#define XRAM_COVER_PROMPT_IMAGE 0x0800
#define XRAM_COVER_PROMPT_PALETTE 0x0850
#define XRAM_OUTRO_PROMPT_IMAGE 0x0900
#define XRAM_PALETTE 0x0100
#define XRAM_PSG 0x0180
/* PCM extension: mono signed 8-bit, 8000 Hz, 2048-byte ring after header.
 * Initialized after the cover, whose pixels temporarily occupy this space. */
#define XRAM_PCM 0xC000
/* OPL2 reuses this page only when PCM is not selected. */
#define XRAM_OPL XRAM_PCM
_Static_assert(XRAM_PCM + 64 + 2048 <= XRAM_GAME_FADE_SOURCE, "Fade overlaps audio");
_Static_assert(XRAM_GAME_FADE_SOURCE + 576 <= XRAM_GAME_FADE_STAGING, "Fade buffers overlap");
_Static_assert(XRAM_GAME_FADE_STAGING + 576 <= 65536UL, "Fade scratch overflow");
#define XRAM_TERRAIN_CONFIG 0x0200
#define XRAM_SOUND_CONFIG 0x0220
#define XRAM_SOUND_ICON_CONFIG 0x0230
#define XRAM_SOUND_ICON 0x02C0
#define XRAM_SOUND_TEXT 0x02C8
#define XRAM_SPRITES 0x0300
#define XRAM_HUD_SPRITES 0x0600
#define XRAM_LOGO_PALETTE 0x0700
#define XRAM_DEMO_FOOTER_PALETTE 0x0720
#define XRAM_DUO_HUD_P1_PALETTE 0x0740
#define XRAM_DUO_HUD_P2_PALETTE 0x0760
#define XRAM_HUD_BLACK_PALETTE 0x05A0
#define XRAM_TERRAIN 0x0800
#define XRAM_TILES 0x2700
#define XRAM_LOGO_IMAGE 0x5A00
#define XRAM_SMALL_MOUNTAIN 0x3600
#define XRAM_MEDIUM_MOUNTAIN 0x5800
#define XRAM_STEPPED_MOUNTAIN 0x5C00
#define XRAM_WIDE_MOUNTAIN 0x5E00
#define XRAM_BRIDGE_IMAGE 0x6000
#define XRAM_IMAGES 0x8000
#define XRAM_SPRITE_PALETTES 0x0400
#define XRAM_JET_PALETTE 0x0580
/* Reserve sprites use only indices 0 and 11. Alias ink 11 to jet ink 1;
 * index 0 is in the unused palette slot before the jet palette. */
#define XRAM_GAME2_LIFE_PALETTE 0x056C
#define XRAM_DUO_PALETTE 0x0584
#define XRAM_DUO_JETS 0x6300
#define XRAM_DUO_LIFE_SPRITES 0x6400
#define DUO_LIFE_SPRITE_COUNT 20
/* Two packed duo_player_t snapshots, published with the normal diagnostics. */
#define XRAM_DUO_STATE 0x00C0
#define XRAM_HUD_BITMAP_CONFIG 0x0240
#define XRAM_DEMO_FOOTER_CONFIG 0x0260
#define XRAM_DEMO_FOOTER_IMAGE 0x3800
#define XRAM_HUD 0xA000
#define XRAM_HUD_DIGITS 0x9B00
#define XRAM_BALLOON_IMAGE 0x9D00
#define XRAM_TANK_IMAGE 0x9D80
#define XRAM_TANK_SHELL 0xBE00
#define XRAM_TANK_BLAST 0xBE10
#define XRAM_TANK_CIRCLES 0xBE30
#define XRAM_TANK_IMAGE_ALT 0xBF00
#define XRAM_TANK_EXPLOSION_PALETTE 0xBF80
#define XRAM_HELICOPTER_SHOT 0xBF90
#define XRAM_TANK_IMAGE_ALT2 0xBFA0
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
#define TERRAIN_TILE_COUNT 117
#define TERRAIN_ROAD_UPPER 116
#define TERRAIN_BANK_SOLID 7
#define HUD_SPRITE_COUNT 19
#define XRAM_RESERVE_IMAGE (XRAM_HUD_DIGITS + 12 * 32)
#define ROAD_SHOT_SPRITE 22
#define PLAYER_SPRITE 23
#define SPRITE_COUNT 25
#define OBJECT_IMAGE_COUNT 13
#define BALLOON_ID 11
#define TANK_ID 12
#define TANK_WIDTH 9
#define TANK_HEIGHT 9
#define TANK_TOP 8
#define TANK_MUZZLE_Y (TANK_TOP + 1)
#define TANK_TRACK_BOTTOM_Y (TANK_TOP + TANK_HEIGHT - 1)
#define TANK_IMAGE_WIDTH 12
#define TANK_IMAGE_HEIGHT 16
#define TANK_IMAGE_BYTES (TANK_IMAGE_WIDTH * TANK_IMAGE_HEIGHT / 2)
#define IMAGE_BYTES 512
#define HUD_BYTES (RIVER_WIDTH * HUD_HEIGHT)

_Static_assert(sizeof(bitmap_config_t) == 14, "PIX bitmap layout");
_Static_assert(sizeof(tile_config_t) == 16, "PIX tile layout");
_Static_assert(sizeof(character_config_t) == 16, "PIX text layout");
_Static_assert(XRAM_SOUND_CONFIG + sizeof(character_config_t) <= XRAM_SOUND_ICON_CONFIG, "Sound configs overlap");
_Static_assert(XRAM_SOUND_ICON_CONFIG + sizeof(bitmap_config_t) <= XRAM_HUD_BITMAP_CONFIG, "Sound icon config overlaps HUD");
_Static_assert(XRAM_SOUND_ICON + 8 == XRAM_SOUND_TEXT, "Sound icon must precede text");
_Static_assert(XRAM_SOUND_TEXT + 4 <= XRAM_SPRITES, "Sound text overlaps sprites");
_Static_assert(sizeof(sprite_t) == 10, "PIX sprite layout");
_Static_assert(sizeof(oscillator_t) == 8, "PIX PSG layout");
_Static_assert(XRAM_GAME2_LIFE_PALETTE >= XRAM_SPRITE_PALETTES + 11 * 32, "GAME 2 life palette overlaps objects");
_Static_assert(XRAM_GAME2_LIFE_PALETTE + 11 * 2 == XRAM_JET_PALETTE + 2, "GAME 2 lives must share jet ink");
_Static_assert(XRAM_PSG % 256 + 64 <= 256, "PSG page boundary");
_Static_assert(XRAM_TERRAIN + TERRAIN_COLUMNS * RIVER_RING <= XRAM_TILES, "Terrain overlaps tiles");
_Static_assert(XRAM_TILES + TERRAIN_TILE_COUNT * 32 <= XRAM_IMAGES, "Tiles overlap sprites");
_Static_assert(XRAM_TILES + TERRAIN_TILE_COUNT * 32 <= XRAM_LOGO_IMAGE, "Tiles overlap logo");
_Static_assert(XRAM_LOGO_IMAGE + 256 <= XRAM_IMAGES, "Logo overlaps sprites");
_Static_assert(XRAM_TILES + TERRAIN_TILE_COUNT * 32 <= XRAM_SMALL_MOUNTAIN, "Tiles overlap mountain");
_Static_assert(XRAM_MEDIUM_MOUNTAIN + IMAGE_BYTES <= XRAM_LOGO_IMAGE, "Mountain overlaps logo");
_Static_assert(XRAM_LOGO_IMAGE + 256 <= XRAM_STEPPED_MOUNTAIN, "Logo overlaps stepped mountain");
_Static_assert(XRAM_STEPPED_MOUNTAIN + IMAGE_BYTES <= XRAM_WIDE_MOUNTAIN, "Mountain images overlap");
_Static_assert(XRAM_WIDE_MOUNTAIN + IMAGE_BYTES <= XRAM_BRIDGE_IMAGE, "Mountain overlaps bridge");
_Static_assert(XRAM_LOGO_IMAGE + 256 <= XRAM_BRIDGE_IMAGE, "Logo overlaps bridge");
_Static_assert(XRAM_BRIDGE_IMAGE + 48 * 32 / 2 <= XRAM_IMAGES, "Bridge overlaps sprites");
_Static_assert(XRAM_BRIDGE_IMAGE + 48 * 32 / 2 <= XRAM_DUO_JETS, "Bridge overlaps DUO");
_Static_assert(XRAM_DUO_JETS + 3 * 80 <= XRAM_IMAGES, "DUO overlaps images");
_Static_assert(XRAM_DUO_JETS + 3 * 80 <= XRAM_DUO_LIFE_SPRITES, "DUO planes overlap life sprites");
_Static_assert(XRAM_DUO_LIFE_SPRITES + DUO_LIFE_SPRITE_COUNT * 10 <= XRAM_IMAGES, "DUO lives overlap images");
_Static_assert(XRAM_DUO_STATE + 46 <= XRAM_PALETTE, "DUO state overlaps palette");
_Static_assert(XRAM_SMALL_MOUNTAIN + IMAGE_BYTES <= XRAM_IMAGES, "Mountain overlaps sprites");
_Static_assert(XRAM_SMALL_MOUNTAIN + IMAGE_BYTES <= XRAM_DEMO_FOOTER_IMAGE, "Mountain overlaps demo footer");
_Static_assert(XRAM_MEDIUM_MOUNTAIN + IMAGE_BYTES <= XRAM_IMAGES, "Medium mountain overlaps sprites");
_Static_assert(XRAM_IMAGES + 11 * IMAGE_BYTES + 96 + 1024 <= XRAM_HUD, "Sprite image overlap");
_Static_assert(XRAM_IMAGES + 11 * IMAGE_BYTES + 96 + 1024 <= XRAM_HUD_DIGITS, "Digit image overlap");
_Static_assert(XRAM_RESERVE_IMAGE + 32 <= XRAM_HUD, "Digits overlap HUD");
_Static_assert(XRAM_RESERVE_IMAGE + 32 <= XRAM_BALLOON_IMAGE, "Reserve overlaps balloon");
_Static_assert(XRAM_BALLOON_IMAGE + 128 <= XRAM_TANK_IMAGE, "Balloon overlaps tank");
_Static_assert(XRAM_TANK_IMAGE + TANK_IMAGE_BYTES <= XRAM_SCORE_DIGITS, "Tank overlaps score digits");
_Static_assert(XRAM_GAME_DIGITS + 2 * 32 <= XRAM_HUD, "Game digits overlap HUD");
_Static_assert(XRAM_SPRITES + SPRITE_COUNT * 10 <= XRAM_SPRITE_PALETTES, "Sprites overlap palettes");
_Static_assert(XRAM_TANK_PALETTE + 32 <= XRAM_HUD_SPRITES, "Tank palette overlaps HUD sprites");
_Static_assert(XRAM_HUD_SPRITES + HUD_SPRITE_COUNT * 10 <= XRAM_TERRAIN, "HUD sprites overlap terrain");
_Static_assert(XRAM_HUD_SPRITES + HUD_SPRITE_COUNT * 10 <= XRAM_LOGO_PALETTE, "HUD sprites overlap logo palette");
_Static_assert(XRAM_LOGO_PALETTE + 14 <= XRAM_TERRAIN, "Logo palette overlaps terrain");
_Static_assert(XRAM_LOGO_PALETTE + 14 <= XRAM_DEMO_FOOTER_PALETTE, "Logo overlaps demo palette");
_Static_assert(XRAM_DEMO_FOOTER_PALETTE + 14 <= XRAM_TERRAIN, "Demo palette overlaps terrain");
_Static_assert(XRAM_DEMO_FOOTER_PALETTE + 14 <= XRAM_DUO_HUD_P1_PALETTE, "Demo overlaps DUO HUD");
_Static_assert(XRAM_DUO_HUD_P1_PALETTE + 32 <= XRAM_DUO_HUD_P2_PALETTE, "DUO HUD palettes overlap");
_Static_assert(XRAM_DUO_HUD_P2_PALETTE + 32 <= XRAM_TERRAIN, "DUO HUD overlaps terrain");
_Static_assert(XRAM_HUD + HUD_BYTES <= 65536UL, "XRAM overflow");
_Static_assert(XRAM_HUD + HUD_BYTES <= XRAM_TANK_SHELL, "HUD overlaps tank shell");
_Static_assert(XRAM_TANK_SHELL + 16 <= XRAM_TANK_BLAST, "Shell overlaps blast");
_Static_assert(XRAM_TANK_BLAST + 32 <= 65536UL, "Tank blast overflow");
_Static_assert(XRAM_TANK_BLAST + 32 <= XRAM_TANK_CIRCLES, "Tank blast overlaps circles");
_Static_assert(XRAM_TANK_CIRCLES + 3 * 64 <= XRAM_TANK_IMAGE_ALT, "Tank circles overlap animation");
_Static_assert(XRAM_TANK_IMAGE_ALT + TANK_IMAGE_BYTES <= XRAM_TANK_EXPLOSION_PALETTE, "Tank animation overlaps explosion palette");
_Static_assert(XRAM_TANK_EXPLOSION_PALETTE + 4 <= 65536UL, "Tank explosion palette overflow");
_Static_assert(XRAM_TANK_EXPLOSION_PALETTE + 4 <= XRAM_HELICOPTER_SHOT, "Tank palette overlaps helicopter shot");
_Static_assert(XRAM_HELICOPTER_SHOT + 16 <= 65536UL, "Helicopter shot overflow");
_Static_assert(XRAM_HELICOPTER_SHOT + 16 <= XRAM_TANK_IMAGE_ALT2, "Helicopter shot overlaps tank animation");
_Static_assert(XRAM_TANK_IMAGE_ALT2 + TANK_IMAGE_BYTES <= XRAM_PCM, "Tank animation overlaps PCM");
_Static_assert(XRAM_PCM + 8 + 2048 <= 65536UL, "PCM ring overflow");
_Static_assert(XRAM_OPL % 256 == 0, "OPL page alignment");
#endif
