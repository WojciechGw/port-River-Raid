; Two unscaled 64x64 indexed sprites, above the demo world and its planes.
; Keep addresses in sync with xram.h; checked against the packaged asset.
.include "rp6502.inc"
.macpack longbranch
.export _demo_splash_load, _demo_splash_present, _demo_splash_palette
.export _demo_splash_reset, _demo_splash_start, _demo_splash_x, _demo_splash_done, _demo_splash_out
.import boot_open, boot_read_xram, boot_close, _sprites, _ready, _paused, boot_fd
.export _demo_splash_kind, _demo_splash_gameover, _demo_splash_cancel
.export _demo_splash_gameover_phase, _demo_splash_music_done
.import _gameover_active, _jingle_kind
LEFT = $6500
RIGHT = $D600
FRONT = $7500
PALETTE = $7580
COLORS = $7780

.segment "BSS"
_demo_splash_x: .res 2
_demo_splash_out: .res 1
_demo_splash_done: .res 1
_demo_splash_kind: .res 1      ; 0 plane, 1 ready, 2 game over.
splash_loaded: .res 1
_demo_splash_gameover_phase: .res 1 ; 0 normal, 1 arriving, 2 holding, 3 departing.
_demo_splash_music_done: .res 1
splash_hold: .res 2              ; Silent/interrupted tune: 107264/16000*60 frames.

.segment "CODE"
; A new demo starts just beyond the right edge. F1 retains its position.
_demo_splash_reset:
    lda _demo_splash_gameover_phase
    bne @done                  ; Native demo may resume before the tune ends.
    lda #<320
    sta _demo_splash_x
    lda #>320
    sta _demo_splash_x+1
    stz _demo_splash_out
    stz _demo_splash_done
    stz _demo_splash_kind
@done:
    rts

; Repeated start presses must not reset the slide.
_demo_splash_start:
    stz _demo_splash_gameover_phase
    stz _demo_splash_kind
    lda #1
    sta _demo_splash_out
    rts

_demo_splash_gameover:
    stz _demo_splash_gameover_phase
    jsr _demo_splash_reset
    inc _demo_splash_gameover_phase
    stz _demo_splash_music_done
    lda #<403
    sta splash_hold
    lda #>403
    sta splash_hold+1
    rts

_demo_splash_cancel:
    stz _demo_splash_gameover_phase
    stz _demo_splash_kind
    stz _demo_splash_out
    lda #1
    sta _demo_splash_done
    rts

; Direct ROM -> XRAM. The music streamer may own boot_fd between frames;
; preserve its descriptor and cursor while opening this independent asset.
splash_load_image:
    lda boot_fd
    pha
    lda boot_fd+1
    pha
    ldy _demo_splash_kind
    lda paths_lo,y
    ldx paths_hi,y
    jsr boot_open
    xreg_values LEFT,4096
    lda #0
    ldx #16
    jsr boot_read_xram
    xreg_values RIGHT,4096
    lda #0
    ldx #16
    jsr boot_read_xram
    xreg_values COLORS,1024
    lda #0
    ldx #4
    jsr boot_read_xram
    jsr boot_close
    pla
    sta boot_fd+1
    pla
    sta boot_fd
    lda _demo_splash_kind
    sta splash_loaded
    jmp _demo_splash_palette

; F1 overwrites video memory, so reload the current image even if unchanged.
_demo_splash_load:
    jsr splash_load_image
    lda #1
    sta RIA_STEP0
    lda #<(FRONT+20)
    sta RIA_ADDR0
    lda #>FRONT
    sta RIA_ADDR0+1
    ldy #0
@config:
    lda sprites,y
    sta RIA_RW0
    iny
    cpy #20
    bne @config
    rts

_demo_splash_palette:
    ; Full brightness throughout both slides; F4 selects color or grayscale.
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    lda #<PALETTE
    sta RIA_ADDR0
    lda #>PALETTE
    sta RIA_ADDR0+1
    lda #<COLORS
    sta RIA_ADDR1
    lda $86
    cmp #255
    beq @color
    lda #>(COLORS+512)
    bra @source
@color:
    lda #>COLORS
@source:
    sta RIA_ADDR1+1
    ldx #0                   ; 256 RGB555 entries, two bytes each.
@copy:
    lda RIA_RW1
    sta RIA_RW0
    lda RIA_RW1
    sta RIA_RW0
    dex
    bne @copy
    rts

; Enter at 2 px/frame (60 frames); exit left at 8 px/frame (41 frames
; from the resting position). Pause and F1 retain the pending start.
splash_tick:
    lda _paused
    ora _demo_splash_done
    jne @done
    lda _demo_splash_gameover_phase
    beq @normal
    lda splash_hold
    ora splash_hold+1
    beq @hold
    lda splash_hold
    bne :+
    dec splash_hold+1
:
    dec splash_hold
@hold:
    lda _demo_splash_gameover_phase
    cmp #2
    bne @normal
    lda _demo_splash_music_done
    bne @leave_gameover
    lda _gameover_active
    beq @silent
    lda _jingle_kind
    beq @done                  ; Wait for the actual PCM/OPL sequencer end.
@silent:
    lda splash_hold
    ora splash_hold+1
    bne @done                  ; Muted/F1-interrupted music uses its duration.
@leave_gameover:
    lda #3
    sta _demo_splash_gameover_phase
    lda #1
    sta _demo_splash_out        ; Keep the GAME OVER image while leaving.
@normal:
    lda _demo_splash_out
    bne @out
    lda _demo_splash_x+1
    bne @in
    lda _demo_splash_x
    cmp #200                    ; X end position of 1st sprite
    bne @in
    lda _demo_splash_gameover_phase
    beq @ready
    lda #2
    sta _demo_splash_gameover_phase
    sta _demo_splash_kind
    rts
@ready:
    lda #1
    sta _demo_splash_kind
    rts
@in:
    lda _demo_splash_x
    sec
    sbc #2
    sta _demo_splash_x
    lda _demo_splash_x+1
    sbc #0
    sta _demo_splash_x+1
    rts
@out:
    lda _demo_splash_x
    sec
    sbc #8                   ; plane fly out speed (16 very fast)
    sta _demo_splash_x
    lda _demo_splash_x+1
    sbc #0
    sta _demo_splash_x+1
    bpl @done
    lda _demo_splash_x
    cmp #129
    bcs @done
    lda #128                 ; Clamp at X=-128: both tiles are off screen.
    sta _demo_splash_x
    inc _demo_splash_done
    lda _demo_splash_gameover_phase
    cmp #3
    bne @done
    stz _demo_splash_gameover_phase
    jmp _demo_splash_reset      ; New plane entry, then ARE YOU READY.
@done:
    rts

; Called at VSYNC with the other sprite descriptors. Keep the original
; player slots for diagnostics while publishing both jets and the overlay
; in one contiguous front-plane list (VGA allows one list per plane).
_demo_splash_present:
    lda _demo_splash_gameover_phase
    bne @tick
    lda _ready
    cmp #2
    bne @image
    lda $c6
    cmp #255
    beq @image
@tick:
    jsr splash_tick
@image:
    lda _demo_splash_kind
    cmp splash_loaded
    beq @draw
    jsr splash_load_image     ; Keep both sprite descriptors visible.
@draw:
    lda #1
    sta RIA_STEP0
    lda #<FRONT
    sta RIA_ADDR0
    lda #>FRONT
    sta RIA_ADDR0+1
    ldy #0
@jets:
    lda _sprites+230,y
    sta RIA_RW0
    iny
    cpy #20
    bne @jets
    lda _demo_splash_gameover_phase
    bne @visible
    lda _ready
    cmp #2
    bne @hidden              ; Hide through startup fade and actual play.
    lda $c6
    cmp #255
    beq @hidden              ; Next demo tick will restart the fade.
    lda _demo_splash_done
    bne @hidden
@visible:
    ldx #0
    ldy #4                   ; Y position of sprites
    bra @position
@hidden:
    ldx #255                 ; X start position of sprites
    ldy #0
@position:
    lda #>FRONT
    sta RIA_ADDR0+1
    lda #<(FRONT+20)
    sta RIA_ADDR0
    lda _demo_splash_x
    sta RIA_RW0
    lda _demo_splash_x+1
    sta RIA_RW0
    sty RIA_RW0
    stx RIA_RW0
    lda #<(FRONT+30)
    sta RIA_ADDR0
    lda _demo_splash_x
    clc
    adc #64
    sta RIA_RW0
    lda _demo_splash_x+1
    adc #0
    sta RIA_RW0
    sty RIA_RW0
    stx RIA_RW0
    rts

.segment "RODATA"
paths_lo: .lobytes plane_path,ready_path,gameover_path
paths_hi: .hibytes plane_path,ready_path,gameover_path
plane_path: .asciiz "ROM:splash-plane.bin"
ready_path: .asciiz "ROM:splash-areyouready.bin"
gameover_path: .asciiz "ROM:splash-gameover.bin"
sprites:
    .word 320,4,LEFT,PALETTE
    .byte $FF,$03             ; 64x64, 8bpp, no doubling.
    .word 384,4,RIGHT,PALETTE
    .byte $FF,$03

