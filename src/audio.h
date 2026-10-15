#ifndef RIVER_AUDIO_H
#define RIVER_AUDIO_H
#include <stdint.h>

enum { AUDIO_AUTO, AUDIO_PSG, AUDIO_OPL2, AUDIO_PCM };
extern uint8_t audio_muted;
uint8_t audio_options(int argc,char** argv);
uint8_t audio_init(void);
uint8_t audio_next(void);
void audio_update(uint8_t paused, uint8_t demo);
void audio_stop(void);

#endif
