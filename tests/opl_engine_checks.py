"""The audible engine must survive effects while all six music voices play."""
from emulator_checks import poke


def run_opl_engine_checks(case,sym,fixture,resume):
    from music_checks import check_opl_crash
    check_opl_crash(case,sym,fixture,resume,'opl-engine-plane-crash',channel=7)
    slots=(0,1,2,8,9,10,16,17,18)

    def voice(regs,ch):
        return bytes(regs[base+slots[ch]] for base in
            (0x20,0x23,0x40,0x43,0x60,0x63,0x80,0x83,0xe0,0xe3))+bytes(
            regs[base+ch] for base in (0xa0,0xb0,0xc0))

    for name,trigger in (
        ('bridge',[poke(0xfa,[23,15])]),
        ('player-shot',[poke(0xfb,15)]),
        ('fuel',[poke(0xf8,[3,8])]),
        ('enemy-shot',[poke(sym['enemy_pending'],1)]),
        ('overlap',[poke(0xfa,[23,15]),poke(sym['enemy_pending'],1)]),
    ):
        commands=fixture+[poke(0xf8,[0]*4)]+resume+trigger
        for frame in range(40):
            # Keep a fresh player shot available after the blast has decayed.
            if name=='overlap': commands += [poke(0xfb,15 if frame%2 else 0)]
            commands += ['run 1','peek xram:0x0082 1',
                         'dump xram:0xc000 256','dump xram:0xc900 256']
        _,data=case('opl-engine-continuous-'+name,commands)
        blasts=shots=tones=0
        for source,output in zip(data[::2],data[1::2]):
            assert output[0xb6]&32, 'Engine switched off during flight'
            assert voice(output,6)==voice(source,0), 'An effect replaced the engine'
            blast=bool(source[0xb4]&32)
            assert voice(output,7)==voice(source,4 if blast else 7), 'Wrong blast/shot routing'
            assert voice(output,8)==voice(source,8), 'Fuel/enemy tone was lost'
            blasts+=blast
            shots+=not blast and bool(output[0xb7]&32)
            tones+=bool(output[0xb8]&32)
        if name in ('bridge','overlap'): assert blasts>=8, 'Explosion missing or truncated'
        if name in ('player-shot','overlap'): assert shots>=8, 'Shot did not play after blast'
        if name in ('fuel','enemy-shot','overlap'): assert tones>=3, 'Fuel/enemy effect missing'
