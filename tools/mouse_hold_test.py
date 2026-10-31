import socket
import time


def read_all(s, wait=0.4):
    s.settimeout(wait)
    out = b''
    try:
        while True:
            part = s.recv(65536)
            if not part:
                break
            out += part
    except socket.timeout:
        pass
    return out.decode('ascii', 'ignore')


s = socket.create_connection(('127.0.0.1', 6511), timeout=5)
read_all(s)
for cmd in ('> 028e 01', '> 0292 16', '> 028b b0', '> 02a7 00', '> 02a3 00', '> dffa 10', 'break 808e'):
    s.sendall((cmd + chr(10)).encode())
    read_all(s)
s.sendall(b'x' + chr(10).encode())
time.sleep(0.1)
s.sendall(b'r' + chr(10).encode())
print(read_all(s, 1.0))
s.sendall(b'm 028e 02a7' + chr(10).encode())
print(read_all(s, 1.0))
s.sendall(b'> 0294 01' + chr(10).encode())
read_all(s)
s.sendall(b'delete 1' + chr(10).encode())
read_all(s)
s.sendall(b'break 80bd' + chr(10).encode())
read_all(s)
s.sendall(b'x' + chr(10).encode())
time.sleep(0.1)
s.sendall(b'r' + chr(10).encode())
print(read_all(s, 1.0))
s.sendall(b'm d8a0 d8f7' + chr(10).encode())
print(read_all(s, 1.0))
s.sendall(b'm db70 db97' + chr(10).encode())
print(read_all(s, 1.0))
s.sendall(b'm dffa dfff' + chr(10).encode())
print(read_all(s, 1.0))
s.sendall(b'screenshot "tools/drag_row22.png" 2' + chr(10).encode())
print(read_all(s, 2.5))
s.sendall(b'delete 1' + chr(10).encode())
read_all(s)
s.sendall(b'x' + chr(10).encode())
read_all(s)
s.close()
