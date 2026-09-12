#!/usr/bin/env python3
"""Diagnostic experiment: skip the unavailable J5 clock worker in QEMU only.

ClockManagerIMX6::run asserts on missing J5-provided clockControl. Its function
boundary is verified by ARM exidx and its assertion string reference. This
does not implement the absent clock service; it tests later initialization.
"""
from pathlib import Path
import json
import struct
import sys

root = Path(__file__).resolve().parent.parent
address = 0x1805bc
old, new = 0xe1a0c00d, 0xe12fff1e  # mov ip, sp -> bx lr


def patch_elf(data):
    ph = struct.unpack_from('<I', data, 28)[0]
    stride, count = struct.unpack_from('<HH', data, 42)
    for i in range(count):
        kind, off, va, _, size, _, flags, _ = struct.unpack_from('<8I', data, ph+i*stride)
        if kind == 1 and flags & 1 and va <= address < va+size:
            pos = off+address-va
            actual = struct.unpack_from('<I', data, pos)[0]
            assert actual in (old, new), 'Unexpected clock worker instruction'
            struct.pack_into('<I', data, pos, new)
            return pos
    raise ValueError('Clock worker not in an executable segment')


elf = root/'guest/shim/build/cpu-root'
data = bytearray(elf.read_bytes())
patch_elf(data)
elf.write_bytes(data)
if '--elf-only' in sys.argv:
    print('Patched emulator cpu-root copy')
    sys.exit(0)
image = root/'extracted/P0480T/seat-transfer.ifs'
ifs = bytearray(image.read_bytes())
pos = struct.unpack_from('<I', ifs, 16)[0]
while True:
    size, _, _, mode = struct.unpack_from('<HHII', ifs, pos)
    if not size:
        raise ValueError('shim/cpu-root not in transfer IFS')
    if mode & 0xf000 == 0x8000 and ifs[pos+32:pos+size].split(b'\0')[0] == b'shim/cpu-root':
        off, length = struct.unpack_from('<II', ifs, pos+24)
        code = bytearray(ifs[off:off+length])
        location = patch_elf(code)
        ifs[off:off+length] = code
        break
    pos += size
struct.pack_into('<I', ifs, len(ifs)-4, 0)
total = sum(v[0] for v in struct.iter_unpack('<I', ifs)) & 0xffffffff
struct.pack_into('<I', ifs, len(ifs)-4, -total & 0xffffffff)
image.write_bytes(ifs)
report = {'emulator_only': True, 'function': 'ClockManagerIMX6::run',
          'address': hex(address), 'ifs_offset': off+location,
          'purpose': 'Skip J5 clock worker to diagnose subsequent initialization'}
(root/'reports/qemu-clock-worker-patch.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
