#!/usr/bin/env python3
"""Run a command on the local emulator's socket-backed QNX console."""
import argparse
import re
import socket
import time
import uuid

def run(command,path='/tmp/mib-control.sock',timeout=60):
    marker='__MIB_'+uuid.uuid4().hex+'__'
    output=bytearray()
    with socket.socket(socket.AF_UNIX) as channel:
        channel.settimeout(timeout);channel.connect(path)
        text='\n'+command+'; echo; echo '+marker+'\n'
        for char in text:
            channel.sendall(char.encode());time.sleep(.025)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            data=channel.recv(65536)
            if not data:raise EOFError('Guest console disconnected')
            output.extend(data)
            if re.search(rb'(?:^|\n)'+marker.encode()+rb'\r*\n',output):
                return output.decode(errors='replace')
    raise TimeoutError('Guest console command did not finish')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command');parser.add_argument('--timeout',type=float,default=60)
    args=parser.parse_args();print(run(args.command,timeout=args.timeout))
