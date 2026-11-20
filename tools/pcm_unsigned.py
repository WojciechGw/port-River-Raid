"""Convert signed 8-bit PCM to the unsigned 8-bit format of the PCM: device.

The repository keeps the firmware generator's signed samples, whose SHA-256
is recorded in the score JSON; the ROM receives this unsigned copy.
"""
import argparse
from pathlib import Path


def unsigned(data: bytes) -> bytes:
    return bytes(b ^ 0x80 for b in data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_bytes(unsigned(args.source.read_bytes()))


if __name__ == '__main__':
    main()
