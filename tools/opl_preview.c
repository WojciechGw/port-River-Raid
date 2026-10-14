/* Optional offline preview shim; link with the firmware's MIT emu8950 core.
 * Windows example: cl /LD /O2 /DUSE_EMU8950_OPL=1 /DEMU8950_NO_RATECONV=1
 * /I<emu8950 directory> emu8950.c opl_preview.c
 * /link /OUT:opl-preview.dll
 * Does not participate in the 6502 build. Gain/clamp match core/aud/opl.c. */
#include "emu8950.h"
#include <stdint.h>
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
static OPL* chip;
EXPORT void rr_reset(void)
{
    if (!chip) chip=OPL_new(3579552,49716);
    OPL_reset(chip);
}
EXPORT void rr_write(unsigned reg,unsigned value)
{
    OPL_writeReg(chip,reg,value);
}
EXPORT int rr_sample(void)
{
    int16_t value;
    int sample;
    OPL_calc_buffer(chip,&value,1);
    sample=value*4;
    return sample>32767 ? 32767 : sample<-32768 ? -32768 : sample;
}
