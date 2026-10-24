"""Main OPL2 + PCM playback across screens/demo, exact clock and handover."""
import hashlib
import json
import sys
from pathlib import Path


def run_intro_checks(case, sym, boot, output, build, assets):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root/'tools'))
    from make_intro import compile_score
    from preview_intro import frames
    score = json.loads((root/'src/intro-score.json').read_text())
    data = compile_score(score)
    assert (build/'intro-score.bin').read_bytes() == data
    assert assets['intro.bin'][1536:] == data
    assert len(assets['intro.bin']) <= 1536 + 0x700
    assert assets['intro-score.bin'] == data
    drums = (root/'assets/intro-drums.pcm').read_bytes()
    assert assets['intro-drums.pcm'] == drums
    assert hashlib.sha256(drums).hexdigest() == score['drum_sha256']
    assert score['samples_per_step'] == 1712 and score['steps'] == 128
    assert len(drums) == 219136
    active = f'0x{sym["intro_active"]:04x}'
    cursor = f'0x{sym["intro_cursor"]:04x}'
    running = f'0x{sym["gameover_active"]:04x}'
    kind = f'0x{sym["jingle_kind"]:04x}'

    # --mute does not consume PCM. Advance its read pointer by complete pages
    # and check every streamed byte, including the fill and loop boundary.
    register_file = bytearray(256)
    expected = []
    cycle = list(frames(data))
    assert len(cycle) == score['steps']
    for writes in cycle:
        for reg, value in writes:
            register_file[reg] = value
        expected.append(bytes(register_file))
    count = len(drums)//256 + 24
    commands = ['wait xram:0x00b0 2 180', f'peek {active} 1',
                'dump xram:0x09f8 8','dump xram:0x0a00 768']
    for page in range(1,count+1):
        commands += [f'poke xram:0x09fe 0 {page%4}', 'run 1',
                     'dump xram:0x0100 256',
                     f'dump xram:0x{0x0a00+((page+2)%4)*256:04x} 256']
    commands += ['peek xram:0x00b0 2', f'peek {active} 1']
    _, observed = case('intro-complete-score-and-loop', commands, gameplay=False)
    assert observed[0] == bytes((0,3,3,10,0x80,0x3e,0,0))
    assert observed[1] == drums[:768]
    for page in range(1,count+1):
        registers, chunk = observed[page*2:page*2+2]
        step = (page*256//score['samples_per_step']) % score['steps']
        assert registers == expected[step], f'OPL score differs at PCM page {page}, step {step}'
        offset = ((page+2)*256) % len(drums)
        assert chunk == drums[offset:offset+256], f'PCM differs at page {page}'
    (output/'intro-timing.json').write_text(json.dumps(dict(
        pages_checked=count, samples_per_step=1712, loop_samples=len(drums))))

    commands = ['wait xram:0x00b0 2 180']
    for frame in range(1,901):
        read = (frame*16000//60) % 1024
        commands += [f'poke xram:0x09fe {read&255} {read>>8}', 'run 1',
                     'dump xram:0x0100 256', 'dump xram:0x09f8 2']
    _, observed = case('intro-16000-hz-clock', commands, gameplay=False)
    for frame in range(1,901):
        consumed = frame*16000//60
        registers, write = observed[(frame-1)*2:frame*2]
        assert registers == expected[(consumed//1712)%128], f'OPL clock drift at frame {frame}'
        queued = (int.from_bytes(write,'little')-consumed)%1024
        assert 512 < queued <= 768, f'PCM underrun at frame {frame}'

    for mode, backend in (('opl2', 2), ('pcm', 3)):
        commands = ['wait xram:0x00b0 2 180', 'run 100', f'peek {active} 1',
            'dump xram:0x0100 256', 'press z', 'wait xram:0x00b0 3 3',
            f'peek {active} 1', 'wait xram:0x00b0 4 90', 'run 2', f'peek {active} 1',
            'release z', 'wait xram:0x00b4 2 120', 'wait xram:0x00b0 2 90',
            f'peek {active} 1', f'dump {cursor} 2']
        for page in range(1,33):
            commands += [f'poke xram:0x09fe 0 {page%4}','run 1']
        commands += [f'dump {cursor} 2',
            'press z', 'run 3', 'release z', 'wait xram:0x0080 82 240',
            f'wait 0x{sym["ready"]:04x} 2 180',
            f'peek 0x{sym["audio_backend"]:04x} {backend}',
            'run 3',f'peek {running} 1',f'peek {kind} 2',
            'press space', 'run 140', 'release space', 'run 4',
            'peek xram:0x0082 1',f'peek {running} 1',f'peek {kind} 2',
            f'peek 0x{sym["pcm_enabled"]:04x} {int(backend==3)}',
            f'dump 0x{sym["pcm_amplitude"]:04x} 2']
        _, snapshots = case(f'intro-handover-{mode}', commands, rom_args=('/'+mode,))
        registers, before, after, amplitude = snapshots
        assert any(registers[0xb0+n]&32 for n in range(9))
        assert before != after, 'Music does not advance on the manual'
        assert any(amplitude), 'Gameplay audio remains silent after intro'

    # F1 loads the overlay again during gameplay. Saved palette/video at
    # $F100..$F8FF must survive; the music score is above this backup.
    commands = boot + ['press space', 'run 140', 'release space', 'run 4',
        'press p', 'run 3', 'release p', 'run 3', 'mark',
        'dump xram:0x0100 32', 'press f1', 'run 3', 'release f1',
        'wait xram:0x00b0 2 120', 'wait xram:0x02a4 222 5', f'peek {active} 1',
        'press z', 'run 3', 'release z', 'wait xram:0x0080 82 240',
        'run 3', 'expect-same', 'dump xram:0x0100 32']
    _, palettes = case('intro-f1-preserves-game', commands)
    assert palettes[0] == palettes[1], 'Intro overlay damaged saved game colors'

    # The runtime player shares the jingle ring but decodes the main score.
    flight_expected=[]
    register_file=bytearray(256)
    for writes in frames(assets['flight-score.bin']):
        for reg,value in writes: register_file[reg]=value
        flight_expected.append(bytes(register_file))
    flight_drums=assets['flight-drums.pcm']
    commands=boot+['run 3',f'peek {running} 1',f'peek {kind} 2',
                  'dump xram:0xca08 768']
    for page in range(1,count+1):
        commands += [f'poke xram:0xca06 0 {page%4}','run 2',
            'dump xram:0xc900 256',f'dump xram:0x{0xca08+((page+2)%4)*256:04x} 256']
    _,observed=case('intro-demo-complete-score-and-loop',commands)
    assert observed[0]==flight_drums[:768]
    for page in range(1,count+1):
        registers,chunk=observed[page*2-1:page*2+1]
        assert registers==flight_expected[(page*256//1712)%128], f'Demo score at page {page}'
        offset=((page+2)*256)%len(flight_drums)
        assert chunk==flight_drums[offset:offset+256], f'Demo PCM at page {page}'

    # Feed the runtime ring at its real sample rate, including two-page refills.
    commands=boot+['run 3']
    for frame in range(1,901):
        read=(frame*16000//60)%1024
        commands += [f'poke xram:0xca06 {read&255} {read>>8}','run 1',
                     'dump xram:0xc900 256','dump xram:0xca00 2']
    _,observed=case('intro-demo-16000-hz-clock',commands)
    for frame in range(1,901):
        consumed=frame*16000//60
        registers,write=observed[(frame-1)*2:frame*2]
        # Script snapshots can precede this frame's main-loop audio update.
        steps=(consumed//1712,((frame-1)*16000//60)//1712)
        assert registers in [flight_expected[step%128] for step in steps], f'Demo clock drift at frame {frame}'
        queued=(int.from_bytes(write,'little')-consumed)%1024
        assert 256 < queued <= 768, f'Demo PCM underrun at frame {frame}'

    case('intro-demo-mute-and-mode',boot+['run 3',f'peek {kind} 2',
        'press f9','run 3','release f9','run 3',f'peek {running} 0',
        'press f9','run 3','release f9','run 3',f'peek {running} 1',
        'press f2','run 3','release f2','run 8',f'peek {running} 1',f'peek {kind} 2'])

    gain=f'0x{sym["intro_gain"]:04x}'
    for screen in ('outro','f1','initial-manual'):
        if screen == 'initial-manual':
            commands=['wait xram:0x00b0 2 180','press z',
                'wait xram:0x00b0 4 90','release z',
                'wait xram:0x00b4 2 120','wait xram:0x00b0 2 90',
                'wait xram:0x02a4 222 5',f'peek {active} 1',
                f'peek {gain} 63','press z']
        else:
            commands=boot+['press '+('escape' if screen=='outro' else 'f1'),
                'wait xram:0x00b0 2 120',f'peek {active} 1']
        if screen == 'f1':
            commands += ['release f1','wait xram:0x02a4 222 5','press z']
        commands += ['wait xram:0x00b0 3 200']
        levels=list(range(63,1,-4))
        for page,level in enumerate(levels,1):
            commands += [f'wait xram:0x00b1 {level} 6',
                f'poke xram:0x09fe 0 {page%4}',
                f'wait xram:0x09f9 {(page+3)%4} 4',
                f'dump 0x{sym["intro_pcm_gain"]:04x} 1',
                f'dump xram:0x{0x0a00+((page+2)%4)*256:04x} 256',
                f'dump {gain} 1','dump xram:0x0100 256']
        commands += ['wait xram:0x00b1 0 3','dump xram:0x0140 32']
        if screen == 'outro':
            commands += ['expect-exit 0 5']
        else:
            # Reopening F1 must restore full intro volume after reaching silence.
            commands += ['release z','wait xram:0x0080 82 240',
                f'wait 0x{sym["ready"]:04x} 2 180','run 4',
                'press f1','wait xram:0x00b0 2 120',f'peek {gain} 63']
        _,observed=case(f'intro-{screen}-opl-and-pcm-fade',commands,gameplay=False)
        slots=(0,1,2,8,9,10,16,17,18)
        for page in range(1,len(levels)+1):
            before,chunk,after,registers=observed[(page-1)*4:page*4]
            source=drums[(page+2)*256:(page+3)*256]
            scaled=bytes(((v if v<128 else v-256)*before[0]//64)&255 for v in source)
            assert chunk==(source if before[0]==63 else scaled), f'{screen} PCM gain page {page}'
            normal=expected[(page*256//1712)%128]
            for ch,slot in enumerate(slots):
                if normal[0xb0+ch]&32:
                    assert registers[0x43+slot]==min(63,normal[0x43+slot]+63-after[0])
        assert all(observed[-1][3+slot]==63 for slot in slots), f'{screen} did not reach silence'

    case('intro-muted-help-and-exit',boot+[
        'press f9','run 3','release f9','run 3',f'peek {running} 0',
        'press f1','wait xram:0x00b0 2 120','release f1',
        'wait xram:0x02a4 222 5',f'peek {active} 0',
        'press z','run 3','release z','wait xram:0x0080 82 240','run 3',
        'press escape','wait xram:0x00b0 2 120',f'peek {active} 0','expect-exit 0 260'],
        gameplay=False)
