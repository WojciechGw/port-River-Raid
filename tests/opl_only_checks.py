"""Shipping OPL2-only package on firmware that DOES support PCM."""
from pathlib import Path
from emulator_checks import poke


def run_opl_only_checks(case,sym,boot,fixture,resume,start,build,assets):
    from music_checks import check_opl_crash
    from help_checks import run_help_fade_checks
    forbidden={'pcm_feed','pcm_reset','pcm_enabled','music_pcm_probe','audio_next','intro_pcm_gain'}
    assert not forbidden.intersection(sym), 'PCM/switching code remains linked'
    assert not any('.pcm' in name or 'psg' in name or name.endswith('-score.bin') for name in assets)
    for name in ('intro','flight','gameover','victory'):
        assert assets[f'{name}-opl.bin'] == (build/f'{name}-opl.bin').read_bytes()
    assert assets['intro.bin'][1536:] == assets['intro-opl.bin']
    assert b'PCM' not in assets['help'] and b'F10' not in assets['help']
    # Verify the packaged keyboard artwork, not merely the CMake selection.
    from make_cover import build as build_screen
    root=Path(__file__).resolve().parents[1]
    pixels,palettes=build_screen(root/'assets/manualOPL.bmp')
    assert assets['manual.bin']==pixels and assets['manual-fade.bin']==palettes
    run_help_fade_checks(case,sym,boot,build/'checks')
    from demo_splash_checks import run_demo_splash_checks
    run_demo_splash_checks(case,sym,boot,build/'checks',assets)
    from splash_scene_checks import run_splash_scene_checks
    run_splash_scene_checks(case,sym,boot,fixture,resume,assets,False,build/'checks')
    check_opl_crash(case,sym,fixture,resume,'opl-only-plane-crash')
    from enemy_audio_checks import run_enemy_audio_checks
    run_enemy_audio_checks(case,sym,fixture,resume,'opl-only')
    from start_checks import run_start_checks
    run_start_checks(case,sym,boot)
    from splash_audio_checks import run_splash_audio_checks
    run_splash_audio_checks(case,sym,boot,False)
    from sound_mode_checks import run_sound_mode_checks
    run_sound_mode_checks(case,sym,boot,fixture,resume,False)

    active=f'peek 0x{sym["gameover_active"]:04x}'
    kind=f'peek 0x{sym["jingle_kind"]:04x}'
    backend=f'peek 0x{sym["audio_backend"]:04x} 2'
    synth=f'peek 0x{sym["music_synth"]:04x} 1'
    gain=f'0x{sym["intro_gain"]:04x}'
    intro=f'peek 0x{sym["intro_active"]:04x}'
    muted=f'peek 0x{sym["audio_muted"]:04x}'
    tap=['press f10','run 3','release f10','run 3']
    f9=['press f9','run 3','release f9','run 3']
    for option in ('/pcm','/psg'):
        case('opl-only-rejects-'+option[1:],['expect-exit 2 120','expect-not "/pcm"'],
             gameplay=False,rom_args=(option,))
    for option in ('/auto','/opl2'):
        case('opl-only-option-'+option[1:],boot+[backend,synth,active+' 1',kind+' 2'],rom_args=(option,))
    case('opl-only-help-option',['expect-exit 0 120','expect-not "/pcm"'],
         gameplay=False,rom_args=('/help',))

    commands=['wait xram:0x00b0 2 180',synth,intro+' 1']
    for _ in range(12): commands+=['run 12','dump xram:0x0100 256']
    _,dumps=case('opl-only-cover-percussion',commands,gameplay=False)
    assert len(set(dumps))>2
    for channel in range(6):
        assert any(d[0xb0+channel]&32 for d in dumps), f'Silent cover voice {channel}'

    # F10 must neither interrupt a tune nor produce the old backend notice.
    for variant in range(3):
        select=boot+['press f2','run 3','release f2','run 8']*variant
        commands=select+[active+' 1',kind+' 2',backend]+tap+[
            active+' 1',kind+' 2',backend,'peek xram:0x02c8 32 32 32 32']+f9*2+[
            muted+' 3',active+' 0']+tap+[
            muted+' 3',active+' 0','peek xram:0x02c8 79 70 70 32',
            'press f9','run 3','release f9','run 3',muted+' 0',active+' 1',
            'peek xram:0x02c8 32 32 32 32','run 65',
            'peek xram:0x02c8 32 32 32 32']
        case(f'opl-only-f9-f10-game{variant+1}',commands)

    _,status=case('opl-only-verbose-no-backend',boot+[
        'dump xram:0x02c0 12','peek xram:0x0232 56 1']+f9*2+['dump xram:0x02c0 12']+
        f9+['dump xram:0x02c0 12',
        'peek xram:0x0232 56 1'],rom_args=('/v',))
    assert [s[8:] for s in status]==[b'    ',b'OFF ',b'    '], 'Wrong OPL-only sound status'
    assert status[0]==status[2] and status[0][:8]!=status[1][:8] and all(any(s[:8]) for s in status)

    commands=fixture+resume+[active+' 1',kind+' 2',synth,
        poke(0xf8,[3,8]),poke(0xfa,[23,15]),'run 2','dump xram:0xc900 256']
    commands+=tap+[active+' 1',kind+' 2',backend]
    _,dumps=case('opl-only-flight-and-effects',commands)
    assert any(dumps[0][0xb0+n]&32 for n in range(3)), 'Melody stopped during effects'
    # A snare is not struck on every beat; effects have dedicated channels.
    assert all(dumps[0][0xb0+n]&32 for n in (6,7,8)), 'Missing overlapping effect voice'

    opening=['press f1','wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5']
    for scene in ('initial-manual','f1','outro'):
        if scene=='initial-manual':
            commands=['wait xram:0x00b0 2 180','press z','run 3','release z',
                'wait xram:0x00b4 2 120','wait xram:0x00b0 2 90','wait xram:0x02a4 222 5']
        else:
            commands=boot+(opening if scene=='f1' else ['press escape','wait xram:0x00b0 2 120'])
        commands += [intro+' 1',f'peek {gain} 63']
        if scene!='outro': commands+=['press z']
        commands+=['wait xram:0x00b0 3 200','wait xram:0x00b1 31 40',f'dump {gain} 1',
            'wait xram:0x00b1 0 40',f'peek {gain} 0','dump xram:0x0140 32']
        if scene=='outro': commands+=['expect-exit 0 5']
        else:
            commands+=['release z','wait xram:0x0080 82 320',
                f'wait 0x{sym["ready"]:04x} 2 180','run 4',active+' 1',kind+' 2']
            commands+=opening+[intro+' 1',f'peek {gain} 63']
        _,dumps=case(f'opl-only-{scene}-fade',commands,gameplay=False)
        assert 25<=dumps[0][0]<=35, 'Music did not fade with the picture'
        assert all(dumps[1][3+n]==63 for n in (0,1,2,8,9,10,16,17,18)), 'Fade did not reach silence'

    case('opl-only-gameover',fixture+[
        poke(0xc0,sym['rr_Copyright0']&255),poke(0xb3,4)]+resume+[
        active+' 1',kind+' 0']+tap+[active+' 1',kind+' 0','run 450',active+' 1',kind+' 2'])
    case('opl-only-victory',fixture+[
        poke(sym['tanks'],[0]*30),poke(0xa2,8),poke(0x96,4),poke(0x9c,0x37),
        poke(0xb5,0),'press down',poke(0xb2,75),poke(0xf5,80),
        poke(0xbd,5),poke(0x90,128)]+resume+[
        active+' 1',kind+' 1','peek 0xc0 32']+tap+[active+' 1',kind+' 1'])
    case('opl-only-frame-budget',start+[
        'press up space','run 1200','release up space','run 2',backend,synth])
