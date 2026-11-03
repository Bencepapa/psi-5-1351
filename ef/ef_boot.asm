; =====================================================================
; Psi-5 Trading Company (+4D 101%) on EasyFlash.
; Boot: restore a RAM snapshot taken at the trainer prompt and resume at its exit ($0DA6), then
; serve every file load from the cartridge instead of the Krill loader.
; The loader entries $0200 (raw) and $020B (load + unpack) jump to the
; resident code in the EasyFlash RAM at $DF00. Files are stored unpacked
; (exactly as they end up in memory), so a load is a copy from ROM.
; Banks 1.. hold the data as one stream; ROML+ROMH = 16 KB per bank.
; build.py fills in the directory and the image tables (marked ;@).
; =====================================================================

DE00     = $DE00         ; bank
DE02     = $DE02         ; control: $04 off, $05 Ultimax, $07 16K (+$80 LED)

; ---------------- ROMH bank 0 (Ultimax $E000-$FFFF at reset) ---------------
        * = $BF00        ; = $FF00 in Ultimax
RESET:  SEI
        LDX #$FF
        TXS
        CLD
        LDX #STUBEND-STUB-1
RS1:    LDA STUB+$4000,X        ; (runs at $FFxx in Ultimax mode)
        STA $0100,X
        DEX
        BPL RS1
        JMP $0100
STUB:   LDA #$07        ; 16K mode: ROML $8000, ROMH $A000, KERNAL back at $E000
        STA DE02
        JMP BOOT
STUBEND:
NMIV:   RTI
        * = $BFFA
        .word NMIV+$4000, RESET+$4000, NMIV+$4000

; ---------------- ROML bank 0: boot ----------------
        * = $8000
BOOT:   SEI
        CLD
        LDX #$FF
        TXS
        LDA #$37
        STA $01
        LDA #$2F
        STA $00
        LDA #$0B        ; screen off while restoring
        STA $D011
        LDX #0          ; resident code -> $DF00
B1:     LDA RESIDENT,X
        STA $DF00,X
        INX
        BNE B1
        ; RAM image segments (bank, offset, dest, length) from the table
        LDX #0
B2:     LDA SEGTAB,X
        BEQ B4          ; bank 0 = end
        STA CBANK
        LDA SEGTAB+1,X
        STA CSRC
        LDA SEGTAB+2,X
        STA CSRC+1
        LDA SEGTAB+3,X
        STA CDST
        LDA SEGTAB+4,X
        STA CDST+1
        LDA SEGTAB+5,X
        STA CLEN
        LDA SEGTAB+6,X
        STA CLEN+1
        TXA
        PHA
        JSR COPY
        PLA
        CLC
        ADC #7
        TAX
        BNE B2
B4:     ; RAM under I/O: the image of $D000-$DFFF was copied to $1000; move it
        LDX #DSTUBEND-DSTUB-1
B5:     LDA DSTUB,X
        STA $0100,X
        DEX
        BPL B5
        JSR $0100
        ; and $1000-$1FFF gets its real contents again
        LDX #0
B6:     LDA FIXSEG,X
        STA CBANK,X
        INX
        CPX #7
        BNE B6
        JSR COPY
        LDX #0          ; colour RAM ($01=$37: I/O visible, the copy writes into it)
B6B:    LDA COLSEG,X
        STA CBANK,X
        INX
        CPX #7
        BNE B6B
        JSR COPY
        ; I/O registers
        LDX #$2E
B7:     LDA VICREGS,X
        STA $D000,X
        DEX
        BPL B7
RASTER: LDA #$99        ; raster compare (build.py sets it for the snapshot's IRQ)
        STA $D012
        LDA #$FF
        STA $D019
        LDA #$7F
        STA $DC0D
        STA $DD0D
        LDA $DC0D
        LDA $DD0D
        LDA #$FF
        STA $DC02
        LDA #$00
        STA $DC03
VBANK:  LDA #$3F        ; VIC bank (build.py: the snapshot's $DD00)
        STA $DD00
        LDA #$03
        STA $DD02
        ; The game's copy protection ($3C77) sets the CIA2 clock to 10:20:40.5 and wipes the stack
        ; unless the alarm fires. The alarm can't be read, so a snapshot has lost it: set it again.
        LDA $DD0F
        ORA #$80
        STA $DD0F
        LDA #$10
        STA $DD0B
        LDA #$20
        STA $DD0A
        LDA #$40
        STA $DD09
        LDA #$05
        STA $DD08
        LDA $DD0F
        AND #$7F
        STA $DD0F
        LDA #$0F
        STA $D418
        LDX #2          ; zero page and stack last (no JSR from here on)
FN1:    LDA ZPIMG,X
        STA $00,X
        INX
        BNE FN1
FN2:    LDA ZPIMG+$100,X
        STA $0100,X
        INX
        BNE FN2
        JMP GO

DSTUB:  LDA #$34        ; all RAM: copy $1000-$1FFF to $D000-$DFFF
        STA $01
        LDY #$10
        LDX #0
DS1:    LDA $1000,X
        STA $D000,X
        INX
        BNE DS1
        INC DS1+2-DSTUB+$0100
        INC DS1+5-DSTUB+$0100
        DEY
        BNE DS1
        LDA #$37
        STA $01
        RTS
DSTUBEND:

VICREGS: .fill 47,0     ;@VIC
FIXSEG:  .fill 7,0      ;@FIX  bank, src, dst, len of the $1000-$1FFF image
COLSEG:  .fill 7,0      ;@COL  colour RAM image
SEGTAB:  .fill 64,0     ;@SEG  segments, 7 bytes each, bank 0 ends
ZPIMG    = $9C00        ; $9C00-$9DFF: image of $0000-$01FF (filled by build.py)
DIR      = $9E00        ; directory: name, 0, bank, src, dst, len (filled by build.py)
RESIDENT:               ; the resident code's bytes follow (filled by build.py)

