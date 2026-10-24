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
/* YM3812 total level is 0.75 dB per step; match the native linear volume. */
static const uint8_t opl_level[16]={63,33,25,20,16,13,11,9,8,6,5,4,3,2,1,0};
/* Native effect parameters are shared by OPL2 and the optional PCM synth. */
uint8_t audio_backend,pcm_amplitude[2],pcm_tone[2];
#if RIVER_PCM
uint8_t pcm_enabled;
static uint8_t requested=AUDIO_OPL2;
#endif
uint8_t audio_muted;
uint8_t sound_verbose;
uint16_t pcm_step[2];
static uint8_t shot_previous,shot_age=18;
static uint16_t noise_rng=0x6502;
static uint16_t synth_shot_step;
static uint8_t synth_shot_volume;
static uint8_t enemy_age=18,enemy_helicopter,enemy_volume,enemy_pending;
static uint16_t enemy_step;
static const uint8_t engine_volume[4]={4,4,7,5};
extern uint8_t demo_splash_out,demo_splash_done,demo_splash_gameover_phase;
static const uint8_t opl_slot[9]={0,1,2,8,9,10,16,17,18};
uint8_t opl_a[9],opl_b[9],opl_volume[9];
/* OPL 0..3: engine, 4..6: blast, 7: missile, 8: enemy shot / fuel tone. */
#if RIVER_PCM
void pcm_feed(void);
void pcm_reset(void);
#endif
void opl_commit(void);
void music_effects(void);

#pragma optimize (push, on)
#pragma code-name(push, "STARTUP_AUDIO")
#pragma rodata-name(push, "STARTUP_AUDIO")
/* Replaced by the game-over player after argument parsing and startup fade. */
uint8_t audio_options(int argc,char** argv)
{
    static const char* const options[]={"/auto","/opl2",
#if RIVER_PCM
        "/pcm",
#endif
        "/v","/help","/?"};
    #define BACKEND_OPTIONS (2+RIVER_PCM)
    #define OPTION_COUNT (sizeof(options)/sizeof(options[0]))
    uint8_t i,n;
    for (i=1;i<argc;++i) {
        for (n=0;n<OPTION_COUNT;++n) if (!stricmp(argv[i],options[n])) break;
        if (n<BACKEND_OPTIONS) {
#if RIVER_PCM
            requested=n ? n+1 : AUDIO_AUTO;
#endif
        }
        else if (n==BACKEND_OPTIONS) sound_verbose=1;
        else {
#if RIVER_PCM
            puts("Usage: load riverraid.rp6502 [/auto | /opl2 | /pcm] [/v]");
#else
            puts("Usage: load riverraid.rp6502 [/auto | /opl2] [/v]");
#endif
            return n<OPTION_COUNT ? 1 : 2;
        }
    }
    return 0;
}
#pragma rodata-name(pop)
#pragma code-name(pop)
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
    /* Keep four independent phase clocks and the full speed accumulator.
     * Strong feedback supplies broadband noise, rather than audible FM notes.
     * Keep the RNG calls unchanged: blast voices share this sequence.
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
    static const uint8_t depth[9]={1,1,1,1,16,16,16,63,63};
    static const uint8_t connection[9]={14,14,14,14,8,8,8,1,1};
    uint8_t n,s,carrier;
    for (n=0;n<9;++n) {
        s=opl_slot[n]; carrier=s+3;
        /* Engine: maximum feedback with almost full modulator amplitude
         * breaks up periodic FM into continuous broadband noise. TL=1 keeps
         * residual carrier energy low; AM/vibrato and percussion stay off.
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
#if RIVER_PCM
static uint8_t try_pcm(void)
{
    static const uint8_t config[8]={0,2,3,11,0x40,0x1f,0,0};
    pcm_reset();
    xram0_set(XRAM_PCM,0,8+2048);
    xram0_write(XRAM_PCM,config,8);
    pcm_enabled=xreg(0,1,2,XRAM_PCM)>=0;
    if (pcm_enabled) audio_backend=AUDIO_PCM;
    return pcm_enabled;
}
#endif
uint8_t audio_init(void)
{
    /* Cover pixels have finished using the shared PCM/OPL XRAM range. */
#if RIVER_PCM
    if (requested==AUDIO_AUTO || requested==AUDIO_PCM) {
        if (try_pcm()) return 1;
        if (requested==AUDIO_PCM) {
            puts("PCM requires firmware with XREG(0,1,2).");
            return 0;
        }
    }
    xreg(0,1,2,0xffff);
#endif
    audio_backend=AUDIO_OPL2;
    /* PCM shares this range; never enable OPL with stale sample bytes. */
    xram0_set(XRAM_OPL,0,256);
    if (xreg(0,1,1,XRAM_OPL)<0) return 0;
    opl_write(1,32);
    opl_instruments();
    return 1;
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
    opl_voice(8,tone_hz(enemy_volume ? enemy_step : pcm_step[0]),
        enemy_volume ? enemy_volume : pcm_tone[0] ? pcm_amplitude[0]>>1 : 0,0);
    opl_commit();
}
void __fastcall__ audio_enemy_shot(uint8_t helicopter)
{
    enemy_pending=helicopter+1;
}
void audio_update(uint8_t paused,uint8_t demo)
{
    uint8_t n,ctrl,divider,volume,shot,engine,muted,flight;
    n=gameover_update();
    /* Starting/resuming music reinitializes audio. Consume this frame's
     * launch afterwards, so the first shot is not lost to audio_stop(). */
    if (enemy_pending) {
        enemy_helicopter=enemy_pending-1; enemy_age=0; enemy_pending=0;
    }
    if (n) {enemy_age=18; return;}
    muted=paused || demo || (audio_muted&AUDIO_MUTE_EFFECTS);
    if (muted || G(0xc6)) enemy_age=18;
    enemy_volume=0;
    if (enemy_age<18) {
        /* Same falling sweep as the player, one octave below / above it. */
        enemy_step=missile_steps[enemy_age];
        if (enemy_helicopter) enemy_step<<=1; else enemy_step>>=1;
        enemy_volume=12-(enemy_age>>1);
        ++enemy_age;
    }
    shot=G(0xfb);
    if (muted || G(0xc6)
#if RIVER_PCM
        || (audio_backend==AUDIO_PCM && G(0xf8)==1)
#endif
    ) shot_age=18;
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
#if RIVER_PCM
        if (audio_backend==AUDIO_PCM && n && shot_age<18) {
            if (!pcm_tone[n] && volume) shot_age=18;
            else {
                pcm_tone[n]=1; volume=15;
                pcm_step[n]=missile_steps[shot_age++];
            }
        }
#endif
        pcm_amplitude[n]=muted ? 0 : volume*2;
    }
    /* Only the departing splash gets an engine in demo. Keep native demo
     * shots/blasts muted, and use the normal engine synth on either backend. */
    if ((demo || demo_splash_gameover_phase==3) && demo_splash_out && !demo_splash_done && !paused &&
        !(audio_muted&AUDIO_MUTE_EFFECTS)) {
        flight=engine=1;
        pcm_tone[0]=0;
        pcm_step[0]=steps[0][31-(G(0xb5)>>4)];
        pcm_amplitude[0]=engine_volume[G(0x84)&3]*2;
    }
    if (
#if RIVER_PCM
        audio_backend!=AUDIO_PCM &&
#endif
        shot_age<18) {
        synth_shot_step=missile_steps[shot_age++]; synth_shot_volume=15;
    }
#if RIVER_PCM
    if (audio_backend==AUDIO_PCM) {
        /* Borrow the engine/fuel voice, never a crash or the player's shot. */
        if (enemy_volume && (engine || pcm_tone[0])) {
            pcm_tone[0]=1; pcm_step[0]=enemy_step;
            pcm_amplitude[0]=enemy_volume*2;
        }
        pcm_feed();
    }
    else
#endif
        opl_update(flight,engine);
    music_effects();
}
void audio_stop(void)
{
    enemy_age=18;
    gameover_stop();
#if RIVER_PCM
    if (audio_backend==AUDIO_PCM) xreg(0,1,2,0xffff);
    else
#endif
        xreg(0,1,1,0xffff);
#if RIVER_PCM
    pcm_enabled=0;
#endif
}
#if RIVER_PCM
uint8_t audio_next(void)
{
    audio_stop();
    requested=AUDIO_OPL2;
    if (audio_backend==AUDIO_OPL2 && try_pcm()) {
        requested=AUDIO_PCM; return 1;
    }
    return audio_init();
}
#endif
#pragma optimize (pop)
