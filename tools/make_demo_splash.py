"""Pack a 128x64 indexed BMP into two unscaled Mode 5 64x64 sprites."""
import argparse
import struct
from pathlib import Path


def build(path):
    bmp=Path(path).read_bytes()
    if len(bmp)<54 or bmp[:2]!=b'BM':
        raise ValueError('Expected a Windows indexed BMP')
    offset=struct.unpack_from('<I',bmp,10)[0]
    dib,width,height,planes,bpp,compression=struct.unpack_from('<IiiHHI',bmp,14)
    count=struct.unpack_from('<I',bmp,46)[0] or 256
    if dib<40 or (width,abs(height),planes,bpp,compression)!=(128,64,1,8,0):
        raise ValueError('Demo splash must be an uncompressed 128x64 8bpp BMP')
    if not 1<=count<=256 or 14+dib+count*4>offset or len(bmp)<offset+8192:
        raise ValueError('Truncated BMP palette or pixels')
    rows=[bmp[offset+y*128:offset+(y+1)*128] for y in range(64)]
    if height>0: rows.reverse()
    if max(b''.join(rows))>=count:
        raise ValueError('Demo splash uses an index outside its BMP palette')
    colors=[]
    mono=[]
    for i in range(256):
        b,g,r=bmp[14+dib+i*4:14+dib+i*4+3] if i<count else (0,0,0)
        opaque=32 if r or g or b else 0
        r,g,b=r>>3,g>>3,b>>3
        colors.append((b<<11)|(g<<6)|opaque|r)
        gray=(r+2*g+b)//4
        mono.append((gray<<11)|(gray<<6)|opaque|gray)
    left=b''.join(row[:64] for row in rows)
    right=b''.join(row[64:] for row in rows)
    return left+right+struct.pack('<512H',*(colors+mono))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.write_bytes(build(args.source))
