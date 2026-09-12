#!/usr/bin/env python3
"""Prepare an emulator-only CPU image with fixed RAM geometry and a debug shell.

Never flash this image. QEMU's unimplemented MMDC registers report zero, making
the original DDR sizing routine declare just 16 MiB. Override its result for
the launcher's 1 GiB guest. Keep the original decoded image unchanged.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def checksum(data, start, end):
    return sum(struct.unpack_from(f'<{(end-start)//4}I', data, start)) & 0xffffffff


def repair(data, start, end):
    struct.pack_into('<I', data, end - 4, 0)
    struct.pack_into('<I', data, end - 4, -checksum(data, start, end) & 0xffffffff)
    assert checksum(data, start, end) == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--debug-shell', action='store_true')
    args = parser.parse_args()
    original = args.input.read_bytes()
    data = bytearray(original)
    startup_end = 0x1e110
    assert len(data) == 9587196, 'Unexpected firmware size'
    assert checksum(data, 8, startup_end) == 0, 'Invalid startup checksum'
    assert checksum(data, startup_end, len(data)) == 0, 'Invalid ImageFS checksum'
    assert struct.unpack_from('<I', data, 0x36a8)[0] == 0xe1a01311
    # ARM: mov r1, #0x40000000 instead of lsl r1, r1, r3.
    struct.pack_into('<I', data, 0x36a8, 0xe3a01101)
    repair(data, 8, startup_end)
    # QEMU's default SD bus is USDHC4. Map the boot storage driver there.
    old = b'addr=0x02198000,irq=56'
    new = b'addr=0x0219c000,irq=57'
    assert data.count(old) == 1, 'Unexpected storage boot command'
    data = data.replace(old, new)
    if args.debug_shell:
        offset, size = 0x20e3c, 0x163
        assert data[offset:offset+10] == b'#!/bin/ksh'
        script = b'#!/bin/ksh\necho QEMU_DIAGNOSTIC_SHELL\nexec /bin/ksh\n'
        data[offset:offset+size] = script.ljust(size, b'\n')
    repair(data, startup_end, len(data))
    args.output.write_bytes(data)
    report = {'emulator_only': True, 'ram_bytes': 1073741824,
              'debug_shell': args.debug_shell, 'storage_controller': 'USDHC4',
              'source_sha256': hashlib.sha256(original).hexdigest(),
              'output_sha256': hashlib.sha256(data).hexdigest()}
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
