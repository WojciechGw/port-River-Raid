; Picocomputer port helpers, ca65 / cc65 ABI.
; Original game rules are generated separately from original/riverraid.asm.
.include "rp6502.inc"
.export _write_row
.import _row
.export _land_xy
.import _river1, _river2, _ring_top
.export _mask_land
.import _collision_mask, _collision_scale
.segment "CODE"

; void __fastcall__ write_row(unsigned xram_address)
; One 320-pixel 4bpp row: 160 bytes. Each logical Atari pixel is doubled.
_write_row:
    sta RIA_ADDR0
    stx RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    ldy #0
@copy:
    lda _row,y
    sta RIA_RW0
    iny
    cpy #160
    bne @copy
    rts

; Fast pixel-to-playfield collision: AX = y*256+x, return boolean A/X=0.
; PF0 covers 16 pixels; PF1 MSB first, PF2 LSB first, right half mirrored.
_land_xy:
    cmp #160
    bcs @water
    cmp #80
    bcc @left
    eor #255
    clc
    adc #160
@left:
    cmp #16
    bcc @land
    sta land_x
    txa
    clc
    adc _ring_top
    bcs @wrap
    cmp #192
    bcc @row
@wrap:
    sbc #192
@row:
    tax
    lda land_x
    cmp #48
    bcs @pf2
    sec
    sbc #16
    lsr a
    lsr a
    tay
    lda _river1,x
    and pf1_bits,y
    ldx #0
    rts
@pf2:
    sbc #48
    lsr a
    lsr a
    tay
    lda _river2,x
    and pf2_bits,y
    ldx #0
    rts
@land:
    lda #1
    ldx #0
    rts
@water:
    lda #0
    ldx #0
    rts
; AX = row origin. Expand each opaque pixel for double/quad sized sprites.
_mask_land:
    sta mask_x
    stx mask_y
    lda _collision_mask
    sta mask_bits
@next:
    asl mask_bits
    bcc @advance
    lda mask_x
    ldx mask_y
    jsr _land_xy
    cmp #0
    bne @hit
    lda _collision_scale
    cmp #1
    beq @advance
    clc
    adc mask_x
    sec
    sbc #1
    ldx mask_y
    jsr _land_xy
    cmp #0
    bne @hit
@advance:
    lda mask_x
    clc
    adc _collision_scale
    sta mask_x
    lda mask_bits
    bne @next
    ldx #0
    rts
@hit:
    lda #1
    ldx #0
    rts
.segment "RODATA"
pf1_bits: .byte $80,$40,$20,$10,$08,$04,$02,$01
pf2_bits: .byte $01,$02,$04,$08,$10,$20,$40,$80
.segment "BSS"
land_x: .res 1
mask_x: .res 1
mask_y: .res 1
mask_bits: .res 1
