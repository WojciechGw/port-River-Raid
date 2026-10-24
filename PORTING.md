# Port status

The port runs the original game routines from `original/riverraid.asm` natively.
The reference source is the **Atari 2600 NTSC** version, using the TIA and RIOT
chips. Game designer: Carol Shaw, Activision (1982); disassembly annotations:
Thomas Jentzsch. The original source remains unchanged.

## Original game logic

`tools/port_original.py` translates DASM to ca65, preserves the complete
4 KB image as reference data, and extracts separate executable routines:

- the `PFPat` generator, bank and island changes, and placement of houses,
  fuel tanks, ships, helicopters, planes, and bridges;
- the original LFSR, saving the section seed, and restoring the course after death;
- fractional scrolling, horizontal and vertical acceleration, and movement
  and animation timing;
- consumption of 32 fuel units per frame and the original refueling behavior;
- scoring of 100/60/30/500/80 points, an extra life every 10,000 points, a limit
  of nine lives, and behavior when the score exceeds 999,990;
- section transitions, explosions, respawning, one-player and two-player modes,
  and difficulty switches;
- sound routines, black-and-white mode, and the color screensaver.

A bridge starts the transition to the next section. The generator changes
the level number during scrolling, as in the original. Enemies are initially
stationary; ships and helicopters begin moving at level two, and planes
appear from level three. Death restores the saved section; the port adds
neither invulnerability nor an artificial safe corridor.

In GAME 2, the active player's P1/P2 label, score and reserve planes share
the aircraft color, including after a turn change or return from F1.
BRIDGE, its number and the high-score display retain their existing colors.

F3 selects the starting bridge in the cycle 1 → 5 → 20 → 50 → 1 and starts
a new game. The selection applies to both players and remains active when
restarting with R. Full initialization applies the selected level, while
respawning and player switching preserve each player's current section.
In the executable copy of the routines, the level limit was increased from
48 to 50; after section 50, the generator returns to 49. The original ROM
image remains unchanged. Missile guidance is toggled independently with
F5 for player 1 and F8 for player 2. F4 toggles color/black and white.
Missiles launch four logical columns from the plane's left edge, one column
left of the Atari offset. Rendering and collisions use this same position.
Each missile uses color 1 of its own plane's palette, including both DUO
pilots and black-and-white mode.
F9 cycles all sound → effects only → full mute → all sound,
without pausing the game or changing the audio backend. `audio_muted` is
a mask: bit 0 suppresses music (including percussion, victory/game-over
jingles, F1 and outro); bit 1 suppresses procedural game effects.
It acts once per press and retains its setting across restart, mode changes
and the F1 manual. Sound starts enabled when the program is launched.
F10 switches OPL2 ↔ PCM, remaining on OPL2 when the firmware rejects
its interface. It stops the previous backend before initializing the next,
ignores presses only during full mute, and retains the selection through
F1 and restart. In the full PCM build, a successful F10 press or returning to all sound with F9 shows OPL or PCM for 60 display
frames (one second), including paused frames. Each new such press restarts the
timer; holding the key does not. Opening F1 dismisses the transient label.
With `/v`, the note and backend remain visible in the full build. The default
OPL2-only build never displays the backend name, including after F9 and with
`/v`. Both builds show SFX or OFF for the two restricted sound states.
The note stays at (312,232) when no label is visible. The icons are defined in
`src/graphics.h` and drawn at (312,232) as a 1bpp bitmap;
the backend starts at (296,232), with three characters aligned to the right
screen edge. While it is visible, the note moves left to (280,232).
The text uses the VGA's built-in 8×8 font in
[character mode](https://picocomputer.github.io/vga.html). Both are white on
the black margin below the scroller, update on F9/F10, expiry or initialization, and share
the white splash palette for startup fade. Without `/v`, the note is hidden
only in the all-sound state; it is crossed when the music mute bit is set.
F1 opens the instruction screen.

Balloons (ID 11) extend the executable copy of the routines: from level two,
they replace some randomly generated enemies, moving and bouncing off the
banks like helicopters. Shooting a balloon awards 60 points; contact with
the plane causes an explosion.
A tank is an additional object in every bridge block, starting with the
first bridge. It starts fully outside the left or right playfield edge, drives
along the entire road, and turns around only after clearing the opposite edge. Its
state moves with the terrain block, pause stops its movement, and restarting
or respawning restores its state. A tank on the land portion of the road
awards 250 points; hitting a bridge with a tank on its span destroys both
objects and awards 750 points in total instead of 500.
A tank still on either approach survives bridge destruction, remains visible
and shootable, and stops with its body before the broken deck (X=47 from the
left or X=104 from the right). Destroying the bridge alone awards 500 points.
Once stopped, it fires toward the river using the bank tank's firing cadence,
range selection, shell descent and splash collisions, even before bridge seven.
Its independent projectile can coexist with both bank tanks' projectiles.
Destroying the survivor clears its shot; scrolling and F1 preserve it, while
pause freezes it and restart clears it.
The companion persists through the bridge's explosion and empty-object states
until its terrain block scrolls away or the section restarts. Road tank
synchronization and motion use compact 6502 helpers to keep DUO within a frame.
The additional 250 points use the original decimal digit pointers, reserve
awards every 10,000 points, the limit of nine lives, and score overflow behavior.
From bridge seven, up to two additional tanks approach from the sides,
stop two logical pixels before the actual ground edge, and shoot onto the
river. Their placement checks every opaque body row so sloping banks do
not leave the tracks in the water. Tanks and shots scroll with the terrain;
pause freezes both, and a restart or respawn clears them.
Each shot chooses a random range from the actual water boundaries, excluding
the decorative brown rims. The whole largest impact circle must fit across
all sixteen of its rows, including bends. An island confines fire to the
tank's own channel; tanks wait when the channel cannot contain the circle.
Shot ranges use a separate random state, preserving the native course generator.
White rounds leave at barrel height and descend gradually to the bottom track
line at their chosen range. Rendering and FUEL collisions share the current
flight height; splash rendering, collisions and water bounds use the final
track height. The flight drop is calculated once per tick and cached.
Rounds in flight do not harm the plane; only opaque splash pixels damage it,
matching the distinction in the 5200 manual. Shooting a bank tank awards
250 points through the same native scoring routine as a road tank.
Water explosions use filled white circles with canvas diameters of 4, 8,
and 16 pixels. Their six phases are small circle, clear, medium circle,
clear, large circle, clear. Each phase lasts three native frames. All filled
pixels can collide with the jet; clear phases have no sprite or collision.
Tank rounds can destroy FUEL depots: the depot enters the native explosion
animation and plays its explosion sound, without awarding player points or
consuming the player's own missile. Transparent depot pixels do not stop a round.
Both road and bank tanks cycle through three track frames every fourth native
frame, at half the helicopter rotor cadence. Pause freezes the animation.
The turret and body remain fixed; the third phase adds offset middle-row links.
Tank collisions follow the opaque pixels of the current track frame.
The readable tank drawing is 9 logical pixels wide and 9 rows high; each
logical column occupies two canvas pixels. Its VGA sprite is padded to 12x16
and placed eight rows below the native block origin. Mirrored sprites compensate
for the three blank columns so both directions share the same collision bounds.
Rounds leave the barrel's row, and water explosions remain centered on that
same trajectory. The entire largest circle is included in the water fit check.
Readable helicopter drawings also follow the supplied references: salmon
rotors, green fuselage, a dark blue stripe for type 1 and an olive stripe for
type 2. Native IDs 5 and 6 remain rotor frames, rather than aircraft types.
Type 2 starts at level 5 and accounts for every fourth new helicopter;
the other three use type 1. Each block retains its assigned type across
rotor animation and scrolling. This counter does not consume native random
state. Type 2 fires a pale four-column horizontal shot, replacing it in the
same frame when the previous shot hits the riverbank. Each helicopter has
at most one active shot. Shots move two logical columns per frame,
scroll with their source block and collide with opaque
jet pixels. Pause freezes them, and restart/respawn clears them.
Shots disappear as soon as any opaque column reaches land, including the
brown river rim or a central island. A dash is not launched into land.
The player's death immediately clears enemy rounds and water impact sprites;
otherwise the native death state would freeze their last animation frame.
Existing bank tanks keep scrolling with the terrain after the last life,
until they leave the screen. In attract mode they do not approach or fire,
and no new bank tanks spawn.
Helicopter shots reuse the companion sprite slots of blocks without bridge
tanks, preserving the existing
250-byte VSYNC sprite upload (including the road survivor's shot and DUO jets).
The port adds these encounters between bridges using the native scenery
seed without changing the original random-number sequence. Their exact
spawn cadence and explosion artwork are approximations of the 5200 version.
Balloon and bridge-with-tank scores are described in the
[Activision manual for the 5200](https://atariage.com/manual_html_page.php?SoftwareID=2101).

The remaining routine changes concern hardware addresses, preserving the cc65
stack, initializing the reserved zero page, and skipping the RIOT timer wait.
The ca65 long branches preserve their conditions and processor flags. The
generator checks the image size and the locations of important source sections;
changes to the disassembly layout require reviewing the ranges selected for
the port.

## Picocomputer layer

RAM `$0000–$007F` is used by cc65, `$0080–$00FF` retains the game variables,
and `$0200–$02FF` contains input readings and sound output registers.
The program starts at `$0300`. Original ROM tables remain byte-for-byte at
`$CB00–$CFFF`, preserving their Atari offsets. The unused copy of Atari code
at `$C000–$CAFF` holds shared music routines. `riverraid.rom` still contains
the full reference; `pack_music_rom.py` combines its unchanged table tail
with the music code for loading, guarded by the first-table linker assertion.
The executable routines have relocated references and a separate initialization
table. The Atari raster code is not executed. There is no Atari CPU emulation.

VGA uses a 320×240 canvas, with the playfield on scanlines 21–180 and logical
coordinates of 160×160. The river uses the original PF0/PF1/PF2 bit order,
mirroring, and bridge openings. A 40×192 ring buffer stores indices of 8×1-pixel
tiles: one tile corresponds to one Atari playfield bit. Only new scanlines
are written, transferring 40 rather than 160 bytes per row.
Tiles at the land/water boundary add a brown rim on the land side, including
islands and all road shades at the bridge. On vertical sections, the rim is
3–5 logical pixels wide. The slope, measured from pairs of samples spaced
two and four rows apart, gradually narrows it to one pixel on steep diagonals;
it accounts for the doubled X scale on the canvas. The `bank_slope_width`
table in `src/graphics.h` defines this relationship without floating-point
calculations. Single-scanline joins close the contour at steps.
When a new block is added, the four preceding rows are refreshed because
their slopes depend on the new neighbor. Samples shared by pairs of rows
are cached within a redraw batch; the cache is cleared after the game logic
changes the data. The width can exceed one tile. The 2600 generator still
defines the river's course, but PF steps are interpolated within the land
to individual logical pixels.
The water contour also has small bends: `bank_wave` reproduces samples of
the long bank in `original/Atari XL/image0.png` (logical rows 41–104).
It shifts the boundary 0–3 pixels into the land; the profile is tied to the
terrain row, so it scrolls with the river. The fast reset uses the same
boundary and prepared tiles for each phase, while mountains retain an
additional three-pixel margin from the water. Large bends are still defined
by the generator data.
`river_left` and `river_right` store the exact boundaries for rendering and
collisions; the road retains the original width of the bridge opening.
Tiles mix water, rim, and ground colors, while the entire buffer still
requires 40 bytes per row.
The player's plane can fly over the brown rim. For each row, the renderer
stores the ground boundaries beyond the rim, separately for both banks and
the island. `mask_player_land` checks only these intervals and the original
terrain masks; a collision occurs only when an opaque pixel of the plane
reaches the ground. Resetting and scrolling update the same boundaries.
Sprites reproduce the A/B streams, row colors, TIA sizes, mirroring, bridge
explosion copies, and plane wrapping at the edges. Bridges use the 5200 beam
profile in `src/graphics.h`: a 15-row brown deck with a gold center stripe,
followed by two rows of black supports. The deck is 48 logical pixels wide
and overlaps each bank by eight pixels around the original 32-pixel opening.
Its opaque pixels also define missile and plane collisions. The approach
road has 20 rows, different gray shades above and below its pale center line,
and shares the bridge's stripe position. Its additional tiles use XRAM below
the small mountain; the static Activision bitmap now occupies $5A00.
Startup sprite conversion stays optimized in Debug to fit the fixed RAM map.
The player's plane occupies
the front VGA layer (plane 2), above game objects on plane 1.
The panel displays digit, fuel, and Activision lettering bitmaps rather than
the VGA font. The score and HI use bold 6×6 digits reconstructed from Atari
XL/5200 references. P1/P2 and HI use a narrow 3×5 typeface, GAME uses wider
letters in 8×6 cells, and BRIDGE retains a separate six-row bitmap with the
original spacing. The variation number below GAME and the bridge number use
the same typeface as the score.
Field positions follow the supplied layout: GAME on the left, the fuel gauge
beside it, and BRIDGE above the reserve icons. The fuel gauge frame with E,
F, and 1/2 is a readable 39×16 bitmap in `src/graphics.h`; the yellow indicator
depends on the current fuel level. In GAME 1 and GAME 2 the gauge always
starts at logical X=45, both before starting and during play.
Five mountain variants replace the house and tree from the 2600 version.
Two were reconstructed from `original/Atari XL/image0.png`: a tall mountain
range with blue slopes and lower brown peaks with black ridges. The third is
a single medium-sized mountain with a black ridge. Two additional user-supplied
references define stepped peaks with blue cuts and a wide overlapping range
with blue and black ridges. Their images occupy $5C00 and $5E00 in XRAM.
The variant depends on
the object data and remains the same when it moves between terrain blocks.
Mountain placement considers the shared strip of land across the full bitmap
height and neighboring interpolation rows, including those outside the
visible area. The margin accounts for three pixels of water smoothing, up
to five pixels of rim, and two logical pixels of clear land. Islands that
are too narrow cause the mountains to shift to the nearest sufficiently
wide strip of land. The position is cached until the terrain block changes;
rendering and collisions use the same offset and the exact new silhouette.
The panel reproduces the 5200 layout: P1/P2 and the score on the left, HI and
the high score on the right, GAME, fuel, and BRIDGE below, and reserve planes
under the bridge number. The session high score is shared by both players
and survives R/game restarts; the number of reserve icons matches the original
game counter and can reach nine. Scores start at zero; startup and SELECT no
longer copy the game number into the score's units digit. GAME displays the
selection separately, so the initial HI stays zero until points are earned.
Counter digits and icons are prepared at startup; sprites update only the
image or number, without redrawing bitmaps during a game frame.
Stream A occupies even rows of a block and B occupies odd rows; this order
preserves the readable FUEL letters cut out of the fuel tank bitmap.
The bridge is 32 logical pixels wide and occupies X 64–95, matching the
river's narrow opening. The wide sprite's position was corrected by one
pixel relative to the value 63 passed to `CalcPosX` by the original game;
rendering and collisions use the same origin.
The panel occupies scanlines 182–218, separated from the game by a single
black scanline. The score starts on panel row 5, GAME/BRIDGE on row 18,
the fuel scale on row 17, and reserves on row 25. The `HUD_*` definitions
at the start of `src/main.c` specify the field coordinates; changing the
typeface does not require changes to the game logic.
The static Activision logo stays at canvas (0,232), below the scrolling
caption, both before starting and during all three game modes. Its complete
62-column source in `src/graphics.h` is padded to 64×8 logical pixels,
stored in 256 bytes at $5A00 and displayed 128 pixels wide. The sprite list
extends through scanline 239 so the bottom rows remain visible. The bitmap
preserves the lettering, five rainbow colors and diagonal connection to A.
A separate sprite and palette preserve the logo's colors
rounded to RGB555; the B&W switch and screensaver use the original color roles.

Before initializing the game, `src/cover.asm` displays the cover image from
`assets/cover.bmp`. The 320×180 bitmap preserves its indices and all palette
colors, rounded to RGB555. It occupies XRAM $1000–$F0FF; its configuration
is at $0280, palette at $0400, and next-palette buffer at $0600. The image
is centered at Y=30 on the 320×240 canvas. `tools/make_cover.py` prepares
64 brightness levels in both directions.
The cover, palettes, and message bitmap are packaged as named `.rp6502`
assets: `cover.bin`, `cover-fade.bin`, and `cover-prompt.bin`. The program
opens them on the `ROM:` drive and reads them using READ_XRAM; the loader
does not load the cover graphics automatically.
Palettes are read into the buffer and copied to the displayed palette after
VSYNC, before the first scanline of the cover. Fade in and fade out each
take about one second. Below the image, at X=120, Y=222, is a centered
"PRESS ANY KEY" bitmap: 5×7 letters in an 80×8 area, white on black.
A separate palette at $0850 and bitmap at $0800 leave the cover colors
unchanged. The configuration at $02A0 moves the message off-screen every
30 VSYNCs, giving half a second of visibility and half a second of darkness.
The message appears after fade in and disappears when a key is pressed,
before fade out.
Main music imports the firmware `riverraid_rom_gen.py --bpm 140` arrangement:
seven OPL2 channels and signed 8-bit mono PCM drums at 16 kHz. The sequencer
advances every 1712 consumed PCM samples, matching the generator's rounded
140.186916 BPM tempo. The eight bars occupy 219136 samples (13.696 seconds).
ROM reads refill a 1024-byte ring at $0A00, with its header at $09F8; the
separate drum descriptor leaves palette streaming independent during fades.
Without PCM support, a display-clock fallback plays both notes and synthesized
drums on OPL2. The capability probe precedes
score selection; OPL2 is the only fallback synth.
The screen player borrows 1024 bytes of derived graphics tables beginning at
`sprites`; these are rebuilt before gameplay and when returning from F1.
The score is at $F900, above the saved F1 video at $F100..$F8FF. The initial
manual continues the cover stream. On the mode-selection/demo screen, the
installed runtime player decodes a quieter three-part flight variation using
the jingle's $CA00 PCM header/$CA08 ring and $C900 OPL registers. It continues
during gameplay. F1 and exit stop it before enabling the screen player. Muting suppresses
both players. During the final farewell fade, OPL carrier attenuation rises
to 63 while each PCM page is scaled by the picture level before publication.

Flight music reserves melodic voices 0..2. With PCM, percussion uses a separate
16 kHz ring, leaving OPL voices 3/4/7/8 for engine/blast/shot/fuel. Without PCM,
three decaying FM voices supply percussion. Effects share 6..8, with blasts
taking precedence over the engine. PCM effects
retain their 8 kHz procedural ring; `music_mix_pcm` consumes each sample twice
at half gain into the 16 kHz percussion page before publishing it. It advances
the effects read pointer itself because firmware consumes only the music ring.
After fade in, the program waits for any HID key, including function keys
and modifiers; LED status bits do not dismiss the cover. The dismissal key
is consumed through its release so it cannot also trigger game controls.
After releasing the cover key, the same helper opens `manual.bin` and
`manual-fade.bin`, generated from `assets/manual.bmp`. The instructions fade
in, wait for a separate key press, fade out, and wait for key release before
initializing the existing mode-selection/demo screen. `manual-prompt.bin`
contains "PRESS ANY KEY TO START THE GAME", centered at X=64, Y=222 in a
192x8 bitmap at $0900, with the same blinking timing and white/black palette.
XRAM $00B4 identifies the current scene: 0 cover, 1 outro, 2 manual.
F1 also opens this manual during play or the demo. The simulation and audio
stop until the closing key is released; an existing pause remains active.
Holding F1 does not dismiss its own screen. Before loading the image, the
host saves terrain base colors at $F100 and live video data ($0100-$07FF)
at $F200-$F8FF, above the last manual pixel. On return it rebuilds static
graphics and terrain from the preserved CPU collision edges, restores
palettes/descriptors and redraws the HUD without advancing game logic.
The restored screen then fades in over 64 VSYNCs, with every palette scaled
from black to its saved colors. Gameplay remains frozen until the fade ends,
and an existing pause is preserved.
The VSYNC baseline is reset so time spent in help is not counted as dropped
game frames. Audio is reinitialized using the selected backend.
The cover helpers and tank extension code/state share free CPU memory from
$D000 through $FDFF, after the original ROM and before CPB's reserved page,
with scene tables in RODATA and small writable state in DATA below the
reference ROM. The linker reserves the entire $FE00-$FEFF page for
PICO-SRAM-BANKED (CPB):
the module rewrites its reset counter at $FED5 whenever the loader resets
the CPU between writing and verifying RAM. Loading code there causes
`?Verify failed at $FED5`; $FED6/$FED7 also hold periodically updated
temperature values. Fixed-width sprite rows omit unused string terminators
to fit below $FE00. The sound status helper and its configuration table
live below $C000 so the high segment fits below these registers.
After the manual fades out, the program restores the footer
strip from a ROM asset, and game initialization restores the remaining assets
in the reused XRAM.
Escape stops audio before reusing the cover's XRAM and palette for the farewell
screen, loading `outro.bin` and `outro-fade.bin` from `assets/outro.bmp`.
The same fade helper reads `outro-prompt.bin` into $0900 and centers its
112x8 bitmap at X=104, Y=222. "SEE YOU NEXT TIME!" remains visible for 180 VSYNCs
after fade in, without blinking or responding to keys. Fade out ends on black;
one final VSYNC displays it before returning to the console, even with Escape held.

In attract mode, the footer is replaced by a caption scrolling left by one
canvas pixel per frame. The text and readable glyphs are in `src/demo-footer.json`.
The overlay uses `assets/splash_plane.bmp`, `splash_areyouready.bmp` and
`splash_gameover.bmp` (128x64, up to 256 palette entries). CMake runs
`tools/make_demo_splash.py` for each and packages `splash-plane.bin`,
`splash-areyouready.bin` and `splash-gameover.bin`: 9216 bytes each, 27 KiB total.
Each image has two unscaled 64x64 8bpp
sprites at XRAM $6500 and $D600, resting at (200,4) and (264,4). The front
sprite plane starts at scanline zero, displaying the entire image. Black
is transparent. Entry starts immediately at X=320 and moves left by 2 pixels
per live demo frame, reaching X=200 after 60 frames. A start request switches
to 8 pixels per frame until X=-128; only then does actual play begin.
The plane image is used for both slides; the ready image replaces it at rest.
The final-life event starts a separate plane entry before the music mute test,
for the sole player in GAME 1 or after both players run out in GAME 2/3.
At X=200 it changes to GAME OVER and holds. The score terminator signals the
actual end of the jingle; an active PCM score is never replaced by a wall-clock
timeout. Muted or interrupted audio falls back to 403 unpaused frames from
the final-life event (107264 samples at 16 kHz). After the hold, GAME OVER
slides left intact, then a new plane enters and changes to ARE YOU READY.
The native world may resume demo earlier, but cannot reset this sequence.
Pause/F1 preserves the phase and silent fallback timer; F2/restart cancels it.
At VSYNC, a changed image is read directly from ROM into both existing XRAM
tiles and their color/mono palettes; descriptors stay visible throughout.
The loader opens its own ROM file and saves/restores boot_fd, retaining the
PCM stream's separate file position. F1 forcibly reloads the selected image.
During departure, audio_update enables only the existing engine effect,
using OPL2 or PCM according to the selected backend. Other demo effects stay
muted. The music mixer admits this engine during demo; F9 OFF, pause, F1,
completion and F2 cancellation stop it without leaving an OPL voice keyed on.
The palette remains at full brightness during both slides. The backdrop
and music continue. Repeated start presses do not reset the slide;
F2 cancels the request and starts a new demo. Pause and F1 preserve the position
and pending request. The native fly-in launches without synthesizing FIRE;
a start/fire button is consumed until release. The former RGB5 fade lookup
is no longer needed; the XRAM image allocation is unchanged.
The front-plane list at $7500 contains both player jets
followed by these two sprites; the legacy jet descriptors remain available.
The active 256-color palette at $7580 follows F4 and screen fades, with color
and grayscale originals at $7780 and $7980. F1 reloads the asset before restoring video.
Each palette occupies 512 bytes. The 1088-byte fade staging buffer follows
at $7B80..$7FBF, leaving 64 bytes before object images at $8000. The source
buffer uses $D000..$D43F, before the right splash tile at $D600.
The game-over installation uses temporary XRAM $E800, clear of both images.
After the initial manual or F1 closes, `src/fade.c` and `src/fade.asm` fade in the entire
game screen over 64 VSYNCs (about one second). All 544 palette entries are
saved in XRAM $D000 and scaled into staging at $7B80. Each RGB555 channel
uses 32 brightness steps, preserving the transparency bit. Palettes start
black before video planes are enabled; each update is copied at VSYNC in
before the playfield is scanned at 8 MHz. The scene remains
stationary during the fade. XRAM $00B2 reports brightness (0..32), followed
by the last publication's VSYNC byte. The scratch buffers do not overlap
the PCM ring or OPL2 registers. Once the fade finishes, the demo starts
immediately. In all three modes, the caption holds at X=0 for 180 unpaused
frames (three seconds) before scrolling. Every 320 pixels of actual movement
adds a 60-frame (one-second) hold, including across a bitmap wrap. Pause
freezes both countdowns. Entering a mode or returning to attract resets the
cadence; F1 preserves its remaining time. The demo runs the
original terrain generator and enemy movement; it skips plane controls,
firing, fuel consumption, and player collisions.
All text glyphs occupy 6×7 logical pixels, including lowercase descenders,
followed by two transparent columns in each eight-pixel cell. The same logo
bitmap from `src/graphics.h` is inserted at `{Activision}`, with transparent
columns extending its 62-pixel width to 64. The complete strip spans exactly
960 logical pixels (six 160-pixel screens), doubled to 1920 VGA pixels.
Unused trailing cells remain transparent; overlong text fails the build. The generator
`tools/make_demo_footer.py` prepares the entire strip when building the ROM;
the program loads it into XRAM $3800 after dismissing the cover. VGA scrolls
the bitmap with horizontal wrapping, without the CPU drawing letters each
frame. A separate palette preserves the light gray text even during the
screensaver. Pause stops the caption; starting a game hides the caption,
and game over restores scrolling. The static logo remains below it in all
modes. GAME 3 uses the same
strip at XRAM $3800 as GAME 1/2, without a prefix. All modes share the same
visibility, pause and one-pixel-per-frame scrolling routine.

The program computes pixel collisions before calling the original game
logic, setting its collision flags. Assembly routines handle scanline
transfers and sprite/terrain checks. Input supports USB HID and two gamepads.
The game clock comes from `RIA.vsync` at 60 Hz. The skipped-frame counter
covers all operations after the initial video configuration, including
restarting, respawning, and player switching.

The scroll position, object list, and caption offset are prepared in RAM
during the preceding frame. Immediately after VSYNC, the `present_frame`
assembly routine publishes them together to XRAM in under 0.5 ms at 8 MHz,
before scanout reaches the first river scanline. Terrain and collision
calculations do not delay this publication. The absence of skipped VSYNCs
alone does not rule out tearing if the background position changes while
a frame is being displayed.

Restarting restores the initial straight corridor with a fast assembly
routine. In Release measurements at 8 MHz, terrain restoration time fell
from about 391 ms to 5–6 ms. The panel transfers only the columns occupied
by digits, fuel, and the logo; glyph rendering is handled in assembly, and
Audio phase increments use constant tables instead of division in each
frame. Player switching updates only the plane palette; a full palette
update is still needed when changing the color mode or screensaver state.
The bank renderer uses fixed working buffers, reducing cc65 stack access
cost during respawning.
TIA color conversion and expansion of the plane bitmap to 4bpp are handled
in assembly. This reduces the cost of a frame combining a restart, panel
redraw, and palette change, without changing the plane pixels or colors.

Audio follows the supplied Atari XL/XE recording `RiverRaid.wav`. Original
AUDC/AUDF/AUDV registers select engine, refueling, low-fuel alarm, missile
and explosion effects. `src/audio.c` supplies shared parameters for three
backends; `src/audio.asm` implements the PCM sample producer and a compact
OPL register uploader.

The `/opl2` and `/pcm` load parameters force a backend.
No parameter selects OPL2. `/auto` selects PCM if available, otherwise OPL2. Explicit
`/pcm` fails with a message on unsupported firmware. Arguments are case
insensitive, with the last audio option taking precedence; `/help` and `/?`
show usage. Unknown options exit with status 2 before displaying the cover.
For the emulator, use `rp6502-emu.exe riverraid.rp6502 -- /opl2`.
The SDK's optional `__argv_mem` allocator uses the existing 512-byte
`reset_tiles` buffer. Arguments are parsed before cover/video initialization
reuses that buffer, avoiding a heap allocation and a permanent argv buffer.

The one-shot jingles in `src/gameover.asm` share a sequencer and stream buffer.
The final-plane jingle uses the firmware generator's exact
OPL2 register writes and signed 16 kHz PCM at 200 BPM, including the last-bar
slowdown. GAME 1 detects the player's final death; GAME 2 requires both native
life pointers to indicate elimination, and GAME 3 requires both life counters
to reach zero. It plays once, then resumes the flight arrangement.
Mute, pause, restart, help and backend/mode changes cancel playback. An automatic
GAME 2 turn change does not trigger it while the other pilot has planes left.
With no PCM support, VSYNC clocks a complete OPL2 arrangement with drums.
The score occupies XRAM $F900, OPL2 registers $C900, and the PCM header/ring
$CA00/$CA08 (1024 bytes). ROM pages stream three pages ahead of the consumer.
After initial video setup, the player replaces startup-only argument parsing,
palette conversion in `STARTUP_AUDIO`; its temporary ZP copy routine then becomes
player state. This preserves the 1 KiB stack and survives returning from F1.
The reusable fade code stays resident in CODE, with state in BSS. Bridge-award
helpers live in MUSIC so the player still fits the smaller startup overlay.
The installed overlay also holds the DUO fuel-row renderer, which is first
used after selecting GAME 3. Before a flight starts, both DUO HUD panels show
three planes and full fuel; an active flight uses the actual player state.

The native bridge destruction path queues the victory fanfare when the HUD's
BRIDGE number is 5, 20 or 50. Native scrolling can advance that number before
destruction; the hook uses the visible number without a parity-based rollback.
The object changes to an explosion before the hook, so simultaneous DUO shots
cannot award twice. After both DUO contexts are saved, the reward adds one
reserve to the current classic player, or one life to both DUO players, capped
at nine classic reserves / ten DUO planes. An eliminated DUO pilot returns to
the normal waiting-for-bridge state. Score bonuses remain independent, and
mute suppresses only playback. The 96 BPM OPL2 + PCM arrangement preserves the
generator's broadening snare roll and final release. A final death interrupts
victory playback with the game-over jingle.

OPL2 uses all nine melodic channels. Four engine channels use deep FM without
feedback, a 3:1 modulator/carrier ratio and independent dither in overlapping
bands. The lower oscillator octave packs the sidebands more closely for a
smoother noise texture. Frequency follows the full speed accumulator over an
almost 3:1 range, with 0.095 Hz register resolution in the engine bands.
Three separate blast channels use a deeper 2:1 FM ratio; their noise bandwidth
falls with the native volume decay, from the initial impact into a low rumble.
No cymbal/hi-hat rhythm voices
are used. Missile and refueling/alarm
each have a separate channel, with additive fundamental and third harmonic
components for a square-like tone. Total-level attenuation maps native linear
volume to the YM3812's 0.75 dB steps. An assembly routine writes only changed
frequency, key and level registers, keeping the nine-voice update within the
Release frame budget. Audio has its own RNG and leaves course generation unchanged.
OPL2 remains an approximation of POKEY: its noise-like spectrum comes from FM
rather than the original audio-rate polynomial. FFT and Haar wavelet
measurements of the XL/XE recording guide bandwidth and treble balance.
Wavelets analyze the reference offline; the chip uses its fixed waveforms.

PCM uses two procedural voices at 8 kHz signed mono. The engine has a
17-bit polynomial clocked according to throttle. A two-sample average and
the PCM mixer's interpolation soften upper harmonics. The death burst uses
a 2 kHz polynomial clock and retains the native half-second volume decay.
The PCM header is at XRAM `$C000`, with a 2048-byte ring at `$C008`. OPL2
reuses the `$C000` page only when PCM is not selected. CPU RAM `$C000`
holds music code; these are separate address spaces.
The cover temporarily occupies this XRAM range, so audio initializes after
cover and graphics preparation. Two silent pages prime the PCM stream.
Each frame prepares at most 160 samples, publishing only complete 256-byte
pages through an atomic high-byte write. The queue target includes 512
prepared samples. The loop uses zero page below `$80`, leaves the native
game RNG untouched and rounds clocks to 31.25 Hz steps (15.625 Hz tones).
Only PCM requires the firmware extension `XREG(0,1,2,base)`. OPL2 uses
the standard [RIA sound interfaces](https://picocomputer.github.io/ria.html#yamaha-opl2-fm-sound-generator).

All backends preserve refueling/alarm sequences. Missiles descend from
about 400 to 200 Hz over 18 frames (0.3 seconds). OPL2 keeps the engine,
missile, blast and fuel tone on separate voices, so they can play together.
PCM retains its two-voice priority: bridge explosions override missiles.
Bank and road tanks trigger a descending 200-to-100 Hz shot; firing helicopters
use 800-to-400 Hz. Both use an 18-frame decaying envelope, triggered only when
a projectile launches. A new enemy shot retriggers their shared voice. OPL2
temporarily uses the fuel-tone voice, preserving player fire, explosions and
music. PCM temporarily replaces the engine/fuel voice, with crashes retaining
priority. Pause, mute, death and F1 discard the enemy-shot tail.
Death cancels the engine and missile tail. Pause and attract mode suppress
effects (demo music continues). Explicit OPL2 initialization stops any PCM stream, and exiting
releases the selected sound device.

The emulator checks export `audio-opl2-*.json` register traces and actual
CPU-generated PCM in `checks/audio/*-cpu.wav`. The effects tests isolate the
procedural synthesizer; separate music tests exercise the combined output.
`tools/preview_synth.py` renders OPL traces offline.
The `engine-ramp` captures use actual throttle input: acceleration, deceleration
and acceleration again, rather than changing the speed register between clips.
OPL traces additionally require a native library built from
`tools/opl_preview.c` and the firmware's MIT-licensed emu8950 source:
`--opl-library path/to/opl-preview.dll`. The model uses the firmware's gain
and clamp. These previews are not recordings from the host sound device
or physical hardware and omit analogue filtering.
`tools/analyze_audio.py` reports FFT spectra and Haar detail energy using
only the Python standard library. The supplied recording remains external.
After rendering the traces, `tools/compare_synth.py --previews build/audio-v2`
checks engine bandwidth, throttle response, excessive treble, fixed-tone
dominance and clipping, including all voices playing together. Short-window
OPL spectra also check for moving tones hidden by whole-clip averaging. Add
`--reference path/to/RiverRaid.wav` to produce `reference-vs-synth.wav`:
each group contains the XL/XE reference and OPL2 model, with matched
RMS levels and labels in the adjacent JSON file. Spectral agreement is a
measurement aid; perceived similarity still needs listening.
RGB555 approximates the colors of the supplied screenshots rather than
modeling the analog behavior of a particular television.
The hardware interfaces are described in the [VGA](https://picocomputer.github.io/vga.html)
and [RIA](https://picocomputer.github.io/ria.html) documentation.

## Visual references

The three `s_RiverRaid_*.png` files and five GIFs in `original/Atari 5200`
serve as references for the palette, mountains, banks, and panel layout.
The PNGs use these RGB values: water (4, 37, 136), dark land (19, 102, 0),
light land (79, 162, 26), rim (74, 0, 0), and panel (89, 89, 89).
The GIF and Atari XL palettes differ; the current port selects the darker
colors from the 5200 PNGs.
Ships have red hulls and turquoise lower sections, fuel tanks have pink
and gray stripes, and helicopters have dark bodies and salmon rotors.
The host rounds colors to RGB555; the color-role mapping in `src/graphics.h`
preserves the original B&W switching and screensaver. Colors absent from
the screenshots still use an approximation of the TIA hue.

The three GIFs in `original/Atari XL` and ten JPEGs in `original/Atari 2600`
are also used to compare objects. The game logic and course generator come
from the 2600; this port develops the appearance using XL/5200 references
rather than reproducing the XL/5200 raster or rules exactly. Balloons and
tanks are extensions of the port; their readable bitmaps in `src/graphics.h`
reproduce the silhouettes from the 5200 PNGs. The original 2600 data image
remains unchanged.

The fuel scale remains black for both players; the moving indicator is yellow.
The second player's plane retains the black color from the earlier 2600
variation; the panel and score for both players now use 5200-inspired colors.
The black HMOVE blanking bar on the left of the Atari images is not reproduced.
Screenshots show individual game states, so they do not yet confirm movement,
collision, and animation timing on a frame-by-frame basis.

## Verification and limitations

`python tests/emulator_checks.py` checks the actual ROM in RP6502-EMU at 8 MHz:
input, pause, fuel, hits, extra lives, the maximum score, the generator, death,
respawning, difficulty, player switching, and restarting.
A 1200-frame scenario checks scrolling with acceleration and firing.
The terrain test compares visible tile pixels, including rims, with collision
masks across the full playfield height. It also checks bridge alignment with
the banks, continuity of the brown contour at bends, and the rim crossing
the road. The other scenarios that end in gameplay also check for skipped
VSYNCs, including respawning, refueling, and player switching. The optional
frame-phase profiler is described in `tests/README.md`.
Audio tests check PCM registration, throttle response, effect/alarm priority,
pause and attract-mode silence. They export actual CPU-generated samples,
check ring wrap and publication, and simulate 8 kHz consumption while scrolling
and firing. Additional OPL2 scenarios use real load arguments, check engine
pitch/texture, priorities, pause/demo silence, exit and 1200-frame budgets.
Argument tests cover backend selection, uppercase options, help and errors.
Muted tests do not verify listening quality or real hardware timing.

Listening tests, frame-by-frame raster comparisons with an Atari emulator,
and testing on physical RP6502 hardware remain outstanding. Game logic
behavior is preserved by using the original routines; exact visual and
audio equivalence is not yet claimed.

## GAME 3 DUO flight positions

DUO runs the shared world once, then the native player rules in two separate
contexts (`src/duo.h`, `src/duo.inc`, `src/duo.asm`). Each context now includes
its own screen Y. Relative distance accumulates the difference of native
velocities (speed / 128 logical pixels per step) in a signed fixed-point
accumulator. Its limit is +/-72 pixels, or four 18-row plane heights.
The pair starts at Y=106 and moves around that center, remaining within
Y=70..142. Equal speeds preserve the accumulated lead; reversing the speed
difference starts closing it immediately, including at the limit.
The rendered position is the position used for collisions in that step;
native acceleration takes effect in the following step. A sole survivor
keeps its altitude and sets the scrolling speed. With both pilots alive,
world scrolling still uses the mean speed.

Player masks, enemy projectiles, tank splashes, refuelling and mutual plane
collisions use each pilot's Y. The missile launch hook translates that Y into
the native absolute missile coordinate, so subsequent throttle changes do not
move an airborne missile. The first pilot passing a bridge marks it as passed;
when a pilot is waiting, passage follows the sole survivor. This remains latched
while that bridge moves through the lower blocks, so changing speed or losing
the trailing plane cannot count an already passed bridge again.
Respawns use the survivor's speed and the fallen pilot's last altitude,
preserving the earned separation and the survivor's position. The spawn
checks terrain, enemies and the partner at that altitude.

When no plane remains in flight, the explosion runs for 32 ticks before
restarting the current section if either pilot still has lives. Lives are
charged only by `duo_kill`, never by the restart. `rr_duo_restart` reuses the
native death checkpoint selection and partial `GameInit`: it restores the
section RNG, including rollback of a section generated ahead of the planes,
without swapping players or resetting scores. The host rebuilds terrain and
clears tanks and helicopter shots before attempting safe spawns. Both heights
return to Y=106 with zero relative lead and full fuel. Empty life pools remain
eliminated; only two empty pools produce game over.

DUO labels, score digits, reserve icons and fuel fills follow their
pilot's plane color, including the
black-and-white switch. Dedicated HUD palettes keep BRIDGE and its number
in the GAME 1 colors. Returning to the classic panel stages its labels and
sprites separately from the score/fuel bitmap to stay within the frame budget.
Both DUO fuel gauges share GAME 1's `fuel_gauge`/`fuel_rows` artwork and
39-by-16 dimensions, at HUD row 10. Their colored fills shrink across the
37-column interior behind the opaque artwork. An assembly row copier applies
the fill and mask together. At most one complete gauge is redrawn per frame;
the second changed value remains pending for the next frame. SELECT completes
its world reset before the replacement HUD layout begins.
The GAME and BRIDGE labels start at the fuel gauges' X=4 and X=84, at Y=28.
DUO reserves use the GAME 1 plane bitmap, with five icons per row at X=44/124
and a seven-column pitch. The rows start at Y=10 and Y=19, leaving one blank
scanline between eight-row icons. Twenty sprite records at XRAM $6400 use
HUD plane 2; only changed visibility coordinates are updated. The DUO bonus
life limit is ten (encoded as 80); both native scoring and tank bonuses use
the same limit comparison, while GAME 1/2 keep their original limit of nine.

Eight-column enemy collisions compare bitmap rows directly to keep two
simultaneous collisions within the frame budget. The readable mountain art
remains in `src/graphics.h`; `tools/pack_mountains.py` generates the two-bit
`mountains.h` table at build time (840 instead of 3360 bytes), preserving all
pixels and providing space for the added DUO code.
