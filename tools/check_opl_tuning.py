"""Render CPU register captures and verify OPL2 noise and relative gain.

Requires tests/emulator_checks.py --opl-tuning-only and the optional emu8950
preview DLL. --baseline contains captures made before the gain change.
This measures the synthesizer model, not audio recorded from physical hardware.
"""
import argparse
import json
import struct
import wave
from pathlib import Path
from preview_synth import render_opl,measure
from compare_synth import peak_fraction,short_time_peak_fraction,envelope_variation


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--traces',type=Path,default=Path('build/cc65/release/checks'))
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--opl-library',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('build/opl-tuning'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    report={}
    for name in ('engine-slow','engine-fast','engine-shared-slow','engine-shared-fast','flight-music'):
        trace=json.loads((args.traces/f'opl-tuning-{name}.json').read_text())
        if name.startswith('engine-shared'):
            # Isolate the engine's actual shared voice from the captured mix.
            for entry in trace:
                for ch in range(6): entry['opl2'][0xb0+ch]&=~32
        samples=render_opl(trace,args.opl_library)
        metrics=measure(samples)
        assert metrics['rms']>100 and metrics['clipped_samples']==0
        if name.startswith('engine'):
            metrics['largest_bin_fraction']=peak_fraction(samples)
            metrics['short_time_peak_fraction']=short_time_peak_fraction(samples)
            metrics['envelope_variation']=envelope_variation(samples)
            assert metrics['largest_bin_fraction']<.035, f'{name}: tonal noise'
            assert metrics['short_time_peak_fraction']<.04, f'{name}: moving tonal components'
            assert metrics['envelope_variation']<.06, f'{name}: pulsating noise'
        if args.baseline and not name.startswith('engine-shared'):
            before=json.loads((args.baseline/f'opl-tuning-{name}.json').read_text())
            old=measure(render_opl(before,args.opl_library))
            metrics['rms_ratio']=metrics['rms']/old['rms']
            low,high=(1.04,1.06) if name=='flight-music' else (.83,.86)
            assert low<metrics['rms_ratio']<high, f'{name}: wrong gain change'
        with wave.open(str(args.output/f'{name}.wav'),'wb') as stream:
            stream.setparams((1,2,49716,0,'NONE','NONE'))
            stream.writeframes(struct.pack('<'+'h'*len(samples),*samples))
        report[name]=metrics
        print('PASS',name,{k:v for k,v in metrics.items() if k!='haar'},flush=True)
    (args.output/'measurements.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
