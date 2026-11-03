# Watch who writes the de message region in a running VICE (v3 disk).
# usage: python watch_de.py            (expects a stopped monitor on MONPORT, then resumes)
# Sets store watches on $EFB8 and $FB5A, resumes, logs each hit's PC and context,
# then continues. Also logs $020B load+unpack entries.
import os, re, socket, sys, time

PORT = int(os.environ.get('MONPORT', '6511'))
LOG = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'watch_de.log'), 'w')


def log(*a):
    print(*a)
    print(*a, file=LOG, flush=True)


class Mon:
    def __enter__(self):
        self.s = socket.create_connection(('127.0.0.1', PORT), timeout=5)
        self.rd(0.5)
        return self

    def __exit__(self, *a):
        self.s.sendall(b'x\n')
        self.rd(0.2)
        self.s.close()

    def rd(self, t=0.5):
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


def main():
    with Mon() as m:
        for c in ('watch store efb8', 'watch store fb5a', 'break 020b'):
            log('>>', c, m.cmd(c, 0.5).strip())
        m.s.sendall(b'x\n')          # resume
        m.rd(0.3)
        stops = 0
        while stops < 40:
            m.s.settimeout(30)
            try:
                buf = b''
                while b'(C:$' not in buf:
                    c = m.s.recv(65536)
                    if not c:
                        return
                    buf += c
            except socket.timeout:
                log('--- 30s without a stop ---')
                continue
            text = buf.decode('ascii', 'ignore')
            log('STOP:', text.strip()[:400])
            pc = re.search(r'\.;([0-9a-f]{4})', text)
            if pc:
                p = int(pc.group(1), 16)
                if p == 0x020B:
                    log(' load entry: registers above; continuing')
                    m.cmd('x' if False else '', 0)  # no-op
                    m.s.sendall(b'x\n')
                    m.rd(0.2)
                    stops += 1
                    continue
                d = m.cmd(f'd {p - 12:04x} {p + 4:04x}', 0.6)
                r = m.cmd('r', 0.4)
                m8 = m.cmd('m efb8 efc0', 0.4)
                m2 = m.cmd('m fb5a fb62', 0.4)
                log(' pc context:\n' + d + r + m8 + m2)
            m.s.sendall(b'x\n')      # continue
            m.rd(0.2)
            stops += 1
        for c in ('delete 1', 'delete 2', 'delete 3'):
            m.cmd(c, 0.3)


if __name__ == '__main__':
    main()
