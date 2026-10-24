; Full-screen OPL2 + PCM. Helpers borrow reset_tiles; the player borrows
; derived graphics tables rebuilt before gameplay and after F1.
.include "rp6502.inc"
.macpack longbranch
.import boot_scene, boot_help, boot_level, boot_open, boot_close, boot_read_xram, boot_fd
.import _audio_muted
.import music_enable, music_page
.if RIVER_PCM
.import music_probe, music_fallback_load, _music_synth
.endif
.export intro_levels, intro_gain
.import _sprites, _tanks, __INTRO_SCORE_SIZE__
.include "intro-score.inc"
.export intro_init, intro_tick, intro_stop, intro_load
.export _intro_active := intro_active, _intro_cursor := intro_cursor
.export _intro_gain := intro_gain
.if RIVER_PCM
.export _intro_pcm_gain := fade_pcm_gain
.endif
.segment "INTRO"
INTRO_OPL = $0100
INTRO_SCORE = $F900

intro_load:
    lda boot_scene
    cmp #2
    bne @load
    lda boot_help
    beq @done              ; Initial manual continues the cover's stream.
@load:
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
    lda _audio_muted
    and #1                   ; Bit 0 mutes music; bit 1 only mutes effects.
    ora intro_active
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
    lda boot_scene
    beq @done              ; Keep playing across cover -> initial manual.
    lda intro_active
    beq @done
    jmp player_stop
@done:
    rts

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
.if RIVER_PCM
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
    lda #<INTRO_PCM
    ldx #>INTRO_PCM
    jsr music_probe
.endif
    lda #>INTRO_OPL
    sta music_page
    jsr music_enable
    bmi @done
    lda #1
    sta intro_active
.if RIVER_PCM
    jsr drum_enter
    lda _music_synth
    beq @drums
    lda #0
    jsr music_fallback_load
    bra @score
@drums:
    jsr drum_open
    inc drum_enabled
@score:
    jsr drum_leave
.endif
    jsr intro_rewind
    jsr intro_sequence
.if RIVER_PCM
    lda drum_enabled
    beq @done
    jsr drum_fill
.endif
@done:
    rts

player_tick:
.if RIVER_PCM
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
.endif
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
    jmp intro_fade

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
    sta intro_levels,x
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
.if RIVER_PCM
    lda drum_enabled
    beq @close
    xreg 0,1,2,$ffff
@close:
    jsr drum_enter
    jsr boot_close
    jmp drum_leave
.else
    rts
.endif

; The palette streamer owns boot_fd between ticks. Borrow the checked ROM
; helpers with a separate descriptor so fading cannot seek the drum stream.
.if RIVER_PCM
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
    jsr drum_fade
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
.endif

intro_slots: .byte 0,1,2,8,9,10,16,17,18
intro_active: .byte 0
intro_levels: .res 9,0
intro_gain: .byte 63
intro_wait: .byte 1
intro_cursor: .word INTRO_SCORE
intro_low: .byte 0
intro_high: .byte 0

.if RIVER_PCM
drum_header: .byte 0,0,3,10,<INTRO_RATE,>INTRO_RATE,0,0
drum_path: .asciiz "ROM:intro-drums.pcm"
drum_enabled: .byte 0
drum_fd: .word $ffff
drum_saved: .word 0
drum_pages: .word 0
drum_read: .word 0
drum_previous: .word 0
drum_write: .byte 0
.endif
intro_phase: .word 0
intro_delta: .word 0
fallback_fraction: .byte 3

.segment "INTRO"
; Fade both manual exits and the outro; cover -> initial manual keeps playing.
; OPL carrier attenuation follows each of the
; 64 fade levels; PCM pages are scaled before they are published to PIX.
intro_fade:
    lda boot_scene
    beq @done
    lda #$b0
    sta RIA_ADDR0
    stz RIA_ADDR0+1
    lda RIA_RW0
    cmp #3
    bne @done
    lda boot_level
    sta intro_gain
    eor #63
    sta fade_attenuation
    lda #>INTRO_OPL
    sta RIA_ADDR0+1
    stz RIA_STEP0
    ldx #8
@channel:
    lda intro_slots,x
    clc
    adc #$43
    sta RIA_ADDR0
    lda intro_levels,x
    clc
    adc fade_attenuation
    cmp #63
    bcc @write
    lda #63
@write:
    sta RIA_RW0
    dex
    bpl @channel
    lda #1
    sta RIA_STEP0
@done:
    rts

fade_attenuation: .byte 0
.if RIVER_PCM
drum_fade:
    lda intro_gain
    sta fade_pcm_gain
    cmp #63
    beq @done
    lda drum_write
    clc
    adc #>INTRO_RING
    sta RIA_ADDR0+1
    sta RIA_ADDR1+1
    stz RIA_ADDR0
    stz RIA_ADDR1
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    ldy #0
@sample:
    lda RIA_RW0
    sta fade_value
    lda #0
    bit fade_value
    bpl @positive
    dec a
@positive:
    sta fade_value+1
    stz fade_product
    stz fade_product+1
    lda intro_gain
    sta fade_factor
    ldx #6
@multiply:
    lsr fade_factor
    bcc @shift
    clc
    lda fade_product
    adc fade_value
    sta fade_product
    lda fade_product+1
    adc fade_value+1
    sta fade_product+1
@shift:
    asl fade_value
    rol fade_value+1
    dex
    bne @multiply
    ldx #6
@divide:
    lsr fade_product+1
    ror fade_product
    dex
    bne @divide
    lda fade_product
    sta RIA_RW1
    iny
    bne @sample
@done:
    rts
fade_pcm_gain: .byte 63
fade_factor: .byte 0
fade_value: .word 0
fade_product: .word 0
.endif

.segment "INTRO_SCORE"
.if RIVER_PCM
.incbin "intro-score.bin"
.else
.incbin "intro-opl.bin"
.endif
