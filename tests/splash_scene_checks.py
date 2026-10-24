"""Final-life graphics and ROM descriptor ownership during PCM playback."""
import struct
from emulator_checks import poke


def run_splash_scene_checks(case,sym,boot,fixture,resume,assets,pcm_build,output):
    kind=f'0x{sym["demo_splash_kind"]:04x}'
    phase=f'0x{sym["demo_splash_gameover_phase"]:04x}'
    arrived=[f'wait {kind} 2 90','run 2']
    frame=['dump xram:0x6500 4096','dump xram:0xd600 4096',
           'dump xram:0x7580 512','dump xram:0x7514 20']
    opening=['press f1','wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5']
    closing=['press z','run 3','release z','wait xram:0x0080 82 320','run 3']

    def verify(data,scene,visible=True,mono=False):
        asset=assets[f'splash-{scene}.bin']
        assert data[0]+data[1]==asset[:8192], f'Wrong {scene} pixels'
        assert data[2]==(asset[8704:9216] if mono else asset[8192:8704]), 'Wrong scene palette'
        if visible:
            for n in range(2):
                assert struct.unpack_from('<hh',data[3],n*10)==(200+64*n,4)

    last=[poke(0xc0,sym['rr_Copyright0']&255),poke(0xb3,4)]
    for variant in (0,1):
        for muted in (0,1,3):
            setup=fixture+[poke(0x80,variant),poke(sym['audio_muted'],muted)]
            if variant: setup += [poke(0xc5,sym['rr_Copyright0']&255)]
            commands=setup+last+resume+arrived+[f'peek {kind} 2']+frame
            if not muted:
                commands += [f'shot "{(output/f"splash-gameover-game{variant+1}.png").as_posix()}"']
            _,data=case(f'splash-gameover-game{variant+1}-mute{muted}',commands)
            verify(data,'gameover')
        for pilot in (0,1):
            case(f'splash-game2-surviving-p{pilot+1}',fixture+[
                poke(0x80,1),poke(0xf4,pilot),poke(0xc5,8)]+last+resume+[
                'run 3',f'peek {kind} 0','peek xram:0x7516 0 255'])

    # F1 must restore GAME OVER even though stopping the tune resets audio.
    commands=fixture+last+resume+arrived+['press p','run 3','release p','run 3']
    _,data=case('splash-gameover-help-and-mono',commands+frame+opening+closing+frame+[
        'press p','run 3','release p','run 3','press f4','run 3','release f4','run 3']+frame)
    verify(data[:4],'gameover'); verify(data[4:8],'gameover'); verify(data[8:],'gameover',mono=True)
    case('splash-gameover-returns-to-demo',fixture+[poke(sym['audio_muted'],3)]+last+resume+arrived+[
        f'wait {phase} 3 500',f'peek {kind} 2',f'wait {phase} 0 60',
        f'wait {kind} 1 90'])
    case('splash-gameover-restart-clears',fixture+last+resume+['run 3','press r',
        'run 3','release r','run 3',f'peek {kind} 0','peek xram:0x7516 0 255'])

    players=sym['duo_players']
    duo=boot+['press f2','run 3','release f2','run 3']*2+['run 5',
        'press space','run 136','release space','run 4','press p','run 3','release p','run 3',
        poke(0xa0,[255]*6),poke(0x8e,[0]*6),poke(0x8b,[0,0]),poke(0xc6,0),poke(0xf8,[0]*4),
        poke(sym['duo_bridge'],0),poke(sym['duo_over'],0),poke(sym['duo_gap'],[0,0]),
        poke(sym['river1'],[0]*192),poke(sym['river2'],[0]*192),
        poke(sym['player_outer_left'],[16]*192),poke(sym['player_outer_right'],[144]*192),
        poke(sym['player_island_left'],[0]*192),poke(sym['player_island_right'],[0]*192),
        'press down s']
    for pilot in (0,1):
        base=players+23*pilot
        duo += [poke(base,[180,60+pilot*30,0,0,128,0]),
                poke(base+6,struct.pack('<H',sym['rr_JetStraight']-1)),
                poke(base+8,[8,255,0,0,65+pilot*30]+[88]*5+[0,1,0,68+pilot*16,106])]
    for pilot in (0,1):
        base,other=players+23*pilot,players+23*(pilot^1)
        case(f'splash-game3-surviving-p{pilot+1}',duo+[poke(base+4,[0,0])]+resume+[
            'run 3',f'peek {kind} 0'])
        for muted in (0,3):
            _,data=case(f'splash-game3-last-p{pilot+1}-mute{muted}',duo+[
                poke(sym['audio_muted'],muted),poke(other+8,0),poke(other+19,[0,0]),
                poke(base+4,[0,0])]+resume+arrived+[f'peek {kind} 2']+frame)
            verify(data,'gameover')
    _,data=case('splash-game3-simultaneous',duo+[poke(players+4,[0,0]),poke(players+27,[0,0])]+
        resume+arrived+[f'peek {kind} 2']+frame)
    verify(data,'gameover')

    # Every final-life trigger now flies in, holds GAME OVER until the
    # actual tune ends, flies out with the text, then starts a fresh entry.
    solo=(fixture,last+resume)
    alternating=(fixture+[poke(0x80,1),poke(0xc5,sym['rr_Copyright0']&255)],last+resume)
    simultaneous=(duo,[poke(players+4,[0,0]),poke(players+27,[0,0])]+resume)
    for variant,(setup,trigger) in enumerate((solo,alternating,simultaneous),1):
        for muted in (0,3):
            commands=setup+[poke(sym['audio_muted'],muted)]+trigger+['run 3',f'peek {phase} 1',f'peek {kind} 0']+frame
            commands+=arrived+[f'peek {phase} 2']+frame
            if pcm_build and not muted:
                # An unconsumed PCM score must keep GAME OVER visible even
                # after the native world has resumed demo and 6.7s passed.
                commands+=['run 450',f'peek {phase} 2',f'peek {kind} 2']
                for page in range(1,420):
                    commands += [f'poke xram:0xca06 0 {page%4}','run 2']
            commands += [f'wait {phase} 3 500',f'peek {kind} 2','run 3']+frame
            commands += [f'wait {phase} 0 60','run 3',f'peek {kind} 0']+frame+[
                f'wait {kind} 1 90','run 2']+frame
            _,data=case(f'splash-gameover-sequence-game{variant}-mute{muted}',commands)
            verify(data[:4],'plane',visible=False)
            verify(data[4:8],'gameover')
            verify(data[8:12],'gameover',visible=False)
            assert -128<struct.unpack_from('<h',data[11])[0]<200, 'GAME OVER did not move left'
            verify(data[12:16],'plane',visible=False)
            assert 200<struct.unpack_from('<h',data[15])[0]<320, 'Next demo skipped the plane entry'
            verify(data[16:20],'areyouready')

    if pcm_build:
        # --mute does not consume PCM. Advance the hardware read pointer to
        # verify the stream continues at the right file offset across swaps.
        for scene,start,samples in (
                ('demo',boot+['run 15','press space','run 3','release space'],assets['flight-drums.pcm']),
                ('gameover',fixture+last+resume+['run 3'],assets['gameover.pcm'])):
            commands=start
            for page in range(1,8):
                commands += [f'poke xram:0xca06 0 {page%4}','run 2',
                    f'dump xram:0x{0xca08+((page+2)%4)*256:04x} 256']
            # OPL effects keep the demo's PCM drums unmixed, so every byte
            # can be compared to the ROM while the plane engine still runs.
            _,data=case(f'splash-preserves-pcm-file-{scene}',commands,
                        rom_args=('/opl2' if scene=='demo' else '/pcm',))
            for page,chunk in enumerate(data,3):
                assert chunk==samples[page*256:(page+1)*256], 'Splash changed the PCM file cursor'
