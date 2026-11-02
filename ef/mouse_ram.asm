; Psi-5 EasyFlash: mouse support, RAM part at $0210-$02FF (Krill's old resident code,
; unused on the cartridge and never written during play).
; Trampolines map the mouse ROM bank (8K mode, $01=$37) and call it; the game's own routines
; ($95AC enable/cancel, $8AE7 rank) are called from here with the cartridge off.
DE00 = $DE00
DE02 = $DE02
MPRE = $8000             ; jump table of the ROM part
MJOY = $8003
MKEY = $8006
MSPR = $8009
MTOP = $800C
MXOR = $800F
RECBUF = $53E8           ; 14 bytes, only used inside TKEY: unused end of the text screen (before the sprite pointers)

        * = $0210
; IRQ hook ($8F2D JSR $8FA5): pots + pointer, then the game's joystick routine
TPRE:   LDX #<MPRE
        JSR ROMCALL
        JMP $8FA5
; joystick read ($8FB1 LDA $DC00): returns the joystick byte for the game
TJOY:   LDX #<MJOY
ROMCALL: STX RC+1      ; X = entry in the ROM part's page $80
        PHP
        SEI
        LDA $01
        PHA
        LDA #$37
        STA $01
        LDA #MBANK
        STA DE00
        LDA #$06        ; 8K mode: ROML at $8000
        STA DE02
RC:     JSR $8000
        STA RCA
        LDA #$04        ; cartridge off
        STA DE02
        PLA
        STA $01
        PLP
        LDA RCA
        RTS
; after the keyboard scan ($9005 JSR $3E72): keep port 2's pots selected all frame
TPOST:  JSR $3E72
        LDA #$BF
        STA $DC00
        RTS
; menu loop getkey ($8609 JSR $3EE9): let the ROM part look at a click, then act on it
TKEY:   LDX #<MKEY
        JSR ROMCALL
        LDA ACT         ; the ROM part has saved the command record and set up its arguments
        BEQ TK9
        CMP #2
        BEQ TKR
        BCS TKE
        LDA ACTA        ; 1 = enable, 0 = cancel the device in $2F
        JSR $95AC
        JMP TK8
TKR:    JSR $8AE7       ; Nav always selects rank 1; other departments use $30
        JMP TK8
TKE:    JSR $8CFC       ; examine target $2F
TK8:    LDY #13
TK2:    LDA RECBUF,Y
        STA $2D,Y
        DEY
        BPL TK2
        LDA #0
        STA ACT
TK9:    JMP $3EE9

; helper for the ROM part (its operand is patched)
PEEK:   .byte $AD       ; LDA abs
        .word $5000
        RTS

; variables
RCA:    .byte 0
OLDX:   .byte 0
OLDY:   .byte 0
MOLD:   .byte 0
MNEW:   .byte 0
XP:     .byte 80
YP:     .byte 116
CCOL:   .byte 20
CROW:   .byte 14
BTN:    .byte 0
CLICK:  .byte 0
MENUON: .byte 0
PCOL:   .byte 0
PROW:   .byte 0
RROW:   .byte 0
MOUSEON: .byte 0
TMP:    .byte 0
TMP2:   .byte 0
TMP3:   .byte 0
ACT:    .byte 0
ACTARG: .byte 0
ACTA:   .byte 0
SPX:    .byte 0         ; pointer sprite, computed by the ROM part
SPY:    .byte 0
SPM:    .byte 0         ; bit 7 = X bit 8
SHX:    .byte 0         ; the game's values for sprite 7 while the pointer uses it
SHY:    .byte 0
SHC:    .byte 0
GEN:    .byte 0         ; the game's $D015
INTXT:  .byte 0         ; bit 7: the raster is in the text area, sprite 7 is the pointer; bit 6: arrow XORed in
PREVW:  .byte 0         ; preview row while a priority item is dragged
HOVR:   .byte 0         ; list hover row, or 14 for native menu selection
HOVS:   .byte 0         ; first column / menu word start
HOVE:   .byte 0         ; list end column, or synthetic-key release phase
RBTN:   .byte 0         ; right mouse button state
RCLICK: .byte 0         ; right-button press edge
CANCEL: .byte 0         ; cancel a drag until the left button is released
; the game's sprite stores (see the sprite pointer below); here because they are all that fits
; $E8D3/$E8FC STA $D001,Y
WRY:    CPY #14
        BNE WRY1
        STA SHY
        BIT INTXT
        BMI WRY2
WRY1:   STA $D001,Y
WRY2:   RTS
; $E88A STA $D02B,X
WRC:    CPX #3
        BNE WRC1
        STA SHC
        BIT INTXT
        BMI WRC2
WRC1:   STA $D02B,X
WRC2:   RTS
; every STA $D015 of the game (A may be changed: all of them load A again)
WRE:    STA GEN
        BIT INTXT
        BPL WRE1
        ORA #$80
WRE1:   STA $D015
        RTS
; $E8C8/$E8F1 STA $D000,Y
WRX:    CPY #14
        BNE WRX1
        STA SHX
        BIT INTXT
        BMI WRX2
WRX1:   STA $D000,Y
WRX2:   RTS
; sprite pointer, code in the ROM part: sprite 7 is multiplexed, the ships use it above the split,
; the pointer below. The game moves its sprites from the main loop at any time, so while the
; pointer is up the game's stores for sprite 7 go to the shadow variables only (WRX, WRY, WRC, WRE).
; text split ($8EFF JMP $8F95)
TSPR:   LDX #<MSPR
        JSR ROMCALL
        JMP $8F95
; line $82, below the top rows of the view ($8E9D STA $0315): the arrow goes into its block
TXOR:   STA $0315
        LDX #<MXOR
        JMP ROMCALL
; top of the screen ($8F40 STA $D018)
TTOP:   STA $D018
        LDX #<MTOP
        JMP ROMCALL
RAMEND:
