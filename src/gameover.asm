; Main/demo music and one-shot OPL2 + PCM jingles over startup-only code.
.include "rp6502.inc"
.if RIVER_PCM
.include "gameover-score.inc"
.include "victory-score.inc"
.endif
.include "intro-score.inc"
.macpack longbranch
.importzp ptr1
.import boot_open, boot_close, boot_read_xram
.import _audio_stop, _audio_init, _audio_muted, _paused, _ready, _duo_players
.import _rr_Copyright0, _reset_tiles, _demo_splash_gameover, _demo_splash_music_done
.export ___argv_mem
.import __STARTUP_AUDIO_RUN__, __GAMEOVER_SIZE__
.import music_enable, music_fallback_load, music_page
.if RIVER_PCM
.import music_probe, music_mix_pcm, _music_synth, music_fx_read, MUSIC_SCORE_BYTES
.endif
.export _gameover_install, _gameover_update, _gameover_stop
.export _gameover_active := active, _gameover_started := started
.export _victory_bridge, _victory_started := victory_started
.export _jingle_kind := kind

SCORE = $F900
PCM = $CA00
RING = PCM+8
OPL = $C900

.segment "BSS"
installed: .res 1
.segment "ZEROPAGE"
copy_code: .res 33
active = copy_code
started = copy_code+1
latched = copy_code+2
variant = copy_code+3
state_begin = copy_code+4
pcm_supported = state_begin
cursor = state_begin+1
remaining = state_begin+3
duration = state_begin+5
read_ptr = state_begin+7
previous = state_begin+9
write_page = state_begin+11
delta = state_begin+12
pages = state_begin+14
fraction = state_begin+16
state_end = state_begin+17
pending = state_end
kind = state_end+1
victory_started = state_end+2
music_wait = state_end+3
music_low = state_end+4
music_high = state_end+5
.assert music_high < copy_code+33, error, "Music state exceeds bootstrap workspace"


.segment "SPLASH"
_gameover_update:
    lda installed
    bne @loaded
    tax
    rts
@loaded:
    jmp update
_gameover_stop:
    lda installed
    beq @done
    jmp stop
@done:
    rts

.segment "STARTUP_AUDIO"
_gameover_install:
    lda #<code_path
    ldx #>code_path
    jsr boot_open
    xreg_values $E800, __GAMEOVER_SIZE__
    lda #<__GAMEOVER_SIZE__
    ldx #>__GAMEOVER_SIZE__
    jsr boot_read_xram
    jsr boot_close
    ldx #copy_end-copy_start-1
@copy:
    lda copy_start,x
    sta copy_code,x
    dex
    bpl @copy
    lda #<__STARTUP_AUDIO_RUN__
    sta ptr1
    lda #>__STARTUP_AUDIO_RUN__
    sta ptr1+1
    lda #0
    sta RIA_ADDR0
    lda #$e8
    sta RIA_ADDR0+1
    ldy #0
    jmp copy_code
; Run from ZP while replacing the currently executing startup segment.
copy_start:
    ldx #>__GAMEOVER_SIZE__
@page:
    lda RIA_RW0
    sta (ptr1),y
    iny
    bne @page
    inc ptr1+1
    dex
    bne @page
@tail:
    cpy #<__GAMEOVER_SIZE__
    beq @done
    lda RIA_RW0
    sta (ptr1),y
    iny
    bra @tail
@done:
    inc installed
    jmp initialize
copy_end:
.assert $E800+__GAMEOVER_SIZE__ <= $F100, lderror, "Installation scratch overlaps F1 backup"
.assert copy_end-copy_start <= 33, error, "Bootstrap exceeds ZP workspace"
code_path: .asciiz "ROM:gameover-code.bin"

.segment "GAMEOVER"
initialize:
    ; Reuse the installation trampoline as music state after its final jump.
    ldx #32
    lda #0
@clear:
    sta copy_code,x
    dex
    bpl @clear
    rts
update:
    lda pending
    beq @death
    stz pending
    jsr award
    lda _audio_muted
    and #1
    ora _paused
    bne @death
    inc victory_started
    lda #1
    jsr start
@death:
    ; Detect the death immediately, before the explosion changes to demo.
    ldy #0
    lda _ready
    bne @candidate
    lda $80
    cmp #2
    beq @duo
    lda $c6
    bpl @candidate
    cmp #255
    beq @candidate
    lda $c0
    cmp #<_rr_Copyright0
    bne @candidate
    lda $80
    beq @last
    ; GAME 2 swaps the active/reserve state, so $c5 is always the other pilot.
    lda $c5
    cmp #<_rr_Copyright0
    bne @candidate
    bra @last
@duo:
    lda _duo_players+8
    ora _duo_players+31
    bne @candidate
    lda _duo_players+20
    ora _duo_players+43
    beq @candidate
@last:
    iny
@candidate:
    lda latched
    sty latched
    cpy #0
    beq @playing
    cmp #0
    bne @playing
    jsr _demo_splash_gameover  ; Visual event is independent of F9/music.
    lda _audio_muted
    and #1
    ora _paused
    bne @playing
    inc started
    lda #0
    jsr start
@playing:
    lda active
    bne @active
    lda _audio_muted
    and #1
    ora _paused
    jne idle
    lda #2
    jsr start
@active:
    lda _audio_muted
    and #1
    jne finish
    lda kind
    cmp #2
    bne @jingle
    lda _paused
    jne finish
    bra @clock
@jingle:
    lda _paused
    jne finish
    lda $0282
    and #1
    jeq finish
    lda $80
    cmp variant
    jne finish
@clock:
.if RIVER_PCM
    lda pcm_supported
    beq @fallback
    stz RIA_STEP1
    lda #>PCM
    sta RIA_ADDR1+1
@read:
    lda #<(PCM+7)
    sta RIA_ADDR1
    lda RIA_RW1
    sta read_ptr+1
    dec RIA_ADDR1
    lda RIA_RW1
    sta read_ptr
    inc RIA_ADDR1
    lda RIA_RW1
    cmp read_ptr+1
    bne @read
    sec
    lda read_ptr
    sbc previous
    sta delta
    lda read_ptr+1
    sbc previous+1
    and #3
    sta delta+1
    lda read_ptr
    sta previous
    lda read_ptr+1
    sta previous+1
    jsr feed
    bra @advance
@fallback:
.endif
    lda #11
    dec fraction
    bne @fraction
    lda #3
    sta fraction
    lda #10
@fraction:
    sta delta
    lda #1
    sta delta+1
@advance:
    sec
    lda remaining
    sbc delta
    sta remaining
    lda remaining+1
    sbc delta+1
    sta remaining+1
    bmi @event
    ora remaining
    bne @done
@event:
    jsr sequence
    lda active
    beq idle
@done:
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    lda kind
    cmp #2
    beq idle                  ; Main music leaves room for gameplay effects.
    lda #1
    ldx #0
    rts
idle:
    lda #0
    tax
    rts
finish:
    jsr stop
    jsr _audio_init
    bra idle

.segment "MUSIC"
sequence_end:
    lda kind
    bne :+
    lda #1
    sta _demo_splash_music_done
:
    jmp finish

start:
    sta kind
    jsr _audio_stop
    lda kind
    cmp #2
    bne :+
    jsr _audio_init            ; Effects keep their own register/sample mirror.
:
.if RIVER_PCM
    stz music_fx_read
    stz music_fx_read+1
    ldx kind
    jsr open_asset
    lda #>SCORE
    sta RIA_XSTACK
    lda #<SCORE
    sta RIA_XSTACK
    ldy kind
    lda score_hi,y
    sta RIA_XSTACK
    tax
    lda score_lo,y
    sta RIA_XSTACK
    jsr boot_read_xram
    jsr boot_close
.endif
    lda #1
    sta active
    lda $80
    sta variant
    ldx #state_end-state_begin-1
    lda #0
@reset:
    sta state_begin,x
    dex
    bpl @reset
    sta RIA_ADDR0
    lda #>OPL
    sta RIA_ADDR0+1
    ldy #0
    lda #0
@clear:
    sta RIA_RW0
    iny
    bne @clear
.if RIVER_PCM
    lda #<PCM
    sta RIA_ADDR0
    lda #>PCM
    sta RIA_ADDR0+1
    ldy #0
@header:
    lda header,y
    sta RIA_RW0
    iny
    cpy #8
    bne @header
    lda #<PCM
    ldx #>PCM
    jsr music_probe
    lda _music_synth
    beq @hybrid
.endif
    ldx kind
    lda fallback_song,x
    jsr music_fallback_load
@hybrid:
    lda #>OPL
    sta music_page
    jsr music_enable
    lda #<SCORE
    sta cursor
    lda #>SCORE
    sta cursor+1
    lda #3
    sta fraction
    lda #1
    sta music_wait
    jsr sequence
.if RIVER_PCM
    lda _music_synth
    bne @done
    jsr pcm_open
    inc pcm_supported
    jsr feed
.endif
@done:
    rts
fallback_song: .byte 2,3,1

.segment "GAMEOVER"
.if RIVER_PCM
pcm_open:
    lda kind
    clc
    adc #3
    tax
    jsr open_asset
    ldy kind
    lda pages_lo,y
    sta pages
    lda pages_hi,y
    sta pages+1
    rts
.endif

sequence:
    lda kind
    cmp #2
    jeq music_sequence
    lda #1
    sta RIA_STEP1
    stz RIA_STEP0
    lda cursor
    sta RIA_ADDR1
    lda cursor+1
    sta RIA_ADDR1+1
    lda RIA_RW1
    sta duration
    lda RIA_RW1
    sta duration+1
    ora duration
    jeq sequence_end
    clc
    lda remaining
    adc duration
    sta remaining
    lda remaining+1
    adc duration+1
    sta remaining+1
    lda #>OPL
    sta RIA_ADDR0+1
    ldx RIA_RW1
    beq @done
@write:
    lda RIA_RW1
    sta RIA_ADDR0
    lda RIA_RW1
    sta RIA_RW0
    dex
    bne @write
@done:
    lda RIA_ADDR1
    sta cursor
    lda RIA_ADDR1+1
    sta cursor+1
    lda #1
    sta RIA_STEP0
    rts

.if RIVER_PCM
feed:
    lda write_page
    sec
    sbc read_ptr+1
    and #3
    cmp #3
    bcs @done
    lda pages
    ora pages+1
    bne @copy
    lda kind
    cmp #2
    bne @done
    jsr boot_close
    jsr pcm_open
@copy:
    lda write_page
    clc
    adc #>RING
    sta RIA_XSTACK
    lda #<RING
    sta RIA_XSTACK
    lda #1
    sta RIA_XSTACK
    lda #0
    sta RIA_XSTACK
    ldx #1
    jsr boot_read_xram
    lda write_page
    jsr music_mix_pcm
    lda pages
    bne @decrement
    dec pages+1
@decrement:
    dec pages
    inc write_page
    lda write_page
    and #3
    sta write_page
    lda #<(PCM+1)
    sta RIA_ADDR0
    lda #>PCM
    sta RIA_ADDR0+1
    lda write_page
    sta RIA_RW0
    bra feed
@done:
    rts
.endif

stop:
    lda active
    beq @done
    stz active
    xreg 0,1,1,$ffff
.if RIVER_PCM
    xreg 0,1,2,$ffff
    lda pcm_supported
    beq @done
    jsr boot_close
.endif
@done:
    rts

; Match BRIDGE on the HUD at the instant of destruction. Native scrolling
; can advance level before the shot; do not undo that visible advancement.
; Resident helpers leave the smaller startup overlay room for the player.
.segment "MUSIC"
_victory_bridge:
    php
    pha
    phy
    ldy $bd
    cpy #5
    beq @reward
    cpy #20
    beq @reward
    cpy #50
    bne @done
@reward:
    lda #1
    sta pending
@done:
    ply
    pla
    plp
    rts

; Apply after both DUO contexts have been saved, independent of sound/mute.
award:
    lda $80
    cmp #2
    beq @duo
    lda $c0
    cmp #72                ; Native maximum is nine reserve glyphs.
    beq @done
    bcc @classic
    lda #0                 ; Space / final-plane sentinel means no reserves.
@classic:
    clc
    adc #8
    sta $c0
@done:
    rts
@duo:
    ldx #23
@pilot:
    lda _duo_players+8,x
    cmp #80                ; GAME 3 includes the current plane, maximum ten.
    bcs @next
    clc
    adc #8
    sta _duo_players+8,x
    lda _duo_players+19,x
    bne @next
    lda #2                 ; Eliminated pilot now waits for bridge passage.
    sta _duo_players+19,x
@next:
    txa
    beq @sync
    ldx #0
    bra @pilot
@sync:
    ldx #0
    lda $f4
    beq @load
    ldx #23
@load:
    lda _duo_players+8,x
    sta $c0
    rts

.segment "GAMEOVER"
.if RIVER_PCM
open_asset:
    lda path_lo,x
    pha
    lda path_hi,x
    tax
    pla
    jmp boot_open
.endif

; Decode the same compact score used on the full-screen scenes. The shared
; sample clock/ring keeps OPL and PCM synchronized throughout the demo loop.
.segment "MUSIC"
music_sequence:
    clc
    lda remaining
    adc #<INTRO_STEP_SAMPLES
    sta remaining
    lda remaining+1
    adc #>INTRO_STEP_SAMPLES
    sta remaining+1
    dec music_wait
    jne @done
    lda #1
    sta RIA_STEP1
    stz RIA_STEP0
    lda #>OPL
    sta RIA_ADDR0+1
@cursor:
    lda cursor
    sta RIA_ADDR1
    lda cursor+1
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
    stz RIA_RW0
    bra @command
@note:
    lda RIA_RW1
    sta music_low
    lda RIA_RW1
    sta music_high
    and #$df
    sta RIA_RW0
    lda music_slots,x
    clc
    adc #$43
    sta RIA_ADDR0
    lda RIA_RW1
    sta RIA_RW0
    txa
    ora #$a0
    sta RIA_ADDR0
    lda music_low
    sta RIA_RW0
    txa
    ora #$b0
    sta RIA_ADDR0
    lda music_high
    sta RIA_RW0
    bra @command
@register:
    lda RIA_RW1
    sta RIA_ADDR0
    lda RIA_RW1
    sta RIA_RW0
    bra @command
@loop:
    lda #<SCORE
    sta cursor
    lda #>SCORE
    sta cursor+1
    jmp @cursor
@delay:
    and #$7f
    inc a
    sta music_wait
    lda RIA_ADDR1
    sta cursor
    lda RIA_ADDR1+1
    sta cursor+1
    lda #1
    sta RIA_STEP0
@done:
    rts
music_slots: .byte 0,1,2,8,9,10,16,17,18
.segment "GAMEOVER"
.if RIVER_PCM
path_lo: .lobytes score_path, victory_score_path, music_score_path, pcm_path, victory_pcm_path, music_pcm_path
path_hi: .hibytes score_path, victory_score_path, music_score_path, pcm_path, victory_pcm_path, music_pcm_path
score_lo: .lobytes GAMEOVER_SCORE_BYTES, VICTORY_SCORE_BYTES, MUSIC_SCORE_BYTES
score_hi: .hibytes GAMEOVER_SCORE_BYTES, VICTORY_SCORE_BYTES, MUSIC_SCORE_BYTES
pages_lo: .lobytes GAMEOVER_PCM_PAGES, VICTORY_PCM_PAGES, INTRO_DRUM_PAGES
pages_hi: .hibytes GAMEOVER_PCM_PAGES, VICTORY_PCM_PAGES, INTRO_DRUM_PAGES
score_path: .asciiz "ROM:gameover-score.bin"
pcm_path: .asciiz "ROM:gameover.pcm"
victory_score_path: .asciiz "ROM:victory-score.bin"
victory_pcm_path: .asciiz "ROM:victory.pcm"
music_score_path: .asciiz "ROM:flight-score.bin"
music_pcm_path: .asciiz "ROM:flight-drums.pcm"
header: .byte 0,0,3,10,$80,$3e,0,0
.endif

.segment "SPLASH"
; Fastcall AX = requested argv workspace size, at most 512 bytes.
___argv_mem:
    cpx #2
    bcc @buffer
    bne @fail
    cmp #0
    bne @fail
@buffer:
    lda #<_reset_tiles
    ldx #>_reset_tiles
    rts
@fail:
    lda #0
    tax
    rts
