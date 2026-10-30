"""Build PSI5-1351_v<N>.d64: assemble psi5_mouse.asm and patch part3 of the original disk.

usage: python build.py [version]       (input ../PSI5.d64, output ../PSI5-1351_v<N>.d64)
part3 is rewritten in place, in its own sectors, so a loader that reads by
track/sector still finds it.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r'C:\dev\c64\mousegui\tools')
from asm6502 import assemble

VERSION = sys.argv[1] if len(sys.argv) > 1 else '1'
IN_D64 = os.path.join(HERE, '..', 'PSI5.d64')
OUT_D64 = os.path.join(HERE, '..', f'PSI5-1351_v{VERSION}.d64')
PART3_BASE = 0x1000
FREE = (0x7808, 0x7FFF)     # verified unused (marker fill + random tour)

# ---------------- D64 helpers (from the Sentinel patch) ----------------
SPT = [0] + [21] * 17 + [19] * 7 + [18] * 6 + [17] * 10


def ts_off(t, s):
    return (sum(SPT[1:t]) + s) * 256


def file_sectors(d, name):
    t, s = 18, 1
    while t:
        o = ts_off(t, s)
        for i in range(8):
            e = d[o + i * 32:o + i * 32 + 32]
            if e[2] & 7 == 2 and e[5:21].rstrip(b'\xa0').decode('latin1') == name:
                secs = []
                ft, fs = e[3], e[4]
                while ft:
                    secs.append(ts_off(ft, fs))
                    ft, fs = d[secs[-1]], d[secs[-1] + 1]
                return secs
        t, s = d[o], d[o + 1]
    raise KeyError(name)


def read_file(d, secs):
    out = bytearray()
    for o in secs:
        n = 254 if d[o] else d[o + 1] - 1
        out += d[o + 2:o + 2 + n]
    return out


def write_file(d, secs, data):
    p = 0
    for o in secs:
        n = 254 if d[o] else d[o + 1] - 1
        d[o + 2:o + 2 + n] = data[p:p + n]
        p += n
    assert p == len(data)


# ---------------- pointer shapes ----------------
ARROW = """
X...........
XX..........
XXX.........
XXXX........
XXXXX.......
XXXXXX......
XXXXXXX.....
XXXXXXXX....
XXXXXXXXX...
XXXXXX......
XX.XXX......
X...XXX.....
....XXX.....
.....XXX....
.....XXX....
"""
BANG = """
XX
XX
XX
XX
XX
XX
..
XX
XX
"""


def shape(*parts):
    img = [[0] * 24 for _ in range(21)]
    for art, ox, oy in parts:
        for y, row in enumerate(art.strip().splitlines()):
            for x, c in enumerate(row):
                if c == 'X':
                    img[oy + y][ox + x] = 1
    b = bytearray()
    for row in img:
        for k in range(3):
            b.append(int(''.join(map(str, row[k * 8:k * 8 + 8])), 2))
    return bytes(b) + b'\0'


def shapes_asm():
    lines = []
    for data in (shape((ARROW, 0, 0)), shape((ARROW, 0, 0), (BANG, 12, 1))):
        for i in range(0, 64, 16):
            lines.append('        .byte ' + ','.join(f'${v:02X}' for v in data[i:i + 16]))
    return '\n'.join(lines) + '\n'


def main():
    src = open(os.path.join(HERE, 'psi5_mouse.asm'), encoding='utf8').read().replace(';@SHAPES', shapes_asm())
    out, sym, listing = assemble(src)
    with open(os.path.join(HERE, 'psi5_mouse.lst'), 'w') as f:
        f.write('\n'.join(listing) + '\n\n')
        for k in sorted(sym, key=lambda k: sym[k]):
            f.write(f'{k:12} = ${sym[k]:04X}\n')
    lo, hi = min(out), max(out)
    assert FREE[0] <= lo and hi <= FREE[1], f'code outside the free area: ${lo:04X}-${hi:04X}'
    assert sym['CODEEND'] <= 0x7F80, f'code runs into the sprites: ${sym["CODEEND"]:04X}'
    print(f'patch code ${lo:04X}-${sym["CODEEND"] - 1:04X} ({sym["CODEEND"] - lo} bytes), sprites $7F80-$7FFF')

    d = bytearray(open(IN_D64, 'rb').read())
    secs = file_sectors(d, 'PART3')
    data = bytearray(read_file(d, secs))
    assert data[0] | data[1] << 8 == PART3_BASE

    def poke(addr, bs, expect=None):
        i = addr - PART3_BASE + 2
        if expect is not None:
            got = bytes(data[i:i + len(expect)])
            assert got == bytes(expect), f'${addr:04X}: expected {bytes(expect).hex()}, found {got.hex()}'
        data[i:i + len(bs)] = bs

    for a in sorted(out):
        poke(a, bytes([out[a]]), [0])   # the free area must still be empty in the original
    jsr = lambda t: bytes([0x20, t & 255, t >> 8])
    poke(0x869D, jsr(sym['MPRE']), [0x20, 0x9F, 0xFF])     # JSR SCNKEY
    poke(0x86A9, jsr(sym['MJOY']), [0xAD, 0x00, 0xDC])     # LDA $DC00
    poke(0x8249, jsr(sym['MLOOP']), [0x20, 0xE4, 0xFF])    # JSR GETIN
    write_file(d, secs, data)
    open(OUT_D64, 'wb').write(d)
    print('wrote', OUT_D64)


if __name__ == '__main__':
    main()
