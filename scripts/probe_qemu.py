#!/usr/bin/env python3
"""Boot the emulator, run diagnostic console commands, and save evidence."""
import argparse
import json
import os
import re
import socket
import select
import subprocess
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path, default=Path('reports/qemu-probe.log'))
parser.add_argument('--command', action='append', default=[])
parser.add_argument('--commands-file', type=Path)
parser.add_argument('--keep-running', action='store_true', help='Keep the guest alive after commands for interactive use')
parser.add_argument('--settle', type=float, default=3)
parser.add_argument('--command-timeout', type=float, default=45,
                    help='seconds to wait for each guest command marker')
args = parser.parse_args()
if args.commands_file:
    args.command = [line for line in args.commands_file.read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith('#')] + args.command
root = Path(__file__).resolve().parent.parent
args.report.parent.mkdir(parents=True, exist_ok=True)
started=time.monotonic()
timings={'started_at':time.time(),'events':[]}
def mark(event):
    timings['events'].append({'event':event,'elapsed_seconds':round(time.monotonic()-started,3)})
    args.report.with_suffix('.timing.json').write_text(json.dumps(timings,indent=2)+'\n')
with args.report.open('w') as log:
    proc = subprocess.Popen([str(root/'qemu/run-mib-qemu.sh')], cwd=root,
                            stdin=subprocess.PIPE, stdout=log,
                            stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.monotonic()+45
        restored=bool(os.environ.get('MIB_LOAD_SNAPSHOT'))
        while not restored and 'imx6:/# ' not in args.report.read_text(errors='replace'):
            if proc.poll() is not None:
                raise RuntimeError(f'QEMU exited: {proc.returncode}')
            if time.monotonic() > deadline:
                raise TimeoutError('QNX diagnostic prompt not reached')
            time.sleep(.25)
        mark('snapshot_requested' if restored else 'qnx_prompt')
        for index, command in enumerate([] if restored else args.command):
            marker = f'__QEMU_COMMAND_{index}_DONE__'
            # UART input overruns if entire multi-command blocks are pasted.
            separator = ' ' if command.rstrip().endswith('&') else '; '
            for char in command+separator+'echo; echo '+marker+'\n':
                proc.stdin.write(char)
                proc.stdin.flush()
                time.sleep(.025)
            deadline = time.monotonic()+args.command_timeout
            while not re.search(r'(?:^|\n)'+marker+r'\r*\n',
                                args.report.read_text(errors='replace')):
                if proc.poll() is not None:
                    raise RuntimeError(f'QEMU exited during: {command}')
                if time.monotonic() > deadline:
                    raise TimeoutError(f'Guest command did not complete: {command}')
                time.sleep(.25)
            mark(f"command_{index}_complete")
        time.sleep(args.settle)
        if args.keep_running:
            print("Startup commands finished; HMI initialization continues. Keeping QEMU running.", flush=True)
            if restored:
                while proc.poll() is None:
                    time.sleep(5)
            else:
                # Forward the diagnostic UART after startup without restarting QNX.
                console_path = Path('/tmp/mib-control.sock')
                console_path.unlink(missing_ok=True)
                with socket.socket(socket.AF_UNIX) as server:
                    server.bind(str(console_path))
                    console_path.chmod(0o600)
                    server.listen(1)
                    server.settimeout(1)
                    try:
                        while proc.poll() is None:
                            try:
                                client, _ = server.accept()
                            except socket.timeout:
                                continue
                            with client, args.report.open('rb') as serial_log:
                                serial_log.seek(0, 2)
                                client.settimeout(2)
                                try:
                                    while proc.poll() is None:
                                        ready, _, _ = select.select([client], [], [], .05)
                                        if ready:
                                            data = client.recv(4096)
                                            if not data:
                                                break
                                            proc.stdin.write(data.decode('ascii'))
                                            proc.stdin.flush()
                                        output = serial_log.read()
                                        if output:
                                            client.sendall(output)
                                except (OSError, UnicodeError):
                                    pass
                    finally:
                        console_path.unlink(missing_ok=True)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
print(args.report)
