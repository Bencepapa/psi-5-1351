# Call a game subroutine from the main loop without a stub: wait until PC == $3EE9 (getkey entry,
# called from the menu loop), push $3EE8 as a return address, set registers/memory and PC = target.
# The target's RTS then returns to $3EE9 and the game carries on.
# usage: callsub.py TARGET A=xx "poke1" "poke2" ...   e.g. callsub.py 95ac A=00 "> 002f 46"
import socket, sys, re, time
target = int(sys.argv[1], 16)
regs = dict(a.split('=') for a in sys.argv[2:] if '=' in a and not a.startswith('>'))
pokes = [a for a in sys.argv[2:] if a.startswith('>')]
s = socket.create_connection(('127.0.0.1', 6511), timeout=5)


def rd(t=0.3):
    s.settimeout(t); out = b''
    try:
        while True:
            c = s.recv(65536)
            if not c: break
            out += c
    except socket.timeout:
        pass
    return out.decode('ascii', 'ignore')


def cmd(c, t=0.4):
    s.sendall((c + '\n').encode()); return rd(t)


rd()
cmd('break 3ee9')
s.sendall(b'x\n')
buf = ''
end = time.time() + 10
while time.time() < end and 'BREAK' not in buf and '3ee9' not in buf.lower():
    s.settimeout(0.5)
    try:
        buf += s.recv(65536).decode('ascii', 'ignore')
    except socket.timeout:
        pass
rd(0.3)
cmd('delete')
out = cmd('r')
sp = int(re.search(r'\.;3ee9 \w\w \w\w \w\w (\w\w)', out).group(1), 16)
cmd(f'> {0x100 + sp:04x} 3e')
cmd(f'> {0x100 + sp - 1:04x} e8')
for p in pokes:
    cmd(p)
r = f'r sp={sp - 2:02x}, pc={target:04x}'
for k, v in regs.items():
    r += f', {k.lower()}={v}'
cmd(r)
print('called', hex(target), 'sp was', hex(sp))
s.sendall(b'x\n'); rd(0.2); s.close()
