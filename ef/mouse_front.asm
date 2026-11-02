; Course / crew front end. Called through TJOY at the original $1EAD read.
; IRQ $1EEB identifies this phase; no bridge IRQ or extra resident RAM is used.
; HOVR: 0 course, 1 portraits, 2 personnel file, 3 final crew.
; MENUON: mouse targeting active, relinquished to joystick directions/keys.
FJOY:   JSR FARTREST
        LDA $DC00
        STA TMP2
        LDA #$BF        ; keyboard scan just selected the other pot port
        STA $DC00
        LDA #0
        STA CANCEL
        LDA MOUSEON
        STA MOLD
        LDA $D419
        AND $D41A
        EOR #$FF
        STA MOUSEON
        BNE FJHAS
        LDA MOLD
        BEQ FJRAW
        JSR FEND
FJRAW:  LDA #0
        STA MENUON
        STA BTN
        STA CLICK
        LDA TMP2
        STA ACTA
        JMP FJRETURN
FJHAS:  LDA MOLD
        BNE FJMOVE
        LDA $D419       ; initial pot sample is a baseline, not mouse movement
        STA OLDX
        LDA $D41A
        STA OLDY
FJMOVE: LDA #0
        STA TMP
        LDA $D419
        LDY OLDX
        JSR MOVCHK
        STY OLDX
        CMP #0
        BEQ FJX
        INC TMP
FJX:    CMP #$80
        ROR A
        CLC
        ADC XP
        CMP #160
        BCC FJXOK
        CMP #$C8
        LDA #159
        BCC FJXOK
        LDA #0
FJXOK:  STA XP
        LSR A
        LSR A
        STA CCOL
        LDA $D41A
        LDY OLDY
        JSR MOVCHK
        STY OLDY
        CMP #0
        BEQ FJY
        INC TMP
FJY:    STA MNEW
        EOR #$FF
        SEC
        ADC YP
        LDX MNEW
        BMI FJDOWN
        BCS FJYOK
        LDA #0
        BEQ FJYOK
FJDOWN: CMP #200
        BCC FJYOK
        LDA #199
FJYOK:  STA YP
        LSR A
        LSR A
        LSR A
        STA CROW
        LDA TMP
        BEQ FJMODE
        LDA #1
        STA MENUON
FJMODE: LDA TMP2
        AND #15
        CMP #15
        BNE FJMANUAL
        LDA $62
        BEQ FJBUTTON
FJMANUAL:LDA #0
        STA MENUON
FJBUTTON:
        LDA #0
        STA CLICK
        LDA TMP2
        AND #$10
        BNE FJRELEASE
        LDA BTN
        BNE FJPHASE
        INC BTN
        INC CLICK
        BNE FJPHASE
FJRELEASE:LDA #0
        STA BTN
FJPHASE:LDA $DD00
        AND #3
        BEQ FJCOURSE
        CMP #2
        BEQ FJFILE
        LDA #1
        LDX $17
        CPX #10
        BCC FJSET
        LDA #3
        BNE FJSET
FJFILE: LDA #2
        BNE FJSET
FJCOURSE:LDA #0
FJSET:  STA HOVR
        LDA #$FF
        STA TMP3
        LDA MENUON
        BEQ FJINPUT
        JSR FHIT
        STA TMP3
        CMP #$FF
        BEQ FJINPUT
        LDX HOVR
        BEQ FJSETCOURSE
        CPX #1
        BEQ FJSETPORTRAIT
        STA $1B         ; Welcome/Exit or Accept/Reselect native option
        JMP FJINPUT
FJSETCOURSE:STA $07      ; original course loop redraws its native highlight
        JMP FJINPUT
FJSETPORTRAIT:
        CMP $19
        BEQ FJINPUT
        PHA
        LDX $19
        LDA #1
        JSR $1D4C       ; unselected borders are white in every department
        PLA
        STA $19
                        ; native loop flashes only the new $19 selection
FJINPUT:LDA TMP2
        LDX MENUON
        BEQ FJRESULT
        ORA #$10
        LDX CLICK
        BEQ FJRESULT
        LDX TMP3
        CPX #$FF
        BEQ FJRESULT
        AND #$EF
FJRESULT:STA ACTA
        AND #$10
        BEQ FJLEAVE
        LDA $62
        BNE FJLEAVE
        JSR FSPRITE
        JMP FJRETURN
FJLEAVE:JSR FHIDE
        LDA HOVR
        CMP #3
        BNE FJRETURN
        LDA ACTA
        AND #$10
        BNE FJNOSUPPRESS
        LDA $1B
        CMP #$15
        BNE FJNOSUPPRESS
        LDA #0
        STA BTN
        LDA #1          ; consume Accept's held click before the bridge begins
        STA CANCEL
FJNOSUPPRESS:JSR FEND
FJRETURN:
        LDA #$BF        ; keep port 2 pots selected between keyboard scans
        STA $DC00
        LDA ACTA
        RTS

; Fixed native geometry: four course rows, six 10x8-cell portrait rectangles,
; personnel footer, and the final crew's two header buttons.
FHIT:   LDX HOVR
        BEQ FHCOURSE
        DEX
        BEQ FHGRID
        DEX
        BEQ FHFILE
        LDA CROW
        CMP #1
        BNE FHNONE
        LDA CCOL
        CMP #22
        JMP FHBUTTON
FHFILE: LDA CROW
        CMP #24
        BNE FHNONE
        LDA CCOL
        CMP #32
FHBUTTON:LDA #$15
        BCC FHBRET
        LDA #5
FHBRET: RTS
FHCOURSE:LDA CROW
        SEC
        SBC #18
        BCC FHNONE
        CMP #7
        BCS FHNONE
        LSR A
        BCS FHNONE
        RTS
FHGRID: LDA CROW
        SEC
        SBC #3
        BCC FHNONE
        CMP #8
        BCC FHTOP
        SBC #10
        BCC FHNONE
        CMP #8
        BCS FHNONE
        LDX #6
        BNE FHCOLUMN
FHTOP:  LDX #0
FHCOLUMN:
        LDA CCOL
        SEC
        SBC #3
        BCC FHNONE
        CMP #10
        BCC FHFOUND
        SBC #12
        BCC FHNONE
        INX
        INX
        CMP #10
        BCC FHFOUND
        SBC #12
        BCC FHNONE
        INX
        INX
        CMP #10
        BCS FHNONE
FHFOUND:TXA
        RTS
FHNONE: LDA #$FF
        RTS

; Bank 0's old title text at $0400 is blank and unused in this phase. Restore
; it before the bridge uses its menu workspace. Course sprite is under KERNAL
; at $FFC0; the personnel sprite borrows a portrait source block at $7FC0.
FEND:   JSR FHIDE
        LDA $D01C
        AND #$7F
        STA $D01C
        LDA $D010
        AND #$7F
        STA $D010
        LDX #63
        LDA #$20
FEND0:  STA $0400,X
        DEX
        BPL FEND0
        LDA #0
        STA HOVR
        STA HOVS
        STA HOVE
        RTS
FHIDE:  LDA $D015
        AND #$7F
        STA $D015
        RTS
FARTREST:
        LDA INTXT
        BEQ FAREND
        LDX #62
FAR0:   LDA FARTDATA,X
        STA $7FC0,X
        DEX
        BPL FAR0
        LDA #0
        STA INTXT
FAREND: RTS
FSPRITE:
        LDA $FB
        PHA
        LDA $FC
        PHA
        LDA HOVR
        BEQ FSCOUT
        CMP #2
        BEQ FSFILE
        LDA #$10
        STA $0BFF
        LDA #0
        STA $FB
        LDA #4
        BNE FSBLOCK
FSCOUT: LDA #$FF
        STA $FBFF
        STA $FC
        LDA #$C0
        STA $FB
        BNE FSCOPY
FSFILE: LDA #$FF
        STA $63FF
        LDA #1
        STA INTXT
        LDA #$C0
        STA $FB
        LDA #$7F
FSBLOCK:STA $FC
FSCOPY: LDY #62
FSC0:   LDA SHAPE,Y
        STA ($FB),Y
        DEY
        BPL FSC0
        PLA
        STA $FC
        PLA
        STA $FB
        LDA YP
        CLC
        ADC #50
        STA $D00F
        LDA #0
        STA SPM
        LDA XP
        ASL A
        ROR SPM
        ADC #24
        STA $D00E
        BCC FSX
        LDA #$80
        STA SPM
FSX:    LDA $D010
        AND #$7F
        ORA SPM
        STA $D010
        LDA $D017
        AND #$7F
        STA $D017
        LDA $D01D
        AND #$7F
        STA $D01D
        LDA $D01B
        AND #$7F
        STA $D01B
        LDA $D01C
        ORA #$80
        STA $D01C
        LDA #0
        STA $D025
        LDA #1
        STA $D02E
        LDA $D015
        ORA #$80
        STA $D015
        RTS
