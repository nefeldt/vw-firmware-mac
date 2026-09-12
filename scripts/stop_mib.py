#!/usr/bin/env python3
"""Stop all verified MIB processes in this project, including orphaned QEMU."""
import os
import signal
import time
from mib_processes import owned_processes,birth

def main():
    targets=owned_processes()
    if not targets:
        print('MIB is already stopped.');return
    # Every PID is checked against its process start time immediately before signalling.
    for pid,stamp,command in targets:
        if birth(pid)==stamp:
            try:os.kill(pid,signal.SIGTERM)
            except ProcessLookupError:pass
    print(f'Stopping {len(targets)} MIB processes, including QEMU...',flush=True)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        remaining=[(p,t,c) for p,t,c in targets if birth(p)==t]
        if not remaining:
            print('MIB stopped. Run ./start-mib.command to start again.');return
        time.sleep(.2)
    # Only the same verified process identities can reach this final cleanup.
    for pid,stamp,command in remaining:
        if birth(pid)==stamp:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
    time.sleep(.3)
    if any(birth(p)==t for p,t,c in remaining):raise SystemExit('Some MIB processes could not be stopped.')
    print('MIB stopped; remaining unresponsive project processes were terminated.')
if __name__=='__main__':main()
