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
