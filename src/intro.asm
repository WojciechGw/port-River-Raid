; OPL2 cover music. This overlay occupies reset_tiles only while a static
; screen is shown. Gameplay audio, its register page and RNG are untouched.
.include "rp6502.inc"
.macpack longbranch
.import boot_scene
.export intro_init, intro_tick, intro_stop
.export _intro_active := intro_active, _intro_cursor := intro_cursor
.segment "INTRO"
INTRO_OPL = $0100
INTRO_SCORE = $F100

intro_init:
    lda boot_scene
    bne @done
    lda #<INTRO_OPL
    sta RIA_ADDR0
    lda #>INTRO_OPL
    sta RIA_ADDR0+1
    ldy #0
    tya
@clear:
    sta RIA_RW0
    iny
    bne @clear
    xreg 0,1,1,INTRO_OPL
    bmi @done                 ; A machine without OPL still shows the cover.
    lda #1
    sta intro_active
    sta intro_wait
    jsr intro_rewind
@done:
    rts

intro_rewind:
    lda #<INTRO_SCORE
    sta intro_cursor
    lda #>INTRO_SCORE
    sta intro_cursor+1
    rts

intro_tick:
    lda intro_active
    jeq @done
    dec intro_wait
    jne @done
    lda #0
    sta RIA_STEP0
    lda #>INTRO_OPL
    sta RIA_ADDR0+1
@cursor:
    lda intro_cursor
    sta RIA_ADDR1
    lda intro_cursor+1
    sta RIA_ADDR1+1
@command:
    lda RIA_RW1
    cmp #$ff
    beq @loop
    cmp #$80
    bcs @delay
    cmp #$20
    beq @register
    tax
    and #15
    ora #$b0
    sta RIA_ADDR0
    lda #0
    sta RIA_RW0                ; Release old note before retriggering.
    cpx #16
    bcs @command              ; $10..$18: note off.
    lda RIA_RW1               ; $00..$08: channel, FNUM, block/key, level.
    sta intro_low
    lda RIA_RW1
    sta intro_high
    lda intro_slots,x
    clc
    adc #$43
    sta RIA_ADDR0
    lda RIA_RW1
    sta RIA_RW0
    txa
    ora #$a0
    sta RIA_ADDR0
    lda intro_low
    sta RIA_RW0
    txa
    ora #$b0
    sta RIA_ADDR0
    lda intro_high
    sta RIA_RW0
    jmp @command
@register:                    ; $20: literal register/value (instruments).
    lda RIA_RW1
    sta RIA_ADDR0
    lda RIA_RW1
    sta RIA_RW0
    jmp @command
@loop:
    jsr intro_rewind
    jmp @cursor
@delay:                       ; $80..$FE: wait 1..127 display frames.
    and #$7f
    clc
    adc #1
    sta intro_wait
    lda RIA_ADDR1
    sta intro_cursor
    lda RIA_ADDR1+1
    sta intro_cursor+1
    lda #1
    sta RIA_STEP0
@done:
    rts

intro_stop:
    lda intro_active
    beq @done
    lda #0
    sta intro_active
    xreg 0,1,1,$ffff
@done:
    rts

intro_slots: .byte 0,1,2,8,9,10,16,17,18
intro_active: .byte 0
intro_wait: .byte 1
intro_cursor: .word INTRO_SCORE
intro_low: .byte 0
intro_high: .byte 0

.segment "INTRO_SCORE"
.incbin "intro-score.bin"
