#ifndef RIVER_GRAPHICS_H
#define RIVER_GRAPHICS_H

/* Readable demo-footer text and thick 6-column glyphs are in src/demo-footer.json.
 * tools/make_demo_footer.py combines them with this reference logo. */

/* Exact pixels from original/Atari 5200/river_raid_5.gif, x=48..167,
 * y=211..217. One character = two canvas pixels; the last row pads the
 * 60x7 logical image to the VGA sprite's 60x8 storage size.
 * . = transparent/black; A = purple, B = lettering, C = orange,
 * D = yellow, E = green, F = blue. */
static const char activision_logo[8][61] = {
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB.BBBBBBBB....BBBBBBB.........",
    "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCBB....B...B...BB...............",
    "CCCCCCCCCCCCCCCCCCCCCCCCCCCCBBB.BB.B.B.B..BB..BBB.B.BBB.B..B",
    "DDDDDDDDDDDDDDDDDDDDDDDDDDDBB.B.B..B.B.B.BB.B.B...B.B.B.BB.B",
    "EEEEEEEEEEEEEEEEEEEEEEEEEEBBBBB.B..B.B.BBB..B.BBB.B.B.B.BBBB",
    "EEEEEEEEEEEEEEEEEEEEEEEEEBB...B.B..B.B.BB...B...B.B.B.B.B.BB",
    "FFFFFFFFFFFFFFFFFFFFFFFFBB....B.BB.B.B.B....B.BBB.B.BBB.B..B",
    "............................................................"
};
/* GIF RGB colors rounded to the nearest RGB555 components. */
static const uint8_t activision_colors[6][3] = {
    {13,4,15},   /* (106,33,120) */
    {23,23,23}, /* (192,192,192) */
    {19,10,0},  /* (159,82,3) */
    {26,19,1},  /* (216,160,12) */
    {13,15,0},  /* (107,120,0) */
    {1,8,26}    /* (8,64,212) */
};
/* Original color roles used when B&W or screensaver filtering is active. */
static const uint8_t activision_color_roles[6]={0x66,0x0c,0x24,0x1a,0xb6,0x84};

/* Atari 5200 references: original/Atari 5200/s_RiverRaid_*.png.
 * RGB555 samples of the flat, lossless PNG colors. The first byte is the
 * original TIA color role, so B&W and the original screensaver still work.
 * Terrain tones are adjusted for darker land and brighter blue water;
 * ship and helicopter greens are tuned for their respective sprites. */
static const uint8_t reference_colors[][4] = {
    {0x00,0,0,0}, {0x04,7,7,7}, {0x06,11,11,11}, {0x08,15,15,15},
    {0x0c,22,22,22}, {0x10,9,9,0}, {0x12,13,13,2}, {0x14,17,16,4},
    {0x18,23,23,7}, {0x1c,31,28,16}, {0x1e,31,28,16},
    {0x20,9,0,0}, {0x2a,29,25,13}, {0x32,13,0,0}, {0x38,31,18,13}, {0x48,23,6,15},
    {0x80,0,4,16}, {0x84,1,9,23}, {0x8c,15,21,30}, {0x9c,16,24,29},
    {0xa8,5,20,19}, {0xac,16,27,29}, {0xb0,0,7,0}, {0xba,12,26,10},
    {0xd2,1,9,0}, {0xd6,6,14,2}, {0xda,19,25,12},
    {0xd8,21,25,8}, {0xc8,13,28,14}, {0xb8,10,27,18}, {0xa6,9,24,22},
    {0x96,9,20,26}, {0x86,16,12,28}, {0x76,20,10,27}, {0x56,27,10,19},
    {0x46,28,13,15}, {0x36,24,13,7}, {0x26,22,18,5}, {0x22,13,2,0},
    {0x24,10,6,0}, {0x28,14,10,0}, {0x2e,21,17,5} /* 5200 bridge beams */
};

/* 5200 bridge, top to bottom, at block rows 8..24. Each digit fills all
 * eight native columns (48 logical pixels); 5 draws only ..5..5.. supports.
 * 1 = red-brown rim, 2 = dark beam, 3 = light beam, 4 = gold stripe,
 * 5 = black support. Beam profile sampled from s_RiverRaid_2.png,
 * x=260..387, y=70..103; widen to cover the port's river and both banks. */
#pragma rodata-name(push, "SPLASH")
static const uint8_t bridge_rows[17]={
    1,       /* 11111111 */
    2,       /* 22222222 */
    3,3,     /* 33333333 */
    2,2,     /* 22222222 */
    4,4,     /* 44444444 */
    3,3,     /* 33333333 */
    2,2,     /* 22222222 */
    3,3,     /* 33333333 */
    1,       /* 11111111 */
    5,5      /* ..5..5.. */
};
static const uint8_t bridge_colors[6]={0,0x22,0x24,0x28,0x2e,0x00};
#pragma rodata-name(pop)
/* Twenty approach-road rows, starting at block row 6. 4 = dark edge,
 * 7 = upper gray, 6 = pale center line, 5 = lower gray. */
static const uint8_t bridge_road[20]={
    4,4,4,7,7,7,7,7,6,6,5,5,5,5,5,5,4,4,4,4
};

/* 5200 balloon: . = transparent, 1..D = indices into balloon_colors.
 * Each character is one logical pixel (two canvas pixels wide). */
static const uint8_t balloon_colors[14]={
    0,0x2a,0xd8,0xc8,0xb8,0xa6,0x96,0x86,0x76,0x56,0x46,0x36,0x26,0x22
};
static const char balloon_pixels[20][9]={
    "..1111..",
    ".222222.",
    ".333333.",
    "44444444",
    "55555555",
    "66666666",
    "77777777",
    "88888888",
    "99999999",
    ".AAAAAA.",
    ".BBBBBB.",
    "..CCCC..",
    "..D..D..",
    "..D..D..",
    "..D..D..",
    "..D..D..",
    "..D..D..",
    "...DD...",
    "...DD...",
    "...DD..."
};
/* Reference tank: 1 = opaque black, . = transparent wheel gaps. */
static const uint8_t tank_colors[3]={0,0x00,0x08};
/* Native ship, top to bottom at block rows 16..23. X = opaque,
 * . = transparent. Each column is doubled horizontally by the renderer.
 * Preserve the native palette slots used by the two-row color bands. */
#pragma rodata-name(push, "SPLASH")
static const char ship_pixels[8][9]={
    "...X....",
    "...X....",
    "..XX....",
    ".XXXX...",
    "XXXXXXXX",
    "XXXXXXX.",
    "XXXXXX..",
    ".XXXXX.."
};
static const uint8_t ship_colors[16]={
    0,0x2a,0xac,0x9c,0x8c,0xba,0x32,0x00,
    0x00,0x20,0x14,0x12,0x14,0x12,0x00,0x00
};
#pragma rodata-name(pop)
/* Tank rounds fly horizontally; white impact circles damage the jet.
 * W = white shell (impact palette), E = pale yellow destruction flash. */
#pragma rodata-name(push, "SPLASH")
static const char tank_shell_pixels[3][9]={
    "........",
    "..WWW...",
    "........"
};
static const char tank_blast_pixels[8][9]={
    "...EE...",
    ".E.EE.E.",
    "..EEEE..",
    "EEEEEEEE",
    "EEEEEEEE",
    "..EEEE..",
    ".E.EE.E.",
    "...EE..."
};
/* Native enemy plane, top to bottom at block rows 14..19. X = opaque,
 * . = transparent. Keep palette slots 7..9 for the native two-row bands;
 * colors below run from the bottom band to the top band. */
static const char enemy_plane_pixels[6][9]={
    "X.......",
    "XX...XX.",
    "XXXXXXXX",
    ".X..XXXX",
    "..XXX...",
    "..XX...."
};
static const uint8_t enemy_plane_colors[3]={0xac,0x9c,0x8c};
/* Reference helicopters facing right. B = black tail, G = dark green,
 * R = salmon rotor, D = dark blue fuselage stripe. In the firing variant
 * B and D use olive instead. IDs 5/6 still select the two rotor frames. */
static const uint8_t helicopter_colors[6]={0,0x00,0xb0,0x38,0x80,0x14};
static const char helicopter_pixels[2][9][9]={
    {
        ".....RRR",
        "...RRR..",
        ".....R..",
        "....GGG.",
        "G..GGGGG",
        "GDDDDDDD",
        "G...GGG.",
        ".....G..",
        "....GGG."
    },
    {
        "...RRR..",
        ".....RRR",
        ".....R..",
        "....GGG.",
        "G..GGGGG",
        "DDDDDDDD",
        "G...GGG.",
        ".....G..",
        "....GGG."
    }
};
/* Filled white water explosions: 4, 8 and 16 canvas pixels in diameter.
 * Logical pixels are twice as wide as high. W = white, . = transparent. */
static const char tank_circle_pixels[3][16][9]={
    {
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "...WW...",
        "...WW...",
        "...WW...",
        "...WW...",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........"
    },
    {
        "........",
        "........",
        "........",
        "........",
        "...WW...",
        "..WWWW..",
        "..WWWW..",
        "..WWWW..",
        "..WWWW..",
        "..WWWW..",
        "..WWWW..",
        "...WW...",
        "........",
        "........",
        "........",
        "........"
    },
    {
        "...WW...",
        "..WWWW..",
        ".WWWWWW.",
        ".WWWWWW.",
        "WWWWWWWW",
        "WWWWWWWW",
        "WWWWWWWW",
        "WWWWWWWW",
        "WWWWWWWW",
        "WWWWWWWW",
        "WWWWWWWW",
        "WWWWWWWW",
        ".WWWWWW.",
        ".WWWWWW.",
        "..WWWW..",
        "...WW..."
    }
};
#pragma rodata-name(pop)
/* Reference outline, widened to nine columns as requested. Visible 9x9
 * drawing, positioned eight rows below the native block origin.
 * Sprite storage is padded to 12x16 by prepare_tank_animation(). */
static const char tank_pixels[9][10]={
    "..1111...",
    "..1111111",
    "...111...",
    "11111111.",
    "111111111",
    "111111111",
    ".1.1.1.1.",
    "1.......1",
    ".1.1.1.1."
};
/* Two extra track frames, drawing rows 6..8. The third phase adds
 * offset links through the middle row to make the rolling motion clearer. */
static const char tank_tracks_alt[2][3][10]={
    {
        "..1.1.1..",
        "........1",
        "..1.1.1.."
    },
    {
        "..1.1.1..",
        "1........",
        "..1.1.1.."
    }
};

/* Mountain silhouettes sampled from original/Atari XL/image0.png.
 * Variant 0: three brown peaks and blue far slopes.
 * Variant 1: lower double peak with black ridges.
 * Variant 2: a single medium peak with a black ridge.
 * Variant 3: three stepped peaks with blue cuts, from the supplied reference.
 * Variant 4: overlapping wide peaks with a blue crest and black ridges.
 * One character = one logical pixel (two canvas pixels).
 * Stored rows are sprite Y=7..27; the other rows are transparent.
 * . = transparent, B = brown, K = black, U = blue. */
#define MOUNTAIN_VARIANTS 5
static const char mountain_pixels[MOUNTAIN_VARIANTS][21][32] = {
    {
        ".......................U........",
        ".....................BBU........",
        ".....................BBU........",
        "..........B.........BBBUU.......",
        "..........B........BBBBUU.......",
        ".........BBB.....BBBBBBUUU......",
        "........BBBBBB.BBBBBBBBUUUU.....",
        "........BBBBBBUBBBBBBBBUUUUU....",
        "........BBBBBBUBBBBBBBBUUUUU....",
        ".....U.BBBBBBBUBBBBBBBBUUUUU....",
        "....BU.BBBBBBBUUBBBBBBBBUUUU....",
        "...BBUUUBBBBBBBUUBBBBBBBUUUUU...",
        "...BBUUUBBBBBBBUUBBBBBBBUUUUU...",
        "..BBBBUUBBBBBBBUUBBBBBBBUUUUUU..",
        "..BBBBBUUBBBBBBBUUBBBBBBUUUUUU..",
        "..BBBBBUUBBBBBBBUUUBBBBBUUUUUU..",
        ".BBBBBBBBBBBBBBBUUUBBBBBBUUUU...",
        "BBBBBBBBBBBBBBBBBUUBBBBBBUUUU...",
        "BBBBBBBBBBBBBBBBBUUBBBBBBUUUUU..",
        "BBBBBBBBBBBBBBBBBUUUBBBBBUUUUUU.",
        "................................",
    },
    {
        "................................",
        "................................",
        "................................",
        "................................",
        "................................",
        ".......K........................",
        ".......K........................",
        ".......K........................",
        "......BKK.....K.................",
        ".....BBBK....BKK................",
        "....BBBBKK...BKKK...............",
        "....BBBBBK..BBBKKK..............",
        "...BBBBBBKK.BBBKKKK.............",
        "...BBBBBKKKKBBBBBKKK............",
        "...BBBBKKBKKKBBBBBKKK...........",
        "..BBBBBKBBBKKBBBBBKKK...........",
        "..BBBBBBBBBBKKBBBBKKKK..........",
        "..BBBBBBBBBBBKBBBBBKKKK.........",
        "BBBBBBBBBBBBBBBBBBBKKKKK........",
        "................................",
        "................................",
    },
    {
        "................................",
        "................................",
        "................................",
        "...............K................",
        "..............BKK...............",
        "..............BBK...............",
        ".............BBBKK..............",
        "............BBBBKKK.............",
        "............BBBBBKK.............",
        "...........BBBBBBKKK............",
        "..........BBBBBBBKKKK...........",
        ".........BBBBBBBBBKKKK..........",
        ".........BBBBBBBBBBKKK..........",
        "........BBBBBBBBBBBKKKK.........",
        ".......BBBBBBBBBBBBBKKKK........",
        "......BBBBBBBBBBBBBBKKKKK.......",
        ".....BBBBBBBBBBBBBBBBKKKKK......",
        "....BBBBBBBBBBBBBBBBBBKKKKK.....",
        "...BBBBBBBBBBBBBBBBBBBBKKKKK....",
        "....BBBBBBBBBBBBBBBBBBBBKKKK....",
        "................................"
    },
    {
        ".................B..............",
        ".................B..............",
        ".................B..............",
        ".................B..............",
        "................BBB...B.........",
        "................BBB...B.........",
        "..........B.....BBB...B.........",
        "..........B.....BBB...B.........",
        ".........BBB...BBBB..BB.........",
        ".........BBB...BBBB..BB.........",
        ".........BBBB.BBBBBBUBBB........",
        ".........BBBB.BBBBBBUBBB........",
        "........BBBBBUBBBBBUBBBB........",
        "........BBBBBUBBBBBUBBBB........",
        "........BBBBUUBBBBUBBBBB........",
        "........BBBBUUBBBBUBBBBB........",
        ".......BBBBUBBBBBUBBBBBBB.......",
        ".......BBBBUBBBBBUBBBBBBB.......",
        "......BBBBBUBBBBUBBBBBBBBB......",
        "......BBBBBUBBBBUBBBBBBBBB......",
        "................................",
    },
    {
        "...............UK...............",
        "..............UBKK..............",
        ".............UBBBKK.....K.......",
        "............UBBBBKK....BKK......",
        "...........UBBBBBBKK..BBBKK.....",
        "..........UBBBBBBBBKBBBBBBKK....",
        ".........UBBBBBBBBBKKBBBBBBKK...",
        ".......UUBBBBBBBBBBKKKBBBBBBKK..",
        "......BBBBBBBBBBBBBKKBKBBBBBBKK.",
        ".....BBBBBBBBBBBBBKKBBBKBBBBBBKK",
        "....BBBBBBBBBBBBKKKBBBBBKBBBBBBK",
        "...BBBBBBBBBBBBBBBBBBBBBBKBBBBBB",
        "..BBBBBBBBBBBBBBBBBBKBBBBBKKKKKK",
        "..BBBBBBBBBBBBBBBBBBBKK.........",
        ".BBBBBBBBBBBBBBBBBBBBBKK........",
        ".BBBBBBBBBBBBBBBBBBBBBBKK.......",
        "BBBBBBBBBBBBBBBBBBBBBBBBKK......",
        "BBBBBBBBBBBBBBBBBBBBBBBBBB......",
        "BBBBBBBBBBBBBBBBBBBBBBBBBBB.....",
        "......BBBBBB.....BBBBB..........",
        "................................",
    },
};
/* Inward cuts in native land, in logical pixels. The shallow, irregular
 * teeth sample the long bank in Atari XL/image0.png (logical rows 41..104).
 * Indexed by world row,
 * so the outline travels with the terrain rather than flickering per frame. */
const uint8_t bank_wave[64]={
    0,0,0,0,1,1,2,3,2,2,2,1,1,0,0,0,
    0,0,0,1,1,1,1,1,2,2,2,2,3,3,2,1,
    1,1,2,2,2,3,3,2,2,1,0,0,2,2,2,3,
    3,3,3,3,3,3,3,2,2,1,1,1,1,0,0,0
};
/* Width of a vertical rim; each entry lasts eight world lines. */
const uint8_t bank_widths[24]={
    3,3,4,4,5,5,4,4,3,3,4,4,5,5,4,4,3,3,4,4,5,5,4,4
};
/* Rim body width versus local angle from vertical. Columns describe
 * the sum of the logical displacements over four and eight lines:
 * 0,4,8,12,16,20,24,28,32+. Averaging the endpoint pairs estimates
 * the tangent over six lines. With two canvas pixels per logical X,
 * angles are approximately 0,34,53,63,69,73,76,78,79+ degrees.
 * Rows start at vertical widths 3,4,5.
 * One-line horizontal joins are drawn separately to keep the contour closed. */
static const uint8_t bank_slope_width[3][9]={
    {3,2,2,1,1,1,1,1,1},
    {4,3,2,2,1,1,1,1,1},
    {5,4,3,2,2,1,1,1,1}
};
/* Four logical pixels per tile: L = ground, B = brown, W = water.
 * Mirrored copies and the five ground colors are generated at startup. */
static const char bank_pixels[9][5]={
    "LBBB", "LLBB", "LLLB", "BBBW", "BBWW", "BWWW",
    "LBBW", "LBWW", "LLBW"
};
static const uint8_t bank_pattern[4][4]={
    {7,3,4,5}, {0,6,7,0}, {1,8,0,0}, {2,0,0,0}
};

/* Monochrome bitmaps below: X = set pixel, . = clear pixel.
 * Rows run top to bottom; characters run left to right.
 * Reserve pixels use the player color; clear pixels are transparent. */
static const char reserve_plane[8][9] = {
    "...X....",
    "...X....",
    "..XXX...",
    ".XXXXX..",
    "XX.X.XX.",
    "X..X..X.",
    "..XXX...",
    ".X.X.X.."
};
/* Reference GAME lettering: 8x6 cells, including spacing; M is seven pixels wide. */
static const char game_label[4][6][9] = {
    { /* G */
        ".XXXXX..",
        "XX......",
        "XX......",
        "XX.XXX..",
        "XX..XX..",
        ".XXXXX.."
    },
    { /* A */
        "..XX....",
        ".XXXX...",
        "XX..XX..",
        "XX..XX..",
        "XXXXXX..",
        "XX..XX.."
    },
    { /* M */
        "XX...XX.",
        "XXX.XXX.",
        "XXXXXXX.",
        "XX.X.XX.",
        "XX...XX.",
        "XX...XX."
    },
    { /* E */
        "XXXXXX..",
        "XX......",
        "XXXXX...",
        "XX......",
        "XX......",
        "XXXXXX.."
    }
};

/* BRIDGE uses the six-row reference lettering, with its original spacing. */
static const char bridge_label[6][29] = {
    "XXX..XXX..XXX.XXX...XXX.XXX.",
    "X.XX.X.XX..X..X.XX.XX...X...",
    "XXX..X.XX..X..X..X.X....XX..",
    "X.XX.XXX...X..X..X.X.XX.X...",
    "X.XX.X.XX..X..X.XX.XX.X.X...",
    "XXX..X..X.XXX.XXX...XXX.XXX."
};

/* Fuel frame, E, F and 1/2, reconstructed from unobscured reference pixels. */
static const char fuel_gauge[16][40] = {
    "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "X.XX...............X...............XX.X",
    "X.XX...............X...............XX.X",
    "X.XX............X..................XX.X",
    "X.XX...........XX..................XX.X",
    "X...............X....XX...............X",
    "X...............X...XX................X",
    "X.XXXXX........XXX.XX...........XXXXX.X",
    "X.X...............XX............X.....X",
    "X.X..............XX.XXX.........X.....X",
    "X.XXXX..........XX....X.........XXXX..X",
    "X.X............XX...XXX.........X.....X",
    "X.X.................X...........X.....X",
    "X.XXXXX.............XXX.........X.....X",
    "X.....................................X",
    "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
};

/* Six-row, thick reference digits; pointer / 8 selects 0..9, ! or space. */
static const char score_digits[12][6][7] = {
    { /* 0 */
        ".XXXX.",
        "XX..XX",
        "XX..XX",
        "XX..XX",
        "XX..XX",
        ".XXXX."
    },
    { /* 1 */
        "..XX..",
        ".XXX..",
        "..XX..",
        "..XX..",
        "..XX..",
        "XXXXXX"
    },
    { /* 2 */
        ".XXXX.",
        "XX..XX",
        "...XX.",
        "..XX..",
        ".XX...",
        "XXXXXX"
    },
    { /* 3 */
        "XXXXXX",
        "...XX.",
        "..XX..",
        "...XX.",
        "XX..XX",
        ".XXXX."
    },
    { /* 4 */
        "...XX.",
        "..XXX.",
        ".XXXX.",
        "XX.XX.",
        "XXXXXX",
        "...XX."
    },
    { /* 5 */
        "XXXXXX",
        "XX....",
        "XXXXX.",
        "....XX",
        "XX..XX",
        ".XXXX."
    },
    { /* 6 */
        ".XXXX.",
        "XX....",
        "XXXXX.",
        "XX..XX",
        "XX..XX",
        ".XXXX."
    },
    { /* 7 */
        "XXXXXX",
        "....XX",
        "...XX.",
        "..XX..",
        ".XX...",
        ".XX..."
    },
    { /* 8 */
        ".XXXX.",
        "XX..XX",
        ".XXXX.",
        "XX..XX",
        "XX..XX",
        ".XXXX."
    },
    { /* 9 */
        ".XXXX.",
        "XX..XX",
        "XX..XX",
        ".XXXXX",
        "....XX",
        ".XXXX."
    },
    { /* ! */
        "..XX..",
        "..XX..",
        "..XX..",
        "..XX..",
        "......",
        "..XX.."
    },
    { /* space */
        "......",
        "......",
        "......",
        "......",
        "......",
        "......"
    }
};

/* Narrow 3x5 lettering for P1/P2 and HI; four-pixel advance. */
static const char hud_font[13][5][4] = {
    { /* 0 */
        "XXX",
        "X.X",
        "X.X",
        "X.X",
        "XXX"
    },
    { /* 1 */
        ".X.",
        "XX.",
        ".X.",
        ".X.",
        "XXX"
    },
    { /* 2 */
        "XXX",
        "..X",
        "XXX",
        "X..",
        "XXX"
    },
    { /* 3 */
        "XXX",
        "..X",
        "XXX",
        "..X",
        "XXX"
    },
    { /* 4 */
        "X.X",
        "X.X",
        "XXX",
        "..X",
        "..X"
    },
    { /* 5 */
        "XXX",
        "X..",
        "XXX",
        "..X",
        "XXX"
    },
    { /* 6 */
        "XXX",
        "X..",
        "XXX",
        "X.X",
        "XXX"
    },
    { /* 7 */
        "XXX",
        "..X",
        ".X.",
        ".X.",
        ".X."
    },
    { /* 8 */
        "XXX",
        "X.X",
        "XXX",
        "X.X",
        "XXX"
    },
    { /* 9 */
        "XXX",
        "X.X",
        "XXX",
        "..X",
        "XXX"
    },
    { /* H */
        "X.X",
        "X.X",
        "XXX",
        "X.X",
        "X.X"
    },
    { /* I */
        "XXX",
        ".X.",
        ".X.",
        ".X.",
        "XXX"
    },
    { /* P */
        "XXX",
        "X.X",
        "XXX",
        "X..",
        "X.."
    }
};
static const char hud_letters[] = "HIP";
#endif
