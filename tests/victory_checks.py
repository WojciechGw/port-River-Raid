"""Real bridge hits: milestone lives, correct section identity and full fanfare."""
import hashlib
import json
import struct
from pathlib import Path
from emulator_checks import poke


def run_victory_pcm_sequence_checks(case, sym, fixture, resume, assets):
    """Play complete PCM fanfares between hits in the same running game."""
    started = f'peek 0x{sym["victory_started"]:04x}'
    kind = f'peek 0x{sym["jingle_kind"]:04x}'
    active = f'peek 0x{sym["gameover_active"]:04x}'
    samples = len(assets['victory.pcm'])
    commands = fixture+resume+[f'peek 0x{sym["audio_backend"]:04x} 3']
    rewards = 0
    expected = []
    for number in range(1,51):
        commands += [poke(sym['tanks'],[0]*30),poke(0xa0,[0]*6),poke(0xa2,8),
            poke(0x96,4),poke(0x9c,0x37),poke(0xbd,number),poke(0x90,128),
            poke(0xb5,0),poke(0xb7,[255,255]),'press down',
            poke(0xb2,75),poke(0xf5,80)]
        # Avoid independent score-bonus lives while counting bridge awards.
        commands += [poke(0xcd+n*2,88 if n<5 else 0) for n in range(6)]
        commands += ['run 6','dump 0xa2 1']
        expected.append(tuple(bytes([frame]) for frame in range(4)))
        if number in (5,20,50):
            rewards += 1
        if number == 50:
            commands += [kind+' 1','dump xram:0xca08 768']
            expected.append((assets['victory.pcm'][:768],))
            # Match the 16 kHz consumer at 60 Hz, including the final partial
            # frame. Once the jingle ends the flight ring starts from zero.
            for frame in range(1,(samples*60+15999)//16000+1):
                read = min(samples,frame*16000//60)%1024
                commands += [f'poke xram:0xca06 {read&255} {read>>8}','run 1']
            commands += ['run 3','dump xram:0xf900 '+str(len(assets['flight-score.bin']))]
            expected.append((assets['flight-score.bin'],))
        commands += [active+' 1',kind+' 2',started+f' {int(number==50)}',
                     f'peek 0xc0 {24+8*rewards}']
    _,dumps = case('victory-pcm-bridges1-through50',commands,rom_args=('/pcm',))
    assert len(dumps) == len(expected)
    for index,(data,choices) in enumerate(zip(dumps,expected)):
        assert data in choices, f'Bridge destruction or music data differs at dump {index}'


def run_victory_progression_checks(case, sym, boot, image):
    """Keep one game alive after a milestone so stale fanfare state is visible."""
    active = f'peek 0x{sym["gameover_active"]:04x}'
    started = f'peek 0x{sym["victory_started"]:04x}'
    kind = f'peek 0x{sym["jingle_kind"]:04x}'
    collision = sym['collisions']
    pcm_build = 'victory.pcm' in dict(image.assets)
    for milestone in (5,20,50):
        commands = boot+[poke(sym['start_level'],milestone-1),
            'press space','run 136','release space','run 4']
        # Level 50 is the native difficulty limit; check progression after
        # the earlier milestones without crossing the native 50 -> 49 loop.
        for number in range(milestone, min(milestone+3,51)):
            # Generate real roads and advance the HUD through native code.
            # Disable collisions only during travel, restore before shooting.
            commands += [poke(collision,96),poke(0xe2,255),poke(0xe4,255),
                poke(0xe6,255),poke(0xe8,255),poke(0xb7,[255,255]),
                'release down','press up']
            commands += [f'wait 0xbd {number} 1500',
                'wait 0xa2 8 1500','release up','press down',poke(0xb5,0),
                poke(collision,image.data[collision]),f'peek 0xbd {number}',
                poke(0xb2,75),poke(0xf5,80),'run 6','peek 0xa2 1',
                'peek 0xc0 32',active+' 1',started+f' {int(number==50)}']
            commands += [kind+(' 1' if number == 50 else ' 2')]
        case(f'victory-natural-bridge{milestone}-progression',commands,
             rom_args=('/pcm',) if pcm_build else ())


def run_victory_checks(case, sym, fixture, resume, boot, assets, image):
    active = f'peek 0x{sym["gameover_active"]:04x}'
    started = f'peek 0x{sym["victory_started"]:04x}'
    kind = f'peek 0x{sym["jingle_kind"]:04x}'
    run_victory_progression_checks(case,sym,boot,image)
    run_victory_pcm_sequence_checks(case,sym,fixture,resume,assets)
    base = fixture + [poke(sym['tanks'],[0]*30),poke(0xa2,8),
        poke(0x96,4),poke(0x9c,0x37),poke(0xb5,0),'press down',
        poke(0xb2,75),poke(0xf5,80)]
    base += [poke(0xcd+n*2,88 if n<5 else 0) for n in range(6)]

    def bridge(number, advanced=False):
        # The reward follows BRIDGE on the HUD, even when scrolling has
        # already advanced it. Exercise both road colors for each HUD number.
        road_number = number-1 if advanced else number
        return [poke(0xbd,number),poke(0x90,128+(4 if road_number%2==0 else 0))]

    for variant,pilot in ((0,0),(1,0),(1,1)):
        for number in (5,20,50):
            for advanced in (False,True):
                case(f'victory-game{variant+1}-p{pilot+1}-{number}-{advanced}',
                    base+[poke(0x80,variant),poke(0xf4,pilot),poke(0xc5,24)]+
                    bridge(number,advanced)+resume+['peek 0xc0 32','peek 0xc5 24',
                    active+' 1',started+f' {int(number==50)}',kind+(' 1' if number==50 else ' 2'),'run 20',
                    'peek 0xc0 32',started+f' {int(number==50)}'])

    for number in (4,6,19,21,49):
        case(f'victory-no-bonus-bridge-{number}',base+bridge(number,True)+resume+[
            'peek 0xc0 24',active+' 1',kind+' 2',started+' 0'])
    case('victory-muted-still-awards',base+bridge(50)+[poke(sym['audio_muted'],1)]+
        resume+['peek 0xc0 32',active+' 0',started+' 0'])
    case('victory-classic-life-cap',base+bridge(50)+[poke(0xc0,72)]+resume+[
        'peek 0xc0 72',active+' 1',started+' 1'])
    case('victory-classic-last-plane',base+bridge(50)+[
        poke(0xc0,sym['rr_Copyright0']&255)]+resume+['peek 0xc0 8',started+' 1'])
    case('victory-no-shot-no-award',base+bridge(50)+[poke(0xb2,180)]+resume+[
        'run 20','peek 0xc0 24',started+' 0'])
    # 9,500 + 500 gives the independent score bonus as well as the bridge bonus.
    case('victory-score-and-bridge-bonuses',base+bridge(50)+[
        poke(0xd1,72),poke(0xd3,40)]+resume+['peek 0xc0 40',started+' 1'])

    root = Path(__file__).resolve().parents[1]
    score = json.loads((root/'src/victory-score.json').read_text())
    pcm = assets['victory.pcm']
    assert pcm == (root/'assets/victory.pcm').read_bytes()
    assert hashlib.sha256(pcm).hexdigest() == score['pcm_sha256']
    assert score['bpm']==96 and score['samples']==len(pcm)==186368
    # Two display frames per page make this clock test longer than real audio;
    # fill the tank so the flight survives the entire verification timeline.
    commands = base+bridge(50)+[poke(0xb7,[255,255])]+resume+['dump xram:0xca08 768']
    for page in range(1,len(pcm)//256):
        commands += [f'poke xram:0xca06 0 {page%4}','run 2','dump xram:0xc900 256']
        if page+2<len(pcm)//256:
            commands += [f'dump xram:0x{0xca08+((page+2)%4)*256:04x} 256']
    commands += [f'poke xram:0xca06 0 {(len(pcm)//256)%4}','run 3',active+' 1',kind+' 2',
                 started+' 1','peek 0xc0 32']
    _,data = case('victory-complete-score-and-pcm',commands)
    assert data.pop(0)==pcm[:768]
    expected=bytearray(256)
    index=end=0
    for page in range(1,len(pcm)//256):
        while page*256>=end:
            record=score['records'][index]
            for reg,value in record['writes']:
                expected[reg]=value
            end+=record['samples']
            index+=1
        assert data.pop(0)==expected, f'OPL differs at page {page}'
        if page+2<len(pcm)//256:
            assert data.pop(0)==pcm[(page+2)*256:(page+3)*256], f'PCM differs at page {page}'
    assert not data

    # Game-over must replace a running fanfare if the awarded plane is lost.
    case('victory-final-death-priority',base+bridge(50)+resume+[
        active+' 1',kind+' 1',
        poke(0xc0,sym['rr_Copyright0']&255),poke(0xb3,4),'run 6',
            'peek 0xf8 1',f'peek 0x{sym["gameover_started"]:04x} 0',kind+' 2',
            f'wait 0x{sym["demo_splash_gameover_phase"]:04x} 1 60','run 2',
            active+' 1',kind+' 0',f'peek 0x{sym["gameover_started"]:04x} 1'])

    duo = boot+['press f2','run 3','release f2','run 3']*2+['run 5',
        'press space','run 136','release space','run 4',
        'press p','run 3','release p','run 3',poke(0xa0,[255]*6),poke(0x8e,[0]*6),
        poke(0x8b,[0,0]),poke(0xc6,0),poke(0xf8,[0]*4),
        poke(sym['duo_bridge'],0),poke(sym['duo_over'],0),poke(sym['duo_gap'],[0,0]),
        poke(sym['river1'],[0]*192),poke(sym['river2'],[0]*192),
        poke(sym['player_outer_left'],[16]*192),poke(sym['player_outer_right'],[144]*192),
        poke(sym['player_island_left'],[0]*192),poke(sym['player_island_right'],[0]*192),
        poke(sym['tanks'],[0]*30),'press down s']
    players=sym['duo_players']
    for pilot in (0,1):
        p=players+pilot*23
        duo += [poke(p,[180,60+pilot*30,0,0,128,0]),
            poke(p+6,struct.pack('<H',sym['rr_JetStraight']-1)),
            poke(p+8,[24,255,0,0,65+pilot*30]+[88]*5+[0,1,0,68+pilot*16,106])]
    duo += ['run 2',poke(0xa2,8),poke(0x96,4),poke(0x9c,0x37)]

    def shoot(pilot):
        return [poke(players+pilot*23,77),poke(players+pilot*23+12,80)]

    def lives(a,b):
        return [f'peek 0x{players+8:04x} {a}',f'peek 0x{players+31:04x} {b}']

    for pilot in (0,1):
        for number in (5,20,50):
            case(f'victory-duo-p{pilot+1}-{number}',duo+bridge(number,True)+shoot(pilot)+
                resume+lives(32,32)+[active+' 1',started+f' {int(number==50)}',
                kind+(' 1' if number==50 else ' 2'),'run 20']+lives(32,32)+[started+f' {int(number==50)}'])
    case('victory-duo-two-shots-one-reward',duo+bridge(50)+shoot(0)+shoot(1)+
        resume+lives(32,32)+[started+' 1'])
    case('victory-duo-life-cap',duo+bridge(50)+shoot(0)+[
        poke(players+8,80),poke(players+31,72)]+resume+lives(80,80)+[started+' 1'])
    case('victory-duo-muted',duo+bridge(50)+shoot(0)+[poke(sym['audio_muted'],1)]+
        resume+lives(32,32)+[started+' 0'])
    for pilot in (0,1):
        other=players+(pilot^1)*23
        case(f'victory-duo-revive-p{(pilot^1)+1}',duo+bridge(50)+shoot(pilot)+[
            poke(other+8,0),poke(other+19,[0,0])]+resume+
            lives(32 if pilot==0 else 8,32 if pilot==1 else 8)+[
                f'peek 0x{other+19:04x} 2',started+' 1'])
