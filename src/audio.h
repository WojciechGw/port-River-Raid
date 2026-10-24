#ifndef RIVER_AUDIO_H
#define RIVER_AUDIO_H
#include <stdint.h>

/* Keep the OPL/PCM status IDs stable; slot 1 is unused. */
enum { AUDIO_AUTO=0, AUDIO_OPL2=2, AUDIO_PCM=3 };
/* F9 cycles 0 -> music off -> both off -> 0. */
enum { AUDIO_MUTE_MUSIC=1, AUDIO_MUTE_EFFECTS=2, AUDIO_MUTE_ALL=3 };
extern uint8_t audio_muted;
uint8_t audio_options(int argc,char** argv);
uint8_t audio_init(void);
#if RIVER_PCM
uint8_t audio_next(void);
#endif
void audio_update(uint8_t paused, uint8_t demo);
/* One short enemy voice; a new shot retriggers it at the shooter's pitch. */
void __fastcall__ audio_enemy_shot(uint8_t helicopter);
void audio_stop(void);
void gameover_install(void);
uint8_t gameover_update(void);
void gameover_stop(void);

#endif
