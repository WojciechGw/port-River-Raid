; Fixed 8x8 VGA text in the unused top margin. Addresses match xram.h.
.include "rp6502.inc"
.export _sound_status_init, _sound_status_update
.import _audio_muted, _audio_backend, _sound_icons, _sound_verbose
SOUND_CONFIG = $0220
SOUND_ICON_CONFIG = $0230
SOUND_ICON = $02C0
SOUND_TEXT = $02C8
WHITE_PALETTE = $BF80          ; Transparent black / opaque white; follows fade.

; Use low RAM to keep the auxiliary segment below CPB's $FE00 page.
.segment "CODE"
_sound_status_init:
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
    ; Text on plane 0, icon bitmap on plane 1, both in scanlines 0..7.
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
    .word 16,0,4,1,SOUND_TEXT,WHITE_PALETTE,$FFFF
    .byte 0,0
    .word 0,0,8,8,SOUND_ICON,WHITE_PALETTE
sound_args:
    .byte 1,0,1, 0,1, 0,0, >SOUND_CONFIG,<SOUND_CONFIG, 0,0, 0,0, 0,8
    .byte 1,0,1, 0,3, 0,0, >SOUND_ICON_CONFIG,<SOUND_ICON_CONFIG, 0,1, 0,0, 0,8

.segment "CODE"
_sound_status_update:
    lda #1
    sta RIA_STEP0
    lda #<SOUND_ICON
    sta RIA_ADDR0
    lda #>SOUND_ICON
    sta RIA_ADDR0+1
    lda _audio_muted
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
    lda _sound_verbose
    beq @text_index
    lda _audio_backend
    asl a
    asl a
@text_index:
    tay
    ldx #4
@backend:
    lda sound_backends,y
    sta RIA_RW0
    iny
    dex
    bne @backend
    rts
sound_backends: .byte "    ","PSG ","OPL2","PCM "
