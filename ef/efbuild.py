"""Build psi5_ef.crt: Psi-5 Trading Company (+4D 101%) as an EasyFlash cartridge.

usage: python efbuild.py [--bridge] [out.crt]
Inputs: ../tools/snap_ram.bin + snap_io.txt (snapshot at the trainer prompt, tools/snap.py),
        or with --bridge the snapb_* files (tools/snap_bridge.py: a test cartridge that starts on
        the bridge with a crew already chosen),
        ../PSI-5 +4D 101% ATA.d64 (the files, stored as they end up in memory after loading).
"""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, r'C:\dev\c64\mousegui\tools')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from asm6502 import assemble
from krillpack import decode

BRIDGE = '--bridge' in sys.argv
ARGS = [a for a in sys.argv[1:] if a != '--bridge']
SNAP = 'snapb_' if BRIDGE else 'snap_'
OUT = ARGS[0] if ARGS else os.path.join(ROOT, 'psi5_ef_bridge.crt' if BRIDGE else 'psi5_ef.crt')
D64 = os.path.join(ROOT, 'PSI-5 +4D 101% ATA.d64')
C1541 = r'C:\dev\c64\vice\win\bin\c1541.exe'
_m = re.search(r'\.;([0-9a-f]{4}) (\w\w) (\w\w) (\w\w) (\w\w) (\w\w) (\w\w) ([01]{8})',
               open(os.path.join(ROOT, 'tools', SNAP + 'cpu.txt')).read())
CPU = dict(pc=int(_m.group(1), 16), a=int(_m.group(2), 16), x=int(_m.group(3), 16), y=int(_m.group(4), 16),
           sp=int(_m.group(5), 16), r01=int(_m.group(7), 16), p=int(_m.group(8), 2))
print('snapshot CPU', {k: hex(v) for k, v in CPU.items()})


def asm_file(fn, prefix='', suffix=''):
    out, sym, _ = assemble(prefix + open(os.path.join(HERE, fn), encoding='utf8').read() + suffix)
    return out, sym


# ---- resident code ($DF00) ----
res_out, res_sym = asm_file('ef_res.asm')
res = bytearray(res_out.get(a, 0) for a in range(0xDF00, 0xE000))
assert res_sym['RESEND'] <= 0xDFFA    # $DFFA-$DFFF: mouse_rom.asm's variables

# ---- snapshot image ----
img = bytearray(open(os.path.join(ROOT, 'tools', SNAP + 'ram.bin'), 'rb').read()[2:])
assert len(img) == 65536
img[0x0200:0x0203] = bytes([0x4C, res_sym['RAWLD'] & 255, res_sym['RAWLD'] >> 8])
img[0x020B:0x020E] = bytes([0x4C, res_sym['CDLD'] & 255, res_sym['CDLD'] >> 8])
sp = CPU['sp']
img[0x0100 + sp - 2:0x0100 + sp + 1] = bytes([CPU['p'], CPU['pc'] & 255, CPU['pc'] >> 8])
for lab, v in (('GO01', CPU['r01']), ('GOA', CPU['a']), ('GOX', CPU['x']), ('GOY', CPU['y'])):
    res[res_sym[lab] + 1 - 0xDF00] = v
res[res_sym['GO'] + 6 - 0xDF00] = sp - 3   # LDX #sp-3 / TXS before the RTI
if os.environ.get('HOLD'):      # debugging: spin at $03C4 with IRQs off; "r pc=03c7" in the monitor resumes
    img[0x03C4:0x03C8] = bytes([0x4C, 0xC4, 0x03, 0x40])
    img[0x0100 + sp - 5:0x0100 + sp - 2] = bytes([0x24, 0xC4, 0x03])
    res[res_sym['GO'] + 6 - 0xDF00] = sp - 6

io = open(os.path.join(ROOT, 'tools', SNAP + 'io.txt')).read()
vic = bytearray()
for line in io.splitlines():
    m = re.match(r'>C:(d0[0-2][0-9a-f])\s+((?:[0-9a-f]{2}\s+)+)', line)
    if m:
        vic += bytes(int(h, 16) for h in m.group(2).split())
vic = vic[:47]
assert len(vic) == 47
vic[0x11] &= 0x7F       # the read value's bit 7 is the current raster line, not the compare
# raster compare: the line the IRQ handler in $0314 expects (the trainer prompt: $99)
RASTER = {0x8F33: 0x2D, 0x8ECE: 0x9A, 0x8F02: 0xAA}.get(img[0x0314] | img[0x0315] << 8, 0x99)

# ---- mouse support: RAM part at $0210 in the image, ROM part in the last bank ----
MOUSE = True
PTRCOL = 1      # pointer colour (outline: black)
mouse_bank = None
if MOUSE:
    ram_out, ram_sym = asm_file('mouse_ram.asm', 'MBANK = 1' + chr(10) + f'PTRCOL = {PTRCOL}' + chr(10))   # mouse ROM part: bank 1 (ROML)
    assert ram_sym['RAMEND'] <= 0x0300, 'mouse RAM part past $02FF'
    for a, v in ram_out.items():
        if not os.environ.get('KEEPRAM'):
            img[a] = v
    # the arrow's block: frame art from a bridge snapshot, shape from mouse_rom.asm
    ARTAD = 0x6080
    art = open(os.path.join(ROOT, 'tools', 'snapb_ram.bin'), 'rb').read()[2:][ARTAD:ARTAD + 63]
    src = open(os.path.join(HERE, 'mouse_rom.asm'), encoding='utf8').read()
    shape = bytes(int(h, 16) for h in re.findall(r'\$([0-9A-F]{2})', src[src.index('SHAPE:'):]))
    shape = shape.ljust(63, bytes(1))
    # (each cell's first line first: the VIC starts reading this row of the bitmap at line 51)
    def unrolled(lab, data):
        return lab + ':' + chr(10) + ''.join(f'        LDA #${v:02X}{chr(10)}        .byte $8D{chr(10)}        .word ${ARTAD + i:04X}{chr(10)}'
                                             for i, v in sorted(enumerate(data), key=lambda p: (p[0] % 8, p[0]))) + '        RTS' + chr(10)
    SIG = next(i for i, v in enumerate(art) if v not in (0, 255))
    rom_extra = chr(10) + unrolled('SHPUT', shape) + unrolled('SHRST', art)
    rom_out, _ = asm_file('mouse_rom.asm', f'SHSIGA = ${ARTAD + SIG:04X}{chr(10)}SHSIG = ${art[SIG]:02X}{chr(10)}SHBLOCK = ${(ARTAD - 0x4000) // 64:02X}{chr(10)}' + ''.join(f'{k} = ${v:04X}' + chr(10) for k, v in ram_sym.items()
                                                    if k.isupper() and not k.startswith('TK')
                                                    and k not in ('MPRE', 'MJOY', 'MKEY', 'MSPR', 'MTOP', 'MXOR')), rom_extra)
    mouse_rom = bytes(rom_out.get(a, 0) for a in range(0x8000, 0xA000))
    STA15 = bytes([0x8D, 0x15, 0xD0])
    HOOKS = {0x8F2D: (bytes([0x20, 0xA5, 0x8F]), ram_sym['TPRE']), 0x8FB1: (bytes([0xAD, 0x00, 0xDC]), ram_sym['TJOY']),
             0x9005: (bytes([0x20, 0x72, 0x3E]), ram_sym['TPOST']), 0x8609: (bytes([0x20, 0xE9, 0x3E]), ram_sym['TKEY']),
             0x8E9D: (bytes([0x8D, 0x15, 0x03]), ram_sym['TXOR']), 0x8EFF: (bytes([0x4C, 0x95, 0x8F]), ram_sym['TSPR']), 0x8F40: (bytes([0x8D, 0x18, 0xD0]), ram_sym['TTOP']),
             0xE8C8: (bytes([0x99, 0x00, 0xD0]), ram_sym['WRX']), 0xE8F1: (bytes([0x99, 0x00, 0xD0]), ram_sym['WRX']),
             0xE8D3: (bytes([0x99, 0x01, 0xD0]), ram_sym['WRY']), 0xE8FC: (bytes([0x99, 0x01, 0xD0]), ram_sym['WRY']),
             0xE88A: (bytes([0x9D, 0x2B, 0xD0]), ram_sym['WRC']), 0xE90B: (STA15, ram_sym['WRE']),
             0x92ED: (STA15, ram_sym['WRE']), 0x9387: (STA15, ram_sym['WRE']), 0x9437: (STA15, ram_sym['WRE']),
             0xB920: (STA15, ram_sym['WRE'])}
    hooked = dict.fromkeys(HOOKS, 0)


    def hook(mem, start):
        # hooks every place that holds the original bytes (RAM image and every file that has them)
        for a, (old, tgt) in HOOKS.items():
            i = a - start
            if 0 <= i and i + 3 <= len(mem) and bytes(mem[i:i + 3]) == old:
                mem[i:i + 3] = bytes([old[0] if old[0] == 0x4C else 0x20, tgt & 255, tgt >> 8])
                hooked[a] += 1


    if BRIDGE:      # hooks of the cartridge the snapshot came from point to the old RAM part
        for a, (old, tgt) in HOOKS.items():
            if img[a] in (0x20, 0x4C) and img[a + 2] in (2, 3):  # (older snapshots: $03xx too)
                img[a:a + 3] = old
    hook(img, 0)

# ---- data stream in banks 1.. ----
stream = bytearray()


def add(blob):
    pos = len(stream)
    stream.extend(blob)
    return pos


FIRST = 2 if True else 1        # bank 1 holds the mouse ROM part


def where(pos):
    bank = FIRST + pos // 16384
    return bank, 0x8000 + pos % 16384


def rec(pos, dst, length):
    bank, src = where(pos)
    return bytes([bank, src & 255, src >> 8, dst & 255, dst >> 8, length & 255, length >> 8])


p1 = add(img[0x0200:0xD000])
p2 = add(img[0xE000:0x10000])
p3 = add(img[0xD000:0xE000])
colram = open(os.path.join(ROOT, 'tools', SNAP + 'col.bin'), 'rb').read()[2:]
p4 = add(colram)
segtab = rec(p1, 0x0200, 0xD000 - 0x0200) + rec(p2, 0xE000, 0x2000) + rec(p3, 0x1000, 0x1000) + b'\0'
fixseg = rec(p1 + 0x1000 - 0x0200, 0x1000, 0x1000)
colseg = rec(p4, 0xD800, 0x0400)

# files: the bytes each load leaves in memory (raw load at L, then unpacked at P)
lst = subprocess.run([C1541, '-attach', D64, '-dir'], capture_output=True, text=True).stdout
names = re.findall(r'^\d+\s+"([^"]*)"\s+prg', lst, re.M)
directory = bytearray()
for nm in names:
    if 'docs' in nm or nm.startswith('psi-5 '):
        continue
    tmp = os.path.join(HERE, 'work_file.prg')
    subprocess.run([C1541, '-attach', D64, '-read', nm, tmp], capture_output=True)
    prg = open(tmp, 'rb').read()
    os.remove(tmp)
    L, s = prg[0] | prg[1] << 8, prg[2:]
    if nm == 'dp':
        start, data = L, bytes(s)
    else:
        _, P, unpacked, _ = decode(prg)
        start = min(L, P)
        end = max(L + len(s), P + len(unpacked))
        mem = bytearray(end - start)
        mem[L - start:L - start + len(s)] = s
        mem[P - start:P - start + len(unpacked)] = unpacked
        data = bytes(mem)
    if MOUSE:
        mem = bytearray(data)
        hook(mem, start)
        data = bytes(mem)
    assert start + len(data) <= 0xD000 or start >= 0xE000, f'{nm} reaches into $D000-$DFFF'
    pos = add(data)
    directory += nm.upper().encode('ascii') + b'\0' + rec(pos, start, len(data))
    print(f'{nm:16} ${start:04X}-${start + len(data) - 1:04X} ({len(data)} bytes) bank {where(pos)[0]}')
directory += b'\0'
assert len(directory) <= 256, len(directory)

# ---- boot code (bank 0) ----
prefix = ''.join(f'{k} = ${res_sym[k]:04X}\n' for k in ('COPY', 'CBANK', 'CSRC', 'CDST', 'CLEN', 'GO'))
boot_out, boot_sym = asm_file('ef_boot.asm', prefix)
assert boot_sym['RESIDENT'] + 256 <= 0x9C00, 'boot code too long'
roml0 = bytearray(0x2000)
romh0 = bytearray(0x2000)
for a, v in boot_out.items():
    if 0x8000 <= a < 0xA000:
        roml0[a - 0x8000] = v
    elif 0xA000 <= a < 0xC000:
        romh0[a - 0xA000] = v


def poke(addr, data):
    roml0[addr - 0x8000:addr - 0x8000 + len(data)] = data


poke(boot_sym['RESIDENT'], res)
poke(boot_sym['VICREGS'], vic)
poke(boot_sym['RASTER'] + 1, bytes([RASTER]))
poke(boot_sym['VBANK'] + 1, bytes([int(re.search(r'>C:dd00\s+(\w\w)', io).group(1), 16)]))
poke(boot_sym['FIXSEG'], fixseg)
poke(boot_sym['COLSEG'], colseg)
poke(boot_sym['SEGTAB'], segtab)
poke(0x9C00, img[0x0000:0x0200])
poke(0x9E00, directory)

# ---- CRT ----
stream = bytearray(mouse_rom + bytes(8192)) + stream     # bank 1 = mouse, data from bank 2
nbanks = 1 + (len(stream) + 16383) // 16384
stream += bytes(nbanks * 16384 - 16384 - len(stream))
crt = bytearray(b'C64 CARTRIDGE   ' + (0x40).to_bytes(4, 'big') + b'\x01\x00' + (32).to_bytes(2, 'big')
                + b'\x01\x00' + bytes(6) + b'PSI-5 TRADING COMPANY'.ljust(32, b'\0'))


def chip(bank, addr, data):
    return b'CHIP' + (0x2010).to_bytes(4, 'big') + (2).to_bytes(2, 'big') + bank.to_bytes(2, 'big') \
        + addr.to_bytes(2, 'big') + (0x2000).to_bytes(2, 'big') + bytes(data)


crt += chip(0, 0x8000, roml0) + chip(0, 0xA000, romh0)
for b in range(1, nbanks):
    chunk = stream[(b - 1) * 16384:b * 16384]
    crt += chip(b, 0x8000, chunk[:8192]) + chip(b, 0xA000, chunk[8192:])
open(OUT, 'wb').write(crt)
print(f'{OUT}: {nbanks} banks, {len(crt)} bytes; directory {len(directory)} bytes')
