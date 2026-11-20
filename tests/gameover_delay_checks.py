"""The last plane's crash must be audible before GAME OVER takes over."""
from emulator_checks import poke


def run_gameover_delay_checks(case,sym,fixture,resume,pcm_build):
    phase=f'0x{sym["demo_splash_gameover_phase"]:04x}'
    started=f'0x{sym["gameover_started"]:04x}'
    kind=f'0x{sym["jingle_kind"]:04x}'
    last=[poke(0xc0,sym['rr_Copyright0']&255),poke(0xb3,4)]
    for backend in (('opl2','pcm') if pcm_build else ('opl2',)):
        data=[]
        for final in (False,True):
            commands=fixture+(last if final else [poke(0xb3,4)])+resume
            for frame in range(22):
                commands += [f'peek {started} 0',f'peek {phase} 0',f'peek {kind} 2',
                    'peek 0xf8 1',f'dump 0x{sym["pcm_amplitude"]:04x} 2',
                    'dump xram:0xc900 256']
                if pcm_build and backend=='pcm':
                    commands += ['dump xram:0xc008 2048']
                commands += ['run 1']
            if final:
                commands += [f'wait {phase} 1 30','run 2','peek 0xf8 0',
                             f'peek {started} 1',f'peek {kind} 0']
            _,dumps=case(f'gameover-crash-first-{backend}-last{final}',commands,
                         rom_args=('/'+backend,))
            stride=3 if pcm_build and backend=='pcm' else 2
            levels=[dumps[i][0] for i in range(0,len(dumps),stride)]
            assert levels[0]>levels[-1]>0, 'Crash envelope was cut or never played'
            if backend=='opl2':
                channel=4 if pcm_build else 7
                assert all(dumps[i+1][0xb0+channel]&32 for i in range(0,len(dumps),stride))
            else:
                assert any(any(dumps[i+2]) for i in range(0,len(dumps),stride)), 'PCM crash is silent'
            data.append(dumps)
        assert data[0]==data[1], 'Last-plane crash differs from the complete ordinary crash path'
        case('gameover-crash-interrupts-victory-'+backend,fixture+[
            poke(sym['tanks'],[0]*30),poke(0xa2,8),poke(0x96,4),poke(0x9c,0x37),
            poke(0xbd,50),poke(0x90,128),poke(0xb5,0),'press down',
            poke(0xb2,75),poke(0xf5,80)]+resume+[f'peek {kind} 1']+last+[
            'run 6','peek 0xf8 1',f'peek {phase} 0',f'peek {started} 0',f'peek {kind} 2',
            f'wait {phase} 1 60','run 2',f'peek {started} 1',f'peek {kind} 0'],
            rom_args=('/'+backend,))

    for action in ('r','f2'):
        case('gameover-crash-cancel-'+action,fixture+last+resume+[
            f'peek {started} 0',f'peek {phase} 0',f'press {action}','run 3',
            f'release {action}','run 60',f'peek {started} 0',f'peek {phase} 0'])
    _,dumps=case('gameover-crash-pause',fixture+last+resume+[
        'press p','run 3','release p','run 3','dump 0xf9 1','run 40','dump 0xf9 1',
        f'peek {started} 0',f'peek {phase} 0',
        'press f1','wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5',
        'press z','run 3','release z','wait xram:0x0080 82 320','run 3','dump 0xf9 1',
        f'peek {started} 0',f'peek {phase} 0']+resume+[
        f'wait {phase} 1 40','run 2',f'peek {started} 1'])
    assert dumps[0]==dumps[1]==dumps[2], 'Crash countdown advanced while paused or in help'
