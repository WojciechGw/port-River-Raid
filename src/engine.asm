; PSG engine only. Timer 1 clocks signed polynomial noise into four stationary
; PSG waves, two for each sign. The previous sample supplies a two-tap average.
; This controls the actual noise clock instead of gating audio-rate white noise.
.include "rp6502.inc"
VIA_ACR = VIA_CR
.export _psg_engine_init, _psg_engine_apply, _psg_engine_stop
.export _engine_ticks, _engine_rng
.export _engine_frame
.import _engine_active, _engine_level, _engine_latch
.segment "BSS"
old_irq: .res 2
old_flags: .res 1
old_acr: .res 1
old_ier: .res 1
old_latch: .res 2
running: .res 1
previous: .res 1
current: .res 1
positive: .res 2
negative: .res 2
_engine_ticks: .res 2
_engine_rng: .res 2
_engine_frame: .res 4
.segment "CODE"
_psg_engine_init:
    php
    pla
    sta old_flags
    sei
    lda $fffe
    sta old_irq
    lda $ffff
    sta old_irq+1
    lda VIA_ACR
    sta old_acr
    lda VIA_IER
    sta old_ier
    lda VIA_T1LL
    sta old_latch
    lda VIA_T1LH
    sta old_latch+1
    lda #$7f
    sta VIA_IER
    lda old_acr
    and #$3f                    ; No PB7 output, timer 1 free-runs.
    ora #$40
    sta VIA_ACR
    lda #<engine_irq
    sta $fffe
    lda #>engine_irq
    sta $ffff
    lda #$02
    sta _engine_rng
    lda #$65
    sta _engine_rng+1
    lda #0
    sta running                ; Re-entering PSG must restart Timer 1.
    cli
    rts

_psg_engine_apply:
    php
    sei
    lda _engine_ticks
    sta _engine_frame
    lda _engine_ticks+1
    sta _engine_frame+1
    lda _engine_rng
    sta _engine_frame+2
    lda _engine_rng+1
    sta _engine_frame+3
    lda _engine_level
    asl a
    asl a
    asl a
    asl a
    sta positive
    sta negative+1
    lda #$f0
    sta positive+1
    sta negative
    ; Volume/gates on engine channels belong to the ISR, not the C uploader.
    lda #0
    sta RIA_STEP0
    lda #1
    sta RIA_ADDR0+1
    lda #$a6
    sta RIA_ADDR0
    lda _engine_active
    sta RIA_RW0
    ldx #3
@gate:
    lda RIA_ADDR0
    clc
    adc #8
    sta RIA_ADDR0
    lda _engine_active
    sta RIA_RW0
    dex
    bne @gate
    lda #1
    sta RIA_STEP0
    lda _engine_active
    bne @on
    lda #$40
    sta VIA_IER
    lda #0
    sta running
    beq @done
@on:
    lda _engine_latch
    sta VIA_T1LL
    lda _engine_latch+1
    sta VIA_T1LH
    lda running
    bne @done                   ; Retuning the latch must not restart phase.
    lda _engine_latch
    sta VIA_T1CL
    lda _engine_latch+1
    sta VIA_T1CH
    lda #$c0
    sta VIA_IER
    lda #1
    sta running
@done:
    plp
    rts

_psg_engine_stop:
    sei
    lda #$7f
    sta VIA_IER
    lda VIA_T1CL
    lda old_acr
    sta VIA_ACR
    lda old_latch
    sta VIA_T1LL
    lda old_latch+1
    sta VIA_T1LH
    lda old_irq
    sta $fffe
    lda old_irq+1
    sta $ffff
    lda old_ier
    sta VIA_IER
    lda old_flags
    pha
    plp
    rts

.macro noise_pair start
    lda #start
    sta RIA_ADDR0
    lda positive,x
    sta RIA_RW0
    sta RIA_RW0
    lda #start+8
    sta RIA_ADDR0
    lda negative,x
    sta RIA_RW0
    sta RIA_RW0
.endmacro

engine_irq:
    pha
    phx
    phy
    lda VIA_IFR
    and #$40
    bne :+
    ply
    plx
    pla
    jmp (old_irq)
:
    lda VIA_T1CL                ; Acknowledge only our timer source.
    lda _engine_active
    bne :+
    jmp irq_done
:
    inc _engine_ticks
    bne :+
    inc _engine_ticks+1
:
    ; Preserve every portal-0 register, including a caller's signed step.
    lda RIA_STEP0
    pha
    lda RIA_ADDR0
    pha
    lda RIA_ADDR0+1
    pha
    lsr _engine_rng+1
    ror _engine_rng
    bcc :+
    lda _engine_rng+1
    eor #$b4                    ; Maximal 16-bit Galois sequence, 65535 ticks.
    sta _engine_rng+1
:
    lda _engine_rng
    and #1
    sta current
    tax
    lda #1
    sta RIA_STEP0
    sta RIA_ADDR0+1
    noise_pair $a3              ; PSG channels 4/5: current binary sample.
    ldx previous
    noise_pair $b3              ; Channels 6/7: previous sample, averaging.
    lda current
    sta previous
    pla
    sta RIA_ADDR0+1
    pla
    sta RIA_ADDR0
    pla
    sta RIA_STEP0
irq_done:
    ply
    plx
    pla
    rti
