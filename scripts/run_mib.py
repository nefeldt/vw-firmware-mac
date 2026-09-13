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
    data_dir=Path(os.environ.get('MIB_DATA_DIR',str(ROOT/'local-data'))).resolve()
    prepared=data_dir/'runtime'
    # Existing workspaces can keep their previous generated layout until imported.
    default_cpu=prepared/'cpu-qemu-debug.ifs'
    default_disk=prepared/'emmc-overlay.qcow2'
    if not default_cpu.exists() and not default_disk.exists():
        default_cpu=ROOT/'extracted/P0480T/cpu-qemu-debug.ifs'
        default_disk=ROOT/'qemu/emmc-overlay.qcow2'
    cpu=Path(os.environ.get('MIB_CPU_IMAGE',str(default_cpu))).resolve()
    disk_image=Path(os.environ.get('MIB_EMMC_IMAGE',str(default_disk))).resolve()
    for path in (binary,cpu,disk_image):
        if not path.is_file():raise SystemExit(f'Missing {path}. See README local-data setup.')
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
        env=dict(os.environ,MIB_QEMU_BIN=str(binary),MIB_QEMU_NATIVE_DISPLAY='1',
                 MIB_CPU_IMAGE=str(cpu),MIB_EMMC_IMAGE=str(disk_image))
        print(f'Using prepared boot image: {cpu}',flush=True)
        print(f'Using emulator disk: {disk_image}',flush=True)
        map_card=data_dir/'maps/navigation-sd.img'
        if map_card.is_file():
            env.setdefault('MIB_MAP_IMAGE',str(map_card))
        if env.get('MIB_MAP_IMAGE'):
            print(f'Using map SD card: {env["MIB_MAP_IMAGE"]}',flush=True)
        env.setdefault('MIB_FULLSCREEN','1')
        launch('launcher',[sys.executable,'scripts/probe_qemu.py','--commands-file','qemu/seat-fast-start.commands','--report','reports/native-guest.log','--command-timeout','240','--keep-running'],env)
        print('Starting SEAT MIB2 in QEMU. Boot and HMI initialization take several minutes.',flush=True)
        print('Fullscreen with visible cursor. Ctrl+Option+G releases mouse grab; use the QEMU View menu for fullscreen.',flush=True)
        print('Browser: http://127.0.0.1:8767/ | Stop: Ctrl-C or stop-mib.command',flush=True)
        while True:
            for p in children:
                if p.poll() is not None:raise RuntimeError(f'A MIB process exited ({p.returncode}); inspect reports/*.log')
            time.sleep(2)
    except KeyboardInterrupt:print('Stopping MIB...',flush=True)
    finally:
        # Repeated Ctrl-C must not interrupt cleanup and leave QEMU running.
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):
            signal.signal(sig,signal.SIG_IGN)
        for p in reversed(children):
            # The launcher can exit before QEMU; terminate the whole owned group.
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        deadline=time.monotonic()+8
        remaining=list(children)
        while remaining and time.monotonic()<deadline:
            groups={int(value) for value in subprocess.check_output(
                ['ps','-axo','pgid='],text=True).split()}
            alive=[]
            for p in remaining:
                p.poll()  # Reap group leaders before checking their descendants.
                if p.pid in groups:alive.append(p)
            remaining=alive
            if remaining:time.sleep(.1)
        for p in remaining:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        for p in children:p.wait()
        for log in logs:log.close()
        STATE.unlink(missing_ok=True)
        lock.close()
        print('MIB stopped, including QEMU and display services.',flush=True)
if __name__=='__main__':main()
