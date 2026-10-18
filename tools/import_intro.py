"""Import the firmware River Raid generator's default OPL2 + PCM arrangement."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('generator', type=Path)
    parser.add_argument('--bpm', type=float, default=140)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.generator.resolve().parent))
    spec = importlib.util.spec_from_file_location('riverraid_reference', args.generator)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    reference.set_tempo(args.bpm)
    events = [[] for _ in reference.OPL_VOICES]

    def note(channel, pitch, previous=None):
        events[channel].append((step, pitch))
        return []

    for step in range(reference.STEPS):
        reference.step(note, step)
    tracks = []
    for channel, (mod, car, feedback) in enumerate(reference.OPL_VOICES):
        notes = []
        changes = events[channel] + [(reference.STEPS, None)]
        for (start, pitch), (end, _) in zip(changes, changes[1:]):
            if pitch is not None:
                notes.append([start, end-start, pitch, car[1]])
        tracks.append(dict(name=('bass','chord 1','chord 2','chord 3','lead','arpeggio','crash')[channel],
                           instrument=dict(mod=mod, car=car, feedback=feedback), notes=notes))
    main_bar, fill = reference.drum_bars()
    drums = main_bar * (reference.BARS-1) + fill
    score = dict(title='River Raid firmware generator — OPL2 + PCM',
                 source=args.generator.name, source_sha256=hashlib.sha256(args.generator.read_bytes()).hexdigest(),
                 requested_bpm=args.bpm, bpm=reference.BPM, sample_rate=reference.RATE,
                 samples_per_step=reference.SIXTEENTH, steps=reference.STEPS,
                 drum_sha256=hashlib.sha256(drums).hexdigest(), opl_bd=0x40,
                 notes_format=['start_step','duration_steps','MIDI_note','OPL_total_level'], tracks=tracks)
    formatted = json.dumps(score, indent=2)
    # Keep each four-number note/instrument row readable on a single line.
    formatted = re.sub(r'\[\s+(-?\d+),\s+(-?\d+),\s+(-?\d+),\s+(-?\d+)\s+\]',
                       r'[\1, \2, \3, \4]', formatted)
    (args.root/'src/intro-score.json').write_text(formatted+'\n', encoding='utf-8')
    (args.root/'assets/intro-drums.pcm').write_bytes(drums)
    print(f'Imported {reference.BPM:.6f} BPM, {len(drums)} PCM samples, {sum(len(t["notes"]) for t in tracks)} notes')


if __name__ == '__main__':
    main()
