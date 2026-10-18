"""Final-plane jingle triggers, sample timing and audio handover on the CPU."""
import hashlib
import json
import struct
from pathlib import Path
from emulator_checks import poke


def run_gameover_checks(case, sym, fixture, resume, boot, build, assets):
    root = Path(__file__).resolve().parents[1]
    score = json.loads((root/'src/gameover-score.json').read_text())
    pcm = (root/'assets/gameover.pcm').read_bytes()
    assert assets['gameover.pcm'] == pcm
    assert hashlib.sha256(pcm).hexdigest() == score['pcm_sha256']
    assert score['bpm'] == 200 and len(pcm) == score['samples'] == 107264
    active = f'peek 0x{sym["gameover_active"]:04x}'
    started = f'peek 0x{sym["gameover_started"]:04x}'
    last = [poke(0xc0,sym['rr_Copyright0']&255), poke(0xb3,4)]
    for backend in ('psg','opl2','pcm'):
        case(f'gameover-final-plane-{backend}',fixture+last+resume+[
            active+' 1',started+' 1','run 20',active+' 1',started+' 1'],
            rom_args=('/'+backend,))
    case('gameover-ordinary-loss',fixture+[poke(0xb3,4)]+resume+[
        active+' 0',started+' 0','run 30',started+' 0'])
    case('gameover-muted-loss',fixture+[poke(sym['audio_muted'],1)]+last+resume+[
        active+' 0',started+' 0'])
    for pilot in (0,1):
        for lives in (8,24):
            case(f'gameover-game2-survivor-p{pilot+1}-{lives//8}',fixture+[
                poke(0x80,1),poke(0xf4,pilot),poke(0xc5,lives)]+last+resume+[
                    active+' 0',started+' 0','run 100',active+' 0',started+' 0'])
        case(f'gameover-game2-last-p{pilot+1}',fixture+[poke(0x80,1),poke(0xf4,pilot),
            poke(0xc5,sym['rr_Copyright0']&255)]+last+resume+[active+' 1',started+' 1',
                'run 100',active+' 1',started+' 1'])

    # Drive the hardware sample clock; --mute does not consume the PCM ring.
    # This checks each streamed page, variable note lengths and the final tail.
    commands = fixture+last+resume+['dump xram:0xc008 768']
    for page in range(1,len(pcm)//256):
        # Let the gameplay render/audio phase finish before sampling a newly
        # published page; a single VSYNC can stop before that frame's refill.
        commands += [f'poke xram:0xc006 0 {page%4}', 'run 2',
                     'dump xram:0xc900 256']
        if page+2 < len(pcm)//256:
            commands += [f'dump xram:0x{0xc008+((page+2)%4)*256:04x} 256']
    commands += [f'poke xram:0xc006 0 {(len(pcm)//256)%4}', 'run 2',
                 active+' 0',started+' 1','run 30',started+' 1']
    _, data = case('gameover-complete-score-and-pcm',commands)
    assert data.pop(0) == pcm[:768]
    expected = bytearray(256)
    record_index, end = 0, 0
    for page in range(1,len(pcm)//256):
        while page*256 >= end:
            record = score['records'][record_index]
            for reg,value in record['writes']:
                expected[reg] = value
            end += record['samples']
            record_index += 1
        assert data.pop(0) == expected, f'OPL score differs at page {page}'
        if page+2 < len(pcm)//256:
            chunk = data.pop(0)
            assert chunk == pcm[(page+2)*256:(page+3)*256], f'PCM differs at page {page}'
    assert not data

    for name, action in (('mute',['press f9']),('pause',['press p']),('restart',['press r']),
                         ('backend',['press f10']),('mode',['press f2'])):
        case(f'gameover-cancel-{name}',fixture+last+resume+[active+' 1']+action+[
            'run 3',active+' 0'])

    case('gameover-cancel-help',fixture+last+resume+[active+' 1','press f1',
        'wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5',
        active+' 0','press space','run 3',
        'release space','wait xram:0x0080 82 240','run 3',active+' 0'])

    duo = boot + ['press f2','run 3','release f2','run 3']*2 + ['run 5',
        'press space','run 140','release space','run 4',
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
            active+' 0',started+' 0'])
        case(f'gameover-duo-last-p{pilot+1}',duo+[
            poke(other+8,0),poke(other+19,[0,0]),poke(base+4,[0,0])]+resume+[
            active+' 1',started+' 1','run 40',active+' 1',started+' 1'])
    case('gameover-duo-simultaneous',duo+[
        poke(players+4,[0,0]),poke(players+27,[0,0])]+resume+[active+' 1',started+' 1'])
    case('gameover-duo-reserves-remain',duo+[poke(players+8,16),poke(players+31,16),
        poke(players+4,[0,0]),poke(players+27,[0,0])]+resume+[active+' 0',started+' 0'])
