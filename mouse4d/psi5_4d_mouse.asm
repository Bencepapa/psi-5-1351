; =====================================================================
; Psi-5 Trading Company (+4D 101%, Avatar) - 1351 mouse support, v1
; Byte patches on the unpacked bridge file `mx` ($81C2-$BB1F).
; Code in $2F60-$30A0: blank rows of a list template in `di`, never written
; during a tour of all departments. Variables in $CC0C-$CC3F (tail of `c`).
; No sprite (the game uses all 8 for the space view) and no zero page (the
; game uses $FB-$FE). The pointer is a character cell in text rows 13-24
; whose colour is flipped (EOR). Mouse in port 2.
;
; Hooks:
;   $8F2D JSR $8FA5 -> JSR MPRE   IRQ: pots + pointer, then the joystick routine
;   $8FB1 LDA $DC00 -> JSR MJOY   joystick read (DDR A = 0): left button
;   $9005 JSR $3E72 -> JSR MPOST  after the keyboard scan: select port 2's pots
;   $8609 JSR $3EE9 -> JSR MKEY   menu loop getkey: turn a click into keys
; A click on the menu row types that word's shortcut key; clicking a device
; of a department list is for v2 (no room yet).
; =====================================================================

JOYRTN   = $8FA5
KBSCAN   = $3E72
GETKEY   = $3EE9
DEVSTATE = $58CC
KQUEUE   = $03CA
KCOUNT   = $4E
TITLE    = $5000+15*40
MENU     = $5000+14*40

OLDX     = $CC0C
OLDY     = $CC0D
MOLD     = $CC0E
MNEW     = $CC0F
XP       = $CC10         ; pointer x in 2-pixel units (0-159)
YP       = $CC11         ; pointer y in pixels (104-199)
CCOL     = $CC12
CROW     = $CC13
BTN      = $CC14
CLICK    = $CC15
MENUON   = $CC16
PCOL     = $CC17
PROW     = $CC18
MOUSEON  = $CC19

        * = $2F60

; ---- IRQ: pots, pointer, then the game's joystick routine ----
MPRE:   LDA $D419
        AND $D41A
        EOR #$FF        ; $FF on both pots = no 1351 in port 2
        STA MOUSEON
        BEQ MP9
        LDA $D419
        LDY OLDX
        JSR MOVCHK
        STY OLDX
        CMP #$80        ; /2 keeping the sign
        ROR A
        CLC
        ADC XP
        CMP #160
        BCC MP2
        LDA #0          ; past an edge: stick to the nearer one
        BIT XP
        BPL MP2
        LDA #159
MP2:    STA XP
        LSR A
        LSR A
        STA CCOL
        LDA $D41A
        LDY OLDY
        JSR MOVCHK
        STY OLDY
        EOR #$FF        ; pot Y grows upwards
        SEC
        ADC YP
        CMP #104
        BCS MP5
        LDA #104
MP5:    CMP #200
        BCC MP6
        LDA #199
MP6:    STA YP
        LSR A
        LSR A
        LSR A
        STA CROW
        JSR FLIP        ; old cell back
        LDA CCOL        ; colour RAM address of the new cell: $D800 + CROW*40 + CCOL
        LDX #$D8
        LDY CROW
RA1:    CLC
        ADC #40
        BCC RA2
        INX
RA2:    DEY
        BNE RA1
        STA FL1+1
        STA FL2+1
        STX FL1+2
        STX FL2+2
        JSR FLIP        ; new cell
MP9:    JMP JOYRTN


; ---- after the keyboard scan: keep port 2's pots selected all frame ----
MPOST:  JSR KBSCAN
        LDA #$BF
        STA $DC00
        RTS

; ---- joystick read (DDR A = 0): left button -> click event ----
MJOY:   LDA MENUON
        BEQ MJ0
        DEC MENUON
MJ0:    LDA $DC00
        LDX MOUSEON
        BEQ MJ8         ; no mouse: the real joystick
        AND #$10
        BNE MJREL
        LDA BTN
        BNE MJ5
        INC BTN         ; press: remember the cell
        LDA CCOL
        STA PCOL
        LDA CROW
        STA PROW
        BNE MJ5
MJREL:  LDA BTN
        BEQ MJ5
        DEC BTN
        LDA #1
        STA CLICK
MJ5:    LDA $DC00
        ORA #$11        ; the mouse's own lines are not a joystick
        LDX BTN         ; outside menus a held button is fire
        BEQ MJ8
        LDX MENUON
        BNE MJ8
        AND #$EF
MJ8:    RTS

; ---- menu loop getkey: turn a click into keys for the game ----
MKEY:   LDA #6
        STA MENUON
        LSR CLICK       ; 1 -> 0, carry = there was a click
        BCC MKX
        LDX PROW
        CPX #14         ; only the menu row for now (lists: v2)
        BNE MKX
        LDX PCOL        ; menu row: the word's shortcut key
        LDA MENU,X
        CMP #$20
        BEQ MKX         ; a gap
MK2:    DEX
        BMI MK3
        LDA MENU,X
        CMP #$20
        BNE MK2
MK3:    LDA MENU+1,X
        CMP #'?'
        BNE MK4
        LDA #'/'
MK4:    CMP #$60
        BCC MK5
        AND #$DF        ; lower case -> upper case
MK5:    CMP #'/'
        BCS PUTKEY
        LDA #$14        ; anything below '/' is the back arrow
PUTKEY: JSR PUTK
MKX:    JMP GETKEY

; CBM MOVCHK: A = new pot, Y = old -> A = signed delta, Y = value to keep
MOVCHK: STY MOLD
        STA MNEW
        SEC
        SBC MOLD
        AND #$7F
        CMP #$40
        BCS MVNEG
        LSR A
        BEQ MVZERO
        LDY MNEW
        RTS
MVNEG:  ORA #$C0
        CMP #$FF
        BEQ MVZERO
        SEC
        ROR A
        LDY MNEW
        RTS
MVZERO: LDA #0
        LDY MOLD
        RTS
CODEEND:

; small helpers in $CBCC-$CBE3 (24 bytes, untouched in the tour)
        * = $CBCC
FLIP:
FL1:    LDA $DBE7
        EOR #$06
FL2:    STA $DBE7
        RTS
PUTK:   LDX KCOUNT
        STA KQUEUE,X
        INC KCOUNT
        RTS
HELPEND:
