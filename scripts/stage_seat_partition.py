#!/usr/bin/env python3
"""Add a read-only SEAT data IFS to a fourth partition in the QEMU overlay."""
import json
import struct
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = root/'extracted/eMMC/emmc.img'
payload = root/'extracted/P0480T/seat-transfer.ifs'
overlay = root/'qemu/emmc-overlay.qcow2'
offset = 0xe5000000
size = payload.stat().st_size
assert 0 < size <= 0x100000000-offset
assert offset >= source.stat().st_size
assert payload.read_bytes()[:7] == b'imagefs', 'Not a data IFS'
with source.open('rb') as stream:
    mbr = bytearray(stream.read(512))
assert mbr[510:512] == b'\x55\xaa'
assert mbr[494:510] == bytes(16), 'Original fourth partition is not empty'
sectors = (size+511)//512
struct.pack_into('<B3sB3sII', mbr, 494, 0, b'\xfe\xff\xff',
                 0xda, b'\xfe\xff\xff', offset//512, sectors)
mbr_file = root/'qemu/emmc-seat-mbr.bin'
mbr_file.write_bytes(mbr)
# qemu-io writes only the existing qcow2 overlay, never its raw backing file.
for file, start, length in [(payload, offset, size), (mbr_file, 0, 512)]:
    subprocess.run(['qemu-io', '-f', 'qcow2', '-c',
                    f'write -s {file} {start} {length}', str(overlay)], check=True)
report = {'payload_bytes': size, 'offset': offset, 'sectors': sectors,
          'device': '/dev/hd0t218', 'source_unchanged': str(source),
          'mount': 'mount_ifs -f /dev/hd0t218 -m /seat'}
(root/'reports/seat-transfer.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
