"""Main OPL2 + PCM playback across screens/demo, exact clock and handover."""
import hashlib
import json
import sys
from pathlib import Path
from pcm_stream import Stream, snapshot


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
    assert hashlib.sha256(drums).hexdigest() == score['drum_sha256']
    # The ROM holds the unsigned copy the PCM: device plays.
    drums = bytes(b ^ 0x80 for b in drums)
    assert assets['intro-drums.pcm'] == drums
    assert score['samples_per_step'] == 1712 and score['steps'] == 128
    assert len(drums) == 219136
    active = f'0x{sym["intro_active"]:04x}'
    cursor = f'0x{sym["intro_cursor"]:04x}'
    running = f'0x{sym["gameover_active"]:04x}'
    kind = f'0x{sym["jingle_kind"]:04x}'

    # The PCM: device consumes in real time, also under --mute. Snapshot every
    # frame and check every queued byte, including the fill and loop boundary,
    # and the OPL registers at the sequencer's sample clock.
    register_file = bytearray(256)
    expected = []
    cycle = list(frames(data))
    assert len(cycle) == score['steps']
    for writes in cycle:
        for reg, value in writes:
            register_file[reg] = value
        expected.append(bytes(register_file))
    count = len(drums)//256 + 24

    def follow(name, start, ring, registers, frames_, rom_args=(), gameplay=False):
        commands = start[:]
        for _ in range(frames_):
            commands += snapshot(sym, ring, [f'dump xram:0x{registers:04x} 256']) + ['run 1']
        _, observed = case(name, commands, gameplay=gameplay, rom_args=rom_args)
        stream, snaps = Stream(), []
        for written, consumed, chunk, regs in zip(*[iter(observed[-4*frames_:])]*4):
            assert stream.add(written, consumed, chunk), f'{name}: stream restarted'
            snaps.append((stream.consumed, stream.queued(), regs))
        return stream, snaps

    stream, snaps = follow('intro-complete-score-and-loop',
        ['wait xram:0x00b0 2 180', f'peek {active} 1'], 0x0a00, 0x0100, count*256*60//16000+8)
    pages = stream.contiguous()
    assert pages[-1] >= count, 'Intro stream did not cross its loop'
    for page in pages:
        offset = (page*256) % len(drums)
        assert stream.pages[page] == drums[offset:offset+256], f'PCM differs at page {page}'
    for frame, (consumed, queued, registers) in enumerate(snaps):
        step = (consumed//score['samples_per_step']) % score['steps']
        assert registers == expected[step], f'OPL score differs at frame {frame}, step {step}'
    (output/'intro-timing.json').write_text(json.dumps(dict(
        pages_checked=len(pages), samples_per_step=1712, loop_samples=len(drums))))

    stream, snaps = follow('intro-16000-hz-clock', ['wait xram:0x00b0 2 180'], 0x0a00, 0x0100, 900)
    for frame, (consumed, queued, registers) in enumerate(snaps):
        assert registers == expected[(consumed//1712)%128], f'OPL clock drift at frame {frame}'
        assert 768 <= queued <= 1024+64, f'PCM underrun at frame {frame}'
    played = snaps[-1][0]-snaps[0][0]
    assert abs(played-899*16000//60) <= 512, 'Intro stream is not clocked at 16 kHz'

    for mode, backend in (('opl2', 2), ('pcm', 3)):
        commands = ['wait xram:0x00b0 2 180', 'run 100', f'peek {active} 1',
            'dump xram:0x0100 256', 'press z', 'wait xram:0x00b0 3 3',
            f'peek {active} 1', 'wait xram:0x00b0 4 90', 'run 2', f'peek {active} 1',
            'release z', 'wait xram:0x00b4 2 120', 'wait xram:0x00b0 2 90',
            f'peek {active} 1', f'dump {cursor} 2']
        commands += ['run 32', f'dump {cursor} 2',
            'press z', 'run 3', 'release z', 'wait xram:0x0080 82 320',
            f'wait 0x{sym["ready"]:04x} 2 180',
            f'peek 0x{sym["audio_backend"]:04x} {backend}',
            'run 3',f'peek {running} 1',f'peek {kind} 2',
            'press space', 'run 136', 'release space', 'run 4',
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
    commands = boot + ['press space', 'run 136', 'release space', 'run 4',
        'press p', 'run 3', 'release p', 'run 3', 'mark',
        'dump xram:0x0100 32', 'press f1', 'run 3', 'release f1',
        'wait xram:0x00b0 2 120', 'wait xram:0x02a4 222 5', f'peek {active} 1',
        'press z', 'run 3', 'release z', 'wait xram:0x0080 82 320',
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
    # Hybrid flight music leaves voices 3/4/7/8 to the effects, which
    # _music_effects copies over them every frame with OPL2 effects.
    slots=(0,1,2,8,9,10,16,17,18)
    effect_regs={base+slots[ch]+op for ch in (3,4,7,8) for op in (0,3)
                 for base in (0x20,0x40,0x60,0x80,0xe0)}|{
                 base+ch for ch in (3,4,7,8) for base in (0xa0,0xb0,0xc0)}

    def music(registers):
        return bytes(0 if reg in effect_regs else value for reg,value in enumerate(registers))

    flight_expected=[music(registers) for registers in flight_expected]
    stream, snaps = follow('intro-demo-complete-score-and-loop',
        boot+['run 3',f'peek {running} 1',f'peek {kind} 2'], 0xca08, 0xc900,
        count*256*60//16000+8, gameplay=True)
    pages = stream.contiguous()
    assert pages[-1] >= count, 'Demo stream did not cross its loop'
    for page in pages:
        offset=(page*256)%len(flight_drums)
        assert stream.pages[page]==flight_drums[offset:offset+256], f'Demo PCM at page {page}'
    for frame,(consumed,queued,registers) in enumerate(snaps):
        assert music(registers)==flight_expected[(consumed//1712)%128], f'Demo score at frame {frame}'

    stream, snaps = follow('intro-demo-16000-hz-clock', boot+['run 3'], 0xca08, 0xc900, 900,
                           gameplay=True)
    for frame,(consumed,queued,registers) in enumerate(snaps):
        assert music(registers)==flight_expected[(consumed//1712)%128], f'Demo clock drift at frame {frame}'
        assert 768 <= queued <= 1024+64, f'Demo PCM underrun at frame {frame}'
    played = snaps[-1][0]-snaps[0][0]
    assert abs(played-899*16000//60) <= 512, 'Demo stream is not clocked at 16 kHz'

    case('intro-demo-mute-and-mode',boot+['run 3',f'peek {kind} 2',
        'press f9','run 3','release f9','run 3',f'peek {running} 0',
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
        for level in levels:
            commands += [f'wait xram:0x00b1 {level} 6',
                f'dump 0x{sym["intro_pcm_gain"]:04x} 1']+snapshot(sym,0x0a00,[
                f'dump {gain} 1','dump xram:0x0100 256'])
        commands += ['wait xram:0x00b1 0 3','dump xram:0x0140 32']
        if screen == 'outro':
            commands += ['expect-exit 0 5']
        else:
            # Reopening F1 must restore full intro volume after reaching silence.
            commands += ['release z','wait xram:0x0080 82 320',
                f'wait 0x{sym["ready"]:04x} 2 180','run 4',
                'press f1','wait xram:0x00b0 2 120',f'peek {gain} 63']
        _,observed=case(f'intro-{screen}-opl-and-pcm-fade',commands,gameplay=False)
        slots=(0,1,2,8,9,10,16,17,18)
        for index in range(len(levels)):
            before,written,consumed,ring,after,registers=observed[index*6:index*6+6]
            # The last queued page was scaled by the gain drum_fade recorded.
            page=int.from_bytes(written,'little')//256-1
            chunk=ring[(page%4)*256:(page%4+1)*256]
            offset=(page*256)%len(drums)
            source=drums[offset:offset+256]
            # A snapshot can stop the machine inside drum_fade, after it has
            # recorded the next page's gain: the fade moves one level a frame.
            scaled=[source if gain>=63 else bytes(((v-128)*gain//64+128)&255 for v in source)
                    for gain in (before[0],before[0]+1)]
            assert chunk in scaled, f'{screen} PCM gain page {page}'
            step=(int.from_bytes(consumed,'little')//1712)%128
            normal=expected[step]
            for ch,slot in enumerate(slots):
                if normal[0xb0+ch]&32:
                    assert registers[0x43+slot]==min(63,normal[0x43+slot]+63-after[0])
        assert all(observed[-1][3+slot]==63 for slot in slots), f'{screen} did not reach silence'

    case('intro-muted-help-and-exit',boot+[
        'press f9','run 3','release f9','run 3',f'peek {running} 0',
        'press f1','wait xram:0x00b0 2 120','release f1',
        'wait xram:0x02a4 222 5',f'peek {active} 0',
        'press z','run 3','release z','wait xram:0x0080 82 320','run 3',
        'press escape','wait xram:0x00b0 2 120',f'peek {active} 0','expect-exit 0 260'],
        gameplay=False)
