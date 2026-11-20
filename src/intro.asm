; Full-screen OPL2 + PCM. Helpers borrow reset_tiles; the player borrows
; derived graphics tables rebuilt before gameplay and after F1.
.include "rp6502.inc"
.macpack longbranch
.import boot_scene, boot_help, boot_level, boot_open, boot_close, boot_read_xram, boot_fd
.import _audio_muted
.import music_enable, music_page
.if RIVER_PCM
.import music_probe, music_fallback_load, _music_synth
.import pcm_dev_queued, pcm_dev_write, pcm_dev_consumed, pcm_dev_flush, PCM_BUF_LIMIT
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
INTRO_RING = $0A00           ; Four staging pages queued to the PCM: device.
.if RIVER_PCM
.assert INTRO_RATE = 16000, error, "The PCM: device stream is opened at 16 kHz"
.assert 4*256 <= PCM_BUF_LIMIT, lderror, "Intro queue exceeds the PCM buffer budget"
.endif

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
    ; Samples the device played since the last frame clock the sequencer.
    jsr pcm_dev_consumed
    sta intro_delta
    stx intro_delta+1
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
    jsr pcm_dev_flush
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
    jsr pcm_dev_queued        ; Keep three pages queued ahead of playback.
    cpx #3
    bcs @done
    lda drum_pages
    ora drum_pages+1
    bne @copy
    jsr boot_close
    jsr drum_open
@copy:
    ; READ_XRAM(address,256) fills a complete page before it is queued.
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
    lda drum_write
    clc
    adc #>INTRO_RING
    tax
    lda #<INTRO_RING
    ldy #1
    jsr pcm_dev_write
    lda drum_pages
    bne @decrement
    dec drum_pages+1
@decrement:
    dec drum_pages
    inc drum_write
    lda drum_write
    and #3
    sta drum_write
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
drum_path: .asciiz "ROM:intro-drums.pcm"
drum_enabled: .byte 0
drum_fd: .word $ffff
drum_saved: .word 0
drum_pages: .word 0
drum_write: .byte 0
; Reloaded with the player, so a stale table is never trusted.
fade_table_gain: .byte $ff
fade_table: .res 256
.endif
intro_phase: .word 0
intro_delta: .word 0
fallback_fraction: .byte 3

.segment "INTRO"
; Fade both manual exits and the outro; cover -> initial manual keeps playing.
; OPL carrier attenuation follows each of the
; 64 fade levels; PCM pages are scaled before they are queued.
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
    cmp fade_table_gain
    beq @scale
    ; Rebuild the unsigned gain table once per fade level. Accumulate
    ; (u-128)*4*gain from u=0: its high byte is floor((u-128)*gain/64),
    ; exactly the former per-sample multiply, at a fraction of its cost.
    sta fade_table_gain
    asl a
    asl a
    sta fade_step
    lda intro_gain
    asl a
    eor #$ff
    inc a
    sta fade_acc+1            ; -512*gain
    stz fade_acc
    ldx #0
@table:
    lda fade_acc+1
    eor #$80
    sta fade_table,x
    clc
    lda fade_acc
    adc fade_step
    sta fade_acc
    bcc :+
    inc fade_acc+1
:
    inx
    bne @table
@scale:
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
    ldx RIA_RW0
    lda fade_table,x
    sta RIA_RW1
    iny
    bne @sample
@done:
    rts
fade_pcm_gain: .byte 63
fade_step: .byte 0
fade_acc: .word 0
.endif

.segment "INTRO_SCORE"
.if RIVER_PCM
.incbin "intro-score.bin"
.else
.incbin "intro-opl.bin"
.endif
