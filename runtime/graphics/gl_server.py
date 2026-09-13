"""Loopback graphics RPC server. Executes guest commands on a Mac GPU context."""
import ctypes as C
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time
from qemu_display import QemuDisplay
qemu_display=QemuDisplay()
from mac_renderer import MacRenderer, U, I, P

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from mib_display_receiver import png
MANIFEST=json.loads(Path(__file__).with_name('gl_manifest.json').read_text())

def exact(sock,count):
    data=bytearray()
    while len(data)<count:
        part=sock.recv(count-len(data))
        if not part: raise EOFError()
        data.extend(part)
    return bytes(data)

def command_header(sock,timeout=120):
    """Allow idle displays, but bound partially transmitted commands."""
    sock.settimeout(None)
    first=exact(sock,1)
    sock.settimeout(timeout)
    return struct.unpack('<II',first+exact(sock,7))

def scalar(typ,data):
    if typ in ('GLfloat','GLclampf'): return C.c_float,struct.unpack('<f',data)[0]
    signed=typ in ('GLint','GLsizei','GLsizeiptr','GLintptr')
    value=int.from_bytes(data,'little',signed=signed)
    if typ in ('GLsizeiptr','GLintptr'): return C.c_ssize_t,value
    if typ=='GLboolean': return C.c_ubyte,value
    return (I if signed else U),value

class Bridge:
    def __init__(self):
        self.renderer=MacRenderer()
        self.frames=0
        self.commands=0
        self.started=time.monotonic()
        self.execute_seconds=0.0
        self.last_png_raw=None
        # Keep detailed tracing opt-in: thousands of synchronous writes per menu.
        self.trace=os.environ.get('MIB_GL_TRACE')=='1'
        self.log=(ROOT/'reports/gl-host-calls.log').open('w',buffering=65536)

    def execute(self,op,items):
        self.commands+=1
        if op==0:
            raw=self.renderer.read_rgba()
            self.frames+=1
            qemu_display.send(raw)
            if raw!=self.last_png_raw:
                temp=ROOT/'reports/hmi-render.png.tmp'
                temp.write_bytes(png(800,480,raw))
                temp.replace(ROOT/'reports/hmi-render.png')
                self.last_png_raw=raw
            status=ROOT/'reports/hmi-render-status.json.tmp'
            status.write_text(json.dumps(dict(
                source='QNX HMI GLES command bridge',frames=self.frames,
                commands=self.commands,last_frame=time.time(),
                bridge_execute_seconds=round(self.execute_seconds,4),
                bridge_uptime_seconds=round(time.monotonic()-self.started,4)),indent=2))
            status.replace(ROOT/'reports/hmi-render-status.json')
            self.log.write(f'swap frame={self.frames}\n')
            self.log.flush()
            return 0,b'',[]
        spec=MANIFEST[str(op)]
        if not spec['supported'] or len(items)!=len(spec['params']):
            raise ValueError('Unsupported command or argument count')
        name=spec['name']
        if self.trace:self.log.write(name+'\n')
        args=[];types=[];outputs=[];keep=[]
        for (typ,_),(mode,size,data) in zip(spec['params'],items):
            if mode==0:
                if '*' in typ:
                    types.append(P);args.append(int.from_bytes(data,'little'))
                else:
                    t,value=scalar(typ,data);types.append(t);args.append(value)
            elif mode in (1,2):
                types.append(P)
                if size:
                    buf=C.create_string_buffer(max(size,256))
                    if mode==1:C.memmove(buf,data,size)
                    args.append(C.cast(buf,P));keep.append(buf)
                else:buf=None;args.append(None)
                if mode==2:outputs.append((buf,size))
            else:raise ValueError('Invalid argument mode')
        extra=b''
        if name=='glGetString':
            strings={0x1F00:b'Apple',0x1F01:b'MIB Mac GPU bridge',
                     0x1F02:b'OpenGL ES 2.0 (desktop translation)',
                     0x8B8C:b'OpenGL ES GLSL ES 1.00',0x1F03:b''}
            extra=strings.get(args[0],b'')+b'\0';result=0
        elif name=='glShaderSource':
            text=items[2][2].rstrip(b'\0').decode()
            translated=self.renderer.translate_shader(text).encode()
            pointer=C.c_char_p(translated);length=I(len(translated))
            self.renderer._call(name,None,[U,I,C.POINTER(C.c_char_p),C.POINTER(I)],
                                args[0],1,C.byref(pointer),C.byref(length))
            result=0
        elif name=='glGetShaderPrecisionFormat':
            C.memmove(outputs[0][0],struct.pack('<ii',127,127),8)
            C.memmove(outputs[1][0],struct.pack('<i',23),4);result=0
        elif name=='glGetIntegerv' and args[0] in (0x8DFA,0x8DF9,0x8DFB,0x8DFC,0x8DFD,0x86A2):
            values={0x8DFA:1,0x8DF9:0,0x8DFB:128,0x8DFC:8,0x8DFD:16,0x86A2:0}
            C.memmove(outputs[0][0],struct.pack('<i',values[args[0]]),4);result=0
        else:
            if name=='glBindFramebuffer' and args[1]==0:args[1]=self.renderer.framebuffer.value
            if name=='glDepthRangef':name='glDepthRange';types=[C.c_double,C.c_double]
            if name=='glClearDepthf':name='glClearDepth';types=[C.c_double]
            if 'Framebuffer' in name or 'Renderbuffer' in name:name+='EXT'
            result_type=None if spec['result']=='void' else I if spec['result']=='GLint' else U
            result=self.renderer._call(name,result_type,types,*args) or 0
        return result & 0xffffffff,extra,[bytes(buf[:size]) if buf else b'' for buf,size in outputs]

    def close(self):
        self.renderer.close();self.log.close()

def serve(port=8768):
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        server.bind(('127.0.0.1',port));server.listen(1)
        print(f'Mac GL bridge on 127.0.0.1:{port}',flush=True)
        while True:
            connection,_=server.accept()
            connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            bridge=Bridge()
            try:
                with connection:
                    while True:
                        # A static menu can be idle indefinitely. Retain its GL
                        # context; only an incomplete command should time out.
                        op,count=command_header(connection)
                        if count>16:raise ValueError('Too many arguments')
                        items=[]
                        for _ in range(count):
                            mode,size=struct.unpack('<II',exact(connection,8))
                            if size>64*1024*1024:raise ValueError('Argument too large')
                            items.append((mode,size,exact(connection,size) if mode!=2 else b''))
                        before=time.monotonic()
                        result,extra,outputs=bridge.execute(op,items)
                        bridge.execute_seconds+=time.monotonic()-before
                        reply=struct.pack('<II',result,len(extra))+extra
                        for output in outputs:reply+=struct.pack('<I',len(output))+output
                        connection.sendall(reply)
            except EOFError:print('Guest disconnected',flush=True)
            except Exception as exc:
                bridge.log.write(f'FAIL: {type(exc).__name__}: {exc}\n')
                print(f'GL bridge failed: {exc}',flush=True)
            finally:bridge.close()

if __name__=='__main__':serve()
