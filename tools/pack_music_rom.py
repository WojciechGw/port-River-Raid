"""Use the unused Atari display/code copy for music; preserve all native tables."""
import argparse
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference', type=Path)
    p.add_argument('music', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    reference, music = a.reference.read_bytes(), a.music.read_bytes()
    assert len(reference) == 4096 and len(music) <= 0xb00
    # $CB00 is Zero, the first data table. Native code runs from its relocated
    # copy; the original display kernel at $C000..$CAFF is never executed.
    a.output.write_bytes(music.ljust(0xb00, b'\0') + reference[0xb00:])


if __name__ == '__main__':
    main()
