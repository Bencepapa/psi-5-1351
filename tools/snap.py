# Boot "PSI-5 +4D 101% ATA.d64" in VICE and stop at the first loader call ($0200):
# save 64 KB RAM (snap_ram.bin), I/O registers (snap_io.txt) and CPU registers (snap_cpu.txt).
import os, re, socket, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
VICE = r'C:\dev\c64\vice\win\bin\x64sc.exe'
D64 = r'C:\dev\c64\psi5\PSI-5 +4D 101% ATA.d64'

subprocess.Popen([VICE, '-remotemonitor', '-remotemonitoraddress', 'ip4://127.0.0.1:6511',
                  '-controlport2device', '1', '-autostart', D64], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)
for _ in range(40):
    try:
        s = socket.create_connection(('127.0.0.1', 6511), timeout=5); break
    except OSError:
        time.sleep(0.5)


def rd(t=0.4):
    s.settimeout(t); out = b''; end = time.time() + 5
    try:
        while time.time() < end:
            c = s.recv(1 << 16)
            if not c: break
            out += c
    except socket.timeout:
        pass
    return out.decode('ascii', 'ignore')


def cmd(c, t=0.5):
    s.sendall((c + '\n').encode()); return rd(t)


rd()
cmd('warp on')
# wait for the intro key loop, then let it through
while True:
    pc = re.search(r'\.;([0-9a-f]{4})', cmd('r')).group(1)
    if 0x0915 <= int(pc, 16) <= 0x0928:
        break
    s.sendall(b'x\n'); time.sleep(1); s.sendall(b'r\n'); rd()
cmd('> 091d ff'); cmd('> 0924 00')
cmd('break 0200')
s.sendall(b'x\n')
buf = ''
end = time.time() + 120
while time.time() < end and 'C:$0200' not in buf and '.C:0200' not in buf:
    try:
        s.settimeout(1); buf += s.recv(1 << 16).decode('ascii', 'ignore')
    except socket.timeout:
        pass
rd()
cmd('delete')
cpu = cmd('r')
open(os.path.join(HERE, 'snap_cpu.txt'), 'w').write(cpu)
cmd('bank ram')
cmd(f'save "{os.path.join(HERE, "snap_ram.bin")}" 0 0000 ffff', 3)
cmd('bank io')
cmd(f'save "{os.path.join(HERE, "snap_col.bin")}" 0 d800 dbff', 2)
io = cmd('m d000 d02f', 1) + cmd('m d400 d41f', 1) + cmd('m dc00 dc0f', 1) + cmd('m dd00 dd0f', 1)
cmd('bank cpu')
io += cmd('m 0000 0001', 1)
open(os.path.join(HERE, 'snap_io.txt'), 'w').write(io)
cmd('warp off')
print(cpu)
print(io)
s.sendall(b'x\n'); rd(); s.close()
