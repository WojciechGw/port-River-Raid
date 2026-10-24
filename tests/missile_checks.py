"""Missile muzzle alignment and each pilot's actual sprite colors."""
import struct

from emulator_checks import poke


def run_missile_checks(case, sym, boot, fixture, resume):
    pause = ["press p", "run 3", "release p", "run 3"]
    appearance = ["dump xram:0x9650 16", "dump xram:0x0580 8"]

    def check_color(shot, jet, pixels, palettes):
        sx, sy, image, palette, size, options = struct.unpack("<hhHHBB", shot)
        jet_palette = struct.unpack_from("<H", jet, 6)[0]
        assert sy >= 0 and image == 0x9650 and size == 0x10 and options == 0x42
        assert palette == jet_palette, "Missile does not use its pilot's palette"
        assert pixels == bytes((0x10, 0)) * 8, "Missile must use jet color index 1"
        offset = palette - 0x0580 + 2
        assert int.from_bytes(palettes[offset:offset+2], "little") != 0
        return sx

    for variant, pilot in ((0, 0), (1, 0), (1, 1)):
        for straight in (False, True):
            for bw in (False, True):
                setup = fixture + [poke(0x80, variant), poke(0xf4, pilot)]
                for key in (["f4"] if bw else []) + (["f8" if pilot else "f5"] if straight else []):
                    setup += [f"press {key}", "run 3", f"release {key}", "run 3"]
                fire = "0xe0" if pilot else "space"
                _, data = case(f"missile-game{variant+1}-p{pilot+1}-{straight=}-{bw=}",
                    setup + [f"press {fire}"] + resume + pause + [f"release {fire}",
                        "dump 0xb3 1", "dump 0xf5 1", "dump xram:0x030a 10",
                        "dump xram:0x03e6 10"] + appearance)
                x, missile_x, shot, jet, pixels, palettes = data
                assert missile_x[0] == x[0] + 4, "Muzzle must be four columns from the jet's left edge"
                assert check_color(shot, jet, pixels, palettes) == missile_x[0]*2

    select = boot + ["press f2", "run 3", "release f2", "run 3",
                     "press f2", "run 3", "release f2", "run 8"]
    duo = select + ["press space", "run 136", "release space", "run 4"] + pause
    duo += [poke(0xa0, [255]*6), poke(0x8e, [0]*6), poke(0xc6, 0),
            poke(sym["duo_gap"], [0, 0]), poke(sym["river1"], [0]*192),
            poke(sym["river2"], [0]*192), poke(sym["river_left"], [0]*192),
            poke(sym["river_right"], [0]*192),
            poke(sym["player_outer_left"], [16]*192),
            poke(sym["player_outer_right"], [144]*192),
            poke(sym["player_island_left"], [0]*192),
            poke(sym["player_island_right"], [0]*192)]
    for n, x in enumerate((60, 90)):
        duo += [poke(sym["duo_players"]+n*23, [180, x, 0, 0, 128, 0]),
                poke(sym["duo_players"]+n*23+6, struct.pack("<H", sym["rr_JetStraight"]-1)),
                poke(sym["duo_players"]+n*23+8,
                     [24, 255, 0, 0, x+4]+[88]*5+[0, 1, 0, x, 106])]
    for straight in (False, True):
        for bw in (False, True):
            setup = duo[:]
            for key in (["f4"] if bw else []) + (["f5", "f8"] if straight else []):
                setup += [f"press {key}", "run 3", f"release {key}", "run 3"]
            _, data = case(f"missile-duo-{straight=}-{bw=}",
                setup + ["press space 0xe0"] + resume + pause + ["release space 0xe0",
                    "dump xram:0x00c0 46", "dump xram:0x03c8 20", "dump xram:0x03e6 20"] + appearance)
            players, shots, jets, pixels, palettes = data
            for n in range(2):
                p = players[n*23:(n+1)*23]
                assert p[12] == p[1]+4, "DUO muzzle must follow its pilot's position"
                assert check_color(shots[n*10:(n+1)*10], jets[n*10:(n+1)*10],
                                   pixels, palettes) == p[12]*2
            assert jets[6:8] != jets[16:18], "Pilots must retain distinct palettes"
