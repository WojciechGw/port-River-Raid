; Cover-only OPL2 + PCM. Shared helpers borrow reset_tiles; the startup-only
; player borrows derived graphics tables rebuilt before gameplay.
.include "rp6502.inc"
.macpack longbranch
.import boot_scene, boot_open, boot_close, boot_read_xram, boot_fd
.import _sprites, _tanks, __INTRO_SCORE_SIZE__
.include "intro-score.inc"
.export intro_init, intro_tick, intro_stop, intro_load
.export _intro_active := intro_active, _intro_cursor := intro_cursor
.segment "INTRO"
INTRO_OPL = $0100
INTRO_SCORE = $F100

intro_load:
    lda boot_scene
    bne @done
    xreg_values $0600, 1024
    lda #0
    ldx #4
    jsr boot_read_xram
    lda #0
    sta RIA_ADDR0
    lda #6
    sta RIA_ADDR0+1
    ldy #0
@copy:
    lda RIA_RW0
    sta _sprites,y
    iny
    bne @copy
    ldy #0
@copy1:
    lda RIA_RW0
    sta _sprites+256,y
    iny
    bne @copy1
@copy2:
    lda RIA_RW0
    sta _sprites+512,y
    iny
    bne @copy2
@copy3:
    lda RIA_RW0
    sta _sprites+768,y
    iny
    bne @copy3
    xreg_values INTRO_SCORE, __INTRO_SCORE_SIZE__
    lda #<__INTRO_SCORE_SIZE__
    ldx #>__INTRO_SCORE_SIZE__
    jsr boot_read_xram
@done:
    rts

intro_init:
    lda boot_scene
    bne @done
    jmp player_init
@done:
    rts
intro_tick:
    lda intro_active
    beq @done
    jmp player_tick
@done:
    rts
intro_stop:
    lda intro_active
    beq @done
    jmp player_stop
@done:
    rts
intro_active: .byte 0

.segment "INTRO_PLAYER"
.assert _sprites+1024 <= _tanks, lderror, "Intro player overwrites persistent tank state"
INTRO_PCM = $09F8
INTRO_RING = $0A00

player_init:
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
    bmi @done
    lda #1
    sta intro_active
    jsr intro_rewind
    jsr intro_sequence
    jsr drum_enter
    jsr drum_open
    jsr drum_leave
    lda #<INTRO_PCM
    sta RIA_ADDR0
    lda #>INTRO_PCM
    sta RIA_ADDR0+1
    ldy #0
@header:
    lda drum_header,y
    sta RIA_RW0
    iny
    cpy #8
    bne @header
    jsr drum_fill
    xreg 0,1,2,INTRO_PCM
    bmi @done
    inc drum_enabled
@done:
    rts

player_tick:
    lda drum_enabled
    beq @fallback
    lda #0
    sta RIA_STEP1
    lda #>INTRO_PCM
    sta RIA_ADDR1+1
@read:
    lda #<(INTRO_PCM+7)
    sta RIA_ADDR1
    lda RIA_RW1
    sta drum_read+1
    dec RIA_ADDR1
    lda RIA_RW1
    sta drum_read
    inc RIA_ADDR1
    lda RIA_RW1
    cmp drum_read+1
    bne @read
    sec
    lda drum_read
    sbc drum_previous
    sta intro_delta
    lda drum_read+1
    sbc drum_previous+1
    and #3
    sta intro_delta+1
    lda drum_read
    sta drum_previous
    lda drum_read+1
    sta drum_previous+1
    jsr drum_fill
    bra @advance
@fallback:
    ; 266, 267, 267 samples per display frame = exactly 16000 Hz.
    lda #11
    dec fallback_fraction
    bne @fraction
    lda #3
    sta fallback_fraction
    lda #10
@fraction:
    sta intro_delta
    lda #1
    sta intro_delta+1
@advance:
    clc
    lda intro_phase
    adc intro_delta
    sta intro_phase
    lda intro_phase+1
    adc intro_delta+1
    sta intro_phase+1
    lda #1
    sta RIA_STEP1
    lda intro_phase
    cmp #<INTRO_STEP_SAMPLES
    lda intro_phase+1
    sbc #>INTRO_STEP_SAMPLES
    bcc @done
    sec
    lda intro_phase
    sbc #<INTRO_STEP_SAMPLES
    sta intro_phase
    lda intro_phase+1
    sbc #>INTRO_STEP_SAMPLES
    sta intro_phase+1
    jsr intro_sequence
@done:
    rts

intro_rewind:
    lda #<INTRO_SCORE
    sta intro_cursor
    lda #>INTRO_SCORE
    sta intro_cursor+1
    rts

intro_sequence:
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
    cpx #16
    bcc @note
    lda #0
    sta RIA_RW0                ; $10..$18: legacy note off.
    bra @command
@note:
    lda RIA_RW1               ; $00..$08: channel, FNUM, block/key, level.
    sta intro_low
    lda RIA_RW1
    sta intro_high
    and #$df
    sta RIA_RW0                ; Retrigger with the new note's pitch, like the source.
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
@delay:                       ; $80..$FE: wait 1..127 sixteenth-note steps.
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

player_stop:
    stz intro_active
    xreg 0,1,1,$ffff
    lda drum_enabled
    beq @close
    xreg 0,1,2,$ffff
@close:
    jsr drum_enter
    jsr boot_close
    jmp drum_leave

; The palette streamer owns boot_fd between ticks. Borrow the checked ROM
; helpers with a separate descriptor so fading cannot seek the drum stream.
drum_enter:
    lda boot_fd
    sta drum_saved
    lda boot_fd+1
    sta drum_saved+1
    lda drum_fd
    sta boot_fd
    lda drum_fd+1
    sta boot_fd+1
    rts
drum_leave:
    lda boot_fd
    sta drum_fd
    lda boot_fd+1
    sta drum_fd+1
    lda drum_saved
    sta boot_fd
    lda drum_saved+1
    sta boot_fd+1
    rts
drum_open:
    lda #<drum_path
    ldx #>drum_path
    jsr boot_open
    lda #<INTRO_DRUM_PAGES
    sta drum_pages
    lda #>INTRO_DRUM_PAGES
    sta drum_pages+1
    rts
drum_fill:
    jsr drum_enter
@next:
    lda drum_write
    sec
    sbc drum_read+1
    and #3
    cmp #3
    bcs @done
    lda drum_pages
    ora drum_pages+1
    bne @copy
    jsr boot_close
    jsr drum_open
@copy:
    ; READ_XRAM(address,256) writes a complete page before publishing it.
    lda drum_write
    clc
    adc #>INTRO_RING
    sta RIA_XSTACK
    lda #0
    sta RIA_XSTACK
    lda #1
    sta RIA_XSTACK
    lda #0
    sta RIA_XSTACK
    ldx #1
    jsr boot_read_xram
    lda drum_pages
    bne @decrement
    dec drum_pages+1
@decrement:
    dec drum_pages
    inc drum_write
    lda drum_write
    and #3
    sta drum_write
    lda #<(INTRO_PCM+1)
    sta RIA_ADDR0
    lda #>INTRO_PCM
    sta RIA_ADDR0+1
    lda drum_write
    sta RIA_RW0
    bra @next
@done:
    jmp drum_leave

intro_slots: .byte 0,1,2,8,9,10,16,17,18
intro_wait: .byte 1
intro_cursor: .word INTRO_SCORE
intro_low: .byte 0
intro_high: .byte 0

drum_header: .byte 0,0,3,10,<INTRO_RATE,>INTRO_RATE,0,0
drum_path: .asciiz "ROM:intro-drums.pcm"
drum_enabled: .byte 0
drum_fd: .word $ffff
drum_saved: .word 0
drum_pages: .word 0
drum_read: .word 0
drum_previous: .word 0
drum_write: .byte 0
intro_phase: .word 0
intro_delta: .word 0
fallback_fraction: .byte 3

.segment "INTRO_SCORE"
.incbin "intro-score.bin"
