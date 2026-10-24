"""Bridge destruction must preserve tanks still on the approaches."""
import struct
from emulator_checks import poke, score


def run_bridge_tank_checks(case, sym, fixture, resume):
    tank = sym["tanks"]+10
    dump = ["dump xram:0x0080 32", "dump 0xa2 1",
            f"dump 0x{tank:04x} 5", "dump xram:0x0378 10"]
    base = fixture + [poke(sym["tanks"],[0]*30), poke(0xa2,8),
        poke(0x96,4), poke(0x9c,0x37), poke(0xb5,0),
        "press down", "press f5", "run 2", "release f5", "run 2"]
    base += [poke(0xcd+n*2,88 if n<5 else 0) for n in range(6)]
    for kind in (0,8):
        _,data=case(f'road-tank-lowered-{kind}',base+[
            poke(0xa2,kind),poke(tank,struct.pack('<hBBB',47,1,0,0)),
            'run 3','dump xram:0x0328 10','dump xram:0x0378 10'])
        road_y=struct.unpack_from('<h',data[0],2)[0]
        tank_y=struct.unpack_from('<h',data[1],2)[0]
        assert tank_y==road_y+10, 'Road tank must sit two rows below its original offset'
    for direction in (0,1):
        _,data=case(f"road-tank-spawn-motion-{direction}",base+[
            poke(sym["tanks"],[0]*30),poke(0xa8,0),poke(0xae,1^direction),
            "run 3",f"dump 0x{tank:04x} 5", "run 30",f"dump 0x{tank:04x} 5"
        ]+resume+["run 20",f"dump 0x{tank:04x} 5"])
        x=160 if direction else -9
        assert data[0]==data[1] and struct.unpack_from("<h",data[0])[0]==x
        moved=struct.unpack_from("<h",data[2])[0]
        assert (0<x-moved<20 if direction else 0<moved-x<20)
        assert data[2][3]==direction
    for direction,x,expected in ((0,159,1),(1,-8,0)):
        _,data=case(f"road-tank-screen-edge-turn-{direction}",base+[
            poke(tank,struct.pack("<hBBB",x,1,direction,0))]+resume+[
                f"dump 0x{tank:04x} 5"])
        assert data[0][3]==expected
    for variant in (0,1):
        for direction,x,stop in ((0,40,47),(1,112,104),(0,-9,47),(1,160,104)):
            _,data=case(f"bridge-spares-approach-game{variant+1}-{direction}-{x}",
                base+[poke(0x80,variant),poke(tank,struct.pack("<hBBB",x,1,direction,0)),
                      poke(0xb2,75),poke(0xf5,80)]+resume+dump+[
                      "run 150"]+dump+["press p","run 3","release p","run 3",
                      f"dump 0x{tank:04x} 5","run 30",f"dump 0x{tank:04x} 5"])
            first,after=data[:4],data[4:8]
            assert score(first[0])==score(after[0])==500
            assert first[1][0]<4 and after[1][0]==0, "Bridge did not finish exploding"
            assert first[2][2]==after[2][2]==1, "Bridge destroyed an approaching tank"
            assert struct.unpack_from("<h",after[2])[0]==stop, "Tank did not stop at the broken bridge"
            assert struct.unpack_from("<h",after[3],2)[0]!=-256, "Surviving tank is invisible"
            assert struct.unpack_from("<H",after[3],4)[0] in (0x9d80,0xbf00,0xbfa0)
            assert data[8]==data[9], "Surviving tank moves while paused"

    for x,missile,expected in ((40,43,250),(76,79,750),(68,95,750)):
        _,data=case(f"bridge-tank-score-regression-{x}-{missile}",base+[
            poke(tank,struct.pack("<hBBB",x,1,0,0)),poke(0xb2,75),poke(0xf5,missile)
        ]+resume+dump)
        assert score(data[0])==expected
        assert data[2][2]==2, "Hit tank must be destroyed"
        assert (data[1][0]==8)==(expected==250)

    # A surviving tank remains shootable after its bridge has disappeared.
    _,data=case("bridge-survivor-direct-hit",base+[
        poke(tank,struct.pack("<hBBB",47,1,0,0)),poke(0xb2,75),poke(0xf5,80)
    ]+resume+dump+["press p","run 3","release p","run 3",
        poke(0xb2,75),poke(0xf5,50)]+resume+dump)
    assert score(data[0])==500 and score(data[4])==750
    assert data[6][2]==2 and data[5][0]<4

    # Companion ownership follows the terrain block even after its explosion.
    _,data=case("bridge-survivor-scroll-and-reset",base+[
        poke(tank,struct.pack("<hBBB",47,1,0,0)),poke(0xa2,0),
        poke(0x8b,31),poke(0xb5,254),poke(0xb6,2)
    ]+resume+[f'dump 0x{sym["tanks"]+5:04x} 5',
        "press r","run 4","release r","run 4",f'dump 0x{sym["tanks"]:04x} 30'])
    assert data[0][2]==1 and struct.unpack_from("<h",data[0])[0]==47
    assert not any(data[1][2::5]), "Restart retained a survivor"

    gunner = sym["bank_tanks"]+26
    gun_dump = [f"dump 0x{gunner:04x} 13", "dump xram:0x03dc 10"]
    shooting = base + [poke(0xa2,0),poke(sym["bank_tanks"],[0]*39),
        poke(sym["river_left"],[64]*192),poke(sym["river_right"],[80]*192)]
    for direction,x in ((0,47),(1,104)):
        _,data=case(f"bridge-survivor-fires-inward-{direction}",shooting+[
            poke(tank,struct.pack("<hBBB",x,1,direction,0))]+resume+[
            f"wait 0x{gunner+9:04x} 1 120", "run 1"]+gun_dump+[
            f"wait 0x{gunner+9:04x} 2 30", "run 1"]+gun_dump)
        firing,sprite,splash,impact=data
        assert firing[6]==direction and firing[7]==1 and firing[9]==1
        shot_x=struct.unpack_from("<h",firing,4)[0]
        assert (shot_x<x if direction else shot_x>x), "Shot flies away from the river"
        assert 64<=firing[10]<=88, "Splash target is outside water"
        assert struct.unpack_from("<h",sprite,2)[0]>0 and sprite[8]==0x01
        assert splash[9]==2 and struct.unpack_from("<h",splash,4)[0]==splash[10]
        assert impact[8]==0x31 and struct.unpack_from("<h",impact,2)[0]>0

    for bridge,x in ((8,47),(0,40)):
        _,data=case(f"road-tank-waits-until-parked-{bridge}",shooting+[
            poke(0xa2,bridge),poke(tank,struct.pack("<hBBB",x,1,0,0))]+resume+[
            f"dump 0x{gunner:04x} 13"])
        assert not any(data[0]), "Tank fired before stopping at a broken bridge"

    # Two bank tanks and the road survivor must retain separate projectiles.
    others=struct.pack("<hhh7B",30,40,40,0,1,90,1,80,0,30)
    others+=struct.pack("<hhh7B",122,90,110,1,1,90,1,80,0,122)
    _,data=case("bridge-survivor-three-gunners-and-pause",shooting+[
        poke(tank,struct.pack("<hBBB",47,1,0,0)),poke(sym["bank_tanks"],others)
    ]+resume+[f"dump 0x{sym['bank_tanks']:04x} 39", "dump xram:0x03a0 70",
        "press p","run 3","release p","run 3",f"dump 0x{gunner:04x} 13",
        "run 30",f"dump 0x{gunner:04x} 13"])
    assert all(data[0][n*13+9] for n in range(3))
    assert all(struct.unpack_from("<h",data[1],n*10+2)[0]>0 for n in (1,3,6))
    assert data[2]==data[3], "Paused road tank advanced its shot"

    _,data=case("bridge-survivor-destroyed-clears-shot",shooting+[
        poke(tank,struct.pack("<hBBB",47,1,0,0))]+resume+[
        "press p","run 3","release p","run 3",poke(0xb2,75),poke(0xf5,50)
    ]+resume+[f"dump 0x{gunner:04x} 13",f"dump 0x{tank:04x} 5",
        "dump xram:0x03dc 10"])
    assert data[1][2]==2 and not any(data[0])
    assert struct.unpack_from("<h",data[2],2)[0]==-256

    # A block rollover must not replace a flying round with a fresh one.
    _,data=case("bridge-gunner-scroll-and-restart",shooting+[
        poke(tank,struct.pack("<hBBB",47,1,0,0)),poke(sym['road_gunner'],2),
        poke(0x8b,31),poke(0xb5,254),poke(0xb6,2),
        poke(gunner,struct.pack('<hhh7B',47,97,56,0,1,90,1,88,0,47))
    ]+resume+[f"dump 0x{gunner:04x} 13", f"dump 0x{sym['road_gunner']:04x} 1",
        "press r","run 4","release r","run 4",f"dump 0x{gunner:04x} 13"])
    assert data[1][0]==1 and struct.unpack_from('<h',data[0],2)[0]>97
    assert 0<data[0][8]<90 and struct.unpack_from('<h',data[0],4)[0]>56
    assert not any(data[2]), "Restart retained the survivor's round"

    snapshot=[f"dump 0x{gunner:04x} 13", "dump xram:0x03dc 10"]
    _,data=case("bridge-gunner-f1-restores-shot",shooting+[
        poke(tank,struct.pack("<hBBB",47,1,0,0))]+resume+[
        "press p","run 3","release p","run 3"]+snapshot+[
        "release down","press f1","wait xram:0x0080 0 10","wait xram:0x00b0 2 120",
        "release f1","wait xram:0x02a4 222 5","press space","run 3",
        "release space","wait xram:0x0080 82 320","run 3"]+snapshot)
    assert data[:2]==data[2:], "F1 changed the survivor's shot"

    for x,direction,facing in ((47,1,0),(104,0,1)):
        _,data=case(f"bridge-survivor-turns-toward-river-{x}",shooting+[
            poke(tank,struct.pack('<hBBB',x,1,direction,0))]+resume+[
            f"dump 0x{tank:04x} 5", f"dump 0x{gunner:04x} 13"])
        assert data[0][3]==data[1][6]==facing and data[1][9]
