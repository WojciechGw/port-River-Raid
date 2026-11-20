; Shared music support in the unused reference-code copy ($C000..$CAFF).
; All original data tables from $CB00 upwards retain their exact addresses.
.include "rp6502.inc"
.macpack longbranch
.import boot_open, boot_close, boot_read_xram
.import _audio_backend, _ready, _paused
.import _demo_splash_out, _demo_splash_done
.import _gameover_active, _jingle_kind
.import _rr_Zero
.export music_enable, music_fallback_load, _music_effects
.export _music_synth, music_page
.if RIVER_PCM
.export music_probe, _music_pcm_probe, music_mix_pcm, music_fx_read
.export _music_fx_read := music_fx_read
.export _pcm_dev_start, pcm_dev_level, pcm_dev_write, pcm_dev_consumed, pcm_dev_queued
.export _pcm_dev_flush := pcm_dev_flush, pcm_dev_flush, _pcm_dev_level := pcm_dev_level
.export _pcm_fd, _pcm_owner, _pcm_written, _pcm_consumed := pcm_consumed
.endif
.segment "MUSIC"
.assert _rr_Zero = $CB00, lderror, "Review reclaimed reference code: first table moved"

; 0: OPL+PCM, 1: OPL with synthesized drums.
_music_synth: .byte 1-RIVER_PCM
music_page: .byte 1
.if RIVER_PCM
music_fx_read: .word 0
; The firmware's PCM: device (RIA 0.43+). One stream is opened on first use
; and kept until exit: 16 kHz, 8-bit unsigned, mono. Its owner feeds it:
; 0 none, 1 procedural effects, 2 music/jingles/intro (effects mixed in).
_pcm_fd: .byte $ff
_pcm_owner: .byte 0
; 24-bit counts since the last flush: bytes written, and written minus the
; queued level at the previous clock. Their difference paces the sequencers
; like a DAC clock; 24 bits keep both absolute for over 17 minutes.
_pcm_written: .res 3
pcm_consumed: .res 3
pcm_total: .res 3
.endif
mix_source: .byte 0
mix_dest: .byte 0
mix_slot: .byte 0
mix_target: .byte 0

.if RIVER_PCM
; The firmware buffers 8192 bytes; producers treat it as half that size.
PCM_BUF_LIMIT = 4096
.export PCM_BUF_LIMIT

; Probe the firmware, not the chosen effects: music owns the stream.
; _music_synth = 0 with PCM drums, 1 with synthesized OPL drums.
music_probe:
    lda #2
    jsr _pcm_dev_start
    eor #1
    sta _music_synth
    rts

; A = owner. Open the device once, empty it and hand it to the owner.
; Returns A = 1 when PCM plays, 0 when the firmware has no PCM: device.
_pcm_dev_start:
    pha
    lda _pcm_fd
    bpl @ready
    jsr _music_pcm_probe
    cpx #0
    bne @fail
    sta _pcm_fd
@ready:
    jsr pcm_dev_flush
    pla
    sta _pcm_owner
    lda #1
    ldx #0
    rts
@fail:
    pla
    lda #0
    tax
    rts

; Kept as a separate call so emulator fixtures can model old firmware's -1.
_music_pcm_probe:
    ldy #pcm_path_end-pcm_path-1
@push:
    ; Strings go on XSTACK reversed, including their terminating zero.
    lda pcm_path,y
    sta RIA_XSTACK
    dey
    bpl @push
    lda #2                  ; O_WRONLY
    sta RIA_A
    stz RIA_X
    lda #RIA_OP_OPEN
    sta RIA_OP
    jmp RIA_SPIN
pcm_path: .asciiz "PCM:16000,8,1"
pcm_path_end:

; Drop everything queued and restart the sample count. No owner remains.
pcm_dev_flush:
    stz _pcm_owner
    ldx #2
@clear:
    stz _pcm_written,x
    stz pcm_consumed,x
    dex
    bpl @clear
    ldx #2                  ; cc65 SEEK_SET empties the buffer
    bra pcm_dev_seek
; A/X = bytes still queued for playback.
pcm_dev_level:
    ldx #0                  ; cc65 SEEK_CUR
pcm_dev_seek:
    lda _pcm_fd
    bmi @closed
    ldy #4
@offset:
    stz RIA_XSTACK          ; 32-bit offset 0, the only seek it allows
    dey
    bne @offset
    stx RIA_XSTACK
    sta RIA_A
    stz RIA_X
    lda #RIA_OP_LSEEK
    sta RIA_OP
    jmp RIA_SPIN
@closed:
    lda #0
    tax
    rts

; A/X = XRAM address, Y = 256-byte pages to queue. Callers keep the level
; below PCM_BUF_LIMIT, so the device takes every byte.
pcm_dev_write:
    stx RIA_XSTACK
    sta RIA_XSTACK
    sty RIA_XSTACK
    stz RIA_XSTACK
    lda _pcm_fd
    sta RIA_A
    stz RIA_X
    lda #RIA_OP_WRITE_XRAM
    sta RIA_OP
    jsr RIA_SPIN
    cpx #$80
    bcs @done
    clc
    adc _pcm_written
    sta _pcm_written
    txa
    adc _pcm_written+1
    sta _pcm_written+1
    bcc @done
    inc _pcm_written+2
@done:
    rts

; A/X = bytes queued at the last clock plus every page written since. Feeders
; call it right after pcm_dev_consumed, without another firmware call.
pcm_dev_queued:
    sec
    lda _pcm_written
    sbc pcm_consumed
    tay
    lda _pcm_written+1
    sbc pcm_consumed+1
    tax
    tya
    rts

; A/X = samples the device has played since the previous call.
pcm_dev_consumed:
    jsr pcm_dev_level
    sta pcm_total
    stx pcm_total+1
    sec
    lda _pcm_written
    sbc pcm_total
    sta pcm_total
    lda _pcm_written+1
    sbc pcm_total+1
    sta pcm_total+1
    lda _pcm_written+2
    sbc #0
    sta pcm_total+2
    sec
    lda pcm_total
    sbc pcm_consumed
    pha
    lda pcm_total+1
    sbc pcm_consumed+1
    pha
    ldx #2
@copy:
    lda pcm_total,x
    sta pcm_consumed,x
    dex
    bpl @copy
    plx
    pla
    rts
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

; Music PCM (unsigned) at $CA08; procedural effects keep their independent
; signed 8 kHz ring at $C008. One pass over the newly filled page scales
; gameplay flight percussion, then adds the effects upsampled twice at half
; gain. Adding signed effects to unsigned music modulo 256 equals the signed
; sum plus 128, so the offset needs no extra work. One-shots own all audio.
; A = newly filled music ring page (0..3).
.if RIVER_PCM
music_mix_pcm:
    ldx _jingle_kind
    cpx #2
    jne @done
    sta mix_page
    ; Flight percussion is quieter only during actual gameplay.
    ldx #<flight_drum_gain
    ldy #>flight_drum_gain
    lda _ready
    sta mix_effects           ; Zero: gameplay, which mixes PCM effects.
    beq @gain
    ldx #<identity_gain
    ldy #>identity_gain
    lda _demo_splash_out      ; Only the departing splash engine mixes.
    beq :+
    lda _demo_splash_done
    bra :++
:   lda #1
:   sta mix_effects
@gain:
    stx @first+1
    sty @first+2
    stx @second+1
    sty @second+2
    lda _audio_backend
    cmp #3
    beq @fetch
    sta mix_effects           ; OPL effects: never mix the PCM ring.
@fetch:
    lda mix_effects
    bne @silent
    ; Effects reads start at multiples of 128, so a block never wraps.
    lda music_fx_read
    clc
    adc #8
    sta RIA_ADDR1
    lda music_fx_read+1
    adc #$c0
    sta RIA_ADDR1+1
    lda #1
    sta RIA_STEP1
    ldx #0
@effect:
    lda RIA_RW1
    cmp #$80
    ror a
    sta mix_half,x
    inx
    bpl @effect
    lda music_fx_read
    eor #128
    sta music_fx_read
    bne :+
    lda music_fx_read+1
    inc a
    and #7
    sta music_fx_read+1
:   lda #6
    sta RIA_ADDR0
    lda #$c0
    sta RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    lda music_fx_read
    sta RIA_RW0
    lda music_fx_read+1
    sta RIA_RW0
    bra @mix
@silent:
    lda _ready
    bne @done                 ; Demo without splash: the page stays as read.
    ; Gameplay with OPL effects: only the percussion gain.
    jsr mix_ports
@scale:
    ldy RIA_RW0
    lda flight_drum_gain,y
    sta RIA_RW1
    ldy RIA_RW0
    lda flight_drum_gain,y
    sta RIA_RW1
    inx
    bpl @scale
    rts
@mix:
    jsr mix_ports
@sample:
    ldy RIA_RW0
@first:
    lda flight_drum_gain,y
    clc
    adc mix_half,x
    sta RIA_RW1
    ldy RIA_RW0
@second:
    lda flight_drum_gain,y
    clc
    adc mix_half,x
    sta RIA_RW1
    inx
    bpl @sample
@done:
    rts
; Two ports read and write the same unpublished page; X = 0.
mix_ports:
    lda mix_page
    clc
    adc #$ca
    sta RIA_ADDR0+1
    sta RIA_ADDR1+1
    lda #8
    sta RIA_ADDR0
    sta RIA_ADDR1
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    ldx #0
    rts
mix_page: .byte 0
mix_effects: .byte 0
mix_half: .res 128            ; Halved effects samples for one music page.

identity_gain:
.repeat 256, sample
    .byte sample
.endrepeat

; Two 15% reductions: 0.85 * 0.85 = 289/400 (72.25% of demo amplitude).
; Unsigned 8-bit samples around 128, rounded to nearest with ties away from
; the midpoint.
flight_drum_gain:
.repeat 256, sample
    .if sample >= 128
        .byte 128 + ((sample - 128) * 289 + 200) / 400
    .else
        .byte 128 - ((128 - sample) * 289 + 200) / 400
    .endif
.endrepeat
.endif

; Effects run normally into their original mirrors. Merge only the voices
; reserved by the three-part flight arrangement; one-shots own all audio.
_music_effects:
    lda _gameover_active
    jeq @done
    lda _jingle_kind
    cmp #2
    jne @done
    ; audio_update mutes demo effects except the departing splash engine.
    ; Copy silent voices too, so F2/cancel cannot leave its engine keyed on.
    lda _paused
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
.else
    ; Six music voices leave three for effects. Keep the engine on 6;
    ; blasts borrow the player-shot voice on 7, never the engine's patch.
    ldx #0
    ldy #6
    jsr opl_copy_voice
    ldx #7
    lda #$b4
    sta RIA_ADDR1
    lda RIA_RW1
    and #32
    beq :+
    ldx #4
:
    ldy #7
    jsr opl_copy_voice
.endif
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
