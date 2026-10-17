"""Render the compiled intro with the firmware OPL core (not a device recording).

Unlike end-of-frame register snapshots, the bytecode preserves note retriggers.
Build the optional library as described in opl_preview.c.
"""
import argparse
import ctypes
import json
import struct
import wave
from pathlib import Path
from make_intro import SLOTS
from preview_audio import RATE


def frames(data):
    """Yield the exact ordered register writes for each frame of one loop."""
    cursor = 0
    writes = []
    while True:
        op = data[cursor]
        cursor += 1
        if op == 255:
            if writes:
                yield writes
            return
        if op >= 128:
            yield writes
            writes = []
            for _ in range(op - 128):
                yield []
        elif op == 32:
            writes.append(tuple(data[cursor:cursor+2]))
            cursor += 2
        elif 16 <= op <= 24:
            writes.append((0xb0+op-16, 0))
        elif op < 9:
            lo, hi, level = data[cursor:cursor+3]
            cursor += 3
            writes.extend(((0xb0+op, 0), (0x43+SLOTS[op], level),
                           (0xa0+op, lo), (0xb0+op, hi)))
        else:
            raise ValueError(f"Invalid intro opcode {op:#x}")


def render(data, library):
    model = ctypes.CDLL(str(library.resolve()))
    model.rr_reset.argtypes = []
    model.rr_reset.restype = None
    model.rr_write.argtypes = [ctypes.c_uint, ctypes.c_uint]
    model.rr_write.restype = None
    model.rr_sample.argtypes = []
    model.rr_sample.restype = ctypes.c_int
    model.rr_reset()
    samples = []
    for i, writes in enumerate(frames(data)):
        for reg, value in writes:
            model.rr_write(reg, value)
        count = round((i+1)*RATE/60) - round(i*RATE/60)
        samples.extend(model.rr_sample() for _ in range(count))
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('score', type=Path, help='compiled intro-score.bin')
    parser.add_argument('--opl-library', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('build/intro.wav'))
    args = parser.parse_args()
    samples = render(args.score.read_bytes(), args.opl_library)
    with wave.open(str(args.output), 'wb') as wav:
        wav.setparams((1, 2, RATE, len(samples), 'NONE', 'not compressed'))
        wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))
    report = dict(seconds=len(samples)/RATE, peak=max(abs(v) for v in samples),
                  rms=round((sum(v*v for v in samples)/len(samples))**.5),
                  clipped_samples=sum(abs(v)>=32767 for v in samples))
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2))
    print(report)


if __name__ == '__main__':
    main()
