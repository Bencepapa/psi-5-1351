"""Boot straight to the title: skip the crack's intro and trainer prompt in 'psi-5       /ata'.

The file (load $0801) is a packed intro: a plain prologue at $080D copies the depacker to $00FD,
the depacker unpacks $0803-$5BF2 and RUNs it. The intro installs the loader and its IRQ setup, waits
for a key at $0915, then the trainer prompt ($0BD9) clears the trainer flags $03F6 and exits at
$0DA6 (LDA #0 / STA $D011 / JMP $0987: load the game).

Patch:
- the prologue's JMP $1CE2 goes to a copier appended to the file; it copies HOOK to $C800 (the
  depacker never writes there) and continues with JMP $1CE2;
- the intro's JSR $0B38 (draws the intro screen) becomes JSR $C800. Its two address bytes are
  literals in the packed stream, so changing them changes only those two bytes of the unpacked
  image (checked by emulating the depacker);
- HOOK keeps the display off ($0901: #$1B -> #$0B) and turns the CLI at $0914 into JMP F;
  F clears $03F6 and jumps to $0DA6. All of the intro's setup up to $0913 still runs.
"""

HOOK = 0xC800
F = HOOK + 21
CODE = bytes([0xA9, 0x0B, 0x8D, 0x01, 0x09,            # display stays off
              0xA9, 0x4C, 0x8D, 0x14, 0x09,            # $0914: JMP F
              0xA9, F & 255, 0x8D, 0x15, 0x09,
              0xA9, F >> 8, 0x8D, 0x16, 0x09,
              0x60,
              0xA9, 0x00, 0x8D, 0xF6, 0x03,            # F: no trainers
              0x4C, 0xA6, 0x0D])
NAME = 'psi-5       /ata'
SIZE = 5663
LIT = {0x61: 0x38, 0x62: 0x0B}                         # PRG offset: packed literal of $08BF/$08C0


def patch(prg):
    prg = bytearray(prg)
    assert len(prg) == SIZE and prg[:2] == b'\x01\x08', 'unexpected psi-5 /ata'
    off = lambda a: a - 0x0801 + 2
    end = 0x0801 + len(prg) - 2
    assert prg[off(0x0819):off(0x081C)] == bytes([0x4C, 0xE2, 0x1C])
    prg[off(0x0819):off(0x081C)] = bytes([0x4C, end & 255, end >> 8])
    src = end + 14
    prg += bytes([0xA2, len(CODE) - 1, 0xBD, src & 255, src >> 8, 0x9D, HOOK & 255, HOOK >> 8,
                  0xCA, 0x10, 0xF7, 0x4C, 0xE2, 0x1C]) + CODE
    for o, old in LIT.items():
        assert prg[o] == old
    prg[0x61], prg[0x62] = HOOK & 255, HOOK >> 8
    return bytes(prg)
