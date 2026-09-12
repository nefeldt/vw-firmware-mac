#!/usr/bin/env python3
"""Start the local viewer, GPU bridge and persistent native QEMU guest together."""
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parent.parent
REPORTS=ROOT/'reports'
STATE=REPORTS/'mib-session.json'
def main():
    REPORTS.mkdir(exist_ok=True)
    lock=(REPORTS/'mib-session.lock').open('w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        print('MIB is already running. Use the SEAT MIB2 window, or ./stop-mib.command to stop it.')
        return
    binary=ROOT/'runtime/qemu-display/build/qemu-system-arm'
    for path in (binary,ROOT/'extracted/P0480T/cpu-qemu-debug.ifs',ROOT/'qemu/emmc-overlay.qcow2'):
        if not path.is_file():raise SystemExit(f'Missing {path.relative_to(ROOT)}. See README build steps.')
    for port in (8766,8767,8768,8769):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',port))==0:raise SystemExit(f'Port {port} is already occupied. Run ./stop-mib.command, then ./start-mib.command.')
    children=[];logs=[]
    def stop(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    signal.signal(signal.SIGHUP,stop)
    try:
        birth=subprocess.check_output(['ps','-p',str(os.getpid()),'-o','lstart='],text=True).strip()
        STATE.write_text(json.dumps({'pid':os.getpid(),'started':birth,'script':str(Path(__file__).resolve())},indent=2))
        def launch(name,command,env=None):
            log=(REPORTS/(name+'.log')).open('w');logs.append(log)
            p=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);children.append(p)
            return p
        launch('viewer',[sys.executable,'scripts/mib_display_receiver.py'])
        launch('renderer',[sys.executable,'runtime/graphics/gl_server.py'])
        time.sleep(1)
        if any(p.poll() is not None for p in children):raise RuntimeError('A display service failed; see reports/viewer.log and renderer.log')
        env=dict(os.environ,MIB_QEMU_BIN=str(binary),MIB_QEMU_NATIVE_DISPLAY='1')
        env.setdefault('MIB_FULLSCREEN','1')
        launch('launcher',[sys.executable,'scripts/probe_qemu.py','--commands-file','qemu/seat-native-input-probe.commands','--report','reports/native-guest.log','--command-timeout','240','--keep-running'],env)
        print('Starting SEAT MIB2 in QEMU. Boot and HMI initialization take several minutes.',flush=True)
        print('Fullscreen with visible cursor. Ctrl+Option+G releases mouse grab; use the QEMU View menu for fullscreen.',flush=True)
        print('Browser: http://127.0.0.1:8767/ | Stop: Ctrl-C or stop-mib.command',flush=True)
        while True:
            for p in children:
                if p.poll() is not None:raise RuntimeError(f'A MIB process exited ({p.returncode}); inspect reports/*.log')
            time.sleep(2)
    except KeyboardInterrupt:print('Stopping MIB...',flush=True)
    finally:
        for p in reversed(children):
            # The launcher can exit before QEMU; terminate the whole owned group.
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        for p in reversed(children):
            try:p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                p.wait()
        for log in logs:log.close()
        STATE.unlink(missing_ok=True)
        lock.close()
if __name__=='__main__':main()
