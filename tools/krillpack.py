"""Decoder and encoder for the packed files of "PSI-5 +4D 101% ATA.d64" (the loader's on-the-fly LZ).

A PRG file is: 2-byte load address L, then the stream.  The stream is:
    [last byte][x][y]   header: destination pointer P = y:x, the first output byte goes to P+1,
                        and `last byte` is written after the end token (it is the final output byte)
    tokens:
      10nnnnnn      copy n+1 literal bytes that follow           (1..64)
      0eeeeddd + v  match of length (e+2), 2..17 bytes, distance 2048 - (ddd<<8) - v   (1..2048)
      11nnnnnn      match of length 2, distance 255 - c          (c = 0xC0..0xFE: 1..63)
      00            end
The packed data ends at the same address as the unpacked data (in-place unpacking):
    E = L + len(stream) - 1   and the output occupies P+1 .. E.

usage:  python krillpack.py unpack  FILE.prg OUT.bin          (prints the destination address)
        python krillpack.py verify  FILE.prg                  (decode, re-encode, decode again, compare)
        python krillpack.py repack  FILE.prg PATCHED.bin NEW.prg   (PATCHED.bin = same size as the unpacked data)
"""
import sys


def decode(prg):
    L = prg[0] | prg[1] << 8
    s = prg[2:]
    last = s[0]
    p = (s[2] << 8 | s[1]) + 1          # first destination address
    out = bytearray()
    i = 3
    while True:
        c = s[i]
        if c == 0:
            break
        if 0x80 <= c <= 0xBF:
            n = c - 0x7F
            out += s[i + 1:i + 1 + n]
            i += 1 + n
        else:
            if c >= 0xC0:
                d = 255 - c
                n = 2
                i += 1
            else:
                d = 2048 - ((c & 7) << 8) - s[i + 1]
                n = (c >> 3) + 2
                i += 2
            assert 1 <= d <= len(out), (d, len(out), hex(L + i))
            for _ in range(n):
                out.append(out[-d])
    out.append(last)
    return L, p, bytes(out), i + 1


def _matches(data, i, limit):
    """best (length, distance) for each distance class at position i; returns (maxlen2048, bestdist, short2)"""
    best_len, best_d = 0, 0
    short = False
    n = len(data)
    maxl = min(17, limit - i)
    if maxl < 2:
        return 0, 0, False
    b0, b1 = data[i], data[i + 1]
    for d in range(1, min(2048, i) + 1):
        j = i - d
        if data[j] != b0 or data[j + 1] != b1:
            continue
        if d <= 63:
            short = True
        k = 2
        while k < maxl and data[j + k] == data[i + k]:
            k += 1
        if k > best_len:
            best_len, best_d = k, d
            if k == maxl:
                break
    return best_len, best_d, short


def encode_stream(data):
    """returns the stream (header + tokens + end token) for the unpacked `data` (data[-1] goes into the header)"""
    last = data[-1]
    body = data[:-1]
    n = len(body)
    INF = 1 << 30
    cost = [INF] * (n + 1)
    how = [None] * (n + 1)
    cost[0] = 0
    mt = [None] * n
    for i in range(n):
        if i + 1 < n:
            mt[i] = _matches(body, i, n)
    for i in range(n):
        c0 = cost[i]
        if c0 >= INF:
            continue
        for k in range(1, min(64, n - i) + 1):          # literal run of k bytes
            if c0 + 1 + k < cost[i + k]:
                cost[i + k] = c0 + 1 + k
                how[i + k] = ('L', i, k)
        m = mt[i]
        if m:
            ln, d, short = m
            if short:                                   # 1-byte token, length 2, distance 1..63
                # find the smallest distance <= 63 that really matches
                for dd in range(1, min(63, i) + 1):
                    if body[i - dd] == body[i] and body[i - dd + 1] == body[i + 1]:
                        if c0 + 1 < cost[i + 2]:
                            cost[i + 2] = c0 + 1
                            how[i + 2] = ('S', i, dd)
                        break
            for k in range(2, ln + 1):                  # 2-byte token, length k, distance d
                if k == 2 and d > 1792:                 # control byte would be 00 = the end token
                    continue
                if c0 + 2 < cost[i + k]:
                    cost[i + k] = c0 + 2
                    how[i + k] = ('M', i, (k, d))
    toks = []
    pos = n
    while pos > 0:
        t = how[pos]
        toks.append(t)
        pos = t[1]
    toks.reverse()
    out = bytearray()
    for kind, i, arg in toks:
        if kind == 'L':
            out.append(0x80 + arg - 1)
            out += body[i:i + arg]
        elif kind == 'S':
            out.append(255 - arg)
        else:
            k, d = arg
            e = 2048 - d
            out.append(((k - 2) << 3) | (e >> 8))
            out.append(e & 255)
    out.append(0)
    return out, toks


def inplace_ok(L, p, toks, stream_len):
    """simulate: the write pointer must stay below the next unread packed byte"""
    I = 3
    J = 0
    D0 = p
    worst = 1 << 30
    for kind, i, arg in toks:
        if kind == 'L':
            I += 1 + arg
            J += arg
        elif kind == 'S':
            I += 1
            J += 2
        else:
            I += 2
            J += arg[0]
        worst = min(worst, (L + I) - (D0 + J))      # unread bytes start at L+I; next write is at D0+J
    return worst


def encode_prg(p, data, trailer=b''):
    """p = first destination address. The stream ends at the end of the unpacked data (in-place),
    `trailer` = raw bytes the file carries after the end token (loaded as they are, after the data)."""
    E = p + len(data) - 1
    hdr_x, hdr_y = (p - 1) & 255, (p - 1) >> 8
    body, toks = encode_stream(data)
    stream = bytearray([data[-1], hdr_x, hdr_y]) + body
    L = E - len(stream) + 1
    return bytes([L & 255, L >> 8]) + bytes(stream) + bytes(trailer), L, toks


def main():
    a = sys.argv
    if a[1] == 'unpack':
        L, p, out, used = decode(open(a[2], 'rb').read())
        open(a[3], 'wb').write(out)
        print(f'load ${L:04X}, destination ${p:04X}-${p + len(out) - 1:04X} ({len(out)} bytes), stream {used} bytes')
    elif a[1] == 'verify':
        prg = open(a[2], 'rb').read()
        L, p, out, used = decode(prg)
        E = L + used - 1
        print(f'orig: load ${L:04X}, dest ${p:04X}-${p + len(out) - 1:04X}, packed {used}, E=${E:04X} '
              f'({"in-place end matches" if E == p + len(out) - 1 else "END MISMATCH"})')
        trailer = prg[2 + used:]
        new, L2, toks = encode_prg(p, out, trailer)
        L3, p3, out3, used3 = decode(new)
        print(f'new : load ${L2:04X}, packed {used3} (orig {used}), trailer {len(trailer)} bytes, '
              f'roundtrip {"OK" if out3 == out and p3 == p and new[2 + used3:] == trailer else "FAIL"}, '
              f'in-place slack {inplace_ok(L2, p, toks, used3)}')
    elif a[1] == 'repack':
        prg = open(a[2], 'rb').read()
        L, p, out, used = decode(prg)
        patched = open(a[3], 'rb').read()
        assert len(patched) == len(out), 'patched data must have the same size as the unpacked data'
        new, L2, toks = encode_prg(p, patched, prg[2 + used:])
        slack = inplace_ok(L2, p, toks, len(new) - 2)
        print(f'repacked: load ${L2:04X} (orig ${L:04X}), {len(new) - 2} bytes (orig {used}), in-place slack {slack}')
        assert slack >= 0, 'in-place unpacking would overwrite unread data'
        open(a[4], 'wb').write(new)


if __name__ == '__main__':
    main()
