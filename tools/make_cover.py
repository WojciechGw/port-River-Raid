"""Convert the indexed startup BMP and its fades to named RP6502 ROM assets.

No external image packages are needed. Pixels retain their original indexes;
only the palette is converted to the VGA's opaque RGB555 format.
"""
import argparse
import struct
from pathlib import Path

FADE_FRAMES = 64
PROMPT = "PRESS ANY KEY"
OUTRO_PROMPT = "SEE YOU NEXT TIME!"
OUTRO_PROMPT_WIDTH = 112
MANUAL_PROMPT = PROMPT
MANUAL_PROMPT_WIDTH = ((len(MANUAL_PROMPT)*6-1+7)//8)*8
# Five-column, seven-row lettering; one empty column separates characters.
PROMPT_FONT = {
    " ": (
        ".....",
        ".....",
        ".....",
        ".....",
        ".....",
        ".....",
        ".....",
    ),
    "A": (
        ".XXX.",
        "X...X",
        "X...X",
        "XXXXX",
        "X...X",
        "X...X",
        "X...X",
    ),
    "E": (
        "XXXXX",
        "X....",
        "X....",
        "XXXX.",
        "X....",
        "X....",
        "XXXXX",
    ),
    "G": (
        ".XXX.",
        "X...X",
        "X....",
        "X.XXX",
        "X...X",
        "X...X",
        ".XXX.",
    ),
    "H": (
        "X...X",
        "X...X",
        "X...X",
        "XXXXX",
        "X...X",
        "X...X",
        "X...X",
    ),
    "I": (
        "XXXXX",
        "..X..",
        "..X..",
        "..X..",
        "..X..",
        "..X..",
        "XXXXX",
    ),
    "K": (
        "X...X",
        "X..X.",
        "X.X..",
        "XX...",
        "X.X..",
        "X..X.",
        "X...X",
    ),
    "N": (
        "X...X",
        "XX..X",
        "X.X.X",
        "X..XX",
        "X...X",
        "X...X",
        "X...X",
    ),
    "M": (
        "X...X",
        "XX.XX",
        "X.X.X",
        "X...X",
        "X...X",
        "X...X",
        "X...X",
    ),
    "O": (
        ".XXX.",
        "X...X",
        "X...X",
        "X...X",
        "X...X",
        "X...X",
        ".XXX.",
    ),
    "P": (
        "XXXX.",
        "X...X",
        "X...X",
        "XXXX.",
        "X....",
        "X....",
        "X....",
    ),
    "R": (
        "XXXX.",
        "X...X",
        "X...X",
        "XXXX.",
        "X.X..",
        "X..X.",
        "X...X",
    ),
    "S": (
        ".XXXX",
        "X....",
        "X....",
        ".XXX.",
        "....X",
        "....X",
        "XXXX.",
    ),
    "T": (
        "XXXXX",
        "..X..",
        "..X..",
        "..X..",
        "..X..",
        "..X..",
        "..X..",
    ),
    "U": (
        "X...X",
        "X...X",
        "X...X",
        "X...X",
        "X...X",
        "X...X",
        ".XXX.",
    ),
    "X": (
        "X...X",
        "X...X",
        ".X.X.",
        "..X..",
        ".X.X.",
        "X...X",
        "X...X",
    ),
    "Y": (
        "X...X",
        "X...X",
        ".X.X.",
        "..X..",
        "..X..",
        "..X..",
        "..X..",
    ),
    "!": (
        "..X..",
        "..X..",
        "..X..",
        "..X..",
        "..X..",
        ".....",
        "..X..",
    ),
}


def prompt_bitmap(text=PROMPT, width=80):
    if width % 8 or len(text)*6-1 > width:
        raise ValueError("Message must fit in a whole-byte-wide bitmap")
    pixels = bytearray(width)  # Eight rows, 1bpp, MSB at the left.
    left = (width-(len(text)*6-1))//2
    for letter, char in enumerate(text):
        for y, row in enumerate(PROMPT_FONT[char]):
            for dx, pixel in enumerate(row):
                if pixel == "X":
                    x = left+letter*6+dx
                    pixels[y*(width//8)+x//8] |= 0x80 >> (x%8)
    return bytes(pixels)


def build(source):
    bmp = source.read_bytes()
    if len(bmp) < 54 or bmp[:2] != b"BM":
        raise ValueError("Expected a Windows indexed BMP")
    offset = struct.unpack_from("<I", bmp, 10)[0]
    dib, width, height, planes, depth, compression = struct.unpack_from("<IiiHHI", bmp, 14)
    colors = struct.unpack_from("<I", bmp, 46)[0] or 256
    if dib < 40 or (width, abs(height), planes, depth, compression) != (320, 180, 1, 8, 0):
        raise ValueError("Cover must be an uncompressed 320x180, 8-bit indexed BMP")
    palette_start = 14 + dib
    stride = (width + 3) & ~3
    if not 1 <= colors <= 256 or palette_start + colors*4 > offset or len(bmp) < offset + stride*abs(height):
        raise ValueError("Truncated BMP palette or pixels")
    palette = [tuple(bmp[palette_start+i*4:palette_start+i*4+3]) for i in range(colors)]
    palette.extend([(0, 0, 0)]*(256-colors))
    rows = [bmp[offset+y*stride:offset+y*stride+width] for y in range(abs(height))]
    if height > 0:
        rows.reverse()
    pixels = b"".join(rows)
    if max(pixels) >= colors:
        raise ValueError("Pixel references a missing BMP palette entry")
    fades = bytearray()
    for level in (*range(FADE_FRAMES), *reversed(range(FADE_FRAMES))):
        for b, g, r in palette:
            r, g, b = ((v >> 3)*level//(FADE_FRAMES-1) for v in (r, g, b))
            fades.extend(struct.pack("<H", r | (g << 6) | (b << 11) | 32))
    return pixels, bytes(fades)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("pixels", type=Path)
    parser.add_argument("fades", type=Path)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("include", type=Path)
    parser.add_argument("footer", type=Path)
    parser.add_argument("outro_prompt", type=Path)
    parser.add_argument("--manual", type=Path, required=True)
    parser.add_argument("--outro", type=Path, required=True)
    parser.add_argument("--duo-footer", type=Path, required=True)
    args = parser.parse_args()
    pixels, fades = build(args.source)
    footer_bytes = args.footer.stat().st_size
    if not 0 < footer_bytes <= 0x2000:
        raise ValueError("Demo footer exceeds its XRAM region")
    args.pixels.parent.mkdir(parents=True, exist_ok=True)
    args.pixels.write_bytes(pixels)
    args.fades.write_bytes(fades)
    prompt = prompt_bitmap()
    args.prompt.write_bytes(prompt)
    outro_prompt = prompt_bitmap(OUTRO_PROMPT, OUTRO_PROMPT_WIDTH)
    args.outro_prompt.write_bytes(outro_prompt)
    for name, source in (("manual", args.manual), ("outro", args.outro)):
        scene_pixels, scene_fades = build(source)
        (args.pixels.parent / f"{name}.bin").write_bytes(scene_pixels)
        (args.pixels.parent / f"{name}_fade.bin").write_bytes(scene_fades)
    manual_prompt = prompt_bitmap(MANUAL_PROMPT, MANUAL_PROMPT_WIDTH)
    (args.pixels.parent / "manual_prompt.bin").write_bytes(manual_prompt)
    args.include.write_text(
        "; Generated by tools/make_cover.py.\n"
        f"COVER_FADE_FRAMES = {FADE_FRAMES}\n"
        f"COVER_HALF_BYTES = {len(pixels)//2}\n"
        f"COVER_PROMPT_BYTES = {len(prompt)}\n"
        f"OUTRO_PROMPT_BYTES = {len(outro_prompt)}\n"
        f"OUTRO_PROMPT_WIDTH = {OUTRO_PROMPT_WIDTH}\n"
        f"MANUAL_PROMPT_BYTES = {len(manual_prompt)}\n"
        f"MANUAL_PROMPT_WIDTH = {MANUAL_PROMPT_WIDTH}\n"
        f"DEMO_ASSET_BYTES = {footer_bytes}\n"
        f"DUO_DEMO_ASSET_BYTES = {args.duo_footer.stat().st_size}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
