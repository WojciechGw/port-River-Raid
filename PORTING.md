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

F3 selects the starting bridge in the cycle 1 → 5 → 20 → 50 → 1 and starts
a new game. The selection applies to both players and remains active when
restarting with R. Full initialization applies the selected level, while
respawning and player switching preserve each player's current section.
In the executable copy of the routines, the level limit was increased from
48 to 50; after section 50, the generator returns to 49. The original ROM
image remains unchanged. Missile guidance is now toggled with F5/F4.

Balloons (ID 11) extend the executable copy of the routines: from level two,
they replace some randomly generated enemies, moving and bouncing off the
banks like helicopters. Shooting a balloon awards 60 points; contact with
the plane causes an explosion.
A tank is an additional object in every bridge block, starting with the
first bridge. It drives along the road and turns around at its ends. Its
state moves with the terrain block, pause stops its movement, and restarting
or respawning restores its state. A tank on the land portion of the road
awards 250 points; hitting a bridge with a tank on its span destroys both
objects and awards 750 points in total instead of 500.
The additional 250 points use the original decimal digit pointers, reserve
awards every 10,000 points, the limit of nine lives, and score overflow behavior.
In this version, tanks do not fire or patrol the banks from bridge seven onward.
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
The program starts at `$0300`. The original ROM image is stored as data at
`$C000–$CFFF`, preserving the bytes assembled for the Atari at `$F000`.
The executable routines have relocated references and a separate initialization
table. The Atari raster code is not executed. There is no Atari CPU emulation.

VGA uses a 320×240 canvas, with the playfield on scanlines 21–180 and logical
coordinates of 160×160. The river uses the original PF0/PF1/PF2 bit order,
mirroring, and road tables. A 40×192 ring buffer stores indices of 8×1-pixel
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
explosion copies, and plane wrapping at the edges. The player's plane occupies
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
depends on the current fuel level.
Three mountain variants replace the house and tree from the 2600 version.
Two were reconstructed from `original/Atari XL/image0.png`: a tall mountain
range with blue slopes and lower brown peaks with black ridges. The third is
a single medium-sized mountain with a black ridge. The variant depends on
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
game counter and can reach nine.
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
The black footer on scanlines 219–229 contains the Activision logo, copied
pixel by pixel from `original/Atari 5200/river_raid_5.gif` (X 48–167, Y 211–217).
The 120×7 bitmap preserves the lettering, five rainbow colors, and the diagonal
connection to the letter A. It starts at canvas X 48, three rows below the
top of the footer. A separate sprite and palette preserve the GIF's colors
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
After fade in, the program waits for any HID key, including function keys
and modifiers; LED status bits do not dismiss the cover. The dismissal key
is consumed through its release so it cannot also trigger game controls.
The code and its few working bytes occupy free CPU memory from $D000,
after the original ROM, without taking space reserved for the stack or game
buffers. After fade out, the program restores the footer strip from a ROM
asset, and game initialization restores the remaining assets in the reused XRAM.

In attract mode, the footer is replaced by a caption scrolling left by one
canvas pixel per frame. The text and readable glyphs are in `src/demo-footer.json`.
After the first game screen is displayed, a 180-VSYNC counter (3 seconds)
holds the caption and demo. Both start in the same frame. The demo runs the
original terrain generator and enemy movement; it skips plane controls,
firing, fuel consumption, and player collisions. Pause also stops the
startup countdown.
The typeface reproduces the bold 6×6 letters from Atari XL/5200 samples,
in cells eight logical pixels wide; the wider "w" occupies seven columns,
and an additional row accommodates lowercase descenders.
TM uses raised 3×5 and 5×5 glyphs, without a preceding space. The same logo
bitmap from `src/graphics.h` is inserted at `{Activision}`. The generator
`tools/make_demo_footer.py` prepares the entire strip when building the ROM;
the program loads it into XRAM $3800 after dismissing the cover. VGA scrolls
the bitmap with horizontal wrapping, without the CPU drawing letters each
frame. A separate palette preserves the light gray text even during the
screensaver. Pause stops the caption; starting a game restores the static
logo, and game over restores scrolling.

The program computes pixel collisions before calling the original game
logic, setting its collision flags. Assembly routines handle scanline
transfers and sprite/terrain checks. Input supports USB HID and two gamepads.
The game clock comes from `RIA.vsync` at 60 Hz. The skipped-frame counter
covers all operations after the initial video configuration, including
restarting, respawning, and player switching.

The scroll position, object list, and caption offset are prepared in RAM
during the preceding frame. Immediately after VSYNC, the `present_frame`
assembly routine publishes them together to XRAM in about 0.3 ms at 8 MHz,
before scanout reaches the first river scanline. Terrain and collision
calculations do not delay this publication. The absence of skipped VSYNCs
alone does not rule out tearing if the background position changes while
a frame is being displayed.

Restarting restores the initial straight corridor with a fast assembly
routine. In Release measurements at 8 MHz, terrain restoration time fell
from about 391 ms to 5–6 ms. The panel transfers only the columns occupied
by digits, fuel, and the logo; glyph rendering is handled in assembly, and
PSG frequencies use tables prepared at startup instead of division in each
frame. Player switching updates only the plane palette; a full palette
update is still needed when changing the color mode or screensaver state.
The bank renderer uses fixed working buffers, reducing cc65 stack access
cost during respawning.
TIA color conversion and expansion of the plane bitmap to 4bpp are handled
in assembly. This reduces the cost of a frame combining a restart, panel
redraw, and palette change, without changing the plane pixels or colors.

The PSG receives frequencies, volumes, and waveform types derived from the
original AUDC/AUDF/AUDV registers. Effect sequences come from the original
game, but PSG noise does not exactly reproduce the TIA polynomial generators.
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
and gray stripes, and helicopters have dark bodies and gold rotors.
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
The tests are muted, so they do not verify sound quality.

Listening tests, frame-by-frame raster comparisons with an Atari emulator,
and testing on physical RP6502 hardware remain outstanding. Game logic
behavior is preserved by using the original routines; exact visual and
audio equivalence is not yet claimed.
