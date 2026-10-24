"""Firmware capability fallback, percussion, flight music and effect coexistence."""
from emulator_checks import poke


def check_opl_crash(case,sym,fixture,resume,name,channel=6):
    # Cause a real bank collision with spare lives, leaving the flight tune
    # running. Check the audible music mirror, not just the effects producer.
    commands=fixture+[poke(0xb3,4)]+resume+[
        'peek xram:0x0082 2',
        f'peek 0x{sym["jingle_kind"]:04x} 2']
    for _ in range(36):
        commands+=['dump xram:0xc000 256','dump xram:0xc900 256','run 1']
    _,dumps=case(name,commands)
    levels=[]
    slot=(0,1,2,8,9,10,16,17,18)[channel]
    for source,output in zip(dumps[::2],dumps[1::2]):
        if source[0xb4]&32:
            assert output[0xb0+channel]&32, 'Crash was replaced by the silent engine'
            for base in (0x20,0x23,0x40,0x43,0x60,0x63,0x80,0x83,0xe0,0xe3):
                assert output[base+slot]==source[base+9], 'Crash instrument/volume was not copied'
            for base in (0xa0,0xb0,0xc0):
                assert output[base+channel]==source[base+4], 'Crash pitch/key was not copied'
            levels.append(output[0x43+slot])
    assert len(levels)>=20 and levels[0]<levels[-1], 'Crash lost its native decay'
    assert not dumps[-1][0xb0+channel]&32, 'Crash did not stop after its decay'


def run_music_checks(case,sym,boot,fixture,resume,build,assets,image):
    reference=(build/'riverraid.rom').read_bytes()
    assert bytes(image.data[a] for a in range(0xcb00,0xd000))==reference[0xb00:]
    assert sym['rr_Zero']==0xcb00
    assert not any('psg' in name.lower() for name in assets), 'PSG assets remain in the package'
    assert 'psg_engine_init' not in sym and 'music_psg_note' not in sym
    case('music-rejects-removed-psg-option',['expect-exit 2 120','expect-not "/psg"'],
         gameplay=False,rom_args=('/psg',))
    synth=f'peek 0x{sym["music_synth"]:04x}'
    active=f'peek 0x{sym["gameover_active"]:04x}'
    kind=f'peek 0x{sym["jingle_kind"]:04x}'
    # A real -1 response at the firmware-probe boundary, without touching the
    # fallback code or forcing its outcome after it has already initialized.
    legacy=[poke(sym['music_pcm_probe'],[0xa9,0xff,0xaa,0x60])]
    check_opl_crash(case,sym,legacy+fixture,resume,'music-crash-no-pcm')
    check_opl_crash(case,sym,fixture,resume,'music-crash-hybrid',channel=4)
    opening=['press f1','wait xram:0x00b0 2 120','release f1',
             'wait xram:0x02a4 222 5']
    closing=['press z','run 3','release z','wait xram:0x0080 82 240','run 4']
    for backend,mode in (('opl2',1),):
        commands=legacy+['wait xram:0x00b0 2 180',synth+f' {mode}',
                         'dump xram:0x0100 256']
        for _ in range(8): commands+=['run 12','dump xram:0x0100 256']
        _,dumps=case(f'music-cover-no-pcm-{backend}',commands,gameplay=False,rom_args=('/'+backend,))
        assert len(set(dumps))>2, 'Fallback notes do not advance without PCM'
        for channel in (3,4,5):
            assert any(d[0xb0+channel]&32 for d in dumps), 'Missing FM percussion voice'
        commands=legacy+boot+[synth+f' {mode}',active+' 1',kind+' 2',
            'dump xram:0xc900 256','run 60','dump xram:0xc900 256',
            'press space','run 140','release space','run 4',active+' 1',kind+' 2',
            'dump xram:0xc900 256','press p','run 3','release p','run 3','mark']
        commands+=opening+[synth+f' {mode}']+closing+['expect-same']+resume+[
            'run 8',active+' 1',kind+' 2',synth+f' {mode}',
            'press f9','run 3','release f9','run 3',active+' 0',
            'press f9','run 3','release f9','run 4',active+' 1',kind+' 2']
        _,dumps=case(f'music-flight-help-mute-no-pcm-{backend}',commands,rom_args=('/'+backend,))
        assert dumps[0]!=dumps[1], 'Demo score did not advance'
        assert dumps[2][0xb6]&32, 'Engine missing alongside FM drums and melody'
        case(f'music-outro-no-pcm-{backend}',legacy+boot+[
            'press escape','wait xram:0x00b0 3 320',synth+f' {mode}',
            'wait xram:0x00b1 0 90']+[
                f'peek xram:0x{0x100+(0x43+(8,9,10)[ch]):04x} {63}'
                for ch in range(3)]+['expect-exit 0 5'],gameplay=False,rom_args=('/'+backend,))
        case(f'music-gameover-no-pcm-{backend}',legacy+fixture+[
            poke(0xc0,sym['rr_Copyright0']&255),poke(0xb3,4)]+resume+[
                synth+f' {mode}',active+' 1',kind+' 0','run 450',active+' 1',kind+' 2'],
                rom_args=('/'+backend,))
        case(f'music-victory-no-pcm-{backend}',legacy+fixture+[
            poke(sym['tanks'],[0]*30),poke(0xa2,8),poke(0x96,4),poke(0x9c,0x37),
            poke(0xb5,0),'press down',poke(0xb2,75),poke(0xf5,80),
            poke(0xbd,5),poke(0x90,128)]+resume+[
                synth+f' {mode}',active+' 1',kind+' 1','peek 0xc0 32'],rom_args=('/'+backend,))

    for backend in ('opl2','pcm'):
        commands=fixture+resume+[synth+' 0',active+' 1',kind+' 2',
            'dump xram:0xc900 256','dump xram:0x0180 64',
            f'dump 0x{sym["pcm_amplitude"]:04x} 2']
        for frame in range(1,181):
            read=(frame*16000//60)%1024
            commands += [f'poke xram:0xca06 {read&255} {read>>8}','run 1']
        commands += [active+' 1',kind+' 2','dump xram:0xc900 256','dump xram:0xca08 1024',
                     'dump xram:0xca00 2','dump xram:0xc006 2']
        _,dumps=case(f'music-flight-effects-{backend}',commands,rom_args=('/'+backend,))
        assert any(dumps[2]), 'Procedural effects were suppressed by music'
        assert dumps[0][:0xb3]!=dumps[3][:0xb3], 'Flight melody stopped'
        if backend=='opl2': assert dumps[3][0xb3]&32, 'OPL engine missing'
        if backend=='pcm': assert any(dumps[6]), 'PCM effects consumer never advanced'
        consumed=180*16000//60
        queued=(int.from_bytes(dumps[5],'little')-consumed)%1024
        assert 256<queued<=768, 'Flight percussion buffer underrun'

    # Known signed effects samples isolate the actual on-CPU mix/upsampling
    # from the procedural synthesizer. Cross both ring wrap boundaries.
    drums=assets['flight-drums.pcm']
    for sample in (24,-24):
        commands=fixture+resume+[poke(sym['pcm_feed'],0x60)]
        commands += [poke(0xc008+offset,[sample&255]*128).replace('poke ','poke xram:',1)
                     for offset in range(0,2048,128)]
        for page in range(1,21):
            commands += [f'poke xram:0xca06 0 {page%4}','run 2',
                f'dump xram:0x{0xca08+((page+2)%4)*256:04x} 256','dump xram:0xc006 2']
        _,dumps=case(f'music-pcm-signed-mix-{sample}',commands,rom_args=('/pcm',))
        for page in range(1,21):
            chunk,read=dumps[(page-1)*2:page*2]
            source=drums[(page+2)*256:(page+3)*256]
            assert chunk==bytes((value+sample//2)&255 for value in source), f'PCM mix page {page}'
            assert int.from_bytes(read,'little')==(384+page*128)%2048
