"""Cover-only OPL2 playback, complete score timing, looping and handover."""
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
    assert assets['intro.bin'][512:] == data
    assert len(assets['intro.bin']) <= 512 + 0xf00
    assert 30*60 < score['frames'] < 33*60
    active = f'0x{sym["intro_active"]:04x}'
    cursor = f'0x{sym["intro_cursor"]:04x}'

    # Read every display frame, including the wrap. Compare all 256 registers
    # against the ordered score, not merely whether some note is playing.
    count = score['frames'] + 120
    commands = ['wait xram:0x00b0 2 180', f'peek {active} 1']
    for _ in range(count):
        commands += ['dump xram:0x0100 256', 'run 1']
    commands += ['peek xram:0x00b0 2', f'peek {active} 1']
    _, observed = case('intro-complete-score-and-loop', commands, gameplay=False)
    register_file = bytearray(256)
    expected = []
    cycle = list(frames(data))
    assert len(cycle) == score['frames']
    for writes in cycle*2:
        for reg, value in writes:
            register_file[reg] = value
        expected.append(bytes(register_file))
    offsets = [i for i in range(60, 70) if expected[i:i+count] == observed]
    assert offsets, 'Cover music loses/reorders note writes or drifts at loop'
    (output/'intro-timing.json').write_text(json.dumps(dict(
        frames_checked=count, initial_frame=offsets[0], loop_frames=len(cycle))))

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
