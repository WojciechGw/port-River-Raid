; Swap only player-owned registers. Terrain, RNG, frame and sound stay shared.
.include "rp6502.inc"
.export _duo_load, _duo_save, _hud_clear
.importzp ptr1
.segment "CODE"
_duo_load:
    sta ptr1
    stx ptr1+1
    ldy #18
@loop:
    ldx registers,y
    lda (ptr1),y
    sta $00,x
    dey
    bpl @loop
    rts
_duo_save:
    sta ptr1
    stx ptr1+1
    ldy #18
@loop:
    ldx registers,y
    lda $00,x
    sta (ptr1),y
    dey
    bpl @loop
    rts
.segment "RODATA"
registers:
    .byte $b2,$b3,$b4,$b5,$b7,$b8,$ba,$bb,$c0,$84,$87,$e0,$f5
    .byte $cd,$cf,$d1,$d3,$d5,$d7
.segment "CODE"
; Clear exactly the 160x37 logical HUD panel; leave the footer intact.
_hud_clear:
    lda #0
    sta RIA_ADDR0
    lda #$a0
    sta RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    lda #$aa
    ldx #23
@page:
    ldy #32
@eight:
    .repeat 8
    sta RIA_RW0
    .endrepeat
    dey
    bne @eight
    dex
    bne @page
    ldy #4
@tail:
    .repeat 8
    sta RIA_RW0
    .endrepeat
    dey
    bne @tail
    rts
