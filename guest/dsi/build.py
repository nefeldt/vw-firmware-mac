#!/usr/bin/env python3
"""Build the emulator DSI tracer with the existing QNX container toolchain."""
from pathlib import Path
import subprocess
import io
import tarfile
import struct
import os
import shutil

root = Path(__file__).resolve().parent
source = root.parent.parent / 'extracted/P0480T/hmi/tsd/tmp/hmi/libtsd.mibstd2.hmi.dsi.native.so'
original = bytearray(source.read_bytes())
assert original[:6] == b'\x7fELF\x01\x01'
phoff = struct.unpack_from('<I', original, 28)[0]
phsize, phcount = struct.unpack_from('<HH', original, 42)
headers = [struct.unpack_from('<8I', original, phoff+i*phsize) for i in range(phcount)]
dynamic = next(h for h in headers if h[0] == 2)
tags = dict(struct.unpack_from('<II', original, pos)
            for pos in range(dynamic[1], dynamic[1]+dynamic[4], 8))
strings = tags[5]
segment = next(h for h in headers if h[0] == 1 and h[2] <= strings < h[2]+h[4])
soname = segment[1]+strings-segment[2]+tags[14]
end = original.index(0, soname)
replacement = b'libdsi-original.so'
assert end-soname >= len(replacement)
original[soname:end] = replacement.ljust(end-soname, b'\0')
# Emulator font root: Pango::openFont compares this prefix exactly with FcPattern file.
# Keep the binary string width unchanged; /seat/hm is an IFS symlink to SEAT.
font_address = 0x3882b8
font_segment = next(h for h in headers if h[0] == 1 and h[2] <= font_address < h[2]+h[4])
font_offset = font_segment[1]+font_address-font_segment[2]
assert original[font_offset:font_offset+9] == b'/tsd/hmi\0'
original[font_offset:font_offset+9] = b'/seat/hm\0'
# JNI headers remain local: import the matching J9 headers from the user's dump.
header_source = root.parent.parent/'extracted/eMMC/filesystems/p1/j9/bin/include'
(root/'include').mkdir(exist_ok=True)
for header in ('jni.h', 'jniport.h'):
    if not (header_source/header).is_file():
        raise SystemExit(f'Missing local J9 header: {header_source/header}')
    shutil.copy2(header_source/header, root/'include'/header)
payload = io.BytesIO()
with tarfile.open(fileobj=payload, mode='w') as archive:
    for name in ('trace.c', 'input.h', 'include'):
        archive.add(root / name, arcname=name)
    entry = tarfile.TarInfo('libdsi-original.so')
    entry.size = len(original)
    archive.addfile(entry, io.BytesIO(original))
script = '''set -e
mkdir -p /tmp/dsi
cd /tmp/dsi
tar -xf -
export QNX_HOST=/opt/qnx650/host/linux/x86
export QNX_TARGET=/opt/qnx650/target/qnx6
export PATH=/opt/qnx650/host/linux/x86/usr/bin:$PATH
qcc -Vgcc_ntoarmv7le -shared -fPIC -O1 -Iinclude -Wl,--no-as-needed -L. -o /tmp/libdsi-trace.so trace.c -l:libdsi-original.so -lsocket
cat /tmp/libdsi-trace.so
'''
result = subprocess.run(
    ['docker', '--context', os.environ.get('DOCKER_CONTEXT', 'default'), 'run', '--rm', '--network', 'none', '--pull', 'never', '-i',
     'ghcr.io/frida/qnx-tools:latest', '-lc', script],
    input=payload.getvalue(), stdout=subprocess.PIPE, check=True)
if result.stdout[:4] != b'\x7fELF':
    raise RuntimeError('Compiler output is not an ELF library')
(root / 'build').mkdir(exist_ok=True)
(root / 'build/libdsi-trace.so').write_bytes(result.stdout)
(root / 'build/libdsi-original.so').write_bytes(original)
print(root / 'build/libdsi-trace.so')
