"""Check rendered OPL previews and optionally build a reference comparison.

Run preview_synth.py first. These are model-based checks, not recordings of
the emulator's sound device. The optional reference is an external PCM16 WAV;
it is never packaged in the game. Comparison clips have matched RMS levels.
Reference crop positions correspond to the supplied Atari XL/XE RiverRaid.wav.
"""
import argparse
import json
import math
import struct
import wave
from pathlib import Path
from analyze_audio import FFT, read_mono
from preview_audio import RATE
from preview_synth import measure


def resample(data, source_rate):
    result=[]
    for i in range(round(len(data)*RATE/source_rate)):
        j,t=divmod(i*source_rate,RATE)
        j=min(j,len(data)-1)
        result.append(data[j]+(data[min(j+1,len(data)-1)]-data[j])*t/RATE)
    return result


def peak_fraction(samples):
    fft=FFT(2048)
    power=[0.0]*1024
    for start in range(0,len(samples)-2048+1,2048):
        for i,value in enumerate(fft.power(samples[start:start+2048])):
            power[i]+=value
    return max(power)/sum(power)


def short_time_peak_fraction(samples):
    """Detect moving tonal components that a whole-clip spectrum smears out."""
    fft=FFT(1024)
    peaks=[]
    for start in range(0,len(samples)-1024+1,1024):
        power=fft.power(samples[start:start+1024])
        peaks.append(max(power)/(sum(power) or 1))
    return sum(peaks)/len(peaks)


def envelope_variation(samples):
    """Relative RMS fluctuation in 50 ms windows, after the initial attack.

    Catches slow amplitude beating/tremolo even when its carrier is noise.
    Use on constant-throttle captures, not acceleration or effect overlaps.
    """
    size=round(RATE*.05)
    rms=[math.sqrt(sum(v*v for v in samples[start:start+size])/size)
         for start in range(size*2,len(samples)-size+1,size)]
    mean=sum(rms)/len(rms)
    return math.sqrt(sum((v-mean)**2 for v in rms)/len(rms))/(mean or 1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previews',type=Path,default=Path('build/audio-v2'))
    parser.add_argument('--reference',type=Path)
    args=parser.parse_args()
    report={}
    audio={}
    for backend in ('opl2',):
        for name in ('engine-slow','engine-fast','explosion','missile','overlap','all-voices'):
            rate,samples=read_mono(args.previews/f'audio-{backend}-{name}.wav')
            assert rate==RATE
            metrics=measure(samples)
            assert metrics['rms']>100 and metrics['clipped_samples']==0, f'{backend}/{name}: silence or clipping'
            if name.startswith('engine'):
                metrics['largest_fft_bin_fraction']=round(peak_fraction(samples),4)
                # OPL now deliberately uses broadband feedback noise;
                # the former low FM bands retained audible engine notes.
                assert 18000<metrics['rolloff90_hz']<24000, f'{backend}/{name}: narrow/tonal noise'
                assert metrics['largest_fft_bin_fraction']<.03, f'{backend}/{name}: fixed tone/hum'
                metrics['short_time_peak_fraction']=round(short_time_peak_fraction(samples),4)
                assert metrics['short_time_peak_fraction']<.035, f'{backend}/{name}: moving tonal engine components'
                metrics['envelope_variation']=round(envelope_variation(samples),4)
                assert metrics['envelope_variation']<.05, f'{backend}/{name}: engine beating/tremolo'
            if backend=='opl2' and name=='explosion':
                assert 550<metrics['rolloff90_hz']<1300 and metrics['above_5khz']<.02, 'Metallic/trebly OPL blast'
            audio[backend,name]=samples
            report[backend+'-'+name]=metrics
            print('PASS',backend,name,{k:v for k,v in metrics.items() if k!='haar'})
        slow=report[backend+'-engine-slow']['rolloff90_hz']
        fast=report[backend+'-engine-fast']['rolloff90_hz']
        assert report[backend+'-engine-fast']['rms']>report[backend+'-engine-slow']['rms']*1.5, \
            'OPL engine volume does not respond to throttle'

    if args.reference:
        rate,reference=read_mono(args.reference)
        listen=[]
        labels=[]
        for name,start,end in (('engine-slow',1.5,2.5),('engine-fast',19,20),
                               ('missile',7.90,8.23),('explosion',25.68,26.19)):
            ref=resample(reference[round(start*rate):round(end*rate)],rate)
            report['reference-'+name]=measure(ref)
            for label,samples in ((name+' reference',ref),
                                  (name+' OPL2 model',audio['opl2',name][:len(ref)])):
                mean=sum(samples)/len(samples)
                rms=math.sqrt(sum((v-mean)**2 for v in samples)/len(samples))
                labels.append(dict(label=label,start_seconds=round(len(listen)/RATE,3),
                                   duration_seconds=round(len(samples)/RATE,3)))
                listen.extend(round(max(-32768,min(32767,(v-mean)*3000/rms))) for v in samples)
                listen.extend([0]*round(RATE*.4))
        with wave.open(str(args.previews/'reference-vs-synth.wav'),'wb') as wav:
            wav.setparams((1,2,RATE,len(listen),'NONE','not compressed'))
            wav.writeframes(struct.pack(f'<{len(listen)}h',*listen))
        (args.previews/'reference-vs-synth.json').write_text(json.dumps(labels,indent=2),encoding='utf-8')
    (args.previews/'verified-synth-metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
