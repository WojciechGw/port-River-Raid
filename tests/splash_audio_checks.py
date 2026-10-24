"""Departure engine, actual OPL routing, PCM mixing and interruption."""
from emulator_checks import poke


def run_splash_audio_checks(case,sym,boot,pcm_build):
    tap=['press f9','run 3','release f9','run 3']
    done=f'0x{sym["demo_splash_done"]:04x}'
    sample=[f'dump 0x{sym["pcm_amplitude"]:04x} 2',
            'dump xram:0xc000 256','dump xram:0xc900 256']
    variants=[('opl2',[],('/opl2',),False)]
    if pcm_build:
        variants += [('pcm',[],('/pcm',),True),
                     ('legacy-opl2',[poke(sym['music_pcm_probe'],[0xa9,0xff,0xaa,0x60])],('/opl2',),False)]
    for name,prefix,args,pcm in variants:
        for presses,mode in enumerate((0,1,3)):
            # --mute does not consume PCM in the emulator. Model firmware
            # reads at the active ring's sample rate, as in music_checks.py.
            def consume(first,count):
                if not pcm: return [f'run {count}']
                address,rate,size=(0xca06,16000,1024) if not mode else (0xc006,8000,2048)
                commands=[]
                for frame in range(first,first+count):
                    read=(frame*rate//60)%size
                    commands += [f'poke xram:0x{address:04x} {read&255} {read>>8}','run 1']
                return commands
            commands=prefix+boot+['run 15']+tap*presses+sample+[
                'press space','run 3','release space']+consume(1,8)+sample
            if pcm:
                commands += ['dump xram:0xc008 2048']
                if not mode:
                    commands += [f'dump 0x{sym["music_fx_read"]:04x} 2']+consume(9,5)+[
                                 f'dump 0x{sym["music_fx_read"]:04x} 2']
            commands += [f'wait {done} 1 60','run 4']+sample
            _,data=case(f'splash-engine-{name}-f9-{mode}',commands,rom_args=args)
            assert not any(data[0]) and not any(data[-3]), 'Engine outside departure'
            assert bool(data[3][0])==(mode!=3) and not data[3][1], 'Missing engine or stray demo effect'
            if pcm:
                assert bool(any(data[6]))==(mode!=3), 'PCM engine samples missing or muted incorrectly'
                if not mode: assert data[7]!=data[8], 'Engine not mixed into PCM music'
            else:
                source=data[4]
                assert all(bool(source[0xb0+n]&32)==(mode!=3) for n in range(4))
                assert not any(source[0xb0+n]&32 for n in range(4,9)), 'Non-engine demo effect leaked'
                if not mode:
                    voice=3 if pcm_build and name=='opl2' else 6
                    assert data[5][0xb0+voice]&32, 'Engine never reached the active music synth'
                    assert not data[-1][0xb0+voice]&32, 'Engine stuck after departure'

        opening=['press f1','wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5']
        closing=['press z','run 3','release z','wait xram:0x0080 82 320','run 3']
        commands=prefix+boot+['run 15','press space','run 3','release space','run 3',
            'press p','run 3','release p','run 3']+sample+opening+closing+sample+[
            'press p','run 3','release p','run 3']+sample+[
            'press f2','run 3','release f2','run 8']+sample
        _,data=case(f'splash-engine-{name}-pause-help-cancel',commands,rom_args=args)
        assert not any(data[0]) and not any(data[3]), 'Engine survived pause/help'
        assert data[6][0] and not any(data[9]), 'Engine did not resume/stop on F2'
        if not pcm:
            voice=3 if pcm_build and name=='opl2' else 6
            assert data[8][0xb0+voice]&32 and not data[11][0xb0+voice]&32, 'OPL engine stuck after F2'
