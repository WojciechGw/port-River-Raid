; Procedural XL/XE-style audio, 8 kHz mono signed PCM.
; The synth fills a 2048-byte ring at $C008; $C006/7 holds its read pointer.
; While effects own the firmware's PCM: device, each completed 256-byte page
; is interpolated to 512 unsigned 16 kHz bytes at $CA08 and queued. While
; music owns it, the music player consumes this ring and moves the pointer.
; Prepare at most 160 samples per frame, keeping 512 samples queued including
; the unfinished page. This spreads CPU work across VSYNCs without IRQ work.
.include "rp6502.inc"
.macpack longbranch
.export _opl_commit
.import _opl_a, _opl_b, _opl_volume
.if RIVER_PCM
.export _pcm_feed, _pcm_reset, _pcm_refills, _pcm_empty
.import _pcm_amplitude, _pcm_step, _pcm_tone
.import _pcm_owner, pcm_dev_level, pcm_dev_write, PCM_BUF_LIMIT
STAGE = $CA08                 ; Music staging ring, idle while effects own PCM.

.segment "ZEROPAGE"
poly: .res 6
amplitude: .res 2
step: .res 4
kind: .res 2
value: .res 2
phase: .res 4
tone_bit: .res 2
previous: .res 1
mixed: .res 1
write_page: .res 1
partial: .res 1
count: .res 1
read_lo: .res 1
read_hi: .res 1
available: .res 2
zero_end:
.segment "BSS"
_pcm_refills: .res 2
_pcm_empty: .res 2
completed: .res 1             ; Bit 7: a page awaits the device; bits 0-2: page.
upsample: .res 1              ; Last unsigned sample, for interpolation.

.segment "CODE"
.macro voice n
    .local no_clock,noise,positive,sign,done
    lda amplitude+n
    beq done
    clc
    lda phase+n*2+1
    adc step+n*2+1
    sta phase+n*2+1
    bcc no_clock
    lda kind+n
    beq noise
    lda tone_bit+n
    eor #1
    sta tone_bit+n
    jmp sign
noise:
    ; Galois form of x^17+x^5+1: long period without audio-rate hiss.
    lsr poly+n*3+2
    ror poly+n*3+1
    ror poly+n*3
    bcc :+
    lda poly+n*3+2
    eor #1
    sta poly+n*3+2
    lda poly+n*3
    eor #$10
    sta poly+n*3
:
    lda poly+n*3
sign:
    and #1
    beq positive
    lda amplitude+n
    jmp :+
positive:
    lda amplitude+n
    eor #$ff
    clc
    adc #1
:
    sta value+n
no_clock:
    lda value+n
done:
.endmacro

_pcm_reset:
    lda #0
    ldx #zero_end-poly-1
:
    sta poly,x
    dex
    bpl :-
    sta completed
    lda #$80
    sta upsample
    lda #0
    sta _pcm_refills
    sta _pcm_refills+1
    sta _pcm_empty
    sta _pcm_empty+1
    lda #$ff
    sta poly
    sta poly+1
    lda #1
    sta poly+2
    sta poly+5
    lda #2
    sta write_page
    lda #$45
    sta poly+3
    lda #$23
    sta poly+4
    rts


_pcm_feed:
    lda #1
    sta RIA_STEP1
    lda _pcm_owner
    cmp #1
    bne feed_read
    ; The device plays two bytes per synth sample. Model its queue as the
    ; ring's read pointer, so published pages count until they are played.
    jsr pcm_dev_level
    stx read_hi
    lsr read_hi
    ror a
    sta read_lo
    sec
    lda #0
    sbc read_lo
    sta read_lo
    lda write_page
    sbc read_hi
    and #7
    sta read_hi
    bra feed_queued
feed_read:
    lda #7
    sta RIA_ADDR1
    lda #$c0
    sta RIA_ADDR1+1
    lda RIA_RW1
    sta read_hi
    lda #6
    sta RIA_ADDR1
    lda RIA_RW1
    sta read_lo
    lda RIA_RW1
    cmp read_hi
    bne feed_read
feed_queued:
    ; Include prepared-but-unpublished samples in the queue target.
    sec
    lda partial
    sbc read_lo
    sta available
    lda write_page
    sbc read_hi
    and #7
    sta available+1
    cmp #2
    bcc :+
    rts
:
    ora available
    bne :+
    lda _pcm_refills
    ora _pcm_refills+1
    beq :+
    inc _pcm_empty
    bne :+
    inc _pcm_empty+1
:
    lda #160
    sta count
    lda available+1
    beq feed_fill
    lda available
    cmp #96
    bcc feed_fill
    lda #0
    sec
    sbc available
    sta count
feed_fill:
    ; Round phase increments to 8-bit precision (31.25 Hz noise clocks).
    ldx #2
:
    lda _pcm_step,x
    clc
    adc #128
    lda _pcm_step+1,x
    adc #0
    bcc :+
    lda #255
:
    sta step+1,x
    dex
    dex
    bpl :--
    ldx #1
feed_params:
    lda _pcm_amplitude,x
    sta amplitude,x
    lda _pcm_tone,x
    sta kind,x
    lda tone_bit,x
    ldy kind,x
    bne feed_sign
    cpx #0
    bne :+
    lda poly
    jmp feed_sign
:
    lda poly+3
feed_sign:
    and #1
    bne :+
    lda amplitude,x
    eor #$ff
    clc
    adc #1
    jmp feed_value
:
    lda amplitude,x
feed_value:
    sta value,x
    dex
    bpl feed_params
    lda partial
    clc
    adc #8
    sta RIA_ADDR1
    lda write_page
    adc #$c0
    sta RIA_ADDR1+1
feed_chunk:
    ; Work in chunks up to the page end, so the sample loop counts only Y.
    sec
    lda #0
    sbc partial
    beq :+                    ; At a page start a whole page is free.
    cmp count
    bcc :++
:   lda count
:   sta available             ; Samples in this chunk.
    tay
    clc
    adc partial
    sta partial               ; Zero once the chunk completes its page.
    sec
    lda count
    sbc available
    sta count
    lda amplitude+1
    jeq feed_one
feed_sample:
    voice 0
    sta mixed
    voice 1
    clc
    adc mixed
    tax
    ; Both amplitudes <=30: sum and previous fit signed 8-bit, no clipping.
    clc
    adc previous
    cmp #$80
    ror a
    sta RIA_RW1
    stx previous
    dey
    beq feed_chunk_done
    jmp feed_sample
; The second voice is silent, as usual in flight: the same samples, cheaper.
feed_one:
    voice 0
    tax
    clc
    adc previous
    cmp #$80
    ror a
    sta RIA_RW1
    stx previous
    dey
    bne feed_one
feed_chunk_done:
    lda partial
    bne feed_more
    lda write_page
    ora #$80
    sta completed
    inc write_page
    lda write_page
    and #7
    sta write_page
    ; Portal 0 publishes while portal 1 continues streaming sample bytes.
    lda #1
    sta RIA_STEP0
    sta RIA_ADDR0
    lda #$c0
    sta RIA_ADDR0+1
    lda write_page
    sta RIA_RW0
    bne :+
    ; The ring starts eight bytes after its header; wrap the data portal.
    lda #8
    sta RIA_ADDR1
    lda #$c0
    sta RIA_ADDR1+1
:
    inc _pcm_refills
    bne feed_more
    inc _pcm_refills+1
feed_more:
    lda count
    jne feed_chunk
feed_done:
    lda completed
    bpl @done
    and #7
    stz completed
    ldx _pcm_owner
    cpx #1
    bne @done
    ; Linear interpolation to 16 kHz, offset to unsigned: the midpoint with
    ; the previous sample, then the sample itself.
    clc
    adc #$c0
    sta RIA_ADDR1+1
    lda #8
    sta RIA_ADDR1
    sta RIA_ADDR0
    lda #>STAGE
    sta RIA_ADDR0+1
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    ldy #0
@sample:
    lda RIA_RW1
    eor #$80
    tax
    clc
    adc upsample
    ror a
    sta RIA_RW0
    stx RIA_RW0
    stx upsample
    iny
    bne @sample
    lda #<STAGE
    ldx #>STAGE
    ldy #2
    jmp pcm_dev_write
@done:
    rts
.assert 1024+512 <= PCM_BUF_LIMIT, lderror, "Effects queue exceeds the PCM buffer budget"
.endif

; Commit the nine prepared OPL voices through one portal setup. Read the
; register mirror to avoid redundant writes/key transitions; no C call per
; register, no separate 256-byte cache, and no sound work inside an IRQ.
.segment "CODE"
_opl_commit:
    lda #0
    sta RIA_STEP0
    lda #$c0
    sta RIA_ADDR0+1
    ldx #0
opl_next:
    txa
    ora #$a0
    sta RIA_ADDR0
    lda _opl_a,x
    cmp RIA_RW0
    beq :+
    sta RIA_RW0
:
    txa
    ora #$b0
    sta RIA_ADDR0
    lda _opl_b,x
    cmp RIA_RW0
    beq :+
    sta RIA_RW0
:
    lda opl_slots,x
    clc
    adc #$43
    sta RIA_ADDR0
    lda _opl_volume,x
    cmp RIA_RW0
    beq :+
    sta RIA_RW0
:
    cpx #7
    bcc opl_done_voice
    lda opl_slots,x
    ora #$40
    sta RIA_ADDR0
    lda _opl_volume,x
    cmp #51
    bcc :+
    lda #50
:
    clc
    adc #13
    cmp RIA_RW0
    beq opl_done_voice
    sta RIA_RW0
opl_done_voice:
    inx
    cpx #9
    bne opl_next
    lda #1
    sta RIA_STEP0
    rts
.segment "RODATA"
opl_slots: .byte 0,1,2,8,9,10,16,17,18
