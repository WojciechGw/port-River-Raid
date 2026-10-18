"""Translate the supplied NTSC DASM listing to ca65 with 5200 enemy extensions.

The reference image retains its original $F000 byte layout, loaded as data
at $C000-$CFFF. Native gameplay
procedures use its original tables and reserved zero page $80-$FF. Only the
TIA kernel, RIOT timer wait, hardware addresses, and destructive reset/stack
initialization are replaced by the Picocomputer host. Balloons extend native
generation/movement/scoring; bridge tanks use host companions and native
decimal score/reserve rules. No Atari CPU emulator.
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
               2251: 'STA    PF1Lst,X', 3066: 'InitTab:', 3510: 'LooseJet SUBROUTINE',
               1244: 'CPY    #ID_BRIDGE', 1246: 'LDA    frameCnt',
               1415: 'CMP    #ID_BRIDGE', 1574: 'LDA    ScoreTab,Y',
               1590: 'CMP    #<Nine',
               2132: 'LDY    EnemyIdTab,X', 2133: '.newFuel:',
               2250: 'LDA    InitTab,X', 1409: '.checkCollisions:',
               317: 'LDA    #<One', 1830: 'ADC    #DIGIT_H',
               1324: 'LDA    SWCHA', 1655: 'LDX    #MIN_MISSILE', 1659: 'ADC    #$05',
               1666: 'DoSound:', 1819: 'EOR    #$01',
               1809: 'STA    player', 1826: 'STA    player', 3610: 'LDA    gameVariation'}
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
    out += ['.include "longbranch.mac"', '.import _start_level, _ready',
            '.import _duo_tick, _duo_call, _duo_dead, _player_y, _victory_bridge']
    # All virtual hardware occupies reserved $0200-$02FF, away from cc65 ZP.
    native_io = {name: (0x200 + value if value < 0x100 else value) for name,value in VCS.items()}
    native_io["INPT4"] = 0x25C  # INPT4-$30 = $022C; player 2 is $022D.
    out += [f"{name} = ${value:04X}" for name,value in native_io.items()]
    for name in sorted(definitions - live_labels):
        relocate = "-$3000" if name in rom_labels else ""
        if name == "MAX_LEVEL":
            out.append("MAX_LEVEL = 50 ; Allow F3 to select bridge 50; reference stays exact.")
        else:
            out.append(f"{name} = reference::{name}{relocate}")
    out += ['; Native reset cannot clear cc65 ZP or change the caller stack.',
            'ID_BALLOON = 11 ; Picocomputer / 5200 extension']
    for number, code in selected:
        # Extend only the native copy; keep the 4096-byte reference unchanged.
        if number == 1324:
            out += ['LDA gameVariation', 'CMP #2', 'jne port_player_entry',
                    'LDA _ready', 'ORA gameMode', 'jne port_player_entry',
                    'JSR _duo_tick', 'JMP port_shared_sound', 'port_player_entry:']
        if number == 1655:
            # Store absolute screen missile coordinates at launch. Later
            # throttle changes must not drag an already airborne missile.
            code += '\nLDA _duo_call\nbeq port_missile_origin\nLDA #142+MIN_MISSILE\nSEC\nSBC _player_y\nTAX\nport_missile_origin:'
        if number == 1659:
            # Align the muzzle one logical column left, including collision X.
            code = 'ADC #$04'
        if number == 1590:
            code = 'JSR port_life_limit'
        if number == 1666:
            code += '\nLDA _duo_call\nbeq port_shared_sound\nrts\nport_shared_sound:'
        if number == 3510:
            code += '\nPHA\nLDA _duo_call\nbeq port_native_death\nPLA\nLDA #1\nSTA _duo_dead\nrts\nport_native_death:\nPLA'
        if number == 1819:
            code = 'CLC\nADC #1\nCMP #3\nbcc port_select_store\nLDA #0\nport_select_store:'
        if number in (1809, 1826):
            code = 'AND #1\n' + code  # DUO always starts with native player slot zero.
        if number == 3610:
            code += '\nCMP #2\njeq local_SwapPlayers_skipSwap\nCMP #0'
        if number == 1409:
            # Attract mode uses native enemy movement and terrain generation,
            # without fuel consumption, player movement, shots or deaths.
            code += '\nLDA _ready\njne local_DisplayState_doSoundJmp'
        if number == 1244:
            out += ['CPY #ID_BALLOON', 'jeq port_balloon_move']
        if number == 1246:
            out.append('port_balloon_move:')
        if number == 1415:
            out += ['CMP #ID_BALLOON', 'jeq local_DisplayState_noBridge']
        if number == 1574:
            if code != 'LDA    ScoreTab,Y':
                raise ValueError('Review native extended score table hook')
            code = 'LDA port_ScoreTab,Y'
        if number == 1569:
            if code != 'INC    sectionEnd':
                raise ValueError('Review native bridge destruction hook')
            code += '\nJSR _victory_bridge'
        if number == 2133:
            out += ['LDA level', 'CMP #2', 'jcc port_original_enemy',
                    'LDA randomLo', 'AND #$18', 'jne port_original_enemy',
                    'LDY #ID_BALLOON', 'port_original_enemy:']
        if number == 2250:
            # Partial GameInit (respawn/swap) ends at $BC, preserving each
            # player's current level. Only full resets initialize $BD/$C2.
            out += ['CPX #level-PF1Lst', 'jeq port_init_level',
                    'CPX #player2State-PF1Lst', 'jne port_init_native',
                    'port_init_level: LDA _start_level', 'JMP port_init_store',
                    'port_init_native:']
            code += '\nport_init_store:'
        if number == 297:  # C runtime already initialized the processor.
            code = "CLD"
        if number == 303:
            code = "STA $80,X"
        if number == 304:
            continue  # TXS would destroy the C caller return address.
        if number == 306:
            code = "BPL local_root_loopClear"
        if number == 317:
            # GAME has its own HUD field; the startup score must stay zero.
            code = "LDA #<Zero"
        if number == 1830:
            # SELECT formerly put the game number (1/2) in both scores.
            code = "LDA #<Zero"
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
    out += ['MainLoop: rts',
            # Preserve A/X/Y and return comparison flags for both bonus paths.
            'port_life_limit: PHA', 'LDA _duo_call', 'beq port_classic_life_limit',
            'PLA', 'CMP #10*DIGIT_H', 'RTS',
            'port_classic_life_limit: PLA', 'CMP #<Nine', 'RTS',
            # Reuse native section selection on death, but do not swap pilots,
            # subtract lives again, or reset either DUO score.
            'port_duo_restart:', 'LDA #1', 'LDY #31', 'JSR LooseJet',
            'LDX #shapePtr0+2-PF1Lst', 'JSR GameInit',
            'TYA', 'ORA #PF_ROAD_FLAG', 'STA blockLstEnd',
            'LDA randomLoSave', 'STA randomLo',
            'LDA randomHiSave', 'STA randomHi',
            'LDA #0', 'STA gameMode', 'STA speedY', 'RTS',
            'port_ScoreTab: .byte 0,0,0,0,$88,$30,$30,$18,$A8,0,$40,$30',
            # Award 250 in two decimal digits, preserving original reserve
            # increments and the original score-overflow/death sequence.
            'port_tank_bonus:', 'LDA #<MaxOut', 'CMP scorePtr1', 'jeq port_bonus_done',
            'LDA #5*DIGIT_H', 'LDX #8', 'JSR port_bonus_digit',
            'LDA #<MaxOut', 'CMP scorePtr1', 'jeq port_bonus_done',
            'LDA #2*DIGIT_H', 'LDX #6', 'JMP port_bonus_digit',
            'port_bonus_done: RTS',
            'port_bonus_digit:', 'PHA', 'CPX #2', 'jne port_bonus_score',
            'LDA livesPtr', 'JSR port_life_limit', 'jeq port_bonus_score',
            'jcc port_bonus_life', 'LDA #$FF',
            'port_bonus_life: ADC #DIGIT_H', 'STA livesPtr',
            'port_bonus_score: LDA scorePtr1,X', 'CMP #<Space', 'jne port_bonus_add',
            'LDA #0', 'STA scorePtr1,X',
            'port_bonus_add: PLA', 'CLC', 'ADC scorePtr1,X', 'CMP #<MaxOut',
            'jcc port_bonus_store', 'SBC #<MaxOut', 'STA scorePtr1,X',
            'LDA #DIGIT_H', 'DEX', 'DEX', 'jpl port_bonus_digit',
            'LDA #<MaxOut', 'LDX #10', 'JSR SetScorePtr1',
            'LDA #<Copyright0', 'STA livesPtr', 'JMP port_tank_crash',
            'port_bonus_store: STA scorePtr1,X', 'RTS',
            'port_tank_crash: LDA #1', 'LDY #$1F', 'JMP LooseJet',
            '.endscope', '_rr_init = native::START',
            '_rr_step = native::local_DisplayState_frame_step',
            '.export _rr_tank_bonus, _rr_tank_crash',
            '_rr_tank_bonus = native::port_tank_bonus',
            '_rr_tank_crash = native::port_tank_crash',
            '.export _rr_duo_player', '_rr_duo_player = native::port_player_entry',
            '.export _rr_duo_restart', '_rr_duo_restart = native::port_duo_restart']
    for label in ('shapePtr1aTab', 'shapePtr1bTab', 'ColorPtrTab', 'ColorTab',
                  'RoadColorTab', 'FuelTab0', 'FuelTab1', 'FuelTab2', 'FuelTab3',
                  'FuelTab4', 'ENABLTab', 'Copyright1', 'Copyright2',
                  'Copyright3', 'Copyright4', 'Copyright5', 'Space', 'Copyright0', 'Zero',
                  'JetStraight', 'JetMove', 'JetExplode'):
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
