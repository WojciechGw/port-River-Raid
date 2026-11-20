"""Capture the actual OPL2 engine and flight-music register streams."""
import json
from emulator_checks import poke


def run_opl_tuning_checks(case,sym,fixture,resume,output):
    clocks={}
    for name,speed,frames in (('engine-slow',0,180),('engine-fast',254,180),
                              ('engine-shared-slow',0,180),('engine-shared-fast',254,180),
                              ('flight-music',0,840)):
        music=name=='flight-music'
        shared=name.startswith('engine-shared')
        address=0xc900 if music or shared else 0xc000
        commands=fixture+[poke(sym['audio_muted'],0 if shared else 2 if music else 1),
            poke(sym['collisions'],0x60),poke(0xb7,[255,255]),poke(0xf8,[0]*4),
            poke(0xb5,speed),'press up' if speed else 'press down']+resume
        for _ in range(frames):
            commands+=['run 1',f'dump xram:0x{address:04x} 256']
        _,dumps=case('opl-tuning-'+name,commands,rom_args=('/opl2',))
        assert len(dumps)==frames
        if shared:
            assert all(r[0xb6]&32 and not(r[0xb7]&32 or r[0xb8]&32) for r in dumps)
        elif not music:
            assert all(all(r[0xb0+n]&32 for n in range(4)) for r in dumps)
            assert all(all(not r[0xb0+n]&32 for n in range(4,9)) for r in dumps)
        else:
            assert any(any(r[0xb0+n]&32 for n in range(6)) for r in dumps)
            assert all(all(not r[0xb0+n]&32 for n in range(6,9)) for r in dumps)
        if not music:
            ch=6 if shared else 0
            clocks[name]=sum((r[0xa0+ch]|((r[0xb0+ch]&3)<<8))*
                49716*2**((r[0xb0+ch]>>2)&7)/2**20 for r in dumps)/len(dumps)
        (output/('opl-tuning-'+name+'.json')).write_text(json.dumps([
            dict(seconds=1/60,opl2=list(r)) for r in dumps]),encoding='utf-8')
    for prefix in ('engine-','engine-shared-'):
        assert clocks[prefix+'fast']>clocks[prefix+'slow']*4, 'Noise clock does not follow throttle'
