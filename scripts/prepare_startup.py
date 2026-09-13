#!/usr/bin/env python3
"""Prepare emulator startup files on the host instead of rebuilding them over UART."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def prepare():
    hmi=ROOT/'extracted/P0480T/hmi/tsd/tmp/hmi'
    out=ROOT/'guest/shim/build';out.mkdir(parents=True,exist_ok=True)
    original=(ROOT/'extracted/eMMC/filesystems/p1/tsd/etc/system/cpu.conf').read_text()
    marker='service iMX6.DispMg\n'
    if original.count(marker)!=1:raise ValueError('Unexpected displaymanager service layout')
    config=original.replace(marker,marker+'   ipc connectionpair tsd.persmaster.tx tsd.persmaster.rx\n')
    config=config.replace('/tsd/hmi','/seat/tsd/hmi').replace('/seat/tsd/hmi/runHMI.sh','/seat/shim/runHMI-emulator.sh')
    import re
    config=re.sub(r'restart global[^\n]*','restart ignore',config)
    (out/'cpu-emulator.conf').write_text(config)
    run=(hmi/'runHMI.sh').read_text()
    replacements={'JAVA_LIBRARY_PATH="':'JAVA_LIBRARY_PATH="/seat/shim:',
                  'domainTimeout=120000':'domainTimeout=5000',
                  'logging.properties=HMI/config/logging.properties':'logging.properties=/seat/shim/logging.properties -Dde.vw.mib.log4mib.console.traces.enabled=false'}
    for old,new in replacements.items():
        if old not in run:raise ValueError('Unexpected HMI startup script: '+old)
        run=run.replace(old,new)
    (out/'runHMI-emulator.sh').write_text('export MIB_DSI_EMPTY_STORE=1 MIB_DSI_POWER_ON=1 MIB_GL_HOST=10.0.2.2 MIB_INPUT=1 FONTCONFIG_PATH=/seat/shim FONTCONFIG_FILE=/seat/shim/fonts.conf\n'+run)
    (out/'runHMI-emulator.sh').chmod(0o755)
    (out/'logging.properties').write_bytes((hmi/'HMI/config/logging.properties').read_bytes())
    startup='''#!/bin/ksh
set -e
echo MIB_BOOT_MOUNT_HMI
mount_ifs -f /seat/tsd/hmi/tsd.mibstd2.hmi.ifs -m /seat
export LD_LIBRARY_PATH=/seat/shim:$LD_LIBRARY_PATH:/tsd/lib/common
echo MIB_BOOT_NETWORK
mount -Tio-pkt devnp-mx6x.so
ifconfig fec0 10.0.2.15 up
route add default 10.0.2.2
slay -f tsd.mibstd2.cpu.root || true
echo > /dev/shmem/displaymanager_screen_ready
export TSD_COMMON_CONFIG=/tsd/etc/system/tsd.mibstd2.cpu.root.conf
export TSD_LOGCHANNEL=iMX6
echo MIB_BOOT_START_HMI
on -p25 /seat/shim/cpu-root -standalone -file=/seat/shim/cpu-emulator.conf -swdlfile=/tsd/etc/system/swdl/cpu_swdl.conf -reset=/tmp/reset.count.cpu > /tmp/root-display.log 2>&1 &
echo MIB_BOOT_HMI_LAUNCHED
'''
    (out/'start-hmi.sh').write_text(startup);(out/'start-hmi.sh').chmod(0o755)
    old=(ROOT/'qemu/seat-native-input-probe.commands').read_text().splitlines()
    fast=['slay -f dumper','mount_ifs -f /dev/hd0t218 -m /seat','/bin/ksh /seat/shim/start-hmi.sh']
    (ROOT/'qemu/seat-fast-start.commands').write_text('\n'.join(fast)+'\n')
    # Same UART pacing; quantify command transmission only, not boot or rendering.
    def seconds(lines):return sum(len(line)+40 for line in lines)*.025
    report={'prepared_files':['cpu-emulator.conf','runHMI-emulator.sh','logging.properties','start-hmi.sh'],
            'old_commands':len(old),'new_commands':len(fast),'estimated_uart_seconds_old':round(seconds(old),1),'estimated_uart_seconds_new':round(seconds(fast),1),
            'measured_boot_time':None}
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/prepared-startup.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':prepare()
