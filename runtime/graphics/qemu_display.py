"""Send original HMI readback to the native QEMU console and return its inputs."""
import json
import os
import socket
import struct
import threading
import urllib.request
class QemuDisplay:
    def __init__(self):
        self.path=os.environ.get('MIB_QEMU_DISPLAY','/tmp/mib-qemu-display.sock');self.sock=None
    def send(self,rgba):
        try:
            if self.sock is None:
                sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(.5);sock.connect(self.path)
                self.sock=sock;threading.Thread(target=self.inputs,args=(sock,),daemon=True).start()
            self.sock.sendall(b'MIBF'+struct.pack('<I',len(rgba))+rgba)
        except OSError:
            if self.sock:self.sock.close()
            self.sock=None
    def inputs(self,sock):
        buffer=b''
        while True:
            try:data=sock.recv(4096)
            except socket.timeout:continue
            except OSError:return
            if not data:return
            buffer+=data
            if len(buffer)>8192:return
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1)
                try:
                    json.loads(line)
                    request=urllib.request.Request('http://127.0.0.1:8767/input',data=line,headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(request,timeout=1) as response:response.read()
                except Exception as exc:print('QEMU input:',exc,flush=True)
