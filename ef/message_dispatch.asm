; Expands an escape/id pair from the repacked crew messages, then feeds the
; original raw-symbol mapper. Ordinary symbols take the original path.
OLDMAP = $C890

        * = DISPATCH
MDISPATCH:
        STX OUTX
        PHA
        LDA PENDING
        BNE TOKEN
        PLA
        CMP #ESCAPE
        BEQ ESC
        LDX OUTX
        JSR OLDMAP
        RTS
ESC:    LDA #1
        STA PENDING
        LDX OUTX
        RTS
TOKEN:  LDA #0
        STA PENDING
        PLA
        TAX
        TYA
        PHA
        LDA DICTOFF,X
        TAY
NEXT:   LDA DICTDATA,Y
        CMP #ESCAPE
        BEQ DONE
        LDX OUTX
        JSR OLDMAP
        STX OUTX
        INY
        BNE NEXT
DONE:   PLA
        TAY
        LDX OUTX
        LDA #1
        RTS
PENDING: .byte 0
OUTX:    .byte 0
MEND:
