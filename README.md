# River Raid for Picocomputer 6502

<!-- rp6502
preset: cc65/Release
publish: riverraid.zip
-->
[![Play River Raid](https://wojciechgw.github.io/port-River-Raid/riverraid/screenshot.png)](https://wojciechgw.github.io/port-River-Raid/riverraid/)

[Play it in your browser](https://wojciechgw.github.io/port-River-Raid/riverraid/).


A River Raid port for Picocomputer 6502 that runs the original game logic natively.
The reference source is `original/riverraid.asm`: Thomas Jentzsch's annotated
disassembly of the **Atari 2600** version. Original game and graphics:
Activision, 1982; designer Carol Shaw.

The original 6502 routines handle the course, enemies, acceleration, fuel,
scoring, extra lives, respawning in the saved section, and two-player games.
The graphics combine original bitmaps with a palette and scenery inspired
by Atari XL and 5200 screenshots: smooth brown banks of varying width,
five mountain variants (blue slopes or black ridges), and dark blue water.
The added balloons have multicolored envelopes and baskets, while tanks
drive along the roads across bridges. From bridge 7, additional tanks
approach the river from either side and fire from the banks at random distances.
The entire largest impact circle stays within the water; tanks facing an
island fire into their own channel. Both tank types
have three-frame animated tracks, running at half the helicopter animation cadence. Tank rounds in flight
do not harm the plane; their growing white filled circles on the water do.
The reference tank silhouette has a distinct barrel and separated black wheels.
Two helicopter variants share animated salmon rotors. From level 5, one in
four new helicopters has an olive fuselage stripe and fires pale horizontal
shots that can hit the player's plane. Its shots disappear at the riverbank
or an island.
Each small, medium, and large impact circle is erased before the next phase.
Tank rounds can also destroy FUEL depots, without awarding player points.
The panel shows the score, fuel,
player, game variation, bridge number, session high score (HI), and reserve
planes. Audio offers PSG, OPL2 and PCM backends, guided by an Atari XL/XE
recording. Speed and throttle control the engine sound. PSG and PCM change
its noise bandwidth; OPL2 uses continuous broadband feedback noise with
throttle-controlled volume to avoid pitched FM hum and beating.
PSG uses eight oscillators and OPL2 nine channels to keep the engine playing
alongside shots, blasts and fuel tones. Missiles descend in
pitch, and explosions have a low body rather than metallic percussion.
Attract mode is silent. Colors and audio remain approximations. Compatibility and limitations
are described in [PORTING.md](PORTING.md).

GAME 3 DUO lets P1 and P2 fly together, with separate scores, fuel and lives.
Each pilot can hold up to ten lives, shown as two rows of five plane icons
beside their fuel gauge.
P1 uses the keyboard; the first gamepad controls P2 (WASD/left Ctrl also work).
Scrolling follows the average speed of the active planes. Each plane's throttle
also changes its vertical position: a faster pilot gains distance over time,
up to four plane heights (72 logical pixels). The rate of gaining distance is
proportional to the speed difference; equal speeds preserve the earned lead.
Shots do not hurt the other pilot, but a plane-to-plane collision kills both.
A fallen pilot with spare lives returns after the survivor passes the next
bridge, once a safe spawn position is available. Losing both planes restarts
the current stage with scores and remaining lives preserved. Each destroyed
plane costs one life; restarting does not charge another. A pilot with no lives
stays eliminated; the game ends when neither pilot has lives left.
Select GAME 3 with F2 and start with Space or Enter.

## Building and running

Requirements: CMake 3.21+, Ninja, Python 3, and cc65 with the `rp6502` target.
SDK installation instructions: https://picocomputer.github.io/sdk.html

PSG and OPL2 use the standard RIA sound interfaces. Only PCM requires the
firmware extension `XREG(0,1,2,base)`. Building this game does not update
firmware on the physical computer. See [PORTING.md](PORTING.md) for details.

Choose audio when loading the game on the computer:

```text
load riverraid.rp6502 /psg
load riverraid.rp6502 /opl2
load riverraid.rp6502 /pcm
```

No parameter selects OPL2. `/auto` selects PCM when supported, otherwise OPL2.
Explicit `/pcm` reports an error if the firmware lacks PCM.
Options are case insensitive; if several audio backends are supplied, the last one wins.
Add `/v` (for example, `load riverraid.rp6502 /opl2 /v`) to show the sound
icon and PSG/OPL/PCM label in the bottom-right corner below the scroller.
Without `/v`, a crossed-out note appears when F9 has muted sound, and F10
shows the selected backend for five seconds, aligned with the right screen
edge. The note moves to its left while the label is visible. F10 is ignored while muted.
`/help` displays usage without opening the cover.
In the emulator, put the game arguments after `--`:

```powershell
.\tools\rp6502-emu.exe .\build\cc65\release\riverraid.rp6502 -- /opl2
```

```powershell
cmake --preset cc65/Release
cmake --build --preset cc65/Release
.\tools\rp6502-emu.exe .\build\cc65\release\riverraid.rp6502
```

The artifact name `riverraid` retains the project's existing target name.
In VS Code, select the `cc65/Release` preset, the `riverraid` target, and the
`RP6502-EMU` launch configuration. F5 starts the emulator with debugger support.
Source symbols are available in both presets. Both use compact optimized C
code to fit the 64 KiB memory map, including GAME 3 DUO.

The port uses ca65. The llvm-mos presets from the old template are currently
unsupported by the port's code. The BASIC branch remains a template example.

## Controls

| Keyboard | Action |
| --- | --- |
| Arrow keys | Player 1: movement; Up accelerates, Down slows down |
| WASD, left Ctrl | Player 2: movement and firing; also control player 1 in single-player games |
| Space or Enter | Fire; start a game or restart after game over |
| F1 | Instructions (any key returns to the game) |
| F2 | SELECT: GAME 1 solo, GAME 2 alternating, GAME 3 DUO |
| F3 | Start a new game at BRIDGE: 1 → 5 → 20 → 50 → 1 |
| F4 | Color / black and white |
| F5 | Player 1: guided or straight missiles |
| F8 | Player 2: guided or straight missiles |
| F9 | Sound on / off (all sounds) |
| F10 | When unmuted, cycle PSG → OPL2 → PCM → PSG; show PSG/OPL/PCM for 5 seconds; skip PCM if unsupported |
| P | Pause |
| R | Start a new game at the bridge selected with F3 |
| Escape | Farewell screen, then exit to the console |

Two gamepads are supported: the D-pad or left stick controls movement, the
four face buttons fire, Start pauses, and Select starts a new game. Flying
over a fuel tank refuels the plane; shooting the tank awards points.
A balloon awards 60 points, a tank on the road or bank 250, a bridge 500,
and a bridge with a tank 750. Scrolling into the next section increases the level.
In GAME 2, players switch after losing a plane; GAME 3 is simultaneous.

In attract mode, the footer scrolls a light gray caption containing the game
title, author, copyright dates, Activision logo, and instructions for starting.
The complete static Activision logo also stays at the bottom-left corner
below the caption, before starting and throughout GAME 1, GAME 2 and GAME 3.
At startup, the program first displays `assets/cover.bmp` with a smooth fade in
(about one second). Any key starts the fade out; once it finishes and the key
is released, `assets/manual.bmp` fades in. The instructions wait for another
key with the blinking message "PRESS ANY KEY TO START THE GAME", then fade out
and open the existing mode-selection/demo screen. Each dismissal key must be
released before continuing. Both images retain their 320×180 aspect ratio
and are centered on a black background.
A small white "PRESS ANY KEY" message blinks below the image, visible for half
a second and hidden for half a second. The cover and its palettes are named
assets in the `.rp6502` file, loaded from `ROM:cover.bin` and `ROM:cover-fade.bin`;
the message bitmap is loaded from `ROM:cover-prompt.bin`.
Escape displays `assets/outro.bmp` with a fade in and the white message
"SEE YOU NEXT TIME!". After three seconds at full brightness, the image fades
out completely before the program exits. Held keys do not interrupt this screen.
The entire game screen fades in from black over about one second, including
the river, objects, HUD and logo. The demo starts as soon as the fade finishes.
In all three modes, the caption holds its opening text for three seconds
before scrolling. Selecting a mode or returning to attract mode repeats this hold.
After every 320 pixels of scrolling, the caption pauses for one second before
continuing. This cadence continues across the end of the caption.
GAME 3 uses the same scrolling caption as GAME 1 and GAME 2.
The text and glyphs can be edited in
`src/demo-footer.json`.
Every text cell uses a 6×7 glyph and two blank columns. The Activision logo
is padded to 64 logical pixels. The entire strip is 960 logical pixels wide
(six screens), displayed as 1920 VGA pixels with horizontal doubling.

## Emulator tests

```powershell
python tests/emulator_checks.py
```

The script tests the actual ROM at 8 MHz without opening a window. It checks
controls, pause, three gamepad types, exact fuel consumption and refueling,
scoring, extra lives, the maximum score, collisions, respawning, missile
guidance, player switching, restarting, the original LFSR, and RAM initialization.
It also checks for skipped VSYNCs during scrolling and firing, refueling,
respawning, and player switching.
Screenshots and scripts are written to `build/cc65/release/checks`.
Diagnostics are described in [tests/README.md](tests/README.md).

## Source code

- `src/main.c`: RIA/VGA configuration, raster rendering, input, and collisions.
- `src/audio.c`: command-line audio selection, PSG layers and OPL2 FM patches.
- `src/engine.asm`: timer-clocked noise with linear amplitude quantization for the PSG engine, independent of PCM.
- `src/audio.asm`: clocked noise, tones and streaming PCM ring producer.
- `src/graphics.h`: Atari 5200-inspired palette and readable bitmaps for balloons,
  tanks, mountains, banks, and panel lettering.
- `src/riverraid.asm`: fast scanline transfers and sprite/terrain collisions.
- `src/cover.asm`: cover, instructions and outro display, fades, and key handling.
- `src/riverraid.cfg`: RAM layout with the original game's zero page reserved.
- `src/xram.h`: XRAM layout and PIX structures checked at compile time.
- `tools/port_original.py`: automatic DASM-to-ca65 translation and selection
  of the original routines. Generates `original_core.asm` in the build directory.
- `tools/make_cover.py`: converts cover/manual/outro BMPs and prepares fade palettes.
- `tools/preview_audio.py`: offline PCM/PSG listening previews from captured parameters.
- `tools/preview_synth.py`: PSG/OPL register-trace WAV previews and spectral/Haar measurements.
- `tools/compare_synth.py`: preview signal checks and an optional RMS-matched XL/XE comparison.
- `tools/opl_preview.c`: optional native shim for the firmware's emu8950 preview model.
- `tools/analyze_audio.py`: WAV spectral measurements and spectrograms.
- `original/riverraid.asm`: unchanged reference source.
