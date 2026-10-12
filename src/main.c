#include <rp6502.h>
#include <string.h>
#include "xram.h"
#include "graphics.h"
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
#define HUD_GAME_NUMBER_X 28
#define HUD_GAME_NUMBER_Y 26
#define HUD_FUEL_X 44
#define HUD_FUEL_Y 17
#define HUD_FUEL_WIDTH 39
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
void __fastcall__ demo_tick(uint8_t vsyncs);
void __fastcall__ write_terrain_row(unsigned address);
void __fastcall__ write_jet_image(unsigned native_address);
void __fastcall__ write_hud_span(unsigned address);
void __fastcall__ reset_terrain(uint8_t color);
void __fastcall__ hud_glyph(unsigned glyph);
#define draw_glyph(x,bits) hud_glyph(((unsigned)(x)<<8)|(bits))
uint8_t __fastcall__ land_xy(unsigned position);
uint8_t __fastcall__ mask_land(unsigned position);
uint8_t __fastcall__ mask_player_land(unsigned position);
uint16_t __fastcall__ tia_color(uint8_t code);
#define land_at(x,y) land_xy(((unsigned)(uint8_t)(y)<<8)|(uint8_t)(x))
extern const uint8_t rr_shapePtr1aTab[], rr_shapePtr1bTab[], rr_ColorPtrTab[];
extern const uint8_t rr_ColorTab[], rr_RoadColorTab[];
extern const uint8_t rr_Space[];
uint8_t row[RIVER_WIDTH];
uint8_t hud_ink;
uint8_t hud_column, hud_length;
uint8_t reset_tiles[512];
uint8_t bank_half[20], tile_mirror[TERRAIN_TILE_COUNT];
/* One 8-pixel tile per Atari PF bit; trim seven rows to make it one line high. */
static tile_config_t terrain = {0,1,0,RIVER_TOP,TERRAIN_COLUMNS,RIVER_RING,
    XRAM_TERRAIN,XRAM_PALETTE,XRAM_TILES};
static bitmap_config_t hud_bitmap = {0,0,0,HUD_TOP,320,HUD_HEIGHT,XRAM_HUD,XRAM_PALETTE};
static const bitmap_config_t demo_footer = {1,0,0,HUD_FOOTER_Y,DEMO_FOOTER_WIDTH,8,
    XRAM_DEMO_FOOTER_IMAGE,XRAM_DEMO_FOOTER_PALETTE};
static uint16_t footer_offset;
static uint8_t shown_demo=255;
static sprite_t sprites[SPRITE_COUNT];
static sprite_t hud_sprites[HUD_SPRITE_COUNT];
static oscillator_t sound[8];
static uint8_t masks[OBJECT_IMAGE_COUNT][32], sprite_colors[OBJECT_IMAGE_COUNT][16];
static uint8_t widths[OBJECT_IMAGE_COUNT], scales[OBJECT_IMAGE_COUNT];
static uint8_t reverse_bits[256];
/* Companion of each native bridge block; it scrolls with that block. */
typedef struct {
    int16_t x;
    uint8_t status, direction, explosion;
} tank_t;
static tank_t tanks[6];
static uint8_t tank_bonus;
typedef struct {
    int16_t native_x, draw_x;
    uint8_t pattern1, pattern2, flags, flip, valid;
} mountain_position_t;
static mountain_position_t mountain_positions[6];
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
static uint8_t paused, switches=0x0b, palette_mask, palette_xor;
/* Applied by native GameInit to both players on a full game reset. */
uint8_t start_level=1;
static uint8_t state_bytes[32], old_score[12], old_fuel, palette_player;
static uint16_t ticks, skipped_frames, jet_cache=0xffff;
/* 1: startup delay, 2: scrolling attract demo, 0: user game. */
uint8_t ready=1;
uint8_t demo_wait=180;
static uint8_t hud_dirty=1, reflected;
static uint8_t fuel_rows[16][HUD_FUEL_WIDTH];
static uint8_t score_rows[12][6];
uint16_t tia_palette[128];
static uint16_t sound_frequency[3][32];
static uint8_t shown_level=255, shown_variant=255, shown_player=255;
static uint8_t shown_reserves=255, high_dirty=1;
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
    return id==BALLOON_ID ? XRAM_BALLOON_IMAGE : id==TANK_ID ? XRAM_TANK_IMAGE :
        XRAM_IMAGES+(uint16_t)id*IMAGE_BYTES;
}
static uint16_t palette_address(uint8_t id)
{
    return id==BALLOON_ID ? XRAM_BALLOON_PALETTE : id==TANK_ID ? XRAM_TANK_PALETTE :
        XRAM_SPRITE_PALETTES+(uint16_t)id*32;
}
static uint8_t terrain_row(uint8_t y)
{
    uint16_t n=(uint16_t)ring_top+y;
    if (n>=RIVER_RING) n-=RIVER_RING;
    return n;
}
static uint8_t road_color(uint8_t code)
{ return code==4 ? 4 : code==8 ? 5 : code==rr_ColorTab[1] ? 6 : 4; }
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
    if ((flags&0x80) && index<13) {
        color=road_color(rr_RoadColorTab[index]); shore_left=left; shore_right=right;
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
static void refresh_jet_palette(void)
{
    static uint16_t colors[2];
    colors[0]=0; colors[1]=PLAYER ? RGB(0,31,31) : tia_color(rr_ColorTab[1]);
    upload(XRAM_JET_PALETTE,colors,4); palette_player=PLAYER;
}
static void refresh_palettes(void)
{
    /* Like the terrain scratch space, this buffer has a single main-loop
     * owner. Avoid indirect stack indexing during a restart plus B&W change. */
    static uint16_t colors[16];
    static uint8_t id,i,count;
    colors[0]=0; colors[1]=tia_color(rr_ColorTab[4]);
    colors[2]=tia_color(0xd2); colors[3]=tia_color(0xd6);
    colors[4]=tia_color(4); colors[5]=tia_color(8); colors[6]=tia_color(rr_ColorTab[1]);
    colors[7]=RGB(0,0,0); colors[8]=tia_color(rr_ColorTab[1]); colors[9]=tia_color(0x0c);
    colors[10]=tia_color(rr_ColorTab[2]); colors[11]=tia_color(rr_ColorTab[3]);
    colors[12]=tia_color(0x20); /* Brown bank rim and mountain faces. */
    colors[13]=tia_color(0x32); colors[14]=tia_color(0x2a); colors[15]=tia_color(0xa8);
    upload(XRAM_PALETTE,colors,32);
    colors[11]=colors[7]; upload(XRAM_HUD_BLACK_PALETTE,colors,32);
    for (id=0;id<OBJECT_IMAGE_COUNT;++id) {
        colors[0]=0;
        count=id==BALLOON_ID ? sizeof(balloon_colors) : id==TANK_ID ? sizeof(tank_colors) : 16;
        for (i=1;i<count;++i) colors[i]=tia_color(sprite_colors[id][i]);
        upload(palette_address(id),colors,32);
    }
    refresh_jet_palette(); colors[0]=0;
    for (i=0;i<6;++i) {
        colors[i+1]=(G(0x86)==255 && !G(0x85)) ?
            RGB(activision_colors[i][0],activision_colors[i][1],activision_colors[i][2]) :
            tia_color(activision_color_roles[i]);
    }
    upload(XRAM_LOGO_PALETTE,colors,14);
    /* The demo caption stays light gray when the screensaver changes hues. */
    colors[2]=RGB(23,23,23); upload(XRAM_DEMO_FOOTER_PALETTE,colors,14);
    palette_mask=G(0x86); palette_xor=G(0x85);
}
static char mountain_pixel(uint8_t variant,uint8_t y,uint8_t x)
{ return y<7 || y>=28 ? '.' : mountain_pixels[variant][y-7][x]; }
static void prepare_images(void)
{
    static uint8_t id,y,j,bits,x,scale,width;
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
        scale=(id==8 || id==9) ? 4 : id==7 ? 2 : 1;
        width=8*scale; scales[id]=scale; widths[id]=width;
        for (y=0;y<32;++y) {
            j=31-y;
            /* The TIA kernel uses A on even block lines and B on odd ones.
             * Reversing these pairs breaks the negative-space FUEL lettering. */
            bits=(j<3 || j>=26) ? 0 :
                G(0xce00+(uint8_t)((j&1 ? rr_shapePtr1bTab[id] : rr_shapePtr1aTab[id])+(j>>1)));
            if (id==9) {
                bits=0;
                for (x=0;x<32;++x) if (mountain_pixel(0,y,x)!='.' ||
                    mountain_pixel(1,y,x)!='.' || mountain_pixel(2,y,x)!='.') {
                    bits|=0x80>>(x>>2);
                    if (x<mountain_min_x) mountain_min_x=x;
                    if (x>mountain_max_x) mountain_max_x=x;
                }
            }
            masks[id][y]=bits;
            if (j<26) sprite_colors[id][(j>>1)+1]=G(0xcf00+(uint8_t)(rr_ColorPtrTab[id]+(j>>1)));
            memset(row,0,width/2);
            for (x=0;x<width;++x) if (bits&(0x80>>(x/scale))) {
                uint8_t ink=(j>>1)+1;
                if (id==9) {
                    static uint8_t pixel;
                    pixel=mountain_pixel(0,y,x);
                    if (pixel=='.') continue;
                    ink=pixel=='K' ? 2 : pixel=='U' ? 3 : 1;
                }
                row[x>>1]|=(uint8_t)(ink<<((x&1) ? 0 : 4));
            }
            upload(XRAM_IMAGES+(uint16_t)id*IMAGE_BYTES+(uint16_t)y*(width/2),row,width/2);
            if (id<4) {
                memset(row,0,8);
                for (x=0;x<8;++x) if (bits&(0x80>>x)) row[x]=((j>>1)+1)*17;
                upload(EXTRA_IMAGES+(uint16_t)id*256+y*8,row,8);
            }
        }
        if (id==9) {sprite_colors[id][1]=0x20; sprite_colors[id][2]=0; sprite_colors[id][3]=0x84;}
    }
    for (id=1;id<3;++id) for (y=0;y<32;++y) {
        memset(row,0,16);
        for (x=0;x<32;++x) {
            static uint8_t pixel;
            pixel=mountain_pixel(id,y,x);
            if (pixel!='.') row[x>>1]|=(pixel=='K' ? 2 : pixel=='U' ? 3 : 1)<<((x&1) ? 0 : 4);
        }
        upload((id==1 ? XRAM_SMALL_MOUNTAIN : XRAM_MEDIUM_MOUNTAIN)+(uint16_t)y*16,row,16);
    }
    for (id=BALLOON_ID;id<=TANK_ID;++id) {
        widths[id]=8; scales[id]=1;
        memcpy(sprite_colors[id],id==BALLOON_ID ? balloon_colors : tank_colors,
            id==BALLOON_ID ? sizeof(balloon_colors) : sizeof(tank_colors));
        for (y=0;y<32;++y) {
            memset(row,0,4); bits=0;
            for (x=0;x<8;++x) {
                uint8_t pixel=id==BALLOON_ID ? balloon_pixels[y][x] : tank_pixels[y][x];
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
    for (y=0;y<8;++y) xram0_poke8(BULLET_IMAGE+y*2,0x80);
}
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
    /* CalcPosX encodes the bridge at 63; its widened TIA sprite starts at
     * 64, covering the river [64,96). Use that origin for drawing and hits. */
    if (ID(n)==9) return fit_mountain(n,x);
    return x+(ID(n)==8);
}
static uint8_t mountain_variant(uint8_t n)
{ return (G(0xa6+n)^(G(0xac+n)>>3)^G(0x94+n))%3; }
static uint8_t opaque(uint8_t id,uint8_t x,uint8_t y,uint8_t flip,uint8_t block)
{
    if (x>=widths[id] || y>=32) return 0;
    if (id==9) return mountain_pixel(mountain_variant(block),y,flip ? 31-x : x)!='.';
    if (scales[id]==2) x>>=1; else if (scales[id]==4) x>>=2;
    if (flip) x=7-x;
    return masks[id][y]&(0x80>>x);
}
static void sync_tanks(void)
{
    uint8_t n,seed;
    for (n=0;n<6;++n) {
        if (ID(n)!=8) {
            if (tanks[n].status) {tanks[n].status=0; tanks[n].explosion=0;}
            continue;
        }
        if (tanks[n].status) continue;
        seed=G(0xa6+n)^G(0xac+n)^G(0xbd);
        tanks[n].direction=seed&1;
        tanks[n].x=tanks[n].direction ? 112 : 40;
        tanks[n].status=1;
    }
}
static void move_tanks(void)
{
    uint8_t n;
    sync_tanks();
    if (MODE) return;
    for (n=0;n<6;++n) {
        if (tanks[n].explosion) --tanks[n].explosion;
        if (tanks[n].status!=1 || (FRAME&1)) continue;
        tanks[n].x+=tanks[n].direction ? -1 : 1;
        if (tanks[n].x<=24) tanks[n].direction=0;
        if (tanks[n].x>=128) tanks[n].direction=1;
    }
}
static uint8_t tank_on_bridge(uint8_t n)
{
    int16_t center=tanks[n].x+4,bridge=object_x(n);
    return tanks[n].status==1 && center>=bridge && center<bridge+32;
}
static void destroy_tank(uint8_t n)
{
    tanks[n].status=2; tanks[n].explosion=12; tank_bonus=1;
}
static void collisions(void)
{
    static uint8_t n,y,x,bits,id,scale,flip,px,jbits;
    static int16_t ox,oy,sy,dy,dx,by;
    px=PX+(reflected!=0); by=153-(int16_t)MY;
    G(0xe2)=G(0xe4)=G(0xe6)=G(0xe8)=255; tank_bonus=0;
    for (n=6;n>0;) {
        --n; /* The TIA kernel visits upper blocks before lower blocks. */
        id=ID(n); if (id>BALLOON_ID) continue;
        ox=object_x(n); oy=128+OFFSET-(int16_t)n*32;
        if (!ready && !MODE && id==8 && tanks[n].status==1) {
            static int16_t tx;
            static uint8_t tf;
            tx=tanks[n].x; tf=tanks[n].direction;
            if (MY<=161 && MX>=tx && MX<tx+8) {
                for (y=0;y<8;++y) {
                    dy=by+y-oy;
                    if (dy>=0 && dy<32 && opaque(TANK_ID,MX-tx,dy,tf,0)) {
                        if (tank_on_bridge(n)) G(0xe2)=n;
                        else MY=180;
                        destroy_tank(n); break;
                    }
                }
            }
            if (tanks[n].status==1 && tx+8>px && tx<px+8 && oy<=159 && oy+32>142) {
                for (y=0;y<18;++y) {
                    dy=142+y-oy; if (dy<0 || dy>=32) continue;
                    jbits=G(JET_ADDRESS+18-y);
                    for (x=0;x<8;++x) if (jbits&(reflected ? (1<<x) : (0x80>>x))) {
                        dx=px+x-tx;
                        if (dx>=0 && dx<8 && opaque(TANK_ID,dx,dy,tf,0)) {
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
        if (ox+widths[id]<=px || ox>=px+8 || oy>159 || oy+32<=142) continue;
        for (y=0;y<18;++y) {
            dy=142+y-oy; if (dy<0 || dy>=32) continue;
            jbits=G(JET_ADDRESS+18-y);
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
        if (mask_player_land(((unsigned)(142+y)<<8)|px)) {
            G(0xe4)=0; goto jet_checked;
        }
    }
jet_checked:
    if (MY<=161) for (y=0;y<8;++y) {
        sy=by+y;
        if (sy>=0 && sy<160 && land_at(MX,sy)) {G(0xe6)=0; break;}
    }
}
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
            inputs[n]|=(pad[0]|pad[1])&15;
            if (pad[2]&0x1b) inputs[n]|=FIRE;
            if (pad[3]&8) inputs[n]|=PAUSE;
            if (pad[3]&4) inputs[n]|=START;
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
/* Pack the first eight readable pixels into the MSB-first glyph format. */
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
static void hud_details(void)
{
    static uint8_t level,reserves,i,dirty,demo;
    level=G(0xbd); reserves=G(0xc0)<80 ? G(0xc0)/8 : 0; dirty=high_dirty;
    demo=ready || MODE==255;
    if (shown_demo!=demo) {
        hud_sprites[18].y=demo ? -256 : HUD_FOOTER_Y;
        xram0_poke16(XRAM_DEMO_FOOTER_CONFIG+4,demo ? HUD_FOOTER_Y : -256);
        footer_offset=0; xram0_poke16(XRAM_DEMO_FOOTER_CONFIG+2,0);
        shown_demo=demo; dirty=1;
    }
    if (demo && ready!=1 && !paused) {
        if (++footer_offset==DEMO_FOOTER_WIDTH) footer_offset=0;
        xram0_poke16(XRAM_DEMO_FOOTER_CONFIG+2,-footer_offset);
    }
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
        hud_label(HUD_PLAYER_X,6,PLAYER ? "P2" : "P1",0xbb); shown_player=PLAYER;
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
        for (y=0;y<16;++y) {
            memcpy(row+HUD_FUEL_X,fuel_rows[y],HUD_FUEL_WIDTH);
            if (y>=5 && y<15) row[HUD_FUEL_X+4+fy]=row[HUD_FUEL_X+5+fy]=0xbb;
            write_hud_span(XRAM_HUD+(uint16_t)(HUD_FUEL_Y+y)*RIVER_WIDTH+HUD_FUEL_X);
        }
    }
    memcpy(old_score,(void*)0xcd,12); old_fuel=fy; hud_dirty=0;
}
static void render(void)
{
    static uint8_t n,id;
    static uint16_t c;
    if (paused) sync_tanks();
    for (n=0;n<SPRITE_COUNT;++n) sprites[n].y=-256;
    jet_image();
    sprites[0].x=(PX+(reflected!=0))*2; sprites[0].y=RIVER_TOP+142;
    sprites[0].image=JET_IMAGE; sprites[0].palette=XRAM_JET_PALETTE;
    sprites[0].size=0x41; sprites[0].options=0x42|(reflected ? 0x10 : 0);
    if (ready) sprites[0].y=-256;
    if (!ready && MY<=161) {
        sprites[1].x=MX*2; sprites[1].y=RIVER_TOP+153-(int16_t)MY;
        sprites[1].image=BULLET_IMAGE; sprites[1].palette=XRAM_PALETTE;
        sprites[1].size=0x10; sprites[1].options=0x42;
    }
    for (n=0;n<6;++n) {
        id=ID(n); if (id>BALLOON_ID) continue;
        sprites[n+2].x=object_x(n)*2; sprites[n+2].y=RIVER_TOP+128+OFFSET-(int16_t)n*32;
        sprites[n+2].image=image_address(id);
        if (id==9) sprites[n+2].image=mountain_variant(n)==0 ? XRAM_IMAGES+9*IMAGE_BYTES :
            mountain_variant(n)==1 ? XRAM_SMALL_MOUNTAIN : XRAM_MEDIUM_MOUNTAIN;
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
        if (id==8 && (tanks[n].status==1 || tanks[n].explosion)) {
            uint8_t ti=tanks[n].status==1 ? TANK_ID : 1;
            sprites[n+10].x=tanks[n].x*2; sprites[n+10].y=sprites[n+2].y;
            sprites[n+10].image=image_address(ti);
            sprites[n+10].palette=palette_address(ti);
            sprites[n+10].size=0x71;
            sprites[n+10].options=0x42|(tanks[n].direction ? 0x10 : 0);
        }
    }
    terrain.y_pos_px=RIVER_TOP-ring_top;
    upload(XRAM_TERRAIN_CONFIG,&terrain,sizeof(terrain)); upload(XRAM_SPRITES,sprites,sizeof(sprites));
    if (palette_mask!=G(0x86) || palette_xor!=G(0x85)) refresh_palettes();
    /* The player switch changes only the jet, not every world palette. */
    else if (palette_player!=PLAYER) refresh_jet_palette();
    if (G(0x8d)) {
        c=tia_color((G(0x8d)&1) ? 0x42 : rr_ColorTab[4]);
        if (!paused) --G(0x8d);
        xram0_poke16(XRAM_PALETTE+2,c);
    } else xram0_poke16(XRAM_PALETTE+2,tia_color(rr_ColorTab[4]));
    for (n=0;n<2;++n) {
        static uint8_t ctrl,volume;
        ctrl=G(0x215+n)&15; volume=G(0x219+n)&15;
        sound[n].freq=sound_frequency[ctrl==4 ? 1 : ctrl==12 ? 2 : 0][G(0x217+n)&31];
        sound[n].duty=128;
        sound[n].attack=sound[n].decay=(15-volume)<<4;
        sound[n].release_wave=(ctrl==8 || ctrl<4) ? 0x40 : 0x10;
        sound[n].pan_gate=volume && !paused;
    }
    upload(XRAM_PSG,sound,16);
    state_bytes[0]=0x52; state_bytes[1]=3;
    state_bytes[2]=ready || MODE==255 ? 3 : MODE==0 ? 1 : MODE>=128 ? 2 : 0;
    state_bytes[3]=PX; state_bytes[4]=G(0xc0)<80 ? G(0xc0)/8 : 0;
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
    if (memcmp(old_score,(void*)0xcd,12)) {hud_dirty|=1; update_high_score();}
    if (old_fuel!=(G(0xb7)>>3)) hud_dirty|=2;
    if (hud_dirty) draw_hud();
    hud_details();
}
static uint8_t configure_video(void)
{
    static uint8_t y,i,x,bits;
    static uint16_t hz;
    if (xreg(1,0,0,1)<0) return 0;
    for (i=0;i<32;++i) {
        hz=31400u/(i+1u);
        sound_frequency[0][i]=(hz>21845u ? 21845u : hz)*3;
        sound_frequency[1][i]=(hz>>1)*3;
        sound_frequency[2][i]=(hz/6)*3;
    }
    for (i=0;i<8;++i) tile_mirror[i]=i;
    for (i=0;i<7;++i) xram0_set(XRAM_TILES+(uint16_t)i*32,i*17,32);
    for (i=8;i<TERRAIN_TILE_COUNT;++i) {
        uint8_t variant=(i-8)%18,land=2+(i-8)/18,pattern=variant%9;
        tile_mirror[i]=variant<9 ? i+9 : i-9;
        for (x=0;x<8;++x) {
            uint8_t pixel=bank_pixels[pattern][variant<9 ? x>>1 : 3-(x>>1)];
            uint8_t color=pixel=='B' ? 12 : pixel=='W' ? 1 : land;
            if (x&1) row[x>>1]|=color; else row[x>>1]=color<<4;
        }
        for (y=0;y<8;++y) upload(XRAM_TILES+(uint16_t)i*32+y*4,row,4);
    }
    xram0_set(XRAM_TILES+TERRAIN_BANK_SOLID*32,0xcc,32);
    for (i=0;i<128;++i) tia_palette[i]=tia_rgb(i*2);
    prepare_images(); refresh_palettes();
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
        memset(row,0,30);
        for (x=0;x<60;++x) {
            uint8_t pixel=activision_logo[y][x];
            if (pixel!='.') row[x>>1]|=(pixel-'A'+1)<<((x&1) ? 0 : 4);
        }
        upload(XRAM_LOGO_IMAGE+y*30,row,30);
    }
    for (i=0;i<HUD_SPRITE_COUNT;++i) {
        hud_sprites[i].y=-256; hud_sprites[i].palette=XRAM_PALETTE;
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
    /* Preserve the logo bitmap while positioning it in the reference layout. */
    hud_sprites[18].x=48; hud_sprites[18].y=HUD_FOOTER_Y;
    hud_sprites[18].image=XRAM_LOGO_IMAGE; hud_sprites[18].palette=XRAM_LOGO_PALETTE;
    hud_sprites[18].size=0x1e;
    for (y=0;y<16;++y) for (x=0;x<HUD_FUEL_WIDTH;++x)
        fuel_rows[y][x]=fuel_gauge[y][x]=='X' ? 0x77 : 0xaa;
    hud_dirty=7;
    upload(XRAM_HUD_BITMAP_CONFIG,&hud_bitmap,sizeof(hud_bitmap)); xram0_set(XRAM_HUD,0xaa,HUD_BYTES);
    upload(XRAM_DEMO_FOOTER_CONFIG,&demo_footer,sizeof(demo_footer));
    xram0_set(XRAM_HUD+HUD_PANEL_HEIGHT*RIVER_WIDTH,0x77,(HUD_HEIGHT-HUD_PANEL_HEIGHT)*RIVER_WIDTH);
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
    /* The expanded assets can span a VSYNC during startup. Publish valid
     * tile dimensions before enabling the plane, even with zero-filled XRAM. */
    upload(XRAM_TERRAIN_CONFIG,&terrain,sizeof(terrain));
    if (xreg(1,0,1,2,0x702,XRAM_TERRAIN_CONFIG,0,RIVER_TOP,RIVER_TOP+RIVER_HEIGHT)<0 ||
        /* Keep the player on the front plane, above all world sprites. */
        xreg(1,0,1,5,0x38,XRAM_SPRITES+sizeof(sprite_t),SPRITE_COUNT-1,1,RIVER_TOP,RIVER_TOP+RIVER_HEIGHT)<0 ||
        xreg(1,0,1,5,0x38,XRAM_SPRITES,1,2,RIVER_TOP,RIVER_TOP+RIVER_HEIGHT)<0 ||
        xreg(1,0,1,5,0x38,XRAM_HUD_SPRITES,HUD_SPRITE_COUNT,1,HUD_TOP,HUD_TOP+HUD_HEIGHT)<0 ||
        xreg(1,0,1,3,2,XRAM_HUD_BITMAP_CONFIG,0,HUD_TOP,HUD_TOP+HUD_HEIGHT)<0 ||
        xreg(1,0,1,3,2,XRAM_DEMO_FOOTER_CONFIG,1,HUD_FOOTER_Y,HUD_FOOTER_Y+8)<0 ||
        xreg(0,0,0,XRAM_KEYBOARD)<0 || xreg(0,0,2,XRAM_GAMEPADS)<0 ||
        xreg(0,1,0,XRAM_PSG)<0) return 0;
    return 1;
}
int main(void)
{
    uint8_t last_vsync,now,delta,input,controls,old_offset,old_intro,scroll,y;
    RIA.step0=1; RIA.step1=1;
    memset((void*)0x200,0,256); G(0x282)=switches; rr_init(); G(0x86)=255;
    /* Prepare the original title scene before showing it, so the river is
     * stationary throughout the startup delay. No joystick is held. */
    G(0x280)=255; G(0x22c)=G(0x22d)=128;
    while (MODE!=255) rr_step();
    xram0_set(XRAM_PSG,0,64);
    if (!configure_video()) return 1;
    rebuild_terrain(); render(); last_vsync=RIA.vsync;
    for (;;) {
        do {now=RIA.vsync;} while (now==last_vsync);
        delta=now-last_vsync; if (delta>1) skipped_frames+=delta-1;
        last_vsync=now;
#ifdef RIVER_PROFILE
        timing_start=timing_stamp=(uint16_t)ria_attr_get(RIA_ATTR_CLK_RUN_MS);
#endif
        input=read_input(); if (input&QUIT) break;
        controls=(pressed(0x3a) ? 1 : 0)|(pressed(0x3b) ? 2 : 0)|
                 (pressed(0x3c) ? 4 : 0)|(pressed(0x3d) ? 8 : 0)|
                 (pressed(0x3e) ? 16 : 0);
        if ((controls&1) && !(previous_keys&1)) switches^=8;
        if ((controls&4) && !(previous_keys&4)) {
            start_level=start_level==1 ? 5 : start_level==5 ? 20 : start_level==20 ? 50 : 1;
        }
        if ((controls&16) && !(previous_keys&16)) switches^=64;
        if ((controls&8) && !(previous_keys&8)) switches^=128;
        if ((input&PAUSE) && !(previous_input&PAUSE)) paused^=1;
        G(0x282)=switches; if (controls&2) G(0x282)&=~2;
        if (((controls&4) && !(previous_keys&4)) ||
            ((input&START) && !(previous_input&START)) ||
            ((ready || MODE==255) && (input&FIRE) && !(previous_input&FIRE))) {
            G(0x282)&=~1; ready=0; paused=0;
        }
        previous_keys=controls;
        previous_input=input;
        PROFILE_PHASE(0);
        if (!paused) {
            demo_tick(delta);
            if (ready) {
                G(0x280)=255; G(0x22c)=G(0x22d)=128;
            }
            if (MODE==255) G(0xc0)=(uint16_t)rr_Space;
            reflected=G(0xe0); collisions(); G(0xe0)=0;
            PROFILE_PHASE(1);
            old_offset=OFFSET; old_intro=MODE; rr_step(); ++ticks; reflected=G(0xe0);
            if (tank_bonus && (G(0x282)&1)) rr_tank_bonus();
            PROFILE_PHASE(2);
            if (!(G(0x282)&1) || (old_intro>=128 && MODE<128)) {
                restart_terrain(); jet_cache=0xffff;
                memset(tanks,0,sizeof(tanks));
            } else {
                scroll=(OFFSET-old_offset)&31;
                if (OFFSET<old_offset && scroll<=4) {
                    memmove(tanks,tanks+1,5*sizeof(tank_t));
                    memset(tanks+5,0,sizeof(tank_t));
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
    xram0_set(XRAM_PSG,0,64);
    xreg(0,0,0,0xffff); xreg(0,0,2,0xffff); xreg(0,1,0,0xffff); xreg(1,0,0,0);
    return 0;
}
