; Two unscaled 64x64 indexed sprites, above the demo world and its planes.
; Keep addresses in sync with xram.h; checked against the packaged asset.
.include "rp6502.inc"
.export _demo_splash_load, _demo_splash_present, _demo_splash_palette
.export _demo_splash_reset, _demo_splash_start, _demo_splash_x, _demo_splash_done, _demo_splash_out
.import boot_open, boot_read_xram, boot_close, _sprites, _ready, _paused
LEFT = $6500
RIGHT = $D600
FRONT = $7500
PALETTE = $7580
COLORS = $7780

.segment "BSS"
_demo_splash_x: .res 2
_demo_splash_out: .res 1
_demo_splash_done: .res 1

.segment "CODE"
; A new demo starts just beyond the right edge. F1 retains its position.
_demo_splash_reset:
    lda #<320
    sta _demo_splash_x
    lda #>320
    sta _demo_splash_x+1
    stz _demo_splash_out
    stz _demo_splash_done
    jmp _demo_splash_palette

; Repeated start presses must not reset the slide.
_demo_splash_start:
    lda #1
    sta _demo_splash_out
    rts

_demo_splash_load:
    lda #<path
    ldx #>path
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
    bne @done
    lda _demo_splash_out
    bne @out
    lda _demo_splash_x+1
    bne @in
    lda _demo_splash_x
    cmp #200                    ; X end position of 1st sprite
    beq @done
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
@done:
    rts

; Called at VSYNC with the other sprite descriptors. Keep the original
; player slots for diagnostics while publishing both jets and the overlay
; in one contiguous front-plane list (VGA allows one list per plane).
_demo_splash_present:
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
    lda _ready
    cmp #2
    bne @hidden              ; Hide through startup fade and actual play.
    lda $c6
    cmp #255
    beq @hidden              ; Next demo tick will restart the fade.
    jsr splash_tick
    lda _demo_splash_done
    bne @hidden
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
path: .asciiz "ROM:demo-splash.bin"
sprites:
    .word 320,4,LEFT,PALETTE
    .byte $FF,$03             ; 64x64, 8bpp, no doubling.
    .word 384,4,RIGHT,PALETTE
    .byte $FF,$03

