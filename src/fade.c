#include <rp6502.h>
#include "xram.h"

/* Startup and F1 return: preserve every palette, including transparent entries,
 * above the audio ring. Keep this code/state outside the startup music overlay.
 * Prepare colors offscreen; publish them together at VSYNC. */
#pragma optimize(push, on)
#pragma code-name("CODE")
#pragma bss-name("BSS")
void game_fade_capture(void);
void game_fade_publish(void);
uint16_t game_fade_read(void);

static void fade_palette(uint8_t level)
{
    static uint16_t i,color,faded;
    static uint8_t scaled[32];
    for (i=0;i<32;++i) scaled[i]=(i*level)>>5;
    RIA.addr0=XRAM_GAME_FADE_SOURCE;
    RIA.addr1=XRAM_GAME_FADE_STAGING;
    for (i=0;i<288;++i) {
        color=game_fade_read();
        faded=(color&32)|scaled[color&31]|
            ((uint16_t)scaled[(color>>6)&31]<<6)|
            ((uint16_t)scaled[color>>11]<<11);
        RIA.rw1=faded; RIA.rw1=faded>>8;
    }
}

void game_fade_prepare(void)
{
    game_fade_capture();
    fade_palette(0);
    game_fade_publish();
    RIA.addr0=XRAM_GAME_FADE_LEVEL; RIA.rw0=0;
}

void game_fade_in(void)
{
    static uint8_t level,vsync;
    vsync=RIA.vsync;
    for (level=1;level<=32;++level) {
        fade_palette(level);
        while ((uint8_t)(RIA.vsync-vsync)<2) {}
        vsync=RIA.vsync;
        game_fade_publish();
        RIA.addr0=XRAM_GAME_FADE_LEVEL; RIA.rw0=level;
        RIA.rw0=vsync;
    }
}
#pragma optimize(pop)
