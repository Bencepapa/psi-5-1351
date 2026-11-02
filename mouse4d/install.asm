; Called instead of the final bridge initializer at mx:$8258.
; Source bytes live in reclaimed crew-message tails, not overlay graphics.
        * = $FB5A
INSTALL:
        JSR $C900
        PHP
        SEI
        LDA $01
        PHA
        LDA #$35
        STA $01
        LDX #0
COPYFIRST:
        LDA $EFB8,X
        STA $2F60,X
        INX
        CPX #239
        BNE COPYFIRST
        LDA $F38F
        STA $304F
        LDX #0
COPYREST:
        LDA $F3B0,X
        STA $3050,X
        INX
        CPX #77
        BNE COPYREST
        LDX #16
COPYHELP:
        LDA $F3FD,X
        STA $CBCC,X
        DEX
        BPL COPYHELP
        LDA #0
        LDX #13
CLEARSTATE:
        STA $CC0C,X
        DEX
        BPL CLEARSTATE
        LDA #80
        STA $CC10
        LDA #116
        STA $CC11
        JMP ACTIVATE
INSTALLEND:

        * = $F856
ACTIVATE:
        LDA #$20
        STA $8F2D
        STA $8FB1
        STA $9005
        STA $8609
        LDA #<MPRE
        STA $8F2E
        LDA #>MPRE
        STA $8F2F
        LDA #<MJOY
        STA $8FB2
        LDA #>MJOY
        STA $8FB3
        LDA #<MPOST
        STA $9006
        LDA #>MPOST
        STA $9007
        LDA #<MKEY
        STA $860A
        LDA #>MKEY
        STA $860B
        PLA
        STA $01
        PLP
        RTS
ACTIVATEEND:
