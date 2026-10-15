"""Execute GAME 3 on the actual 6502, including shared-world edge cases."""
import struct
from emulator_checks import poke


def run_duo_checks(case, sym, boot, output):
    base = sym['duo_players']
    stride = 22

    def player(n, offset, values):
        return poke(base+n*stride+offset, values)

    def states(buffers):
        return [buffers[-1][:22], buffers[-1][22:]]

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
    dump = ['dump xram:0x00c0 44']
    fixture = start + pause + [poke(0xa0,[255]*6),poke(0x8e,[0]*6),
        poke(0x8b,[0,0]),poke(0xc6,0),poke(0xf8,[0]*4),
        poke(sym['duo_bridge'],0),poke(sym['duo_over'],0),
        poke(sym['river1'],[0]*192),poke(sym['river2'],[0]*192),
        poke(sym['river_left'],[0]*192),poke(sym['river_right'],[0]*192),
        poke(sym['player_outer_left'],[16]*192),
        poke(sym['player_outer_right'],[144]*192),
        poke(sym['player_island_left'],[0]*192),poke(sym['player_island_right'],[0]*192),
        'press down s']
    for n,x in enumerate((60,90)):
        fixture += [player(n,0,[180,x,0,0,128,0]),
            player(n,6,struct.pack('<H',sym['rr_JetStraight']-1)),
            player(n,8,[24,255,0,0,x+5]+[88]*5+[0,1,0,68+n*16])]

    fixture += ['run 2']

    _, buffers = case('duo-start-two-visible',start+dump+[
        'dump xram:0x03dc 20',f'shot "{(output / "duo.png").as_posix()}"'])
    assert buffers[0][19]==buffers[0][41]==1
    jets=buffers[1]
    assert struct.unpack_from('<h',jets,2)[0]==struct.unpack_from('<h',jets,12)[0]==163
    assert jets[6:8]!=jets[16:18], 'Planes must have distinct palettes'

    _, buffers=case('duo-keyboard-and-first-pad',fixture+['pad 0 connect',
        'press left','pad 0 press right b']+resume+['run 10','release left',
        'pad 0 release right b']+dump)
    p1,p2=states(buffers)
    assert p1[1]<60 and p2[1]>90 and p1[0]==180 and p2[0]<180

    _,buffers=case('duo-average-speed',fixture+[player(0,3,40),player(1,3,200)]+
        resume+dump+['dump xram:0x009a 1'])
    p1,p2=buffers[0][:22],buffers[0][22:]
    assert buffers[1][0]==(p1[3]+p2[3])//2
    _,buffers=case('duo-one-survivor-speed',fixture+[player(0,19,2),
        player(0,3,254),player(1,3,100)]+resume+dump+['dump xram:0x009a 1'])
    assert buffers[1][0]==buffers[0][25]

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

    _,buffers=case('duo-mutual-collision-game-over',fixture+
        [player(0,1,76),player(1,1,76)]+resume+dump+['run 40',
        f'peek 0x{sym["ready"]:04x} 2'])
    assert all(p[19]==2 and p[8]==16 for p in states(buffers))

    _,buffers=case('duo-both-dead-before-bridge',fixture+[player(0,1,4)]+resume+
        pause+[player(1,1,4)]+resume+dump+['run 40',f'peek 0x{sym["ready"]:04x} 2'])
    assert all(p[19]==2 and p[8]==16 for p in states(buffers))

    # Bridge block zero starts at y=128+OFFSET. Its top is +8; it has
    # completely passed the 18-row planes only when OFFSET reaches 24.
    waiting=fixture+[player(0,19,2),player(0,8,16),poke(0x8e,128)]
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
        player(0,0,8),player(0,12,93),player(1,0,8),player(1,12,63)]+resume+dump)
    assert all(p[19]==1 and p[8]==24 for p in states(buffers))

    _,buffers=case('duo-restart',fixture+[player(0,1,4)]+resume+[
        'press r','run 3','release r','run 140','press space','run 20',
        'release space','run 2']+dump)
    assert all(p[19]==1 and p[8]==24 for p in states(buffers))

    # Track stack low water using untouched random RAM, including render,
    # input, dual collisions and sound at 8 MHz. Lower half must remain free.
    _,buffers=case('duo-performance-and-stack',fixture+[
        player(0,4,[255,255]),player(1,4,[255,255]),
        'dump 0xbc00 512','press space 0xe0']+resume+['run 1200']+dump+[
        'dump 0xbc00 512','peek xram:0x009e 0 0'])
    assert buffers[0]==buffers[-1], 'cc65 stack exceeded half its 1 KiB reserve'
    assert all(p[19]==1 for p in (buffers[1][:22],buffers[1][22:]))

    _,buffers=case('duo-world-once-per-frame',fixture+[
        player(0,3,254),player(1,3,254),'release down s','press up w',
        'run 2','dump xram:0x0080 32']+resume+['dump xram:0x0080 32'])
    before,after=buffers
    elapsed=int.from_bytes(after[14:16],'little')-int.from_bytes(before[14:16],'little')
    assert (after[12]-before[12])%32==2*elapsed

    _,buffers=case('duo-independent-refuelling',fixture+object_at(0,10,90)+[
        'run 2']+dump+['dump xram:0x008e 2']+resume+dump+['dump xram:0x008e 2'])
    before,t0,after,t1=buffers
    elapsed=int.from_bytes(t1,'little')-int.from_bytes(t0,'little')
    fuel=lambda p:p[4]*256+p[5]
    assert fuel(before[:22])-fuel(after[:22])==32*elapsed
    assert fuel(after[22:])-fuel(before[22:])==480*elapsed

    for n in (0,1):
        bank=list(struct.pack('<hhh7B',44,96,0,0,1,90,0,0,0,0))
        _,buffers=case(f'duo-bank-tank-owner-p{n+1}',fixture+[
            poke(0xbd,7),poke(sym['bank_tanks'],bank),
            player(n,0,45),player(n,12,47)]+resume+dump)
        p=states(buffers)
        assert points(p[n])==250 and points(p[n^1])==0

        _,buffers=case(f'duo-bridge-tank-owner-p{n+1}',fixture+object_at(1,8,63)+[
            poke(sym['tanks']+5,list(struct.pack('<hBBB',76,1,0,0))),
            player(n,0,45),player(n,12,79)]+resume+dump)
        p=states(buffers)
        assert points(p[n])==750 and points(p[n^1])==0

        _,buffers=case(f'duo-enemy-projectile-p{n+1}',fixture+[
            poke(sym['helicopter_shots'],list(struct.pack('<hh2B',60+n*30,145,1,1)))]+
            resume+dump)
        p=states(buffers)
        assert p[n][19]==2 and p[n^1][19]==1

    _,buffers=case('duo-personal-bonus-life',fixture+[
        poke(0xbd,7),poke(sym['bank_tanks'],bank),
        player(1,13,[88,88,72,56,40,0]),player(1,0,45),player(1,12,47)]+resume+dump)
    p1,p2=states(buffers)
    assert points(p2)==10000 and p2[8]==32 and p1[8]==24

    # An eligible respawn cannot rescue the team after its last pilot dies.
    _,buffers=case('duo-survivor-dies-during-blocked-respawn',fixture+[
        player(0,19,3),player(0,21,16),player(1,1,4),
        poke(sym['river1'],[255]*192),poke(sym['river2'],[255]*192),
        poke(sym['player_outer_left'],[160]*192)]+resume+['run 40',
        f'peek 0x{sym["ready"]:04x} 2']+dump)
    assert all(p[19]!=1 for p in states(buffers))

    # Exercise the shared sound alarm with only P2 low on fuel.
    case('duo-p2-fuel-alarm',fixture+[player(1,4,[16,0])]+resume+[
        'dump 0xf8 2', 'peek 0x0215 12'])
