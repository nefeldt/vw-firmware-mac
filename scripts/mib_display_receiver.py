#!/usr/bin/env python3
"""Local QNX framebuffer viewer. No simulated HMI; accepts Screen RGBA frames."""
import http.server
import json
from pathlib import Path
import socketserver
import struct
import threading
import time
import zlib
from mib_input import hub

ROOT = Path(__file__).resolve().parent.parent
lock = threading.Lock()
state = {'frames': 0, 'source': 'QNX Screen transport diagnostic', 'last_frame': None}
frame = b''
def restore_frame():
    """Show the last diagnostic frame after a receiver restart, marked as saved."""
    global frame
    image_path = ROOT/'reports/qnx-display.png'
    status_path = ROOT/'reports/qnx-display-status.json'
    if not image_path.exists():
        return
    saved = image_path.read_bytes()
    if not saved.startswith(b'\x89PNG\r\n\x1a\n'):
        return
    try:
        metadata = json.loads(status_path.read_text())
    except (OSError, ValueError):
        metadata = {}
    frame = saved
    state.update(frames=max(1, int(metadata.get('frames', 1))),
                 last_frame=metadata.get('last_frame') or image_path.stat().st_mtime,
                 saved=True)
def chunk(kind, data):
    return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
def png(w, h, raw):
    scan = b''.join(b'\0' + raw[y*w*4:(y+1)*w*4] for y in range(h))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', w,h,8,6,0,0,0)) + chunk(b'IDAT', zlib.compress(scan, 1)) + chunk(b'IEND', b'')
def exact(sock, n):
    result = bytearray()
    while len(result)<n:
        part=sock.recv(n-len(result))
        if not part: raise EOFError('Incomplete guest frame')
        result.extend(part)
    return bytes(result)
class Frames(socketserver.BaseRequestHandler):
    def handle(self):
        global frame
        self.request.settimeout(5)
        try:
            magic,w,h,stride,fmt = struct.unpack('!5I',exact(self.request,20))
            if magic != 0x4d494246 or not 0<w<=1920 or not 0<h<=1080 or stride!=w*4 or fmt!=8: raise ValueError('Unsupported frame')
            data=png(w,h,exact(self.request,stride*h))
            with lock:
                frame=data;state.update(frames=state['frames']+1,last_frame=time.time(),width=w,height=h,saved=False)
                (ROOT/'reports/qnx-display.png').write_bytes(data)
                (ROOT/'reports/qnx-display-status.json').write_text(json.dumps(state,indent=2))
            print('Guest frame',state['frames'],w,h,flush=True)
        except (EOFError,ValueError,OSError) as exc: print('Rejected frame:',exc,flush=True)
PAGE_TEMPLATE='''<!doctype html><meta charset="utf-8"><title>SEAT HMI Display</title>
<style>body{background:#141619;color:#eee;font:16px system-ui;margin:40px}main{max-width:960px;margin:auto}h1{font-size:24px}img{width:100%;max-width:800px;aspect-ratio:5/3;background:#000;border:1px solid #444}p,a{color:#adb4bc}strong{color:#ffbd69}</style>
<main><h1>__TITLE__ &middot; 800 &times; 480</h1><p><strong>__DESCRIPTION__</strong></p><img id="screen" alt="Warte auf Bilddaten"><p id="status">Warte auf Bilder...</p><div id="controls"></div><p id="input-status"></p><a href="__LINK__">__LINK_LABEL__</a></main>
<script>let last=null; async function tick(){try{const s=await(await fetch('__PREFIX__/status')).json();if(s.frames&&s.last_frame!==last){last=s.last_frame;document.querySelector('img').src='__PREFIX__/frame.png?t='+last;}const age=Math.max(0,Math.floor(Date.now()/1000-s.last_frame));document.querySelector('#status').textContent=s.frames ? (age>5?'Gespeicherter letzter Frame | ':'Neue Frames | ')+s.frames+' Frames | Letztes Bild vor '+age+' s' : 'Warte auf Bilder...';}catch(e){document.querySelector('#status').textContent='Keine Verbindung zum lokalen Viewer';}setTimeout(tick,500)}tick();
if('__PREFIX__'===''){
let pending=Promise.resolve(),down=false,moved=false;
function send(e){pending=pending.then(async()=>{const r=await fetch('/input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(e)});const s=await r.json();document.querySelector('#input-status').textContent=r.ok?'Eingabe gesendet':s.error;}).catch(()=>{document.querySelector('#input-status').textContent='Eingabe nicht verbunden';});}
const screen=document.querySelector('#screen');screen.style.touchAction='none';screen.draggable=false;
function touch(e,phase){const r=screen.getBoundingClientRect();send({type:'touch',phase,x:Math.max(0,Math.min(799,Math.floor((e.clientX-r.left)/r.width*800))),y:Math.max(0,Math.min(479,Math.floor((e.clientY-r.top)/r.height*480)))});}
screen.onpointerdown=e=>{down=true;moved=false;screen.setPointerCapture(e.pointerId);touch(e,'down');};
screen.onpointermove=e=>{if(down&&(Math.abs(e.movementX)+Math.abs(e.movementY)>1)){moved=true;touch(e,'move');}};
screen.onpointerup=e=>{if(down)touch(e,moved?'release':'up');down=false;};screen.onpointercancel=e=>{if(down)touch(e,'release');down=false;};
for(const name of ['RADIO','MEDIA','PHONE','VOICE','NAV','TRAFFIC','CAR','MENU','BACK','POWER','TUNE']){const b=document.createElement('button');b.textContent=name;b.onclick=()=>send({type:'button',name});document.querySelector('#controls').append(b);}
for(const name of ['VOLUME','TUNE'])for(const delta of [-1,1]){const b=document.createElement('button');b.textContent=name+(delta>0?' +':' −');b.onclick=()=>send({type:'encoder',name,delta});document.querySelector('#controls').append(b);}
}
</script>'''
def page(diagnostic):
    values = dict(TITLE='QNX Diagnose' if diagnostic else 'SEAT HMI',
        DESCRIPTION='Diagnosebild aus QEMU — keine SEAT-HMI' if diagnostic else 'Original-HMI über die QNX-Grafikbrücke. Radiomenü sichtbar; Touch und Tasten werden geprüft.',
        PREFIX='/diagnostic' if diagnostic else '',
        LINK='/' if diagnostic else '/diagnostic',
        LINK_LABEL='Zur HMI' if diagnostic else 'Separates Diagnosebild')
    result=PAGE_TEMPLATE
    for key,value in values.items(): result=result.replace('__'+key+'__',value)
    return result.encode()
def hmi_status():
    try: return json.loads((ROOT/'reports/hmi-render-status.json').read_text())
    except (OSError,ValueError): return dict(frames=0,last_frame=None)
class HTTP(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path!='/input': self.send_error(404);return
        origin=self.headers.get('Origin')
        if origin and origin not in ('http://127.0.0.1:8767','http://localhost:8767'):self.send_error(403);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024:raise ValueError('Invalid input size')
            data=json.dumps(hub.submit(json.loads(self.rfile.read(length)))).encode();code=200
        except (ValueError,KeyError,TypeError) as exc:data=json.dumps({'error':str(exc)}).encode();code=400
        except ConnectionError as exc:data=json.dumps({'error':str(exc)}).encode();code=503
        self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

    def log_message(self,*args): pass
    def do_GET(self):
        path=self.path.split('?',1)[0]
        with lock:
            if path=='/frame.png':
                try: data=(ROOT/'reports/hmi-render.png').read_bytes()
                except OSError: data=b''
                typ='image/png'
            elif path=='/status': data,typ=json.dumps(dict(hmi_status(),input_connected=hub.connected,input_sent=hub.sent)).encode(),'application/json'
            elif path=='/diagnostic/frame.png': data,typ=frame,'image/png'
            elif path=='/diagnostic/status': data,typ=json.dumps(state).encode(),'application/json'
            elif path in ('/','/diagnostic'): data,typ=page(path=='/diagnostic'),'text/html; charset=utf-8'
            else: self.send_error(404);return
        self.send_response(200 if data else 503);self.send_header('Content-Type',typ);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True
if __name__=='__main__':
    restore_frame()
    hub.start()
    tcp=Server(('127.0.0.1',8766),Frames)
    threading.Thread(target=tcp.serve_forever,daemon=True).start()
    print('Display http://127.0.0.1:8767; QNX receiver 127.0.0.1:8766',flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1',8767),HTTP).serve_forever()
