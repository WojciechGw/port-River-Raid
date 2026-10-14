"""Render real uploaded PSG/OPL register traces (offline, not sound-device recordings).

OPL needs a native library built from opl_preview.c and the firmware's MIT
emu8950 source. PSG uses the BSD model in preview_audio.py. Neither preview
includes host resampling or physical analogue filtering.
"""
import argparse
import ctypes
import json
import math
import struct
import wave
from pathlib import Path
from analyze_audio import FFT,haar_energy
from preview_audio import RATE,Oscillator,render


def render_psg_clocked(trace):
    """Reconstruct timer-clocked engine levels from real IRQ counts/seeds.

    The frame trace omits individual bus-write times. Spread the measured
    ticks evenly within each frame; synth envelopes still run at native rate.
    Effects use their unchanged end-of-frame register snapshots.
    """
    oscillators=[Oscillator() for _ in range(8)]
    samples=[]
    previous=trace[0]['engine_noise']['start_rng']&1
    for entry in trace:
        config=entry['psg']
        for n,oscillator in enumerate(oscillators):
            oscillator.configure(config[n*8:n*8+8])
        noise=entry['engine_noise']
        rng=noise['start_rng']
        count=round(entry['seconds']*RATE)
        accumulator=0
        for _ in range(count):
            accumulator+=noise['ticks']
            if accumulator>=count:
                accumulator-=count
                rng=(rng>>1)^(0xb400 if rng&1 else 0)
                current=rng&1
                for pair,code in ((4,current),(6,previous)):
                    level=noise['level']<<4
                    positive,negative=(240,level) if code else (level,240)
                    for n,value in ((pair,positive),(pair+1,negative)):
                        oscillator=oscillators[n]
                        oscillator.attack=oscillator.decay=value
                previous=current
            left=0
            for oscillator in oscillators:
                l,_=oscillator.output()
                left+=l
                oscillator.step()
            samples.append(max(-32768,min(32767,(left+64)>>7)))
        assert rng==noise['end_rng'], 'Captured IRQ seed/count do not match the noise sequence'
    return samples


def render_opl(trace,library):
    model=ctypes.CDLL(str(library.resolve()))
    model.rr_reset.argtypes=[]
    model.rr_reset.restype=None
    model.rr_write.argtypes=[ctypes.c_uint,ctypes.c_uint]
    model.rr_write.restype=None
    model.rr_sample.argtypes=[]
    model.rr_sample.restype=ctypes.c_int
    model.rr_reset()
    previous=[0]*256
    samples=[]
    for entry in trace:
        registers=entry['opl2']
        # Recreate the key-off before changing operators that occurs inside
        # opl_instrument(), but is not visible in an end-of-frame snapshot.
        for n,slot in enumerate((0,1,2,8,9,10,16,17,18)):
            if any(registers[r+slot]!=previous[r+slot] for r in (0x20,0x23,0xe3)):
                previous[0xb0+n]&=31
                model.rr_write(0xb0+n,previous[0xb0+n])
        for reg,value in enumerate(registers):
            if 0xb0<=reg<=0xb8:
                continue
            if value!=previous[reg]:
                model.rr_write(reg,value)
        # Instruments are installed before notes in the game. In particular,
        # additive connection/type must be set before a modulator's key-on.
        for reg in range(0xb0,0xb9):
            if registers[reg]!=previous[reg]:
                model.rr_write(reg,registers[reg])
        previous=registers.copy()
        samples.extend(model.rr_sample() for _ in range(round(entry['seconds']*RATE)))
    return samples


def measure(samples):
    size=2048
    fft=FFT(size)
    power=[0.0]*(size//2)
    for start in range(0,len(samples)-size+1,size):
        for i,v in enumerate(fft.power(samples[start:start+size])):
            power[i]+=v
    total=sum(power) or 1
    accumulated=0
    for i,v in enumerate(power):
        accumulated+=v
        if accumulated>=total*.9: break
    mean=sum(samples)/len(samples)
    return dict(rms=round(math.sqrt(sum((v-mean)**2 for v in samples)/len(samples))),
                peak=max(abs(v) for v in samples),clipped_samples=sum(abs(v)>=32767 for v in samples),
                rolloff90_hz=round(i*RATE/size),
                above_5khz=round(sum(power[round(5000*size/RATE):])/total,4),
                haar=haar_energy(samples,RATE))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces',type=Path,nargs='+')
    parser.add_argument('--opl-library',type=Path)
    parser.add_argument('--output',type=Path,default=Path('build/audio'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    report={}
    for source in args.traces:
        trace=json.loads(source.read_text(encoding='utf-8'))
        if 'opl2' in trace[0]:
            if not args.opl_library: parser.error('OPL traces require --opl-library')
            samples=render_opl(trace,args.opl_library)
        elif 'engine_noise' in trace[0]:
            samples=render_psg_clocked(trace)
        else:
            samples,_=render(trace,1/60)
        destination=args.output/(source.stem+'.wav')
        with wave.open(str(destination),'wb') as wav:
            wav.setparams((1,2,RATE,len(samples),'NONE','not compressed'))
            wav.writeframes(struct.pack(f'<{len(samples)}h',*samples))
        report[source.stem]=measure(samples)
        print(source.stem, {k:v for k,v in report[source.stem].items() if k!='haar'})
    (args.output/'synth-metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
