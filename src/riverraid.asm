; Picocomputer port helpers, ca65 / cc65 ABI.
; Original game rules are generated separately from original/riverraid.asm.
.include "rp6502.inc"
.export _write_terrain_row, _write_hud_row, _reset_terrain
.export _hud_glyph
.export _write_hud_span
.import _hud_ink, _hud_column, _hud_length
.import _row
.export _land_xy
.import _river1, _river2, _ring_top
.export _mask_land
.import _collision_mask, _collision_scale
.segment "CODE"

; AX = (column<<8) | original glyph bits. Keep blank pixels from row's fill.
_hud_glyph:
    sta glyph_bits
    ldy #8
@pixel:
    asl glyph_bits
    bcc @blank
    lda _hud_ink
    sta _row,x
@blank:
    inx
    dey
    bne @pixel
    rts

; Upload only the 40 tile IDs that describe one complete terrain line.
_write_terrain_row:
    sta RIA_ADDR0
    stx RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    ldy #0
@copy:
    lda _row,y
    cmp #2
    beq @bank
    cmp #3
    bne @write
@bank:
    ; Brown stays inside the collidable land; water tile 1 is unchanged.
    ldx #0
    cpy #0
    beq @right
    lda _row-1,y
    cmp #1
    bne @right
    inx
@right:
    cpy #39
    beq @edge
    lda _row+1,y
    cmp #1
    bne @edge
    inx
    inx
@edge:
    txa
    beq @plain
    clc
    adc #6
    ldx _row,y
    cpx #2
    beq @write
    clc
    adc #3
    bne @write
@plain:
    lda _row,y
@write:
    sta RIA_RW0
    iny
    cpy #40
    bne @copy
    rts

; Upload a small side-panel field; bounds are supplied by the C renderer.
_write_hud_span:
    sta RIA_ADDR0
    stx RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    ldx _hud_column
    ldy _hud_length
@copy:
    lda _row,x
    sta RIA_RW0
    inx
    dey
    bne @copy
    rts

; Score, fuel and copyright occupy only logical columns 56..103.
_write_hud_row:
    sta RIA_ADDR0
    stx RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    ldy #0
@copy:
    lda _row+56,y
    sta RIA_RW0
    iny
    cpy #48
    bne @copy
    rts

; GameInit's uniform corridor, without a 160-line C redraw.
; AX ABI: A = land tile (2/3); initial water spans logical X 64..95.
_reset_terrain:
    sta reset_color
    clc
    adc #5
    cmp #7
    beq @edges
    lda #10
@edges:
    sta reset_left
    clc
    adc #1
    sta reset_right
    lda #0
    sta _ring_top
    sta RIA_ADDR0
    lda #$08
    sta RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    ldy #160
@row:
    lda reset_color
    .repeat 15
        sta RIA_RW0
    .endrepeat
    lda reset_right
    sta RIA_RW0
    lda #1
    .repeat 8
        sta RIA_RW0
    .endrepeat
    lda reset_left
    sta RIA_RW0
    lda reset_color
    .repeat 15
        sta RIA_RW0
    .endrepeat
    dey
    beq @masks
    jmp @row
@masks:
    ldx #0
@mask:
    lda #$ff
    sta _river1,x
    lda #$0f
    sta _river2,x
    inx
    cpx #192
    bne @mask
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
reset_color: .res 1
reset_left: .res 1
reset_right: .res 1
glyph_bits: .res 1
