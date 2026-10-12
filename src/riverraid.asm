; Picocomputer port helpers, ca65 / cc65 ABI.
; Original game rules are generated separately from original/riverraid.asm.
.include "rp6502.inc"
.export _write_terrain_row, _write_hud_row, _reset_terrain
.export _write_jet_image
.export _hud_glyph
.export _write_hud_span
.import _hud_ink, _hud_column, _hud_length
.import _reset_tiles, _bank_wave, _bank_widths, _river_left, _river_right
.import _player_outer_left, _player_outer_right, _player_island_left, _player_island_right
.importzp ptr1
.import _row, _bank_half, _tile_mirror
.export _land_xy
.import _river1, _river2, _ring_top
.export _mask_land
.export _mask_player_land
.import _collision_mask, _collision_scale
.export _tia_color
.import _tia_palette
.export _demo_tick
.import _ready, _demo_wait
.export _present_frame
.import _terrain, _sprites, _footer_offset
.segment "CODE"

; Present the prepared world immediately after VSYNC, before the VGA reaches
; RIVER_TOP. Only Y changes in the tile config; dimensions/data stay fixed.
; 160 sprite bytes + Y take approximately 0.3 ms at 8 MHz. Never publish
; the scroll origin halfway through expensive terrain/collision processing.
_present_frame:
    lda #1
    sta RIA_STEP0
    lda #$04
    sta RIA_ADDR0
    lda #$02
    sta RIA_ADDR0+1
    lda _terrain+4
    sta RIA_RW0
    lda _terrain+5
    sta RIA_RW0
    lda #0
    sta RIA_ADDR0
    lda #$03
    sta RIA_ADDR0+1
    ldy #0
@sprite:
    lda _sprites,y
    sta RIA_RW0
    iny
    cpy #160
    bne @sprite
    lda #$62
    sta RIA_ADDR0
    lda #$02
    sta RIA_ADDR0+1
    sec
    lda #0
    sbc _footer_offset
    sta RIA_RW0
    lda #0
    sbc _footer_offset+1
    sta RIA_RW0
    rts

; A = elapsed 60 Hz VSYNCs, including missed frames. Called after input,
; before native rules and footer rendering, so both start on the same frame.
; ready: 1 waits 180 VSYNCs, 2 runs attract mode, 0 is the user game.
_demo_tick:
    tax
    lda _ready
    cmp #1
    beq @waiting
    lda $282
    lsr a
    bcc @done                 ; A user reset takes precedence over attract.
    lda $c6
    cmp #$ff
    bne @done                 ; Return to attract after game over / F2.
    beq @activate
@waiting:
    txa
    cmp _demo_wait
    bcs @activate
    eor #$ff
    sec
    adc _demo_wait            ; Saturating wait -= elapsed VSYNCs.
    sta _demo_wait
@done:
    rts
@activate:
    lda #2
    sta _ready
    lda #0
    sta _demo_wait
    sta $c6                   ; Native running mode: move enemies/terrain.
    lda #64
    sta $b5                   ; Normal river speed, without player rules.
    rts

; A = original color role, AX = RGB555. Mask/xor are native B&W/screensaver
; filters. The byte offset is the filtered code rounded down to even, avoiding
; C stack/index arithmetic when all palettes change during a terrain reset.
_tia_color:
    eor $85
    and $86
    and #$fe
    tay
    lda _tia_palette,y
    ldx _tia_palette+1,y
    rts

; AX = native jet bitmap pointer. Expand two bits to each 4bpp output byte.
; JET_IMAGE = XRAM_IMAGES + 11*IMAGE_BYTES = $9600 (src/xram.h).
_write_jet_image:
    sta ptr1
    stx ptr1+1
    lda #$00
    sta RIA_ADDR0
    lda #$96
    sta RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    ldy #18
@row:
    lda (ptr1),y
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    tax
    lda jet_pair_first,x
    sta RIA_RW0
    lda jet_pair_last,x
    sta RIA_RW0
    pla
    and #15
    tax
    lda jet_pair_first,x
    sta RIA_RW0
    lda jet_pair_last,x
    sta RIA_RW0
    dey
    bne @row
    lda #0
    .repeat 8
        sta RIA_RW0
    .endrepeat
    rts

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

; Upload the 40 tile IDs prepared by the sub-tile shoreline renderer.
_write_terrain_row:
    sta RIA_ADDR0
    stx RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    ldy #0
@copy:
    lda _row,y
    sta RIA_RW0
    iny
    cpy #20
    bne @copy
    ldy #19
@mirror:
    ldx _bank_half,y
    lda _tile_mirror,x
    sta RIA_RW0
    dey
    bpl @mirror
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

; Score and fuel occupy logical columns 40..87.
_write_hud_row:
    sta RIA_ADDR0
    stx RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    ldy #0
@copy:
    lda _row+40,y
    sta RIA_RW0
    iny
    cpy #48
    bne @copy
    rts

; Fast corridor reset. Fine water cuts follow the same bank outline as newly
; generated terrain. Four precomputed tiles cover the expanded edge and rim.
_reset_terrain:
    sta reset_color
    lda #<_reset_tiles
    sta ptr1
    lda #>_reset_tiles
    ldx reset_color
    cpx #2
    beq @base
    clc
    adc #1
@base:
    sta ptr1+1
    lda #0
    sta reset_phase
    sta reset_count
    sta _ring_top
    sta RIA_ADDR0
    lda #$08
    sta RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
@row:
    lda reset_color
    .repeat 14
        sta RIA_RW0
    .endrepeat
    ldy reset_phase
    lda (ptr1),y
    sta RIA_RW0
    iny
    lda (ptr1),y
    sta RIA_RW0
    lda #1
    .repeat 8
        sta RIA_RW0
    .endrepeat
    iny
    lda (ptr1),y
    sta RIA_RW0
    iny
    lda (ptr1),y
    sta RIA_RW0
    lda reset_color
    .repeat 14
        sta RIA_RW0
    .endrepeat
    inc reset_count
    lda reset_phase
    clc
    adc #4
    sta reset_phase
    lda reset_count
    cmp #160
    beq @masks
    jmp @row
@masks:
    ldx #0
@mask:
    lda #$ff
    sta _river1,x
    lda #$0f
    sta _river2,x
    txa
    and #63
    tay
    lda #64
    sec
    sbc _bank_wave,y
    sta _river_left,x
    txa
    lsr a
    lsr a
    lsr a
    tay
    lda _bank_widths,y
    sta reset_width
    lda _river_left,x
    sec
    sbc reset_width
    sta _player_outer_left,x
    tya
    clc
    adc #9
    cmp #24
    bcc @phase
    sbc #24
@phase:
    tay
    lda #160
    sec
    sbc _river_left,x
    clc
    adc _bank_widths,y
    sta _player_outer_right,x
    lda #80
    sta _river_right,x
    sta _player_island_left,x
    sta _player_island_right,x
    inx
    ; The visible corridor occupies rows 0..159. Each hidden ring row is
    ; initialized by draw_terrain_row before scrolling makes it visible.
    cpx #160
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
    ; Fine boundaries cut only native land pixels. The following PF test
    ; remains authoritative for original masks (including unusual patterns).
    lda land_x
    cmp _river_left,x
    bcc @native
    cmp _river_right,x
    bcc @water
@native:
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
; AX = player row origin, scale one. Brown rims are safe for the jet.
; Ground intervals come from the renderer, including independent bank widths
; on both halves and islands. Keep native PF masks authoritative for water.
_mask_player_land:
    sta mask_x
    stx mask_y
    txa
    clc
    adc _ring_top
    bcs @wrap
    cmp #192
    bcc @row
@wrap:
    sbc #192
@row:
    sta player_mask_row
    lda _collision_mask
    sta mask_bits
@next:
    asl mask_bits
    bcc @advance
    ldx player_mask_row
    lda mask_x
    cmp _player_outer_left,x
    bcc @native
    cmp _player_outer_right,x
    bcs @native
    cmp _player_island_left,x
    bcc @advance
    cmp _player_island_right,x
    bcs @advance
@native:
    ldx mask_y
    jsr _land_xy
    cmp #0
    bne @hit
@advance:
    inc mask_x
    lda mask_bits
    bne @next
    ldx #0
    rts
@hit:
    lda #1
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
jet_pair_first: .byte $00,$00,$00,$00,$01,$01,$01,$01,$10,$10,$10,$10,$11,$11,$11,$11
jet_pair_last:  .byte $00,$01,$10,$11,$00,$01,$10,$11,$00,$01,$10,$11,$00,$01,$10,$11
pf1_bits: .byte $80,$40,$20,$10,$08,$04,$02,$01
pf2_bits: .byte $01,$02,$04,$08,$10,$20,$40,$80
.segment "BSS"
land_x: .res 1
mask_x: .res 1
mask_y: .res 1
mask_bits: .res 1
player_mask_row: .res 1
reset_color: .res 1
reset_base: .res 1
reset_phase: .res 1
reset_count: .res 1
reset_width: .res 1
glyph_bits: .res 1
