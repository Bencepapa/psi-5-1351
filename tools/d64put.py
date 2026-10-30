"""Replace the contents of a PRG file inside a D64 image, keeping its directory entry.

usage: python d64put.py DISK.d64 "file name" NEW.prg [OUT.d64]
The file keeps its first sectors; sectors that are no longer needed are freed in the BAM,
extra sectors (if the new file is longer) are taken from free sectors of the BAM, nearest tracks first.
"""
import sys

SPT = [0] + [21] * 17 + [19] * 7 + [18] * 6 + [17] * 10


def ts_off(t, s):
    return (sum(SPT[1:t]) + s) * 256


def find_entry(d, name):
    """returns (offset of the directory entry, first track, first sector)"""
    t, s = 18, 1
    while t:
        o = ts_off(t, s)
        for i in range(8):
            e = o + i * 32
            if d[e + 2] & 7 == 2 and bytes(d[e + 5:e + 21]).rstrip(b'\xa0').decode('latin1').lower() == name.lower():
                return e, d[e + 3], d[e + 4]
        t, s = d[o], d[o + 1]
    raise KeyError(name)


def chain(d, t, s):
    out = []
    while t:
        out.append((t, s))
        o = ts_off(t, s)
        t, s = d[o], d[o + 1]
    return out


def bam_free(d, t, s):
    o = ts_off(18, 0) + 4 * t
    if not d[o + 1 + s // 8] & (1 << (s % 8)):
        d[o + 1 + s // 8] |= 1 << (s % 8)
        d[o] += 1


def bam_take(d, t, s):
    o = ts_off(18, 0) + 4 * t
    assert d[o + 1 + s // 8] & (1 << (s % 8))
    d[o + 1 + s // 8] &= ~(1 << (s % 8))
    d[o] -= 1


def find_free(d, near):
    order = sorted((t for t in range(1, 36) if t != 18), key=lambda t: (abs(t - near), t))
    for t in order:
        o = ts_off(18, 0) + 4 * t
        for s in range(SPT[t]):
            if d[o + 1 + s // 8] & (1 << (s % 8)):
                return t, s
    raise SystemExit('disk full')


def put(d, name, data):
    e, t, s = find_entry(d, name)
    old = chain(d, t, s)
    need = max(1, -(-len(data) // 254))
    secs = list(old[:need])
    for _ in range(need - len(old)):
        ts = find_free(d, secs[-1][0])
        bam_take(d, *ts)
        secs.append(ts)
    for ts in old[need:]:
        bam_free(d, *ts)
    for k, (t, s) in enumerate(secs):
        o = ts_off(t, s)
        chunk = data[k * 254:(k + 1) * 254]
        d[o + 2:o + 2 + 254] = chunk.ljust(254, b'\0')
        if k + 1 < len(secs):
            d[o], d[o + 1] = secs[k + 1]
        else:
            d[o], d[o + 1] = 0, len(chunk) + 1
    d[e + 28], d[e + 29] = need & 255, need >> 8
    return len(old), need


if __name__ == '__main__':
    disk = bytearray(open(sys.argv[1], 'rb').read())
    old, need = put(disk, sys.argv[2], open(sys.argv[3], 'rb').read())
    out = sys.argv[4] if len(sys.argv) > 4 else sys.argv[1]
    open(out, 'wb').write(disk)
    print(f'{sys.argv[2]}: {old} -> {need} sectors, wrote {out}')
