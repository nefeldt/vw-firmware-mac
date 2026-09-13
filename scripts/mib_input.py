"""Local input hub: validated controls become original DSIKeyPanel notifications."""
import json
from pathlib import Path
import queue
import socketserver
import struct
import threading
import time
ROOT=Path(__file__).resolve().parent.parent
BUTTONS={'RADIO':15,'MEDIA':1,'PHONE':3,'VOICE':50,'NAV':4,'TRAFFIC':5,'CAR':6,'MENU':78,'POWER':17,'TUNE':16,'BACK':13,'SETUP':7}
class Hub:
    def __init__(self):
        self.queue=queue.Queue(maxsize=128);self.connected=False;self.sent=0;self.lock=threading.Lock()
    def packet(self,attribute,payload):
        data=struct.pack('<III',0x0201d800,0xa63ff832,attribute)+payload
        return struct.pack('<I',len(data))+data
    def submit(self,event):
        kind=event.get('type');packets=[]
        if kind=='touch':
            x,y=int(event['x']),int(event['y']);phase=event['phase']
            if not (0<=x<800 and 0<=y<480):raise ValueError('Coordinates outside display')
            gesture={'down':4,'up':1,'release':3,'move':5}[phase]
            # keyboard, gesture, finger, z, x, y, param1, param2, elapsed, validity
            # For GESTURE_TAP param1 is click count. Zero is rejected by the
            # original TouchInputDeviceHandler.validateClickGesture().
            clicks=1 if phase=='up' else 0
            # Serializer.deserialize_boolean consumes getInt(), not one byte.
            packets=[self.packet(20,struct.pack('<10i',13,gesture,0,0,x,y,clicks,0,1,1))]
        elif kind=='button':
            # P0480T configurationmanager.res maps front-panel HMI keys to
            # KBD_TOUCHSCREEN_FRONT (13). FCC (1) has different media events
            # and no MENU mapping. Voice also accepts the steering-wheel group.
            name=event['name'];key=BUTTONS[name];kbd=4 if name=='VOICE' else 13
            packets=[self.packet(25,struct.pack('<iiiii',kbd,key,pressed,0,1)) for pressed in (1,0)]
        elif kind=='encoder':
            name=event['name'];delta=int(event['delta'])
            if name not in ('VOLUME','TUNE') or delta not in (-1,1):raise ValueError('Invalid encoder')
            packets=[self.packet(23,struct.pack('<iiiii',1,17 if name=='VOLUME' else 16,delta,1,1))]
        else:raise ValueError('Unknown input')
        if not self.connected:raise ConnectionError('QNX input is not connected')
        try:self.queue.put_nowait(packets)
        except queue.Full:raise ConnectionError('Input queue full')
        with (ROOT/'reports/hmi-input.jsonl').open('a') as log:log.write(json.dumps(dict(time=time.time(),event=event))+'\n')
        return {'queued':True,'packets':len(packets)}
    def start(self):
        hub=self
        class Guest(socketserver.BaseRequestHandler):
            def handle(self):
                with hub.lock:
                    if hub.connected:return
                    hub.connected=True
                self.request.settimeout(3)
                try:
                    while True:
                        try:packets=hub.queue.get(timeout=1)
                        except queue.Empty:
                            # Probe for disconnect without sending invalid DSI data.
                            import select,socket
                            if select.select([self.request],[],[],0)[0] and not self.request.recv(1,socket.MSG_PEEK):break
                            continue
                        for data in packets:
                            self.request.sendall(data);hub.sent+=1
                            if len(packets)>1:time.sleep(.08)
                except OSError:pass
                finally:
                    hub.connected=False
                    while not hub.queue.empty():
                        try:hub.queue.get_nowait()
                        except queue.Empty:break
        class Server(socketserver.ThreadingTCPServer):allow_reuse_address=True;daemon_threads=True
        self.server=Server(('127.0.0.1',8769),Guest)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
hub=Hub()
