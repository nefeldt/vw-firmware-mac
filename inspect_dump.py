#!/usr/bin/env python3
"""Inventory an extracted MIB dump without executing or modifying its contents."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct


def inspect_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        head = stream.read(64)
        digest.update(head)
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    result = {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    if head[:4] == b'\x7fELF' and len(head) >= 20:
        if head[4] in (1, 2) and head[5] in (1, 2):
            machine = struct.unpack_from('<H' if head[5] == 1 else '>H', head, 18)[0]
            result['elf'] = {
                'bits': 32 if head[4] == 1 else 64,
                'endian': 'little' if head[5] == 1 else 'big',
                'machine': machine,
                'architecture': {3: 'x86', 40: 'ARM', 62: 'x86-64', 183: 'AArch64'}.get(machine, 'unknown'),
                'osabi': head[7],
            }
        else:
            result['warning'] = 'Invalid ELF class or endianness'
    if path.suffix.lower() in ('.ifs', '.jxe', '.jar', '.so', '.mcf', '.spf'):
        result['candidate'] = path.suffix.lower()[1:]
    if path.name.lower() == 'metainfo2.txt':
        result['candidate'] = 'firmware metadata'
    return result


def inventory(root):
    files, errors, skipped = [], [], []
    def walk_error(error):
        errors.append({'path': str(error.filename), 'error': str(error)})
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for name in sorted(names):
            path = Path(directory) / name
            relative = str(path.relative_to(root))
            if path.is_symlink() or not path.is_file():
                skipped.append(relative)
                continue
            try:
                files.append({'path': relative, **inspect_file(path)})
            except OSError as error:
                errors.append({'path': relative, 'error': str(error)})
    return {'source': str(root), 'files': files, 'errors': errors, 'skipped': skipped,
            'note': 'Inventory only; IFS containers are not unpacked. This does not establish bootability.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', type=Path, help='Extracted dump directory')
    parser.add_argument('--output', type=Path, required=True, help='New JSON report outside the dump')
    args = parser.parse_args()
    root, output = args.dump.resolve(), args.output.resolve()
    if not root.is_dir():
        parser.error('Dump directory does not exist')
    if output.is_relative_to(root):
        parser.error('Output must be outside the source dump')
    report = inventory(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(f"{len(report['files'])} files, {len(report['errors'])} errors -> {output}")
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
