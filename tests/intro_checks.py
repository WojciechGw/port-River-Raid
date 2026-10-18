"""Cover OPL2 + PCM playback, exact sample clock, looping and handover."""
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
    assert len(assets['intro.bin']) <= 1536 + 0xf00
    drums = (root/'assets/intro-drums.pcm').read_bytes()
    assert assets['intro-drums.pcm'] == drums
    assert hashlib.sha256(drums).hexdigest() == score['drum_sha256']
    assert score['samples_per_step'] == 1712 and score['steps'] == 128
    assert len(drums) == 219136
    active = f'0x{sym["intro_active"]:04x}'
    cursor = f'0x{sym["intro_cursor"]:04x}'

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

    for mode, backend in (('psg', 1), ('opl2', 2), ('pcm', 3)):
        commands = ['wait xram:0x00b0 2 180', 'run 100', f'peek {active} 1',
            'dump xram:0x0100 256', 'press z', 'wait xram:0x00b0 3 3',
            f'peek {active} 1', 'wait xram:0x00b0 4 90', 'run 2', f'peek {active} 0',
            'release z', 'wait xram:0x00b4 2 120', 'wait xram:0x00b0 2 90',
            f'peek {active} 0', f'dump {cursor} 2', 'run 90', f'dump {cursor} 2',
            'press z', 'run 3', 'release z', 'wait xram:0x0080 82 240',
            f'wait 0x{sym["ready"]:04x} 2 180',
            f'peek 0x{sym["audio_backend"]:04x} {backend}',
            f'peek 0x{sym["pcm_enabled"]:04x} {int(backend==3)}',
            'press space', 'run 140', 'release space', 'run 4',
            'peek xram:0x0082 1', f'dump 0x{sym["pcm_amplitude"]:04x} 2']
        _, snapshots = case(f'intro-handover-{mode}', commands, rom_args=('/'+mode,))
        registers, before, after, amplitude = snapshots
        assert any(registers[0xb0+n]&32 for n in range(9))
        assert before == after, 'Music restarts on the manual'
        assert any(amplitude), 'Gameplay audio remains silent after intro'

    # F1 loads the overlay again during gameplay. Saved palette/video at
    # $F100..$F8FF must survive; this is also the startup score's address.
    commands = boot + ['press space', 'run 140', 'release space', 'run 4',
        'press p', 'run 3', 'release p', 'run 3', 'mark',
        'dump xram:0x0100 32', 'press f1', 'run 3', 'release f1',
        'wait xram:0x00b0 2 120', 'wait xram:0x02a4 222 5', f'peek {active} 0',
        'press z', 'run 3', 'release z', 'wait xram:0x0080 82 240',
        'run 3', 'expect-same', 'dump xram:0x0100 32']
    _, palettes = case('intro-f1-preserves-game', commands)
    assert palettes[0] == palettes[1], 'Intro overlay damaged saved game colors'
