#!/usr/bin/env python3
"""Capture a standalone local QEMU disk and internal VM snapshot through QMP."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from qmp_console import QMP

ROOT=Path(__file__).resolve().parent.parent

def wait_job(q,identifier,timeout=180):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=next((x for x in q.call('query-jobs') if x['id']==identifier),None)
        if job and job['status']=='concluded':
            q.call('job-dismiss',{'id':identifier})
            if job.get('error'):raise RuntimeError(job['error'])
            return
        time.sleep(.25)
    raise TimeoutError('Snapshot job did not finish: '+identifier)

def main():
    directory=ROOT/'snapshots';directory.mkdir(exist_ok=True)
    stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid())
    disk=directory/('live-'+stamp+'.qcow2')
    tag='mib-live';node='mib-capture-'+str(os.getpid())
    q=QMP();q.socket.settimeout(30)
    running=False;added=False;paused=False
    try:
        running=q.call('query-status')['running']
        device=next(x['inserted'] for x in q.call('query-block') if x.get('device')=='emmc')
        subprocess.run(['qemu-img','create','-f','qcow2',str(disk),str(device['image']['virtual-size'])],check=True)
        q.call('blockdev-add',{'driver':'qcow2','node-name':node,'file':{'driver':'file','filename':str(disk)}});added=True
        q.call('stop');paused=True
        print('Saving disk and live VM state; QEMU is briefly paused.',flush=True)
        q.call('blockdev-backup',{'job-id':node+'-copy','device':device['node-name'],'target':node,'sync':'full','auto-dismiss':False})
        wait_job(q,node+'-copy')
        q.call('snapshot-save',{'job-id':node+'-state','tag':tag,'vmstate':node,'devices':[node]})
        wait_job(q,node+'-state')
        q.call('blockdev-del',{'node-name':node});added=False
        binary=ROOT/'runtime/qemu-display/build/qemu-system-arm'
        metadata={'version':1,'disk':str(disk.relative_to(ROOT)),'tag':tag,
                  'created_at':time.time(),'qemu_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
                  'restore_verified':False,'graphics_state':'external; restoration must be verified'}
        manifest=directory/'live.json';temporary=directory/'live.json.tmp'
        temporary.write_text(json.dumps(metadata,indent=2)+'\n');temporary.replace(manifest)
        print('Saved '+str(disk),flush=True)
        print('Live snapshot captured. Full graphics/input restoration is not yet verified.',flush=True)
    finally:
        if added:
            try:q.call('blockdev-del',{'node-name':node})
            except Exception:pass
        if paused and running:
            try:q.call('cont')
            except Exception:pass
        q.close()

if __name__=='__main__':main()
