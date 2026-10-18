"""Switch actual audio backends without restarting the game."""
from emulator_checks import poke


def run_audio_switch_checks(case,sym,fixture,resume,start,output):
    backend=f'peek 0x{sym["audio_backend"]:04x}'
    muted=f'peek 0x{sym["audio_muted"]:04x}'
    enabled=f'peek 0x{sym["pcm_enabled"]:04x}'
    amplitudes=f'dump 0x{sym["pcm_amplitude"]:04x} 2'
    tap=['press f10','run 3','release f10','run 3']
    opening=['press f1','wait xram:0x0080 0 10','wait xram:0x00b0 2 120',
             'release f1','wait xram:0x02a4 222 5']
    closing=['press space','run 3','release space','wait xram:0x0080 82 240','run 3']

    for option,initial in (('psg',1),('opl2',2),('pcm',3)):
        commands=fixture+['dump 0x80 128']
        current=initial
        for _ in range(6):
            current=current%3+1
            commands+=['press f10','run 3',backend+f' {current}',
                       enabled+f' {int(current==3)}','run 12',backend+f' {current}',
                       'release f10','run 3',amplitudes]
        commands+=['dump 0x80 128']+opening+closing+[
            backend+f' {initial}', 'peek xram:0x008b 1','dump 0x80 128']+resume+[
            'run 4',amplitudes]
        _,data=case(f'f10-cycle-and-help-{option}',commands,rom_args=('/'+option,))
        assert data[0]==data[7]==data[8], 'Switching audio changed the paused game'
        assert all(not any(a) for a in data[1:7]), 'Switching audio broke pause silence'
        assert any(data[9]), 'Selected backend did not resume sound'

    # Exercise switching while flying, including F9 and a second PSG IRQ setup.
    for duo in (False,True):
        if duo:
            setup=start+['press f2','run 3','release f2','run 8',
                         'press f2','run 3','release f2','run 8',
                         'press space','run 140','release space','run 4','press down s']
        else:
            setup=fixture+resume+['press down']
        commands=setup+['press f9','run 3','release f9','run 3',muted+' 1']
        for _ in range(6):
            commands+=tap+[backend+' 2',muted+' 1',amplitudes,
                            'peek xram:0x02c8 32 32 32 32']
        commands+=['press f9','run 3','release f9','run 3',muted+' 0',amplitudes,
                   'release down s','peek xram:0x008b 0']
        _,data=case(f'f10-live-muted-{"duo" if duo else "solo"}',commands)
        assert all(not any(a) for a in data[:-1]) and any(data[-1])

    # The one-second notice also expires while the game is paused.
    for option,current,label in (('psg',2,b'OPL '),('opl2',3,b'PCM '),('pcm',1,b'PSG ')):
        _,data=case(f'f10-notice-one-second-{option}',fixture+tap+[
            backend+f' {current}', 'dump xram:0x0220 30', 'dump xram:0x02c8 4',
            f'shot "{(output / f"f10-notice-{option}.png").as_posix()}"',
            'run 50','dump xram:0x02c8 4','run 10','dump xram:0x02c8 4',
            'peek xram:0x0232 56 1'],
            rom_args=('/'+option,))
        assert int.from_bytes(data[0][2:4],'little')==296
        assert int.from_bytes(data[0][6:8],'little')==3
        assert int.from_bytes(data[0][18:20],'little')==280
        assert int.from_bytes(data[0][4:6],'little')==232
        assert data[1:]==[label,label,b'    ']

    _,data=case('f10-notice-refresh',fixture+tap+['run 30']+tap+[
        backend+' 1','run 30','dump xram:0x02c8 4','run 20',
        'dump xram:0x02c8 4','run 10','dump xram:0x02c8 4'])
    assert data==[b'PSG ',b'PSG ',b'    ']
    _,data=case('f10-hold-does-not-refresh',fixture+[
        'press f10','run 3',backend+' 3','dump xram:0x02c8 4',
        'run 70',backend+' 3','dump xram:0x02c8 4',
        'release f10','run 3','press f10','run 3',backend+' 1',
        'release f10','run 3','dump xram:0x02c8 4'])
    assert data==[b'PCM ',b'    ',b'PSG ']

    for option,current,label in (('psg',1,b'PSG '),('opl2',2,b'OPL '),('pcm',3,b'PCM ')):
        _,data=case(f'f9-unmute-notice-{option}',fixture+[
            'press f9','run 3','release f9','run 3',muted+' 1',
            'dump xram:0x02c0 8','dump xram:0x02c8 4',
            'press f9','run 3',muted+' 0',backend+f' {current}',
            'dump xram:0x02c0 8','dump xram:0x02c8 4',
            'run 50','dump xram:0x02c8 4','run 10',
            'dump xram:0x02c8 4','release f9','run 3'],
            rom_args=('/'+option,))
        assert any(data[0]) and not any(data[2]), 'F9 did not hide the muted note'
        assert data[1]==b'    '
        assert data[3:]==[label,label,b'    '], 'F9 notice did not expire while held'

    # This emulator always supports PCM. Simulate the capability probe's
    # negative return, without changing production code or CLI options.
    commands=fixture+[poke(sym['try_pcm'],[0xa9,0,0xa2,0,0x60])]
    for current in (1,2,1,2,1):
        commands+=tap+[backend+f' {current}',enabled+' 0']
    commands+=opening+closing+[backend+' 1']+resume+['run 4',amplitudes,
        'expect-not "PCM requires firmware"']
    _,data=case('f10-skips-unavailable-pcm',commands)
    assert any(data[0]), 'Fallback to PSG left audio silent'

    ticks=f'dump 0x{sym["engine_ticks"]:04x} 2'
    _,data=case('f10-live-audible-and-timer',fixture+resume+[
        'press down']+tap+[backend+' 3',amplitudes]+tap+[
        backend+' 1','run 8',amplitudes,ticks,'run 8',ticks]+
        tap+[backend+' 2',amplitudes,ticks,'run 8',ticks,
             'dump xram:0x0180 64','dump xram:0xc000 256']+
        tap+tap+[backend+' 1','run 8',ticks,'run 8',ticks])
    assert all(any(data[n]) for n in (0,1,4)), 'An audible backend switch went silent'
    assert data[2]!=data[3] and data[5]==data[6], 'PSG timer was not started/stopped'
    assert all(not (data[7][n*8+6]&1) for n in range(8)), 'PSG still plays under OPL'
    assert any(data[8][0xb0+n]&32 for n in range(9)), 'OPL did not resume'
    assert data[9]!=data[10], 'Returning to PSG did not restart its engine timer'
