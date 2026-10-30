# Snapshot of the running game at the bridge (VICE remote monitor on 6511), stopped at the menu
# loop's getkey ($3EE9): snapb_ram.bin, snapb_col.bin, snapb_io.txt, snapb_cpu.txt.
# efbuild.py --bridge builds a test cartridge that starts there directly.
import os, re, socket, time
HERE = os.path.dirname(os.path.abspath(__file__))
s = socket.create_connection(('127.0.0.1', 6511), timeout=5)


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
cmd('break 3ee9')
s.sendall(b'x\n')
buf = ''
end = time.time() + 20
while time.time() < end and '3ee9' not in buf.lower():
    try:
        s.settimeout(1); buf += s.recv(1 << 16).decode('ascii', 'ignore')
    except socket.timeout:
        pass
rd()
cmd('delete')
cpu = cmd('r')
open(os.path.join(HERE, 'snapb_cpu.txt'), 'w').write(cpu)
cmd('bank ram')
cmd(f'save "{os.path.join(HERE, "snapb_ram.bin")}" 0 0000 ffff', 3)
cmd('bank io')
cmd(f'save "{os.path.join(HERE, "snapb_col.bin")}" 0 d800 dbff', 2)
io = cmd('m d000 d02f', 1) + cmd('m dc00 dc0f', 1) + cmd('m dd00 dd0f', 1)
cmd('bank cpu')
open(os.path.join(HERE, 'snapb_io.txt'), 'w').write(io)
print(cpu)
s.sendall(b'x\n'); rd(); s.close()
