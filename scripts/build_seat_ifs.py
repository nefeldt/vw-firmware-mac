#!/usr/bin/env python3
"""Rebuild the nonbootable SEAT data IFS (plus optional guest shim dir) with the QNX 6.5 mkifs.

The HMI tree and guest/shim/build are streamed as a tar into a disposable Frida
qnx-tools container (the workspace is not bind-mountable there); mkifs output
comes back on stdout. Then stage_seat_partition.py rewrites MBR slot 4 in the
qcow2 overlay. Originals (emmc.img, firmware) are never modified.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--hmi', type=Path, default=root/'extracted/P0480T/hmi/tsd/tmp/hmi')
parser.add_argument('--shim', type=Path, default=root/'guest/shim/build',
                    help='directory placed at /shim inside the IFS (omit contents if empty)')
parser.add_argument('--extra', type=Path, action='append', default=[],
                    help='additional directory whose contents are placed at /extra/<name>')
parser.add_argument('--output', type=Path, default=root/'extracted/P0480T/seat-transfer.ifs')
parser.add_argument('--no-stage', action='store_true')
args = parser.parse_args()

image = 'ghcr.io/frida/qnx-tools:latest'
build = ['[+raw]', '/tsd/hmi=/work/hmi', '[type=link] /hm=tsd/hmi']
tar_cmd = ['tar', '--exclude=._*', '--exclude=.DS_Store', '-cf', '-',
           '-C', str(args.hmi.parent), args.hmi.name]
inputs = [('hmi', args.hmi)]
if args.shim.is_dir() and any(args.shim.iterdir()):
    # Shared objects must be page aligned to be mmap-loadable; [+raw] entries are not.
    build.append('[-raw +page_align data=copy]\n/shim=/work/shim\n[+raw -page_align]')
    inputs.append(('shim', args.shim))
for extra in args.extra:
    build.append(f'/extra/{extra.name}=/work/extra/{extra.name}')
    inputs.append((f'extra/{extra.name}', extra))

# Stage a single tar with the desired in-container layout.
stage = root/'build/seat-ifs-stage'
if stage.exists():
    shutil.rmtree(stage)
for name, src in inputs:
    dest = stage/name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, symlinks=True,
                    ignore=shutil.ignore_patterns('._*', '.DS_Store'))
(stage/'seat.build').write_text('\n'.join(build)+'\n')
env = dict(os.environ, COPYFILE_DISABLE='1')
tar = subprocess.Popen(['tar', '--no-xattrs', '-cf', '-', '-C', str(stage), '.'], stdout=subprocess.PIPE, env=env)
script = ('set -e; mkdir -p /work && cd /work && tar -xf - ; '
          'export QNX_HOST=/opt/qnx650/host/linux/x86 QNX_TARGET=/opt/qnx650/target/qnx6 '
          'PATH=/opt/qnx650/host/linux/x86/usr/bin:$PATH; '
          'mkifs seat.build /work/out.ifs 1>&2 && cat /work/out.ifs')
t0 = time.time()
with subprocess.Popen(['docker', 'run', '--rm', '--network', 'none', '--pull', 'never', '-i', image, '-lc', script],
                      stdin=tar.stdout, stdout=subprocess.PIPE) as docker:
    tar.stdout.close()
    data = docker.stdout.read()
if tar.wait() or docker.returncode:
    sys.exit(f'build failed: tar={tar.returncode} docker={docker.returncode}')
assert data[:7] == b'imagefs', 'mkifs output is not a data IFS'
if args.output.exists():
    shutil.copy2(args.output, args.output.with_suffix('.ifs.prev'))
args.output.write_bytes(data)
print(f'{args.output}: {len(data)} bytes in {time.time()-t0:.1f}s; build file:\n' + '\n'.join(build))
if not args.no_stage:
    subprocess.run([sys.executable, str(root/'scripts/stage_seat_partition.py')], check=True)
