#include <rp6502.h>
#include <stdio.h>
#include <string.h>
#include "xram.h"
#include "audio.h"
#define G(a) (*(uint8_t*)(a))

/* XL/XE uses clocked polynomial noise. PCM produces it at 8 kHz, together
 * with tones. Steps: noise clock, pure tone edges, /6 tone edges.
 * A two-sample filter and RIA interpolation soften the upper harmonics. */
static const uint16_t steps[3][32]={
    {65500u,65500u,65500u,65500u,65500u,65500u,65500u,64307u,57162u,51446u,46769u,42871u,39574u,36747u,34297u,32154u,30262u,28581,27077,25723,24498,23384,22368,21436,20578,19787,19054,18373,17740,17149,16595,16077},
    {65500u,65500u,65500u,64307u,51446u,42871u,36747u,32154u,28581,25723,23384,21436,19787,18373,17149,16077,15131,14290,13538,12861,12249,11692,11184,10718,10289,9893,9527,9187,8870,8574,8298,8038},
    {65500u,42871u,28581,21436,17149,14290,12249,10718,9527,8574,7795,7145,6596,6124,5716,5359,5044,4763,4513,4287,4083,3897,3728,3573,3430,3298,3176,3062,2957,2858,2766,2679}
};
static const uint16_t missile_steps[18]={
    6554,6190,5864,5571,5305,5064,4844,4642,4456,4285,4126,3979,3842,3714,3594,3482,3376,3277
};
static const uint8_t attenuation[16]={15,13,11,9,7,6,5,4,3,3,2,1,1,1,0,0};
/* YM3812 total level is 0.75 dB per step; match the native linear volume. */
static const uint8_t opl_level[16]={63,33,25,20,16,13,11,9,8,6,5,4,3,2,1,0};
uint8_t audio_backend,pcm_enabled,pcm_amplitude[2],pcm_tone[2];
uint16_t pcm_step[2];
static uint8_t requested=AUDIO_OPL2,shot_previous,shot_age=18;
static oscillator_t psg[8];
static uint16_t noise_rng=0x6502;
static uint16_t synth_shot_step;
static uint8_t synth_shot_volume;
static const uint8_t engine_volume[4]={4,4,7,5};
/* VIA sample clock, about 1000..3000 Hz. Runtime scales for PHI2. */
static uint16_t engine_period[16];
static const uint16_t engine_divider[16]={256,226,202,183,167,154,142,132,124,116,110,104,98,94,89,85};
uint16_t engine_latch;
uint8_t engine_active,engine_level;
static const uint8_t opl_slot[9]={0,1,2,8,9,10,16,17,18};
uint8_t opl_a[9],opl_b[9],opl_volume[9];
/* PSG 0: native effect, 1: missile, 2: bridge noise, 3: blast body,
 * 4..7: engine. OPL 0..3: engine, 4..6: blast, 7: missile, 8: fuel tone. */
void pcm_feed(void);
void pcm_reset(void);
void opl_commit(void);
void psg_engine_init(void);
void psg_engine_apply(void);
void psg_engine_stop(void);

#pragma optimize (push, on)
/* The SDK's optional argv allocator otherwise returns NULL. Arguments are
 * parsed before the cover/game reuse this 512-byte terrain working buffer. */
extern uint8_t reset_tiles[512];
void* __fastcall__ __argv_mem(unsigned bytes)
{
    return bytes<=512 ? reset_tiles : 0;
}
uint8_t audio_options(int argc,char** argv)
{
    uint8_t i;
    for (i=1;i<argc;++i) {
        if (!stricmp(argv[i],"/psg")) requested=AUDIO_PSG;
        else if (!stricmp(argv[i],"/opl2")) requested=AUDIO_OPL2;
        else if (!stricmp(argv[i],"/pcm")) requested=AUDIO_PCM;
        else if (!stricmp(argv[i],"/auto")) requested=AUDIO_AUTO;
        else {
            puts("Usage: load riverraid.rp6502 [/auto | /psg | /opl2 | /pcm]");
            return !stricmp(argv[i],"/help") || !strcmp(argv[i],"/?") ? 1 : 2;
        }
    }
    return 0;
}
static void opl_write(uint8_t reg,uint8_t value)
{
    RIA.step0=0; RIA.addr0=XRAM_OPL+reg;
    if (RIA.rw0!=value) RIA.rw0=value;
    RIA.step0=1;
}
static uint8_t noise8(void)
{
    /* Audio-only xorshift16; never consume the native course generator RNG. */
    noise_rng^=noise_rng<<7; noise_rng^=noise_rng>>9; noise_rng^=noise_rng<<8;
    return (uint8_t)noise_rng;
}
static uint16_t engine_pitch(uint8_t band)
{
    /* Separate, overlapping bands keep the noise spectrum steady. Deep 3:1
     * FM fills the spectrum; opl_voice lowers the engine by one octave.
     * Use the full speed accumulator for a smooth, almost 3:1 throttle range.
     * Max product is 44*255, within cc65's 16-bit arithmetic. */
    uint16_t hz=8+band*7+(noise8()>>4);
    return hz+((hz*G(0xb5))>>7);
}
static uint16_t tone_hz(uint16_t step)
{
    /* 8000/65536 = 1/8 - 1/512 - 1/1024; step clocks two edges/cycle. */
    return ((step>>3)-(step>>9)-(step>>10))>>1;
}
static void opl_instruments(void)
{
    static const uint8_t modulator[9]={0x23,0x23,0x23,0x23,0x22,0x22,0x22,0x23,0x23};
    static const uint8_t depth[9]={6,6,6,6,16,16,16,63,63};
    static const uint8_t connection[9]={0,0,0,0,8,8,8,1,1};
    uint8_t n,s,carrier;
    for (n=0;n<9;++n) {
        s=opl_slot[n]; carrier=s+3;
        /* Engine: deeper FM at a lower clock packs the sidebands more closely.
         * Zero feedback removes the rough, buzzy feedback harmonics.
         * Blast: retain the 2:1 feedback patch and its low body.
         * Tones: additive fundamental plus third harmonic (square-wave body),
         * instead of the former half-sine FM whistle. */
        opl_write(0x20+s,modulator[n]);
        opl_write(0x20+carrier,0x21);
        opl_write(0x40+s,depth[n]);
        opl_write(0x40+carrier,63);
        opl_write(0x60+s,0xf0); opl_write(0x60+carrier,0xf0);
        opl_write(0x80+s,0x0f); opl_write(0x80+carrier,0x0f);
        opl_write(0xe0+s,0); opl_write(0xe0+carrier,0);
        opl_write(0xc0+n,connection[n]);
    }
}
uint8_t audio_init(void)
{
    /* Cover pixels have finished using the shared PCM/OPL XRAM range. */
    if (requested==AUDIO_AUTO || requested==AUDIO_PCM) {
        static const uint8_t config[8]={0,2,3,11,0x40,0x1f,0,0};
        pcm_reset();
        xram0_set(XRAM_PCM,0,8+2048);
        xram0_write(XRAM_PCM,config,8);
        pcm_enabled=xreg(0,1,2,XRAM_PCM)>=0;
        if (pcm_enabled) {audio_backend=AUDIO_PCM; return 1;}
        if (requested==AUDIO_PCM) {
            puts("PCM requires firmware with XREG(0,1,2).");
            return 0;
        }
    }
    audio_backend=requested==AUDIO_PSG ? AUDIO_PSG : AUDIO_OPL2;
    /* A supported PCM stream must not remain mixed with an explicit PSG/OPL. */
    if (requested==AUDIO_OPL2 || requested==AUDIO_PSG) xreg(0,1,2,0xffff);
    if (audio_backend==AUDIO_OPL2) {
        if (xreg(0,1,1,XRAM_OPL)<0) return 0;
        opl_write(1,32); /* waveform selection */
        opl_instruments();
        return 1;
    }
    {
        uint8_t n;
        uint16_t clock=(uint16_t)ria_attr_get(RIA_ATTR_PHI2_KHZ)>>5;
        /* Q8 periods avoid linking a 32-bit divider for startup alone. */
        for (n=0;n<16;++n) engine_period[n]=((clock*engine_divider[n])>>3)-2;
        /* Opposite stationary waves act as signed level outputs. A timer
         * clocks polynomial noise into their volume registers; no PCM API. */
        for (n=4;n<8;++n) {
            psg[n].duty=255; psg[n].release_wave=(n&1) ? 0x30 : 0x10;
            psg[n].attack=psg[n].decay=0xf0;
        }
        xram0_write(XRAM_PSG,psg,sizeof(psg));
        if (xreg(0,1,0,XRAM_PSG)<0) return 0;
        psg_engine_init(); return 1;
    }
}
static void psg_update(uint8_t flight,uint8_t native_engine)
{
    uint8_t n,volume,level,bridge,mix;
    bridge=!pcm_tone[1] ? pcm_amplitude[1]>>1 : 0;
    /* Native PSG effect settings stay unchanged. Engine no longer occupies
     * or replaces an effect/bass slot. */
    volume=pcm_amplitude[0]>>1;
    psg[0].freq=(pcm_tone[0] ? tone_hz(pcm_step[0]) : 36+volume*4)*3;
    psg[0].duty=pcm_tone[0] ? 128 : 240;
    level=attenuation[volume];
    if (!pcm_tone[0]) level=level+6>14 ? 14 : level+6;
    if (native_engine) {
        /* Engine noise now has its own four level outputs. */
        volume=0;
    }
    psg[0].attack=psg[0].decay=level<<4;
    psg[0].release_wave=pcm_tone[0] ? 0x10 : 0x40;
    psg[0].pan_gate=volume!=0;

    psg[1].freq=tone_hz(synth_shot_step)*3;
    psg[1].duty=128; psg[1].release_wave=0x10;
    psg[1].attack=psg[1].decay=attenuation[synth_shot_volume]<<4;
    psg[1].pan_gate=synth_shot_volume!=0;

    psg[2].freq=(36+bridge*4)*3;
    psg[2].duty=240; psg[2].release_wave=0x40;
    level=attenuation[bridge]+6; if (level>14) level=14;
    psg[2].attack=psg[2].decay=level<<4; psg[2].pan_gate=bridge!=0;

    psg[3].pan_gate=0; psg[3].duty=255; psg[3].release_wave=0x30;
    if (!native_engine && !pcm_tone[0] && volume) {
        psg[3].freq=(40+volume*3)*3;
        psg[3].attack=psg[3].decay=attenuation[volume]<<4;
        psg[3].pan_gate=1;
    } else if (bridge) {
        psg[3].freq=(36+bridge*4)*3;
        psg[3].attack=psg[3].decay=(attenuation[bridge]+2)<<4;
        psg[3].pan_gate=1;
    }
    /* Keep the accepted effect patches, but leave mixing headroom when they
     * overlap. Engine noise keeps a nonzero gain, even with all effects on. */
    mix=(synth_shot_volume!=0)+(bridge!=0)+(!native_engine && volume!=0);
    mix=mix>=3 ? 4 : mix==2 ? 2 : 0;
    if (mix) for (n=0;n<4;++n) {
        level=(psg[n].attack>>4)+mix;
        if (level>15) level=15;
        psg[n].attack=psg[n].decay=level<<4;
    }
    engine_level=attenuation[engine_volume[G(0x84)&3]]+5+mix;
    if (engine_level>14) engine_level=14;
    engine_active=flight; engine_latch=engine_period[G(0xb5)>>4];
    xram0_write(XRAM_PSG,psg,32);
    psg_engine_apply();
}
static void opl_voice(uint8_t n,uint16_t hz,uint8_t volume,uint8_t trim)
{
    uint8_t level,block=24;
    uint16_t fnum;
    level=volume ? opl_level[volume]+trim : 63;
    if (level>63) level=63;
    /* Engine pitch is in half-Hz units, with 0.095 Hz register resolution.
     * Other low bands get 0.19 Hz; tones retain their original octave ranges. */
    if (hz<188) {block=n<4 ? 4 : 8; fnum=hz*21>>2;}
    else {
        if (hz>1500) {hz>>=1; block=28;}
        fnum=hz*21>>6;
    }
    opl_a[n]=(uint8_t)fnum;
    opl_b[n]=(fnum>>8)|block|(volume ? 32 : 0);
    opl_volume[n]=level;
}
static void opl_update(uint8_t flight,uint8_t native_engine)
{
    uint8_t n,volume,blast,bridge;
    uint16_t hz;
    volume=flight ? engine_volume[G(0x84)&3] : 0;
    for (n=0;n<4;++n) {
        hz=flight ? engine_pitch(n) : 0;
        opl_voice(n,hz,volume,3);
    }
    blast=(!native_engine && !pcm_tone[0]) ? pcm_amplitude[0]>>1 : 0;
    bridge=!pcm_tone[1] ? pcm_amplitude[1]>>1 : 0;
    if (bridge>blast) blast=bridge;
    for (n=4;n<7;++n) {
        /* Native volume controls both decay and the falling noise bandwidth:
         * a broad initial impact settles into a low rumble, never three tones.
         * Keep all bands separate from the engine, missile and fuel voices. */
        hz=blast ? 8+(n-4)*7+(noise8()>>4)+(blast<<1) : 0;
        opl_voice(n,hz,blast,6);
    }
    opl_voice(7,tone_hz(synth_shot_step),synth_shot_volume,0);
    opl_voice(8,tone_hz(pcm_step[0]),pcm_tone[0] ? pcm_amplitude[0]>>1 : 0,0);
    opl_commit();
}
void audio_update(uint8_t paused,uint8_t demo)
{
    uint8_t n,ctrl,divider,volume,shot,engine,muted,flight;
    muted=paused || demo;
    shot=G(0xfb);
    if (muted || G(0xc6) || (audio_backend==AUDIO_PCM && G(0xf8)==1)) shot_age=18;
    else if (shot>shot_previous) shot_age=0;
    shot_previous=shot;
    engine=!G(0xf8) && (G(0x215)&15)==8;
    flight=!G(0xc6) && !muted;
    synth_shot_volume=0;
    for (n=0;n<2;++n) {
        ctrl=G(0x215+n)&15; divider=G(0x217+n)&31;
        volume=G(0x219+n)&15;
        pcm_tone[n]=!(ctrl==8 || ctrl<4);
        pcm_step[n]=steps[!pcm_tone[n] ? 0 : ctrl==4 ? 1 : 2][divider];
        if (!n && G(0xf8)==1 && !pcm_tone[n]) pcm_step[n]=16384;
        if (audio_backend==AUDIO_PCM && n && shot_age<18) {
            if (!pcm_tone[n] && volume) shot_age=18;
            else {
                pcm_tone[n]=1; volume=15;
                pcm_step[n]=missile_steps[shot_age++];
            }
        }
        pcm_amplitude[n]=muted ? 0 : volume*2;
    }
    if (audio_backend!=AUDIO_PCM && shot_age<18) {
        synth_shot_step=missile_steps[shot_age++]; synth_shot_volume=15;
    }
    if (audio_backend==AUDIO_PCM) pcm_feed();
    else if (audio_backend==AUDIO_OPL2) opl_update(flight,engine);
    else psg_update(flight,engine);
}
void audio_stop(void)
{
    if (audio_backend==AUDIO_PCM) xreg(0,1,2,0xffff);
    else if (audio_backend==AUDIO_OPL2) xreg(0,1,1,0xffff);
    else {psg_engine_stop(); xram0_set(XRAM_PSG,0,64); xreg(0,1,0,0xffff);}
}
#pragma optimize (pop)
