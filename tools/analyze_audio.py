"""Measure a PCM16 reference recording with a dependency-free short-time FFT."""
import argparse
import array
import csv
import json
import math
import struct
import sys
import wave
import zlib
from pathlib import Path


def read_mono(path):
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2:
            raise ValueError("Expected 16-bit PCM WAV")
        rate, channels = source.getframerate(), source.getnchannels()
        raw = array.array("h", source.readframes(source.getnframes()))
    if sys.byteorder != "little":
        raw.byteswap()
    mono = [sum(raw[i:i+channels])/channels for i in range(0, len(raw), channels)]
    return rate, mono


def haar_energy(samples,rate,levels=8):
    """Haar detail energies; frequency bounds are nominal dyadic bands.

    Haar has broad overlapping filters. Use this to compare transient grain
    across scales, not as a sharp bandpass or a waveform upload for OPL2.
    """
    mean=sum(samples)/len(samples)
    coarse=[v-mean for v in samples]
    energies=[]
    for level in range(1,levels+1):
        pairs=len(coarse)//2
        detail=[(coarse[i*2]-coarse[i*2+1])/math.sqrt(2) for i in range(pairs)]
        coarse=[(coarse[i*2]+coarse[i*2+1])/math.sqrt(2) for i in range(pairs)]
        energies.append(dict(level=level,nominal_low_hz=rate/(2**(level+1)),
                             nominal_high_hz=rate/(2**level),energy=sum(v*v for v in detail)))
    residual=sum(v*v for v in coarse)
    total=sum(item["energy"] for item in energies)+residual or 1
    for item in energies:
        item["fraction"]=round(item.pop("energy")/total,5)
    return dict(details=energies,residual_fraction=round(residual/total,5))


class FFT:
    def __init__(self, size):
        self.size = size
        bits = size.bit_length()-1
        self.reverse = [int(f"{i:0{bits}b}"[::-1], 2) for i in range(size)]
        self.twiddle = [complex(math.cos(-2*math.pi*i/size), math.sin(-2*math.pi*i/size))
                        for i in range(size//2)]
        self.window = [.5-.5*math.cos(2*math.pi*i/(size-1)) for i in range(size)]

    def power(self, samples):
        mean = sum(samples)/self.size
        data = [complex((samples[i]-mean)*self.window[i]/32768) for i in self.reverse]
        length = 2
        while length <= self.size:
            half, stride = length//2, self.size//length
            for start in range(0, self.size, length):
                for j in range(half):
                    a = data[start+j]
                    b = data[start+j+half]*self.twiddle[j*stride]
                    data[start+j], data[start+j+half] = a+b, a-b
            length *= 2
        return [v.real*v.real+v.imag*v.imag for v in data[:self.size//2]]


def png(path, columns, rate, size):
    """Log-frequency heatmap: 40 Hz at bottom, 10 kHz at top, -90..-10 dB."""
    height, width = 256, len(columns)
    bins = [min(size//2-1, round(10000*(40/10000)**(y/(height-1))*size/rate))
            for y in range(height)]
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for column in columns:
            power = column[bins[y]]/(size*size)
            level = max(0, min(1, (10*math.log10(max(power, 1e-12))+90)/80))
            rows.extend((round(255*min(1,level*2)), round(255*max(0,level*2-1)),
                         round(120*max(0,1-abs(level-.3)*3))))

    def chunk(kind, data):
        return struct.pack(">I", len(data))+kind+data+struct.pack(">I", zlib.crc32(kind+data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n"+
                     chunk(b"IHDR", struct.pack(">IIBBBBB", width,height,8,2,0,0,0))+
                     chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def analyze(path, output):
    rate, mono = read_mono(path)
    size, hop = 4096, 2048
    fft = FFT(size)
    columns, measurements = [], []
    for start in range(0, len(mono)-size+1, hop):
        samples = mono[start:start+size]
        power = fft.power(samples)
        columns.append(power)
        total = sum(power) or 1
        centroid = sum(i*rate/size*v for i,v in enumerate(power))/total
        accumulated, rolloff = 0, 0
        for i,value in enumerate(power):
            accumulated += value
            if accumulated >= total*.9:
                rolloff = i*rate/size
                break
        peaks = sorted((i for i in range(2,len(power)-1)
                        if power[i]>power[i-1] and power[i]>=power[i+1]),
                       key=lambda i:power[i], reverse=True)[:5]
        mean = sum(samples)/size
        rms = math.sqrt(sum((v-mean)**2 for v in samples)/size)/32768
        bands = [sum(power[round(a*size/rate):round(b*size/rate)])/total
                 for a,b in ((0,250),(250,1000),(1000,5000),(5000,rate/2))]
        measurements.append(dict(time=round((start+size/2)/rate,3),
                                 rms_db=round(20*math.log10(max(rms,1e-8)),1),
                                 centroid_hz=round(centroid),rolloff90_hz=round(rolloff),
                                 peaks_hz=[round(i*rate/size,1) for i in peaks],
                                 bands=[round(v,3) for v in bands]))
    output.mkdir(parents=True, exist_ok=True)
    report = dict(file=str(path),rate=rate,duration=len(mono)/rate,
                  window=size,hop=hop,measurements=measurements,haar=haar_energy(mono,rate))
    (output/"analysis.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    with (output/"analysis.csv").open("w", newline="",encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(("time","rms_db","centroid_hz","rolloff90_hz","peaks_hz","bands"))
        for frame in measurements:
            writer.writerow(frame.values())
    png(output/"spectrogram.png",columns,rate,size)
    print(f"{len(mono)/rate:.3f} s at {rate} Hz; {len(measurements)} spectral windows")
    for frame in measurements[::round(rate/hop/2)]:
        print(frame)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav",type=Path)
    parser.add_argument("--output",type=Path,default=Path("build/audio-reference"))
    arguments = parser.parse_args()
    analyze(arguments.wav,arguments.output)
