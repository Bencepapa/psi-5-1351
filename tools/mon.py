# VICE remote monitor client. usage: mon.py cmd1 cmd2 ...   (always resumes with x at the end)
# special: "sleep N" (resume, wait N s, re-enter), "WAIT" (resume until a checkpoint stops)
import socket, sys, time, os
s = socket.create_connection(('127.0.0.1', int(os.environ.get('MONPORT', '6511'))), timeout=5)
def rd(t=0.5):
    s.settimeout(t); out = b''
    try:
        while True:
            c = s.recv(65536)
            if not c: break
            out += c
    except socket.timeout: pass
    return out.decode('ascii', 'ignore')
rd(0.5)
for c in sys.argv[1:]:
    if c.startswith('sleep '):
        s.sendall(b'x\n'); time.sleep(float(c[6:])); s.sendall(b'r\n'); rd(0.5); continue
    if c == 'WAIT':
        s.sendall(b'x\n'); s.settimeout(30); buf = b''
        while b'(C:$' not in buf: buf += s.recv(65536)
        print(buf.decode('ascii', 'ignore')); rd(0.3); continue
    s.sendall((c + '\n').encode()); print(rd(2.5 if c.startswith('screenshot') else 0.8), end='')
s.sendall(b'x\n'); rd(0.3); s.close()
