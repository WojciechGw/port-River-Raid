"""Execute the shipping ROM at 8 MHz and check native original game rules.

Rare conditions use paused RAM fixtures. No test commands are compiled into
the game. The original zero-page layout is deliberately retained at $80-$FF.
"""
import argparse
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def symbols(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("sym\t"):
            continue
        name = re.search(r'name="(_[^"]+)"', line)
        value = re.search(r"\bval=(0x[0-9A-Fa-f]+)", line)
        if name and value:
            result[name[1][1:]] = int(value[1], 16)
    return result


def poke(address, values):
    if isinstance(values, int):
        values = [values]
    return f"poke 0x{address:04x} " + " ".join(str(v) for v in values)


def score(state):
    value = 0
    for ptr in state[16:22]:
        value = value * 10 + (ptr // 8 if ptr < 80 else 0)
    return value


def check_terrain_pixels(config, terrain, tiles, river1, river2):
    """Compare rendered pixels (including brown rims) with collision masks."""
    origin_y = struct.unpack_from("<h", config, 4)[0]
    for screen_y in range(21, 181):
        n = (screen_y-origin_y) % 192
        for x in range(160):
            mirrored_x = x if x < 80 else 159-x
            if mirrored_x < 16:
                land = True
            elif mirrored_x < 48:
                land = bool(river1[n] & (128 >> ((mirrored_x-16)//4)))
            else:
                land = bool(river2[n] & (1 << ((mirrored_x-48)//4)))
            tile = terrain[n*40+x//4]
            # One logical pixel occupies both nibbles of one texture byte.
            pixel_pair = tiles[tile*32+x%4]
            assert ((pixel_pair >> 4) != 1) == land, f"Terrain/land mismatch at {x},{screen_y}"
            assert ((pixel_pair & 15) != 1) == land, f"Terrain/land mismatch at {x},{screen_y}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build/cc65/release")
    parser.add_argument("--emulator", type=Path, default=ROOT / "tools/rp6502-emu.exe")
    args = parser.parse_args()
    build = args.build.resolve()
    sym = symbols(build / "riverride.dbg")
    output = build / "checks"
    output.mkdir(exist_ok=True)
    count = 0

    def case(name, commands, fill="random"):
        nonlocal count
        # Allow the next loop to account for the last rendered frame, including
        # full resets/respawns. The exit case has already returned to the OS.
        if not commands[-1].startswith("expect-exit"):
            commands = commands + ["run 2", "peek xram:0x009e 0 0"]
        script = output / f"{name}.script"
        script.write_text("\n".join(commands) + "\n", encoding="utf-8")
        process = subprocess.run([
            str(args.emulator.resolve()), str(build / "riverride.rp6502"),
            "--script", str(script), "--mute", "--phi2", "8000", "--seed", "42",
            "--fill", fill, "--save-dir", str(output / "save"),
        ], cwd=ROOT, text=True, capture_output=True, timeout=60)
        # Some emulator releases report a script error with exit code zero.
        if process.returncode or "rp6502-emu:" in process.stderr:
            raise AssertionError(f"{name}:\n{process.stdout}{process.stderr}")
        dumps = [bytes.fromhex(line) for line in process.stdout.splitlines()
                 if re.fullmatch(r"(?:[0-9A-Fa-f]{2} ?)+", line)]
        count += 1
        print(f"PASS {name}", flush=True)
        return process.stdout, dumps

    boot = ["run 240", "peek xram:0x0080 0x52 3 3"]
    start = boot + ["press space", "run 140", "release space", "run 4",
                    "peek xram:0x0082 1", "peek xram:0x0084 3 1"]
    pause = start + ["press p", "run 3", "release p", "run 3", "peek xram:0x008b 1"]
    resume = ["press p", "run 3", "release p", "run 3"]
    dump = ["dump xram:0x0080 32"]
    # Safe, stationary first-level corridor; exact original state addresses.
    fixture = pause + [poke(0xa0, [0]*6), poke(0x8b, [0, 0]),
        poke(0xb3, [76, 0, 0, 2, 128, 0]), poke(0xba, [0xbb, 0xcc]),
        poke(0xc0, 24), poke(0xc6, 0), poke(0xb2, 180), poke(0xf5, 81),
        poke(0xe0, 0), poke(sym["river1"], [0]*192), poke(sym["river2"], [0]*192)]
    clear_score = [poke(0xcd + n*2, 88 if n<5 else 0) for n in range(6)]

    def object_at(block, kind, x=76):
        coarse, fine = divmod(x+1, 15)
        size = 7 if kind == 8 else 5 if kind in (7, 9) else 0
        return [poke(0xa0+block, kind), poke(0x94+block, coarse),
                poke(0x9a+block, ((fine^7)<<4)|size)]

    a, _ = case("title-random", boot + ["crc", f'shot "{(output / "title.png").as_posix()}"'])
    b, _ = case("title-zero", boot + ["crc"], "0")
    assert a == b, "Initial image depends on RAM contents"

    # The tank lettering is three columns of transparent pixels inside its
    # opaque body. Check recognizable glyphs in the actual uploaded 4-bpp image.
    _, images = case("fuel-lettering", boot + ["dump xram:0x9400 128"])
    tank = images[-1]
    for letter, top, glyph in (
        ("F", 7, (0b111, 0b100, 0b110, 0b100, 0b100)),
        ("U", 13, (0b101, 0b101, 0b101, 0b111)),
        ("E", 18, (0b111, 0b100, 0b110, 0b100, 0b111)),
        ("L", 24, (0b100, 0b100, 0b100, 0b100, 0b111)),
    ):
        for y, expected in enumerate(glyph, top):
            holes = 0
            for x in range(2, 5):
                color = (tank[y*4+x//2] >> (0 if x&1 else 4)) & 15
                holes = (holes << 1) | (color == 0)
            assert holes == expected, f"Broken {letter} in FUEL, row {y-top}"

    _, states = case("keyboard-acceleration-and-pause", start + dump + [
        "press right", "run 4"] + dump + ["run 24", "release right", "run 2"] + dump + [
        "press p", "run 3", "release p", "run 3", "mark"] + dump + [
        "run 60", "expect-same"] + dump)
    assert states[1][3]-states[0][3] < states[2][3]-states[1][3]
    assert states[-1][6:8] == states[-2][6:8] and states[-1][14:16] == states[-2][14:16]

    for kind in ("western", "eastern", "playstation"):
        _, states = case(f"gamepad-{kind}", boot + [f"pad 0 connect {kind} sticks",
            "pad 0 press b", "run 140", "pad 0 release b", "run 4",
            "peek xram:0x0082 1", "pad 0 stick 127 0 0 0", "run 20",
            "pad 0 stick 0 0 0 0", "run 3"] + dump)
        assert states[-1][3] > 76

    _, states = case("throttle", fixture + [poke(0xb5, 64)] + resume + dump + [
        "press up", "run 12", "release up"] + dump + [
        "press down", "run 12", "release down"] + dump)
    assert states[1][26] > states[0][26] and states[2][26] < states[1][26]

    _, states = case("exact-fuel-burn", fixture + ["run 1"] + dump + resume + dump)
    elapsed = int.from_bytes(states[1][14:16], "little")-int.from_bytes(states[0][14:16], "little")
    assert int.from_bytes(states[0][6:8], "little")-int.from_bytes(states[1][6:8], "little") == elapsed*32

    _, states = case("exact-refuelling", fixture + object_at(0, 10) + ["run 1"] + dump + resume + dump)
    elapsed = int.from_bytes(states[1][14:16], "little")-int.from_bytes(states[0][14:16], "little")
    assert int.from_bytes(states[1][6:8], "little")-int.from_bytes(states[0][6:8], "little") == elapsed*480

    # Let the original generator build a road, then compare the actual sprite
    # span with the water pixels in the uploaded circular terrain buffer.
    _, buffers = case("bridge-bank-alignment", boot + [
        "press p", "run 3", "release p", "run 3", poke(0xa0, [0]*6),
        poke(0xb5, [254, 2, 255, 255]), poke(0x8b, [31, 255]),
        poke(0xb9, 1), poke(0xbc, 12), poke(0x88, [12, 0]), poke(0xc6, 0),
        "press p", "run 35", "release p", "run 1", "press p", "run 3",
        "release p", "run 3", "dump 0xa0 6", "dump xram:0x0300 100",
        "dump xram:0x0200 16", "dump xram:0x0800 7680", "dump xram:0x9000 512",
        "dump xram:0x2700 416", f'dump 0x{sym["river1"]:04x} 192',
        f'dump 0x{sym["river2"]:04x} 192',
        f'shot "{(output / "bridge.png").as_posix()}"'])
    shapes, sprites, config, terrain, bridge, tiles, river1, river2 = buffers
    check_terrain_pixels(config, terrain, tiles, river1, river2)
    block = shapes.index(8)
    x, y, _, _, size, options = struct.unpack_from("<hhHHBB", sprites, (block+2)*10)
    image_width = ((size & 15)+1)*4
    screen_width = image_width*(2 if options & 64 else 1)
    terrain_y = struct.unpack_from("<h", config, 4)[0]
    row_offset = ((y+12-terrain_y) % 192)*40
    water = [i*4+p for i, tile in enumerate(terrain[row_offset:row_offset+40])
             if tile == 1 for p in range(4)]
    assert water == list(range(64, 96)), "Original road has unexpected bank positions"
    assert (x, x+screen_width) == (water[0]*2, (water[-1]+1)*2), "Bridge misses a river bank"
    body = bridge[12*image_width//2:13*image_width//2]
    assert all((pixel >> 4) and (pixel & 15) for pixel in body), "Gap in bridge deck"

    # F3 selects straight missiles, so guidance cannot pull a missed shot
    # back into the bridge on a later frame.
    for missile_x, expected in ((63, 0), (95, 500)):
        _, states = case(f"bridge-edge-{missile_x}", fixture + clear_score +
            object_at(1, 8, 63) + [poke(0xb2, 43), poke(0xf5, missile_x),
                "press f3", "run 2", "release f3", "run 2"] + resume + dump)
        assert score(states[-1]) == expected, "Bridge collision disagrees with its visible edge"

    for kind, points in ((4, 100), (5, 60), (7, 30), (8, 500), (10, 80)):
        _, states = case(f"score-object-{kind}", fixture + clear_score + object_at(1, kind) + [
            poke(0xb2, 43), poke(0xf5, 81)] + resume + dump)
        assert score(states[-1]) == points, f"Object {kind}: score {score(states[-1])}"
        if kind == 8:
            assert states[-1][5] == 1, "Bridge advances the section when it scrolls out, not on hit"

    _, states = case("bonus-life", fixture + [poke(0xcd+n*2, v) for n,v in
        enumerate((88,88,72,72,72,0))] + object_at(1,7) + [poke(0xb2,43)] + resume + dump)
    assert score(states[-1]) == 10020 and states[-1][4] == 4

    _, states = case("maximum-score", fixture + [poke(0xcd+n*2,v) for n,v in
        enumerate((72,72,72,72,72,0))] + object_at(1,7) + [poke(0xb2,43)] + resume + dump)
    assert states[-1][16:22] == bytes([80]*6) and states[-1][2] == 2

    _, states = case("literal-generator-lfsr", fixture + [poke(0x8b,31), poke(0x8c,255),
        poke(0xb5,254), poke(0xb6,2), poke(0xb9,8), poke(0xe9,[0x14,0xa8]),
        "run 4", "press p up", "run 3", "release p up", "run 3"] + dump)
    assert states[-1][24:26] == bytes([0x29,0x50])

    case("black-and-white-switch", boot + ["mark", "press f1", "run 4",
        "release f1", "run 4", "peek 0x86 15", "expect-changed"])
    case("screensaver-and-input", fixture + [poke(0xf7,128)] + resume + [
        "peek 0x86 247", "press right", "run 4", "release right", "run 3", "peek 0x86 255"])
    _, states = case("maximum-level-wrap", fixture + [poke(0xbd,48), poke(0xb9,1),
        poke(0xb6,1), poke(0x8b,31), poke(0xb5,254), "run 4",
        "press p up", "run 3", "release p up", "run 3"] + dump)
    assert states[-1][5] == 47, "The original loops levels 47/48"
    _, states = case("enemy-bank-bounce", fixture + [poke(0xbd,2), poke(0x8f,64)] +
        object_at(1,7,8) + resume + ["dump 0x9b 1"])
    assert states[-1][0]&8, "Ship failed to reverse at the bank"

    case("bank-crash-and-section-replay", fixture + [poke(0xb3,4), poke(0xbe,[0x34,0x12])]
        + resume + ["peek xram:0x0082 2", "wait 0xc6 48 300", "run 3", "peek 0xbe 52 18",
                    "peek xram:0x0084 2", "press space", "run 3", "release space",
                    "run 3", "peek xram:0x0082 1"])
    case("empty-fuel", fixture + [poke(0xb7,[0,16])] + resume + ["peek xram:0x0082 2"])
    case("enemy-crash", fixture + object_at(0,7) + resume + ["peek xram:0x0082 2"])
    case("missile-land", fixture + [poke(0xb2,43), poke(0xf5,4)] + resume + ["peek xram:0x0088 0"])

    for hard in (False, True):
        commands = fixture + [poke(0xb2,50), poke(0xf5,40), poke(0xb3,90)]
        if hard:
            commands += ["press f3", "run 2", "release f3", "run 2"]
        _, states = case("straight-missile" if hard else "guided-missile", commands + resume + dump)
        assert states[-1][9] == (40 if hard else 95)

    two = boot + ["press f2", "run 2", "release f2", "run 2", "peek 0x80 1",
                  "press space", "run 140", "release space", "run 4", "peek xram:0x0082 1",
                  "press p", "run 3", "release p", "run 3", poke(0xb3,4)]
    _, states = case("two-player-switch", two + resume + ["wait 0xf4 1 240"] + dump + [
        "wait 0xc6 48 300", "run 3", "press d", "run 18", "release d", "run 2"] + dump)
    assert states[-1][29] == 1 and states[-1][3] > 76

    # Copyright0 ($59) marks the last jet: no reserve jet remains.
    case("game-over-restart-exit", fixture + [poke(0xc0,89), poke(0xb3,4)] + resume + [
        "wait 0xc6 255 300", "press space", "run 140", "release space", "run 4",
        "peek xram:0x0082 1", "peek xram:0x0084 3 1", "press escape", "expect-exit 0 120"])
    _, states = case("scroll-and-performance", start + ["press up space", "run 1200",
        "release up space", "run 4"] + dump + [f'shot "{(output / "gameplay.png").as_posix()}"'])
    assert int.from_bytes(states[-1][30:32], "little") == 0, "Skipped VSYNC at 8 MHz"
    assert states[-1][5] >= 2
    # A restart and palette change can redraw terrain, score, fuel and logo
    # together. Exercise that combination after some gameplay, repeatedly.
    commands = start + ["press up space", "run 600", "release up space", "run 4"]
    for _ in range(6):
        commands += ["press r f1", "run 4", "release r f1", "run 12"]
    case("restart-and-palette-performance", commands)
    print(f"All {count} emulator checks passed. Screenshots: {output}", flush=True)


if __name__ == "__main__":
    main()
