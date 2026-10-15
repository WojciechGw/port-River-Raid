"""Function keys and resuming a frozen game after the F1 manual."""
import struct


def run_help_checks(case, sym, boot, output):
    opening = ["press f1", "wait xram:0x0080 0 10",
               "wait xram:0x00b0 2 120", "run 90", "peek xram:0x00b0 2",
               "release f1", "wait xram:0x02a4 222 5"]
    closing = ["press space", "run 3", "release space",
               "wait xram:0x0080 82 240", "run 3"]
    pause = ["press p", "run 3", "release p", "run 3"]
    snapshot = ["dump 0x80 128", "dump xram:0x0200 16",
                "dump xram:0x0800 7680", "dump xram:0xa000 5920",
                "dump xram:0x0300 250", "dump xram:0x0400 512",
                f'dump 0x{sym["duo_players"]:04x} 46']
    for variant in range(3):
        select = boot + [cmd for _ in range(variant) for cmd in
                         ("press f2", "run 3", "release f2", "run 8")]
        start = select + ["press space", "run 140", "release space", "run 4"]
        for backend in (("pcm", "opl2", "psg") if variant==0 else ("pcm",)):
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
            "press q", "run 3", "release q", "wait xram:0x0080 82 240",
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
        "press escape", "run 3", "release escape", "wait xram:0x0080 82 240",
        "run 3", f'peek 0x{sym["ready"]:04x} 2', "peek 0x80 0"])
    _, values=case("remapped-function-keys",boot+pause+[
        "dump 0x0282 1", "press f4", "run 3", "dump 0x0282 1",
        "run 60", "dump 0x0282 1", "release f4", "run 3",
        "press f5", "run 3", "release f5", "run 3", "dump 0x0282 1",
        "press f8", "run 3", "dump 0x0282 1", "run 60", "dump 0x0282 1",
        "release f8", "run 3", "press f6", "run 3", "release f6", "run 3",
        "dump 0x0282 1"])
    assert [v[0] for v in values]==[0x0b,0x03,0x03,0x43,0xc3,0xc3,0xc3]
