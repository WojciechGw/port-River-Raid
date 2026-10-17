; Cover uses XRAM before game startup and after audio stops on exit.
; Shared helpers live above the reference ROM to preserve game RAM/stack space.
.include "rp6502.inc"
.include "cover.inc"
.macpack longbranch
.importzp ptr1
.export _show_cover, _show_outro, _show_manual
.import _reset_tiles, intro_init, intro_tick, intro_stop, __INTRO_SCORE_SIZE__
.export boot_scene
.segment "SPLASH"

COVER_CONFIG  = $0280
COVER_PALETTE = $0400
COVER_STAGING = $0600
COVER_IMAGE   = $1000
COVER_PROMPT_CONFIG  = $02A0
COVER_PROMPT_IMAGE   = $0800
OUTRO_PROMPT_IMAGE   = $0900
COVER_PROMPT_PALETTE = $0850
COVER_PROMPT_Y       = 222
COVER_BLINK_FRAMES   = 30   ; Half a second on, half a second off, at 60 Hz
OUTRO_HOLD_FRAMES    = 180  ; Three seconds at 60 Hz
COVER_STATE   = $00B0         ; 1 fade in, 2 wait, 3 fade out, 4 black, 0 game
COVER_LEVEL   = COVER_STATE+1 ; 0..63, observable by emulator checks
COVER_SCENE   = $00B4         ; 0 cover, 1 outro, 2 manual

.macro boot_address portal, address
    lda #<(address)
    sta portal
    lda #>(address)
    sta portal+1
.endmacro

.macro boot_open_file name
    lda #<(name)
    ldx #>(name)
    jsr boot_open
.endmacro

.macro boot_read address, count
    ; READ_XRAM's count is limited to $7FFF. Reject errors and short reads.
    xreg_values address, count
    lda #<(count)
    ldx #>(count)
    jsr boot_read_xram
.endmacro

.segment "CODE"
_show_manual:
    lda #1
    sta boot_help
    lda #2
    sta boot_scene
    jmp boot_show
_show_outro:
    lda #0
    sta boot_help
    lda #1
    sta boot_scene
    jmp boot_show
.segment "SPLASH"
_show_cover:
    lda #0
    sta boot_help
    sta boot_scene
boot_show:
    lda #$ff
    sta boot_fd+1
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    ; Shared screen helpers and the music player borrow terrain scratch RAM.
    ; Staging is safe even on F1: never touch the saved video above $F100.
    boot_open_file intro_path
    boot_read COVER_STAGING, 512
    boot_address RIA_ADDR0, COVER_STAGING
    ldy #0
@overlay:
    lda RIA_RW0
    sta _reset_tiles,y
    iny
    bne @overlay
@overlay_hi:
    lda RIA_RW0
    sta _reset_tiles+256,y
    iny
    bne @overlay_hi
    lda boot_scene
    bne @no_score
    boot_read $F100, __INTRO_SCORE_SIZE__
@no_score:
    jsr boot_close
    ; State data must not look like an initialized game while the cover is up.
    boot_address RIA_ADDR0, $0080
    lda #0
    sta RIA_RW0
    boot_address RIA_ADDR0, COVER_STATE
    sta RIA_RW0
    sta RIA_RW0
    boot_address RIA_ADDR0, COVER_SCENE
    lda boot_scene
    sta RIA_RW0
    asl a
    tay
    lda image_paths,y
    ldx image_paths+1,y
    jsr boot_open
    boot_read COVER_IMAGE, COVER_HALF_BYTES
    boot_read COVER_IMAGE+COVER_HALF_BYTES, COVER_HALF_BYTES
    jsr boot_close
    lda boot_scene
    jeq @startup_prompt
    cmp #2
    beq @manual_prompt
    boot_open_file outro_path
    boot_read OUTRO_PROMPT_IMAGE, OUTRO_PROMPT_BYTES
    jmp @prompt_loaded
@manual_prompt:
    boot_open_file manual_prompt_path
    boot_read OUTRO_PROMPT_IMAGE, MANUAL_PROMPT_BYTES
    jmp @prompt_loaded
@startup_prompt:
    boot_open_file prompt_path
    boot_read COVER_PROMPT_IMAGE, COVER_PROMPT_BYTES
@prompt_loaded:
    jsr boot_close
    boot_address RIA_ADDR0, COVER_PROMPT_PALETTE
    lda #$20                ; Opaque black background, opaque white letters
    sta RIA_RW0
    lda #0
    sta RIA_RW0
    lda #$ff
    sta RIA_RW0
    sta RIA_RW0
    lda boot_scene
    asl a
    tay
    lda fade_paths,y
    ldx fade_paths+1,y
    jsr boot_open
    ; Publish the first, black palette before enabling the bitmap plane.
    lda #0
    sta boot_level
    jsr boot_prepare_palette
    jsr boot_copy_palette
    boot_address RIA_ADDR0, COVER_CONFIG
    ldy #0
@config:
    lda cover_config,y
    sta RIA_RW0
    iny
    cpy #14
    bne @config
    boot_address RIA_ADDR0, COVER_PROMPT_CONFIG
    ldy #0
@prompt_config:
    lda prompt_config,y
    ldx boot_scene
    beq @write_prompt_config
    cpx #2
    beq @manual_config
    lda outro_config,y
    jmp @write_prompt_config
@manual_config:
    lda manual_config,y
@write_prompt_config:
    sta RIA_RW0
    iny
    cpy #14
    bne @prompt_config
    xreg 1,0,0,1             ; 320x240; center the 320x180 cover at Y=30
    jmi boot_error
    xreg 0,0,0,0             ; Direct HID keyboard, including modifier keys
    jmi boot_error
    xreg 1,0,1,3,3,COVER_CONFIG,0
    jmi boot_error
    xreg 1,0,1,3,0,COVER_PROMPT_CONFIG,1
    jmi boot_error
    jsr intro_init
    lda #1
    jsr boot_state
    ; Level zero has already been loaded. Every subsequent palette is read
    ; into hidden XRAM, then copied in ~0.8 ms just after VSYNC, before Y=30.
    inc boot_level
@fade_in:
    jsr boot_next_palette
    inc boot_level
    lda boot_level
    cmp #COVER_FADE_FRAMES
    bne @fade_in
    lda #2
    jsr boot_state
    lda boot_scene
    cmp #1
    bne @startup_wait
    lda #OUTRO_HOLD_FRAMES
    sta boot_blink
    lda #1
    sta boot_prompt_visible
    jsr boot_vsync
    jsr boot_prompt
@outro_wait:
    jsr boot_vsync
    dec boot_blink
    bne @outro_wait
    jmp @dismiss
@startup_wait:
    ; F1 opens help but must not dismiss it, even when held through fade in.
    lda boot_help
    beq @ready_prompt
@release_help:
    jsr boot_vsync
    jsr boot_any_key
    bne @release_help
@ready_prompt:
    lda #COVER_BLINK_FRAMES
    sta boot_blink
    lda #1
    sta boot_prompt_visible
    jsr boot_vsync
    jsr boot_prompt
@wait_key:
    jsr boot_vsync
    jsr boot_any_key
    bne @dismiss
    dec boot_blink
    bne @wait_key
    lda #COVER_BLINK_FRAMES
    sta boot_blink
    lda boot_prompt_visible
    eor #1
    sta boot_prompt_visible
    jsr boot_prompt
    jmp @wait_key
@dismiss:
    lda #0
    sta boot_prompt_visible
    jsr boot_prompt
    lda #3
    jsr boot_state
    lda #COVER_FADE_FRAMES-1
    sta boot_level
@fade_out:
    jsr boot_next_palette
    dec boot_level
    bpl @fade_out
    lda #4
    jsr boot_state
    jsr intro_stop
    lda boot_scene
    cmp #1
    bne @release_key
    ; Show a completely black frame, then return even if Escape is held.
    jsr boot_vsync
    jsr boot_close
    rts
    ; Display the last black frame and consume the dismissal key completely.
    ; Holding Space/F3/P/Escape must not also start/change/pause/exit the game.
@release_key:
    jsr boot_vsync
    jsr boot_any_key
    bne @release_key
    jsr boot_close
    lda boot_scene
    bne @restore_game
    lda #2
    sta boot_scene
    jmp boot_show
@restore_game:
    xreg 1,0,0,1             ; Blank the cover before restoring game assets
    jmi boot_error
    boot_open_file footer_path
    boot_read $3800, DEMO_ASSET_BYTES
    jsr boot_close
    lda #0
    jsr boot_state
    rts

boot_next_palette:
    jsr boot_prepare_palette
    jsr boot_vsync
    jsr boot_copy_palette
    boot_address RIA_ADDR0, COVER_LEVEL
    lda boot_level
    sta RIA_RW0
    rts

boot_prepare_palette:
    boot_read COVER_STAGING, 512
    rts

.segment "INTRO"
boot_copy_palette:
    boot_address RIA_ADDR0, COVER_PALETTE
    boot_address RIA_ADDR1, COVER_STAGING
    ldy #0
@copy:
    lda RIA_RW1
    sta RIA_RW0
    lda RIA_RW1
    sta RIA_RW0
    iny
    bne @copy
    rts

.segment "SPLASH"
boot_vsync:
    jsr intro_tick
    lda RIA_VSYNC
@wait:
    cmp RIA_VSYNC
    beq @wait
    rts

.segment "INTRO"
boot_any_key:
    boot_address RIA_ADDR0, 0
    lda RIA_RW0
    and #$f0                ; Bits 0..3 are no-key / lock LED status, not keys
    sta boot_keys
    ldy #31
@scan:
    lda RIA_RW0
    ora boot_keys
    sta boot_keys
    dey
    bne @scan
    lda boot_keys
    rts

; Called only just after VSYNC. Hide by moving below the canvas's top edge.
boot_prompt:
    boot_address RIA_ADDR0, COVER_PROMPT_CONFIG+4
    lda boot_prompt_visible
    beq @hidden
    lda #COVER_PROMPT_Y
    sta RIA_RW0
    lda #0
    sta RIA_RW0
    rts
@hidden:
    lda #0
    sta RIA_RW0
    lda #$ff                ; Y=-256
    sta RIA_RW0
    rts

.segment "SPLASH"
boot_state:
    tax
    boot_address RIA_ADDR0, COVER_STATE
    stx RIA_RW0
    rts

; File helpers live below $C000 to reserve the entire $FE00 CPB page.
.segment "CODE"
boot_open:
    sta ptr1
    stx ptr1+1
    ldy #0
@length:
    lda (ptr1),y
    beq @push
    iny
    bne @length
@push:
    ; Strings go on XSTACK reversed, including their terminating zero.
    lda (ptr1),y
    sta RIA_XSTACK
    dey
    bpl @push
    lda #1                  ; O_RDONLY
    sta RIA_A
    lda #0
    sta RIA_X
    lda #RIA_OP_OPEN
    sta RIA_OP
    jsr RIA_SPIN
    jmi boot_error
    sta boot_fd
    stx boot_fd+1
    rts

boot_close:
    lda boot_fd
    sta RIA_A
    lda boot_fd+1
    sta RIA_X
    lda #RIA_OP_CLOSE
    sta RIA_OP
    jsr RIA_SPIN
    lda #$ff
    sta boot_fd+1
    rts

.segment "SPLASH"
; Shared checked read keeps room for the caption in the fixed CPU map.
boot_read_xram:
    sta boot_read_count
    stx boot_read_count+1
    lda boot_fd
    sta RIA_A
    lda boot_fd+1
    sta RIA_X
    lda #RIA_OP_READ_XRAM
    sta RIA_OP
    jsr RIA_SPIN
    cmp boot_read_count
    jne boot_error
    cpx boot_read_count+1
    jne boot_error
    rts

boot_error:
    lda boot_fd+1
    bmi @closed
    jsr boot_close
@closed:
    xreg 0,1,1,$ffff
    xreg 0,0,0,$ffff
    xreg 1,0,0,0
    lda #1
    sta RIA_A
    lda #0
    sta RIA_X
    lda #RIA_OP_EXIT
    sta RIA_OP
    jmp RIA_SPIN

.segment "RODATA"
cover_config:
    .byte 0,0
    .word 0,30,320,180,COVER_IMAGE,COVER_PALETTE
prompt_config:
    .byte 0,0
    .word 120,$ff00,80,8,COVER_PROMPT_IMAGE,COVER_PROMPT_PALETTE
cover_path:  .asciiz "ROM:cover.bin"
fade_path:   .asciiz "ROM:cover-fade.bin"
prompt_path: .asciiz "ROM:cover-prompt.bin"
footer_path: .asciiz "ROM:demo-footer.bin"
.segment "SPLASH"
intro_path: .asciiz "ROM:intro.bin"
.segment "DATA"
boot_fd:     .word $ffff
boot_level:  .byte 0
boot_keys:   .byte 0
boot_blink:  .byte 0
boot_prompt_visible: .byte 0
boot_scene: .byte 0
boot_help: .byte 0
boot_read_count: .word 0

.assert COVER_IMAGE+2*COVER_HALF_BYTES <= $10000, error, "Cover exceeds XRAM"
.assert COVER_FADE_FRAMES <= 128, error, "Fade counter range"
.assert DEMO_ASSET_BYTES <= $2000, error, "Demo footer overlaps mountain"
.assert COVER_PROMPT_IMAGE+COVER_PROMPT_BYTES <= COVER_PROMPT_PALETTE, error, "Prompt overlaps palette"
.assert COVER_PROMPT_PALETTE+4 <= COVER_IMAGE, error, "Prompt overlaps cover"
.assert OUTRO_PROMPT_IMAGE+OUTRO_PROMPT_BYTES <= COVER_IMAGE, error, "Outro prompt overlaps cover"

.segment "RODATA"
outro_config:
    .byte 0,0
    .word (320-OUTRO_PROMPT_WIDTH)/2,$ff00,OUTRO_PROMPT_WIDTH,8,OUTRO_PROMPT_IMAGE,COVER_PROMPT_PALETTE
outro_path: .asciiz "ROM:outro-prompt.bin"

manual_config:
    .byte 0,0
    .word (320-MANUAL_PROMPT_WIDTH)/2,$ff00,MANUAL_PROMPT_WIDTH,8,OUTRO_PROMPT_IMAGE,COVER_PROMPT_PALETTE
image_paths: .word cover_path, outro_image_path, manual_image_path
fade_paths: .word fade_path, outro_fade_path, manual_fade_path
outro_image_path: .asciiz "ROM:outro.bin"
outro_fade_path: .asciiz "ROM:outro-fade.bin"
manual_image_path: .asciiz "ROM:manual.bin"
manual_fade_path: .asciiz "ROM:manual-fade.bin"
manual_prompt_path: .asciiz "ROM:manual-prompt.bin"
.assert OUTRO_PROMPT_IMAGE+MANUAL_PROMPT_BYTES <= COVER_IMAGE, error, "Manual prompt overlaps cover"
