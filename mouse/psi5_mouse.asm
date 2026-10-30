; =====================================================================
; Psi-5 Trading Company - Commodore 1351 mouse support, v1
; Patch for part3 ($1000-$9FFF). Code and sprite live in $7808-$7FFF,
; unused bitmap memory (verified untouched by a random 227-move tour).
;
; - 1351 in port 1 or 2 (auto-detected), proportional mode: a pointer sprite.
; - In a menu (the game's one menu loop at $8249): the item under the
;   pointer is highlighted by feeding the game's own joystick left/right
;   logic, and a click selects it (fire).
; - Elsewhere a mouse click is fire. The joystick works as before.
; Hooks (part3):
;   $869D JSR $FF9F  -> JSR MPRE   (IRQ: read pots before the keyboard scan)
;   $86A9 LDA $DC00  -> JSR MJOY   (IRQ: the joystick read, DDR A = 0 here)
;   $8249 JSR $FFE4  -> JSR MLOOP  (menu loop: marks "a menu is active")
; =====================================================================

SCNKEY  = $FF9F
GETIN   = $FFE4
CURITEM = $103A         ; game: current menu item (1-based)
MENUROW = $5230         ; game: text screen row 14 holds the menu
SPRBLK  = $FE           ; $7F80 (normal) / $FF = $7FC0 (over an item)
MAXQ    = 6             ; frames a menu stays "active" after the loop polled

        * = $7808

; ---- IRQ, before the keyboard scan: pots, pointer, sprite ----
MPRE:   LDA $D419
        STA POTX
        LDA $D41A
        STA POTY
        JSR MOUSE
        JSR MOVE
        JSR SPRITE
        JMP SCNKEY

; ---- IRQ, instead of LDA $DC00: returns the port-2 lines the game sees ----
MJOY:   LDA $DC00
        STA J2
        LDA $DC01
        STA J1
        LDA PSEL        ; latch: becomes the output when the game restores
        STA $DC00       ; DDR A, so the mouse port's pots are selected all frame
        LDA #$FF
        STA VJ
        LDA MLOCK
        BNE MJ0
        JMP MJOUT       ; no mouse: the game sees the real port 2
MJ0:    LDX MPORT       ; left button = the mouse port's fire line
        LDA JV-1,X
        AND #$10
        EOR #$10        ; nonzero = pressed
        STA BTN
        BEQ MJ1
        LDA LASTB
        BNE MJ1
        LDA #1          ; press edge
        STA PEND
MJ1:    LDA BTN
        STA LASTB
        LDA MPORT       ; port-1 buttons show up as keys: drop them
        CMP #1
        BNE MJ2
        LDA J1
        AND #$11
        CMP #$11
        BEQ MJ2
        LDA #0
        STA $C6
MJ2:    LDA MENUON
        BEQ NOMENU
        DEC MENUON
        LDA #7          ; yellow pointer if over an item
        STA PCOL
        JSR ITEMAT
        BNE MJ3
        LDA #1          ; in a menu but not on an item: ignore clicks
        STA PCOL
        LDA #0
        STA PEND
        JMP MJOUT
MJ3:    STA TGT
        CMP CURITEM
        BEQ ATTGT
        LDA PULSE       ; step one item every second frame (press, release)
        EOR #1
        STA PULSE
        BEQ MJOUT
        LDA TGT
        CMP CURITEM
        BCC MJL
        LDA #$F7        ; right
        STA VJ
        JMP MJOUT
MJL:    LDA #$FB        ; left
        STA VJ
        JMP MJOUT
ATTGT:  LDA PEND        ; on the wanted item: deliver the click as fire
        BEQ MJOUT
        LDA #0
        STA PEND
        LDA #$EF
        STA VJ
        JMP MJOUT
NOMENU: LDA #1
        STA PCOL
        LDA #0
        STA PEND
        LDA BTN         ; outside menus a held button is a held fire
        BEQ MJOUT
        LDA #$EF
        STA VJ
MJOUT:  LDA J2
        LDX MLOCK
        BEQ MJ9
        LDX MPORT       ; mouse on port 2: its own fire/up lines are ours to decide
        CPX #2
        BNE MJ9
        ORA #$11
MJ9:    AND VJ
        RTS

; ---- menu loop hook: remember that a menu is waiting for input ----
MLOOP:  LDA #MAXQ
        STA MENUON
        JMP GETIN

; ---- item number (1-based) under the pointer on the menu row, 0 = none ----
ITEMAT: LDA CROW
        CMP #14
        BNE ITN
        LDX CCOL
        LDA MENUROW,X
        CMP #$20
        BEQ ITN
        LDY #0          ; count word starts from column 0 up to the pointer
        LDX #0
        LDA #$20
        STA PREV
IT1:    LDA MENUROW,X
        CMP #$20
        BEQ IT2
        LDA PREV
        CMP #$20
        BNE IT2
        INY
IT2:    LDA MENUROW,X
        STA PREV
        CPX CCOL
        BEQ IT3
        INX
        BNE IT1
IT3:    TYA
        RTS
ITN:    LDA #0
        RTS

; ---- 1351: detection (both ports, alternating) and movement ----
MOUSE:  LDA #0
        STA DX
        STA DY
        LDA POTX
        AND POTY
        CMP #$FF        ; empty port / joystick reads $FF
        BEQ MNONE
        LDA MLOCK
        BNE MHAVE
        LDA POTX
        STA OLDX
        LDA POTY
        STA OLDY
        LDA #1
        STA MLOCK
        LDA #0
        STA FFCNT
        JMP MPS
MHAVE:  LDA #0
        STA FFCNT
        LDA POTX
        LDY OLDX
        JSR MOVCHK
        STY OLDX
        STA DX
        LDA POTY
        LDY OLDY
        JSR MOVCHK
        STY OLDY
        EOR #$FF
        CLC
        ADC #1
        STA DY
        JMP MPS
MNONE:  LDA MLOCK
        BEQ MSCAN
        INC FFCNT
        LDA FFCNT
        CMP #50
        BCC MPS
        LDA #0
        STA MLOCK
MSCAN:  INC SCNT
        LDA SCNT
        AND #7
        BNE MPS
        LDA MPORT
        EOR #3          ; 1 <-> 2
        STA MPORT
MPS:    LDX MPORT
        LDA PSELT-1,X
        STA PSEL
        RTS

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

; ---- pointer position: x 0-319, y 0-199, character cell ----
MOVE:   LDX #0
        LDA DX
        BPL MV1
        DEX
MV1:    CLC
        ADC XL
        STA XL
        TXA
        ADC XH
        STA XH
        BMI XNEG
        CMP #1
        BCC XOK
        BNE XMAX
        LDA XL
        CMP #<320
        BCC XOK
XMAX:   LDA #<319
        STA XL
        LDA #>319
        STA XH
        JMP XOK
XNEG:   LDA #0
        STA XL
        STA XH
XOK:    LDX #0
        LDA DY
        BPL MV2
        DEX
MV2:    CLC
        ADC YP
        STA YP
        TXA
        ADC #0
        BMI YNEG
        BNE YMAX
        LDA YP
        CMP #200
        BCC YOK
YMAX:   LDA #199
        STA YP
        JMP YOK
YNEG:   LDA #0
        STA YP
YOK:    LDA XH
        LSR A
        LDA XL
        ROR A
        LSR A
        LSR A
        STA CCOL
        LDA YP
        LSR A
        LSR A
        LSR A
        STA CROW
        RTS

; ---- sprite 0 as the pointer (only while a mouse is present) ----
SPRITE: LDA MLOCK
        BNE SP1
        LDA $D015
        AND #$FE
        STA $D015
        RTS
SP1:    LDA PCOL        ; shape: arrow, or arrow with "!" over a menu item
        CMP #7
        BEQ SP2
        LDA #SPRBLK
        .byte $2C       ; BIT abs: skip the next LDA
SP2:    LDA #SPRBLK+1
        STA $53F8       ; text screen and bitmap colour screen both need it
        STA $57F8
        LDA PCOL
        STA $D027
        LDA XL
        CLC
        ADC #24
        STA $D000
        LDA XH
        ADC #0
        STA TMP
        LDA $D010
        AND #$FE
        ORA TMP
        STA $D010
        LDA YP
        CLC
        ADC #50
        STA $D001
        LDA $D01C
        AND #$FE
        STA $D01C
        LDA $D015
        ORA #1
        STA $D015
        RTS

; ---- variables ----
PSELT:  .byte $7F,$BF   ; $DC00 latch for the pots of port 1 / port 2
MPORT:  .byte 2
PSEL:   .byte $BF
MLOCK:  .byte 0
FFCNT:  .byte 0
SCNT:   .byte 0
POTX:   .byte 0
POTY:   .byte 0
OLDX:   .byte 0
OLDY:   .byte 0
MOLD:   .byte 0
MNEW:   .byte 0
DX:     .byte 0
DY:     .byte 0
XL:     .byte 160
XH:     .byte 0
YP:     .byte 120
CCOL:   .byte 0
CROW:   .byte 0
JV:
J1:     .byte $FF
J2:     .byte $FF
VJ:     .byte $FF
BTN:    .byte 0
LASTB:  .byte 0
PEND:   .byte 0
MENUON: .byte 0
TGT:    .byte 0
PULSE:  .byte 0
PREV:   .byte 0
PCOL:   .byte 1
TMP:    .byte 0
CODEEND:

; ---- pointer shapes (sprite blocks $FE, $FF in VIC bank 1) ----
        * = $7F80
;@SHAPES
