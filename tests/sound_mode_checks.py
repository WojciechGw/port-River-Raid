"""F9 cycles all sound, effects only and full mute."""
from emulator_checks import poke


def run_sound_mode_checks(case,sym,boot,fixture,resume,pcm_build):
    tap=['press f9','run 3','release f9','run 3']
    mode=f'peek 0x{sym["audio_muted"]:04x}'
    music=f'peek 0x{sym["gameover_active"]:04x}'
    kind=f'peek 0x{sym["jingle_kind"]:04x}'
    labels=(b'    ',b'SFX ',b'    ',b'OFF ')
    opening=['press f1','wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5']
    closing=['press z','run 3','release z','wait xram:0x0080 82 320','run 4']
    backends=('opl2','pcm') if pcm_build else ('opl2',)
    for backend in backends:
        commands=fixture+resume+['press down']
        for index,state in enumerate((0,1,3,0)):
            if index: commands+=tap
            commands+=[mode+f' {state}',music+f' {int(not state&1)}',
                poke(0xf8,[0,0,0,15]),'run 2',
                f'dump 0x{sym["pcm_amplitude"]:04x} 2',
                'dump xram:0xc000 256','dump xram:0xc900 256',
                'dump xram:0x02c8 4']
        _,data=case('f9-three-states-'+backend,commands,rom_args=('/'+backend,))
        for i,state in enumerate((0,1,3,0)):
            amp,effects,score,label=data[i*4:i*4+4]
            assert bool(any(amp))==bool(not state&2), f'Wrong effect volume in F9 state {state}'
            expected=labels[state] if state or not pcm_build or i==0 else (b'OPL ' if backend=='opl2' else b'PCM ')
            assert label==expected, (state,label,expected)
            if backend=='opl2':
                assert bool(any(effects[0xb0+n]&32 for n in range(9)))==bool(not state&2)

    for variant in range(3):
        commands=boot+['press f2','run 3','release f2','run 8']*variant
        for state in (1,3,0):
            commands+=['press f9','run 3',mode+f' {state}','run 70',mode+f' {state}',
                'release f9','run 3']+opening+[
                f'peek 0x{sym["intro_active"]:04x} {int(not state&1)}']+closing+[
                mode+f' {state}',music+f' {int(not state&1)}']
        case(f'f9-hold-help-game{variant+1}',commands)

    # Both jingles obey music mute; a victory still awards a life.
    for state in (0,1,3):
        for victory in (False,True):
            setup=fixture+tap*{0:0,1:1,3:2}[state]
            if victory:
                setup += [poke(sym['tanks'],[0]*30),poke(0xa2,8),poke(0x96,4),poke(0x9c,0x37),
                    poke(0xb5,0),'press down',poke(0xb2,75),poke(0xf5,80),poke(0xbd,5),poke(0x90,128)]
            else: setup += [poke(0xc0,sym['rr_Copyright0']&255),poke(0xb3,4)]
            commands=setup+resume+[mode+f' {state}',music+f' {int(not state&1)}']
            if not state&1: commands += [kind+f' {int(victory)}']
            if victory: commands += ['peek 0xc0 32']
            case(f'f9-state-{state}-'+('victory' if victory else 'gameover'),commands)

    if pcm_build:
        commands=fixture+resume
        for state,current in ((1,3),(3,3),(0,2)):
            commands+=tap+['press f10','run 3','release f10','run 3',mode+f' {state}',
                f'peek 0x{sym["audio_backend"]:04x} {current}',music+f' {int(not state&1)}']
        case('f9-partial-mute-allows-f10',commands)
