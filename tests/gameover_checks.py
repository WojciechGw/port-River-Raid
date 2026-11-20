"""Final-plane jingle triggers, sample timing and audio handover on the CPU."""
import hashlib
import json
import struct
from pathlib import Path
from emulator_checks import poke
from pcm_stream import Stream, snapshot


def follow_jingle(case, sym, name, commands, pcm, records, rom_args=()):
    """Snapshot each frame of a one-shot jingle: every queued page must match
    the ROM and the OPL registers must hold the records due at the sample
    clock (or the one before, when the clock just crossed a record)."""
    frames = len(pcm)*60//16000+8
    for _ in range(frames):
        commands = commands+snapshot(sym,0xca08,['dump xram:0xc900 256'])+['run 1']
    _, observed = case(name, commands, rom_args=rom_args)
    observed = observed[-4*frames:]
    stream = Stream()
    states = [bytearray(256)]
    starts = [0]
    for record in records:
        state = bytearray(states[-1])
        for reg, value in record['writes']:
            state[reg] = value
        states.append(state)
        starts.append(starts[-1]+record['samples'])
    checked = 0
    for written, consumed, ring, registers in zip(*[iter(observed)]*4):
        if not stream.add(written, consumed, ring):
            break               # The jingle ended and flight music restarted.
        due = sum(1 for start in starts[:-1] if start <= stream.consumed)
        assert registers in (states[due], states[due-1]), f'{name}: OPL differs at sample {stream.consumed}'
        checked += 1
    pages = stream.contiguous()
    # The first snapshot can follow the start by a few frames.
    assert pages[0] <= 8 and pages[-1] == len(pcm)//256-1, f'{name}: jingle pages {pages[0]}..{pages[-1]}'
    for page in pages:
        assert stream.pages[page] == pcm[page*256:(page+1)*256], f'{name}: PCM differs at page {page}'
    return checked


def run_gameover_checks(case, sym, fixture, resume, boot, build, assets):
    from gameover_delay_checks import run_gameover_delay_checks
    run_gameover_delay_checks(case,sym,fixture,resume,True)
    root = Path(__file__).resolve().parents[1]
    score = json.loads((root/'src/gameover-score.json').read_text())
    pcm = (root/'assets/gameover.pcm').read_bytes()
    assert hashlib.sha256(pcm).hexdigest() == score['pcm_sha256']
    # The ROM holds the unsigned copy the PCM: device plays.
    pcm = bytes(b ^ 0x80 for b in pcm)
    assert assets['gameover.pcm'] == pcm
    assert score['bpm'] == 200 and len(pcm) == score['samples'] == 107264
    active = f'peek 0x{sym["gameover_active"]:04x}'
    started = f'peek 0x{sym["gameover_started"]:04x}'
    kind = f'peek 0x{sym["jingle_kind"]:04x}'
    begin = [f'wait 0x{sym["demo_splash_gameover_phase"]:04x} 1 60','run 2']
    last = [poke(0xc0,sym['rr_Copyright0']&255), poke(0xb3,4)]
    for backend in ('opl2','pcm'):
        case(f'gameover-final-plane-{backend}',fixture+last+resume+begin+[
            active+' 1',started+' 1','run 20',active+' 1',started+' 1'],
            rom_args=('/'+backend,))
    case('gameover-ordinary-loss',fixture+[poke(0xb3,4)]+resume+[
        active+' 1',kind+' 2',started+' 0','run 30',started+' 0'])
    case('gameover-muted-loss',fixture+[poke(sym['audio_muted'],1)]+last+resume+[
        active+' 0',started+' 0'])
    for pilot in (0,1):
        for lives in (8,24):
            case(f'gameover-game2-survivor-p{pilot+1}-{lives//8}',fixture+[
                poke(0x80,1),poke(0xf4,pilot),poke(0xc5,lives)]+last+resume+[
                    active+' 1',kind+' 2',started+' 0','run 100',active+' 1',kind+' 2',started+' 0'])
        case(f'gameover-game2-last-p{pilot+1}',fixture+[poke(0x80,1),poke(0xf4,pilot),
            poke(0xc5,sym['rr_Copyright0']&255)]+last+resume+begin+[active+' 1',started+' 1',
                'run 100',active+' 1',started+' 1'])

    # The PCM: device clocks the jingle in real time, also under --mute.
    # This checks each queued page, variable note lengths and the final tail.
    follow_jingle(case, sym, 'gameover-complete-score-and-pcm', fixture+last+resume+begin,
                  pcm, score['records'])
    case('gameover-complete-returns-to-flight', fixture+last+resume+begin+[
        f'run {len(pcm)*60//16000+20}', active+' 1', kind+' 2', started+' 1',
        'run 30', started+' 1'])

    for name, action in (('mute',['press f9']),('pause',['press p']),('restart',['press r']),
                         ('backend',['press f10']),('mode',['press f2'])):
        case(f'gameover-cancel-{name}',fixture+last+resume+begin+[active+' 1']+action+[
            'run 3',action[0].replace('press ','release '),'run 4',
            active+(' 0' if name in ('mute','pause') else ' 1')]+([kind+' 2'] if name not in ('mute','pause') else []))

    case('gameover-cancel-help',fixture+last+resume+begin+[active+' 1','press f1',
        'wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5',
        active+' 0','press space','run 3',
        'release space','wait xram:0x0080 82 320','run 3',active+' 1',kind+' 2'])

    duo = boot + ['press f2','run 3','release f2','run 3']*2 + ['run 5',
        'press space','run 136','release space','run 4',
        'press p','run 3','release p','run 3',poke(0xa0,[255]*6),poke(0x8e,[0]*6),
        poke(0x8b,[0,0]),poke(0xc6,0),poke(0xf8,[0]*4),
        poke(sym['duo_bridge'],0),poke(sym['duo_over'],0),poke(sym['duo_gap'],[0,0]),
        poke(sym['river1'],[0]*192),poke(sym['river2'],[0]*192),
        poke(sym['player_outer_left'],[16]*192),poke(sym['player_outer_right'],[144]*192),
        poke(sym['player_island_left'],[0]*192),poke(sym['player_island_right'],[0]*192),
        'press down s']
    players = sym['duo_players']
    for pilot in (0,1):
        base = players+pilot*23
        duo += [poke(base,[180,60+pilot*30,0,0,128,0]),
                poke(base+6,struct.pack('<H',sym['rr_JetStraight']-1)),
                poke(base+8,[8,255,0,0,65+pilot*30]+[88]*5+[0,1,0,68+pilot*16,106])]
    duo += ['run 2']
    for pilot in (0,1):
        base, other = players+pilot*23, players+(pilot^1)*23
        case(f'gameover-duo-survivor-p{pilot+1}',duo+[poke(base+4,[0,0])]+resume+[
            active+' 1',kind+' 2',started+' 0'])
        case(f'gameover-duo-last-p{pilot+1}',duo+[
            poke(other+8,0),poke(other+19,[0,0]),poke(base+4,[0,0])]+resume+begin+[
            active+' 1',started+' 1','run 40',active+' 1',started+' 1'])
    case('gameover-duo-simultaneous',duo+[
        poke(players+4,[0,0]),poke(players+27,[0,0])]+resume+begin+[active+' 1',started+' 1'])
    case('gameover-duo-reserves-remain',duo+[poke(players+8,16),poke(players+31,16),
        poke(players+4,[0,0]),poke(players+27,[0,0])]+resume+[active+' 1',kind+' 2',started+' 0'])
