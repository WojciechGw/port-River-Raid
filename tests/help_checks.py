"""Function keys and resuming a frozen game after the F1 manual."""
import struct
import re
from pathlib import Path


def run_help_fade_checks(case,sym,boot,output):
    palette_ranges=((0x0100,32),(0x0400,512),(0x0700,14),(0x0720,14),(0xbf80,4),(0x7580,512))
    count=len(palette_ranges)
    words_format='<'+str(sum(size for _,size in palette_ranges)//2)+'H'
    palette_dump=[f'dump xram:0x{address:04x} {size}' for address,size in palette_ranges]
    state_dump=['dump 0x80 128',f'dump 0x{sym["duo_players"]:04x} 46']
    pause=['press p','run 3','release p','run 3']
    for variant in range(3):
        for mono in (False,True):
            name=f'help-fade-game{variant+1}-'+('mono' if mono else 'color')
            commands=boot+['press f2','run 3','release f2','run 8']*variant
            if mono: commands+=['press f4','run 3','release f4','run 3']
            commands+=['press space','run 136','release space','run 4']+pause
            commands+=palette_dump+state_dump+['mark','press f1',
                'wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5',
                'press z','run 3','release z','wait xram:0x00b0 0 120',
                'wait xram:0x00b2 0 160']
            for level in range(33):
                if level: commands+=[f'wait xram:0x00b2 {level} 3']
                commands+=['dump xram:0x00b3 1']+palette_dump+state_dump
                if level in (0,16,32):
                    commands+=[f'shot "{(output/f"{name}-{level}.png").as_posix()}"']
            commands+=['wait xram:0x0080 82 10','run 3','expect-same',
                'peek xram:0x008b 1']+pause+['run 10','dump 0x80 128']
            _,buffers=case(name,commands,rom_args=('/v',))
            words=struct.unpack(words_format,b''.join(buffers[:count]))
            state=buffers[count:count+2]
            times=[]
            for level in range(33):
                offset=count+2+level*(count+3)
                times.append(buffers[offset][0])
                expected=struct.pack(words_format,*((c&32)|((c&31)*level//32)|
                    ((((c>>6)&31)*level//32)<<6)|((((c>>11)&31)*level//32)<<11) for c in words))
                assert b''.join(buffers[offset+1:offset+1+count])==expected, f'{name}: palette level {level}'
                assert buffers[offset+1+count:offset+3+count]==state, f'{name}: game advanced during fade'
            assert all((b-a)&255==2 for a,b in zip(times[1:],times[2:])), 'Uneven fade cadence'
            assert buffers[-1]!=state[0], 'Game did not resume after fade/pause'


def run_life_hud_checks(case, sym, boot, output):
    icons=['dump xram:0x0600 190']
    help_roundtrip=['press f1','wait xram:0x00b0 2 120','release f1',
        'wait xram:0x02a4 222 5','press space','run 3','release space',
        'wait xram:0x0080 82 320','run 4']
    for variant in (0,1):
        select=boot+(['press f2','run 3','release f2','run 8'] if variant else [])
        _,data=case(f'classic-selection-life-icons-game{variant+1}',select+icons+[
            f'shot "{(output / f"game{variant+1}-selection-lives.png").as_posix()}"']+
            help_roundtrip+icons+['press space','run 136','release space','run 4',
                'press p','run 3','release p','run 3']+icons+[
                'poke 0xc0 8','run 3']+icons+[
                f'poke 0xc0 {sym["rr_Copyright0"]&255}','run 3']+icons)
        for sprites,count in zip(data,(3,3,3,1,0)):
            for i in range(9):
                x,y,art,palette,size,options=struct.unpack_from('<hhHHBB',sprites,(i+9)*10)
                assert y==(207 if i<count else -256), f'GAME {variant+1}: expected {count} life icons'
                assert art==0x9c80 and size==0x11 and options==0x42
                assert palette==(0x056c if variant else 0x0100)


def run_help_checks(case, sym, boot, output):
    run_help_fade_checks(case,sym,boot,output)
    run_life_hud_checks(case,sym,boot,output)
    # Use the editable artwork as the reference, so drawing a new note does
    # not require duplicating its pixels in this renderer integration check.
    graphics=(Path(__file__).resolve().parents[1] / 'src/graphics.h').read_text(encoding='utf-8')
    icon_source=graphics.split('static const char sound_icons',1)[1].split('};',1)[0]
    icon_rows=re.findall(r'"([.Xx]{8})"',icon_source)
    assert len(icon_rows)==16
    icons=bytes(sum((pixel in 'Xx') << (7-x) for x,pixel in enumerate(row)) for row in icon_rows)
    note,muted=icons[:8],icons[8:]
    opening = ["press f1", "wait xram:0x0080 0 10",
               "wait xram:0x00b0 2 120", "run 90", "peek xram:0x00b0 2",
               "release f1", "wait xram:0x02a4 222 5"]
    closing = ["press space", "run 3", "release space",
               "wait xram:0x0080 82 320", "run 3"]
    pause = ["press p", "run 3", "release p", "run 3"]
    # Follow real turn changes, rather than forcing PLAYER in a paused game.
    hud_dump=['dump xram:0x0100 32','dump xram:0x056c 24',
              'dump xram:0x0600 190','dump xram:0xa000 1920','dump 0xf4 1']
    game2=boot+['press f2','run 3','release f2','run 8',
                'press space','run 136','release space','run 4']+pause
    _,hud=case('game2-player-hud-colors',game2+hud_dump+[
        f'shot "{(output / "game2-hud-p1.png").as_posix()}"',
        'poke 0xb3 4']+pause+['wait 0xf4 1 240','wait 0xc6 48 300','run 3']+
        pause+hud_dump+[
        f'shot "{(output / "game2-hud-p2.png").as_posix()}"',
        'press f4','run 3','release f4','run 3']+pause+pause+['peek 0x86 15']+hud_dump+
        [f'shot "{(output / "game2-hud-p2-mono.png").as_posix()}"',
         'mark']+opening+closing+['expect-same']+hud_dump+[
        'press f4','run 3','release f4','run 3']+pause+pause+['peek 0x86 255']+hud_dump)
    for turn,player in enumerate((0,1,1,1,1)):
        palette,life_palette,sprites,bitmap,active=hud[turn*5:turn*5+5]
        assert active==bytes((player,))
        assert palette[16:18]==life_palette[22:24], 'Score differs from jet color'
        assert life_palette[:2]==b'\0\0', 'Life icon background must stay transparent'
        for slot in range(9,18):
            assert struct.unpack_from('<H',sprites,slot*10+6)[0]==0x056c
        label=[b for y in range(6,12) for b in bitmap[y*160+12:y*160+20]]
        assert 0x88 in label and all((b>>4) in (8,10) and (b&15) in (8,10) for b in label)
        assert 0x88 in bitmap[5*160+26:11*160], 'Score ink missing'
        ink=int.from_bytes(palette[16:18],'little')
        if turn in (2,3):
            assert (ink&31)==((ink>>6)&31)==(ink>>11), 'P2 HUD remains colored in mono'
        elif turn in (1,4):
            assert ink==0xffe0, 'P2 cyan not restored in color mode'
    assert hud[1][22:24]!=hud[6][22:24], 'P1 and P2 should have different colors'
    assert hud[5][22:24]==hud[0][22:24], 'Turn change altered BRIDGE color'
    _,mono=case('game2-select-after-mono',boot+[
        'press f4','run 3','release f4','run 3',
        'press f2','run 3','release f2','run 8',
        'peek 0x86 15','peek 0xf4 1']+hud_dump+[
        f'shot "{(output / "game2-selection-mono.png").as_posix()}"'])
    ink=int.from_bytes(mono[0][16:18],'little')
    assert (ink&31)==((ink>>6)&31)==(ink>>11), 'Selecting GAME 2 restored P2 cyan in mono'
    assert mono[0][16:18]==mono[1][22:24], 'P2 label/score and life colors differ'
    for variant,verbose in ((v,verbose) for v in range(3) for verbose in (False,True)):
        suffix='' if verbose else '-quiet'
        options=(('/opl2','/V') if variant==1 else ('/v','/opl2')) if verbose else ()
        select=boot+[cmd for _ in range(variant) for cmd in
                     ('press f2','run 3','release f2','run 8')]
        start=select+['press space','run 136','release space','run 4']+pause
        text_dump=['dump xram:0x02c0 12']
        toggle=['press f9','run 3','release f9','run 3']
        cycle=['press f10','run 3','release f10','run 3']
        _,data=case(f'sound-status-game{variant+1}{suffix}',start+[
            'dump xram:0x0220 30','dump xram:0xbf80 4']+text_dump+[
            f'shot "{(output / f"sound-status-on-game{variant+1}{suffix}.png").as_posix()}"']+
            toggle*2+text_dump+[
            f'shot "{(output / f"sound-status-off-game{variant+1}{suffix}.png").as_posix()}"',
            'mark']+opening+closing+['expect-same']+
            cycle+text_dump+cycle+text_dump+cycle+toggle+text_dump+['run 60','mark']+
            opening+closing+['expect-same']+text_dump+[
            'press f4','run 3','release f4','run 3','dump xram:0xbf80 4']+text_dump,
            rom_args=options)
        assert struct.unpack('<BBhhhhHHH',data[0][:16])==(0,0,296,232,3,1,0x02c8,0xbf80,0xffff)
        assert struct.unpack('<BBhhhhHH',data[0][16:])==(0,0,280 if verbose else 312,232,8,8,0x02c0,0xbf80)
        assert data[1]==data[8]==bytes((0,0,255,255)), 'Status is not white on black'
        on=note+b'OPL ' if verbose else bytes(8)+b'    '
        off=muted+b'OFF '
        unmuted=(note if verbose else bytes(8))+b'OPL '
        assert data[2:8]==[on,off,off,off,unmuted,on]
        assert data[9]==on
    snapshot = ["dump 0x80 128", "dump xram:0x0200 16",
                "dump xram:0x0800 7680", "dump xram:0xa000 5920",
                "dump xram:0x0300 250", "dump xram:0x0400 512",
                f'dump 0x{sym["duo_players"]:04x} 46']
    for variant in range(3):
        select = boot + [cmd for _ in range(variant) for cmd in
                         ("press f2", "run 3", "release f2", "run 8")]
        start = select + ["press space", "run 136", "release space", "run 4"]
        for backend in (("pcm", "opl2") if variant==0 else ("pcm",)):
            _, buffers = case(f"help-resume-game{variant+1}-{backend}",
                start+pause+snapshot+["mark"]+opening+[
                    f'shot "{(output / f"help-game{variant+1}.png").as_posix()}"'
                ]+closing+["expect-same", "peek xram:0x008b 1"]+snapshot+
                opening+closing+["expect-same"]+pause+["run 10"],
                rom_args=("/"+backend,))
            before,after=buffers[:7],buffers[7:]
            assert before[0]==after[0], "Manual changed native game state"
            # The ring's unused rows may never have been initialized.
            top=(21-struct.unpack_from("<h",before[1],4)[0])%192
            for y in range(160):
                row=(top+y)%192*40
                assert before[2][row:row+40]==after[2][row:row+40], f"Terrain changed at row {y}"
            assert before[1]==after[1] and before[3:]==after[3:], "Manual changed HUD, sprites, palettes or pilots"

        _,buffers=case(f"help-live-game{variant+1}",start+opening+[
            "dump 0x80 128", f'dump 0x{sym["duo_players"]:04x} 46',
            "run 120", "dump 0x80 128", f'dump 0x{sym["duo_players"]:04x} 46',
            "press q", "run 3", "release q", "wait xram:0x0080 82 320",
            "dump 0x80 128", f'dump 0x{sym["duo_players"]:04x} 46',
            "peek xram:0x008b 0", "run 10", "dump 0x80 128"])
        assert buffers[:2]==buffers[2:4], "Live game advanced while help was open"
        assert buffers[6]!=buffers[4], "Live game did not resume"

    for presses in (1,2,3):
        stage=boot+["press f4", "run 3", "release f4", "run 3"]+[
                    cmd for _ in range(presses) for cmd in
                    ("press f3", "run 3", "release f3", "run 3")]
        _,buffers=case(f"help-later-stage-{presses}",stage+["run 170"]+pause+
            snapshot+["mark"]+
            opening+closing+["expect-same"]+snapshot)
        assert buffers[0]==buffers[7] and buffers[3:7]==buffers[10:14]

    case("help-attract-consumes-escape",boot+opening+[
        "press escape", "run 3", "release escape", "wait xram:0x0080 82 320",
        "run 3", f'peek 0x{sym["ready"]:04x} 2', "peek 0x80 0"])
    _, values=case("remapped-function-keys",boot+pause+[
        "dump 0x0282 1", "press f4", "run 3", "dump 0x0282 1",
        "run 60", "dump 0x0282 1", "release f4", "run 3",
        "press f5", "run 3", "release f5", "run 3", "dump 0x0282 1",
        "press f8", "run 3", "dump 0x0282 1", "run 60", "dump 0x0282 1",
        "release f8", "run 3", "press f6", "run 3", "release f6", "run 3",
        "dump 0x0282 1"])
    assert [v[0] for v in values]==[0x0b,0x03,0x03,0x43,0xc3,0xc3,0xc3]

    for variant in range(3):
        select=boot+[cmd for _ in range(variant) for cmd in
                     ('press f2','run 3','release f2','run 8')]
        start=select+['press space','run 136','release space','run 4']
        for backend in ('opl2','pcm'):
            sound_dump=[f'dump 0x{sym["pcm_amplitude"]:04x} 2',
                        'dump xram:0xc000 256' if backend=='opl2' else
                        'dump xram:0xc000 8']
            flag=f'peek 0x{sym["audio_muted"]:04x}'
            # Check the frame budget through F9/F1. A full terrain rebuild
            # on R can take an extra frame independently of the mute toggle.
            mute=['press f9','run 3','release f9','run 3']*2
            _,buffers=case(f'f9-mute-game{variant+1}-{backend}',start+[flag+' 0']+
                sound_dump+mute+[flag+' 3','peek xram:0x008b 0']+
                sound_dump+['press space','run 20',flag+' 3']+sound_dump+[
                    'release space','release f9','run 3']+pause+opening+closing+[
                    flag+' 3','peek xram:0x008b 1']+sound_dump+pause+[
                    'press f9','run 3','release f9','run 3',flag+' 0']+sound_dump+mute+[flag+' 3',
                    'peek xram:0x009e 0 0',
                    'press r','run 4','release r','run 4',flag+' 3',
                    'press f2','run 3','release f2','run 8',flag+' 3'],
                gameplay=False,rom_args=('/'+backend,))
            amplitudes=buffers[::2]
            assert any(amplitudes[0]) and any(amplitudes[4]), 'F9 did not restore sound'
            assert all(not any(a) for a in amplitudes[1:4]), 'Muted effects remain audible'
            registers=buffers[1::2]
            if backend=='opl2':
                assert all(not (s[0xb0+n]&32) for s in registers[1:4] for n in range(9))
                assert any(registers[4][0xb0+n]&32 for n in range(9))
