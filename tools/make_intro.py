"""Compile the cover's OPL2 score; each sequencer tick is one sixteenth note."""
import argparse
import json
from pathlib import Path

SLOTS = (0, 1, 2, 8, 9, 10, 16, 17, 18)


def pitch(note):
    hz = 440 * 2 ** ((note - 69) / 12)
    for block in range(8):
        fnum = round(hz * 2 ** (20 - block) / 49716)
        if fnum <= 1023:
            return fnum & 255, (fnum >> 8) | (block << 2) | 32
    raise ValueError(f"OPL pitch out of range: {note}")


def compile_score(score):
    assert 0 < len(score['tracks']) <= 9
    duration = score['steps']
    events = {}
    data = bytearray()

    def reg(address, value):
        data.extend((0x20, address, value))

    reg(1, 32)
    reg(0xbd, score['opl_bd'])
    for ch in range(9):
        reg(0xb0 + ch, 0)
    for ch, track in enumerate(score['tracks']):
        s = SLOTS[ch]
        instrument = track['instrument']
        mod, depth, ma, mr = instrument['mod']
        car, level, ca, cr = instrument['car']
        feedback = instrument['feedback']
        for address, value in ((0x20+s, mod), (0x23+s, car),
                (0x40+s, depth), (0x43+s, level), (0x60+s, ma),
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
            if previous_end < duration and not any(n[0] == previous_end for n in track['notes']):
                events.setdefault(previous_end, []).append((0, bytes((0x20, 0xb0+ch, hi & ~32))))
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
    parser.add_argument('--include', type=Path)
    args = parser.parse_args()
    score = json.loads(args.score.read_text(encoding='utf-8'))
    data = compile_score(score)
    args.output.write_bytes(data)
    if args.include:
        args.include.write_text(f"INTRO_RATE = {score['sample_rate']}\n"
            f"INTRO_STEP_SAMPLES = {score['samples_per_step']}\n"
            f"INTRO_DRUM_PAGES = {score['samples_per_step']*score['steps']//256}\n")
    print(f"OPL2 + PCM intro: {score['bpm']:.6f} BPM, {len(data)} score bytes")


if __name__ == '__main__':
    main()
