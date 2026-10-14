"""Render listening previews from emulator_checks.py's engine parameters.

These are offline PCM/PSG models, not recordings from the host audio device.
The sine, square, noise, sawtooth and triangle waves are implemented. Wave, phase,
envelope and mixer arithmetic follow Picocomputer's BSD-licensed PSG core:
https://github.com/picocomputer/rp6502/blob/main/src/core/aud/psg.c
Copyright (c) 2026 Rumbledethumps, SPDX-License-Identifier: BSD-3-Clause.
The preview omits the host's resampler and analogue output filtering.

License for the adapted PSG model:
Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software without
   specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import argparse
import json
import math
import struct
import wave
from pathlib import Path

RATE = 49716
GAINS = (256, 204, 168, 142, 120, 102, 86, 73,
         61, 50, 40, 31, 22, 14, 7, 0)
ATTACK_MS = (2, 8, 16, 24, 38, 56, 68, 80,
             100, 250, 500, 800, 1000, 3000, 5000, 8000)
RELEASE_MS = (6, 24, 48, 72, 114, 168, 204, 240,
              300, 750, 1500, 2400, 3000, 9000, 15000, 24000)


def increment(milliseconds):
    return (1 << 24) // (RATE * milliseconds // 1000)


class Oscillator:
    def __init__(self):
        self.phase = self.sample = self.volume = 0
        self.noise1, self.noise2 = 0x67452301, 0xEFCDAB89
        self.envelope = "release"

    def configure(self, data):
        self.freq, self.duty, self.attack, self.decay, self.wave, self.pan, _ = \
            struct.unpack("<H6B", bytes(data))
        self.phase_inc = (self.freq << 32) // (3 * RATE)
        if self.pan & 1:
            if self.envelope == "release":
                self.envelope = "attack"
        else:
            self.envelope = "release"

    def output(self):
        sample = (self.sample * (self.volume >> 12) + 2048) >> 12
        pan = int((self.pan if self.pan < 128 else self.pan - 256) / 2)
        if pan == -64:
            return 0, 0
        return sample * (63 - pan), sample * (63 + pan)

    def step(self):
        self.phase = (self.phase + self.phase_inc) & 0xffffffff
        phase=self.phase>>24
        kind=self.wave>>4
        if kind==3:
            half=self.duty>>1
            if phase<128-half or phase>=128+half:
                self.sample=-32767
            elif phase>=128:
                self.sample=32767-((self.phase-0x80000000)>>15)
            else:
                self.sample=(self.phase>>15)-32768
        elif kind==0:
            half=self.duty>>1
            self.sample=round(-math.cos(phase*2*math.pi/256)*32767) \
                if 128-half<=phase<128+half else -32767
        elif phase > self.duty:
            self.sample = -32767
        elif self.wave >> 4 == 4:
            self.noise1 ^= self.noise2
            raw = self.noise2 & 0xffff
            self.sample = raw if raw < 32768 else raw - 65536
            self.noise2 = (self.noise2 + self.noise1) & 0xffffffff
        elif self.wave >> 4 == 1:
            self.sample = 32767
        elif kind==2:
            self.sample=32767-(self.phase>>16)
        else:
            raise ValueError("Unknown PSG waveform")
        target_attack = GAINS[self.attack >> 4] << 16
        target_decay = GAINS[self.decay >> 4] << 16
        if self.envelope == "attack":
            self.volume = min(target_attack, self.volume + increment(ATTACK_MS[self.attack & 15]))
            if self.volume == target_attack:
                self.envelope = "decay"
        elif self.envelope == "decay":
            self.volume = max(0, self.volume - increment(RELEASE_MS[self.decay & 15]))
            if self.volume <= target_decay:
                self.envelope = "sustain"
                if target_decay <= target_attack:
                    self.volume = target_decay
        elif self.envelope == "sustain":
            if target_decay <= target_attack:
                self.volume = target_decay
        else:
            self.volume = max(0, self.volume - increment(RELEASE_MS[self.wave & 15]))


def previous_settings(tia):
    """Former two-voice renderer, including its PWM and volume mapping."""
    config = bytearray()
    for n in range(2):
        control, divisor, volume = tia[n] & 15, (tia[n + 2] & 31) + 1, tia[n + 4] & 15
        hz = 31400 // divisor
        hz = hz >> 1 if control == 4 else hz // 6 if control == 12 else min(hz, 21845)
        config.extend(struct.pack("<H6B", hz * 3, 128, (15 - volume) << 4,
                                  (15 - volume) << 4, 0x40 if control == 8 or control < 4 else 0x10,
                                  bool(volume), 0))
    # Silent third channel; run its noise state as the current renderer does.
    config.extend(struct.pack("<H6B", 0, 255, 240, 240, 0x40, 0, 0))
    return config


def render(trace, seconds, old=False):
    if not old and "amplitude" in trace[0]:
        return render_pcm(trace,seconds)
    count=3 if old else len(trace[0]["psg"])//8
    oscillators = [Oscillator() for _ in range(count)]
    samples, sections = [], []
    for entry in trace:
        config = previous_settings(entry["tia"]) if old else entry["psg"]
        for n, oscillator in enumerate(oscillators):
            oscillator.configure(config[n * 8:(n + 1) * 8])
        begin = len(samples)
        for _ in range(round(entry.get("seconds",seconds) * RATE)):
            left = right = 0
            for oscillator in oscillators:
                l, r = oscillator.output()
                left += l
                right += r
                oscillator.step()
            # The game uses centered pan, so the stereo channels are equal.
            samples.append(max(-32768, min(32767, (left + 64) >> 7)))
        sections.append((begin, len(samples), struct.unpack_from("<H", bytes(config))[0] / 3))
    return samples, sections


def render_pcm(trace,seconds):
    """Match audio.asm, then linearly interpolate like the RIA PCM mixer."""
    phase,poly,bits=[0,0],[0x1ffff,0x12345],[0,0]
    pcm,sections,previous=[],[],0
    for entry in trace:
        begin=len(pcm)
        for _ in range(round(seconds*8000)):
            mixed=0
            for n in range(2):
                amplitude=entry["amplitude"][n]
                if not amplitude:
                    continue
                phase[n]+=min(255,(entry["step"][n]+128)//256)
                if phase[n]>=256:
                    phase[n]-=256
                    if entry["tone"][n]:
                        bits[n]^=1
                    else:
                        carry=poly[n]&1
                        poly[n]>>=1
                        if carry:
                            poly[n]^=0x10010
                bit=bits[n] if entry["tone"][n] else poly[n]&1
                mixed+=amplitude if bit else -amplitude
            pcm.append(((mixed+previous)//2)*256)
            previous=mixed
        sections.append((round(begin*RATE/8000),round(len(pcm)*RATE/8000),0))
    samples=[]
    for i in range(round(len(pcm)*RATE/8000)):
        index,remainder=divmod(i*8000,RATE)
        a,b=pcm[index],pcm[min(index+1,len(pcm)-1)]
        samples.append(a+(b-a)*remainder//RATE)
    return samples,sections


def statistics(samples, sections):
    from analyze_audio import FFT
    fft=FFT(4096)
    result = []
    for begin, end, frequency in sections:
        data = samples[begin + min(RATE//10,(end-begin)//4):end]
        mean = sum(data) / len(data)
        rms = math.sqrt(sum((x - mean) ** 2 for x in data) / len(data))
        real = imaginary = 0.0
        for n, sample in enumerate(data):
            angle = 2 * math.pi * frequency * n / RATE
            real += (sample - mean) * math.cos(angle)
            imaginary += (sample - mean) * math.sin(angle)
        carrier = 2 * math.hypot(real, imaginary) / len(data)
        power=[0.0]*2048
        for start in range(0,len(data)-4095,4096):
            for i,value in enumerate(fft.power(data[start:start+4096])):
                power[i]+=value
        total=sum(power) or 1
        accumulated=0
        for i,value in enumerate(power):
            accumulated+=value
            if accumulated>=total*.9:
                break
        result.append(dict(rms=round(rms, 1), pwm_carrier=round(carrier, 1),
                           peak=max(abs(x) for x in data),rolloff90_hz=round(i*RATE/4096),
                           above_5khz=round(sum(power[round(5000*4096/RATE):])/total,4)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seconds", type=float, default=1.5)
    args = parser.parse_args()
    if not 0.1 <= args.seconds <= 10:
        parser.error("--seconds must be between 0.1 and 10")
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    output = args.output or args.trace.parent / "audio"
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, old in (("jet-before", True), ("jet-after", False)):
        samples, sections = render(trace, args.seconds, old)
        with wave.open(str(output / f"{name}.wav"), "wb") as wav:
            wav.setparams((1, 2, RATE, len(samples), "NONE", "not compressed"))
            wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        report[name] = statistics(samples, sections)
    report["labels"] = [entry["label"] for entry in trace]
    (output / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Offline audio model previews: {output}")


if __name__ == "__main__":
    main()
