# Trace the post-crew-accept load sequence on the running VICE session.
# Prereq: a VICE session at the crew selection screen (front-end loop $1E9x),
# remote monitor on MONPORT. Sets break $020B + store watches on $EFB8/$FB5A,
# injects the crew selection through the front-end queue, and logs every stop:
# load names (X/Y pointer + $B7), the depacker source pointer, and key memory.
import os, re, socket, sys, time

PORT = int(os.environ.get('MONPORT', '6511'))
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = open(os.path.join(HERE, 'loadtrace.log'), 'w', encoding='utf8')


def log(*a):
    print(*a)
    print(*a, file=LOG, flush=True)


class Mon:
    def __init__(self):
        self.s = socket.create_connection(('127.0.0.1', PORT), timeout=5)
        self.rd(0.5)

    def rd(self, t=0.4):
        self.s.settimeout(t)
        out = b''
        try:
            while True:
                c = self.s.recv(65536)
                if not c:
                    break
                out += c
        except socket.timeout:
            pass
        return out.decode('ascii', 'ignore')

    def cmd(self, c, t=0.5):
        self.s.sendall((c + '\n').encode())
        return self.rd(t)


REG = re.compile(r'A:([0-9A-Fa-f]{2}) X:([0-9A-Fa-f]{2}) Y:([0-9A-Fa-f]{2})')


def handle_stop(m, text, state):
    """A checkpoint stopped the machine; gather info and resume."""
    pc = re.search(r'\(C:\$?([0-9a-f]{4})\)\s*$', text.strip())
    pcm = re.search(r'\.C:([0-9a-f]{4})\s+[0-9A-Fa-f]{2}\s', text)
    addr = int((pc or pcm).group(1), 16) if (pc or pcm) else None
    regs = REG.search(text)
    a = x = y = None
    if regs:
        a, x, y = (int(g, 16) for g in regs.groups())
    if addr == 0x020B:
        # load+unpack entry: name pointer in X/Y, length at $B7
        for label, ptr in (('YX', (y << 8) | x if y is not None and x is not None else None),
                           ('XY', (x << 8) | y if y is not None and x is not None else None)):
            if ptr is None:
                continue
            dump = m.cmd(f'm {ptr:04x} {ptr + 15:04x}', 0.4)
            hexes = re.findall(r'>C:[0-9a-f]{4}\s+((?:[0-9a-f]{2}\s*)+)', dump)
            bs = bytes(int(h, 16) for h in (' '.join(hexes)).split())
            if bs and all(32 <= b < 91 or b in (0,) for b in bs[:4]) and bs[0] != 0xFF:
                log(f'LOAD name@{label}=${ptr:04x}: {bs!r} len={m.cmd("m 00b7 00b7", 0.3)}')
                break
        else:
            log(f'LOAD (name not decoded) A={a:02X} X={x:02X} Y={y:02X}')
        log(m.cmd('m 01f0 01ff', 0.3).strip())
    else:
        log(f'WATCH/OTHER stop at ${addr:04X}: {text.strip()[:200]}')
        # depacker source pointer and the bytes around the write target
        log(m.cmd('r', 0.3).strip())
        log(m.cmd('m 00f0 00ff', 0.3).strip())       # depacker zp: $F2/$F3 = source ptr
        log(m.cmd('m efb8 efc0', 0.3).strip())
        log(m.cmd('m fb5a fb62', 0.3).strip())
    m.s.sendall(b'x\n')
    m.rd(0.2)
    state['stops'] += 1


def drain(m, seconds, state):
    end = time.time() + seconds
    while time.time() < end and state['stops'] < 80:
        chunk = m.rd(1.0)
        if '(C:$' in chunk and ('Stop on' in chunk or 'BREAK' in chunk or 'Watch' in chunk or 'watch' in chunk):
            handle_stop(m, chunk, state)
        elif chunk.strip():
            log('OTHER OUTPUT:', chunk.strip()[:200])
        if 'JAM' in chunk or 'jam' in chunk:
            log('JAM DETECTED')
            return False
    return True


def main():
    m = Mon()
    state = {'stops': 0}
    log('== loadtrace start ==')
    log(m.cmd('r', 0.4).strip())
    for c in ('break 020b', 'watch store efb8', 'watch store fb5a'):
        log('>>', c, m.cmd(c, 0.4).strip())
    m.s.sendall(b'x\n')
    m.rd(0.3)
    # crew selection through the front-end key queue ($CF00, count $62)
    for i in range(5):
        m.cmd('> cf00 0d')
        m.cmd('> 0062 01')
        if not drain(m, 2.5, state):
            break
        m.cmd('> cf00 57')
        m.cmd('> 0062 01')
        if not drain(m, 3.5, state):
            break
        log(f'-- crew member {i + 1} done, stops so far {state["stops"]} --')
    m.cmd('> cf00 0d')      # accept the crew
    m.cmd('> 0062 01')
    log('-- crew accepted; watching the load sequence --')
    m.cmd('warp on', 0.3)
    m.s.sendall(b'x\n') if False else None
    drain(m, 90, state)
    log('== final state ==')
    log(m.cmd('r', 0.4).strip())
    for c in ('m efb8 efc0', 'm fb5a fb62', 'm 2f60 2f70', 'm 8f2d 8f2f', 'm 8258 825d'):
        log(m.cmd(c, 0.4).strip())
    m.cmd('warp off', 0.3)
    for i in (1, 2, 3):
        m.cmd(f'delete {i}', 0.3)
    m.s.sendall(b'x\n')
    m.rd(0.3)
    log('== loadtrace end, stops:', state['stops'], '==')


if __name__ == '__main__':
    main()
