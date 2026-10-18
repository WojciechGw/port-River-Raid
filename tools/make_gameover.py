"""Compile sample durations and exact OPL register writes for one-shot jingles."""
import argparse
import json
from pathlib import Path
import struct


def compile_score(score):
    data = bytearray()
    for record in score['records']:
        assert 0 < record['samples'] <= 32767 and len(record['writes']) < 256
        data.extend(struct.pack('<HB', record['samples'], len(record['writes'])))
        for reg, value in record['writes']:
            data.extend((reg, value))
    data.extend(b'\0\0\0')
    assert len(data) <= 0x700
    assert sum(r['samples'] for r in score['records']) == score['samples']
    assert score['sample_rate'] == 16000 and score['samples'] % 256 == 0
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('score', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('include', type=Path)
    parser.add_argument('--prefix', default='GAMEOVER')
    args = parser.parse_args()
    score = json.loads(args.score.read_text(encoding='utf-8'))
    data = compile_score(score)
    args.output.write_bytes(data)
    args.include.write_text(f'{args.prefix}_SCORE_BYTES = {len(data)}\n{args.prefix}_PCM_PAGES = {score["samples"]//256}\n')


if __name__ == '__main__':
    main()
