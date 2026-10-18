; One-shot OPL2 + PCM jingles, installed over startup-only code.
.include "rp6502.inc"
.include "gameover-score.inc"
.include "victory-score.inc"
.macpack longbranch
.importzp ptr1
.import boot_open, boot_close, boot_read_xram
.import _audio_stop, _audio_init, _audio_muted, _paused, _ready, _duo_players
.import _rr_Copyright0, _reset_tiles
.export ___argv_mem
.import __STARTUP_AUDIO_RUN__, __GAMEOVER_SIZE__
.export _gameover_install, _gameover_update, _gameover_stop
.export _gameover_active := active, _gameover_started := started
.export _victory_bridge, _victory_started := victory_started
.export _jingle_kind := kind

SCORE = $F900
PCM = $C000
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
.assert victory_started < copy_code+33, error, "Jingle state exceeds bootstrap workspace"


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
    xreg_values $E000, __GAMEOVER_SIZE__
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
    lda #$e0
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
    lda _audio_muted
    ora _paused
    bne @playing
    inc started
    lda #0
    jsr start
@playing:
    lda active
    jeq idle
    lda _audio_muted
    ora _paused
    jne finish
    lda $0282
    and #1
    jeq finish
    lda $80
    cmp variant
    jne finish
@clock:
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

start:
    sta kind
    jsr _audio_stop
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
    xreg 0,1,1,OPL
    lda #<SCORE
    sta cursor
    lda #>SCORE
    sta cursor+1
    lda #3
    sta fraction
    jsr sequence
    lda kind
    clc
    adc #2
    tax
    jsr open_asset
    ldy kind
    lda pages_lo,y
    sta pages
    lda pages_hi,y
    sta pages+1
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
    jsr feed
    xreg 0,1,2,PCM
    bmi @done
    inc pcm_supported
@done:
    rts

sequence:
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
    jeq finish
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

feed:
    lda pages
    ora pages+1
    beq @done
    lda write_page
    sec
    sbc read_ptr+1
    and #3
    cmp #3
    bcs @done
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

stop:
    lda active
    beq @done
    stz active
    xreg 0,1,1,$ffff
    xreg 0,1,2,$ffff
    jsr boot_close
@done:
    rts

; Match BRIDGE on the HUD at the instant of destruction. Native scrolling
; can advance level before the shot; do not undo that visible advancement.
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

open_asset:
    lda path_lo,x
    pha
    lda path_hi,x
    tax
    pla
    jmp boot_open

path_lo: .lobytes score_path, victory_score_path, pcm_path, victory_pcm_path
path_hi: .hibytes score_path, victory_score_path, pcm_path, victory_pcm_path
score_lo: .lobytes GAMEOVER_SCORE_BYTES, VICTORY_SCORE_BYTES
score_hi: .hibytes GAMEOVER_SCORE_BYTES, VICTORY_SCORE_BYTES
pages_lo: .lobytes GAMEOVER_PCM_PAGES, VICTORY_PCM_PAGES
pages_hi: .hibytes GAMEOVER_PCM_PAGES, VICTORY_PCM_PAGES
score_path: .asciiz "ROM:gameover-score.bin"
pcm_path: .asciiz "ROM:gameover.pcm"
victory_score_path: .asciiz "ROM:victory-score.bin"
victory_pcm_path: .asciiz "ROM:victory.pcm"
header: .byte 0,0,3,10,$80,$3e,0,0

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
