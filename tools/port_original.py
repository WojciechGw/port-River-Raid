"""Translate the supplied NTSC DASM listing to ca65 without rewriting rules.

The reference image retains its original $F000 byte layout, loaded as data
at $C000-$CFFF. Native gameplay
procedures use its original tables and reserved zero page $80-$FF. Only the
TIA kernel, RIOT timer wait, hardware addresses, and destructive reset/stack
initialization are replaced by the Picocomputer host. No Atari CPU emulator.
Original: Activision / Carol Shaw, annotations Thomas Jentzsch.
"""
import argparse
import re
from pathlib import Path

VCS = {
    **{name: i for i, name in enumerate("VSYNC VBLANK WSYNC RSYNC NUSIZ0 NUSIZ1 COLUP0 COLUP1 COLUPF COLUBK CTRLPF REFP0 REFP1 PF0 PF1 PF2 RESP0 RESP1 RESM0 RESM1 RESBL AUDC0 AUDC1 AUDF0 AUDF1 AUDV0 AUDV1 GRP0 GRP1 ENAM0 ENAM1 ENABL HMP0 HMP1 HMM0 HMM1 HMBL VDELP0 VDELP1 VDELBL RESMP0 RESMP1 HMOVE HMCLR CXCLR".split())},
    **{name: 0x30+i for i, name in enumerate("CXM0P CXM1P CXP0FB CXP1FB CXM0FB CXM1FB CXBLPF CXPPMM INPT0 INPT1 INPT2 INPT3 INPT4 INPT5".split())},
    "SWCHA": 0x280, "SWCHB": 0x282, "INTIM": 0x284, "TIM64T": 0x296,
}


def active_lines(source):
    flags = dict(NTSC=1, FILL_OPT=1, SCREENSAVER=1, TRAINER=0)
    stack = []
    active = True
    macro = False
    scope = "root"
    result = []
    for number, raw in enumerate(source.splitlines(), 1):
        code = raw.split(";", 1)[0].strip()
        if code.startswith("MAC "):
            macro = True
        if macro:
            if code == "ENDM":
                macro = False
            continue
        if code.startswith("IF "):
            expr = code[3:].strip()
            name, _, value = expr.partition("=")
            truth = bool(flags[name.strip()]) if not value else flags[name.strip()] == int(value)
            stack.append((active, truth))
            active = active and truth
            continue
        if code == "ELSE":
            parent, truth = stack[-1]
            active = parent and not truth
            continue
        if code == "ENDIF":
            active = stack.pop()[0]
            continue
        if not active or not code or code.startswith(("processor", "include")):
            continue
        match = re.fullmatch(r"(\w+)\s+SUBROUTINE", code)
        if match:
            scope = match[1]
            code = scope + ":"
        # DASM local labels are scoped by SUBROUTINE, not by every global label.
        code = re.sub(r"(?<!\w)\.([A-Za-z_]\w*)", lambda m: f"local_{scope}_{m[1]}"
                      if m[1] not in ("byte", "word", "ds") else m[0], code)
        code = code.replace("[", "(").replace("]", ")")
        code = re.sub(r"^(\w+)\.w\s+", r"\1 a:", code)
        code = code.replace("#-1", "#255")
        code = re.sub(r"#~(\w+)", r"#(255^\1)", code)
        if code.startswith("FILL_NOP "):
            result.extend((number, "NOP") for _ in range(int(code.split()[1])))
        elif code.startswith("ORG "):
            result.append((number, ".org $F000"))
        elif code.startswith("align "):
            result.append((number, ".align " + code.split()[1]))
        elif code.startswith(".ds "):
            result.append((number, ".res " + code[4:]))
        else:
            result.append((number, code))
    if stack:
        raise ValueError("Unbalanced source conditionals")
    return result


def generate(source):
    # These slices refer to the supplied, annotated disassembly. Fail closed
    # if its layout changes, rather than silently extract unrelated code.
    anchors = {296: 'START:', 1156: 'DEC    frameCnt', 1805: 'LDA    SWCHB',
               2251: 'STA    PF1Lst,X', 3066: 'InitTab:', 3510: 'LooseJet SUBROUTINE'}
    raw_lines = source.splitlines()
    for number, expected in anchors.items():
        if not raw_lines[number-1].strip().startswith(expected):
            raise ValueError(f'Source layout changed at line {number}; review native slices')
    lines = active_lines(source)
    definitions = set()
    rom_labels = set()
    for _, code in lines:
        match = re.match(r"(\w+)\s*(?:=|:)", code)
        if match:
            definitions.add(match[1])
        if re.match(r"(\w+):", code):
            rom_labels.add(match[1])
    out = ['; Generated from original/riverraid.asm; see tools/port_original.py.',
           '.segment "RR_ROM"', '.export _rr_rom', '_rr_rom:', '.scope reference']
    out += [f"{name} = ${value:04X}" for name, value in VCS.items()]
    out += [code for _, code in lines]
    out += ['.assert * = $10000, error, "Reference image must retain its 4096-byte layout"',
            '.endscope', '.reloc', '.segment "CODE"', '.export _rr_init, _rr_step', '.scope native']
    ranges = [(296,319), (1155,1785), (1804,2288), (2307,2340),
              (3066,3086), (3092,3124), (3430,3460), (3510,3553), (3608,3634)]
    selected = [(n, code) for n,code in lines if any(a<=n<=b for a,b in ranges)]
    live_labels = {re.match(r"(\w+):", c)[1] for _,c in selected if re.match(r"(\w+):", c)}
    live_labels.add("MainLoop")
    out += ['.include "longbranch.mac"']
    # All virtual hardware occupies reserved $0200-$02FF, away from cc65 ZP.
    native_io = {name: (0x200 + value if value < 0x100 else value) for name,value in VCS.items()}
    native_io["INPT4"] = 0x25C  # INPT4-$30 = $022C; player 2 is $022D.
    out += [f"{name} = ${value:04X}" for name,value in native_io.items()]
    for name in sorted(definitions - live_labels):
        relocate = "-$3000" if name in rom_labels else ""
        out.append(f"{name} = reference::{name}{relocate}")
    out += ['; Native reset cannot clear cc65 ZP or change the caller stack.']
    for number, code in selected:
        if number == 297:  # C runtime already initialized the processor.
            code = "CLD"
        if number == 303:
            code = "STA $80,X"
        if number == 304:
            continue  # TXS would destroy the C caller return address.
        if number == 306:
            code = "BPL local_root_loopClear"
        if number == 1810:
            code = "LDX #$77"  # RESET clears $F7-$FF, preserving game selection.
        if number == 1805:
            out.append("LDY #$82 ; Restore Y set by the omitted VSYNC sequence.")
        if number == 1156:
            out += ['JMP MainLoop ; End reset before the omitted display kernel.',
                    'local_DisplayState_frame_step:',
                    'LDY #0 ; Screensaver/joystick code establishes its own Y.']
        # Source relative branches depended on 2-byte TIA accesses. Expand
        # branches in the relocated native code; the reference stays exact.
        code = re.sub(r"^(BCC|BCS|BEQ|BNE|BMI|BPL|BVC|BVS)\b",
                      lambda m: {"BCC":"jcc", "BCS":"jcs", "BEQ":"jeq", "BNE":"jne",
                                 "BMI":"jmi", "BPL":"jpl", "BVC":"jvc", "BVS":"jvs"}[m[0]], code)
        out.append(code)
    out += ['MainLoop: rts', '.endscope', '_rr_init = native::START',
            '_rr_step = native::local_DisplayState_frame_step']
    for label in ('shapePtr1aTab', 'shapePtr1bTab', 'ColorPtrTab', 'ColorTab',
                  'RoadColorTab', 'FuelTab0', 'FuelTab1', 'FuelTab2', 'FuelTab3',
                  'FuelTab4', 'ENABLTab', 'Copyright1', 'Copyright2',
                  'Copyright3', 'Copyright4', 'Copyright5', 'Space', 'Copyright0'):
        out += [f'.export _rr_{label}', f'_rr_{label} = reference::{label}-$3000']
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generate(args.source.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
