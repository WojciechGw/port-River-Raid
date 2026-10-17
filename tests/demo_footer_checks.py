"""Shared six-screen caption, its cell geometry and scrolling pauses."""
import json
import re
import struct
from pathlib import Path
from emulator_checks import poke


def run_demo_footer_checks(case, sym, boot, output, fixture):
    root = Path(__file__).resolve().parents[1]
    caption = json.loads((root / 'src/demo-footer.json').read_text(encoding='utf-8'))
    classic = (output.parent / 'demo_footer.bin').read_bytes()
    duo = (output.parent / 'duo_demo_footer.bin').read_bytes()
    assert duo == classic, 'All game modes must use the same caption'
    assert len(classic) == 960*8, 'Caption must span six 160-pixel logical screens'
    assert caption['advance'] == caption['space_advance'] == 8
    assert all(len(glyph)==7 and all(len(row)==6 for row in glyph)
               for glyph in caption['font'].values())
    graphics=(root / 'src/graphics.h').read_text(encoding='utf-8')
    logo_source=re.search(r'activision_logo\[8\]\[\d+\]\s*=\s*\{(.*?)\};',graphics,re.S)[1]
    logo=re.findall(r'"([.A-F]+)"',logo_source)
    logo_width=(len(logo[0])+7)//8*8
    static_logo=bytearray()
    for pixels in logo:
        colors=[0 if p=='.' else ord(p)-ord('A')+1 for p in pixels]
        colors += [0]*(64-len(colors))
        static_logo.extend((colors[x]<<4)|colors[x+1] for x in range(0,64,2))
    x=0
    for token in re.findall(r'\{Activision\}|.',caption['text']):
        if token=='{Activision}':
            assert logo_width==64
            for y,pixels in enumerate(logo):
                expected=bytes(0 if p=='.' else (ord(p)-ord('A')+1)*17 for p in pixels)
                assert classic[y*960+x:y*960+x+len(pixels)]==expected
                assert not any(classic[y*960+x+len(pixels):y*960+x+logo_width])
            x+=logo_width
        else:
            for y in range(8):
                expected=bytes(0x22 if p=='X' else 0 for p in caption['font'][token][y-1]) if y and token!=' ' else bytes(6)
                assert classic[y*960+x:y*960+x+6]==expected
                assert classic[y*960+x+6:y*960+x+8]==bytes(2), 'Letter spacing must be two blank pixels'
            x+=8
    assert x<=960
    assert all(not any(classic[y*960+x:(y+1)*960]) for y in range(8))

    _, data = case('footer-startup-delay', boot + ['dump xram:0x0260 14',
        'run 90', 'dump xram:0x0260 14', 'run 60', 'dump xram:0x0260 14'])
    assert struct.unpack_from('<h', data[0], 2)[0] == 0 and data[0] == data[1]
    assert struct.unpack_from('<h', data[2], 2)[0] < 0

    # Re-enter GAME 1 too, so each hold starts at mode selection.
    selects = [boot + [cmd for _ in range(variant or 3) for cmd in
               ('press f2', 'run 3', 'release f2', 'run 8')]
               for variant in range(3)]

    def screen_stop(distance, width):
        # VGA stores the negative bitmap offset.
        origin = (-(distance % width)) & 0xffff
        return [f'wait xram:0x0263 {origin >> 8} 700',
                f'wait xram:0x0262 {origin & 255} 340',
                'dump xram:0x0260 14', 'run 59', 'dump xram:0x0260 14',
                'run 3', 'dump xram:0x0260 14']

    def check_stop(data, distance, width):
        first, held, resumed = data
        assert struct.unpack_from('<h', first, 2)[0] == -(distance % width)
        assert held == first, 'Caption did not hold for a full second'
        moved = (struct.unpack_from('<h', held, 2)[0]-struct.unpack_from('<h', resumed, 2)[0]) % width
        assert 1 <= moved <= 3, 'Caption did not resume after its one-second hold'

    for variant, select in enumerate(selects):
        image, address = classic, 0x3800
        width = len(image)//4
        _, data = case(f'footer-game{variant+1}-scroll', select + [
            'dump xram:0x0260 14', 'run 150', 'dump xram:0x0260 14',
            'run 50', 'dump xram:0x0260 14', 'run 60', 'dump xram:0x0260 14',
            f'dump xram:0x{address:04x} {len(image)}', 'dump xram:0x0720 14',
            f'shot "{(output / f"footer-game{variant+1}.png").as_posix()}"'])
        opening, held, first, second, actual, palette = data
        assert struct.unpack_from('<h', opening, 2)[0] == 0
        assert held == opening, 'Caption moved during its initial three-second hold'
        assert struct.unpack_from('<h', first, 2)[0] < 0, 'Caption did not start after three seconds'
        assert struct.unpack_from('<hhHH', second, 6) == (width, 8, address, 0x0720)
        assert struct.unpack_from('<h', second, 4)[0] == 222
        assert (struct.unpack_from('<h', first, 2)[0]-struct.unpack_from('<h', second, 2)[0]) % width == 60
        assert actual == image
        assert palette[4:6] == bytes((247, 189))

        _, data = case(f'footer-game{variant+1}-screen-stops', select +
                       screen_stop(320, width) + screen_stop(640, width))
        check_stop(data[:3], 320, width)
        check_stop(data[3:], 640, width)

        _, data = case(f'footer-game{variant+1}-static-logo', select + [
            'dump xram:0x06b4 10', 'dump xram:0x5a00 256',
            f'shot "{(output / f"logo-before-game{variant+1}.png").as_posix()}"',
            'press space', 'run 140', 'release space', 'run 4',
            'dump xram:0x06b4 10', 'dump xram:0x5a00 256',
            f'shot "{(output / f"logo-playing-game{variant+1}.png").as_posix()}"'])
        for descriptor, bitmap in (data[:2],data[2:]):
            assert struct.unpack('<hhHHBB',descriptor)==(0,232,0x5a00,0x0700,0x1f,0x42)
            assert bitmap==static_logo, 'Activision logo was cropped or changed'

    select = selects[2]
    width = len(duo)//4
    # Start at offset 2: a full caption pass then crosses width//320 stops,
    # even when the editable text ends just short of a screen boundary.
    wrap_start = ['wait xram:0x0262 254 300', 'dump xram:0x0260 14']
    _, data = case('footer-duo-wrap', select + wrap_start + [
        f'run {width+(width//320)*60}', 'dump xram:0x0260 14'] + screen_stop(2560, width))
    assert data[0] == data[1], 'GAME 3 caption failed to wrap'
    check_stop(data[2:], 2560, width)
    classic_width = len(classic)//4
    _, data = case('footer-classic-wrap-screen-stop', selects[0] + wrap_start + [
        f'run {classic_width+(classic_width//320)*60}',
        'dump xram:0x0260 14'] + screen_stop(2240, classic_width))
    assert data[0] == data[1], 'Classic caption failed to wrap'
    check_stop(data[2:], 2240, classic_width)
    pause = ['press p', 'run 3', 'release p', 'run 3']
    _, data = case('footer-duo-pause-and-help', select + pause + [
        'dump xram:0x0260 14', 'mark', 'run 60', 'expect-same',
        'press f1', 'wait xram:0x0080 0 10', 'wait xram:0x00b0 2 120',
        'release f1', 'wait xram:0x02a4 222 5', 'press space', 'run 3',
        'release space', 'wait xram:0x0080 82 240', 'run 3', 'expect-same',
        'dump xram:0x0260 14', f'dump xram:0x3800 {len(duo)}'] + pause + [
        'run 150', 'dump xram:0x0260 14', 'run 30', 'dump xram:0x0260 14'])
    assert data[0] == data[1] and data[2] == duo
    assert struct.unpack_from('<h', data[3], 2)[0] == 0, 'F1 or pause lost the initial hold'
    assert struct.unpack_from('<h', data[4], 2)[0] < 0, 'Caption stayed held after resuming'

    _, data = case('footer-screen-hold-pause-and-help', select + [
        'wait xram:0x0263 254 700', 'wait xram:0x0262 192 100', 'run 20'] + pause + [
        'mark', 'run 120', 'expect-same',
        'press f1', 'wait xram:0x0080 0 10', 'wait xram:0x00b0 2 120',
        'release f1', 'wait xram:0x02a4 222 5', 'press space', 'run 3',
        'release space', 'wait xram:0x0080 82 240', 'run 3', 'expect-same'] + pause + [
        'run 20', 'dump xram:0x0260 14', 'run 25', 'dump xram:0x0260 14'])
    assert struct.unpack_from('<h', data[0], 2)[0] == -320
    assert struct.unpack_from('<h', data[1], 2)[0] < -320

    # RAM staging must reach VGA at the next VSYNC, before the playfield.
    _, buffers=case('vsync-world-presentation',fixture+['run 2',
        'dump xram:0x0200 16', 'dump xram:0x0300 10',
        poke(0xb3,90), poke(sym['ring_top'],17), 'dump xram:0x0200 16',
        'dump xram:0x0300 10', 'run 1',
        f'dump 0x{sym["terrain"]:04x} 16', f'dump 0x{sym["sprites"]:04x} 10',
        'dump xram:0x0200 16', 'dump xram:0x0300 10',
        'run 1', 'dump xram:0x0200 16', 'dump xram:0x0300 10'])
    assert buffers[0]==buffers[2]
    assert buffers[1]==buffers[3]==buffers[7]
    # A script may stop during the short copy, before the river is scanned.
    assert buffers[6] in (buffers[0],buffers[4])
    assert buffers[4]==buffers[8] and buffers[5]==buffers[9]
    assert struct.unpack_from('<h',buffers[4],4)[0]==4
    assert struct.unpack_from('<h',buffers[5],0)[0]==180
    _, data = case('footer-duo-start-and-classic-return', select + [
        'press space', 'run 140', 'release space', 'run 4',
        'dump xram:0x0260 14', 'press f2', 'run 3', 'release f2', 'run 8',
        'dump xram:0x0260 14', f'dump xram:0x3800 {len(classic)}'])
    assert struct.unpack_from('<h', data[0], 4)[0] < 0
    assert struct.unpack_from('<hhHH', data[1], 4) == (222, len(classic)//4, 8, 0x3800)
    assert data[2] == classic
