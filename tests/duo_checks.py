"""Execute GAME 3 on the actual 6502, including shared-world edge cases."""
import struct
from emulator_checks import poke


def run_duo_checks(case, sym, boot, output):
    base = sym['duo_players']
    stride = 23

    def player(n, offset, values):
        return poke(base+n*stride+offset, values)

    def states(buffers):
        return [buffers[-1][:23], buffers[-1][23:]]

    def points(p):
        result = 0
        for digit in p[13:19]:
            result = result*10 + (digit//8 if digit<80 else 0)
        return result

    def object_at(block,kind,x=76):
        coarse,fine=divmod(x+1,15)
        size=7 if kind==8 else 5 if kind in (7,9) else 0
        return [poke(0xa0+block,kind),poke(0x94+block,coarse),
                poke(0x9a+block,((fine^7)<<4)|size)]

    select = boot + ['press f2','run 3','release f2','run 3',
                     'press f2','run 3','release f2','run 8','peek 0x80 2']
    start = select + ['press space','run 140','release space','run 4',
                      'peek xram:0x0082 1']
    pause = ['press p','run 3','release p','run 3']
    resume = ['press p','run 3','release p','run 3']
    dump = ['dump xram:0x00c0 46']
    fixture = start + pause + [poke(0xa0,[255]*6),poke(0x8e,[0]*6),
        poke(0x8b,[0,0]),poke(0xc6,0),poke(0xf8,[0]*4),
        poke(sym['duo_bridge'],0),poke(sym['duo_over'],0),poke(sym['duo_gap'],[0,0]),
        poke(sym['river1'],[0]*192),poke(sym['river2'],[0]*192),
        poke(sym['river_left'],[0]*192),poke(sym['river_right'],[0]*192),
        poke(sym['player_outer_left'],[16]*192),
        poke(sym['player_outer_right'],[144]*192),
        poke(sym['player_island_left'],[0]*192),poke(sym['player_island_right'],[0]*192),
        'press down s']
    for n,x in enumerate((60,90)):
        fixture += [player(n,0,[180,x,0,0,128,0]),
            player(n,6,struct.pack('<H',sym['rr_JetStraight']-1)),
            player(n,8,[24,255,0,0,x+5]+[88]*5+[0,1,0,68+n*16,106])]

    fixture += ['run 2']

    _, buffers = case('duo-start-two-visible',start+dump+[
        'dump xram:0x03e6 20',f'shot "{(output / "duo.png").as_posix()}"'])
    assert buffers[0][19]==buffers[0][42]==1
    jets=buffers[1]
    assert struct.unpack_from('<h',jets,2)[0]==struct.unpack_from('<h',jets,12)[0]==21+buffers[0][22]
    assert jets[6:8]!=jets[16:18], 'Planes must have distinct palettes'

    _,buffers=case('duo-life-icons-two-rows',fixture+[
        player(0,8,80),player(1,8,48),'run 4','dump xram:0x6400 200',
        'dump xram:0x0600 190',f'shot "{(output / "duo-ten-lives.png").as_posix()}"'])
    for n,count in enumerate((10,6)):
        for i in range(10):
            x,y,art,palette,size,options=struct.unpack_from('<hhHHBB',buffers[0],(n*10+i)*10)
            assert x==(44+n*80+(i%5)*7)*2
            assert y==(182+10+(9 if i>=5 else 0) if i<count else -256)
            assert art==0x9c80 and palette==(0x0760 if n else 0x0740)
    for i in (12,13,17,18):
        assert struct.unpack_from('<h',buffers[1],i*10+2)[0]<0, 'Numeric life display still visible'

    _,buffers=case('duo-life-icons-hide-in-game-one',fixture+[
        player(0,8,80),player(1,8,80),'run 3']+resume+[
        'press f2','run 3','release f2','run 10','peek 0x80 0','dump xram:0x6400 200'])
    assert all(struct.unpack_from('<h',buffers[0],i*10+2)[0]<0 for i in range(20))

    _, buffers=case('duo-keyboard-and-first-pad',fixture+['pad 0 connect',
        'press left','pad 0 press right b']+resume+['run 10','release left',
        'pad 0 release right b']+dump)
    p1,p2=states(buffers)
    assert p1[1]<60 and p2[1]>90 and p1[0]==180 and p2[0]<180

    _,buffers=case('duo-average-speed',fixture+[player(0,3,40),player(1,3,200)]+
        resume+dump+['dump xram:0x009a 1'])
    p1,p2=buffers[0][:23],buffers[0][23:]
    assert buffers[1][0]==(p1[3]+p2[3])//2
    _,buffers=case('duo-one-survivor-speed',fixture+[player(0,19,2),
        player(0,3,254),player(1,3,100)]+resume+dump+['dump xram:0x009a 1'])
    assert buffers[1][0]==buffers[0][26]

    def gap(pixels):
        # Prepare a physically consistent paused pair at a known separation.
        y0=106-pixels//2
        return [poke(sym['duo_gap'],struct.pack('<h',pixels*128)),
                player(0,22,y0),player(1,22,y0+pixels)]

    # Relative distance integrates native velocity (speed / 128), including
    # subpixel steps. Equal speeds preserve the lead already earned.
    for speed in (64,254):
        throttle=['release down','press up'] if speed==254 else []
        _,buffers=case(f'duo-integrated-lead-{speed}',fixture+[
            player(0,3,speed)]+throttle+resume+dump+['dump xram:0x008e 2',
            'run 10']+dump+['dump xram:0x008e 2'])
        before,t0,after,t1=buffers
        elapsed=int.from_bytes(t1,'little')-int.from_bytes(t0,'little')
        lead=lambda p:p[45]-p[22]
        assert abs(lead(after)-lead(before)-speed*elapsed/128)<=1

    advancing=fixture+[player(0,1,68),player(1,1,84),player(0,3,254),'release down','press up']+resume+['run 80']
    _,buffers=case('duo-four-heights-limit',advancing+dump+[
        'dump xram:0x03e6 20',f'shot "{(output / "duo-overtake.png").as_posix()}"'])
    p1,p2=buffers[0][:23],buffers[0][23:]
    assert p1[19]==p2[19]==1 and p2[22]-p1[22]==72
    assert struct.unpack_from('<h',buffers[1],2)[0]==p1[22]+21
    assert struct.unpack_from('<h',buffers[1],12)[0]==p2[22]+21

    _,buffers=case('duo-equal-speed-keeps-earned-lead',advancing+pause+[
        player(0,3,0),'release up','press down',player(0,1,90)]+resume+[
        'run 30']+dump)
    p1,p2=states(buffers)
    assert p1[19]==p2[19]==1 and p2[22]-p1[22]==72

    # Reversing throttle immediately uses the lead; no hidden excess builds
    # beyond the 72-pixel limit, and P2 can eventually overtake P1.
    _,buffers=case('duo-reverse-earned-lead',advancing+pause+[
        player(0,3,0),player(1,3,254),'release up s','press down w']+resume+dump+[
        'run 90']+dump)
    assert 0<buffers[0][45]-buffers[0][22]<72
    assert buffers[1][22]-buffers[1][45]==72

    for separation,dead in ((13,False),(10,True),(0,True)):
        _,buffers=case(f'duo-vertical-collision-{separation}',fixture+gap(separation)+[
            player(0,1,90)]+resume+dump)
        assert all(p[19]==(2 if dead else 1) and p[8]==(16 if dead else 24)
                   for p in states(buffers))

    # A launched shot keeps its own absolute trajectory while the pilot moves.
    firing=fixture+gap(54)+['press space 0xe0']
    _,buffers=case('duo-missiles-launch-at-own-height',firing+resume+dump)
    p1,p2=states(buffers)
    assert p1[0]-p2[0]==54 and p1[22]==79 and p2[22]==133
    _,buffers=case('duo-airborne-missile-keeps-position',firing+resume+pause+[
        'release space 0xe0 s','press w',player(1,3,254)]+dump+[
        'dump xram:0x008e 2']+resume+dump+['dump xram:0x008e 2'])
    before,t0,after,t1=buffers
    elapsed=int.from_bytes(t1,'little')-int.from_bytes(t0,'little')
    assert after[0]-before[0]==6*elapsed and after[22]>before[22]

    # Positions in each collision path follow the accumulated distance.
    raised=fixture+gap(-18)  # P1 y=115, P2 y=97.
    _,buffers=case('duo-raised-plane-enemy-collision',raised+[
        poke(0x8b,8)]+object_at(1,4,60)+resume+dump)
    assert states(buffers)[0][19]==2 and states(buffers)[1][19]==1
    _,buffers=case('duo-raised-plane-tank-splash',raised+[
        poke(0xbd,7),poke(sym['bank_tanks'],
            list(struct.pack('<hhh7B',30,102,60,0,1,90,2,60,18,30)))]+resume+dump)
    assert states(buffers)[0][19]==2 and states(buffers)[1][19]==1
    _,buffers=case('duo-raised-plane-refuel',raised+object_at(1,10,60)+resume+dump)
    assert states(buffers)[0][4]>128 and states(buffers)[1][4]<128
    _,buffers=case('duo-raised-plane-helicopter-shot',raised+[
        poke(sym['helicopter_shots'],list(struct.pack('<hh2B',60,118,1,1)))]+resume+dump)
    assert states(buffers)[0][19]==2 and states(buffers)[1][19]==1

    for backend in ('psg','opl2','pcm'):
        _,buffers=case(f'duo-overtaking-performance-{backend}',fixture+[
            player(1,3,254),'release s','press w space 0xe0']+resume+[
            'run 40']+dump,rom_args=(f'/{backend}',))
        p1,p2=states(buffers)
        assert p1[19]==p2[19]==1 and p1[22]-p2[22]==72

    case('duo-initial-spawn-does-not-pass-bridge',fixture+[
        player(0,19,3),player(1,19,3),poke(sym['duo_started'],1),
        poke(0x8f,128)]+resume+[f'peek 0x{sym["duo_bridge"]:04x} 0'])

    # Only the living pilot affects scroll. Its altitude and the fallen
    # pilot's altitude stay fixed until the partner returns at that height.
    waiting_high=fixture+gap(72)+[player(1,19,2),player(1,8,16),
        poke(0x90,128),poke(0xa2,1)]
    _,buffers=case('duo-raised-bridge-not-yet-passed',waiting_high+[
        poke(0x8b,15)]+resume+dump)
    assert states(buffers)[1][19]==2
    _,buffers=case('duo-raised-bridge-respawn',waiting_high+[
        poke(0x8b,16)]+resume+dump)
    p1,p2=states(buffers)
    assert p1[19]==p2[19]==1 and p1[22]==70 and p2[22]==142

    _,buffers=case('duo-passed-bridge-cannot-revive-later-death',fixture+gap(72)+[
        poke(0x90,128),poke(0xa2,1),poke(0x8b,16)]+resume+pause+[
        player(1,4,[0,0])]+resume+dump)
    assert states(buffers)[0][19]==1 and states(buffers)[1][19]==2

    _,buffers=case('duo-pause',fixture+dump+['run 60']+dump)
    assert buffers[0]==buffers[1]

    for n in (0,1):
        _,buffers=case(f'duo-bank-death-p{n+1}',fixture+[player(n,1,4)]+resume+dump)
        p=states(buffers)
        assert p[n][19]==2 and p[n][8]==16 and p[n][0]==180
        assert p[n^1][19]==1 and p[n^1][8]==24
        _,buffers=case(f'duo-fuel-death-p{n+1}',fixture+[player(n,4,[0,0])]+resume+dump)
        p=states(buffers)
        assert p[n][19]==2 and p[n][8]==16 and p[n^1][19]==1

    restarted=['run 40','peek 0xc6 0',f'peek 0x{sym["ready"]:04x} 0']+dump
    _,buffers=case('duo-mutual-collision-restarts-stage',fixture+
        [player(0,1,76),player(1,1,76)]+resume+dump+restarted)
    assert all(buffers[0][n*stride+19]==2 and buffers[0][n*stride+8]==16 for n in (0,1))
    assert all(p[19]==1 and p[8]==16 and p[4]>=254 and p[22]==106 for p in states(buffers))

    _,buffers=case('duo-both-dead-before-bridge',fixture+[player(0,1,4)]+resume+
        pause+[player(1,1,4)]+resume+dump+restarted)
    assert all(p[19]==1 and p[8]==16 for p in states(buffers))

    # Keep each score and the current section, not the F3 starting level.
    # The saved RNG must rebuild the same section from its beginning.
    for early_next in (False,True):
        _,buffers=case(f'duo-restart-section-checkpoint-{early_next}',fixture+gap(72)+[
            poke(0xbd,8 if early_next else 7),poke(0xbe,[19,37]),
            poke(0xeb,[51,69]),poke(0x8a,0),poke(0x93,4 if early_next else 0),
            player(0,13,[88,88,88,8,16,24]),player(1,13,[88,88,88,32,40,48]),
            player(0,1,4),player(1,1,4)]+resume+[
            f'wait 0x{sym["duo_started"]:04x} 1 50','peek 0xbd 7',
            'peek 0xb9 17',f'peek 0xe9 {51 if early_next else 19} {69 if early_next else 37}',
            f'peek 0x{sym["duo_gap"]:04x} 0 0',
            f'wait 0x{sym["duo_started"]:04x} 2 30','run 2']+dump)
        p1,p2=states(buffers)
        assert points(p1)==123 and points(p2)==456
        assert all(p[8]==16 and p[19]==1 and p[22]==106 for p in (p1,p2))

    for eliminated in (0,1):
        _,buffers=case(f'duo-restart-with-one-life-pool-empty-p{eliminated+1}',fixture+[
            player(eliminated,8,8),player(0,1,76),player(1,1,76)]+resume+restarted)
        p=states(buffers)
        assert p[eliminated][19]==0 and p[eliminated][8]==0
        assert p[eliminated^1][19]==1 and p[eliminated^1][8]==16

    _,buffers=case('duo-no-lives-game-over',fixture+[player(0,8,8),player(1,8,8),
        player(0,1,76),player(1,1,76)]+resume+['run 40',
        f'peek 0x{sym["ready"]:04x} 2']+dump)
    assert all(p[8]==0 and p[19]==0 for p in states(buffers))

    # Three successive crashes exhaust exactly the initial three lives.
    commands=fixture+[player(0,1,76),player(1,1,76)]+resume+restarted
    commands+=pause+[player(0,1,76),player(1,1,76)]+resume+restarted
    commands+=pause+[player(0,1,76),player(1,1,76)]+resume+[
        'run 40',f'peek 0x{sym["ready"]:04x} 2']+dump
    _,buffers=case('duo-three-crashes-exhaust-three-lives',commands)
    for data,lives,state in zip(buffers,(16,8,0),(1,1,0)):
        assert all(data[n*stride+8]==lives and data[n*stride+19]==state for n in (0,1))

    # Pause also freezes the delay before a shared restart.
    _,buffers=case('duo-pause-during-shared-explosion',fixture+[
        player(0,1,76),player(1,1,76)]+resume+pause+dump+['run 60']+dump+
        resume+restarted)
    assert buffers[0]==buffers[1]
    assert all(p[8]==16 and p[19]==1 for p in states(buffers))

    # Bridge block zero starts at y=128+OFFSET. Its top is +8; it has
    # completely passed a survivor at Y=142 only when OFFSET reaches 24.
    waiting=fixture+[player(0,19,2),player(0,8,16),player(1,22,142),poke(0x8e,128)]
    for offset in (0,20,23):
        _,buffers=case(f'duo-no-early-respawn-{offset}',waiting+
            [poke(0x8b,offset),poke(0xa0,1),poke(0xbd,5)]+resume+dump)
        assert states(buffers)[0][19]==2
    _,buffers=case('duo-respawn-after-passing-bridge',waiting+
        [poke(0x8b,24),poke(0xa0,1)]+resume+dump)
    p1,p2=states(buffers)
    assert p1[19]==1 and p1[8]==16 and p1[4]>=254
    assert abs(p1[1]-p2[1])>=12 and p2[19]==1
    _,buffers=case('duo-no-life-no-respawn',waiting+
        [player(0,19,0),player(0,8,0),poke(0x8b,24)]+resume+dump)
    assert states(buffers)[0][19]==0

    _,buffers=case('duo-blocked-respawn-retries',waiting+[
        poke(0x8b,24),poke(sym['player_outer_left'],[144]*192),
        poke(sym['river1'],[255]*192),poke(sym['river2'],[255]*192),
        player(1,1,144),poke(sym['player_outer_right'],[160]*192)]+resume+
        ['run 8']+dump+pause+[
        poke(sym['player_outer_left'],[16]*192),
        poke(sym['river1'],[0]*192),poke(sym['river2'],[0]*192),
        poke(sym['player_outer_right'],[160]*192)]+resume+['run 50']+dump)
    assert buffers[0][19]==3, 'Blocked respawn must remain pending'
    assert buffers[1][19]==1, 'Respawn must retry once water is available'

    # Native fuel bitmap at block 2; both missiles can hit the same object
    # without putting the planes together. X=76, sprite origin y=64.
    target=[poke(0xa2,10),poke(0x96,5),poke(0x9c,0x40)]
    for n in (0,1):
        _,buffers=case(f'duo-score-owner-p{n+1}',fixture+target+[
            player(n,0,80),player(n,12,79)]+resume+dump)
        p=states(buffers)
        assert points(p[n])==80 and points(p[n^1])==0, [points(q) for q in p]
    _,buffers=case('duo-one-award-simultaneous-hit',fixture+target+[
        player(0,0,80),player(1,0,80),player(0,12,79),player(1,12,79)]+resume+dump)
    assert sorted(points(p) for p in states(buffers))==[0,80]

    # Missiles at the partner's opaque row cannot hurt that player.
    _,buffers=case('duo-friendly-projectiles',fixture+[
        player(0,0,44),player(0,12,93),player(1,0,44),player(1,12,63)]+resume+dump)
    assert all(p[19]==1 and p[8]==24 for p in states(buffers))

    _,buffers=case('duo-restart',fixture+[player(0,1,4)]+resume+[
        'press r','run 3','release r',f'wait 0x{sym["duo_started"]:04x} 2 180',
        'run 2']+dump)
    assert all(p[19]==1 and p[8]==24 for p in states(buffers))

    # Track stack low water using untouched random RAM, including render,
    # input, dual collisions and sound at 8 MHz. Lower half must remain free.
    _,buffers=case('duo-performance-and-stack',fixture+[
        player(0,4,[255,255]),player(1,4,[255,255]),
        'dump 0xbc00 512','press space 0xe0']+resume+['run 1200']+dump+[
        'dump 0xbc00 512','peek xram:0x009e 0 0'])
    assert buffers[0]==buffers[-1], 'cc65 stack exceeded half its 1 KiB reserve'
    assert all(p[19]==1 for p in (buffers[1][:23],buffers[1][23:]))

    _,buffers=case('duo-world-once-per-frame',fixture+[
        player(0,3,254),player(1,3,254),'release down s','press up w',
        'run 2','dump xram:0x0080 32']+resume+['dump xram:0x0080 32'])
    before,after=buffers
    elapsed=int.from_bytes(after[14:16],'little')-int.from_bytes(before[14:16],'little')
    assert (after[12]-before[12])%32==2*elapsed

    _,buffers=case('duo-independent-refuelling',fixture+object_at(1,10,90)+[
        'run 2']+dump+['dump xram:0x008e 2']+resume+dump+['dump xram:0x008e 2'])
    before,t0,after,t1=buffers
    elapsed=int.from_bytes(t1,'little')-int.from_bytes(t0,'little')
    fuel=lambda p:p[4]*256+p[5]
    assert fuel(before[:23])-fuel(after[:23])==32*elapsed
    assert fuel(after[23:])-fuel(before[23:])==480*elapsed

    for n in (0,1):
        bank=list(struct.pack('<hhh7B',44,96,0,0,1,90,0,0,0,0))
        _,buffers=case(f'duo-bank-tank-owner-p{n+1}',fixture+[
            poke(0xbd,7),poke(sym['bank_tanks'],bank),
            player(n,0,45),player(n,12,47)]+resume+dump)
        p=states(buffers)
        assert points(p[n])==250 and points(p[n^1])==0

        _,buffers=case(f'duo-bridge-tank-owner-p{n+1}',fixture+object_at(2,8,63)+[
            poke(sym['tanks']+10,list(struct.pack('<hBBB',76,1,0,0))),
            player(n,0,77),player(n,12,79)]+resume+dump)
        p=states(buffers)
        assert points(p[n])==750 and points(p[n^1])==0

        for direction,x,stop in ((0,40,47),(1,112,104)):
            _,buffers=case(f'duo-bridge-spares-tank-p{n+1}-{direction}',
                fixture+object_at(2,8,63)+[
                    poke(sym['tanks']+10,list(struct.pack('<hBBB',x,1,direction,0))),
                    player(n,0,77),player(n,12,79)]+resume+['run 50',
                    f'dump 0x{sym["tanks"]+10:04x} 5','dump xram:0x0378 10']+dump)
            p=states(buffers)
            assert points(p[n])==500 and points(p[n^1])==0
            assert buffers[0][2]==1 and struct.unpack_from('<h',buffers[0])[0]==stop
            assert struct.unpack_from('<h',buffers[1],2)[0]!=-256

        _,buffers=case(f'duo-enemy-projectile-p{n+1}',fixture+[
            poke(sym['helicopter_shots'],list(struct.pack('<hh2B',60+n*30,109,1,1)))]+
            resume+dump)
        p=states(buffers)
        assert p[n][19]==2 and p[n^1][19]==1

        for phase in (1,2):
            # Same trajectory as a bank tank: flight is safe, splash is not.
            shot=struct.pack('<hhh7B',47,96,60+n*30,0,1,90,phase,110,6,47)
            _,buffers=case(f'duo-road-gunner-phase{phase}-p{n+1}',fixture+[
                poke(0xa1,0),poke(sym['tanks']+5,struct.pack('<hBBB',47,1,0,0)),
                poke(sym['road_gunner'],1),poke(sym['bank_tanks']+26,shot)
            ]+resume+dump)
            p=states(buffers)
            assert p[n][19]==(2 if phase==2 else 1) and p[n^1][19]==1

    case('duo-three-gunners-performance',fixture+[
        poke(0xa3,0),poke(sym['tanks']+15,struct.pack('<hBBB',47,1,0,0)),
        poke(sym['river_left'],[64]*192),poke(sym['river_right'],[80]*192),
        poke(sym['bank_tanks'],struct.pack('<hhh7B',53,0,0,0,1,0,0,0,0,53)+
             struct.pack('<hhh7B',98,64,0,1,1,0,0,0,0,98))
    ]+resume+['run 180','peek xram:0x00d3 1','peek xram:0x00ea 1'])

    _,buffers=case('duo-personal-bonus-life',fixture+[
        poke(0xbd,7),poke(sym['bank_tanks'],bank),
        player(1,13,[88,88,72,56,40,0]),player(1,0,45),player(1,12,47)]+resume+dump)
    p1,p2=states(buffers)
    assert points(p2)==10000 and p2[8]==32 and p1[8]==24

    # Both the native object score and the tank bonus must allow 9 -> 10,
    # and must not award an eleventh life or touch the partner's reserve.
    for n in (0,1):
        for lives in (72,80):
            for tank in (False,True):
                commands=fixture+[player(n,8,lives)]
                if tank:
                    commands += [poke(0xbd,7),poke(sym['bank_tanks'],bank),
                        player(n,13,[88,88,72,56,40,0]),player(n,0,45),player(n,12,47)]
                else:
                    commands += target+[player(n,13,[88,88,72,72,16,0]),
                        player(n,0,80),player(n,12,79)]
                _,buffers=case(f'duo-life-cap-p{n+1}-{lives//8}-{tank}',commands+resume+dump)
                p=states(buffers)
                assert points(p[n])==10000 and p[n][8]==80 and p[n^1][8]==24
        _,buffers=case(f'duo-death-from-ten-lives-p{n+1}',fixture+[
            player(n,8,80),player(n,1,4)]+resume+dump)
        assert states(buffers)[n][8]==72 and states(buffers)[n][19]==2

    # A blocked respawn must restart the stage after the last pilot dies.
    _,buffers=case('duo-survivor-dies-during-blocked-respawn',fixture+[
        player(0,19,3),player(0,21,16),player(1,1,4),
        poke(sym['river1'],[255]*192),poke(sym['river2'],[255]*192),
        poke(sym['player_outer_left'],[160]*192)]+resume+restarted)
    p1,p2=states(buffers)
    assert p1[19]==p2[19]==1 and p1[8]==24 and p2[8]==16

    # Exercise the shared sound alarm with only P2 low on fuel.
    case('duo-p2-fuel-alarm',fixture+[player(1,4,[16,0])]+resume+[
        'dump 0xf8 2', 'peek 0x0215 12'])

    # Shared bonus code must retain the original nine-life cap in GAME 1/2.
    for variant in (0,1):
        classic=boot+(['press f2','run 3','release f2','run 8'] if variant else [])
        classic+=['press space','run 140','release space','run 4']+pause+[
            poke(0xa0,[0]*6),poke(0x8b,[0,0]),poke(0xb3,[76,0,0,2,128,0]),
            poke(0xba,[0xbb,0xcc]),poke(0xc0,72),poke(0xc6,0),poke(0xb2,180),
            poke(0xf5,81),poke(0xe0,0),poke(sym['river1'],[0]*192),poke(sym['river2'],[0]*192)]
        for tank in (False,True):
            digits=(88,88,72,56,40,0) if tank else (88,88,72,72,72,0)
            commands=classic+[poke(0xcd+i*2,v) for i,v in enumerate(digits)]
            commands+=object_at(1,8,63)+[poke(sym['tanks']+5,[40,0,1,0,0]),
                poke(0xb2,45),poke(0xf5,43)] if tank else object_at(1,7)+[poke(0xb2,43)]
            _,buffers=case(f'classic-life-cap-game{variant+1}-{tank}',commands+resume+[
                'peek 0xc0 72','dump xram:0x0090 6'])
            score=0
            for digit in buffers[0]:
                score=score*10+(digit//8 if digit<80 else 0)
            assert score==(10000 if tank else 10020)
