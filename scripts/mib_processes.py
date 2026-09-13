"""Identify only MIB processes whose working directory is this project."""
from pathlib import Path
import os
import subprocess
import shlex
ROOT=Path(__file__).resolve().parent.parent
MARKERS=('scripts/run_mib.py','scripts/probe_qemu.py','scripts/mib_display_receiver.py','runtime/graphics/gl_server.py')
def birth(pid):
    r=subprocess.run(['ps','-p',str(pid),'-o','lstart='],text=True,capture_output=True)
    return r.stdout.strip() if r.returncode==0 else None

def owned_processes():
    result=[]
    listing=subprocess.run(['ps','-axo','pid=,command='],text=True,capture_output=True,check=True)
    for line in listing.stdout.splitlines():
        parts=line.strip().split(None,1)
        if len(parts)!=2:continue
        pid=int(parts[0]);command=parts[1]
        if pid==os.getpid():continue
        try: argv=shlex.split(command)
        except ValueError: continue
        if not argv: continue
        executable=Path(argv[0]).name.lower()
        script=False
        if executable.startswith('python') and len(argv)>1:
            args=argv[1:]
            while args and args[0] in ('-u','-B','-I'): args=args[1:]
            script=bool(args and any(args[0]==marker or args[0]==str(ROOT/marker) for marker in MARKERS))
        guest=executable=='qemu-system-arm' and any(argv[i] in ('-M','-machine') and argv[i+1]=='sabrelite' for i in range(len(argv)-1))
        if not (script or guest):continue
        cwd=subprocess.run(['lsof','-a','-p',str(pid),'-d','cwd','-Fn'],capture_output=True,text=True)
        paths=[Path(x[1:]).resolve() for x in cwd.stdout.splitlines() if x.startswith('n')]
        if ROOT.resolve() not in paths:continue
        stamp=birth(pid)
        if stamp:result.append((pid,stamp,command))
    return result
