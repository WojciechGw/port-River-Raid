"""Render OPL2 and PCM percussion with the firmware OPL core (not a recording).

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
    """Yield the exact ordered register writes for each sequencer step."""
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
            writes.extend(((0xb0+op, hi & ~32), (0x43+SLOTS[op], level),
                           (0xa0+op, lo), (0xb0+op, hi)))
        else:
            raise ValueError(f"Invalid intro opcode {op:#x}")


def render(data, library, score, drums):
    model = ctypes.CDLL(str(library.resolve()))
    model.rr_reset.argtypes = []
    model.rr_reset.restype = None
    model.rr_write.argtypes = [ctypes.c_uint, ctypes.c_uint]
    model.rr_write.restype = None
    model.rr_sample.argtypes = []
    model.rr_sample.restype = ctypes.c_int
    model.rr_reset()
    samples = []
    samples_per_step = RATE*score['samples_per_step']/score['sample_rate']
    for i, writes in enumerate(frames(data)):
        for reg, value in writes:
            model.rr_write(reg, value)
        count = round((i+1)*samples_per_step) - round(i*samples_per_step)
        samples.extend(model.rr_sample() for _ in range(count))
    for i in range(len(samples)):
        position = i*score['sample_rate']/RATE
        index = int(position) % len(drums)
        a, b = drums[index], drums[(index+1) % len(drums)]
        a = a-256 if a>=128 else a
        b = b-256 if b>=128 else b
        percussion = round((a+(b-a)*(position-int(position)))*256)
        samples[i] = max(-32768, min(32767, samples[i]+percussion))
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('score', type=Path, help='compiled intro-score.bin')
    parser.add_argument('--opl-library', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('build/intro.wav'))
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1]/'src/intro-score.json')
    parser.add_argument('--drums', type=Path, default=Path(__file__).resolve().parents[1]/'assets/intro-drums.pcm')
    args = parser.parse_args()
    score = json.loads(args.source.read_text(encoding='utf-8'))
    samples = render(args.score.read_bytes(), args.opl_library, score, args.drums.read_bytes())
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
