"""F3 start selection in all game modes, HUD, restart and player changes."""
import struct
from emulator_checks import poke


def run_bridge_selection_checks(case,sym,boot,fixture,resume):
    levels=(5,10,15,20,25,30,35,40,45,49,1,5)
    for variant in range(3):
        commands=boot+["press f2", "run 3", "release f2", "run 8"]*variant+["peek 0xbd 1"]
        for level in levels:
            commands += ["press f3", "run 3",
                         f'peek 0x{sym["start_level"]:04x} {level}', "run 32",
                         f'peek 0x{sym["start_level"]:04x} {level}',
                         f'peek 0x{sym["ready"]:04x} 2',"peek xram:0x0082 3",
                         f'peek 0x{sym["demo_splash_out"]:04x} 0',
                         "dump xram:0x0696 20" if variant==2 else "dump xram:0x060a 20",
                         "release f3", "run 3"]
        # Selecting did not launch. A separate Start press uses the choice
        # for both native player states, including the newly added bridge 15.
        commands += ["press f3","run 3","release f3","run 3"]*2
        commands += ["press space","run 136","release space","run 4",
                     f'peek 0x{sym["ready"]:04x} 0',"peek xram:0x0082 1",
                     "peek 0xbd 15","peek 0xc2 15"]
        commands += ["press p","run 3","release p","run 3","mark",
                     "press f3","run 32","release f3","run 3",
                     f'peek 0x{sym["start_level"]:04x} 20',"peek 0xbd 15",
                     "peek xram:0x008b 1","expect-same",
                     "press r","run 3","release r","run 3",
                     "peek 0xbd 20","peek 0xc2 20","peek xram:0x008b 0"]
        _, hud_numbers=case(f"bridge-difficulty-cycle-game{variant+1}",commands)
        for level,sprites in zip(levels,hud_numbers):
            for digit in (0,1):
                _,y,image,_,_,_=struct.unpack_from("<hhHHBB",sprites,digit*10)
                assert image==0x9e00+(level//10 if digit==0 else level%10)*32
                assert (y>=0)==(digit==1 or level>=10), "Incorrect BRIDGE digit visibility"

    case("bridge-difficulty-paused-restart",fixture+[poke(0xcd+10,40),"run 2","mark",
         "press f3", "run 3", "release f3", "run 3",
         f'peek 0x{sym["start_level"]:04x} 5',"peek 0xbd 1",
         "peek xram:0x008b 1","expect-same",poke(0xbd,7),
         "press r", "run 3", "release r", "run 3", "peek 0xbd 5", "peek 0xc2 5",
         "peek xram:0x008b 0","peek xram:0x0090 88 88 88 88 88 0"])

    commands=boot+["press f2", "run 2", "release f2", "run 2", "peek 0x80 1"]
    for _ in range(4):
        commands += ["press f3", "run 3", "release f3", "run 3"]
    case("bridge-difficulty-two-players",commands+[f'peek 0x{sym["ready"]:04x} 2',
         "press space", "run 136", "release space", "run 4",
         "peek 0xbd 20", "peek 0xc2 20","peek 0xf4 0",
         "press p", "run 3", "release p", "run 3",
         poke(0xb3,4)]+resume+["wait 0xf4 1 240", "wait 0xc6 48 300", "run 3",
         "peek 0xbd 20", "peek 0xc2 20"])

    case("bridge-difficulty-respawn",fixture+[poke(sym["start_level"],20),
         poke(0xbd,50),poke(0xb3,4)]+resume+["wait 0xc6 48 300", "run 3",
         "peek 0xbd 50"])

