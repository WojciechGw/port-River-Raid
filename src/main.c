/*
 * River Raid™ by Carol Shaw / Activision
 * © 1982, 1983 Activision
 *
 * Picocomputer 6502 port
 * © 2026 WojciechGw
 * with assistance from Codex GPT-6.1 Sol High
 */

#include <rp6502.h>
#include <string.h>
#include "xram.h"
#include "graphics.h"
#include "audio.h"
#include "duo.h"
#include "demo_footer.h"

_Static_assert(XRAM_DEMO_FOOTER_IMAGE + DEMO_FOOTER_BYTES <= XRAM_MEDIUM_MOUNTAIN, "Demo footer overlaps mountain");

/* Original native 6502 rules: original_core.asm. This host replaces the
 * Atari raster kernel, collision latches, switches and sound hardware.
 * Carol Shaw / Activision (1982), disassembly by Thomas Jentzsch. */
#define G(a) (*(uint8_t*)(a))
#define VAR G(0x80)
#define FRAME G(0x82)
#define OFFSET G(0x8b)
#define MODE G(0xc6)
#define PLAYER G(0xf4)
#define PX G(0xb3)
#define MY G(0xb2)
#define MX G(0xf5)
#define FLAGS(n) G(0x8e + (n))
#define ID(n) G(0xa0+(n))
#define OBJSTATE(n) G(0x9a+(n))
#define JET_ADDRESS (*(uint16_t*)0xba)
#define JET_IMAGE (XRAM_IMAGES+11*IMAGE_BYTES)
#define BULLET_IMAGE (JET_IMAGE+80)
#define EXTRA_IMAGES (BULLET_IMAGE+16)
/* Reference panel layout, in 160-wide logical coordinates. */
#define HUD_PLAYER_X 12
#define HUD_SCORE_X 26
#define HUD_SCORE_Y 5
#define HUD_HI_X 88
#define HUD_RECORD_X 100
#define HUD_GAME_X 13
#define HUD_GAME_Y 18
#define HUD_GAME_PITCH 8
#define HUD_GAME_NUMBER_X 29
#define HUD_GAME_NUMBER_Y 26
#define HUD_FUEL_X 45
#define HUD_FUEL_Y 17
#define HUD_FUEL_WIDTH 39
#define HUD_FUEL_HEIGHT (sizeof(fuel_gauge)/sizeof(fuel_gauge[0]))
#define DUO_FUEL_Y 10
#define DUO_STAGE_Y 28
#define HUD_RESERVES_Y 25
#define HUD_BRIDGE_NUMBER_X 140
#define HUD_FOOTER_Y (HUD_TOP+HUD_PANEL_HEIGHT+3)
/* Three pixels of bank smoothing, up to five of brown rim, two of gap. */
#define MOUNTAIN_CLEARANCE 10
enum { UP=1, DOWN=2, LEFT=4, RIGHT=8, FIRE=16, START=32, PAUSE=64, QUIT=128 };
void rr_init(void);
void rr_step(void);
void rr_tank_bonus(void);
void rr_tank_crash(void);
void demo_tick(void);
void present_frame(void);
int sound_status_init(void);
void sound_status_update(void);
void sound_status_notify(void);
void sound_status_tick(void);
void refresh_jet_palette(void);
void show_cover(void);
void show_outro(void);
void show_manual(void);
void game_fade_prepare(void);
void game_fade_in(void);
void __fastcall__ write_terrain_row(unsigned address);
void __fastcall__ write_jet_image(unsigned native_address);
void __fastcall__ write_hud_span(unsigned address);
void __fastcall__ reset_terrain(uint8_t color);
void __fastcall__ hud_glyph(unsigned glyph);
#define draw_glyph(x,bits) hud_glyph(((unsigned)(x)<<8)|(bits))
uint8_t __fastcall__ land_xy(unsigned position);
uint8_t __fastcall__ helicopter_water(unsigned position);
#define helicopter_water_at(x,y) helicopter_water(((unsigned)(uint8_t)(y)<<8)|(uint8_t)(x))
uint8_t __fastcall__ mask_land(unsigned position);
uint8_t __fastcall__ mask_player_land(unsigned position);
uint16_t __fastcall__ tia_color(uint8_t code);
#define land_at(x,y) land_xy(((unsigned)(uint8_t)(y)<<8)|(uint8_t)(x))
extern const uint8_t rr_shapePtr1aTab[], rr_shapePtr1bTab[], rr_ColorPtrTab[];
extern const uint8_t rr_ColorTab[], rr_RoadColorTab[];
extern const uint8_t rr_Space[];
uint8_t row[RIVER_WIDTH];
uint8_t hud_ink;
uint8_t hud_fill;
uint8_t hud_column, hud_length;
uint8_t reset_tiles[512];
uint8_t bank_half[20], tile_mirror[TERRAIN_TILE_COUNT];
/* One 8-pixel tile per Atari PF bit; trim seven rows to make it one line high. */
tile_config_t terrain = {0,1,0,RIVER_TOP,TERRAIN_COLUMNS,RIVER_RING,
    XRAM_TERRAIN,XRAM_PALETTE,XRAM_TILES};
static bitmap_config_t hud_bitmap = {0,0,0,HUD_TOP,320,HUD_HEIGHT,XRAM_HUD,XRAM_PALETTE};
extern const bitmap_config_t demo_footer;
extern uint16_t footer_offset;
#pragma zpsym ("footer_offset")
uint8_t shown_demo=255;
sprite_t sprites[SPRITE_COUNT];
sprite_t hud_sprites[HUD_SPRITE_COUNT];
static uint8_t shown_duo_lives[2];
static uint8_t masks[OBJECT_IMAGE_COUNT][32], sprite_colors[OBJECT_IMAGE_COUNT][16];
static uint8_t widths[OBJECT_IMAGE_COUNT], scales[OBJECT_IMAGE_COUNT];
static uint8_t reverse_bits[256];
/* Road companion survives its bridge; it scrolls and resets with the block. */
typedef struct {
    int16_t x;
    uint8_t status, direction, explosion;
} tank_t;
_Static_assert(sizeof(tank_t)==5, "Road tank layout used by sync_tanks");
tank_t tanks[6];
static uint8_t tank_bonus;

/* Two independent bank tanks, with one harmless round / dangerous splash
 * each. Keep extension state above the original reference ROM. */
typedef struct {
    int16_t x, y, shot_x;
    uint8_t side, status, cooldown, shot_phase, shot_target, timer, ground_target;
} bank_tank_t;
typedef struct {
    int16_t x,y;
    uint8_t active,direction;
} helicopter_shot_t;
#pragma data-name(push, "SPLASH")
/* Slot 2 shares a stopped road tank body, with an independent shot. */
static bank_tank_t bank_tanks[3]={{0}};
static uint8_t bank_shot_random=0xa7;
static helicopter_shot_t helicopter_shots[6]={{0}};
/* 0 = unassigned block, 1 = normal helicopter, 2 = firing helicopter. */
static uint8_t helicopter_types[6]={0}, helicopter_spawn=0;
#pragma data-name(pop)
typedef struct {
    int16_t native_x, draw_x;
    uint8_t pattern1, pattern2, flags, flip, valid;
} mountain_position_t;
static mountain_position_t mountain_positions[6];
static const uint16_t mountain_images[MOUNTAIN_VARIANTS]={
    XRAM_IMAGES+9*IMAGE_BYTES,XRAM_SMALL_MOUNTAIN,XRAM_MEDIUM_MOUNTAIN,
    XRAM_STEPPED_MOUNTAIN,XRAM_WIDE_MOUNTAIN
};
static uint8_t mountain_min_x=32, mountain_max_x;
uint8_t collision_mask, collision_scale;
uint8_t river1[RIVER_RING], river2[RIVER_RING], ring_top;
uint8_t river_left[RIVER_RING], river_right[RIVER_RING];
/* Green/road ground limits, excluding the decorative rim. Full-width X:
 * outer land lies outside [left,right), an island inside [left,right). */
uint8_t player_outer_left[RIVER_RING], player_outer_right[RIVER_RING];
uint8_t player_island_left[RIVER_RING], player_island_right[RIVER_RING];
static uint8_t first_water[256], last_water[256];
/* Native PF patterns repeat for two lines. Reuse tangent samples within a
 * redraw batch; rr_step may change their block pointers before the next one. */
static uint8_t edge_left[96], edge_right[96], edge_valid[96];
static uint8_t shore_left, shore_right, shore_outer, shore_inner, shore_base, shore_color;
static uint8_t keys[32], pads[40], inputs[2], previous_input, previous_keys;
uint8_t paused;
static uint8_t switches=0x0b, palette_mask, palette_xor;
uint8_t tank_track_phase;
uint8_t road_gunner=255;
static const uint16_t tank_images[3]={XRAM_TANK_IMAGE,XRAM_TANK_IMAGE_ALT,XRAM_TANK_IMAGE_ALT2};
/* Applied by native GameInit to both players on a full game reset. */
uint8_t start_level=1;
static uint8_t state_bytes[32], old_score[12], old_fuel;
uint8_t palette_player;
static uint16_t ticks, skipped_frames, jet_cache=0xffff;
/* 1: startup fade, 2: scrolling attract demo, 0: user game. */
uint8_t ready=1;
static uint8_t hud_dirty=1, reflected, hud_pending;
static uint8_t fuel_rows[HUD_FUEL_HEIGHT][HUD_FUEL_WIDTH];
static uint8_t score_rows[12][6];
uint16_t tia_palette[128];
static uint8_t shown_level=255, shown_variant=255, shown_player=255;
static uint8_t shown_reserves=255;
uint8_t high_dirty=1;
static uint8_t high_score[6]={88,88,88,88,88,0};
#ifdef RIVER_PROFILE
/* Max milliseconds: input, collisions, original rules, terrain, render, frame. */
static uint16_t timings[6], timing_start, timing_stamp, timing_frame;
static void profile_phase(uint8_t phase)
{
    uint16_t now=(uint16_t)ria_attr_get(RIA_ATTR_CLK_RUN_MS), elapsed=now-timing_stamp;
    if (elapsed>timings[phase]) timings[phase]=elapsed;
    timing_stamp=now;
}
#define PROFILE_PHASE(n) profile_phase(n)
#else
#define PROFILE_PHASE(n) ((void)0)
#endif
#define RGB(r,g,b) ((uint16_t)(((uint16_t)(b)<<11)|((g)<<6)|(r)|32))
static const uint8_t hues[16][3] = {
    {31,31,31},{29,26,4},{31,18,3},{31,11,5},{29,6,12},{23,6,23},
    {13,6,29},{7,9,31},{4,14,31},{3,21,29},{3,26,24},{5,27,14},
    {8,26,5},{18,25,4},{25,23,4},{29,20,4}
};
#pragma optimize(push, on)
static uint16_t tia_rgb(uint8_t code)
{
    static const uint8_t luminance[8]={0,9,13,17,21,24,26,29};
    uint8_t h,l,r,g,b,i;
    for (i=0;i<sizeof(reference_colors)/sizeof(reference_colors[0]);++i)
        if (reference_colors[i][0]==code)
            return RGB(reference_colors[i][1],reference_colors[i][2],reference_colors[i][3]);
    h=code>>4; l=code&14;
    if (!h) return RGB(luminance[l>>1],luminance[l>>1],luminance[l>>1]);
    r=hues[h][0]*(l+8)/20; g=hues[h][1]*(l+8)/20; b=hues[h][2]*(l+8)/20;
    if (r>31) r=31; if (g>31) g=31; if (b>31) b=31;
    return RGB(r,g,b);
}
static void upload(uint16_t address,const void* data,uint16_t count)
{ xram0_write(address,data,count); }
static uint16_t image_address(uint8_t id)
{
    return id==8 ? XRAM_BRIDGE_IMAGE : id==BALLOON_ID ? XRAM_BALLOON_IMAGE : id==TANK_ID ? XRAM_TANK_IMAGE :
        XRAM_IMAGES+(uint16_t)id*IMAGE_BYTES;
}
static uint16_t palette_address(uint8_t id)
{
    return id==BALLOON_ID ? XRAM_BALLOON_PALETTE : id==TANK_ID ? XRAM_TANK_PALETTE :
        XRAM_SPRITE_PALETTES+(uint16_t)id*32;
}
#pragma code-name(push, "SPLASH")
static uint8_t helicopter_type(uint8_t n)
{
    /* Assign once per aircraft, preserving its type across rotor frames. */
    if (!helicopter_types[n]) {
        ++helicopter_spawn;
        helicopter_types[n]=G(0xbd)>=5 && !(helicopter_spawn&3) ? 2 : 1;
    }
    return G(0xbd)>=5 && helicopter_types[n]==2;
}
#pragma code-name(pop)
static uint8_t helicopter_ink(char pixel,uint8_t type)
{
    return pixel=='B' ? (type ? 5 : 1) : pixel=='G' ? 2 : pixel=='R' ? 3 :
        pixel=='D' ? (type ? 5 : 4) : 0;
}
#pragma optimize(pop)
#pragma code-name(push, "SPLASH")
static void prepare_helicopters(void)
{
    uint8_t id,type,x,y,bits,ink;
    for (id=5;id<=6;++id) {
        memcpy(sprite_colors[id],helicopter_colors,sizeof(helicopter_colors));
        for (type=0;type<2;++type) for (y=0;y<32;++y) {
            memset(row,0,4); bits=0;
            if (y>=8 && y<17) for (x=0;x<8;++x) {
                ink=helicopter_ink(helicopter_pixels[id-5][y-8][x],type);
                if (!ink) continue;
                bits|=0x80>>x;
                row[x>>1]|=ink<<((x&1) ? 0 : 4);
            }
            if (!type) masks[id][y]=bits;
            upload(image_address(id)+(uint16_t)type*128+(uint16_t)y*4,row,4);
        }
    }
    memset(row,0,16); row[5]=row[6]=0xee;
    upload(XRAM_HELICOPTER_SHOT,row,16);
}
#pragma optimize(push, on)
static void prepare_tank_animation(void)
{
    uint8_t y,x,frame;
    uint16_t address;
    widths[TANK_ID]=TANK_WIDTH; scales[TANK_ID]=1;
    memcpy(sprite_colors[TANK_ID],tank_colors,sizeof(tank_colors));
    for (y=0;y<TANK_IMAGE_HEIGHT;++y) {
        memset(row,0,TANK_IMAGE_WIDTH/2);
        if (y<TANK_HEIGHT) for (x=0;x<TANK_WIDTH;++x) {
            if (tank_pixels[y][x]!='.')
                row[x>>1]|=(tank_pixels[y][x]-'0')<<((x&1) ? 0 : 4);
        }
        upload(XRAM_TANK_IMAGE+(uint16_t)y*(TANK_IMAGE_WIDTH/2),row,TANK_IMAGE_WIDTH/2);
    }
    for (frame=0;frame<2;++frame) {
        address=tank_images[frame+1];
        xram0_read(row,XRAM_TANK_IMAGE,TANK_IMAGE_BYTES);
        upload(address,row,TANK_IMAGE_BYTES);
        for (y=0;y<3;++y) {
            memset(row,0,TANK_IMAGE_WIDTH/2);
            for (x=0;x<TANK_WIDTH;++x)
                if (tank_tracks_alt[frame][y][x]!='.')
                    row[x>>1]|=(tank_tracks_alt[frame][y][x]-'0')<<((x&1) ? 0 : 4);
            upload(address+(uint16_t)(6+y)*(TANK_IMAGE_WIDTH/2),row,TANK_IMAGE_WIDTH/2);
        }
    }
}
static uint16_t tank_image(void)
{
    return tank_images[tank_track_phase];
}
#pragma optimize(pop)
#pragma code-name(pop)
static uint8_t terrain_row(uint8_t y)
{
    uint16_t n=(uint16_t)ring_top+y;
    if (n>=RIVER_RING) n-=RIVER_RING;
    return n;
}
static void terrain_pattern(uint8_t distance, uint8_t* p1, uint8_t* p2)
{
    uint8_t block=distance>>5,index=(distance&31)>>1,flags=FLAGS(block);
    *p1=G((uint16_t)(0xcc00|((flags&1)<<8))+G(0xa6+block)+index);
    *p2=G((uint16_t)(0xcc00|((flags&2)<<7))+G(0xac+block)+index);
}
static void pattern_edges(uint8_t p1,uint8_t p2,uint8_t* left,uint8_t* right)
{
    p1=reverse_bits[p1];
    *left=p1!=255 ? 16+first_water[p1]*4 : 48+first_water[p2]*4;
    *right=p2!=255 ? 48+last_water[p2]*4 : 16+last_water[p1]*4;
    if (p1==255 && p2==255) *left=*right=80;
}
static void terrain_edges(uint8_t distance, uint8_t* left, uint8_t* right)
{
    uint8_t pair=distance>>1,p1,p2;
    if (!edge_valid[pair]) {
        terrain_pattern(distance,&p1,&p2); pattern_edges(p1,p2,left,right);
        edge_left[pair]=*left; edge_right[pair]=*right; edge_valid[pair]=1;
    } else { *left=edge_left[pair]; *right=edge_right[pair]; }
}
static uint8_t bank_slope(uint8_t a,uint8_t b)
{
    uint8_t delta=a>b ? a-b : b-a;
    delta>>=2; return delta>8 ? 8 : delta;
}
static uint8_t smooth_left(uint8_t a,uint8_t b)
{ return b<a ? (a+b)>>1 : a; }
static uint8_t smooth_right(uint8_t a,uint8_t b)
{ return b>a ? (a+b+1)>>1 : a; }
static uint8_t bank_left(uint8_t edge,uint8_t phase)
{ return edge<16+bank_wave[phase&63] ? 16 : edge-bank_wave[phase&63]; }
static uint8_t bank_right(uint8_t edge,uint8_t phase)
{ return edge+bank_wave[(phase+23)&63]>80 ? 80 : edge+bank_wave[(phase+23)&63]; }
static uint8_t shore_tile(uint8_t x,uint8_t mirror)
{
    uint8_t land=0,water=0,reverse=0,end=x+4,width;
    if (shore_left==shore_right) return shore_color;
    if (end<=shore_left) {
        width=shore_outer;
        land=end+width<=shore_left ? 4 : x+width<shore_left ? shore_left-width-x : 0;
    } else if (x>=shore_right) {
        width=shore_inner; reverse=1;
        land=x>=shore_right+width ? 4 : end>shore_right+width ? end-shore_right-width : 0;
    } else if (x>=shore_left && end<=shore_right) return 1;
    else if (x<shore_left) {
        water=end-shore_left;
        if (x+shore_outer<shore_left) land=shore_left-shore_outer-x;
    } else {
        reverse=1; water=shore_right-x;
        if (end>shore_right+shore_inner) land=end-shore_right-shore_inner;
    }
    if (land==4) return shore_color;
    if (!land && !water) return TERRAIN_BANK_SOLID;
    return shore_base+((reverse^mirror) ? 9 : 0)+bank_pattern[land][water];
}
static void shore_half(void)
{
    uint8_t start,end,outer,inner;
    if (shore_color==7) shore_color=TERRAIN_ROAD_UPPER;
    memset(bank_half,shore_color,20);
    if (shore_left==shore_right) return;
    start=(shore_left+3)>>2; end=shore_right>>2;
    if (end>start) memset(bank_half+start,1,end-start);
    outer=shore_outer>shore_left ? 0 : shore_left-shore_outer;
    inner=shore_right+shore_inner; if (inner>80) inner=80;
    start=(outer+3)>>2; end=shore_left>>2;
    if (end>start) memset(bank_half+start,TERRAIN_BANK_SOLID,end-start);
    start=(shore_right+3)>>2; end=inner>>2;
    if (end>start) memset(bank_half+start,TERRAIN_BANK_SOLID,end-start);
    /* Only the four transitions can occupy a partial tile. Whole spans
     * use memset; avoid running the general pixel logic for all 40 tiles. */
    start=outer>>2; if (start<20) bank_half[start]=shore_tile(start*4,0);
    start=shore_left>>2; if (start<20) bank_half[start]=shore_tile(start*4,0);
    start=shore_right>>2; if (start<20) bank_half[start]=shore_tile(start*4,0);
    start=inner>>2; if (start<20) bank_half[start]=shore_tile(start*4,0);
}
/* Reserve space for all mountain bitmaps in the fixed Debug memory map. */
#pragma optimize(push, on)
static void draw_terrain_row(uint8_t y)
{
    /* Called only from the main loop. Fixed scratch storage avoids cc65's
     * costly software-stack accesses when a respawn draws many lines. */
    static uint8_t n,distance,block,index,flags,p1,p2,color,x,phase;
    static uint8_t left,right,pl,pr,nl,nr,near_left,near_right,outer_cap,inner_cap;
    static uint8_t far_left,far_right,other_left,other_right,outer_slope,inner_slope,base_width;
    n=terrain_row(y); distance=159-y+OFFSET; block=distance>>5;
    index=(distance&31)>>1; flags=FLAGS(block); phase=n>>3;
    terrain_pattern(distance,&p1,&p2);
    river1[n]=p1; river2[n]=p2;
    pattern_edges(p1,p2,&left,&right);
    edge_left[distance>>1]=left; edge_right[distance>>1]=right; edge_valid[distance>>1]=1;
    pl=nl=left; pr=nr=right;
    if (distance>=2) terrain_edges(distance-2,&pl,&pr);
    if (distance<190) terrain_edges(distance+2,&nl,&nr);
    /* Average the endpoints at +/-2 and +/-4 lines to estimate a six-line
     * tangent. This avoids treating each PF stair as a separate bend. */
    far_left=left; far_right=right; other_left=left; other_right=right;
    if (distance>=4) terrain_edges(distance-4,&far_left,&far_right);
    if (distance<188) terrain_edges(distance+4,&other_left,&other_right);
    outer_slope=bank_slope(far_left+pl,other_left+nl);
    inner_slope=bank_slope(far_right+pr,other_right+nr);
    /* Interpolate inside the native land at PF steps. The same boundaries
     * drive rendering and collisions. Roads keep their exact bridge span. */
    shore_left=smooth_left(left,(distance&1) ? nl : pl);
    shore_right=smooth_right(right,(distance&1) ? nr : pr);
    color=(flags&4) ? 3 : 2;
    if ((flags&0x80) && index>=3 && index<13) {
        color=bridge_road[25-(distance&31)]; shore_left=left; shore_right=right;
    } else if (shore_left<shore_right) {
        shore_left=bank_left(shore_left,n); shore_right=bank_right(shore_right,n);
    }
    river_left[n]=shore_left; river_right[n]=shore_right;
    near_left=bank_left(smooth_left(left,(distance&1) ? pl : nl),(distance&1) ? n+1 : n-1);
    x=bank_left(smooth_left((distance&1) ? nl : pl,left),(distance&1) ? n-1 : n+1);
    if (x<near_left) near_left=x;
    near_right=bank_right(smooth_right(right,(distance&1) ? pr : nr),(distance&1) ? n+1 : n-1);
    x=bank_right(smooth_right((distance&1) ? nr : pr,right),(distance&1) ? n-1 : n+1);
    if (x>near_right) near_right=x;
    outer_cap=near_left<shore_left ? shore_left-near_left : 0;
    inner_cap=near_right>shore_right ? near_right-shore_right : 0;
    shore_base=8+(color-2)*18; shore_color=color;
    base_width=bank_widths[phase]-3;
    shore_outer=bank_slope_width[base_width][outer_slope];
    shore_inner=bank_slope_width[base_width][inner_slope];
    if (shore_outer<outer_cap) shore_outer=outer_cap;
    if (shore_inner<inner_cap) shore_inner=inner_cap;
    player_outer_left[n]=shore_outer>shore_left ? 0 : shore_left-shore_outer;
    x=shore_right+shore_inner; player_island_left[n]=x>80 ? 80 : x;
    shore_half(); memcpy(row,bank_half,20);
    phase+=9; if (phase>=24) phase-=24;
    base_width=bank_widths[phase]-3;
    shore_outer=bank_slope_width[base_width][outer_slope];
    shore_inner=bank_slope_width[base_width][inner_slope];
    if (shore_outer<outer_cap) shore_outer=outer_cap;
    if (shore_inner<inner_cap) shore_inner=inner_cap;
    x=shore_outer>shore_left ? 0 : shore_left-shore_outer; player_outer_right[n]=160-x;
    x=shore_right+shore_inner; player_island_right[n]=160-(x>80 ? 80 : x);
    if (shore_left==shore_right) {
        player_outer_left[n]=player_outer_right[n]=80;
        player_island_left[n]=player_island_right[n]=80;
    }
    shore_half();
    write_terrain_row(XRAM_TERRAIN+(uint16_t)n*TERRAIN_COLUMNS);
}
#pragma optimize(pop)
static void restart_terrain(void)
{
    uint8_t y;
    /* GameInit restores a straight corridor. Only OFFSET top rows may already
     * belong to a new block after rr_step; preserve them with the normal path. */
    reset_terrain((FLAGS(0)&4) ? 3 : 2);
    memset(edge_valid,0,sizeof(edge_valid));
    for (y=0;y<OFFSET;++y) draw_terrain_row(y);
}
static void rebuild_terrain(void)
{
    uint8_t y;
    ring_top=0;
    memset(edge_valid,0,sizeof(edge_valid));
    for (y=0;y<160;++y) draw_terrain_row(y);
}
/* Keep bounded palette updates compact in the fixed Debug memory map. */
#pragma optimize(push, on)
static void refresh_duo_hud_palettes(void)
{
    static uint16_t colors[12];
    /* Bitmap roles: 5 = native BRIDGE, 6 = P2, 7 = black,
     * 8 = P1, 10 = panel. Score glyphs use transparent 0 and ink 11. */
    colors[5]=tia_color(rr_ColorTab[3]); colors[6]=tia_color(0xac);
    colors[7]=RGB(0,0,0); colors[8]=tia_color(rr_ColorTab[1]);
    colors[10]=tia_color(rr_ColorTab[2]); colors[11]=colors[8];
    upload(XRAM_DUO_HUD_P1_PALETTE,colors,sizeof(colors));
    xram0_poke16(XRAM_DUO_HUD_P2_PALETTE,0);
    xram0_poke16(XRAM_DUO_HUD_P2_PALETTE+22,colors[6]);
}
/* Linker-managed zero page keeps the palette scratch outside full main RAM. */
#pragma bss-name(push, "ZEROPAGE")
static uint16_t palette_colors[16];
#pragma bss-name(pop)
#pragma zpsym("palette_colors")
static void refresh_palettes(void)
{
    /* Like the terrain scratch space, this buffer has a single main-loop
     * owner. Avoid indirect stack indexing during a restart plus B&W change. */
    static uint8_t id,i,count;
    palette_colors[0]=0; palette_colors[1]=tia_color(rr_ColorTab[4]);
    palette_colors[2]=tia_color(0xd2); palette_colors[3]=tia_color(0xd6);
    palette_colors[4]=tia_color(4); palette_colors[5]=tia_color(8); palette_colors[6]=tia_color(rr_ColorTab[1]);
    palette_colors[7]=RGB(0,0,0); palette_colors[8]=tia_color(rr_ColorTab[1]); palette_colors[9]=tia_color(0x06);
    palette_colors[10]=tia_color(rr_ColorTab[2]); palette_colors[11]=tia_color(rr_ColorTab[3]);
    palette_colors[12]=tia_color(0x20); /* Brown bank rim and mountain faces. */
    palette_colors[13]=tia_color(0x32); palette_colors[14]=tia_color(0x2a); palette_colors[15]=tia_color(0xa8);
    upload(XRAM_PALETTE,palette_colors,32);
    palette_colors[11]=palette_colors[7]; upload(XRAM_HUD_BLACK_PALETTE,palette_colors,32);
    if (VAR==2) refresh_duo_hud_palettes();
    for (id=0;id<OBJECT_IMAGE_COUNT;++id) {
        palette_colors[0]=0;
        count=id==BALLOON_ID ? sizeof(balloon_colors) : id==TANK_ID ? sizeof(tank_colors) : 16;
        for (i=1;i<count;++i) palette_colors[i]=tia_color(sprite_colors[id][i]);
        upload(palette_address(id),palette_colors,32);
    }
    refresh_jet_palette(); palette_colors[0]=0;
    for (i=0;i<6;++i) {
        palette_colors[i+1]=(G(0x86)==255 && !G(0x85)) ?
            RGB(activision_colors[i][0],activision_colors[i][1],activision_colors[i][2]) :
            tia_color(activision_color_roles[i]);
    }
    upload(XRAM_LOGO_PALETTE,palette_colors,14);
    /* The demo caption stays light gray when the screensaver changes hues. */
    palette_colors[2]=RGB(23,23,23); upload(XRAM_DEMO_FOOTER_PALETTE,palette_colors,14);
    palette_mask=G(0x86); palette_xor=G(0x85);
}
#pragma optimize(pop)
static char mountain_pixel(uint8_t variant,uint8_t y,uint8_t x)
{ return y<7 || y>=28 ? '.' : ".BKU"[(mountain_packed[variant][y-7][x>>2]>>((3-(x&3))*2))&3]; }
/* Startup-only conversion must also fit the fixed RAM map in Debug. */
#pragma optimize(push, on)
static void prepare_images(void)
{
    static uint8_t id,y,j,bits,x,scale,width,variant;
    static uint16_t v;
    for (v=0;v<256;++v) {
        bits=v; j=0;
        for (x=0;x<8;++x) {j=(j<<1)|(bits&1); bits>>=1;}
        reverse_bits[v]=j;
        first_water[v]=8; last_water[v]=0;
        for (x=0;x<8;++x) if (!(v&(1<<x))) {
            if (first_water[v]==8) first_water[v]=x;
            last_water[v]=x+1;
        }
    }
    for (id=0;id<11;++id) {
        scale=id==8 ? 6 : id==9 ? 4 : id==7 ? 2 : 1;
        width=8*scale; scales[id]=scale; widths[id]=width;
        for (y=0;y<32;++y) {
            j=31-y;
            /* The TIA kernel uses A on even block lines and B on odd ones.
             * Reversing these pairs breaks the negative-space FUEL lettering.
             * FUEL spans 24 rows: four six-row color bands. Keep its bottom
             * gray row below L (j=2), which other sprites do not use. */
            bits=(id==4 || id==7 || j<(id==10 ? 2 : 3) || j>=26) ? 0 :
                G(0xce00+(uint8_t)((j&1 ? rr_shapePtr1bTab[id] : rr_shapePtr1aTab[id])+(j>>1)));
            if (id==4 && y>=14 && y<20)
                for (x=0;x<8;++x) if (enemy_plane_pixels[y-14][x]=='X') bits|=0x80>>x;
            if (id==7 && y>=16 && y<24)
                for (x=0;x<8;++x) if (ship_pixels[y-16][x]=='X') bits|=0x80>>x;
            if (id==9) {
                bits=0;
                for (x=0;x<32;++x) for (variant=0;variant<MOUNTAIN_VARIANTS;++variant)
                    if (mountain_pixel(variant,y,x)!='.') {
                        bits|=0x80>>(x>>2);
                        if (x<mountain_min_x) mountain_min_x=x;
                        if (x>mountain_max_x) mountain_max_x=x;
                        break;
                    }
            }
            if (id!=4 && id!=7 && j<26) sprite_colors[id][(j>>1)+1]=G(0xcf00+(uint8_t)(rr_ColorPtrTab[id]+(j>>1)));
            if (id==8) {
                j=y>=8 && y<25 ? bridge_rows[y-8] : 0;
                bits=j==5 ? 0x24 : j ? 255 : 0;
            }
            masks[id][y]=bits;
            memset(row,0,width/2);
            for (x=0;x<width;++x) if (bits&(0x80>>(x/scale))) {
                uint8_t ink=id==8 ? j : (j>>1)+1;
                if (id==9) {
                    static uint8_t pixel;
                    pixel=mountain_pixel(0,y,x);
                    if (pixel=='.') continue;
                    ink=pixel=='K' ? 2 : pixel=='U' ? 3 : 1;
                }
                row[x>>1]|=(uint8_t)(ink<<((x&1) ? 0 : 4));
            }
            upload(image_address(id)+(uint16_t)y*(width/2),row,width/2);
            if (id<4) {
                memset(row,0,8);
                for (x=0;x<8;++x) if (bits&(0x80>>x)) row[x]=((j>>1)+1)*17;
                upload(EXTRA_IMAGES+(uint16_t)id*256+y*8,row,8);
            }
        }
        if (id==4) memcpy(sprite_colors[id]+7,enemy_plane_colors,sizeof(enemy_plane_colors));
        if (id==9) {sprite_colors[id][1]=0x20; sprite_colors[id][2]=0; sprite_colors[id][3]=0x84;}
        if (id==8) memcpy(sprite_colors[id],bridge_colors,sizeof(bridge_colors));
        if (id==7) memcpy(sprite_colors[id],ship_colors,sizeof(ship_colors));
    }
    for (id=1;id<MOUNTAIN_VARIANTS;++id) for (y=0;y<32;++y) {
        memset(row,0,16);
        for (x=0;x<32;++x) {
            static uint8_t pixel;
            pixel=mountain_pixel(id,y,x);
            if (pixel!='.') row[x>>1]|=(pixel=='K' ? 2 : pixel=='U' ? 3 : 1)<<((x&1) ? 0 : 4);
        }
        upload(mountain_images[id]+(uint16_t)y*16,row,16);
    }
    id=BALLOON_ID;
    {
        widths[id]=8; scales[id]=1;
        memcpy(sprite_colors[id],balloon_colors,sizeof(balloon_colors));
        for (y=0;y<32;++y) {
            memset(row,0,4); bits=0;
            /* Center the trimmed 20-row bitmap in the original 32-row canvas. */
            if (y>=6 && y<26) for (x=0;x<8;++x) {
                uint8_t pixel=balloon_pixels[y-6][x];
                if (pixel=='.') continue;
                j=pixel<='9' ? pixel-'0' : pixel-'A'+10;
                bits|=0x80>>x;
                row[x>>1]|=j<<((x&1) ? 0 : 4);
            }
            masks[id][y]=bits;
            upload(image_address(id)+y*4,row,4);
        }
    }
    xram0_set(BULLET_IMAGE,0,16);
    for (y=0;y<8;++y) xram0_poke8(BULLET_IMAGE+y*2,0x10);
    for (y=0;y<8;++y) {
        memset(row,0,4);
        for (x=0;x<8;++x) if (tank_blast_pixels[y][x]!='.')
            row[x>>1]|=(x&1) ? 14 : 0xe0;
        upload(XRAM_TANK_BLAST+y*4,row,4);
        if (y<4) {
            memset(row,0,4);
            /* VGA storage has four rows; pad the shorter drawing with zero. */
            if (y<sizeof(tank_shell_pixels)/sizeof(tank_shell_pixels[0]))
                for (x=0;x<8;++x) if (tank_shell_pixels[y][x]!='.')
                    row[x>>1]|=(x&1) ? 1 : 0x10;
            upload(XRAM_TANK_SHELL+y*4,row,4);
        }
    }
    for (id=0;id<3;++id) for (y=0;y<16;++y) {
        memset(row,0,4);
        for (x=0;x<8;++x) if (tank_circle_pixels[id][y][x]!='.')
            row[x>>1]|=(x&1) ? 1 : 0x10;
        upload(XRAM_TANK_CIRCLES+(uint16_t)id*64+y*4,row,4);
    }
    xram0_poke16(XRAM_TANK_EXPLOSION_PALETTE,0);
    xram0_poke16(XRAM_TANK_EXPLOSION_PALETTE+2,RGB(31,31,31));
    prepare_tank_animation();
    prepare_helicopters();
}
#pragma optimize(pop)
/* Keep mountain placement compact alongside the additional bitmap data. */
#pragma optimize(push, on)
static void jet_image(void)
{
    if (JET_ADDRESS==jet_cache) return;
    jet_cache=JET_ADDRESS;
    write_jet_image(JET_ADDRESS);
}
static int16_t fit_mountain(uint8_t n,int16_t native_x)
{
    static mountain_position_t* cached;
    static uint8_t pattern1,pattern2,flags,flip,p1,p2,y,index,tile,mirror,land,first,min_x,max_x;
    static uint16_t base1,base2;
    static int16_t low,high,candidate,distance,best,best_distance;
    cached=&mountain_positions[n];
    pattern1=G(0xa6+n); pattern2=G(0xac+n); flags=FLAGS(n)&3; flip=OBJSTATE(n)&8;
    p1=p2=first=255; min_x=mountain_min_x; max_x=mountain_max_x;
    best=native_x; best_distance=32767;
    if (cached->valid && cached->native_x==native_x && cached->pattern1==pattern1 &&
        cached->pattern2==pattern2 && cached->flags==flags && cached->flip==flip)
        return cached->draw_x;
    if (mountain_min_x==32) return native_x;
    if (flip) {min_x=31-mountain_max_x; max_x=31-mountain_min_x;}
    /* Every mountain row belongs to its own original terrain block. Read the
     * whole footprint, including rows above/below the viewport, so scrolling
     * does not make a mountain slide sideways as new rows become visible. */
    base1=(uint16_t)(0xcc00|((flags&1)<<8))+pattern1;
    base2=(uint16_t)(0xcc00|((flags&2)<<7))+pattern2;
    for (y=0;y<32;++y) if (masks[9][y]) {
        index=(31-y)>>1; p1&=G(base1+index); p2&=G(base2+index);
        if (index) {p1&=G(base1+index-1); p2&=G(base2+index-1);}
        if (index<15) {p1&=G(base1+index+1); p2&=G(base2+index+1);}
    }
    /* Find the nearest land interval shared by all opaque rows. The outer
     * banks extend offscreen; narrow islands cannot hold a full mountain. */
    for (tile=0;tile<=TERRAIN_COLUMNS;++tile) {
        land=0;
        if (tile<TERRAIN_COLUMNS) {
            mirror=tile<20 ? tile : 39-tile;
            land=mirror<4 ? 1 : mirror<12 ? p1&(0x80>>(mirror-4)) : p2&(1<<(mirror-12));
        }
        if (land) {if (first==255) first=tile; continue;}
        if (first==255) continue;
        /* Keep the entire silhouette beyond the smoothed water and brown
         * rim, with two logical pixels of visible ground between them. */
        low=(first ? (int16_t)first*4+MOUNTAIN_CLEARANCE : -32)-min_x;
        high=(tile<TERRAIN_COLUMNS ? (int16_t)tile*4-MOUNTAIN_CLEARANCE : 192)-1-max_x;
        first=255;
        if (low>high) continue;
        candidate=native_x<low ? low : native_x>high ? high : native_x;
        distance=candidate>native_x ? candidate-native_x : native_x-candidate;
        if (distance<best_distance) {
            best=candidate; best_distance=distance;
            if (!distance) break;
        }
    }
    cached->native_x=native_x; cached->draw_x=best;
    cached->pattern1=pattern1; cached->pattern2=pattern2;
    cached->flags=flags; cached->flip=flip; cached->valid=1;
    return best;
}
static int16_t object_x(uint8_t n)
{
    static int16_t x;
    x=(int16_t)G(0x94+n)*15+((OBJSTATE(n)>>4)^7)-1;
    /* CalcPosX encodes the bridge at 63. Its deck covers [56,104),
     * overlapping each bank by eight logical pixels around [64,96). */
    if (ID(n)==9) return fit_mountain(n,x);
    return x-(ID(n)==8 ? 7 : 0);
}
static uint8_t mountain_variant(uint8_t n)
{ return (G(0xa6+n)^(G(0xac+n)>>3)^G(0x94+n))%MOUNTAIN_VARIANTS; }
#pragma optimize(pop)
#pragma code-name(push, "SPLASH")
static uint8_t opaque(uint8_t id,uint8_t x,uint8_t y,uint8_t flip,uint8_t block)
{
    if (x>=widths[id] || y>=32) return 0;
    if (id==TANK_ID) {
        if (y<TANK_TOP || y>=TANK_TOP+TANK_HEIGHT) return 0;
        y-=TANK_TOP; if (flip) x=TANK_WIDTH-1-x;
        return y>=6 && tank_track_phase ? tank_tracks_alt[tank_track_phase-1][y-6][x]!='.' : tank_pixels[y][x]!='.';
    }
    if (id==9) return mountain_pixel(mountain_variant(block),y,flip ? 31-x : x)!='.';
    if (scales[id]==6) x/=6; else if (scales[id]==2) x>>=1; else if (scales[id]==4) x>>=2;
    if (flip) x=7-x;
    return masks[id][y]&(0x80>>x);
}
void sync_tanks(void);
void move_tanks(void);
static uint8_t tank_on_bridge(uint8_t n)
{
    int16_t center=tanks[n].x+4,bridge=object_x(n);
    return ID(n)==8 && tanks[n].status==1 && center>=bridge && center<bridge+widths[8];
}
static void destroy_tank(uint8_t n)
{
    tanks[n].status=2; tanks[n].explosion=12; tank_bonus=1;
    if (road_gunner==n) bank_tanks[2].shot_phase=0;
}

static void bank_round_hits_fuel(bank_tank_t *t);
static void helicopter_shots_tick(uint8_t scroll)
{
    uint8_t n,id;
    int16_t y;
    helicopter_shot_t *s;
    if (ready || MODE) return;
    for (n=0;n<6;++n) {
        s=helicopter_shots+n;
        if (s->active) {
            s->y+=scroll; s->x+=s->direction ? -2 : 2;
            /* All four opaque columns must remain in water. Native land
             * masks include brown rims and central islands. */
            if (s->y>=159 || s->x<=-8 || s->x>=160 ||
                !helicopter_water_at(s->x+2,s->y+1)) s->active=0;
            else continue;
            /* Replace a spent shot in this same tick, without a cooldown. */
        }
        id=ID(n);
        if ((id!=5 && id!=6) || !helicopter_type(n)) continue;
        y=128+OFFSET-(int16_t)n*32+12;
        if (y<0 || y>=160) continue;
        s->direction=(OBJSTATE(n)&8)!=0;
        s->x=object_x(n)+(s->direction ? -6 : 6); s->y=y;
        if (helicopter_water_at(s->x+2,y+1)) s->active=1;
    }
}
static void helicopter_shots_collisions(void)
{
    uint8_t n,y,x,bits,px=PX+(reflected!=0);
    int16_t dx;
    helicopter_shot_t *s;
    if (ready || MODE) return;
    for (n=0;n<6;++n) {
        s=helicopter_shots+n;
        if (!s->active || s->y+1<player_y || s->y+1>=player_y+18) continue;
        y=s->y+1-player_y;
        bits=G(JET_ADDRESS+18-y);
        for (x=0;x<8;++x) if (bits&(reflected ? (1<<x) : (0x80>>x))) {
            dx=px+x-s->x;
            if (dx>=2 && dx<6) {rr_tank_crash(); return;}
        }
    }
}
static void helicopter_shots_render(void)
{
    uint8_t n;
    sprite_t *s;
    for (n=0;n<6;++n) if (helicopter_shots[n].active) {
        /* A helicopter and a bridge tank cannot occupy the same block.
         * Their companion descriptor therefore serves either extension. */
        s=sprites+n+10;
        if (s->y!=-256) continue;
        s->x=helicopter_shots[n].x*2; s->y=RIVER_TOP+helicopter_shots[n].y;
        s->image=XRAM_HELICOPTER_SHOT; s->palette=XRAM_PALETTE;
        s->size=0x01; s->options=0x42;
    }
}
static void clear_enemy_shots(void)
{
    bank_tanks[0].shot_phase=bank_tanks[1].shot_phase=bank_tanks[2].shot_phase=0;
    memset(helicopter_shots,0,sizeof(helicopter_shots));
}
/* Interpolate the drop over the selected range, stopping at track height.
 * Use main RAM for this helper; the auxiliary segment is almost full. */
#pragma code-name(push, "CODE")
#pragma optimize(push, on)
static uint8_t bank_shot_height(bank_tank_t *t)
{
    static int16_t start,distance,travelled;
    start=t->side ? t->x-6 : t->x+TANK_WIDTH-2;
    distance=t->side ? start-t->shot_target : t->shot_target-start;
    travelled=t->side ? start-t->shot_x : t->shot_x-start;
    if (distance<=0 || travelled>=distance) return TANK_TRACK_BOTTOM_Y;
    if (travelled<=0) return TANK_MUZZLE_Y;
    return TANK_MUZZLE_Y+(uint16_t)travelled*(TANK_TRACK_BOTTOM_Y-TANK_MUZZLE_Y)/distance;
}
#pragma optimize(pop)
#pragma code-name(pop)
static uint8_t bank_choose_target(bank_tank_t *t)
{
    uint8_t y,r,a,b,left=0,right=160,count;
    /* The largest circle spans eight logical columns and sixteen rows.
     * Intersect actual water intervals across its entire footprint. When
     * an island splits the river, stay in the channel facing this tank. */
    if (t->y<8-TANK_TRACK_BOTTOM_Y || t->y>152-TANK_TRACK_BOTTOM_Y) return 0;
    for (y=0;y<16;++y) {
        r=terrain_row(t->y+TANK_TRACK_BOTTOM_Y-8+y);
        a=river_left[r]; b=river_right[r];
        if (a>=b) return 0;
        if (b==80) b=160-a;
        else if (t->side) {r=a; a=160-b; b=160-r;}
        if (a>left) left=a;
        if (b<right) right=b;
        if (left>=right || right-left<8) return 0;
    }
    /* Separate random state preserves the original course generator.
     * Scale into all legal circle origins, including both endpoints. */
    bank_shot_random=(bank_shot_random>>1)^((bank_shot_random&1) ? 0xb8 : 0);
    count=right-left-7;
    t->shot_target=left+(((uint16_t)bank_shot_random*count)>>8);
    return 1;
}
static void bank_tanks_tick(uint8_t scroll)
{
    uint8_t n,y,r,edge;
    int16_t target,sy;
    bank_tank_t *t;
    t=bank_tanks+2;
    /* The body remains owned by its native road block. Match the previous
     * screen row so a block shift preserves the round and firing cooldown. */
    if (road_gunner==255) {
        if (t->status) memset(t,0,sizeof(*t));
    } else {
        sy=128+OFFSET-(int16_t)road_gunner*32-scroll;
        if (!t->status || t->y!=sy) {
            memset(t,0,sizeof(*t));
            t->x=tanks[road_gunner].x; t->y=sy;
            t->side=tanks[road_gunner].direction;
            t->ground_target=t->x; t->status=1;
        }
    }
    for (n=0;n<3;++n) {
        t=bank_tanks+n;
        if (!t->status) continue;
        t->y+=scroll;
        if (t->y>=160) {memset(t,0,sizeof(*t)); continue;}
        /* Follow the terrain through death and attract mode, even while
         * approach, firing and explosion timers are stopped. */
        if (ready || MODE) continue;
        if (t->status==2) {
            if (t->timer) --t->timer;
            continue;
        }
        /* Fit every opaque tank row on real ground, with a two-pixel gap.
         * Sampling the entire body also handles a sharply sloping shore. */
        target=t->ground_target;
        if (!target) {
            edge=t->side ? 0 : 160;
            for (y=TANK_TOP;y<TANK_TOP+TANK_HEIGHT;++y) {
                sy=t->y+y; if (sy<0 || sy>=160) continue;
                r=terrain_row(sy);
                if (t->side) {
                    if (player_outer_right[r]>edge) edge=player_outer_right[r];
                } else if (player_outer_left[r]<edge) edge=player_outer_left[r];
            }
            target=t->side ? edge+2 : (int16_t)edge-TANK_WIDTH-2;
            if (target<0) target=0;
            if (target>160-TANK_WIDTH) target=160-TANK_WIDTH;
            /* The tank and its ground move down together. Its destination
             * is a world coordinate; scrolling does not change this edge. */
            t->ground_target=target;
        }
        if (!(FRAME&1)) {
            if (t->x<target) ++t->x;
            else if (t->x>target) --t->x;
        }
        if (t->cooldown) --t->cooldown;
        if (t->shot_phase==1) {
            t->shot_x+=t->side ? -2 : 2;
            /* Cache the drop for rendering and collisions in this frame.
             * During the splash, timer instead counts explosion phases. */
            t->timer=bank_shot_height(t)-TANK_MUZZLE_Y;
            bank_round_hits_fuel(t);
            if (!t->shot_phase) continue;
            if (t->side ? t->shot_x<=t->shot_target : t->shot_x>=t->shot_target) {
                t->shot_x=t->shot_target; t->shot_phase=2; t->timer=18;
            }
        } else if (t->shot_phase==2) {
            if (--t->timer==0) t->shot_phase=0;
        } else if (t->x==target && !t->cooldown) {
            if (!bank_choose_target(t)) {t->cooldown=8; continue;}
            t->shot_x=t->side ? t->x-6 : t->x+TANK_WIDTH-2;
            t->shot_phase=1; t->timer=0; t->cooldown=90;
        }
    }
    /* Native blocks arrive every 32 rows. Separate tanks by at least two
     * blocks; reuse native scenery seeds without consuming its random state. */
    if (ready || MODE || G(0xbd)<7 || !scroll || OFFSET>=scroll || ID(4)==8 || ID(4)==9) return;
    for (n=0;n<2;++n) if (bank_tanks[n].status && bank_tanks[n].y<64) return;
    for (n=0;n<2;++n) if (!bank_tanks[n].status) {
        t=bank_tanks+n;
        t->side=(G(0xaa)^G(0xb0)^G(0xbd))&1;
        t->x=t->side ? 160 : -8; t->y=OFFSET;
        t->status=1; t->cooldown=20;
        break;
    }
}

/* Each size is visible for three frames, followed by three clear frames.
 * 255 hides the sprite and disables its collision, including the final gap. */
static const uint8_t tank_explosion_phases[19]={
    255,255,255,255,2,2,2,255,255,255,1,1,1,255,255,255,0,0,0
};
static uint8_t tank_explosion_stage(uint8_t timer)
{ return tank_explosion_phases[timer]; }

#pragma optimize(push, on)
static void bank_round_hits_fuel(bank_tank_t *t)
{
    uint8_t n,x,y;
    int16_t ox,oy,dx,dy,shot_y;
    if (t->shot_phase!=1) return;
    shot_y=t->y+TANK_MUZZLE_Y+t->timer-1;
    for (n=0;n<6;++n) {
        if (ID(n)!=10) continue;
        ox=object_x(n); oy=128+OFFSET-(int16_t)n*32;
        if (t->shot_x+6<=ox || t->shot_x+2>=ox+widths[10]) continue;
        for (y=0;y<sizeof(tank_shell_pixels)/sizeof(tank_shell_pixels[0]);++y) {
            dy=shot_y+y-oy; if (dy<0 || dy>=32) continue;
            for (x=2;x<6;++x) if (tank_shell_pixels[y][x]!='.') {
                dx=t->shot_x+x-ox;
                if (dx>=0 && dx<widths[10] && opaque(10,dx,dy,(OBJSTATE(n)&8)!=0,n)) {
                    /* Use the native explosion sequence and sound, while
                     * leaving the player's score and missile untouched. */
                    ID(n)=1; G(0xfa)=23; t->shot_phase=0; return;
                }
            }
        }
    }
}

#pragma optimize(pop)
static void bank_tanks_collisions(void)
{
    uint8_t n,y,x,bits,stage,px=PX+(reflected!=0);
    int16_t dy,dx,by=153-(int16_t)MY;
    bank_tank_t *t;
    if (ready || MODE) return;
    if (!(bank_tanks[0].status|bank_tanks[1].status|bank_tanks[2].status)) return;
    for (n=0;n<3;++n) {
        t=bank_tanks+n;
        if (t->status!=1) continue;
        if (n<2 && !tank_bonus && MY<=161 && MX>=t->x && MX<t->x+TANK_WIDTH) {
            for (y=0;y<8;++y) {
                dy=by+y-t->y;
                if (dy>=0 && dy<32 && opaque(TANK_ID,MX-t->x,dy,t->side,0)) {
                    t->status=2; t->timer=12; t->shot_phase=0;
                    MY=180; tank_bonus=1; break;
                }
            }
        }
        if (t->status!=1 || t->shot_phase!=2) continue;
        stage=tank_explosion_stage(t->timer);
        if (stage==255) continue;
        /* Traveling rounds are safe, as in the 5200 manual. Only opaque
         * splash pixels are tested against opaque native jet pixels. */
        for (y=0;y<18;++y) {
            dy=player_y+y-(t->y+TANK_TRACK_BOTTOM_Y-8); if (dy<0 || dy>=16) continue;
            bits=G(JET_ADDRESS+18-y);
            for (x=0;x<8;++x) if (bits&(reflected ? (1<<x) : (0x80>>x))) {
                dx=px+x-t->shot_x;
                if (dx>=0 && dx<8 && tank_circle_pixels[stage][dy][dx]!='.') {
                    rr_tank_crash(); return;
                }
            }
        }
    }
}

static void bank_tanks_render(void)
{
    uint8_t n,stage;
    bank_tank_t *t;
    sprite_t *s;
    if (!(bank_tanks[0].status|bank_tanks[1].status|bank_tanks[2].status)) return;
    for (n=0;n<3;++n) {
        t=bank_tanks+n;
        if (!t->status) continue;
        if (n==2) {s=sprites+ROAD_SHOT_SPRITE-1; goto shot;}
        s=sprites+16+n*2;
        s->x=t->x*2; s->y=RIVER_TOP+t->y;
        s->image=tank_image(); s->palette=XRAM_TANK_PALETTE;
        s->y+=TANK_TOP;
        /* Hardware mirrors padded storage; cancel its three blank columns. */
        if (t->side) s->x-=(TANK_IMAGE_WIDTH-TANK_WIDTH)*2;
        s->size=0x32; s->options=0x42|(t->side ? 0x10 : 0);
        if (t->status==2) {
            if (!t->timer) {s->y=-256; continue;}
            s->x=t->x*2; s->image=XRAM_TANK_BLAST; s->palette=XRAM_PALETTE; s->size=0x11;
            continue;
        }
shot:
        if (t->shot_phase) {
            stage=t->shot_phase==2 ? tank_explosion_stage(t->timer) : 0;
            if (stage==255) continue;
            ++s; s->x=t->shot_x*2;
            s->y=RIVER_TOP+t->y+(t->shot_phase==1 ? TANK_MUZZLE_Y+t->timer-1 : TANK_TRACK_BOTTOM_Y-8);
            s->image=t->shot_phase==1 ? XRAM_TANK_SHELL :
                XRAM_TANK_CIRCLES+(uint16_t)stage*64;
            s->palette=XRAM_TANK_EXPLOSION_PALETTE;
            s->size=t->shot_phase==1 ? 0x01 : 0x31; s->options=0x42;
        }
    }
}
#pragma code-name(pop)
static void collisions(void)
{
    static uint8_t n,y,x,bits,id,scale,flip,px,jbits;
    static int16_t ox,oy,sy,dy,dx,by;
    player_y=duo_call ? duo_p->y : 142;
    px=PX+(reflected!=0); by=153-(int16_t)MY;
    G(0xe2)=G(0xe4)=G(0xe6)=G(0xe8)=255; tank_bonus=0;
    bank_tanks_collisions();
    helicopter_shots_collisions();
    for (n=6;n>0;) {
        --n; /* The TIA kernel visits upper blocks before lower blocks. */
        id=ID(n); if (id>BALLOON_ID) continue;
        ox=object_x(n); oy=128+OFFSET-(int16_t)n*32;
        if (!ready && !MODE && (id==8 || id<4) && tanks[n].status==1) {
            static int16_t tx;
            static uint8_t tf;
            tx=tanks[n].x; tf=tanks[n].direction;
            if (MY<=161 && MX>=tx && MX<tx+TANK_WIDTH) {
                for (y=0;y<8;++y) {
                    dy=by+y-oy;
                    if (dy>=0 && dy<32 && opaque(TANK_ID,MX-tx,dy,tf,0)) {
                        if (tank_on_bridge(n)) G(0xe2)=n;
                        else MY=180;
                        destroy_tank(n); break;
                    }
                }
            }
            if (tanks[n].status==1 && tx+TANK_WIDTH>px && tx<px+8 && oy<player_y+18 && oy+32>player_y) {
                for (y=0;y<18;++y) {
                    dy=player_y+y-oy; if (dy<0 || dy>=32) continue;
                    jbits=G(JET_ADDRESS+18-y);
                    for (x=0;x<8;++x) if (jbits&(reflected ? (1<<x) : (0x80>>x))) {
                        dx=px+x-tx;
                        if (dx>=0 && dx<TANK_WIDTH && opaque(TANK_ID,dx,dy,tf,0)) {
                            rr_tank_crash(); goto tank_checked;
                        }
                    }
                }
            }
        }
tank_checked:
        flip=(OBJSTATE(n)&8)!=0; scale=scales[id]; FLAGS(n)&=~32;
        if (!MODE && G(0xbd)>=2 && ((id>=5 && id<=7) || id==BALLOON_ID) && (FLAGS(n)&0x40)) {
            collision_scale=scale;
            for (y=6;y<29;++y) {
                sy=oy+y; if (sy<0 || sy>=160) continue;
                bits=masks[id][y];
                if (!bits) continue;
                collision_mask=flip ? reverse_bits[bits] : bits;
                if (mask_land(((unsigned)sy<<8)|(uint8_t)ox)) {
                    FLAGS(n)|=32; goto enemy_checked;
                }
            }
        }
enemy_checked:
        if (ready || MODE) continue;
        if (!tank_bonus && MY<=161 && MX>=ox && MX<ox+widths[id]) {
            for (y=0;y<8;++y) {
                dy=by+y-oy;
                if (dy>=0 && dy<32 && opaque(id,MX-ox,dy,flip,n)) {
                    G(0xe2)=n;
                    if (id==8 && tank_on_bridge(n)) destroy_tank(n);
                    break;
                }
            }
        }
        if (ox+widths[id]<=px || ox>=px+8 || oy>=player_y+18 || oy+32<=player_y) continue;
        for (y=0;y<18;++y) {
            dy=player_y+y-oy; if (dy<0 || dy>=32) continue;
            /* Empty object rows cannot touch the plane, even when the
             * padded 32-row sprite rectangles overlap at different Y. */
            if (!masks[id][dy]) continue;
            jbits=G(JET_ADDRESS+18-y);
            if (!jbits) continue;
            /* Eight-column objects can use exact row masks directly.
             * DUO jets now fly through several blocks; avoid up to eight
             * opaque() calls per row when overlapping a fuel depot. */
            if (scale==1) {
                bits=masks[id][dy];
                if (flip) bits=reverse_bits[bits];
                if (reflected) jbits=reverse_bits[jbits];
                dx=ox-px;
                if (dx>=0 ? (jbits&(bits>>dx)) : (bits&(jbits>>-dx))) {
                    G(0xe8)=n; goto player_checked;
                }
                continue;
            }
            for (x=0;x<8;++x) if (jbits&(reflected ? (1<<x) : (0x80>>x))) {
                dx=px+x-ox;
                if (dx>=0 && dx<widths[id] && opaque(id,dx,dy,flip,n)) {G(0xe8)=n; goto player_checked;}
            }
        }
player_checked:;
    }
    if (ready || MODE) return;
    collision_scale=1;
    for (y=0;y<18;++y) {
        bits=G(JET_ADDRESS+18-y);
        if (!bits) continue;
        collision_mask=reflected ? reverse_bits[bits] : bits;
        if (mask_player_land(((unsigned)(player_y+y)<<8)|px)) {
            G(0xe4)=0; goto jet_checked;
        }
    }
jet_checked:
    if (MY<=161) for (y=0;y<8;++y) {
        sy=by+y;
        if (sy>=0 && sy<160 && land_at(MX,sy)) {G(0xe6)=0; break;}
    }
}
#include "duo.inc"
/* Keep bounded input decoding compact in the fixed Debug memory map. */
#pragma optimize(push, on)
static uint8_t pressed(uint8_t code)
{ return (keys[code>>3]&(1<<(code&7)))!=0; }
static uint8_t read_input(void)
{
    static uint8_t n,v;
    static uint8_t* pad;
    xram0_read(keys,XRAM_KEYBOARD,32); xram0_read(pads,XRAM_GAMEPADS,40);
    inputs[0]=inputs[1]=0;
    if (pressed(0x52)) inputs[0]|=UP;
    if (pressed(0x51)) inputs[0]|=DOWN;
    if (pressed(0x50)) inputs[0]|=LEFT;
    if (pressed(0x4f)) inputs[0]|=RIGHT;
    if (pressed(0x2c)||pressed(0x28)) inputs[0]|=FIRE;
    if (pressed(0x1a)) inputs[1]|=UP;
    if (pressed(0x16)) inputs[1]|=DOWN;
    if (pressed(0x04)) inputs[1]|=LEFT;
    if (pressed(0x07)) inputs[1]|=RIGHT;
    if (pressed(0xe0)) inputs[1]|=FIRE;
    for (n=0;n<2;++n) {
        pad=pads+n*10;
        if (pad[0]&0x80) {
            v=VAR==2 ? 1 : n;
            inputs[v]|=(pad[0]|pad[1])&15;
            if (pad[2]&0x1b) inputs[v]|=FIRE;
            if (pad[3]&8) inputs[v]|=PAUSE;
            if (pad[3]&4) inputs[v]|=START;
        }
    }
    if (!VAR) inputs[0]|=inputs[1];
    v=inputs[0]|inputs[1];
    if (pressed(0x15)) v|=START;
    if (pressed(0x13)) v|=PAUSE;
    if (pressed(0x29)) v|=QUIT;
    G(0x280)=(uint8_t)~((inputs[0]&15)<<4|(inputs[1]&15));
    G(0x22c)=(inputs[0]&FIRE) ? 0 : 128;
    G(0x22d)=(inputs[1]&FIRE) ? 0 : 128;
    return v;
}
#pragma optimize(pop)
/* Pack the first eight readable pixels into the MSB-first glyph format. */
/* Keep presentation compact enough for all three audio backends in Debug. */
#pragma optimize (push, on)
static uint8_t bitmap_row(const char* pixels)
{
    uint8_t bits=0,mask=0x80;
    while (*pixels && mask) {
        if (*pixels++=='X') bits|=mask;
        mask>>=1;
    }
    return bits;
}
static void hud_label(uint8_t x,uint8_t top,const char* text,uint8_t ink)
{
    uint8_t glyphs[6],n=0,i,y;
    const char* letter;
    while (text[n] && n<6) {
        if (text[n]>='0' && text[n]<='9') glyphs[n]=text[n]-'0';
        else {
            letter=strchr(hud_letters,text[n]);
            glyphs[n]=letter ? 10+(letter-hud_letters) : 0;
        }
        ++n;
    }
    hud_column=x; hud_length=n*4; hud_ink=ink;
    for (y=0;y<5;++y) {
        memset(row+x,0xaa,hud_length);
        for (i=0;i<n;++i) draw_glyph(x+i*4,bitmap_row(hud_font[glyphs[i]][y]));
        write_hud_span(XRAM_HUD+(uint16_t)(top+y)*RIVER_WIDTH+x);
    }
}
void demo_footer_tick(void);
static void hud_details(void)
{
    static uint8_t level,reserves,i,dirty;
    demo_footer_tick();
    level=G(0xbd); reserves=G(0xc0)<80 ? G(0xc0)/8 : 0; dirty=high_dirty;
    if (shown_level!=level || shown_variant!=VAR) {
        /* Digit images are prepared once. Three sprites avoid rasterizing
         * extra numbers during the same frame as a reset and palette change. */
        hud_sprites[0].image=XRAM_SCORE_DIGITS+(uint16_t)(VAR+1)*32;
        hud_sprites[1].image=XRAM_SCORE_DIGITS+(uint16_t)(level/10)*32;
        hud_sprites[1].y=level>=10 ? HUD_TOP+HUD_GAME_Y : -256;
        hud_sprites[2].image=XRAM_SCORE_DIGITS+(uint16_t)(level%10)*32;
        shown_level=level; shown_variant=VAR; dirty=1;
    }
    if (high_dirty) {
        for (i=0;i<6;++i) hud_sprites[i+3].image=XRAM_SCORE_DIGITS+(uint16_t)(high_score[i]>>3)*32;
        high_dirty=0;
    }
    if (shown_reserves!=reserves) {
        for (i=0;i<9;++i) hud_sprites[i+9].y=i<reserves ? HUD_TOP+HUD_RESERVES_Y : -256;
        shown_reserves=reserves; dirty=1;
    }
    if (dirty) upload(XRAM_HUD_SPRITES,hud_sprites,sizeof(hud_sprites));
    if (shown_player!=PLAYER) {
        hud_label(HUD_PLAYER_X,6,PLAYER ? "P2" : "P1",VAR==1 ? 0x88 : 0xbb); shown_player=PLAYER;
    }
}
static void update_high_score(void)
{
    static uint8_t i,current,previous;
    /* Compare the original six decimal glyph pointers, avoiding conversion
     * to a 32-bit number. A restart preserves the session's high score. */
    for (i=0;i<6;++i) {
        current=G(0xcd+i*2); if (current==88) current=0;
        previous=high_score[i]; if (previous==88) previous=0;
        if (current<previous) return;
        if (current>previous) {
            for (i=0;i<6;++i) high_score[i]=G(0xcd+i*2);
            high_dirty=1; return;
        }
    }
}
static void draw_hud(void)
{
    static uint8_t y,i,bits,fy;
    fy=G(0xb7)>>3;
    hud_ink=0x88;
    if (hud_dirty&1) {
        hud_column=HUD_SCORE_X; hud_length=48;
        for (y=0;y<6;++y) {
            memset(row+HUD_SCORE_X,0xaa,48);
            for (i=0;i<6;++i) {
                bits=score_rows[G(0xcd+i*2)>>3][y]; draw_glyph(HUD_SCORE_X+i*8,bits);
            }
            write_hud_span(XRAM_HUD+(uint16_t)(HUD_SCORE_Y+y)*RIVER_WIDTH+HUD_SCORE_X);
        }
    }
    if (hud_dirty&2) {
        hud_column=HUD_FUEL_X; hud_length=HUD_FUEL_WIDTH;
        for (y=0;y<HUD_FUEL_HEIGHT;++y) {
            memcpy(row+HUD_FUEL_X,fuel_rows[y],HUD_FUEL_WIDTH);
            /* Keep the gauge lettering in front of the moving needle. */
            if (y>=5 && y<15) for (i=0;i<2;++i)
                if (fuel_rows[y][4+fy+i]==0xaa) row[HUD_FUEL_X+4+fy+i]=0xbb;
            write_hud_span(XRAM_HUD+(uint16_t)(HUD_FUEL_Y+y)*RIVER_WIDTH+HUD_FUEL_X);
        }
    }
    memcpy(old_score,(void*)0xcd,12); old_fuel=fy; hud_dirty=0;
}
static void duo_lives_hud(void)
{
    static uint8_t n,i,lives,previous;
    static uint16_t address;
    for (n=0;n<2;++n) {
        lives=VAR==2 ? duo_players[n].lives>>3 : 0;
        previous=shown_duo_lives[n];
        if (previous==lives) continue;
        shown_duo_lives[n]=lives;
        /* Only show/hide icons whose state changed; positions and colors
         * are initialized once. Avoid uploading twenty sprites per change. */
        i=lives<previous ? lives : previous;
        address=XRAM_DUO_LIFE_SPRITES+(n*DUO_MAX_LIVES+i)*sizeof(sprite_t)+2;
        for (;i<lives || i<previous;++i) {
            xram0_poke16(address,i<lives ? HUD_TOP+DUO_FUEL_Y+(i>=5 ? 9 : 0) : -256);
            address+=sizeof(sprite_t);
        }
    }
}
static void render(void)
{
    static uint8_t n,id;
    static uint16_t c;
    if (paused) sync_tanks();
    /* Native death freezes game ticks. Remove their last projectile frame
     * before presenting the jet explosion, including deaths from terrain. */
    if (MODE>=128) clear_enemy_shots();
    for (n=0;n<SPRITE_COUNT;++n) sprites[n].y=-256;
    jet_image();
    sprites[0].x=(PX+(reflected!=0))*2; sprites[0].y=RIVER_TOP+142;
    sprites[0].image=JET_IMAGE; sprites[0].palette=XRAM_JET_PALETTE;
    sprites[0].size=0x41; sprites[0].options=0x42|(reflected ? 0x10 : 0);
    if (ready) sprites[0].y=-256;
    if (!ready && MY<=161) {
        sprites[1].x=MX*2; sprites[1].y=RIVER_TOP+153-(int16_t)MY;
        sprites[1].image=BULLET_IMAGE; sprites[1].palette=XRAM_JET_PALETTE;
        sprites[1].size=0x10; sprites[1].options=0x42;
    }
    for (n=0;n<6;++n) {
        id=ID(n); if (id>BALLOON_ID) continue;
        if (id!=5 && id!=6) helicopter_types[n]=0;
        sprites[n+2].x=object_x(n)*2; sprites[n+2].y=RIVER_TOP+128+OFFSET-(int16_t)n*32;
        sprites[n+2].image=image_address(id);
        if ((id==5 || id==6) && helicopter_type(n)) sprites[n+2].image+=128;
        if (id==9) sprites[n+2].image=mountain_images[mountain_variant(n)];
        sprites[n+2].palette=palette_address(id);
        sprites[n+2].size=0x70|((widths[id]>>2)-1);
        sprites[n+2].options=0x42|((OBJSTATE(n)&8) ? 0x10 : 0);
        if ((OBJSTATE(n)&7)==1) {
            sprites[n+2].size=0x71;
            sprites[8]=sprites[n+2]; sprites[8].x+=32;
        } else if (id<4 && (OBJSTATE(n)&7)==5) {
            sprites[n+2].image=EXTRA_IMAGES+(uint16_t)id*256;
            sprites[n+2].size=0x73;
        }
        if (id==4 && (sprites[n+2].x<0 || sprites[n+2].x>304)) {
            sprites[9]=sprites[n+2];
            sprites[9].x+=sprites[n+2].x<0 ? 320 : -320;
        }
        if ((id==8 || id<4) && (tanks[n].status==1 || tanks[n].explosion)) {
            uint8_t ti=tanks[n].status==1 ? TANK_ID : 1;
            sprites[n+10].x=tanks[n].x*2; sprites[n+10].y=sprites[n+2].y;
            sprites[n+10].image=ti==TANK_ID ? tank_image() : image_address(ti);
            sprites[n+10].palette=palette_address(ti);
            sprites[n+10].size=0x71;
            sprites[n+10].options=0x42|(tanks[n].direction ? 0x10 : 0);
            if (ti==TANK_ID) {
                sprites[n+10].y+=TANK_TOP; sprites[n+10].size=0x32;
                if (tanks[n].direction) sprites[n+10].x-=(TANK_IMAGE_WIDTH-TANK_WIDTH)*2;
            }
        }
    }
    bank_tanks_render();
    helicopter_shots_render();
    /* Keep the legacy descriptor at zero for diagnostics. PIX has one
     * sprite list per plane: both front-plane jets must be contiguous. */
    sprites[PLAYER_SPRITE]=sprites[0];
    if (VAR==2) duo_render();
    terrain.y_pos_px=RIVER_TOP-ring_top;
    /* World position and sprites stay in RAM until the next VSYNC. Publish
     * them together before doing any input, collision or terrain work. */
    if (palette_mask!=G(0x86) || palette_xor!=G(0x85)) refresh_palettes();
    /* Refresh the jet and GAME 2 player HUD together on a turn change. */
    else if (palette_player!=PLAYER) refresh_jet_palette();
    if (G(0x8d)) {
        c=tia_color((G(0x8d)&1) ? 0x42 : rr_ColorTab[4]);
        if (!paused) --G(0x8d);
        xram0_poke16(XRAM_PALETTE+2,c);
    } else xram0_poke16(XRAM_PALETTE+2,tia_color(rr_ColorTab[4]));
    audio_update(paused,ready || MODE==255);
    state_bytes[0]=0x52; state_bytes[1]=3;
    state_bytes[2]=ready || MODE==255 ? 3 : MODE==0 ? 1 : MODE>=128 ? 2 : 0;
    state_bytes[3]=PX; state_bytes[4]=G(0xc0)<(VAR==2 ? 88 : 80) ? G(0xc0)/8 : 0;
    state_bytes[5]=G(0xbd); state_bytes[6]=G(0xb8); state_bytes[7]=G(0xb7);
    state_bytes[8]=MY<=161; state_bytes[9]=MX; state_bytes[10]=MY;
    state_bytes[11]=paused; state_bytes[12]=OFFSET; state_bytes[13]=G(0xf8)>=3;
    state_bytes[14]=ticks; state_bytes[15]=ticks>>8;
    for (n=0;n<6;++n) state_bytes[16+n]=G(0xcd+n*2);
    state_bytes[22]=G(0xb9); state_bytes[23]=G(0x84);
    state_bytes[24]=G(0xe9); state_bytes[25]=G(0xea);
    state_bytes[26]=G(0xb5); state_bytes[27]=MODE;
    state_bytes[28]=VAR; state_bytes[29]=PLAYER;
    state_bytes[30]=skipped_frames; state_bytes[31]=skipped_frames>>8;
    upload(XRAM_STATE,state_bytes,32);
    duo_lives_hud();
    if (hud_pending) return;
    if (VAR==2) {
        upload(XRAM_DUO_STATE,duo_players,sizeof(duo_players));
        duo_hud(); return;
    }
    if (memcmp(old_score,(void*)0xcd,12)) {hud_dirty|=1; update_high_score();}
    if (old_fuel!=(G(0xb7)>>3)) hud_dirty|=2;
    if (hud_dirty) draw_hud();
    hud_details();
}
#pragma code-name(push, "SPLASH")
static void hud_layout(void)
{
    static uint8_t i,y;
    if (hud_pending==4) {hud_pending=0; return;}
    if (hud_pending==3) {
        /* Finish classic labels/sprites before rasterizing score and fuel.
         * Returning from DUO can otherwise exceed a frame at 8 MHz. */
        if (VAR!=2) {hud_details(); hud_pending=4;}
        else hud_pending=0;
        return;
    }
    shown_level=shown_variant=shown_player=shown_reserves=shown_demo=255;
    palette_player=255; high_dirty=1;
    if (VAR==2) {
        if (hud_pending<2) {
        refresh_duo_hud_palettes();
        hud_dirty=7;
        old_score[0]=old_score[1]=255;
        for (i=0;i<HUD_SPRITE_COUNT;++i) {
            hud_sprites[i].y=-256; hud_sprites[i].size=0x11;
            hud_sprites[i].palette=XRAM_HUD_BLACK_PALETTE;
        }
        hud_label(4,3,"P1",0x88); hud_label(84,3,"P2",0x66);
        for (i=0;i<12;++i) {
            hud_sprites[i].x=(20+(i/6)*80+(i%6)*8)*2;
            hud_sprites[i].y=HUD_TOP+2;
            hud_sprites[i].palette=i<6 ? XRAM_DUO_HUD_P1_PALETTE : XRAM_DUO_HUD_P2_PALETTE;
        }
        hud_sprites[14].x=44*2; hud_sprites[14].y=HUD_TOP+DUO_STAGE_Y;
        hud_sprites[14].image=XRAM_SCORE_DIGITS+3*32;
        hud_sprites[15].x=hud_sprites[10].x; hud_sprites[16].x=hud_sprites[11].x;
        hud_sprites[16].y=HUD_TOP+DUO_STAGE_Y;
        hud_sprites[15].palette=hud_sprites[16].palette=XRAM_PALETTE;
        if (hud_pending) {hud_pending=2; return;}
        }
        hud_column=4; hud_length=32; hud_ink=0x77;
        for (y=0;y<6;++y) {
            memset(row+4,0xaa,32);
            for (i=0;i<4;++i) draw_glyph(4+i*8,bitmap_row(game_label[i][y]));
            write_hud_span(XRAM_HUD+(uint16_t)(DUO_STAGE_Y+y)*RIVER_WIDTH+4);
        }
        hud_column=84; hud_ink=0x55;
        for (y=0;y<6;++y) {
            memset(row+84,0xaa,32);
            for (i=0;i<4;++i) draw_glyph(84+i*8,bitmap_row(bridge_label[y]+i*8));
            write_hud_span(XRAM_HUD+(uint16_t)(DUO_STAGE_Y+y)*RIVER_WIDTH+84);
        }
        if (hud_pending) hud_pending=3;
        return;
    }
    if (hud_pending<2) {
    for (i=0;i<HUD_SPRITE_COUNT;++i) {
        hud_sprites[i].y=-256;
        hud_sprites[i].palette=VAR==1 && i>=9 ? XRAM_GAME2_LIFE_PALETTE : XRAM_PALETTE;
        hud_sprites[i].size=0x11; hud_sprites[i].options=0x42;
        if (i>=3 && i<9) {
            hud_sprites[i].x=(HUD_RECORD_X+(i-3)*8)*2; hud_sprites[i].y=HUD_TOP+HUD_SCORE_Y;
            hud_sprites[i].palette=XRAM_HUD_BLACK_PALETTE;
        } else if (i>=9 && i<18) {
            hud_sprites[i].x=(88+(i-9)*8)*2; hud_sprites[i].image=XRAM_RESERVE_IMAGE;
        }
    }
    hud_sprites[0].x=HUD_GAME_NUMBER_X*2; hud_sprites[0].y=HUD_TOP+HUD_GAME_NUMBER_Y;
    hud_sprites[0].palette=XRAM_HUD_BLACK_PALETTE;
    hud_sprites[1].x=(HUD_BRIDGE_NUMBER_X-8)*2;
    hud_sprites[2].x=HUD_BRIDGE_NUMBER_X*2; hud_sprites[2].y=HUD_TOP+HUD_GAME_Y;
    hud_dirty=7;
    if (hud_pending) {hud_pending=2; return;}
    }
    hud_label(HUD_HI_X,6,"HI",0x77);
    hud_column=HUD_HI_X; hud_length=28; hud_ink=0xbb;
    for (y=0;y<6;++y) {
        memset(row+HUD_HI_X,0xaa,28);
        for (i=0;i<4;++i) draw_glyph(HUD_HI_X+i*8,bitmap_row(bridge_label[y]+i*8));
        write_hud_span(XRAM_HUD+(uint16_t)(HUD_GAME_Y+y)*RIVER_WIDTH+HUD_HI_X);
    }
    hud_column=HUD_GAME_X; hud_length=4*HUD_GAME_PITCH; hud_ink=0x77;
    for (y=0;y<6;++y) {
        memset(row+HUD_GAME_X,0xaa,hud_length);
        for (i=0;i<4;++i) draw_glyph(HUD_GAME_X+i*HUD_GAME_PITCH,bitmap_row(game_label[i][y]));
        write_hud_span(XRAM_HUD+(uint16_t)(HUD_GAME_Y+y)*RIVER_WIDTH+HUD_GAME_X);
    }
    if (hud_pending) hud_pending=3;
}
#pragma code-name(pop)
static void duo_hud(void)
{
    static uint8_t n,i,y,x,fuel,fill,fuel_drawn;
    fuel_drawn=0;
    for (n=0;n<2;++n) {
        duo_p=duo_players+n;
        for (i=0;i<6;++i) hud_sprites[n*6+i].image=XRAM_SCORE_DIGITS+
            (uint16_t)(duo_started ? duo_p->score[i]>>3 : i==5 ? 0 : 11)*32;
        fuel=duo_started ? duo_p->fuel_hi>>3 : 0;
        /* One complete gauge per frame bounds the cost at 8 MHz. A second
         * changed gauge keeps its old value and is drawn on the next frame. */
        if (!fuel_drawn && old_score[n]!=fuel) {
            fuel_drawn=1;
            old_score[n]=fuel; x=4+n*80;
            fill=(uint16_t)fuel*(HUD_FUEL_WIDTH-2)/31;
            hud_fill=fill+1;
            hud_column=x; hud_length=HUD_FUEL_WIDTH; hud_ink=n ? 0x66 : 0x88;
            for (y=0;y<HUD_FUEL_HEIGHT;++y) {
                /* Share GAME 1 artwork; its frame, scale and lettering
                 * remain in front of each pilot's shrinking fuel fill. */
                duo_fuel_row(fuel_rows[y]);
                write_hud_span(XRAM_HUD+(uint16_t)(DUO_FUEL_Y+y)*RIVER_WIDTH+x);
            }
        }
    }
    hud_sprites[15].image=XRAM_SCORE_DIGITS+(uint16_t)(G(0xbd)/10)*32;
    hud_sprites[15].y=G(0xbd)>=10 ? HUD_TOP+DUO_STAGE_Y : -256;
    hud_sprites[16].image=XRAM_SCORE_DIGITS+(uint16_t)(G(0xbd)%10)*32;
    demo_footer_tick();
    upload(XRAM_HUD_SPRITES,hud_sprites,sizeof(hud_sprites)); hud_dirty=0;
}
/* The manual ends at $F0FF. Preserve each terrain row's base color and
 * live descriptors/palettes above it; collision edges remain in CPU RAM. */
static void help_save(void)
{
    uint8_t y;
    uint16_t a;
    for (y=0;y<RIVER_RING;++y)
        xram0_poke8(XRAM_HELP_TERRAIN_COLORS+y,xram0_peek8(XRAM_TERRAIN+(uint16_t)y*TERRAIN_COLUMNS));
    for (a=0;a<HELP_VIDEO_BYTES;a+=sizeof(row)) {
        uint16_t count=HELP_VIDEO_BYTES-a<sizeof(row) ? HELP_VIDEO_BYTES-a : sizeof(row);
        xram0_read(row,XRAM_PALETTE+a,count); upload(XRAM_HELP_VIDEO+a,row,count);
    }
}
static void help_restore_terrain(void)
{
    uint8_t n;
    for (n=0;n<RIVER_RING;++n) {
        shore_color=xram0_peek8(XRAM_HELP_TERRAIN_COLORS+n);
        if (shore_color==TERRAIN_ROAD_UPPER) shore_color=7;
        shore_base=8+(shore_color-2)*18;
        shore_left=river_left[n]; shore_right=river_right[n];
        shore_outer=shore_left-player_outer_left[n];
        shore_inner=player_island_left[n]-shore_right;
        shore_half(); memcpy(row,bank_half,20);
        shore_outer=shore_left-(160-player_outer_right[n]);
        shore_inner=160-player_island_right[n]-shore_right;
        shore_half();
        write_terrain_row(XRAM_TERRAIN+(uint16_t)n*TERRAIN_COLUMNS);
    }
}
static uint8_t configure_video(uint8_t restoring)
{
    static uint8_t y,i,x,bits;
    static sprite_t life_sprite;
    if (xreg(1,0,0,1)<0) return 0;
    for (i=0;i<8;++i) tile_mirror[i]=i;
    for (i=0;i<7;++i) xram0_set(XRAM_TILES+(uint16_t)i*32,i*17,32);
    tile_mirror[TERRAIN_ROAD_UPPER]=TERRAIN_ROAD_UPPER;
    xram0_set(XRAM_TILES+TERRAIN_ROAD_UPPER*32,0x99,32);
    for (i=8;i<TERRAIN_ROAD_UPPER;++i) {
        uint8_t variant=(i-8)%18,land=2+(i-8)/18,pattern=variant%9;
        tile_mirror[i]=variant<9 ? i+9 : i-9;
        for (x=0;x<8;++x) {
            uint8_t pixel=bank_pixels[pattern][variant<9 ? x>>1 : 3-(x>>1)];
            uint8_t color=pixel=='B' ? 12 : pixel=='W' ? 1 : land==7 ? 9 : land;
            if (x&1) row[x>>1]|=color; else row[x>>1]=color<<4;
        }
        for (y=0;y<8;++y) upload(XRAM_TILES+(uint16_t)i*32+y*4,row,4);
    }
    xram0_set(XRAM_TILES+TERRAIN_BANK_SOLID*32,0xcc,32);
    for (i=0;i<128;++i) tia_palette[i]=tia_rgb(i*2);
    prepare_images(); refresh_palettes();
    for (i=0;i<3;++i) {
        write_jet_image((uint16_t)(i==0 ? rr_JetStraight : i==1 ? rr_JetMove : rr_JetExplode)-1);
        xram0_read(row,JET_IMAGE,80); upload(XRAM_DUO_JETS+(uint16_t)i*80,row,80);
    }
    shore_right=80;
    for (i=0;i<128;++i) {
        uint8_t phase=i&63,other=((phase>>3)+9)%24;
        shore_left=64-bank_wave[phase];
        shore_color=i<64 ? 2 : 3; shore_base=8+(shore_color-2)*18;
        shore_outer=bank_widths[phase>>3]; shore_inner=shore_outer;
        reset_tiles[i*4]=shore_tile(56,0); reset_tiles[i*4+1]=shore_tile(60,0);
        shore_outer=bank_widths[other]; shore_inner=shore_outer;
        reset_tiles[i*4+2]=shore_tile(60,1); reset_tiles[i*4+3]=shore_tile(56,1);
    }
    for (i=0;i<12;++i) for (y=0;y<8;++y) {
        bits=y<6 ? bitmap_row(score_digits[i][y]) : 0;
        if (y<6) score_rows[i][y]=bits;
        memset(row,0,4);
        for (x=0;x<6;++x) if (bits&(0x80>>x)) row[x>>1]|=(x&1) ? 11 : 0xb0;
        upload(XRAM_SCORE_DIGITS+(uint16_t)i*32+y*4,row,4);
    }
    for (y=0;y<8;++y) {
        memset(row,0,4);
        for (x=0;x<8;++x) if (reserve_plane[y][x]=='X') row[x>>1]|=(x&1) ? 11 : 0xb0;
        upload(XRAM_RESERVE_IMAGE+y*4,row,4);
    }
    for (y=0;y<8;++y) {
        memset(row,0,32);
        for (x=0;x<sizeof(activision_logo[0])-1;++x) {
            uint8_t pixel=activision_logo[y][x];
            if (pixel!='.') row[x>>1]|=(pixel-'A'+1)<<((x&1) ? 0 : 4);
        }
        upload(XRAM_LOGO_IMAGE+y*32,row,32);
    }
    for (y=0;y<HUD_FUEL_HEIGHT;++y) for (x=0;x<HUD_FUEL_WIDTH;++x)
        fuel_rows[y][x]=fuel_gauge[y][x]=='X' ? 0x77 : 0xaa;
    upload(XRAM_HUD_BITMAP_CONFIG,&hud_bitmap,sizeof(hud_bitmap));
    upload(XRAM_DEMO_FOOTER_CONFIG,&demo_footer,sizeof(demo_footer));
    xram0_set(XRAM_HUD+HUD_PANEL_HEIGHT*RIVER_WIDTH,0x77,(HUD_HEIGHT-HUD_PANEL_HEIGHT)*RIVER_WIDTH);
    hud_pending=0;
    hud_clear(); hud_layout();
    shown_duo_lives[0]=shown_duo_lives[1]=0;
    life_sprite.y=-256; life_sprite.image=XRAM_RESERVE_IMAGE;
    life_sprite.size=0x11; life_sprite.options=0x42;
    for (i=0;i<DUO_LIFE_SPRITE_COUNT;++i) {
        life_sprite.x=(44+(i/10)*80+(i%5)*7)*2;
        life_sprite.palette=i<10 ? XRAM_DUO_HUD_P1_PALETTE : XRAM_DUO_HUD_P2_PALETTE;
        upload(XRAM_DUO_LIFE_SPRITES+i*sizeof(sprite_t),&life_sprite,sizeof(life_sprite));
    }
    /* Prepare the entire first frame before enabling its planes. XRAM still
     * contains cover pixels, so even a partially initialized scene can flash. */
    upload(XRAM_TERRAIN_CONFIG,&terrain,sizeof(terrain));
    if (restoring) {
        uint16_t a;
        help_restore_terrain();
        jet_cache=0xffff; jet_image();
        if (VAR==2) {duo_hud(); duo_hud();}
        else {draw_hud(); hud_details();}
        duo_lives_hud();
        for (a=0;a<HELP_VIDEO_BYTES;a+=sizeof(row)) {
            uint16_t count=HELP_VIDEO_BYTES-a<sizeof(row) ? HELP_VIDEO_BYTES-a : sizeof(row);
            xram0_read(row,XRAM_HELP_VIDEO+a,count); upload(XRAM_PALETTE+a,row,count);
        }
        /* F1 may interrupt a HUD layout spread over several frames. */
        upload(XRAM_HUD_SPRITES,hud_sprites,sizeof(hud_sprites));
    } else {
        rebuild_terrain();
        if (!audio_init()) return 0;
        render(); present_frame();
        game_fade_prepare();
    }
    if (restoring && !audio_init()) return 0;
    if (sound_status_init()<0 ||
        xreg(1,0,1,2,0x702,XRAM_TERRAIN_CONFIG,0,RIVER_TOP,RIVER_TOP+RIVER_HEIGHT)<0 ||
        /* Keep the player on the front plane, above all world sprites. */
        xreg(1,0,1,5,0x38,XRAM_SPRITES+sizeof(sprite_t),PLAYER_SPRITE-1,1,RIVER_TOP,RIVER_TOP+RIVER_HEIGHT)<0 ||
        xreg(1,0,1,5,0x38,XRAM_SPRITES+PLAYER_SPRITE*sizeof(sprite_t),2,2,RIVER_TOP,RIVER_TOP+RIVER_HEIGHT)<0 ||
        xreg(1,0,1,5,0x38,XRAM_HUD_SPRITES,HUD_SPRITE_COUNT,1,HUD_TOP,240)<0 ||
        xreg(1,0,1,5,0x38,XRAM_DUO_LIFE_SPRITES,DUO_LIFE_SPRITE_COUNT,2,HUD_TOP,HUD_TOP+HUD_HEIGHT)<0 ||
        xreg(1,0,1,3,2,XRAM_HUD_BITMAP_CONFIG,0,HUD_TOP,HUD_TOP+HUD_HEIGHT)<0 ||
        xreg(1,0,1,3,2,XRAM_DEMO_FOOTER_CONFIG,1,HUD_FOOTER_Y,HUD_FOOTER_Y+8)<0 ||
        xreg(0,0,0,XRAM_KEYBOARD)<0 || xreg(0,0,2,XRAM_GAMEPADS)<0) return 0;
    if (!restoring) game_fade_in();
    return 1;
}
/* Keep startup and the frame loop compact in the fixed Debug RAM map. */
int main(int argc,char** argv)
{
    uint8_t last_vsync,now,delta,input,controls,changes,old_offset,old_intro,old_variant,scroll,y;
    input=audio_options(argc,argv);
    if (input) return input==1 ? 0 : 2;
    RIA.step0=1; RIA.step1=1;
    show_cover();
    memset((void*)0x200,0,256); G(0x282)=switches; rr_init(); G(0x86)=255;
    /* Prepare the original title scene before showing it, so the river is
     * stationary throughout the startup fade. No joystick is held. */
    G(0x280)=255; G(0x22c)=G(0x22d)=128;
    while (MODE!=255) rr_step();
    xram0_set(XRAM_PSG,0,64);
    if (!configure_video(0)) return 1;
    last_vsync=RIA.vsync;
    for (;;) {
        do {now=RIA.vsync;} while (now==last_vsync);
        delta=now-last_vsync; if (delta>1) skipped_frames+=delta-1;
        last_vsync=now;
        present_frame();
        sound_status_tick();
#ifdef RIVER_PROFILE
        timing_start=timing_stamp=(uint16_t)ria_attr_get(RIA_ATTR_CLK_RUN_MS);
#endif
        /* SELECT first rebuilds the demo world; lay out its HUD afterwards. */
        if (hud_pending && MODE!=255) hud_layout();
        input=read_input(); if (input&QUIT) break;
        if (pressed(0x3a)) {
            uint8_t saved_paused=paused;
            uint16_t saved_footer=footer_offset;
            audio_stop();
            xreg(1,0,0,1);
            help_save();
            show_manual();
            paused=1;
            if (!configure_video(1)) return 1;
            paused=saved_paused; footer_offset=saved_footer;
            upload(XRAM_STATE,state_bytes,32);
            previous_keys=previous_input=0;
            last_vsync=RIA.vsync;
            continue;
        }
        /* Gather F2..F5 from HID byte 7 and F8..F10 from byte 8. */
        controls=((keys[7]>>5)&1)|((keys[7]>>2)&6)|
                 ((keys[7]>>3)&8)|((keys[8]<<3)&112);
        changes=controls&~previous_keys;
        switches^=(changes&25)<<3; /* F4 palette, F5/F8 missile guidance. */
        if (changes&4) {
            start_level=start_level==1 ? 5 : start_level==5 ? 20 : start_level==20 ? 50 : 1;
        }
        if (changes&32) audio_muted^=1;
        if ((changes&64) && !audio_muted) {
            if (!audio_next()) return 1;
            sound_status_notify();
        }
        if (changes&96) sound_status_update();
        if ((input&PAUSE) && !(previous_input&PAUSE)) paused^=1;
        G(0x282)=switches; if (controls&2) G(0x282)&=~2;
        if ((changes&4) ||
            ((input&START) && !(previous_input&START)) ||
            ((ready || MODE==255) && (input&FIRE) && !(previous_input&FIRE))) {
            G(0x282)&=~1; ready=0; paused=0;
        }
        previous_keys=controls;
        previous_input=input;
        PROFILE_PHASE(0);
        if (!paused) {
            demo_tick();
            if (ready) {
                G(0x280)=255; G(0x22c)=G(0x22d)=128;
            }
            if (MODE==255) G(0xc0)=(uint16_t)rr_Space;
            reflected=G(0xe0);
            /* RESET discards this frame's collision latches. Leave time
             * for rebuilding terrain and switching palettes together. */
            if ((G(0x282)&1) && (VAR!=2 || ready || MODE)) collisions();
            G(0xe0)=0;
            PROFILE_PHASE(1);
            old_offset=OFFSET; old_intro=MODE; old_variant=VAR;
            rr_step(); ++ticks; reflected=G(0xe0);
            if (VAR!=2 && tank_bonus && (G(0x282)&1)) rr_tank_bonus();
            if (!(G(0x282)&1) || old_variant!=VAR) {
                duo_started=duo_restart=0; memset(duo_players,0,sizeof(duo_players));
            }
            if (duo_restart) duo_restart_stage();
            if (old_variant!=VAR) {
                hud_clear(); hud_pending=1;
                xram0_poke16(XRAM_HUD_BITMAP_CONFIG+12,VAR==2 ? XRAM_DUO_HUD_P1_PALETTE : XRAM_PALETTE);
            }
            PROFILE_PHASE(2);
            if (duo_restart || !(G(0x282)&1) || (old_intro>=128 && MODE<128)) {
                duo_restart=0;
                restart_terrain(); jet_cache=0xffff;
                memset(tanks,0,sizeof(tanks));
                tank_track_phase=0;
                memset(bank_tanks,0,sizeof(bank_tanks)); scroll=0;
                memset(helicopter_shots,0,sizeof(helicopter_shots));
                memset(helicopter_types,0,sizeof(helicopter_types)); helicopter_spawn=0;
            } else {
                scroll=(OFFSET-old_offset)&31;
                if (OFFSET<old_offset && scroll<=4) {
                    memmove(tanks,tanks+1,5*sizeof(tank_t));
                    memset(tanks+5,0,sizeof(tank_t));
                    memmove(helicopter_shots,helicopter_shots+1,5*sizeof(helicopter_shot_t));
                    memset(helicopter_shots+5,0,sizeof(helicopter_shot_t));
                    memmove(helicopter_types,helicopter_types+1,5); helicopter_types[5]=0;
                }
                if (scroll>4) rebuild_terrain();
                else if (scroll) {
                    ring_top=ring_top>=scroll ? ring_top-scroll : RIVER_RING+ring_top-scroll;
                    memset(edge_valid,0,sizeof(edge_valid));
                    for (y=0;y<scroll;++y) draw_terrain_row(y);
                    /* A new block supplies the forward tangent samples
                     * missing when the last four world rows were drawn. */
                    if (OFFSET<old_offset)
                        for (y=scroll;y<scroll+4;++y) draw_terrain_row(y);
                }
            }
            move_tanks();
            bank_tanks_tick(scroll);
            helicopter_shots_tick(scroll);
        }
        PROFILE_PHASE(3);
        render();
        PROFILE_PHASE(4);
#ifdef RIVER_PROFILE
        timing_frame=(uint16_t)ria_attr_get(RIA_ATTR_CLK_RUN_MS)-timing_start;
        if (timing_frame>timings[5]) timings[5]=timing_frame;
        xram0_write(XRAM_TIMING,timings,sizeof(timings));
#endif
    }
    audio_stop();
    xreg(1,0,0,1);
    show_outro();
    xreg(0,0,0,0xffff); xreg(0,0,2,0xffff); xreg(1,0,0,0);
    return 0;
}
#pragma optimize(pop)
