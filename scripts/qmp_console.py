#!/usr/bin/env python3
"""Inspect or send a click to the project's local QEMU console through QMP."""
import argparse
import json
from pathlib import Path
import socket
class QMP:
    def __init__(self,path='/tmp/mib-qmp.sock'):
        self.socket=socket.socket(socket.AF_UNIX);self.socket.settimeout(5);self.socket.connect(path)
        self.stream=self.socket.makefile('rwb',buffering=0);json.loads(self.stream.readline());self.call('qmp_capabilities')
    def call(self,command,arguments=None):
        self.stream.write((json.dumps({'execute':command,'arguments':arguments or {}})+'\n').encode())
        while True:
            response=json.loads(self.stream.readline())
            if 'error' in response:raise RuntimeError(response['error'])
            if 'return' in response:return response['return']
    def click(self,x,y):
        if not 0<=x<1000 or not 0<=y<600:raise ValueError('Outside native console')
        self.call('input-send-event',{'events':[{'type':'abs','data':{'axis':'x','value':round(x/999*32767)}},{'type':'abs','data':{'axis':'y','value':round(y/599*32767)}},{'type':'btn','data':{'button':'left','down':True}}]})
        import time;time.sleep(.1)
        self.call('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':False}}]})
    def close(self):self.stream.close();self.socket.close()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--screenshot',type=Path);p.add_argument('--click',type=int,nargs=2,metavar=('X','Y'));a=p.parse_args()
    q=QMP()
    try:
        print(json.dumps(q.call('query-status')))
        if a.click:q.click(*a.click)
        if a.screenshot:q.call('screendump',{'filename':str(a.screenshot.resolve())})
    finally:q.close()
if __name__=='__main__':main()
