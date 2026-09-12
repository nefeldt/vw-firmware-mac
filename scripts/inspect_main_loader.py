#!/usr/bin/env python3
"""Extract the word-swapped J5 loader and document its image-reader code.

This is static analysis, not a decoder for the MAIN firmware payload.
Offsets in disassembly are relative to the executable's first instruction.
"""
from pathlib import Path
import hashlib
import json
import struct

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

ROOT = Path(__file__).resolve().parent.parent
source = ROOT / 'firmware/P0480T/main/mainboot_sec/24/default/init_mibstd2_main_sec.dat'
raw = source.read_bytes()
if len(raw) % 4:
    raise ValueError('Loader is not word aligned')
swapped = b''.join(raw[i:i+4][::-1] for i in range(0, len(raw), 4))
entries = []
for pos in range(0, 0x200, 32):
    offset, length = struct.unpack_from('<II', swapped, pos)
    name = swapped[pos+20:pos+32].split(b'\0', 1)[0]
    if name in (b'X-LOADER', b'PRIMAPP', b'KEYS'):
        if offset + length > len(swapped):
            raise ValueError('TOC entry outside file')
        entries.append({'name': name.decode(), 'offset': offset, 'length': length})
xloader = next(e for e in entries if e['name'] == 'X-LOADER')
start = xloader['offset'] + 0x400
code = swapped[start:xloader['offset'] + xloader['length']]
if code[:4] != bytes.fromhex('020000ea') or code[4:8] != b'$HDR':
    raise ValueError('Unexpected executable header; do not reuse known code offsets')
out = ROOT / 'extracted/P0480T'
(out / 'init_mibstd2_main_sec.dat.wordswap').write_bytes(swapped)
(out / 'main-xloader.bin').write_bytes(code)
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
sections = [
    ('Record dispatcher: reads 12-byte records, type 11 calls inflate wrapper', 0x79c, 0xa34),
    ('Halfword reader wrapper', 0x3450, 0x3474),
    ('Streaming zlib wrapper', 0x3a9c, 0x3bbc),
    ('Record type 11 wrapper', 0x3bbc, 0x3bf4),
]
lines = []
for title, a, z in sections:
    lines.append('\n' + title)
    lines.extend(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(code[a:z], a))
(ROOT / 'reports/main-loader-image-reader.log').write_text('\n'.join(lines) + '\n')
report = {
    'source': str(source.relative_to(ROOT)),
    'sha256': hashlib.sha256(raw).hexdigest(),
    'toc': entries,
    'executable_offset': start,
    'executable_size': len(code),
    'header_word_8': hex(struct.unpack_from('<I', code, 8)[0]),
    'main_payload_decoded': False,
    'note': 'Bootloader record framing does not yet identify update-package framing or encryption.',
}
(ROOT / 'reports/main-loader-layout.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
