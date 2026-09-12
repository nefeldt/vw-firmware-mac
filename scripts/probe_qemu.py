#!/usr/bin/env python3
"""Boot the emulator, run diagnostic console commands, and save evidence."""
import argparse
import re
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
with args.report.open('w') as log:
    proc = subprocess.Popen([str(root/'qemu/run-mib-qemu.sh')], cwd=root,
                            stdin=subprocess.PIPE, stdout=log,
                            stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.monotonic()+45
        while 'imx6:/# ' not in args.report.read_text(errors='replace'):
            if proc.poll() is not None:
                raise RuntimeError(f'QEMU exited: {proc.returncode}')
            if time.monotonic() > deadline:
                raise TimeoutError('QNX diagnostic prompt not reached')
            time.sleep(.25)
        for index, command in enumerate(args.command):
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
        time.sleep(args.settle)
        if args.keep_running:
            print("Guest ready; keeping QEMU running for interactive input", flush=True)
            while proc.poll() is None:
                time.sleep(5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
print(args.report)
