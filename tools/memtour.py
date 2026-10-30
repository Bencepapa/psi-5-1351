# Run-time access test: trace (non-stopping) load/store checkpoints on candidate areas while touring
# every department, then report which areas were touched and by which code.
# Run on the bridge (after tobridge.sh). usage: python memtour.py [extra_wait_seconds]
import socket, sys, time, re, collections
AREAS = [(0x0334, 0x0373), (0xCBCC, 0xCC3F), (0x4300, 0x4DFF),
         (0x3500, 0x35FF), (0x1F00, 0x1FFF), (0x2F00, 0x30FF)]
# keys (bridge queue) with waits: every department, Status and Display, ? and Ack, back with <-
TOUR = [('44', 2), ('14', 2), ('57', 2), ('53', 2), ('44', 2), ('2f', 2), ('14', 2),
        ('53', 2), ('53', 2), ('44', 2), ('14', 2), ('4e', 2), ('53', 2), ('44', 2), ('14', 2),
        ('52', 2), ('53', 2), ('44', 2), ('14', 2), ('41', 3), ('45', 2), ('53', 2), ('44', 2)]
extra = float(sys.argv[1]) if len(sys.argv) > 1 else 60
s = socket.create_connection(('127.0.0.1', 6511), timeout=5)
log = ''


def rd(t=0.3):
    global log
    s.settimeout(t); out = b''
    try:
        while True:
            c = s.recv(1 << 16)
            if not c: break
            out += c
    except socket.timeout:
        pass
    txt = out.decode('ascii', 'ignore'); log += txt
    return txt


def cmd(c, t=0.4):
    s.sendall((c + '\n').encode()); return rd(t)


rd()
num = {}
for i, (a, b) in enumerate(AREAS):
    for kind in ('load', 'store'):
        out = cmd(f'trace {kind} {a:04x} {b:04x}')
        m = re.search(r'TRACE: (\d+)', out)
        if m:
            num[int(m.group(1))] = (a, b, kind)
print('checkpoints', num)
cmd('warp on')


def run(secs):
    s.sendall(b'x\n')
    end = time.time() + secs
    while time.time() < end:
        rd(0.5)
    s.sendall(b'r\n'); rd(0.3)


for k, w in TOUR:
    cmd(f'> 03ca {k}'); cmd('> 004e 01')
    run(w); print('key', k, 'log', len(log), flush=True)
run(extra)
cmd('delete'); cmd('warp off')
s.sendall(b'x\n'); rd(0.3); s.close()
open('memtour.log', 'w').write(log)
hits = collections.defaultdict(collections.Counter)
for m in re.finditer(r'#(\d+) \(Trace\s+(load|store)\s+([0-9a-f]{4})[^)]*\)[^\n]*\n?\s*\.?C?:?([0-9a-f]{4})?', log, re.I):
    n = int(m.group(1))
    if n in num:
        hits[num[n]][m.group(4) or '?'] += 1
print('dropped as busy:', sorted(num[n] for n in dropped if n in num))
for (a, b, kind) in sorted(set(num.values())):
    h = hits.get((a, b, kind))
    print(f'{a:04x}-{b:04x} {kind:5}: ' + (f'{sum(h.values())} hits, PCs {dict(h.most_common(6))}' if h else 'untouched'))
