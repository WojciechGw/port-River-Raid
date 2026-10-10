#include <rp6502.h>
#include <string.h>
#include "xram.h"

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
enum { UP=1, DOWN=2, LEFT=4, RIGHT=8, FIRE=16, START=32, PAUSE=64, QUIT=128 };
void rr_init(void);
void rr_step(void);
void __fastcall__ write_row(unsigned address);
uint8_t __fastcall__ land_xy(unsigned position);
uint8_t __fastcall__ mask_land(unsigned position);
#define land_at(x,y) land_xy(((unsigned)(uint8_t)(y)<<8)|(uint8_t)(x))
extern const uint8_t rr_shapePtr1aTab[], rr_shapePtr1bTab[], rr_ColorPtrTab[];
extern const uint8_t rr_ColorTab[], rr_RoadColorTab[];
extern const uint8_t rr_FuelTab0[], rr_FuelTab1[], rr_FuelTab2[], rr_FuelTab3[], rr_FuelTab4[];
extern const uint8_t rr_ENABLTab[], rr_Copyright1[], rr_Copyright2[], rr_Copyright3[];
extern const uint8_t rr_Copyright4[], rr_Copyright5[], rr_Space[];
uint8_t row[RIVER_WIDTH];
static bitmap_config_t bitmap = {0,1,0,8,320,RIVER_RING,XRAM_BITMAP,XRAM_PALETTE};
static bitmap_config_t hud_bitmap = {0,0,0,176,320,64,XRAM_HUD,XRAM_PALETTE};
static sprite_t sprites[SPRITE_COUNT];
static oscillator_t sound[8];
static uint8_t masks[11][32], sprite_colors[11][16], widths[11], scales[11];
static uint8_t reverse_bits[256];
uint8_t collision_mask, collision_scale;
uint8_t river1[RIVER_RING], river2[RIVER_RING], ring_top;
static uint8_t keys[32], pads[40], inputs[2], previous_input, previous_keys;
static uint8_t paused, switches=0x0b, palette_mask, palette_xor;
static uint8_t state_bytes[32], old_score[12], old_lives, old_fuel, old_mode, old_player;
static uint16_t ticks, skipped_frames, jet_cache=0xffff;
static uint8_t hud_dirty=1, ready=1, reflected;
static uint8_t fuel_rows[15][160];
static uint16_t tia_palette[128];
static uint8_t shown_copyright;
#define RGB(r,g,b) ((uint16_t)(((uint16_t)(b)<<11)|((g)<<6)|(r)|32))
/* TIA hue anchors. NTSC codes/luminances come from the original tables;
 * the RGB mapping is an approximation of analog television colors. */
static const uint8_t hues[16][3] = {
    {31,31,31},{29,26,4},{31,18,3},{31,11,5},{29,6,12},{23,6,23},
    {13,6,29},{7,9,31},{4,14,31},{3,21,29},{3,26,24},{5,27,14},
    {8,26,5},{18,25,4},{25,23,4},{29,20,4}
};
static uint16_t tia_rgb(uint8_t code)
{
    static const uint8_t luminance[8]={0,9,13,17,21,24,26,29};
    uint8_t h,l,r,g,b;
    h=code>>4; l=code&14;
    if (!h) return RGB(luminance[l>>1],luminance[l>>1],luminance[l>>1]);
    r=hues[h][0]*(l+8)/20; g=hues[h][1]*(l+8)/20; b=hues[h][2]*(l+8)/20;
    if (r>31) r=31; if (g>31) g=31; if (b>31) b=31;
    return RGB(r,g,b);
}
static uint16_t tia_color(uint8_t code)
{ return tia_palette[((code^G(0x85))&G(0x86))>>1]; }
static void upload(uint16_t address,const void* data,uint16_t count)
{ xram0_write(address,data,count); }
static uint8_t terrain_row(uint8_t y)
{
    uint16_t n=(uint16_t)ring_top+y;
    if (n>=RIVER_RING) n-=RIVER_RING;
    return n;
}
static uint8_t road_color(uint8_t code)
{ return code==4 ? 4 : code==8 ? 5 : code==rr_ColorTab[1] ? 6 : 4; }
static void draw_terrain_row(uint8_t y)
{
    uint8_t n=terrain_row(y),distance=159-y+OFFSET,block=distance>>5;
    uint8_t index=(distance&31)>>1,flags=FLAGS(block),p1,p2,color,x;
    p1=G((uint16_t)(0xcc00|((flags&1)<<8))+G(0xa6+block)+index);
    p2=G((uint16_t)(0xcc00|((flags&2)<<7))+G(0xac+block)+index);
    river1[n]=p1; river2[n]=p2;
    color=(flags&4) ? 3 : 2;
    if ((flags&0x80) && index<13) color=road_color(rr_RoadColorTab[index]);
    memset(row,color*17,16);
    for (x=0;x<8;++x) {
        memset(row+16+x*4,(p1&(0x80>>x)) ? color*17 : 0x11,4);
        memset(row+48+x*4,(p2&(1<<x)) ? color*17 : 0x11,4);
    }
    for (x=0;x<80;++x) row[159-x]=row[x];
    write_row(XRAM_BITMAP+(uint16_t)n*160);
}
static void rebuild_terrain(void)
{
    uint8_t y;
    ring_top=0;
    for (y=0;y<160;++y) draw_terrain_row(y);
}
static void refresh_palettes(void)
{
    uint16_t colors[16];
    uint8_t id,i;
    colors[0]=0; colors[1]=tia_color(rr_ColorTab[4]);
    colors[2]=tia_color(0xd2); colors[3]=tia_color(0xd6);
    colors[4]=tia_color(4); colors[5]=tia_color(8); colors[6]=tia_color(rr_ColorTab[1]);
    colors[7]=RGB(0,0,0); colors[8]=PLAYER ? colors[7] : tia_color(rr_ColorTab[1]); colors[9]=colors[8];
    colors[10]=tia_color(rr_ColorTab[2]); colors[11]=tia_color(rr_ColorTab[3]);
    colors[12]=tia_color(0x46); colors[13]=colors[14]=colors[15]=colors[7];
    upload(XRAM_PALETTE,colors,32);
    for (id=0;id<11;++id) {
        colors[0]=0;
        for (i=1;i<16;++i) colors[i]=tia_color(sprite_colors[id][i]);
        upload(XRAM_SPRITE_PALETTES+(uint16_t)id*32,colors,32);
    }
    colors[0]=0; colors[1]=PLAYER ? RGB(0,0,0) : tia_color(rr_ColorTab[1]);
    upload(XRAM_JET_PALETTE,colors,4);
    palette_mask=G(0x86); palette_xor=G(0x85);
}
static void prepare_images(void)
{
    uint8_t id,y,j,bits,x,scale,width;
    uint16_t v;
    for (v=0;v<256;++v) {
        bits=v; j=0;
        for (x=0;x<8;++x) {j=(j<<1)|(bits&1); bits>>=1;}
        reverse_bits[v]=j;
    }
    for (id=0;id<11;++id) {
        scale=id==8 ? 4 : (id==7 || id==9) ? 2 : 1;
        width=8*scale; scales[id]=scale; widths[id]=width;
        for (y=0;y<32;++y) {
            j=31-y;
            bits=(j<3 || j>=26) ? 0 :
                G(0xce00+(uint8_t)((j&1 ? rr_shapePtr1aTab[id] : rr_shapePtr1bTab[id])+(j>>1)));
            masks[id][y]=bits;
            if (j<26) sprite_colors[id][(j>>1)+1]=G(0xcf00+(uint8_t)(rr_ColorPtrTab[id]+(j>>1)));
            memset(row,0,width/2);
            for (x=0;x<width;++x) if (bits&(0x80>>(x/scale)))
                row[x>>1]|=(uint8_t)(((j>>1)+1)<<((x&1) ? 0 : 4));
            upload(XRAM_IMAGES+(uint16_t)id*IMAGE_BYTES+(uint16_t)y*(width/2),row,width/2);
            if (id<4) {
                memset(row,0,8);
                for (x=0;x<8;++x) if (bits&(0x80>>x)) row[x]=((j>>1)+1)*17;
                upload(EXTRA_IMAGES+(uint16_t)id*256+y*8,row,8);
            }
        }
    }
    xram0_set(BULLET_IMAGE,0,16);
    for (y=0;y<8;++y) xram0_poke8(BULLET_IMAGE+y*2,0x80);
}
static void jet_image(void)
{
    uint8_t y,x,bits;
    if (JET_ADDRESS==jet_cache) return;
    jet_cache=JET_ADDRESS;
    for (y=0;y<20;++y) {
        bits=y<18 ? G(JET_ADDRESS+18-y) : 0;
        memset(row,0,4);
        for (x=0;x<8;++x) if (bits&(0x80>>x)) row[x>>1]|=(x&1) ? 1 : 16;
        upload(JET_IMAGE+y*4,row,4);
    }
}
static int16_t object_x(uint8_t n)
{ return (int16_t)G(0x94+n)*15+((OBJSTATE(n)>>4)^7)-1; }
static uint8_t opaque(uint8_t id,uint8_t x,uint8_t y,uint8_t flip)
{
    if (x>=widths[id] || y>=32) return 0;
    if (scales[id]==2) x>>=1; else if (scales[id]==4) x>>=2;
    if (flip) x=7-x;
    return masks[id][y]&(0x80>>x);
}
static void collisions(void)
{
    uint8_t n,y,x,bits,id,scale,flip,px=PX+(reflected!=0),jbits;
    int16_t ox,oy,sy,dy,dx,by=153-(int16_t)MY;
    G(0xe2)=G(0xe4)=G(0xe6)=G(0xe8)=255;
    for (n=6;n>0;) {
        --n; /* The TIA kernel visits upper blocks before lower blocks. */
        id=ID(n); if (id>10) continue;
        ox=object_x(n); oy=128+OFFSET-(int16_t)n*32;
        flip=(OBJSTATE(n)&8)!=0; scale=scales[id]; FLAGS(n)&=~32;
        if (!MODE && G(0xbd)>=2 && id>=5 && id<=7 && (FLAGS(n)&0x40)) {
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
        if (MODE) continue;
        if (MY<=161 && MX>=ox && MX<ox+widths[id]) {
            for (y=0;y<8;++y) {
                dy=by+y-oy;
                if (dy>=0 && dy<32 && opaque(id,MX-ox,dy,flip)) {G(0xe2)=n; break;}
            }
        }
        if (ox+widths[id]<=px || ox>=px+8 || oy>159 || oy+32<=142) continue;
        for (y=0;y<18;++y) {
            dy=142+y-oy; if (dy<0 || dy>=32) continue;
            jbits=G(JET_ADDRESS+18-y);
            for (x=0;x<8;++x) if (jbits&(reflected ? (1<<x) : (0x80>>x))) {
                dx=px+x-ox;
                if (dx>=0 && dx<widths[id] && opaque(id,dx,dy,flip)) {G(0xe8)=n; goto player_checked;}
            }
        }
player_checked:;
    }
    if (MODE) return;
    collision_scale=1;
    for (y=0;y<18;++y) {
        bits=G(JET_ADDRESS+18-y);
        if (!bits) continue;
        collision_mask=reflected ? reverse_bits[bits] : bits;
        if (mask_land(((unsigned)(142+y)<<8)|px)) {
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
    uint8_t n,v;
    uint8_t* pad;
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
static void hud_glyph(uint8_t xpos,uint8_t bits,uint8_t color)
{
    uint8_t x;
    for (x=0;x<8;++x) if (bits&(0x80>>x)) row[xpos+x]=color*17;
}
static uint8_t copyright_offset(void)
{
    uint8_t n=FRAME>>3;
    if (MODE!=255 || n<12) return 7;
    if (n>=20) return 15;
    return n-4;
}
static void draw_hud(void)
{
    uint8_t y,i,bits,fy=G(0xb7)>>3,copyright_line;
    for (y=0;y<42;++y) {
        if (y>=8 && y<14) continue;
        if (y>=29 && y<34) continue;
        if (y<8 && !(hud_dirty&1)) continue;
        if (y>=14 && y<29 && !(hud_dirty&2)) continue;
        if (y>=34 && !(hud_dirty&4)) continue;
        memset(row,0xaa,160);
        if (y<8) for (i=0;i<6;++i) {
            bits=G(*(uint16_t*)(0xcd+i*2)+7-y); hud_glyph(56+i*8,bits,8);
        }
        if (y>=14 && y<29) {
            memcpy(row,fuel_rows[y-14],160);
            if (rr_ENABLTab[28-y]&2) row[69+fy]=row[70+fy]=0xbb;
        }
        if (y>=34 && y<42) {
            copyright_line=copyright_offset()-(y-34);
            hud_glyph(56,G(*(uint16_t*)0xc0+copyright_line),PLAYER ? 7 : 8);
            hud_glyph(64,rr_Copyright1[copyright_line],8);
            hud_glyph(72,rr_Copyright2[copyright_line],8);
            hud_glyph(80,rr_Copyright3[copyright_line],8);
            hud_glyph(88,rr_Copyright4[copyright_line],8);
            hud_glyph(96,rr_Copyright5[copyright_line],8);
        }
        write_row(XRAM_HUD+(uint16_t)y*160);
    }
    memcpy(old_score,(void*)0xcd,12); old_lives=G(0xc0);
    old_fuel=fy; old_mode=MODE; old_player=PLAYER; hud_dirty=0;
    shown_copyright=copyright_offset();
}
static void render(void)
{
    uint8_t n,id;
    uint16_t c;
    for (n=0;n<SPRITE_COUNT;++n) sprites[n].y=-256;
    jet_image();
    sprites[0].x=(PX+(reflected!=0))*2; sprites[0].y=150;
    sprites[0].image=JET_IMAGE; sprites[0].palette=XRAM_JET_PALETTE;
    sprites[0].size=0x41; sprites[0].options=0x42|(reflected ? 0x10 : 0);
    if (MY<=161) {
        sprites[1].x=MX*2; sprites[1].y=161-(int16_t)MY;
        sprites[1].image=BULLET_IMAGE; sprites[1].palette=XRAM_PALETTE;
        sprites[1].size=0x10; sprites[1].options=0x42;
    }
    for (n=0;n<6;++n) {
        id=ID(n); if (id>10) continue;
        sprites[n+2].x=object_x(n)*2; sprites[n+2].y=136+OFFSET-(int16_t)n*32;
        sprites[n+2].image=XRAM_IMAGES+(uint16_t)id*IMAGE_BYTES;
        sprites[n+2].palette=XRAM_SPRITE_PALETTES+(uint16_t)id*32;
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
    }
    bitmap.y_pos_px=8-ring_top;
    upload(XRAM_BITMAP_CONFIG,&bitmap,sizeof(bitmap)); upload(XRAM_SPRITES,sprites,sizeof(sprites));
    if (palette_mask!=G(0x86) || palette_xor!=G(0x85) || old_player!=PLAYER) refresh_palettes();
    if (G(0x8d)) {
        c=tia_color((G(0x8d)&1) ? 0x42 : rr_ColorTab[4]);
        if (!paused) --G(0x8d);
        xram0_poke16(XRAM_PALETTE+2,c);
    } else xram0_poke16(XRAM_PALETTE+2,tia_color(rr_ColorTab[4]));
    for (n=0;n<2;++n) {
        uint8_t ctrl=G(0x215+n)&15,volume=G(0x219+n)&15;
        uint16_t hz=31400u/(G(0x217+n)+1u);
        if (ctrl==4) hz>>=1;
        if (ctrl==12) hz/=6;
        if (hz>21845u) hz=21845u; /* PSG stores Hz*3 in a 16-bit word. */
        sound[n].freq=hz*3; sound[n].duty=128;
        sound[n].attack=sound[n].decay=(15-volume)<<4;
        sound[n].release_wave=(ctrl==8 || ctrl<4) ? 0x40 : 0x10;
        sound[n].pan_gate=volume && !paused;
    }
    upload(XRAM_PSG,sound,16);
    state_bytes[0]=0x52; state_bytes[1]=2;
    state_bytes[2]=MODE==0 ? 1 : MODE==255 ? 3 : MODE>=128 ? 2 : 0;
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
    if (memcmp(old_score,(void*)0xcd,12)) hud_dirty|=1;
    if (old_fuel!=(G(0xb7)>>3)) hud_dirty|=2;
    if (old_lives!=G(0xc0) || (old_mode==255)!=(MODE==255) || old_player!=PLAYER ||
        shown_copyright!=copyright_offset()) hud_dirty|=4;
    if (hud_dirty) draw_hud();
}
static uint8_t configure_video(void)
{
    uint8_t y,i;
    const uint8_t* fuel_tables[5];
    fuel_tables[0]=rr_FuelTab0; fuel_tables[1]=rr_FuelTab1; fuel_tables[2]=rr_FuelTab2;
    fuel_tables[3]=rr_FuelTab3; fuel_tables[4]=rr_FuelTab4;
    if (xreg(1,0,0,1)<0) return 0;
    for (i=0;i<128;++i) tia_palette[i]=tia_rgb(i*2);
    prepare_images(); refresh_palettes();
    for (y=0;y<15;++y) {
        memset(row,0xaa,160);
        for (i=0;i<5;++i) hud_glyph(64+i*8,fuel_tables[i][14-y],8);
        memcpy(fuel_rows[y],row,160);
    }
    hud_dirty=7;
    upload(XRAM_HUD_BITMAP_CONFIG,&hud_bitmap,sizeof(hud_bitmap)); xram0_set(XRAM_HUD,0xaa,HUD_BYTES);
    if (xreg(1,0,1,3,2,XRAM_BITMAP_CONFIG,0,8,168)<0 ||
        xreg(1,0,1,5,0x38,XRAM_SPRITES,SPRITE_COUNT,1,8,168)<0 ||
        xreg(1,0,1,3,2,XRAM_HUD_BITMAP_CONFIG,0,176,240)<0 ||
        xreg(0,0,0,XRAM_KEYBOARD)<0 || xreg(0,0,2,XRAM_GAMEPADS)<0 ||
        xreg(0,1,0,XRAM_PSG)<0) return 0;
    return 1;
}
int main(void)
{
    uint8_t last_vsync,now,delta,input,controls,old_offset,old_intro,scroll,y,setup;
    RIA.step0=1; RIA.step1=1;
    memset((void*)0x200,0,256); G(0x282)=switches; rr_init(); G(0x86)=255;
    xram0_set(XRAM_PSG,0,64);
    if (!configure_video()) return 1;
    rebuild_terrain(); render(); last_vsync=RIA.vsync;
    for (;;) {
        do {now=RIA.vsync;} while (now==last_vsync);
        delta=now-last_vsync; if (delta>1) skipped_frames+=delta-1;
        last_vsync=now; setup=0; input=read_input(); if (input&QUIT) break;
        controls=(pressed(0x3a) ? 1 : 0)|(pressed(0x3b) ? 2 : 0)|
                 (pressed(0x3c) ? 4 : 0)|(pressed(0x3d) ? 8 : 0);
        if ((controls&1) && !(previous_keys&1)) switches^=8;
        if ((controls&4) && !(previous_keys&4)) switches^=64;
        if ((controls&8) && !(previous_keys&8)) switches^=128;
        previous_keys=controls;
        if ((input&PAUSE) && !(previous_input&PAUSE)) paused^=1;
        G(0x282)=switches; if (controls&2) G(0x282)&=~2;
        if (((input&START) && !(previous_input&START)) ||
            ((ready || MODE==255) && (input&FIRE) && !(previous_input&FIRE))) {
            G(0x282)&=~1; ready=0; paused=0;
        }
        previous_input=input;
        if (!paused) {
            if (MODE==255) G(0xc0)=(uint16_t)rr_Space;
            reflected=G(0xe0); collisions(); G(0xe0)=0;
            old_offset=OFFSET; old_intro=MODE; rr_step(); ++ticks; reflected=G(0xe0);
            if (!(G(0x282)&1) || (old_intro>=128 && MODE<128)) {
                rebuild_terrain(); jet_cache=0xffff; setup=1;
            } else {
                scroll=(OFFSET-old_offset)&31;
                if (scroll>4) {rebuild_terrain(); setup=1;}
                else if (scroll) {
                    ring_top=ring_top>=scroll ? ring_top-scroll : RIVER_RING+ring_top-scroll;
                    for (y=0;y<scroll;++y) draw_terrain_row(y);
                }
            }
        }
        render();
        if (setup) last_vsync=RIA.vsync;
    }
    xram0_set(XRAM_PSG,0,64);
    xreg(0,0,0,0xffff); xreg(0,0,2,0xffff); xreg(0,1,0,0xffff); xreg(1,0,0,0);
    return 0;
}
