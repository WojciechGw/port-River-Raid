"""Compile the cover's OPL2 arrangement to a small 60 Hz register/note stream.

The source WAV is only a transcription reference; no recorded samples enter
the ROM. The checked-in score is sufficient to build without audio packages.
"""
import argparse
import json
from pathlib import Path

SLOTS = (0, 1, 2, 8, 9, 10, 16, 17, 18)
# mod/car multiple+EG, mod TL, mod/car AR/DR, mod/car SL/RR, feedback
PATCHES = {
    "lead": (0x21, 0x21, 22, 0xf2, 0xf2, 0x16, 0x16, 0),
    "strings": (0x21, 0x21, 26, 0xc2, 0xd2, 0x16, 0x16, 0),
    "bass": (0x21, 0x21, 25, 0xf3, 0xf3, 0x17, 0x17, 2),
    "kick": (0x01, 0x01, 20, 0xf8, 0xf7, 0x88, 0x88, 2),
    "snare": (0x21, 0x01, 1, 0xf0, 0xf8, 0x0f, 0x88, 14),
}


def pitch(note):
    hz = 440 * 2 ** ((note - 69) / 12)
    for block in range(8):
        fnum = round(hz * 2 ** (20 - block) / 49716)
        if fnum <= 1023:
            return fnum & 255, (fnum >> 8) | (block << 2) | 32
    raise ValueError(f"OPL pitch out of range: {note}")


def compile_score(score):
    assert score['fps'] == 60
    assert 0 < len(score['tracks']) <= 9
    duration = score['frames']
    events = {}
    data = bytearray()

    def reg(address, value):
        data.extend((0x20, address, value))

    reg(1, 32)
    reg(0xbd, 0)
    for ch in range(9):
        reg(0xb0 + ch, 0)
    for ch, track in enumerate(score['tracks']):
        s = SLOTS[ch]
        mod, car, depth, ma, ca, mr, cr, feedback = PATCHES[track['patch']]
        for address, value in ((0x20+s, mod), (0x23+s, car),
                (0x40+s, depth), (0x43+s, 63), (0x60+s, ma),
                (0x63+s, ca), (0x80+s, mr), (0x83+s, cr),
                (0xe0+s, 0), (0xe3+s, 0), (0xc0+ch, feedback)):
            reg(address, value)
        previous_end = 0
        for start, length, note, level in track['notes']:
            assert 0 <= start < start + length <= duration
            assert start >= previous_end, f"Overlapping notes on channel {ch}"
            assert 0 <= note <= 127 and 0 <= level <= 63
            previous_end = start + length
            lo, hi = pitch(note)
            events.setdefault(start, []).append((1, bytes((ch, lo, hi, level))))
            events.setdefault(previous_end, []).append((0, bytes((0x10+ch,))))
    events.setdefault(duration, [])
    cursor = 0
    for frame in sorted(events):
        delay = frame - cursor
        while delay:
            part = min(delay, 127)
            data.append(0x80 + part - 1)
            delay -= part
        for _, command in sorted(events[frame]):
            data.extend(command)
        cursor = frame
    data.append(0xff)
    assert len(data) <= 0xf00, f"Intro score exceeds cover scratch XRAM: {len(data)}"
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('score', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    score = json.loads(args.score.read_text(encoding='utf-8'))
    data = compile_score(score)
    args.output.write_bytes(data)
    print(f"OPL2 intro: {score['frames']/60:.2f} s, {len(data)} bytes")


if __name__ == '__main__':
    main()
