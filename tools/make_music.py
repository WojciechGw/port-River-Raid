"""Build a flight arrangement and complete OPL scores without PCM.

All source notes remain in intro-score.json. Flight keeps its lead/harmony,
with a quieter three-part texture, syncopated bass and an answering arpeggio.
Fallback drums use three decaying FM voices.
"""
import argparse
import copy
import json
import math
import random
import struct
from pathlib import Path
from make_intro import SLOTS, pitch, compile_score

RATE = 16000
FLIGHT_GAIN = 0.7
# YM3812 total level has 0.75 dB steps: four steps give 70.8% amplitude.
FLIGHT_ATTENUATION = round(-20*math.log10(FLIGHT_GAIN)/0.75)
DRUMS = (
    dict(mod=[1,63,0xf8,0x68],car=[1,16,0xf8,0x68],feedback=0),
    dict(mod=[0x0f,0,0xf8,0x68],car=[1,27,0xf8,0x68],feedback=14),
    dict(mod=[0x0e,0,0xf9,0x79],car=[7,36,0xf9,0x79],feedback=14),
)


def quieten_flight_track(track):
    level = track['instrument']['car'][1]
    track['instrument']['car'][1] = (level & 0xc0) | min(63, (level & 63)+FLIGHT_ATTENUATION)
    for note in track['notes']:
        note[3] = min(63, note[3]+FLIGHT_ATTENUATION)


def flight_score(source):
    score = copy.deepcopy(source)
    score['title'] = 'River Raid — flight variation'
    score['tracks'] = [copy.deepcopy(source['tracks'][i]) for i in (0,4,5)]
    for index, track in enumerate(score['tracks']):
        track['name'] = ('syncopated bass','lead variation','answering arpeggio')[index]
        track['instrument']['car'][1] += (8,10,12)[index]
        for note in track['notes']:
            note[3] += (8,10,12)[index]
            if index == 1:
                # Preserve the motif, soften its register on alternate phrases.
                note[2] -= 12 if (note[0]//16)%2 else 0
            if index == 2:
                note[2] -= 12
        if index == 0:
            roots = [next(n[2] for n in track['notes'] if n[0] == bar*16) for bar in range(8)]
            track['notes'] = [[bar*16+s, length, root+octave, 16]
                for bar,root in enumerate(roots)
                for s,length,octave in ((0,3,0),(3,1,12),(6,2,0),(8,3,0),(11,1,7),(14,2,12))]
        quieten_flight_track(track)
    return score


def drum_events(steps, flight=False):
    result = []
    for step in range(steps):
        s = step%16
        fill = step//16 == steps//16-1
        if s in ((0,7,8,14) if flight else (0,6,8,10)) and not (fill and s>=8):
            result.append((step,0,36,16))
        if s in (4,12) or (fill and s in (10,11,14,15)):
            result.append((step,1,54,27))
        # Eighth-note hats leave room for effects; last bar adds a short fill.
        if not s%2 or (fill and s>=12):
            result.append((step,2,90,36 if not s%4 else 32))
    return result


def pcm_drums(score):
    length = score['steps']*score['samples_per_step']
    samples = [0.0]*length
    rng = random.Random(6502)
    for step,drum,note,level in drum_events(score['steps'],True):
        start = step*score['samples_per_step']
        phase = 0.0
        for i in range(min((2800,1800,500)[drum],length-start)):
            t = i/RATE
            if drum == 0:
                phase += 2*math.pi*(48+100*math.exp(-t/0.022))/RATE
                value = math.sin(phase)*math.exp(-t/0.10)*0.55
            elif drum == 1:
                value = (rng.uniform(-1,1)*0.65+math.sin(2*math.pi*185*t)*0.35)*math.exp(-t/0.045)*0.36
            else:
                value = rng.uniform(-1,1)*math.exp(-t/0.009)*0.12
            samples[start+i] += value
    return bytes(max(-127,min(127,round(v*100*FLIGHT_GAIN)))&255 for v in samples)


def compact(score, flight=False):
    # Three melodic voices leave three drums and three OPL effects.
    tracks = copy.deepcopy(score['tracks'] if flight else [score['tracks'][i] for i in (0,4,5)])
    for drum,instrument in enumerate(DRUMS):
        hits=[(s,n,l) for s,d,n,l in drum_events(score['steps'],flight) if d==drum]
        track = dict(name=('kick','snare','hat')[drum],instrument=copy.deepcopy(instrument),
            notes=[[s,(hits[i+1][0] if i+1<len(hits) else score['steps'])-s,n,l]
                   for i,(s,n,l) in enumerate(hits)])
        if flight:
            quieten_flight_track(track)
        tracks.append(track)
    return compile_score(dict(score,tracks=tracks))


def fallback_jingle(score):
    """Keep original timings/pitches; reserve channels 3..5 for percussion."""
    output = bytearray()
    # The source lead is ch4; bass ch0 and harmony ch1 retain the harmony.
    channels = (0,4,1)
    for index,record in enumerate(score['records']):
        writes = []
        def reg(r,v): writes.append((r,v))
        if index == 0:
            reg(1,32); reg(0xbd,0)
            for ch,patch in enumerate(DRUMS,3):
                slot=SLOTS[ch]
                for r,v in zip((0x20,0x40,0x60,0x80),patch['mod']): reg(r+slot,v)
                for r,v in zip((0x23,0x43,0x63,0x83),patch['car']): reg(r+slot,v)
                reg(0xc0+ch,patch['feedback'])
        for address,value in record['writes']:
            for ch,source in enumerate(channels):
                src,dst=SLOTS[source],SLOTS[ch]
                mapping={base+src+op:base+dst+op for base in (0x20,0x40,0x60,0x80,0xe0) for op in (0,3)}
                mapping.update({base+source:base+ch for base in (0xa0,0xb0,0xc0)})
                if address in mapping: reg(mapping[address],value)
        # Percussion follows each original musical event; silence at the tail.
        if index<len(score['records'])-2:
            drum=0 if index%4==0 else 1 if index%4==2 else 2
            ch=3+drum
            lo,hi=pitch((36,54,90)[drum])
            reg(0xb0+ch,hi&~32); reg(0xa0+ch,lo); reg(0xb0+ch,hi)
        assert len(writes)<256
        output.extend(struct.pack('<HB',record['samples'],len(writes)))
        output.extend(v for pair in writes for v in pair)
    output.extend(b'\0\0\0')
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path); p.add_argument('output',type=Path)
    p.add_argument('--opl-only',action='store_true',help='Omit hybrid scores and PCM samples')
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    source=json.loads((a.source/'intro-score.json').read_text())
    flight=flight_score(source)
    if not a.opl_only:
        (a.output/'flight-score.json').write_text(json.dumps(flight,indent=2)+'\n',encoding='utf-8')
        (a.output/'flight-score.bin').write_bytes(compile_score(flight))
        (a.output/'flight-drums.pcm').write_bytes(pcm_drums(flight))
    sizes=[]
    for name,score in (('intro',source),('flight',flight),
                       ('gameover',json.loads((a.source/'gameover-score.json').read_text())),
                       ('victory',json.loads((a.source/'victory-score.json').read_text()))):
        data=compact(score,name=='flight') if name in ('intro','flight') else fallback_jingle(score)
        assert len(data)<=(0x700 if name=='intro' else 0x2000),(name,len(data))
        (a.output/f'{name}-opl.bin').write_bytes(data)
        sizes.append(len(data))
        print(name,len(data))
    (a.output/'music.inc').write_text('MUSIC_SCORE_BYTES = '+str(len(compile_score(flight)))+'\n'+
        'music_sizes_lo: .lobytes '+','.join(map(str,sizes))+'\n'+
        'music_sizes_hi: .hibytes '+','.join(map(str,sizes))+'\n')


if __name__=='__main__': main()
