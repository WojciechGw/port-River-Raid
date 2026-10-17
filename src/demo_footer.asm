; Shared attract-mode caption; keep the frame path compact at 8 MHz.
.include "rp6502.inc"
.include "cover.inc"
.export _demo_footer_tick
.export _demo_footer
.exportzp _footer_offset
.import _ready, _paused, _shown_demo, _high_dirty, _hud_sprites

FOOTER_CONFIG = $0260
FOOTER_Y = 222
CLASSIC_WIDTH = DEMO_ASSET_BYTES / 4
DUO_WIDTH = DUO_DEMO_ASSET_BYTES / 4
FOOTER_DELAY = 180
FOOTER_SCREEN_DELAY = 60
; Both strips have widths divisible by four. Counting four-pixel steps
; keeps the 320-pixel cadence continuous across either bitmap's wrap point.
FOOTER_SCREEN_QUARTERS = 320/4
.assert (CLASSIC_WIDTH & 3) = 0, error, "Classic caption must end on a four-pixel boundary"

.segment "ZEROPAGE"
_footer_offset: .res 2
footer_delay: .res 1
footer_quarters: .res 1

.segment "SPLASH"
_demo_footer_tick:
    ldx #0
    lda _ready
    bne @demo
    lda $c6
    cmp #255
    bne @visibility
@demo:
    inx
@visibility:
    cpx _shown_demo
    beq @tick
    stx _shown_demo
    lda #1
    sta _high_dirty
    sta RIA_STEP0
    lda #<FOOTER_CONFIG
    sta RIA_ADDR0
    lda #>FOOTER_CONFIG
    sta RIA_ADDR0+1
    ldy #0
    lda $80
    cmp #2
    bne @config
    ldy #14
@config:
    ldx #14
@copy:
    lda footer_configs,y
    sta RIA_RW0
    iny
    dex
    bne @copy
    stz _footer_offset
    stz _footer_offset+1
    ; F1 restores video with pause forced on: preserve the live countdown.
    lda _paused
    bne @initialized
    lda #FOOTER_DELAY
    sta footer_delay
@initialized:
    ; The caption is for attract mode; the complete logo stays below it.
    lda _shown_demo
    bne @logo
    lda #<(FOOTER_CONFIG+4)
    sta RIA_ADDR0
    lda #0
    sta RIA_RW0
    lda #255
    sta RIA_RW0
@logo:
    ldx #9
@logo_byte:
    lda logo_config,x
    sta _hud_sprites+180,x
    dex
    bpl @logo_byte
@tick:
    lda _shown_demo
    beq @done
    lda _ready
    dec a
    beq @done
    lda _paused
    bne @done
    jsr footer_wait
    bcs @done
    inc _footer_offset
    bne @wrap
    inc _footer_offset+1
@wrap:
    ldy #0
    lda $80
    cmp #2
    bne @width
    ldy #14
@width:
    lda _footer_offset
    cmp footer_configs+6,y
    bne @done
    lda _footer_offset+1
    cmp footer_configs+7,y
    bne @done
    lda #0
    sta _footer_offset
    sta _footer_offset+1
@done:
    rts

.segment "CODE"
; Carry set holds the position. Count only actual scrolling pixels, with
; a full second at each screen boundary and three seconds on mode entry.
footer_wait:
    lda footer_delay
    beq @move
    lda #FOOTER_SCREEN_QUARTERS
    sta footer_quarters
    dec footer_delay
    sec
    rts
@move:
    lda _footer_offset
    inc a
    and #3
    bne @ready
    dec footer_quarters
    bne @ready
    lda #FOOTER_SCREEN_DELAY
    sta footer_delay
@ready:
    clc
    rts

.segment "RODATA"
logo_config:
    .word 0,232,$5A00,$0700
    .byte $1F,$42          ; 64x8 logical pixels, doubled horizontally.
footer_configs:
_demo_footer:
    .byte 1,0
    .word 0,FOOTER_Y,CLASSIC_WIDTH,8,$3800,$0720
    .byte 1,0
    .word 0,FOOTER_Y,CLASSIC_WIDTH,8,$3800,$0720
