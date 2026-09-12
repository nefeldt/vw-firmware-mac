#!/usr/bin/env python3
"""Assemble emulator copies from locally supplied, version-specific inputs."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
from doctor import ROOT,missing_inputs

def run(*args):subprocess.run([str(a) for a in args],cwd=ROOT,check=True)
def main():
    missing=missing_inputs()
    if missing:raise SystemExit('Missing local inputs; see docs/SETUP.md:\n'+'\n'.join(missing))
    for directory in ('reports','guest/shim/build','extracted/P0480T','qemu'):(ROOT/directory).mkdir(parents=True,exist_ok=True)
    py=sys.executable
    cpu=ROOT/'extracted/P0480T/cpu-unpacked.ifs'
    run(py,'scripts/unpack_mib_cpu.py',ROOT/'firmware/P0480T/cpu/cpuimage_sec_stdNavi/24/default/mibstd2_cpu.boot',cpu)
    run(py,'scripts/prepare_qemu_cpu.py',cpu,ROOT/'extracted/P0480T/cpu-qemu-debug.ifs','--debug-shell')
    env=dict(os.environ,MIB_GLES_IMPL='bridge')
    subprocess.run(['zsh','guest/shim/build.sh'],cwd=ROOT,env=env,check=True)
    run(py,'guest/dsi/build.py')
    shim=ROOT/'guest/shim/build'
    for source,name in [('guest/dsi/build/libdsi-original.so','libdsi-original.so'),('guest/dsi/build/libdsi-trace.so','libtsd.mibstd2.hmi.dsi.native.so'),('extracted/eMMC/system-ifs/tsd/bin/root/tsd.mibstd2.cpu.root','cpu-root'),('extracted/eMMC/system-ifs/tsd/bin/displaymanager/tsd.mibstd2.system.displaymanager','displaymanager')]:shutil.copy2(ROOT/source,shim/name)
    run(py,'scripts/patch_qemu_clock_worker.py','--elf-only')
    fonts=(ROOT/'extracted/P0480T/hmi/tsd/tmp/hmi/fonts.conf').read_text().replace('<dir>Resources/','<dir>/seat/hm/Resources/').replace('/tsd/var/fonts_cache','/tmp')
    (shim/'fonts.conf').write_text(fonts)
    overlay=ROOT/'qemu/emmc-overlay.qcow2'
    if not overlay.exists():
        run('qemu-img','create','-f','qcow2','-F','raw','-b',ROOT/'extracted/eMMC/emmc.img',overlay)
        run('qemu-img','resize',overlay,'4G')
    run(py,'scripts/build_seat_ifs.py')
    print('Emulator image ready. Do not flash it to a vehicle.')
if __name__=='__main__':main()
