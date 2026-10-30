# Set a checkpoint, inject keys into the bridge key queue, and report the first few hits (PC + registers).
# usage: catch.py "watch load 042e" KEYHEX [KEYHEX...] [--n 3]
import socket, sys, time, re
args = sys.argv[1:]
n = 3
if '--n' in args:
    i = args.index('--n'); n = int(args[i + 1]); del args[i:i + 2]
chk, keys = args[0], [int(k, 16) for k in args[1:]]
s = socket.create_connection(('127.0.0.1', 6511), timeout=5)


def rd(t=0.4):
    s.settimeout(t); out = b''
    try:
        while True:
            c = s.recv(65536)
            if not c: break
            out += c
    except socket.timeout:
        pass
    return out.decode('ascii', 'ignore')


def cmd(c, t=0.5):
    s.sendall((c + '\n').encode()); return rd(t)


rd()
cmd(chk)
hits = []
for k in keys:
    cmd(f'> 03ca {k:02x}'); cmd('> 004e 01')
    s.sendall(b'x\n')
    end = time.time() + 3
    buf = ''
    while time.time() < end and len(hits) < n:
        s.settimeout(0.3)
        try:
            buf += s.recv(65536).decode('ascii', 'ignore')
        except socket.timeout:
            continue
        if '(C:$' in buf:
            m = re.findall(r'\.C:([0-9a-f]{4})\s+(.*?)\s+- A:(\w\w) X:(\w\w) Y:(\w\w)', buf)
            if m:
                hits.append(m[-1])
                print('hit', m[-1])
                print(cmd('bt', 0.6) if False else '', end='')
                stack = cmd('m 0100 01ff', 0.6)
                sp = re.search(r'SP:(\w\w)', buf)
                if sp:
                    spv = int(sp.group(1), 16)
                    print('  stack top:', ''.join(l for l in stack.splitlines() if l.startswith(f'>C:01{(spv + 1) & 0xf0:02x}'))[:80])
            buf = ''
            if len(hits) >= n:
                break
            s.sendall(b'x\n')
    s.sendall(b'r\n'); rd(0.3)
cmd('delete')
s.sendall(b'x\n'); rd(0.2); s.close()
