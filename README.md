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
planes. Audio uses OPL2 by default; the optional PCM build offers both backends, guided by an Atari XL/XE
recording. Speed and throttle control the engine sound. PCM changes
its noise bandwidth; OPL2 uses continuous broadband feedback noise with
throttle-controlled volume to avoid pitched FM hum and beating.
OPL2 uses nine channels to keep the engine playing
alongside shots, blasts and fuel tones. Missiles descend in
pitch, and explosions have a low body rather than metallic percussion.
Attract mode slides `assets/splash_plane.bmp` in from the right at its native 128x64
size, using two 64x64 sprites with transparent black. The image moves at
2 pixels per frame to X=200, Y=4, then replaces it with `splash_areyouready.bmp`.
Starting play restores the plane and slides it off the left edge at 8 pixels per frame (about
0.68 seconds from rest), accompanied by the engine effect while demo music
continues. F9 OFF and pause silence the engine; SFX keeps it enabled.
When GAME 1 runs out of planes, or both players run out in GAME 2/3, the plane
flies in and changes to `splash_gameover.bmp`. It waits for the game-over tune
to finish, then leaves with the GAME OVER text. Only afterwards does a new
plane enter and change to ARE YOU READY. With music muted or interrupted,
the sequence uses the tune's nominal 6.7-second duration; pause/F1 freezes it.
All three images are packaged in the ROM and loaded directly into the same
XRAM buffers without hiding the sprites during image replacement.
Colors and audio remain approximations. Compatibility and limitations
are described in [PORTING.md](PORTING.md).

The music is based on the OPL2 melody and PCM drums from the firmware's
`tests/gen/riverraid_rom_gen.py --bpm 140`. Its eight-bar loop lasts 13.696 seconds
at the generator's actual tempo of 140.186916 BPM. It plays on the cover,
instructions/F1 and farewell screen. Mode selection, demo and gameplay use a
quieter variation of the same theme, with syncopated bass, an alternating lead
register and answering arpeggios. It keeps the same tempo and loop length.
`tools/make_music.py` builds this arrangement and its percussion from the source
score. Engine, shots, explosions and fuel warnings continue alongside it.
On exit, both OPL2 and PCM fade out with the farewell picture. F9 music mute also
applies to music. In the PCM build, music uses OPL2 plus PCM when the firmware
supports PCM, regardless of the gameplay option. The default OPL2 build plays
both melody and synthesized percussion through OPL2. The same arrangement is
used when PCM firmware support is unavailable, including victory and game-over jingles.
The reduced arrangement reserves voices for effects; effects take priority
over the engine when the fallback's shared voices are busy. Notes and instruments are in
`src/intro-score.json`; `assets/intro-drums.pcm` holds the generated percussion.
To reimport: `python tools/import_intro.py path/to/riverraid_rom_gen.py --bpm 140`.

Losing the last plane plays the OPL2 + PCM arrangement from
`riverraid_gameover_rom_gen.py --bpm 200`, including its final slowdown and decay
(6.704 seconds). GAME 1 triggers it when the player runs out of planes;
GAME 2 and GAME 3 wait until both players run out. The jingle respects mute and
returns to the flight arrangement after the jingle.
To reimport: `python tools/import_gameover.py path/to/riverraid_gameover_rom_gen.py --bpm 200`.

Destroying a bridge while the HUD shows BRIDGE 5, 20 or 50 plays the OPL2 + PCM victory fanfare from
`riverraid_victory_rom_gen.py --bpm 96` (11.648 seconds). It also awards one extra
life to the current player in GAME 1/2, or to each player in GAME 3, including
an eliminated player. The existing life limits apply. Muting sound does not
disable the reward, and the regular score bonus remains independent.
To reimport: `python tools/import_gameover.py path/to/riverraid_victory_rom_gen.py --name victory --bpm 96`.
Normal builds use the checked-in assets and do not require the firmware checkout.

GAME 3 DUO lets P1 and P2 fly together, with separate scores, fuel and lives.
Each pilot can hold up to ten lives, shown as two rows of five plane icons
beside their fuel gauge.
Selecting GAME 3 already shows three planes and a full fuel gauge for each
pilot, before starting the flight.
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

OPL2 uses the standard RIA sound interface. Only PCM requires the
firmware extension `XREG(0,1,2,base)`. Building this game does not update
firmware on the physical computer. See [PORTING.md](PORTING.md) for details.

The default build uses OPL2 for all music, percussion and effects.
In the optional PCM build, choose gameplay audio when loading the game:

```text
load riverraid.rp6502 /opl2
load riverraid.rp6502 /pcm
```

No parameter selects OPL2. `/auto` selects PCM when supported, otherwise OPL2.
Explicit `/pcm` reports an error if the firmware lacks PCM.
Options are case insensitive; if several audio backends are supplied, the last one wins.
Add `/v` (for example, `load riverraid.rp6502 /opl2 /v`) to show the sound
icon in the bottom-right corner below the scroller. The full PCM build also
shows the OPL/PCM label; the OPL2-only build never displays a backend label.
F9 cycles through all sound, effects only (`SFX`),
and silence (`OFF`), then restores all sound. These status labels remain
visible without `/v`. In the full build, restoring all sound with F9 or
switching with F10 shows the backend for one second, aligned with the right
screen edge. The note moves to its left while a label is visible.
F10 is ignored only in the fully muted state.
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
The default `cc65/Release` and `cc65/Debug` presets set `RIVER_PCM=OFF`.
Their ROM omits PCM samples, hybrid scores and PCM playback/mixing code.
F10 has no action and is omitted from help and the `assets/manualOPL.bmp`
keyboard screen. F9 offers the same three sound states, without showing an OPL label.
`/auto` and `/opl2` select OPL2;
`/pcm` is rejected.

To build the full OPL2 + PCM version in a separate directory:

```powershell
cmake --preset cc65/Release-PCM
cmake --build --preset cc65/Release-PCM
.\tools\rp6502-emu.exe .\build\cc65\release-pcm\riverraid.rp6502
```

The PCM preset sets `RIVER_PCM=ON` and restores F10 and `/pcm`.
The existing `cc65/Release-OPL2` preset remains available in `build/cc65/release-opl2`.
Any cc65 configuration can use `-DRIVER_PCM=OFF` or `-DRIVER_PCM=ON`;
PCM is disabled by default. Re-run `cmake --preset cc65/Release` when updating
an existing build directory to replace its cached PCM setting.

In VS Code, select the `cc65/Release` preset, the `riverraid` target, and the
`RP6502-EMU` launch configuration. F5 starts the emulator with debugger support.
Source symbols are available in all cc65 presets. They use compact optimized C
code to fit the 64 KiB memory map, including GAME 3 DUO.

The port uses ca65. The llvm-mos presets from the old template are currently
unsupported by the port's code. The BASIC branch remains a template example.

## Controls

| Keyboard | Action |
| --- | --- |
| Arrow keys | Player 1: movement; Up accelerates, Down slows down |
| WASD, left Ctrl | Player 2: movement and firing; also control player 1 in single-player games |
| Space or Enter | Fire; start a game or restart after game over |
| F1 | Instructions (any key returns with a one-second fade-in; the game stays frozen until it finishes) |
| F2 | SELECT: GAME 1 solo, GAME 2 alternating, GAME 3 DUO |
| F3 | Start a new game at BRIDGE: 1 → 5 → 20 → 50 → 1 |
| F4 | Color / black and white |
| F5 | Player 1: guided or straight missiles |
| F8 | Player 2: guided or straight missiles |
| F9 | All sound → effects only → mute → all sound |
| F10 | Unless fully muted, switch OPL2 ↔ PCM; show OPL/PCM for 1 second; stay on OPL2 if PCM is unsupported |
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
- `src/audio.c`: command-line audio selection and OPL2 FM patches.
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
- `tools/preview_audio.py`: offline PCM listening previews from captured parameters.
- `tools/preview_synth.py`: OPL register-trace WAV previews and spectral/Haar measurements.
- `tools/compare_synth.py`: preview signal checks and an optional RMS-matched XL/XE comparison.
- `tools/opl_preview.c`: optional native shim for the firmware's emu8950 preview model.
- `tools/analyze_audio.py`: WAV spectral measurements and spectrograms.
- `original/riverraid.asm`: unchanged reference source.
