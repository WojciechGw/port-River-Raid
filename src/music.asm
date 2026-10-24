; Shared music support in the unused reference-code copy ($C000..$CAFF).
; All original data tables from $CB00 upwards retain their exact addresses.
.include "rp6502.inc"
.macpack longbranch
.import boot_open, boot_close, boot_read_xram
.import _audio_backend, _ready, _paused
.import _gameover_active, _jingle_kind
.import _rr_Zero
.export music_enable, music_fallback_load, _music_effects
.export _music_synth, music_page
.if RIVER_PCM
.export music_probe, _music_pcm_probe, music_mix_pcm, music_fx_read
.endif
.segment "MUSIC"
.assert _rr_Zero = $CB00, lderror, "Review reclaimed reference code: first table moved"

; 0: OPL+PCM, 1: OPL with synthesized drums.
_music_synth: .byte 1-RIVER_PCM
music_page: .byte 1
.if RIVER_PCM
probe_address: .word 0
music_fx_read: .word 0
fx_sample: .byte 0
.endif
mix_source: .byte 0
mix_dest: .byte 0
mix_slot: .byte 0
mix_target: .byte 0

; A/X = initialized PCM header. Probe the firmware, not the chosen effects.
.if RIVER_PCM
music_probe:
    sta probe_address
    stx probe_address+1
    stz _music_synth
    jsr _music_pcm_probe
    bpl @done
    inc _music_synth
@done:
    rts
; Kept as a separate call so emulator fixtures can model old firmware's -1.
_music_pcm_probe:
    lda #0
    sta RIA_XSTACK
    lda #1
    sta RIA_XSTACK
    lda #2
    sta RIA_XSTACK
    lda probe_address+1
    sta RIA_XSTACK
    lda probe_address
    sta RIA_XSTACK
    lda #RIA_OP_XREG
    sta RIA_OP
    jmp RIA_SPIN
.endif

music_enable:
    lda #0
    sta RIA_XSTACK
    lda #1
    sta RIA_XSTACK
    lda #1
    sta RIA_XSTACK
    lda music_page
    sta RIA_XSTACK
    lda #0
    sta RIA_XSTACK
    lda #RIA_OP_XREG
    sta RIA_OP
    jmp RIA_SPIN

; A = intro, flight, gameover, victory. Caller owns/saves boot_fd.
music_fallback_load:
    tay
    phy
    lda music_paths_lo,y
    ldx music_paths_hi,y
    jsr boot_open
    ply
    lda #$f9
    sta RIA_XSTACK
    lda #0
    sta RIA_XSTACK
    lda music_sizes_hi,y
    sta RIA_XSTACK
    tax
    lda music_sizes_lo,y
    sta RIA_XSTACK
    jsr boot_read_xram
    jmp boot_close

; Music PCM at $CA08; procedural effects keep their independent 8 kHz ring
; at $C008. Upsample each effects sample twice, at half gain, before publish.
; A = newly filled music ring page (0..3).
.if RIVER_PCM
music_mix_pcm:
    ldx _audio_backend
    cpx #3
    jne @done
    ldx _jingle_kind
    cpx #2
    jne @done
    ldx _ready
    jne @done
    clc
    adc #$ca
    sta RIA_ADDR0+1
    lda #8
    sta RIA_ADDR0
    stz RIA_STEP0
    lda music_fx_read
    clc
    adc #8
    sta RIA_ADDR1
    lda music_fx_read+1
    adc #$c0
    sta RIA_ADDR1+1
    lda #1
    sta RIA_STEP1
    ldy #0
@sample:
    tya
    and #1
    bne @reuse
    lda RIA_RW1
    cmp #$80
    ror a
    sta fx_sample
    lda RIA_ADDR1+1
    cmp #$c8
    bne @reuse
    lda RIA_ADDR1
    cmp #8
    bne @reuse
    lda #$c0
    sta RIA_ADDR1+1
@reuse:
    lda RIA_RW0
    clc
    adc fx_sample
    sta RIA_RW0
    inc RIA_ADDR0
    bne :+
    inc RIA_ADDR0+1
:
    iny
    bne @sample
    lda music_fx_read
    clc
    adc #128
    sta music_fx_read
    lda music_fx_read+1
    adc #0
    and #7
    sta music_fx_read+1
    lda #6
    sta RIA_ADDR0
    lda #$c0
    sta RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    lda music_fx_read
    sta RIA_RW0
    lda music_fx_read+1
    sta RIA_RW0
@done:
    rts
.endif

; Effects run normally into their original mirrors. Merge only the voices
; reserved by the three-part flight arrangement; one-shots own all audio.
_music_effects:
    lda _gameover_active
    jeq @done
    lda _jingle_kind
    cmp #2
    jne @done
    lda _ready
    ora _paused
    jne @done
    lda _audio_backend
    cmp #2
    beq @opl
@done:
    rts
@opl:
    stz RIA_STEP0
    stz RIA_STEP1
    lda #$c0
    sta RIA_ADDR1+1
    lda #$c9
    sta RIA_ADDR0+1
.if RIVER_PCM
    lda _music_synth
    bne @compact
    ldx #0
    ldy #3
    jsr opl_copy_voice
    ldx #4
    ldy #4
    jsr opl_copy_voice
    bra @tones
@compact:
.endif
    ldx #0
    lda #$b4
    sta RIA_ADDR1
    lda RIA_RW1
    and #32
    ; Preserve the key-on test flags: LDX #0 here would always pick engine.
    beq :+
    ldx #4
:
    ldy #6
    jsr opl_copy_voice
@tones:
    ldx #7
    ldy #7
    jsr opl_copy_voice
    ldx #8
    ldy #8
    jsr opl_copy_voice
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    rts

opl_copy_voice:
    stx mix_source
    sty mix_dest
    lda slots,x
    sta mix_slot
    lda slots,y
    sta mix_target
    ldx #9
@operator:
    lda operator_regs,x
    clc
    adc mix_slot
    sta RIA_ADDR1
    lda operator_regs,x
    clc
    adc mix_target
    sta RIA_ADDR0
    lda RIA_RW1
    sta RIA_RW0
    dex
    bpl @operator
    ldx #2
@channel:
    lda channel_regs,x
    clc
    adc mix_source
    sta RIA_ADDR1
    lda channel_regs,x
    clc
    adc mix_dest
    sta RIA_ADDR0
    lda RIA_RW1
    cmp RIA_RW0
    beq :+
    sta RIA_RW0
:
    dex
    bpl @channel
    rts
operator_regs: .byte $20,$23,$40,$43,$60,$63,$80,$83,$e0,$e3
channel_regs: .byte $b0,$a0,$c0
slots: .byte 0,1,2,8,9,10,16,17,18

.include "music.inc"
.export MUSIC_SCORE_BYTES
music_paths_lo: .lobytes intro_opl,flight_opl,over_opl,win_opl
music_paths_hi: .hibytes intro_opl,flight_opl,over_opl,win_opl
intro_opl: .asciiz "ROM:intro-opl.bin"
flight_opl: .asciiz "ROM:flight-opl.bin"
over_opl: .asciiz "ROM:gameover-opl.bin"
win_opl: .asciiz "ROM:victory-opl.bin"
