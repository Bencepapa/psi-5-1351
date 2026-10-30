; Resident part: runs in the EasyFlash RAM at $DF00-$DFFF (copied there by the boot).
; COPY expects: interrupts off, $01=$37, $DE02=$07 (16K mode). It leaves bank 0 selected.
DE00 = $DE00
DE02 = $DE02
DIR  = $9E00             ; directory in bank 0 ROML: name, 0, bank, src lo/hi, dst lo/hi, len lo/hi

        * = $DF00
; COPY: CLEN bytes from bank CBANK at CSRC ($8000-$BFFF window) to CDST
COPY:   LDA CBANK
        STA DE00
        LDA CSRC
        STA CP1+1
        LDA CSRC+1
        STA CP1+2
        LDA CDST
        STA CP2+1
        LDA CDST+1
        STA CP2+2
CP1:    LDA $8000
CP2:    .byte $8D       ; STA abs (forced: the operand is patched)
        .word $0000
        INC CP1+1
        BNE CP3
        INC CP1+2
        LDA CP1+2
        CMP #$C0
        BNE CP3
        LDA #$80        ; continue in the next bank
        STA CP1+2
        INC CBANK
        LDA CBANK
        STA DE00
CP3:    INC CP2+1
        BNE CP4
        INC CP2+2
CP4:    LDA CLEN
        BNE CP5
        DEC CLEN+1
CP5:    DEC CLEN
        LDA CLEN
        ORA CLEN+1
        BNE CP1
        LDA #0
        STA DE00
        RTS

; loader entries: $0200 -> RAWLD (0-terminated name), $020B -> CDLD (length in $B7)
RAWLD:  LDA #16
        .byte $2C
CDLD:   LDA $B7
        STA NLEN
        STX NM+1
        STY NM+2
        LDY #0          ; copy the name first: it may lie under the cartridge window
NM:     LDA $FFFF,Y
        STA NAME,Y
        BEQ NM1
        INY
        CPY NLEN
        BNE NM
NM1:    LDA #0
        STA NAME,Y
        PHP
        SEI
        LDA $01
        PHA
        LDA #$37
        STA $01
        LDA #$07
        STA DE02
        LDA #0
        STA DE00
        LDX #0
FD1:    LDA DIR,X       ; end of directory?
        BEQ NOTF
        LDY #0
FD2:    LDA DIR,X       ; NAME is 0-terminated: equal up to and including the 0 = found
        CMP NAME,Y
        BNE FD4
        CMP #0          ; both ended (0-terminated name)
        BEQ FOUND
        INX
        INY
        BNE FD2
FD4:    LDA DIR,X       ; skip to the entry's 0, then its 7 data bytes
        BEQ FD5
        INX
        BNE FD4
FD5:    TXA
        CLC
        ADC #8
        TAX
        BNE FD1
NOTF:   BEQ DONE        ; (A = 0 here)
FOUND:  LDY #0
FD6:    LDA DIR+1,X
        STA CBANK,Y
        INX
        INY
        CPY #7
        BNE FD6
        JSR COPY
DONE:   LDA #$04        ; cartridge off
        STA DE02
        PLA
        STA $01
        PLP
        LDA #0
        RTS

; GO: the end of the boot (zero page and stack are restored already).
; Afterwards these bytes are the loader's name buffer (17 bytes).
NAME:
GO:     LDA #$04
        STA DE02
        LDX #$F3        ; the image has P, PCL, PCH at $01F4-$01F6
        TXS
GO01:   LDA #$35
        STA $01
GOA:    LDA #$60
GOX:    LDX #$00
GOY:    LDY #$00
        RTI

CBANK:  .byte 0
CSRC:   .word 0
CDST:   .word 0
CLEN:   .word 0
NLEN:   .byte 0
RESEND:
