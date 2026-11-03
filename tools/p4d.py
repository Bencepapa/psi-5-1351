# Psi-5 +4D helper over the VICE remote monitor.
#   p4d.py boot                 start VICE and get to the bridge (course 1)
#   p4d.py keys 45 53           put PETSCII codes (hex) into the keyboard buffer, run a while
#   p4d.py shot NAME            screenshot into the scratchpad
#   p4d.py dump NAME            save all 64 KB of RAM to NAME.bin
#   p4d.py mon "cmd" ...        raw monitor commands
import socket, subprocess, sys, time, os
SP = os.path.dirname(os.path.abspath(__file__))
VICE = r'C:\dev\c64\vice\win\bin\x64sc.exe'
D64 = os.environ.get('PSI_D64', r'C:\dev\c64\psi5\PSI-5 +4D 101% ATA.d64')
MONPORT = int(os.environ.get('MONPORT', '6511'))


def conn():
    for _ in range(40):
        try:
            return socket.create_connection(('127.0.0.1', MONPORT), timeout=5)
        except OSError:
            time.sleep(0.5)
    raise SystemExit('no monitor')


class Mon:
    def __enter__(self):
        self.s = conn(); self.rd(0.5); return self

    def __exit__(self, *a):
        self.s.sendall(b'x\n'); self.rd(0.2); self.s.close()

    def rd(self, t=0.4):
        self.s.settimeout(t); out = b''
        try:
            while True:
                c = self.s.recv(65536)
                if not c: break
                out += c
        except socket.timeout:
            pass
        return out.decode('ascii', 'ignore')

    def cmd(self, c, t=0.5):
        self.s.sendall((c + '\n').encode()); return self.rd(t)

    def run(self, secs):
        self.s.sendall(b'x\n'); time.sleep(secs); self.s.sendall(b'r\n'); self.rd(0.3)


def wait_pc(lo, hi, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        with Mon() as m:
            out = m.cmd('r')
        import re
        mm = re.search(r'\.;([0-9a-f]{4})', out)
        if mm and lo <= int(mm.group(1), 16) <= hi:
            return True
        time.sleep(1)
    return False


def keys(m, codes):
    # the bridge program's key queue: keys at $03CA (max 10), count in $4E (KERNAL buffer is not used;
    # $0277 holds loader code in this version, never write there)
    m.cmd('> 03ca ' + ' '.join(f'{c:02x}' for c in codes))
    m.cmd(f'> 004e {len(codes):02x}')


a = sys.argv[1]
if a == 'boot':
    subprocess.Popen([VICE, '-remotemonitor', '-remotemonitoraddress', f'ip4://127.0.0.1:{MONPORT}',
                      '-controlport2device', '3', '-autostart', D64],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    with Mon() as m:
        m.cmd('warp on')
    wait_pc(0x0915, 0x0928)                       # intro key loop
    with Mon() as m:
        if os.environ.get('LOADLOG'):             # log every loader call (non-stopping traces)
            m.cmd(f'logname "{os.environ["LOADLOG"]}"'); m.cmd('log on')
            for ep in ('0200', '020b'):
                out = m.cmd(f'trace exec {ep}')
                import re as _re
                n = _re.search(r'TRACE: (\d+)', out)
                if n:
                    m.cmd(f'command {n.group(1)} "m 01f0 01ff"')
        m.cmd('> 091d ff'); m.cmd('> 0924 00')
    wait_pc(0x0c80, 0x0d40)                       # trainer prompt
    time.sleep(1)
    with Mon() as m:
        m.cmd('> 0d2d ff')
    # wait for the course list: 'Destination' on the text screen ($0400 here) or anywhere in RAM bank 0
    end = time.time() + 150
    while time.time() < end:
        time.sleep(3)
        with Mon() as m:          # "estinat" as screen codes (lower case set) on the text screen
            out = m.cmd('h 0400 07e7 05 13 14 09 0e 01 14', 1.5)
        found = [l for l in out.splitlines() if l.strip() and not l.startswith('(C:')]
        if found:
            break
    time.sleep(2)
    with Mon() as m:                    # course 1, through the front end's key queue ($CF00, count $62)
        m.cmd('> cf00 31'); m.cmd('> 0062 01')
    time.sleep(15)
    with Mon() as m:
        m.cmd('warp off')
    print('booted')
elif a == 'keys':
    with Mon() as m:
        keys(m, [int(x, 16) for x in sys.argv[2:]])
        m.run(1.5)
elif a == 'shot':
    with Mon() as m:
        m.cmd(f'screenshot "{os.path.join(SP, sys.argv[2])}.png" 2', 2.5)
elif a == 'dump':
    with Mon() as m:
        m.cmd('bank ram')
        m.cmd(f'save "{os.path.join(SP, sys.argv[2])}.bin" 0 0000 ffff', 2)
        m.cmd('bank cpu')
elif a == 'mon':
    with Mon() as m:
        for c in sys.argv[2:]:
            print(m.cmd(c, 1.0), end='')
