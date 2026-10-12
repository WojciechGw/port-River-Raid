# River Raid for Picocomputer 6502

A River Raid port for Picocomputer 6502 that runs the original game logic natively.
The reference source is `original/riverraid.asm`: Thomas Jentzsch's annotated
disassembly of the **Atari 2600** version. Original game and graphics:
Activision, 1982; designer Carol Shaw.

The original 6502 routines handle the course, enemies, acceleration, fuel,
scoring, extra lives, respawning in the saved section, and two-player games.
The graphics combine original bitmaps with a palette and scenery inspired
by Atari XL and 5200 screenshots: smooth brown banks of varying width,
two mountain variants (blue slopes or black ridges), and dark blue water.
The added balloons have multicolored envelopes and baskets, while tanks
drive along the roads across bridges. The panel shows the score, fuel,
player, game variation, bridge number, session high score (HI), and reserve
planes. Sound maps the TIA registers to the PSG.
RGB555 colors and noise remain approximations. Compatibility and limitations
are described in [PORTING.md](PORTING.md).

## Building and running

Requirements: CMake 3.21+, Ninja, Python 3, and cc65 with the `rp6502` target.
SDK installation instructions: https://picocomputer.github.io/sdk.html

```powershell
cmake --preset cc65/Release
cmake --build --preset cc65/Release
.\tools\rp6502-emu.exe .\build\cc65\release\riverraid.rp6502
```

The artifact name `riverraid` retains the project's existing target name.
In VS Code, select the `cc65/Release` preset, the `riverraid` target, and the
`RP6502-EMU` launch configuration. F5 starts the emulator with debugger support.
Source symbols are also available in Release. `cc65/Debug` provides unoptimized
builds; use Release for performance measurements.

The port uses ca65. The llvm-mos presets from the old template are currently
unsupported by the port's code. The BASIC branch remains a template example.

## Controls

| Keyboard | Action |
| --- | --- |
| Arrow keys | Player 1: movement; Up accelerates, Down slows down |
| WASD, left Ctrl | Player 2: movement and firing; also control player 1 in single-player games |
| Space or Enter | Fire; start a game or restart after game over |
| F1 | Color / black and white |
| F2 | SELECT: one-player or two-player variation |
| F3 | Start a new game at BRIDGE: 1 → 5 → 20 → 50 → 1 |
| F5, F4 | Player 1 / 2: guided or straight missiles |
| P | Pause |
| R | Start a new game at the bridge selected with F3 |
| Escape | Exit to the console |

Two gamepads are supported: the D-pad or left stick controls movement, the
four face buttons fire, Start pauses, and Select starts a new game. Flying
over a fuel tank refuels the plane; shooting the tank awards points.
A balloon awards 60 points, a tank on the road 250, a bridge 500,
and a bridge with a tank 750. Scrolling into the next section increases the level.
In two-player games, players switch after losing a plane.

In attract mode, the footer scrolls a light gray caption containing the game
title, author, copyright dates, Activision logo, and instructions for starting.
At startup, the program first displays `assets/cover.bmp` with a smooth fade in
(about one second). Any key starts the fade out; once it finishes and the key
is released, the game screen appears. The cover retains its 320×180 aspect
ratio and is centered on a black background.
A small white "PRESS ANY KEY" message blinks below the image, visible for half
a second and hidden for half a second. The cover and its palettes are named
assets in the `.rp6502` file, loaded from `ROM:cover.bin` and `ROM:cover-fade.bin`;
the message bitmap is loaded from `ROM:cover-prompt.bin`.
After displaying the game screen, the program waits 3 seconds, then starts
the scrolling caption and the demo with the scrolling river simultaneously.
The text and glyphs can be edited in `src/demo-footer.json`.

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

- `src/main.c`: RIA/VGA/PSG configuration, raster rendering, input, and collisions.
- `src/graphics.h`: Atari 5200-inspired palette and readable bitmaps for balloons,
  tanks, mountains, banks, and panel lettering.
- `src/riverraid.asm`: fast scanline transfers and sprite/terrain collisions.
- `src/cover.asm`: cover display, fades, and waiting for a key.
- `src/riverraid.cfg`: RAM layout with the original game's zero page reserved.
- `src/xram.h`: XRAM layout and PIX structures checked at compile time.
- `tools/port_original.py`: automatic DASM-to-ca65 translation and selection
  of the original routines. Generates `original_core.asm` in the build directory.
- `tools/make_cover.py`: converts `assets/cover.bmp` and prepares fade palettes.
- `original/riverraid.asm`: unchanged reference source.

<!-- rp6502
preset: cc65/Release
publish: riverraid.zip
-->
