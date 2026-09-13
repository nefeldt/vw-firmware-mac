#!/usr/bin/env python3
"""Add a read-only SEAT data IFS to a fourth partition in the QEMU overlay."""
import argparse
import json
import tempfile
import struct
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = root/'extracted/eMMC/emmc.img'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--payload', type=Path, default=root/'extracted/P0480T/seat-transfer.ifs')
parser.add_argument('--overlay', type=Path, default=(root/'local-data/runtime/emmc-overlay.qcow2'
                    if (root/'local-data/runtime/emmc-overlay.qcow2').is_file()
                    else root/'qemu/emmc-overlay.qcow2'))
parser.add_argument('--report', type=Path, default=root/'reports/seat-transfer.json')
args = parser.parse_args()
payload = args.payload.resolve()
overlay = args.overlay.resolve()
if overlay == source.resolve():
    raise SystemExit('Refusing to overwrite the original eMMC dump')
offset = 0xe5000000
size = payload.stat().st_size
assert 0 < size <= 0x100000000-offset
assert offset >= source.stat().st_size
with payload.open('rb') as stream:
    assert stream.read(7) == b'imagefs', 'Not a data IFS'
with source.open('rb') as stream:
    mbr = bytearray(stream.read(512))
assert mbr[510:512] == b'\x55\xaa'
assert mbr[494:510] == bytes(16), 'Original fourth partition is not empty'
sectors = (size+511)//512
struct.pack_into('<B3sB3sII', mbr, 494, 0, b'\xfe\xff\xff',
                 0xda, b'\xfe\xff\xff', offset//512, sectors)
# Keep diagnostic runs from sharing a mutable MBR temporary file.
with tempfile.TemporaryDirectory(prefix='mib-stage-', dir=root/'qemu') as work:
    mbr_file = Path(work)/'mbr.bin'
    mbr_file.write_bytes(mbr)
    (Path(work)/'payload.ifs').symlink_to(payload)
    # Fixed relative names avoid qemu-io command parsing of arbitrary paths.
    # qemu-io enforces the qcow2 write lock; do not use force-share.
    for name, start, length in [('payload.ifs', offset, size), ('mbr.bin', 0, 512)]:
        subprocess.run(['qemu-io', '-f', 'qcow2', '-c',
                        f'write -s {name} {start} {length}', str(overlay)],
                       cwd=work, check=True)
report = {'overlay': str(overlay), 'payload': str(payload), 'payload_bytes': size, 'offset': offset, 'sectors': sectors,
          'device': '/dev/hd0t218', 'source_unchanged': str(source),
          'mount': 'mount_ifs -f /dev/hd0t218 -m /seat'}
args.report.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
