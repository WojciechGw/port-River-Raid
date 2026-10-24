.include "rp6502.inc"
.export _game_fade_capture, _game_fade_publish
.export _game_fade_read
.segment "CODE"

; Exactly two portal reads; avoid cc65 reloading a volatile low byte while
; assembling a 16-bit C expression, which advances the XRAM stream twice.
_game_fade_read:
    lda RIA_RW0
    ldx RIA_RW0
    rts

; Five palette ranges, 288 RGB555 words. No sprite/config/bitmap bytes change.
_game_fade_capture:
    lda #$00
    sta RIA_ADDR1
    lda #$d0
    sta RIA_ADDR1+1
    ldx #0
@range:
    jsr fade_address
@copy:
    lda RIA_RW0
    sta RIA_RW1
    lda RIA_RW0
    sta RIA_RW1
    dey
    bne @copy
    inx
    cpx #5
    bne @range
    rts

; About 0.8 ms at 8 MHz: complete before the first playfield scanline (Y=21).
_game_fade_publish:
    lda #$00
    sta RIA_ADDR1
    lda #$d3
    sta RIA_ADDR1+1
    ldx #0
@range:
    jsr fade_address
@copy:
    lda RIA_RW1
    sta RIA_RW0
    lda RIA_RW1
    sta RIA_RW0
    dey
    bne @copy
    inx
    cpx #5
    bne @range
    rts

fade_address:
    lda fade_low,x
    sta RIA_ADDR0
    lda fade_high,x
    sta RIA_ADDR0+1
    ldy fade_words,x
    rts

.segment "RODATA"
fade_low:   .byte $00,$00,$00,$20,$80
fade_high:  .byte $01,$04,$07,$07,$bf
fade_words: .byte 16,0,7,7,2
