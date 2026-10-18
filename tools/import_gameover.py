"""Import a firmware one-shot OPL2 + PCM jingle (gameover or victory)."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('generator', type=Path)
    parser.add_argument('--bpm', type=float, default=200)
    parser.add_argument('--name', choices=('gameover','victory'), default='gameover')
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.generator.resolve().parent))
    spec = importlib.util.spec_from_file_location('gameover_reference', args.generator)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    reference.set_tempo(args.bpm)
    pcm = reference.timeline()
    records = []
    for step, length in enumerate(reference.LENGTHS):
        writes = (reference.opl_init() if step == 0 else []) + reference.step(reference.opl_note, step)
        records.append(dict(samples=length, writes=list(zip(writes[::2], writes[1::2]))))
    release = reference.end(reference.opl_off)
    records.append(dict(samples=len(pcm)-reference.START[-1], writes=list(zip(release[::2], release[1::2]))))
    score = dict(source=args.generator.name, source_sha256=hashlib.sha256(args.generator.read_bytes()).hexdigest(),
                 bpm=reference.BPM, sample_rate=reference.RATE, samples=len(pcm),
                 pcm_sha256=hashlib.sha256(pcm).hexdigest(), records=records)
    root = Path(__file__).resolve().parents[1]
    (root/f'src/{args.name}-score.json').write_text(json.dumps(score, indent=2)+'\n', encoding='utf-8')
    (root/f'assets/{args.name}.pcm').write_bytes(pcm)
    print(f'Imported {reference.BPM:g} BPM, {len(pcm)} samples ({len(pcm)/reference.RATE:.3f} s)')


if __name__ == '__main__':
    main()
