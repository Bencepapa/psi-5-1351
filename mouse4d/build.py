"""Build PSI5-4D-1351_v<N>.d64 from "PSI-5 +4D 101% ATA.d64".

usage: python build.py [version]
Assembles psi5_4d_mouse.asm, writes the code into the unpacked files `di` ($2F60 block) and `c`
($CBCC helpers), the hooks into `mx`, repacks the three files (tools/krillpack.py) and writes them
into a copy of the disk (tools/d64put.py), and patches the boot file to skip the intro and the
trainer prompt (notrainer.py). The 38-block docs file is left out of the copy: the
patched files are larger (code packs worse than the spaces it replaces) and the disk was full.
"""
import os, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, 'tools')
PRGS = os.path.join(ROOT, 'plus4d')
sys.path.insert(0, r'C:\dev\c64\mousegui\tools')
sys.path.insert(0, os.path.join(ROOT, 'ef'))
from asm6502 import assemble
from message_codec import patch_messages, patch_decoder, DISPATCH, DICT_OFFSETS, DICT_DATA, ESCAPE

VERSION = sys.argv[1] if len(sys.argv) > 1 else '1'
SRC_D64 = os.path.join(ROOT, 'PSI-5 +4D 101% ATA.d64')
OUT_D64 = os.path.join(ROOT, f'PSI5-4D-1351_v{VERSION}.d64')
C1541 = r'C:\dev\c64\vice\win\bin\c1541.exe'
WORK = os.path.join(HERE, 'work')
os.makedirs(WORK, exist_ok=True)


def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    return r.stdout


def unpack(name):
    out = run(os.path.join(TOOLS, 'krillpack.py'), 'unpack', os.path.join(PRGS, name + '.prg'),
              os.path.join(WORK, name + '.bin'))
    start = int(re.search(r'destination \$([0-9A-Fa-f]{4})', out).group(1), 16)
    return start, bytearray(open(os.path.join(WORK, name + '.bin'), 'rb').read())


def main():
    out, sym, listing = assemble(open(os.path.join(HERE, 'psi5_4d_mouse.asm'), encoding='utf8').read())
    with open(os.path.join(HERE, 'psi5_4d_mouse.lst'), 'w') as f:
        f.write('\n'.join(listing) + '\n\n' + '\n'.join(f'{k:12} = ${v:04X}' for k, v in sorted(sym.items(), key=lambda kv: kv[1])))
    assert sym['CODEEND'] <= 0x30A1, 'main code past $30A0'
    assert sym['HELPEND'] <= 0xCBE4, 'helpers past $CBE3'

    # Never put code directly in di/c: their runtime overlays overwrite it.
    files = {n: unpack(n) for n in ('mx', 'ma', 'de')}

    def put(addr, bs, expect=None):
        for n, (start, data) in files.items():
            if start <= addr and addr + len(bs) <= start + len(data):
                i = addr - start
                if expect is not None:
                    ncheck = 1 if expect == 'blank' else len(expect)
                    got = bytes(data[i:i + ncheck])
                    if expect == 'blank':
                        assert got[0] in (0x00, 0x20), f'{n} ${addr:04X}: expected blank, found {got.hex()}'
                    else:
                        assert got == bytes(expect), f'{n} ${addr:04X}: expected {bytes(expect).hex()}, found {got.hex()}'
                data[i:i + len(bs)] = bs
                return n
        raise SystemExit(f'${addr:04X} is in none of the files')

    image = bytes(out[a] for a in range(0x2F60, sym['CODEEND']))
    helpers = bytes(out[a] for a in range(0xCBCC, sym['HELPEND']))
    assert len(image) == 317 and len(helpers) == 17
    prefix = (f'DISPATCH = ${DISPATCH:04X}\nDICTOFF = ${DICT_OFFSETS:04X}\n'
              f'DICTDATA = ${DICT_DATA:04X}\nESCAPE = ${ESCAPE:02X}\n')
    decoder, dsym, _ = assemble(prefix + open(os.path.join(ROOT, 'ef', 'message_dispatch.asm'), encoding='utf8').read())
    dispatch = bytes(decoder[a] for a in range(DISPATCH, dsym['MEND']))
    assert len(dispatch) == 72
    start, data = files['de']
    assert patch_messages(data, start, image[:240], dispatch) == 101
    put(0xF3B0, image[240:], bytes(77))
    put(0xF3FD, helpers, bytes(17))
    install_prefix = ''.join(f'{k} = ${sym[k]:04X}\n' for k in ('MPRE', 'MJOY', 'MPOST', 'MKEY'))
    installer, isym, _ = assemble(install_prefix + open(os.path.join(HERE, 'install.asm'), encoding='utf8').read())
    assert isym['INSTALLEND'] <= 0xFBC4
    assert isym['ACTIVATEEND'] <= 0xF8D7
    for a, v in installer.items():
        put(a, bytes([v]), [0])
    start, data = files['ma']
    patch_decoder(data, start)
    jsr = lambda t: bytes([0x20, t & 255, t >> 8])
    put(0x8258, jsr(isym['INSTALL']), [0x20, 0x00, 0xC9])

    shutil.copy(SRC_D64, OUT_D64)
    subprocess.run([C1541, '-attach', OUT_D64, '-delete', 'psi-5 docs  /ata'], capture_output=True)
    for n, (start, data) in files.items():
        binf = os.path.join(WORK, n + '_patched.bin')
        open(binf, 'wb').write(data)
        newprg = os.path.join(WORK, n + '_patched.prg')
        run(os.path.join(TOOLS, 'krillpack.py'), 'repack', os.path.join(PRGS, n + '.prg'), binf, newprg)
        print(n, run(os.path.join(TOOLS, 'd64put.py'), OUT_D64, n, newprg).strip())
    sys.path.insert(0, TOOLS)
    from d64read import prg_entries, read_file
    import notrainer
    disk = open(OUT_D64, 'rb').read()
    entry = next(e for e in prg_entries(disk) if e[0] == notrainer.NAME)
    boot = os.path.join(WORK, 'boot_notrainer.prg')
    open(boot, 'wb').write(notrainer.patch(read_file(disk, *entry[1:])))
    print('boot', run(os.path.join(TOOLS, 'd64put.py'), OUT_D64, notrainer.NAME, boot).strip())
    print(f'code ${0x2F60:04X}-${sym["CODEEND"] - 1:04X}, helpers $CBCC-${sym["HELPEND"] - 1:04X}; wrote {OUT_D64}')


if __name__ == '__main__':
    main()
