# Marker test: fill candidate areas with $55, tour every department with injected keys (warp),
# then report which bytes changed. Run on the bridge (after tobridge.sh).
# usage: python filltour.py [extra_wait_seconds]
import socket, sys, time, re, os
AREAS = [tuple(int(x, 16) for x in a.split("-")) for a in os.environ.get("AREAS", "CBCC-CC3F,2F60-30A0").split(",")]
TOUR = ['44', '14', '57', '53', '44', '2f', '14', '53', '53', '44', '14', '4e', '53', '44', '14',
        '52', '53', '44', '14', '41', '45', '53', '44']
extra = float(sys.argv[1]) if len(sys.argv) > 1 else 60
s = socket.create_connection(('127.0.0.1', 6511), timeout=5)


def rd(t=0.3):
    s.settimeout(t); out = b''; end = time.time() + 3
    try:
        while time.time() < end:
            c = s.recv(1 << 16)
            if not c: break
            out += c
    except socket.timeout:
        pass
    return out.decode('ascii', 'ignore')


def cmd(c, t=0.4):
    s.sendall((c + '\n').encode()); return rd(t)


def run(secs):
    s.sendall(b'x\n'); time.sleep(secs); s.sendall(b'r\n'); rd(0.3)


rd()
for a, b in AREAS:
    cmd(f'f {a:04x} {b:04x} 55')
cmd('warp on')
for k in TOUR:
    cmd(f'> 03ca {k}'); cmd('> 004e 01')
    run(1.5)
run(extra)
cmd('warp off')
for a, b in AREAS:
    out = cmd(f'm {a:04x} {b:04x}', 1.0)
    bad = []
    for line in out.splitlines():
        m = re.match(r'>C:([0-9a-f]{4})\s+((?:[0-9a-f]{2}\s+)+)', line)
        if m:
            base = int(m.group(1), 16)
            bad += [base + k for k, h in enumerate(m.group(2).split()) if h != '55' and base + k <= b]
    print(f'{a:04x}-{b:04x}: {len(bad)} bytes changed' + (f', first {hex(bad[0])} last {hex(bad[-1])}' if bad else ''))
s.sendall(b'x\n'); rd(0.2); s.close()
