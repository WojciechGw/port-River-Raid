; Backend text and 8x8 note in the bottom-right corner below the scroller.
; Addresses match xram.h.
.include "rp6502.inc"
.export _sound_status_init, _sound_status_update
.export _sound_status_notify, _sound_status_tick
.export _sound_status_f9
.import _audio_muted, _audio_backend, _sound_icons, _sound_verbose
SOUND_CONFIG = $0220
SOUND_ICON_CONFIG = $0230
SOUND_ICON = $02C0
SOUND_TEXT = $02C8
WHITE_PALETTE = $BF80          ; Transparent black / opaque white; follows fade.
SOUND_ICON_X = 320-8
SOUND_ICON_Y = 240-8

.segment "ZEROPAGE"
sound_notice: .res 1

; Use low RAM to keep the auxiliary segment below CPB's $FE00 page.
.segment "CODE"
_sound_status_init:
    stz sound_notice
    lda #1
    sta RIA_STEP0
    lda #<SOUND_CONFIG
    sta RIA_ADDR0
    lda #>SOUND_CONFIG
    sta RIA_ADDR0+1
    ldy #0
@config:
    lda sound_config,y
    sta RIA_RW0
    iny
    cpy #30
    bne @config
    jsr _sound_status_update
    ; Text on plane 0 and icon on plane 1 below the scroller.
    ldy #0
    jsr sound_program
    cpx #0
    bne @done
    ldy #15
    ; Tail call returns the second XREG result to the caller.
    jmp sound_program
@done:
    rts
sound_program:
    ldx #15
@args:
    lda sound_args,y
    sta RIA_XSTACK
    iny
    dex
    bne @args
    lda #RIA_OP_XREG
    sta RIA_OP
    jmp RIA_SPIN
.segment "RODATA"
sound_config:
    .byte 0,0
    .word 296,SOUND_ICON_Y,3,1,SOUND_TEXT,WHITE_PALETTE,$FFFF
    .byte 0,0
    .word SOUND_ICON_X,SOUND_ICON_Y,8,8,SOUND_ICON,WHITE_PALETTE
sound_args:
    .byte 1,0,1, 0,1, 0,0, >SOUND_CONFIG,<SOUND_CONFIG, 0,0, 0,SOUND_ICON_Y, 0,SOUND_ICON_Y+8
    .byte 1,0,1, 0,3, 0,0, >SOUND_ICON_CONFIG,<SOUND_ICON_CONFIG, 0,1, 0,SOUND_ICON_Y, 0,SOUND_ICON_Y+8

.segment "CODE"
; Category masks cycle 0=all -> 1=effects only -> 3=silent -> 0.
_sound_status_f9:
    lda _audio_muted
    cmp #3
    bne @next
    lda #0
    bra @store
@next:
    asl a
    inc a
@store:
    sta _audio_muted
    stz sound_notice
    cmp #0
    bne @done
.if RIVER_PCM
    lda #60
    sta sound_notice
.endif
@done:
    rts

; Count all 60 Hz display frames, including pause and attract mode.
_sound_status_notify:
.if RIVER_PCM
    lda #<60
    sta sound_notice
.endif
    rts
_sound_status_tick:
.if RIVER_PCM
    lda sound_notice
    beq @done
    dec sound_notice
    lda sound_notice
    beq _sound_status_update
@done:
.endif
    rts

_sound_status_update:
    lda #1
    sta RIA_STEP0
    ; Leave the rightmost 24 pixels to the label while it is visible.
    ; Otherwise restore the note to the very corner.
    lda #<(SOUND_ICON_CONFIG+2)
    sta RIA_ADDR0
    lda #>SOUND_ICON_CONFIG
    sta RIA_ADDR0+1
    lda _audio_muted
.if RIVER_PCM
    ora _sound_verbose
    ora sound_notice
.endif
    beq @right
    lda #<280
    bra @position
@right:
    lda #<SOUND_ICON_X
@position:
    sta RIA_RW0
    lda #<SOUND_ICON
    sta RIA_ADDR0
    lda _audio_muted
    and #1                   ; Cross the note when music is disabled.
    asl a
    asl a
    asl a
    tay
    ; Carry retains icon visibility throughout the copy (INY/DEX preserve it).
    lda _audio_muted
    ora _sound_verbose
    cmp #1
    ldx #8
@icon:
    lda #0
    bcc @pixel
    lda _sound_icons,y
@pixel:
    sta RIA_RW0
    iny
    dex
    bne @icon
    ; Text follows the icon in XRAM; continue through the same port.
.if RIVER_PCM
    lda sound_notice
    bne @backend_index
.endif
    lda _audio_muted
    bne @text_index
.if RIVER_PCM
    lda _sound_verbose
    beq @text_index
@backend_index:
    lda _audio_backend
    clc
    adc #2
.endif
@text_index:
    asl a
    asl a
    tay
    ldx #4
@backend:
    lda sound_backends,y
    sta RIA_RW0
    iny
    dex
    bne @backend
    rts
sound_backends: .byte "    ","SFX ","    ","OFF "
.if RIVER_PCM
    .byte "OPL ","PCM "
.endif
