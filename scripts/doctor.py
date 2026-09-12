#!/usr/bin/env python3
"""Check local inputs without executing proprietary firmware."""
from pathlib import Path
import platform
import shutil
import sys
ROOT=Path(__file__).resolve().parent.parent
INPUTS=[
 'firmware/P0480T/cpu/cpuimage_sec_stdNavi/24/default/mibstd2_cpu.boot',
 'extracted/P0480T/hmi/tsd/tmp/hmi/runHMI.sh',
 'extracted/P0480T/hmi/tsd/tmp/hmi/fonts.conf',
 'extracted/P0480T/hmi/tsd/tmp/hmi/tsd.mibstd2.hmi.ifs',
 'extracted/P0480T/hmi/tsd/tmp/hmi/libtsd.mibstd2.hmi.dsi.native.so',
 'extracted/P0480T/hmi/tsd/tmp/hmi/Resources/skin1/Fonts/SEAT MetaStyle-bold.ttf',
 'extracted/eMMC/emmc.img',
 'extracted/eMMC/system-ifs/tsd/bin/root/tsd.mibstd2.cpu.root',
 'extracted/eMMC/system-ifs/tsd/bin/displaymanager/tsd.mibstd2.system.displaymanager',
 'extracted/eMMC/filesystems/p1/j9/bin/include/jni.h',
 'extracted/eMMC/filesystems/p1/j9/bin/include/jniport.h',
]
def missing_inputs():return [p for p in INPUTS if not (ROOT/p).is_file()]
def main():
    missing=missing_inputs();tools=[x for x in ('qemu-system-arm','qemu-img','qemu-io','docker','zsh') if not shutil.which(x)]
    print('Host:',platform.system(),platform.machine())
    for item in missing:print('MISSING INPUT:',item)
    for item in tools:print('MISSING TOOL:',item)
    if platform.system()!='Darwin':print('NOTE: Native CGL renderer requires macOS')
    if missing or tools:return 1
    print('Local inputs and commands found. This does not validate firmware compatibility or Docker availability.')
    return 0
if __name__=='__main__':sys.exit(main())
