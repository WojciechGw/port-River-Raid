"""Execute the shipping ROM at 8 MHz and check native original game rules.

Rare conditions use paused RAM fixtures. No test commands are compiled into
the game. The original zero-page layout is deliberately retained at $80-$FF.
"""
import argparse
import math
import re
import struct
import subprocess
import sys
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


def check_terrain_pixels(config, terrain, tiles, river1, river2, river_left, river_right):
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
            land = land and not river_left[n]<=mirrored_x<river_right[n]
            tile = terrain[n*40+x//4]
            # One logical pixel occupies both nibbles of one texture byte.
            pixel_pair = tiles[tile*32+x%4]
            assert ((pixel_pair >> 4) != 1) == land, f"Terrain/land mismatch at {x},{screen_y}"
            assert ((pixel_pair & 15) != 1) == land, f"Terrain/land mismatch at {x},{screen_y}"


def check_player_ground(config, terrain, tiles, outer_left, outer_right, island_left, island_right):
    """Only ground pixels collide with the jet; the visible brown rim is safe."""
    origin_y=struct.unpack_from("<h",config,4)[0]
    for y in range(21,181):
        n=(y-origin_y)%192
        for x in range(160):
            ground=(x<outer_left[n] or x>=outer_right[n] or
                    island_left[n]<=x<island_right[n])
            color=tiles[terrain[n*40+x//4]*32+x%4]&15
            assert ground==(color not in (1,12)), f"Jet ground differs from pixels at {x},{y}"


def check_bank_contours(config, terrain, tiles, require_features=True, smooth_width=True):
    """Every visible water/land contact has a brown rim, including bends/roads."""
    origin_y = struct.unpack_from("<h", config, 4)[0]
    pixels = []
    for screen_y in range(21, 181):
        n = (screen_y-origin_y) % 192
        pixels.append([tiles[terrain[n*40+x//4]*32+x%4] & 15 for x in range(160)])
    vertical_contacts = road_contacts = 0
    different_widths = False
    profiles = []
    widths = set()
    for y, line in enumerate(pixels):
        for x, color in enumerate(line):
            if color == 1:
                continue
            horizontal = any(0<=nx<160 and line[nx]==1 for nx in (x-1, x+1))
            vertical = any(0<=ny<160 and pixels[ny][x]==1 for ny in (y-1, y+1))
            if horizontal or vertical:
                assert color == 12, f"Missing brown river rim at {x},{y+21}"
                vertical_contacts += vertical and not horizontal
                road_contacts += horizontal and any(c in (4,5,6) for c in line)
        water = [x for x, c in enumerate(line) if c==1]
        if water:
            left, right = water[0]-1, water[-1]+1
            lw = rw = 0
            while left>=0 and line[left]==12:
                lw += 1
                left -= 1
            while right<160 and line[right]==12:
                rw += 1
                right += 1
            different_widths |= lw != rw
            widths.update((lw,rw))
            profiles.append((water[0],water[-1],lw,rw))
        else:
            profiles.append(None)
    for y in range(4,len(profiles)-4):
        previous,current,following=profiles[y-1:y+2]
        if not all((previous,current,following)):
            continue
        for edge,side in ((0,2),(1,3)):
            window=profiles[y-4:y+5]
            if all(p and p[edge]==current[edge] for p in window):
                if smooth_width:
                    assert abs(previous[side]-current[side])<=1, f"Rim width jumps at {y+21}: {previous}, {current}, {following}"
                widths.add(current[side])
    if require_features:
        assert vertical_contacts, "Scene does not exercise a sloping bank"
        assert road_contacts, "Scene does not exercise rims crossing a road"
        assert different_widths, "Opposite banks have identical repeating teeth"
        assert len(widths)>=3, "Bank width does not vary over longer segments"
        assert any({1,12}<={p&15 for p in tiles[tile*32:tile*32+4]}
                   for tile in terrain), \
            "Shoreline does not use partial water/bank tiles"


def check_mountains_on_fine_terrain(sprites, config, terrain, tiles, images):
    origin_y = struct.unpack_from("<h", config, 4)[0]
    for block in range(6):
        x,y,address,_,size,options=struct.unpack_from("<hhHHBB",sprites,(block+2)*10)
        if address not in images:
            continue
        image=images[address]
        width=((size&15)+1)*4
        for sy in range(32):
            py=y+sy
            if not 21<=py<181:
                continue
            for sx in range(width):
                ix=width-1-sx if options&16 else sx
                if not ((image[sy*width//2+ix//2]>>(0 if ix&1 else 4))&15):
                    continue
                for px in (x+sx*2,x+sx*2+1):
                    if 0<=px<320:
                        # A two-logical-pixel gap, including diagonals, must
                        # separate every visible mountain pixel from the rim.
                        for cy in range(max(21,py-2),min(181,py+3)):
                            n=(cy-origin_y)%192
                            for cx in range(max(0,px-4),min(320,px+5)):
                                texture=terrain[n*40+cx//8]
                                pair=tiles[texture*32+(cx%8)//2]
                                assert ((pair>>(0 if cx&1 else 4))&15) not in (1,12), \
                                    f"Mountain touches water/bank: {px},{py}, nearby {cx},{cy}"


def check_bank_angle(config, terrain, tiles, river1=None, river2=None):
    """Measure the actual brown band normal to straight and sloping shores."""
    origin_y = struct.unpack_from("<h", config, 4)[0]
    profiles = []
    coarse = []
    for y in range(21,181):
        n=(y-origin_y)%192
        if river1 is not None:
            native_water=[x for x in range(16,80) if not (
                river1[n] & (128 >> ((x-16)//4)) if x<48 else
                river2[n] & (1 << ((x-48)//4)))]
            coarse.append((native_water[0],159-native_water[0]) if native_water else None)
        line=[tiles[terrain[n*40+x//4]*32+x%4]&15 for x in range(160)]
        water=[x for x,c in enumerate(line) if c==1]
        if not water:
            profiles.append(None)
            continue
        left,right=water[0],water[-1]
        lw=rw=0
        while left-lw-1>=0 and line[left-lw-1]==12:
            lw+=1
        while right+rw+1<160 and line[right+rw+1]==12:
            rw+=1
        profiles.append((left,right,lw,rw))
    groups={"vertical":[],"gentle":[],"steep":[]}
    for y in range(4,len(profiles)-4):
        window=(coarse if coarse else profiles)[y-4:y+5]
        if not all(window):
            continue
        for edge,width in ((0,2),(1,3)):
            positions=[p[edge] for p in window]
            steps=[b-a for a,b in zip(positions,positions[1:])]
            # Exclude a reversal: endpoint slope cannot describe a sharp tip.
            if min(steps)<0<max(steps):
                continue
            delta=abs(positions[-1]-positions[0])
            group="vertical" if not max(positions)-min(positions) else \
                "gentle" if 0<delta<=6 else "steep" if delta>=8 else None
            if group:
                # X is doubled on the canvas. Correct for tangent angle to
                # distinguish stroke thickness from a long horizontal join.
                groups[group].append(2*profiles[y][width]/math.sqrt(1+(delta/4)**2))
    assert all(len(values)>=2 for values in groups.values()), "Scene lacks three bank angles"
    means={name:sum(values)/len(values) for name,values in groups.items()}
    assert means["vertical"]>means["gentle"]>means["steep"], \
        f"Brown rim does not thin as angle from vertical increases: {means}"
    return means


def check_bank_detail(config, terrain, tiles, river1, river2):
    """A long native straight has the small water-edge bends seen on Atari XL."""
    origin_y=struct.unpack_from("<h",config,4)[0]
    profiles=[]
    for y in range(21,181):
        n=(y-origin_y)%192
        native=[x for x in range(16,80) if not (
            river1[n] & (128 >> ((x-16)//4)) if x<48 else
            river2[n] & (1 << ((x-48)//4)))]
        water=[x for x in range(16,80)
               if tiles[terrain[n*40+x//4]*32+x%4]&15==1]
        profiles.append((native[0],water[0]) if native and water else None)
    for y in range(len(profiles)-32):
        window=profiles[y:y+32]
        if not all(window) or len({p[0] for p in window})!=1:
            continue
        # Skip the end samples: smoothing may depend on a neighboring bend.
        cuts=[p[0]-p[1] for p in window[1:-1]]
        steps=[b-a for a,b in zip(cuts,cuts[1:]) if b!=a]
        reversals=sum(a*b<0 for a,b in zip(steps,steps[1:]))
        if min(cuts)==0 and max(cuts)==3 and reversals>=2:
            assert max(map(abs,steps))<=2, "Water edge jumps too far on a straight bank"
            return
    raise AssertionError("Native straight bank still lacks the reference's small water-edge bends")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build/cc65/release")
    parser.add_argument("--emulator", type=Path, default=ROOT / "tools/rp6502-emu.exe")
    args = parser.parse_args()
    build = args.build.resolve()
    sym = symbols(build / "riverraid.dbg")
    output = build / "checks"
    output.mkdir(exist_ok=True)
    count = 0

    def case(name, commands, fill="random", gameplay=True):
        nonlocal count
        # Allow the next loop to account for the last rendered frame, including
        # full resets/respawns. The exit case has already returned to the OS.
        if gameplay and not commands[-1].startswith("expect-exit"):
            commands = commands + ["run 2", "peek xram:0x009e 0 0"]
        script = output / f"{name}.script"
        script.write_text("\n".join(commands) + "\n", encoding="utf-8")
        process = subprocess.run([
            str(args.emulator.resolve()), str(build / "riverraid.rp6502"),
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

    dismiss_cover = ["wait xram:0x00b0 2 180", "press z", "run 3", "release z",
                     "wait xram:0x00b0 0 120"]
    title = dismiss_cover + ["wait xram:0x0080 82 240", "run 2", "peek xram:0x0080 0x52 3 3"]
    boot = title + [f'wait 0x{sym["ready"]:04x} 2 180', "run 60",
                    "peek xram:0x0080 0x52 3 3"]
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

    # Cover pixels and RGB555 endpoints are checked directly against the BMP,
    # not just the converter's output. Check every displayed fade step and
    # that holding a gameplay key across dismissal cannot start the game.
    bmp=(ROOT / "assets/cover.bmp").read_bytes()
    offset=struct.unpack_from("<I",bmp,10)[0]
    dib,w,h,_,_=struct.unpack_from("<IiiHH",bmp,14)
    rows=[bmp[offset+y*320:offset+(y+1)*320] for y in range(abs(h))]
    expected_pixels=b"".join(reversed(rows) if h>0 else rows)
    rgb=[tuple(v>>3 for v in bmp[14+dib+i*4:17+dib+i*4]) for i in range(256)]
    # Use the SDK's ROM parser to verify these are named files inside the
    # cartridge, loaded on demand rather than prepopulated XRAM chunks.
    sys.path.insert(0,str(ROOT / "tools"))
    from rp6502 import ROM
    rom=ROM()
    rom.add_rom_file(str(build / "riverraid.rp6502"))
    assets=dict(rom.assets)
    assert assets["cover.bin"]==expected_pixels
    assert assets["cover-fade.bin"]==(build / "cover_fade.bin").read_bytes()
    assert assets["cover-prompt.bin"]==(build / "cover_prompt.bin").read_bytes()
    assert not any(0x11000<=a<0x1f100 for a in rom.data), "Cover was preloaded to XRAM"

    def cover_palette(level):
        return b"".join(struct.pack("<H", (r*level//63) | ((g*level//63)<<6) |
                     ((b*level//63)<<11) | 32) for b,g,r in rgb)

    commands=["wait xram:0x00b0 1 180"]
    for level in range(1,64):
        commands += [f"wait xram:0x00b1 {level} 3", "dump xram:0x0400 512"]
    commands += ["wait xram:0x00b0 2 3", "dump xram:0x0280 14",
        "dump xram:0x1000 57600", "run 2", "mark", "run 240", "expect-same",
        # Lock LED bits must not be interpreted as held keyboard keys.
        "lock num", "lock caps", "lock scroll", "run 10", "peek xram:0x00b0 2",
        f'shot "{(output / "cover-full.png").as_posix()}"',
        "press space", "wait xram:0x00b0 3 3"]
    for level in reversed(range(64)):
        commands += [f"wait xram:0x00b1 {level} 3", "dump xram:0x0400 512"]
        if level==32:
            commands += [f'shot "{(output / "cover-half.png").as_posix()}"']
    commands += ["wait xram:0x00b0 4 3", "run 2", "mark", "run 20", "expect-same",
        f'shot "{(output / "cover-black.png").as_posix()}"', "release space",
        "wait xram:0x0080 82 240", "run 2", f'peek 0x{sym["ready"]:04x} 1',
        f'peek 0x{sym["start_level"]:04x} 1', "peek xram:0x008b 0"]
    _, buffers=case("cover-fades-and-wait",commands)
    assert buffers[:63]==[cover_palette(i) for i in range(1,64)], "Fade-in palette/frame mismatch"
    assert struct.unpack("<BBhhhhHH",buffers[63])==(0,0,0,30,320,180,0x1000,0x0400)
    assert buffers[64]==expected_pixels, "Cover pixels differ from original BMP"
    assert buffers[65:]==[cover_palette(i) for i in reversed(range(64))], "Fade-out palette/frame mismatch"

    _, buffers=case("cover-prompt-blink",["wait xram:0x00b0 1 180",
        "peek xram:0x02a4 0 255", "wait xram:0x02a4 222 90", "run 2",
        "dump xram:0x02a0 14", "dump xram:0x0800 80", "dump xram:0x0850 4",
        "dump xram:0x0400 512", "mark",
        f'shot "{(output / "cover-prompt-on.png").as_posix()}"',
        "run 30", "expect-changed", "peek xram:0x02a4 0 255",
        f'shot "{(output / "cover-prompt-off.png").as_posix()}"',
        "dump xram:0x0400 512", "run 30", "expect-same", "peek xram:0x02a4 222 0",
        "press q", "wait xram:0x00b0 3 3", "peek xram:0x02a4 0 255",
        "release q", "wait xram:0x0080 82 240", "run 2"])
    config,bitmap,palette,colors_on,colors_off=buffers
    assert struct.unpack("<BBhhhhHH",config)==(0,0,120,222,80,8,0x0800,0x0850)
    assert bitmap==assets["cover-prompt.bin"] and any(bitmap) and not any(bitmap[-10:])
    assert palette==struct.pack("<HH",32,0xffff), "Prompt is not opaque white on black"
    assert colors_on==colors_off, "Blink modified the cover palette"

    # Verify arbitrary, function and modifier keys, Escape and a key held
    # before fade-in; consumed keys must not trigger the game controls.
    for key in ("q","f3","p","escape","lctrl"):
        case(f"cover-key-{key}",["wait xram:0x00b0 2 180", f"press {key}", "run 3",
            f"release {key}", "wait xram:0x0080 82 240", "run 2",
            f'peek 0x{sym["ready"]:04x} 1', f'peek 0x{sym["start_level"]:04x} 1',
            "peek xram:0x008b 0"])
    case("cover-held-before-fade",["press enter", "wait xram:0x00b0 3 180",
        "wait xram:0x00b0 4 90", "run 3", "peek xram:0x0080 0",
        "release enter", "wait xram:0x0080 82 240", "run 2",
        f'peek 0x{sym["ready"]:04x} 1'])
    for fill in ("0","255"):
        case(f"cover-wait-fill-{fill}",["wait xram:0x00b0 2 180", "run 2", "mark",
            "run 120", "expect-same", "peek xram:0x00b0 2", "peek xram:0x00b1 63"],
            fill=fill,gameplay=False)

    # Staging must not alter the live VGA descriptors until the next VSYNC.
    # The renderer then prepares the following frame; it must not overwrite
    # descriptors already being scanned out during the displayed frame.
    _, buffers=case("vsync-world-presentation",fixture+["run 2",
        "dump xram:0x0200 16", "dump xram:0x0300 10",
        poke(0xb3,90), poke(sym["ring_top"],17), "dump xram:0x0200 16",
        "dump xram:0x0300 10", "run 1",
        f'dump 0x{sym["terrain"]:04x} 16', f'dump 0x{sym["sprites"]:04x} 10',
        "dump xram:0x0200 16", "dump xram:0x0300 10",
        "run 1", "dump xram:0x0200 16", "dump xram:0x0300 10"])
    assert buffers[0]==buffers[2], "Changing native terrain altered live VGA descriptors"
    assert buffers[1]==buffers[3]==buffers[7], "Preparing sprites altered the displayed frame"
    # The script can stop during the short VSYNC copy: Y is written before
    # sprites. Allow that transient in the top blank lines, before the river.
    assert buffers[6] in (buffers[0],buffers[4])
    assert buffers[4]==buffers[8] and buffers[5]==buffers[9], "World descriptors were not presented together"
    assert struct.unpack_from("<h",buffers[4],4)[0]==4
    assert struct.unpack_from("<h",buffers[5],0)[0]==180

    footer=(build / "demo_footer.bin").read_bytes()
    width=len(footer)//8
    # Synchronize with the first displayed scene, rather than ROM loading.
    # Check the last delayed frame and the first caption/demo frame together.
    _, buffers=case("demo-startup-delay",title+[
        "dump xram:0x0260 14", "dump xram:0x0200 16",
        "run 175", f'wait 0x{sym["demo_wait"]:04x} 1 8', "peek xram:0x0262 0 0",
        f'peek 0x{sym["ready"]:04x} 1', "dump xram:0x0200 16",
        f'wait 0x{sym["ready"]:04x} 2 3', "run 2",
        "dump xram:0x0260 14", "dump xram:0x0200 16",
        "run 120", "dump xram:0x0200 16", "peek 0xc6 0",
        "dump xram:0x0080 32", "peek xram:0x0302 0 255"])
    caption_before,river_before,river_last,caption_after,river_after,river_later,state=buffers
    assert struct.unpack_from("<h",caption_before,2)[0]==0
    assert river_before==river_last, "River moved before the demo started"
    assert struct.unpack_from("<h",caption_after,2)[0]<0
    assert river_after!=river_later, "Demo did not scroll the river"
    assert state[2]==3 and state[4]==0 and score(state)==1, "Demo changed player lives/score"

    case("demo-start-before-delay",title+["press space", "run 140", "release space",
        "run 4", f'peek 0x{sym["ready"]:04x} 0', "peek xram:0x0082 1",
        "peek xram:0x0084 3 1"])

    _, buffers=case("demo-startup-pause",title+["press p", "run 3", "release p", "run 3",
        f'dump 0x{sym["demo_wait"]:04x} 1', "mark", "run 180", "expect-same",
        f'dump 0x{sym["demo_wait"]:04x} 1']+resume+[
        f'wait 0x{sym["ready"]:04x} 2 180', "run 3", "peek 0xc6 0"])
    assert buffers[0]==buffers[1], "Pause did not stop the startup countdown"

    _, buffers=case("demo-footer-scroll",boot+["dump xram:0x0260 14", "run 60",
        "dump xram:0x0260 14",f"dump xram:0x3800 {len(footer)}",
        "dump xram:0x0720 14", "dump xram:0x06b4 10",
        f'shot "{(output / "demo-caption.png").as_posix()}"'])
    first,second,image,palette,logo=buffers
    assert first[:2]==bytes((1,0)) and first[4:]==second[4:]
    x1,x2=(struct.unpack_from("<h",cfg,2)[0] for cfg in (first,second))
    assert (x1-x2)%(width*2)==60, "Demo caption did not scroll left at one pixel/frame"
    assert struct.unpack_from("<hhHH",second,6)==(width*2,8,0x3800,0x0720)
    assert struct.unpack_from("<h",second,4)[0]==222
    assert struct.unpack_from("<h",logo,2)[0]<0, "Static logo covers demo text"
    assert image==footer, "Caption asset was not loaded into XRAM"
    assert int.from_bytes(palette[4:6],"little")==((23<<11)|(23<<6)|23|32)
    # Ten eight-pixel cells precede the raised TM, as in the Atari caption.
    for y,pattern in enumerate(("XXX.X...X", ".X..XX.XX", ".X..XXXXX", ".X..X.X.X", ".X..X...X")):
        assert image[y*width+80:y*width+89]==bytes(0x22 if p=="X" else 0 for p in pattern)
    assert not any(image[:80]), "Normal title lettering is not below superscript TM"
    for y,pattern in enumerate(("XXXXX.","XX..XX","XX..XX","XXXXX.","XX.XX.","XX..XX"),1):
        assert image[y*width:y*width+6]==bytes(0x22 if p=="X" else 0 for p in pattern), "Caption R differs from reference"

    _, buffers=case("demo-footer-wrap-and-gray",boot+["dump xram:0x0260 14",
        f"run {width*2}","dump xram:0x0260 14", "peek xram:0x0724 247 189"])
    assert buffers[0]==buffers[1], "Demo caption did not wrap after a complete pass"
    case("demo-footer-pause",boot+["press p", "run 3", "release p", "run 3",
        "mark", "run 60", "expect-same"])
    _, buffers=case("demo-footer-start-and-return",start+["dump xram:0x0260 14",
        "dump xram:0x06b4 10", "press f2", "run 3", "release f2", "run 3",
        "dump xram:0x0260 14", "dump xram:0x06b4 10"])
    playing,logo_playing,demo,logo_demo=buffers
    assert struct.unpack_from("<h",playing,4)[0]<0
    assert struct.unpack_from("<hh",logo_playing,0)==(48,222)
    assert struct.unpack_from("<h",demo,4)[0]==222
    assert struct.unpack_from("<h",logo_demo,2)[0]<0

    # A held F3 must advance once, update both native player states, and show
    # the selected bridge using the real HUD sprites, including two digits.
    commands=boot+["peek 0xbd 1"]
    for level in (5,20,50,1):
        commands += ["press f3", "run 3", f"peek 0xbd {level}", f"peek 0xc2 {level}",
                     f'peek 0x{sym["start_level"]:04x} {level}', "run 32",
                     f"peek 0xbd {level}", "dump xram:0x060a 20",
                     "release f3", "run 3"]
    _, hud_numbers=case("bridge-difficulty-cycle",commands)
    for level, sprites in zip((5,20,50,1),hud_numbers):
        for digit in (0,1):
            _,y,image,_,_,_=struct.unpack_from("<hhHHBB",sprites,digit*10)
            assert image==0x9e00+(level//10 if digit==0 else level%10)*32
            assert (y>=0)==(digit==1 or level>=10), "Incorrect BRIDGE digit visibility"

    case("bridge-difficulty-paused-restart",fixture+[poke(0xcd+10,40),
         "press f3", "run 3", "release f3", "run 3", "peek xram:0x0085 5",
         "peek xram:0x008b 0", "peek xram:0x0090 88 88 88 88 88 0",
         "press p", "run 3", "release p", "run 3",poke(0xbd,7),
         "press r", "run 3", "release r", "run 3", "peek 0xbd 5", "peek 0xc2 5",
         "peek xram:0x008b 0"])

    commands=boot+["press f2", "run 2", "release f2", "run 2", "peek 0x80 1"]
    for _ in range(2):
        commands += ["press f3", "run 3", "release f3", "run 3"]
    case("bridge-difficulty-two-players",commands+["peek 0xbd 20", "peek 0xc2 20",
         "peek 0xf4 0", "press space", "wait 0xc6 0 180", "release space", "run 3",
         "press p", "run 3", "release p", "run 3",
         poke(0xb3,4)]+resume+["wait 0xf4 1 240", "wait 0xc6 48 300", "run 3",
         "peek 0xbd 20", "peek 0xc2 20"])

    case("bridge-difficulty-respawn",fixture+[poke(sym["start_level"],20),
         poke(0xbd,50),poke(0xb3,4)]+resume+["wait 0xc6 48 300", "run 3",
         "peek 0xbd 50"])

    def object_at(block, kind, x=76):
        coarse, fine = divmod(x+1, 15)
        size = 7 if kind == 8 else 5 if kind in (7, 9) else 0
        return [poke(0xa0+block, kind), poke(0x94+block, coarse),
                poke(0x9a+block, ((fine^7)<<4)|size)]

    # Wider mountains must remain on land, including curves, islands and
    # mirrored images. Paused fixtures supply known original PF patterns and
    # the corresponding visible tile map; the shipping renderer places them.
    commands = pause + [poke(0xa0, [9]*6), poke(sym["ring_top"], 0), poke(0xb2, 180)]
    mountain_scenes = (
        ([255]*16, [15]*16),
        ([255]*6+[255,254,252,248,252,254]+[255]*4, [0]*16),
        ([192]*16, [192]*16),  # Island too narrow for the new sprite.
        ([192]*16, [240]*16),  # Island wide enough for the whole silhouette.
    )
    for scene, (p1, p2) in enumerate(mountain_scenes):
        # Change native pointers with each scene to exercise cache invalidation.
        commands += [poke(0xcc00+scene*16, p1), poke(0xcc80+scene*16, p2),
            poke(0x8e, [0]*6), poke(0xa6, [scene*16]*6), poke(0xac, [128+scene*16]*6)]
        for block, x in enumerate((54, 90, 71, 54, 90, 71)):
            commands += object_at(block, 9, x)
            if block&1:
                fine = (x+1)%15
                commands += [poke(0x9a+block, ((fine^7)<<4)|13)]
        for offset in (0,31):
            tiles = []
            for y in range(192):
                index = ((159-y+offset)&31)>>1
                for tile in range(40):
                    mirror = tile if tile<20 else 39-tile
                    land = (mirror<4 or (p1[index] & (128>>(mirror-4)) if mirror<12
                            else p2[index] & (1<<(mirror-12))))
                    tiles.append(2 if land else 1)
            # The widest decorative band consumes eight native ground
            # pixels. Include its horizontal and vertical joins in fixtures.
            for y in range(192):
                for tile in range(40):
                    if tiles[y*40+tile]==2 and any(
                        tiles[((y+dy)%192)*40+tile+dx]==1
                        for dy in range(-2,3) for dx in range(-2,3)
                        if 0<=tile+dx<40):
                        tiles[y*40+tile]=7
            commands += [poke(0x8b, offset)]
            commands += [poke(0x0800+i, tiles[i:i+192]).replace("poke ", "poke xram:", 1)
                         for i in range(0,len(tiles),192)]
            commands += ["run 3",
                "dump xram:0x0300 100", "dump xram:0x0200 16", "dump xram:0x0800 7680"]
        commands += [f'shot "{(output / f"mountains-{scene}.png").as_posix()}"']
    commands += ["dump xram:0x9200 512", "dump xram:0x3600 512", "dump xram:0x5800 512",
                 "dump xram:0x2700 3136"]
    _, mountain_buffers = case("mountains-stay-on-land", commands)
    mountain_images = {0x9200:mountain_buffers[-4], 0x3600:mountain_buffers[-3],
                       0x5800:mountain_buffers[-2]}
    mountain_tiles=mountain_buffers[-1]
    assert 3 in [(p>>shift)&15 for p in mountain_images[0x9200] for shift in (0,4)]
    assert 2 in [(p>>shift)&15 for p in mountain_images[0x3600] for shift in (0,4)]
    assert 3 not in [(p>>shift)&15 for p in mountain_images[0x3600] for shift in (0,4)]
    seen_images = set()
    for sample in range(len(mountain_scenes)*2):
        sprites, config, tiles = mountain_buffers[sample*3:sample*3+3]
        origin_y = struct.unpack_from("<h", config, 4)[0]
        previous = mountain_buffers[(sample-1)*3] if sample&1 else None
        visible = 0
        for block in range(6):
            x, y, address, _, size, options = struct.unpack_from("<hhHHBB", sprites, (block+2)*10)
            image = mountain_images[address]
            seen_images.add(address)
            if previous is not None:
                assert x == struct.unpack_from("<h", previous, (block+2)*10)[0], \
                    "Mountain slides sideways when scrolling"
                assert address==struct.unpack_from("<H",previous,(block+2)*10+4)[0], \
                    "Mountain changes silhouette while scrolling"
            width = ((size&15)+1)*4
            for sy in range(32):
                py = y+sy
                if not 21<=py<181:
                    continue
                for sx in range(width):
                    ix = width-1-sx if options&16 else sx
                    color = (image[sy*width//2+ix//2] >> (0 if ix&1 else 4))&15
                    if not color:
                        continue
                    for px in (x+sx*2, x+sx*2+1):
                        if not 0<=px<320:
                            continue
                        visible += 1
                        row = (py-origin_y)%192
                        assert tiles[row*40+px//8] != 1, \
                            f"Mountain covers water: scene {sample//2}, block {block}, pixel {px},{py}"
        assert visible > 100, "Mountain fixture did not display its sprites"
        check_mountains_on_fine_terrain(sprites,config,tiles,mountain_tiles,mountain_images)
    assert seen_images==set(mountain_images), "Game does not display all three mountain silhouettes"
    # The new silhouette has one peak and fits between the old two in area.
    areas={address:sum(bool((p>>shift)&15) for p in image for shift in (0,4))
           for address,image in mountain_images.items()}
    assert areas[0x3600]<areas[0x5800]<areas[0x9200]

    a, _ = case("title-random", boot + ["crc", f'shot "{(output / "title.png").as_posix()}"'])
    b, _ = case("title-zero", boot + ["crc"], "0")
    assert a == b, "Initial image depends on RAM contents"

    # Keep the title's road on screen; the attract river now scrolls it away.
    _, buffers = case("river-bank-contours", title + [
        "press p", "run 3", "release p", "run 3",
        "dump xram:0x0200 16", "dump xram:0x0800 7680", "dump xram:0x2700 3136",
        f'dump 0x{sym["river1"]:04x} 192', f'dump 0x{sym["river2"]:04x} 192',
        f'dump 0x{sym["river_left"]:04x} 192', f'dump 0x{sym["river_right"]:04x} 192',
        f'dump 0x{sym["player_outer_left"]:04x} 192', f'dump 0x{sym["player_outer_right"]:04x} 192',
        f'dump 0x{sym["player_island_left"]:04x} 192', f'dump 0x{sym["player_island_right"]:04x} 192',
        f'shot "{(output / "river-banks.png").as_posix()}"'])
    check_terrain_pixels(*buffers[:7])
    check_player_ground(*buffers[:3],*buffers[7:11])
    check_bank_contours(*buffers[:3])
    check_bank_angle(*buffers[:3],*buffers[3:5])
    check_bank_detail(*buffers[:3],*buffers[3:5])

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

    _, jet_buffers = case("jet-bitmap", pause + ["dump 0xba 2","dump 0xc000 4096","dump xram:0x9600 80"])
    pointer,native,jet=jet_buffers
    address=int.from_bytes(pointer,"little")-0xc000
    assert 0<=address and address+18<len(native), "Unexpected native jet bitmap page"
    for y in range(20):
        bits=native[address+18-y] if y<18 else 0
        for x in range(8):
            color=(jet[y*4+x//2]>>(0 if x&1 else 4))&15
            assert color==int(bool(bits&(128>>x))), f"Jet bitmap changed at {x},{y}"

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
        "dump xram:0x2700 3136", f'dump 0x{sym["river1"]:04x} 192',
        f'dump 0x{sym["river2"]:04x} 192',
        f'dump 0x{sym["river_left"]:04x} 192', f'dump 0x{sym["river_right"]:04x} 192',
        f'shot "{(output / "bridge.png").as_posix()}"'])
    shapes, sprites, config, terrain, bridge, tiles, river1, river2, river_left, river_right = buffers
    check_terrain_pixels(config, terrain, tiles, river1, river2, river_left, river_right)
    # This paused fixture jumps OFFSET and replaces the native generator
    # context above retained title rows. Their old tangent samples do not
    # describe the new context; slope smoothness is checked on natural scenes.
    check_bank_contours(config, terrain, tiles, smooth_width=False)
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

    road_scene = (output / "bridge-bank-alignment.script").read_text(encoding="utf-8").splitlines()
    road_scene = road_scene[:road_scene.index("dump 0xa0 6")]
    case("5200-enemies-preview", road_scene + object_at(block-1,11,76) + [
        poke(sym["tanks"]+block*5,[76,0,1,0,0]), "run 4",
        f'shot "{(output / "enemies-5200.png").as_posix()}"'])

    # F5 selects straight missiles, so guidance cannot pull a missed shot
    # back into the bridge on a later frame.
    for missile_x, expected in ((63, 0), (95, 500)):
        _, states = case(f"bridge-edge-{missile_x}", fixture + clear_score +
            object_at(1, 8, 63) + [poke(0xb2, 43), poke(0xf5, missile_x),
                "press f5", "run 2", "release f5", "run 2"] + resume + dump)
        assert score(states[-1]) == expected, "Bridge collision disagrees with its visible edge"

    for kind, points in ((4, 100), (5, 60), (7, 30), (8, 500), (10, 80), (11, 60)):
        _, states = case(f"score-object-{kind}", fixture + clear_score + object_at(1, kind) + [
            poke(0xb2, 43), poke(0xf5, 81)] + resume + dump)
        assert score(states[-1]) == points, f"Object {kind}: score {score(states[-1])}"
        if kind == 8:
            assert states[-1][5] == 1, "Bridge advances the section when it scrolls out, not on hit"

    # 5200 additions use uploaded readable assets and actual game collisions.
    _, images = case("5200-enemy-bitmaps", boot + [
        "dump xram:0x9d00 128", "dump xram:0x9d80 96", "dump xram:0x05e0 6"])
    balloon, tank, palette = images
    assert balloon[9*4:15*4] == bytes([ink*17 for ink in range(4,10) for _ in range(4)])
    assert tank[4*6:5*6] == bytes([0x11]*4+[0x10,0])
    assert palette[:4] == bytes([0,0,32,0]), "Black tank body must be opaque"
    case("balloon-crash", fixture + object_at(0,11) + resume + ["peek xram:0x0082 2"])
    _, states = case("balloon-bank-bounce", fixture + [poke(0xbd,2), poke(0x8f,64)] +
        object_at(1,11,8) + resume + ["dump 0x9b 1", "peek 0xa1 11"])
    assert states[-1][0]&8, "Balloon failed to reverse at the bank"

    # The two native IDs are rotor phases. Both aircraft variants preserve
    # those phases; only type 2 launches the horizontal pale projectile.
    _, images=case("helicopter-reference-bitmaps",boot + [
        "dump xram:0x8a00 128","dump xram:0x8a80 128",
        "dump xram:0x8c00 128","dump xram:0x8c80 128",
        "dump xram:0xbf90 16"])
    for index,image in enumerate(images[:4]):
        assert image[13*4:14*4]==bytes([0x55 if index&1 else 0x44]*4)
        assert not any(image[:8*4]) and not any(image[17*4:])
    assert images[0][8*4:10*4]!=images[2][8*4:10*4], "Rotor frames do not differ"
    assert images[0][11*4:12*4]==images[2][11*4:12*4], "Rotor animation changes the fuselage"
    assert images[-1]==bytes([0]*5+[0xee,0xee]+[0]*9)
    for level in (4,5,20):
        commands=fixture + [poke(0xbd,level),poke(sym["helicopter_types"],[0]*6),
            poke(sym["helicopter_spawn"],0)]
        for _ in range(12):
            commands += object_at(2,5,76) + [poke(sym["helicopter_types"]+2,0),
                "run 2",f'dump 0x{sym["helicopter_types"]+2:04x} 1',"dump xram:0x0328 10"]
        _, samples=case(f"helicopter-frequency-level-{level}",commands)
        firing=[]
        for i,(state,descriptor) in enumerate(zip(samples[::2],samples[1::2])):
            expected=level>=5 and i%4==3
            assert (state[0]==2)==expected, "Firing helicopter frequency or minimum level differs"
            assert (struct.unpack_from("<H",descriptor,4)[0]==0x8a80)==expected
            firing.append(state[0]==2)
        assert sum(firing)==(3 if level>=5 else 0)
    commands=boot + [poke(0xbd,5),poke(sym["helicopter_types"],[0]*6),
        poke(sym["helicopter_spawn"],0)]
    for _ in range(12):
        commands += ["run 240","dump 0xa0 18","dump xram:0x0300 200"]
    _, samples=case("helicopter-natural-variants",commands)
    types=set()
    for state,descriptors in zip(samples[::2],samples[1::2]):
        for n,kind in enumerate(state[:6]):
            if kind in (5,6):
                address=struct.unpack_from("<H",descriptors,(n+2)*10+4)[0]
                types.add(address in (0x8a80,0x8c80))
    assert types=={False,True}, "Native course does not show both helicopter variants"
    for kind in (0,1):
        for direction in (0,1):
            _, buffers=case(f"helicopter-firing-{kind}-{direction}",fixture +
                object_at(2,5,76) + [poke(0xbd,5),poke(sym["helicopter_types"]+2,kind+1),
                poke(0x9c,0x50|direction*8),
                poke(sym["helicopter_shots"],[0]*36)] + resume + [
                f'dump 0x{sym["helicopter_shots"]:04x} 36',"dump xram:0x0300 200",
                "press p","run 3","release p","run 3",
                f'dump 0x{sym["helicopter_shots"]:04x} 36',"run 60",
                f'dump 0x{sym["helicopter_shots"]:04x} 36',
                f'shot "{(output / f"helicopter-{kind}-{direction}.png").as_posix()}"'])
            state,descriptors,paused0,paused1=buffers
            assert bool(state[2*6+4])==bool(kind), "Wrong helicopter type fired"
            assert paused0==paused1, "Helicopter fire moves during pause"
            address=struct.unpack_from("<H",descriptors,40+4)[0]
            assert address in ((0x8a80,0x8c80) if kind else (0x8a00,0x8c00))
            if kind:
                sx,sy=struct.unpack_from("<hh",state,12)
                assert sy==76 and (58<=sx<=64 if direction else 88<=sx<=94), \
                    f"Helicopter shot moves in the wrong direction: {sx},{sy}"
                assert struct.unpack_from("<H",descriptors,120+4)[0]==0xbf90
    for y,crashes in ((145,True),(140,False)):
        case(f"helicopter-shot-jet-{y}",fixture + [
            poke(sym["helicopter_shots"],list(struct.pack("<hh2B",76,y,1,1)))] +
            resume + [f"peek xram:0x0082 {2 if crashes else 1}"])
    _, states=case("helicopter-shot-restart",fixture + [
        poke(sym["helicopter_shots"],list(struct.pack("<hh2B",60,60,1,0)))] +
        resume + ["press r","run 4","release r","run 4",
        f'dump 0x{sym["helicopter_shots"]:04x} 36'])
    assert states[-1]==bytes(36), "Restart retained helicopter fire"
    crowded=fixture + [poke(0xbd,5),poke(sym["helicopter_types"],[2]*6)]
    for block in range(6):
        crowded+=object_at(block,5,50)
    case("helicopters-frame-budget",crowded + resume + ["run 120"])

    # Rims count as shore for the dash, even though they are safe for the
    # player's plane. Check outer banks and both island-facing channels.
    for island in (False,True):
        for direction in (0,1):
            x=(102 if direction else 52) if island else (44 if direction else 110)
            _, states=case(f"helicopter-shot-shore-{island}-{direction}",fixture + [
                poke(sym["river1"],[255]*192),poke(sym["river2"],[255]*192),
                poke(sym["river_left"],[20 if island else 42]*192),
                poke(sym["river_right"],[60 if island else 80]*192),
                poke(sym["helicopter_shots"],list(struct.pack("<hh2B",x,76,1,direction))),
                "run 3","dump xram:0x0364 10"] + resume + [
                f'dump 0x{sym["helicopter_shots"]:04x} 6',"dump xram:0x0364 10"])
            before,state,after=states
            assert struct.unpack_from("<h",before,2)[0]!=-256
            assert state[4]==0 and struct.unpack_from("<h",after,2)[0]==-256, \
                "Helicopter projectile passed through the bank or island"
    for direction in (0,1):
        x=44 if direction else 100
        _, states=case(f"helicopter-shot-stays-in-water-{direction}",fixture + [
            poke(sym["river1"],[255]*192),poke(sym["river2"],[255]*192),
            poke(sym["river_left"],[42]*192),poke(sym["river_right"],[80]*192),
            poke(sym["helicopter_shots"],list(struct.pack("<hh2B",x,76,1,1-direction)))] +
            resume + [f'dump 0x{sym["helicopter_shots"]:04x} 6'])
        assert states[0][4]==1, "Water incorrectly stops a helicopter projectile"

    # Watch each frame at the bank: the spent dash must be replaced at the
    # helicopter's muzzle with no inactive frame or fixed firing delay.
    for direction in (0,1):
        commands=fixture + object_at(2,5,76) + [
            poke(0xbd,5),poke(sym["helicopter_types"]+2,2),
            poke(0x9c,0x50|direction*8),
            poke(sym["river1"],[255]*192),poke(sym["river2"],[255]*192),
            poke(sym["river_left"],[42]*192),poke(sym["river_right"],[80]*192),
            poke(sym["helicopter_shots"],[0]*36),
            poke(sym["helicopter_shots"]+12,
                 list(struct.pack("<hh2B",40 if direction else 112,76,1,direction))),
            "press p"]
        for frame in range(80):
            # Hold the source away from the banks and within this block;
            # otherwise native movement eventually blocks its muzzle.
            commands += object_at(2,5,76) + [poke(0x9c,0x50|direction*8),
                poke(0x8b,0),poke(0xb5,[0,2]),
                "run 1",f'dump 0x{sym["helicopter_shots"]+12:04x} 6']
            if frame==2:
                commands += ["release p"]
        _, samples=case(f"helicopter-shot-immediate-refire-{direction}",commands)
        positions=[struct.unpack_from("<h",s)[0] for s in samples]
        assert all(s[4]==1 for s in samples), "A bank hit left a gap before the next shot"
        assert any(64<=x<=76 if direction else 76<=x<=88 for x in positions[:6]), \
            "The next shot was not launched immediately at the helicopter's muzzle"
        resets=sum((b>a if direction else b<a) for a,b in zip(positions,positions[1:]))
        assert resets>=3, "Helicopter still waits between shots"

    # Re-firing must still respect the source type and the muzzle's water.
    for kind,x in ((0,76),(1,76),(2,112)):
        _, states=case(f"helicopter-shot-refire-blocked-{kind}",fixture +
            object_at(2,5 if kind else 0,x) + [
            poke(0xbd,5),poke(sym["helicopter_types"]+2,kind),
            poke(sym["river1"],[255]*192),poke(sym["river2"],[255]*192),
            poke(sym["river_left"],[0 if kind==2 else 42]*192),
            poke(sym["river_right"],[0 if kind==2 else 80]*192),
            poke(sym["helicopter_shots"]+12,list(struct.pack("<hh2B",112,76,1,0)))] +
            resume + [f'dump 0x{sym["helicopter_shots"]+12:04x} 6',"peek xram:0x0082 1"])
        assert not states[0][4], "An absent/type-1 helicopter or blocked muzzle fired"

    _, states=case("helicopter-type-block-scroll",fixture + object_at(2,5,76) + [
        poke(0xbd,5),poke(sym["helicopter_types"],[0,0,2,0,0,0]),
        poke(0x8b,31),poke(0xb5,254),poke(0xb6,2)] + resume + [
        "dump 0xa0 6",f'dump 0x{sym["helicopter_types"]:04x} 6'])
    assert states[0][1] in (5,6) and states[1][1]==2, "Scrolling changed the helicopter's type"

    def tank_at(block, x):
        return [poke(sym["tanks"]+block*5, [x,0,1,0,0])]

    for x, points in ((40,250),(76,750)):
        _, states = case(f"tank-score-{points}", fixture + clear_score + object_at(1,8,63) +
            tank_at(1,x) + [poke(0xb2,45),poke(0xf5,x+3)] + resume + dump + ["dump 0xa1 1"])
        assert score(states[0]) == points, f"Tank at {x}: score {score(states[0])}"
        assert (states[1][0]==8) == (points==250), "Tank/bridge destruction disagrees with score"
    _, states = case("tank-on-bridge-edge-hit", fixture + clear_score + object_at(1,8,63) +
        tank_at(1,68) + [poke(0xb2,43),poke(0xf5,95),"press f5","run 2",
        "release f5","run 2"] + resume + dump)
    assert score(states[-1])==750, "Bridge hit must include the tank bonus"
    case("tank-crash", fixture + object_at(0,8,63) + tank_at(0,76) + resume + [
        "peek xram:0x0082 2"])
    for reserves in (24,72):
        _, states = case(f"tank-bonus-life-{reserves}", fixture + [
            poke(0xcd+n*2,v) for n,v in enumerate((88,88,72,56,40,0))] +
            object_at(1,8,63) + tank_at(1,40) + [poke(0xc0,reserves),
            poke(0xb2,45),poke(0xf5,43)] + resume + dump)
        assert score(states[-1]) == 10000 and states[-1][4] == (4 if reserves==24 else 9)
    _, states = case("tank-maximum-score", fixture + [
        poke(0xcd+n*2,v) for n,v in enumerate((72,72,72,56,40,0))] +
        object_at(1,8,63) + tank_at(1,40) + [poke(0xb2,45),poke(0xf5,43)] + resume + dump)
    assert states[-1][16:22] == bytes([80]*6) and states[-1][2] == 2

    _, buffers = case("tank-driving-pause-restart", fixture + object_at(2,8,63) + [
        "run 3", "dump xram:0x0300 160", "run 60", "dump xram:0x0300 160"] +
        resume + ["run 20", "dump xram:0x0300 160", "press r", "run 4", "release r", "run 4",
        "dump xram:0x0300 160"])
    initial, paused_tanks, moving, restarted = buffers
    assert initial[120:130] == paused_tanks[120:130], "Tank moves while paused"
    x0,y0,image0,_,_,_ = struct.unpack_from("<hhHHBB",initial,120)
    assert image0 in (0x9d80,0xbf00) and y0==93
    assert struct.unpack_from("<h",moving,120)[0] != x0, "Tank does not drive"
    assert all(struct.unpack_from("<h",restarted,(10+n)*10+2)[0]==-256 for n in range(6)), \
        "Restart retained road tanks"

    _, buffers = case("tank-block-scroll", fixture + object_at(2,8,63) + tank_at(2,54) + [
        poke(0x8b,31),poke(0xb5,254),poke(0xb6,2)] + resume + [
        "dump 0xa0 6",f'dump 0x{sym["tanks"]:04x} 30',"dump xram:0x0300 160"])
    ids, tanks, sprites = buffers
    assert ids[1]==8 and tanks[5+2]==1 and 54<=struct.unpack_from("<h",tanks,5)[0]<=58
    assert struct.unpack_from("<H",sprites,110+4)[0] in (0x9d80,0xbf00)

    # Shoreline tanks are independent of bridge tanks. A controlled 40..120
    # corridor lets both banks and the safe-round / dangerous-splash rule be
    # exercised against the actual native jet and missile bitmaps.
    bank_fixture = fixture + [poke(0xbd,7),
        poke(sym["bank_tanks"],[0]*26),
        poke(sym["river1"],[0xfc]*192),
        poke(sym["river_left"],[40]*192),poke(sym["river_right"],[80]*192),
        poke(sym["player_outer_left"],[40]*192),
        poke(sym["player_outer_right"],[120]*192),
        poke(sym["player_island_left"],[0]*192),
        poke(sym["player_island_right"],[0]*192)]

    def bank_at(x=0, y=40, side=0, phase=0, shot_x=0, target=0, timer=0):
        return [poke(sym["bank_tanks"],list(struct.pack("<hhh7B",
            x,y,shot_x,side,1,90 if phase else 0,phase,target,timer,0)))]

    # Both 9x9 drawings are packed into 12x16 storage. Padding must remain
    # transparent, mirrored storage must not move the visible tank, and the
    # ninth column must collide in both directions.
    _, buffers=case("bank-tank-wider-bitmaps",bank_fixture + bank_at(x=29) + [
        poke(sym["bank_tanks"]+13,list(struct.pack("<hhh7B",122,80,0,1,1,90,0,0,0,122))),
        "run 3","dump xram:0x9d80 96","dump xram:0xbf00 96",
        "dump xram:0x03a0 40"])
    a,b,descriptors=buffers
    assert a[:36]==b[:36] and a[54:]==b[54:], "Track animation changes the body"
    assert a[36:54]!=b[36:54], "Track animation frames are identical"
    assert all((p>>shift)&15 in (0,1) for p in a+b for shift in (0,4)), "Tank has non-black ink"
    for image in (a,b):
        lit=[(x,y) for y in range(16) for x in range(12)
            if (image[y*6+x//2]>>(0 if x&1 else 4))&15]
        assert max(x for x,y in lit)==8 and max(y for x,y in lit)==8
    for slot,side in ((0,0),(2,1)):
        sx,sy,_,_,size,options=struct.unpack_from("<hhHHBB",descriptors,slot*10)
        assert size==0x32 and bool(options&16)==bool(side)
        assert sx==(119 if side else 29)*2 and sy==21+(80 if side else 40)+8
    for side in (0,1):
        for column,hits in ((8,True),(9,False)):
            x=122 if side else 29
            _, states=case(f"bank-tank-ninth-column-{side}-{column}",
                bank_fixture + clear_score + bank_at(x=x,y=96,side=side) + [
                "press f5","run 2","release f5","run 2",
                poke(0xb2,45),poke(0xf5,x+column)] + resume + dump + [
                f'dump 0x{sym["bank_tanks"]:04x} 13'])
            assert score(states[0])==(250 if hits else 0), "Ninth-column hit differs from drawing"
            assert (states[1][7]==2)==hits

    # Repeated independent shots must vary, and the whole largest explosion
    # must fit in actual water across bends and on either side of an island.
    for shape in ("straight","bend","island","island-bend","narrow","closed"):
        left=[40]*192; right=[80]*192
        if shape.startswith("island"):
            left=[20]*192; right=[60]*192
        if "bend" in shape:
            for y in range(41,57):
                left[y]+=y-41
                if shape.startswith("island"):
                    right[y]-=(y-41)//2
        if shape=="narrow":
            right=[44]*192
        if shape=="closed":
            right=[40]*192
        for side in (0,1):
            commands=bank_fixture + [poke(sym["ring_top"],0),
                poke(sym["river_left"],left),poke(sym["river_right"],right)]
            for attempt in range(12):
                # Keep the terrain stationary during six active frames.
                commands+=bank_at(x=122 if side else 30,side=side) + [
                    poke(0xb5,0),poke(0x8c,0)] + resume + [
                    f'dump 0x{sym["bank_tanks"]:04x} 13',
                    "press p","run 3","release p","run 3"]
            _, samples=case(f"bank-random-range-{shape}-{side}",commands)
            targets=set()
            for state in samples:
                if shape in ("narrow","closed"):
                    assert state[9]==0, "Tank fired without room for its explosion"
                    continue
                assert state[9] in (1,2), "Tank did not fire into available water"
                assert struct.unpack_from("<h",state,2)[0]==40, "Fixture scrolled"
                target=state[10]; targets.add(target)
                for y in range(41,57):
                    for x in range(target,target+8):
                        mx=x if x<80 else 159-x
                        assert left[y]<=mx<right[y], \
                            f"Tank aimed outside water at {x},{y} ({shape}, side {side})"
                        if right[y]<80:
                            assert (x>=80)==bool(side), "Tank shot across an island"
            if shape not in ("narrow","closed"):
                assert len(targets)>=5, f"Tank range does not vary: {targets}"

    for side in (0,1):
        _, buffers = case(f"bank-tank-approach-{side}", bank_fixture +
            bank_at(x=160 if side else -8,side=side) + resume + [
            "run 90",f'dump 0x{sym["bank_tanks"]:04x} 13',
            "dump xram:0x03a0 20"])
        tank_state, descriptors = buffers
        assert struct.unpack_from("<h",tank_state)[0] == (122 if side else 29)
        assert tank_state[7]==1 and tank_state[9] in (1,2), "Tank did not fire at water"
        assert struct.unpack_from("<H",descriptors,4)[0] in (0x9d80,0xbf00)
        assert struct.unpack_from("<H",descriptors,14)[0] in (0xbe00,0xbe30,0xbe70,0xbeb0)
        if tank_state[9]==1:
            y=struct.unpack_from("<h",tank_state,2)[0]
            assert struct.unpack_from("<h",descriptors,12)[0]+1==21+y+9, \
                "Tank round is not aligned with its barrel"

    case("bank-round-crosses-jet-safely", bank_fixture +
        bank_at(x=30,y=134,phase=1,shot_x=76,target=110) + resume + [
        "peek xram:0x0082 1"])
    case("bank-splash-crashes-jet", bank_fixture +
        bank_at(x=30,y=134,phase=2,shot_x=76,target=76,timer=18) + resume + [
        "peek xram:0x0082 2"])
    # Native death freezes extension ticks. Every enemy projectile must be
    # hidden immediately, whether death came from a splash or from the bank.
    for cause in ("splash","ground"):
        commands=bank_fixture + bank_at(x=29,y=134,phase=2,
            shot_x=76 if cause=="splash" else 45,target=76 if cause=="splash" else 45,timer=6) + [
            poke(sym["bank_tanks"]+13,list(struct.pack("<hhh7B",122,40,55,1,1,90,2,55,6,122))),
            poke(sym["helicopter_shots"],list(struct.pack("<hh2B",60,80,1,0))),
            "run 3","dump xram:0x03a0 40"]
        if cause=="ground":
            commands += [poke(0xb3,4)]
        _, states=case(f"bank-splash-cleared-on-death-{cause}",commands + resume + [
            "peek xram:0x0082 2",f'dump 0x{sym["bank_tanks"]:04x} 26',
            f'dump 0x{sym["helicopter_shots"]:04x} 36',"dump xram:0x03a0 40",
            "run 20","dump xram:0x03a0 40"])
        visible,tanks,shots,dead,later=states
        assert all(struct.unpack_from("<h",visible,i*10+2)[0]!=-256 for i in (1,3))
        assert tanks[9]==tanks[22]==0 and shots==bytes(36)
        assert all(struct.unpack_from("<h",data,i*10+2)[0]==-256
            for data in (dead,later) for i in (1,3)), "Frozen impact circle survives the player's death"

    # After the last life, the native river resumes scrolling in attract
    # mode. Bank tanks follow that river without approaching or firing.
    for side in (0,1):
        snapshot=[f'dump 0x{sym["bank_tanks"]:04x} 26',
                  "dump xram:0x0200 16","dump xram:0x03a0 40"]
        _, samples=case(f"bank-tank-last-life-scroll-{side}",bank_fixture +
            bank_at(x=122 if side else 29,y=40,side=side) + [
            poke(0xc0,sym["rr_Copyright0"]&255),poke(0xb3,4)] + resume + [
            "peek xram:0x0082 2",f'wait 0x{sym["ready"]:04x} 2 240',
            "run 3"] + snapshot + ["run 60"] + snapshot + [
            "press p","run 3","release p","run 3"] + snapshot + [
            "run 60"] + snapshot + [
            "press p","run 3","release p","run 3","run 600"] + snapshot)
        before,config0,sprites0,after,config1,sprites1,paused0,_,_,paused1,_,_,gone,_,hidden=samples
        delta=(struct.unpack_from("<h",config1,4)[0]-
               struct.unpack_from("<h",config0,4)[0])%192
        assert 0<delta<80, "Game-over scenery did not scroll"
        assert struct.unpack_from("<h",sprites1,2)[0]-struct.unpack_from("<h",sprites0,2)[0]==delta, \
            "Bank tank stopped following scenery after the last life"
        assert before[:2]==after[:2] and not before[9] and not after[9], \
            "Attract-mode tank approached or fired"
        assert paused0==paused1, "Attract-mode bank tank moves during pause"
        assert gone==bytes(26), "Off-screen tank was retained or a new tank spawned in attract mode"
        assert all(struct.unpack_from("<h",hidden,i*10+2)[0]==-256 for i in range(4))

    # Check all six visible/clear phases, filled pixels and actual white ink.
    circle_commands=bank_fixture + bank_at(x=30,y=40,phase=2,shot_x=60,target=60,timer=18)
    for timer in (18,15,12,9,6,3):
        circle_commands += [poke(sym["bank_tanks"]+11,timer),"run 3",
            "dump xram:0x03aa 10",f'shot "{(output / f"tank-circle-{timer}.png").as_posix()}"']
    _, circle_buffers = case("bank-splash-white-circles", circle_commands + [
        "dump xram:0xbe30 192","dump xram:0xbf80 4"])
    circle_images=circle_buffers[-2]
    assert circle_buffers[-1]==bytes([0,0,255,255]), "Impact circles are not white"
    diameters=[]
    for phase,descriptor in enumerate(circle_buffers[:6]):
        if phase&1:
            assert struct.unpack_from("<h",descriptor,2)[0]==-256, "Circle was not erased"
            continue
        stage=phase//2
        assert struct.unpack_from("<H",descriptor,4)[0]==0xbe30+stage*64
        assert struct.unpack_from("<H",descriptor,6)[0]==0xbf80
        assert descriptor[8]==0x31
        pixels=circle_images[stage*64:(stage+1)*64]
        lit=[(x,y) for y in range(16) for x in range(8)
             if (pixels[y*4+x//2]>>(0 if x&1 else 4))&15]
        diameters.append(max(y for x,y in lit)-min(y for x,y in lit)+1)
        assert pixels[7*4+1]&15, "Circle has a transparent centre"
        for y in {y for x,y in lit}:
            xs=[x for x,py in lit if py==y]
            assert len(xs)==max(xs)-min(xs)+1, "Circle is not filled"
    assert diameters==[4,8,16], f"Wrong splash diameters: {diameters}"
    case("bank-cleared-circle-safe-for-jet", bank_fixture +
        bank_at(x=30,y=134,phase=2,shot_x=76,target=76,timer=3) + resume + [
        "peek xram:0x0082 1"])

    # The tank's round consumes fuel without awarding the player's 80 points
    # or consuming a player missile. A shot through transparent padding misses.
    for tank_y, destroys in ((96,True),(71,False)):
        _, buffers = case(f"bank-round-fuel-{tank_y}", bank_fixture + clear_score +
            object_at(1,10,56) + bank_at(x=30,y=tank_y,phase=1,shot_x=58,target=110) +
            [poke(0xb2,0),poke(0xf5,110)] + resume + dump + ["dump 0xa1 1"])
        assert score(buffers[0])==0, "Enemy fire awarded points to the player"
        assert (buffers[1][0]!=10)==destroys, "Tank round / FUEL bitmap collision disagrees"
        assert buffers[0][8], "Enemy fire consumed the player's missile"

    _, buffers = case("bank-round-fuel-at-impact", bank_fixture + clear_score +
        object_at(1,10,94) + bank_at(x=30,y=96,phase=1,shot_x=88,target=90) +
        resume + dump + ["dump 0xa1 1"])
    assert score(buffers[0])==0 and buffers[1][0]!=10, \
        "A round touching FUEL at its water impact must destroy the depot"
    _, buffers = case("bank-splash-expires", bank_fixture +
        bank_at(x=30,y=134,phase=2,shot_x=45,target=45,timer=18) + resume + [
        "run 14",f'dump 0x{sym["bank_tanks"]:04x} 13',"peek xram:0x0082 1"])
    assert buffers[-1][9]==0, "Expired splash remains dangerous"

    _, buffers = case("bank-tank-score", bank_fixture + clear_score +
        bank_at(x=44,y=96) + [poke(0xb2,45),poke(0xf5,47)] + resume + dump + [
        f'dump 0x{sym["bank_tanks"]:04x} 13'])
    assert score(buffers[0])==250 and buffers[1][7]==2, "Bank tank hit did not award 250"

    _, buffers = case("bank-tank-pause-restart", bank_fixture + bank_at() + [
        "run 4",f'dump 0x{sym["bank_tanks"]:04x} 26',
        "run 60",f'dump 0x{sym["bank_tanks"]:04x} 26'] + resume + [
        "press r","run 4","release r","run 4",
        f'dump 0x{sym["bank_tanks"]:04x} 26',"dump xram:0x03a0 40"])
    assert buffers[0]==buffers[1], "Bank tank or its projectile moves during pause"
    assert buffers[2]==bytes(26), "Restart retained shoreline tanks"
    assert all(struct.unpack_from("<h",buffers[3],i*10+2)[0]==-256 for i in range(4))

    _, buffers = case("bank-tanks-on-rendered-banks", fixture + [poke(0xbd,7),
        poke(sym["bank_tanks"],[0]*26)] + bank_at(x=-8,y=20) + [
        poke(sym["bank_tanks"]+13,list(struct.pack("<hhh7B",160,0,0,1,1,0,0,0,0,0)))] +
        resume + ["run 110", "dump xram:0x03a0 40", "dump xram:0x0200 16",
        "dump xram:0x0800 7680", "dump xram:0x2700 3136", "dump xram:0x9d80 96",
        f'shot "{(output / "bank-tanks.png").as_posix()}"'])
    sprites, config, terrain, tiles, image = buffers
    origin_y=struct.unpack_from("<h",config,4)[0]
    for sprite in (0,2):
        sx,sy,address,_,_,options=struct.unpack_from("<hhHHBB",sprites,sprite*10)
        assert address in (0x9d80,0xbf00) and sy!=-256, "Bank tank is not visible"
        for y in range(16):
            if not 21<=sy+y<181:
                continue
            row_index=(sy+y-origin_y)%192
            for x in range(12):
                ix=11-x if options&16 else x
                if not (image[y*6+ix//2]>>(0 if ix&1 else 4))&15:
                    continue
                for px in range(sx//2+x-2,sx//2+x+3):
                    assert 0<=px<160, "Tank did not finish approaching the bank"
                    tile=terrain[row_index*40+px//4]
                    color=tiles[tile*32+px%4]&15
                    assert color not in (1,12), "Tank touches water or decorative bank"

    for level in (6,7):
        _, buffers = case(f"bank-tank-spawn-level-{level}", bank_fixture + [
            poke(sym["bank_tanks"],[0]*26),poke(0xbd,level),poke(0x8b,31),
            poke(0xb5,254),poke(0xb6,2)] + resume + [
            f'dump 0x{sym["bank_tanks"]:04x} 26'])
        assert bool(buffers[-1][7]) == (level>=7), "Shore tanks must start at bridge 7"

    # Scrolling with two tanks and firing exercises the extra sprites and
    # bank sampling inside the shipping Release frame budget.
    case("bank-tanks-frame-budget", bank_fixture + bank_at(x=30) + [
        poke(sym["bank_tanks"]+13,list(struct.pack("<hhh7B",122,110,0,1,1,0,0,0,0,0))),
        poke(0xb5,254),poke(0xb6,2)] + resume + [
        "press lctrl","run 1200","release lctrl"])

    # Native procedural generation supplies balloons without test-only rules.
    _, buffers = case("balloon-generator", fixture + [poke(0xbd,2),poke(0x8b,31),
        poke(0x8c,255),poke(0xb5,254),poke(0xb6,2),poke(0xb9,8),
        poke(0xe9,[0x00,0x68])] + resume + ["dump 0xa0 6"])
    assert 11 in buffers[-1], "Native generator did not create a balloon"

    # HI is a visible session record, so a new game must retain it while
    # clearing the live score and restoring the reserve-plane display.
    _, buffers = case("hud-record-and-reserves", fixture + clear_score + object_at(1,8,63) + [
        poke(0xb2,43), poke(0xf5,81)] + resume + dump + ["dump xram:0x0600 180",
        "press r", "run 4", "release r", "run 4"] + dump + ["dump xram:0x0600 180",
        "press space", "run 140", "release space", "run 4"] + dump + ["dump xram:0x0600 180"])
    before, sprites_before, reset, sprites_reset, after, sprites_after = buffers
    assert score(before) == 500 and score(reset) == 0 and score(after) < 500
    record_before = tuple(struct.unpack_from("<H", sprites_before, i*10+4)[0] for i in range(3,9))
    record_after = tuple(struct.unpack_from("<H", sprites_after, i*10+4)[0] for i in range(3,9))
    record_reset = tuple(struct.unpack_from("<H", sprites_reset, i*10+4)[0] for i in range(3,9))
    assert record_before == tuple(0x9e00+n*32 for n in (11,11,11,5,0,0)), "HI does not show 500"
    assert record_after == record_reset == record_before, "Restart cleared the session record"
    assert all(struct.unpack_from("<h", sprites_reset, i*10+2)[0] == -256 for i in range(9,18)), \
        "Attract mode retained reserve-plane icons"
    reserves = sum(struct.unpack_from("<h", sprites_after, i*10+2)[0] == 207 for i in range(9,18))
    assert reserves == after[4] == 3, "Reserve-plane icons disagree with the game"

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
    _, states = case("bridge-difficulty-advance-50", fixture + [poke(0xbd,49), poke(0xb9,1),
        poke(0xb6,1), poke(0x8b,31), poke(0xb5,254), "run 4",
        "press p up", "run 3", "release p up", "run 3"] + dump)
    assert states[-1][5] == 50, "Bridge 49 must advance to 50"
    _, states = case("maximum-level-wrap", fixture + [poke(0xbd,50), poke(0xb9,1),
        poke(0xb6,1), poke(0x8b,31), poke(0xb5,254), "run 4",
        "press p up", "run 3", "release p up", "run 3"] + dump)
    assert states[-1][5] == 49, "The extended limit loops bridges 49/50"
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
    # Native PF bits still mark the removed corner as land. These missiles
    # exercise the real CPU collision routine on both sides of a fine edge.
    for name,p2,left,right,missile_x,active,plane_x in (
        ("outer-land",15,62,80,61,0,76), ("outer-water",15,62,80,62,1,76),
        ("island-water",240,48,66,65,1,52), ("island-land",240,48,66,66,0,52),
    ):
        case(f"smoothed-bank-{name}", fixture + [
            poke(sym["river1"],[255]*192), poke(sym["river2"],[p2]*192),
            poke(sym["river_left"],[left]*192), poke(sym["river_right"],[right]*192),
            poke(0xb2,43), poke(0xf5,missile_x), poke(0xb3,plane_x)] + resume + [
            f"peek xram:0x0088 {active}"])

    # Brown pixels are native PF land, but only the player may fly above them.
    # Wide rims fit the whole native jet; paired cases move it one pixel until
    # the first opaque wing pixel touches ground. Include both island edges.
    def rim_fixture(island):
        water_left,water_right=(48,64) if island else (64,80)
        limits=(40,120,72,88) if island else (56,104,80,80)
        line=[2 if x<limits[0] or x>=limits[1] or limits[2]<=x<limits[3] else
              1 if water_left<=min(x,159-x)<water_right else 7 for x in range(0,160,4)]
        terrain=line*192
        commands=fixture + [poke(sym["river1"],[255]*192),
            poke(sym["river2"],[240 if island else 15]*192),
            poke(sym["river_left"],[water_left]*192), poke(sym["river_right"],[water_right]*192)]
        for field,value in zip(("player_outer_left","player_outer_right",
                                "player_island_left","player_island_right"),limits):
            commands += [poke(sym[field],[value]*192)]
        commands += [poke(0x0800+i,terrain[i:i+192]).replace("poke ","poke xram:",1)
                     for i in range(0,len(terrain),192)]
        for block in range(6):
            commands += object_at(block,0,4)
        return commands

    for island,side,brown_x,ground_x in ((False,"left",55,54),(False,"right",96,97),
                                       (True,"left",64,65),(True,"right",87,86)):
        name="island" if island else "outer"
        for kind,plane_x,status in (("rim",brown_x,1),("ground",ground_x,2)):
            case(f"player-{name}-{side}-{kind}",rim_fixture(island) + [poke(0xb3,plane_x)] +
                 resume + [f"peek xram:0x0082 {status}"])
    for island,missile_x,plane_x in ((False,60,76),(True,68,52)):
        case(f"missile-{'island' if island else 'outer'}-rim",rim_fixture(island) +
             [poke(0xb2,43),poke(0xf5,missile_x),poke(0xb3,plane_x)] + resume +
             ["peek xram:0x0082 1","peek xram:0x0088 0"])

    for hard in (False, True):
        commands = fixture + [poke(0xb2,50), poke(0xf5,40), poke(0xb3,90)]
        if hard:
            commands += ["press f5", "run 2", "release f5", "run 2"]
        _, states = case("straight-missile" if hard else "guided-missile", commands + resume + dump)
        assert states[-1][9] == (40 if hard else 95)

    two = boot + ["press f2", "run 2", "release f2", "run 2", "peek 0x80 1",
                  "press space", "run 140", "release space", "run 4", "peek xram:0x0082 1",
                  "press p", "run 3", "release p", "run 3", poke(0xb3,4)]
    _, states = case("two-player-switch", two + resume + ["wait 0xf4 1 240"] + dump + [
        "wait 0xc6 48 300", "run 3", "press d", "run 18", "release d", "run 2",
        "peek xram:0x0582 224 255"] + dump)
    assert states[-1][29] == 1 and states[-1][3] > 76

    # Copyright0 ($59) marks the last jet: no reserve jet remains.
    case("game-over-restart-exit", fixture + [poke(0xc0,89), poke(0xb3,4)] + resume + [
        "wait 0xc6 255 300", "press space", "run 140", "release space", "run 4",
        "peek xram:0x0082 1", "peek xram:0x0084 3 1", "press escape", "expect-exit 0 120"])
    _, buffers = case("scroll-and-performance", start + ["press up space", "run 1200",
        "release up space", "run 4"] + dump + [
        "dump xram:0x0200 16", "dump xram:0x0800 7680", "dump xram:0x2700 3136",
        f'dump 0x{sym["river1"]:04x} 192', f'dump 0x{sym["river2"]:04x} 192',
        f'dump 0x{sym["river_left"]:04x} 192', f'dump 0x{sym["river_right"]:04x} 192',
        f'dump 0x{sym["player_outer_left"]:04x} 192', f'dump 0x{sym["player_outer_right"]:04x} 192',
        f'dump 0x{sym["player_island_left"]:04x} 192', f'dump 0x{sym["player_island_right"]:04x} 192',
        "dump xram:0x0300 100", "dump xram:0x9200 512", "dump xram:0x3600 512", "dump xram:0x5800 512",
        f'shot "{(output / "gameplay.png").as_posix()}"'])
    state,config,terrain,tiles,p1,p2,left,right,outer_left,outer_right,island_left,island_right,sprites,large,small,medium=buffers
    assert int.from_bytes(state[30:32], "little") == 0, "Skipped VSYNC at 8 MHz"
    assert state[5] >= 2
    check_terrain_pixels(config,terrain,tiles,p1,p2,left,right)
    check_player_ground(config,terrain,tiles,outer_left,outer_right,island_left,island_right)
    check_bank_contours(config,terrain,tiles,require_features=False)
    check_bank_angle(config,terrain,tiles,p1,p2)
    check_mountains_on_fine_terrain(sprites,config,terrain,tiles,{0x9200:large,0x3600:small,0x5800:medium})
    # A restart and palette change can redraw terrain, score, fuel and logo
    # together. Exercise that combination after some gameplay, repeatedly.
    commands = start + ["press up space", "run 600", "release up space", "run 4"]
    for _ in range(6):
        commands += ["press r f1", "run 4", "release r f1", "run 12"]
    case("restart-and-palette-performance", commands)
    print(f"All {count} emulator checks passed. Screenshots: {output}", flush=True)


if __name__ == "__main__":
    main()
