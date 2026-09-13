#!/usr/bin/env python3
"""Create an emulator-only FAT32 SD card from a supplied MIB2 map ZIP."""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import tempfile
import zipfile


def prepare(archive, output, size_gib=16):
    archive, output = archive.resolve(), output.resolve()
    if output.exists():
        raise ValueError(f'Refusing to replace existing map card: {output}')
    for tool in ('mformat', 'mcopy', 'mtype'):
        if not shutil.which(tool):
            raise ValueError('Install mtools first: brew install mtools')
    if size_gib < 1 or size_gib & (size_gib - 1):
        raise ValueError('SD size must be a positive power of two in GiB')
    output.parent.mkdir(parents=True, exist_ok=True)
    capacity = size_gib * 1024**3
    offset = 1024**2
    sectors = (capacity-offset)//512
    partial = output.with_name(output.name + '.partial')
    if partial.exists():
        raise ValueError(f'Previous incomplete card exists: {partial}')
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename:
                raise ValueError('Unsafe ZIP member path')
            if entry.file_size >= 2**32:
                raise ValueError('Map file exceeds FAT32 file size limit')
        names = {entry.filename.lower(): entry.filename for entry in entries}
        root_name = names.get('maps/00/nds/root.nds')
        info_name = names.get('maps/00/nds/dbinfo.txt')
        if not root_name or not info_name:
            raise ValueError('Expected maps/00/nds/ROOT.NDS and dbinfo.txt')
        total = sum(entry.file_size for entry in entries)
        if total > capacity * .9:
            raise ValueError('Map archive is too large for this card')
        if shutil.disk_usage(output.parent).free < total * 2 + 512*1024**2:
            raise ValueError('Insufficient space for extracted maps and FAT image')
        info = source.read(info_name)
        with tempfile.TemporaryDirectory(prefix='map-build-', dir=output.parent) as temp:
            print(f'Extracting and checking ZIP CRCs ({total / 1024**3:.2f} GiB)...', flush=True)
            source.extractall(temp)
            mbr = bytearray(512)
            struct.pack_into('<B3sB3sII', mbr, 446, 0, b'\xfe\xff\xff',
                             0x0c, b'\xfe\xff\xff', offset//512, sectors)
            mbr[510:512] = b'\x55\xaa'
            try:
                with partial.open('xb') as stream:
                    stream.truncate(capacity)
                    stream.write(mbr)
                image = str(partial) + '@@' + str(offset)
                subprocess.run(['mformat', '-i', image, '-F', '-T', str(sectors),
                                '-H', str(offset//512), '-v', 'SEAT_MAPS', '::'], check=True)
                print('Writing maps into the virtual SD card...', flush=True)
                subprocess.run(['mcopy', '-i', image, '-s', str(Path(temp)/'maps'), '::/'], check=True)
                actual = subprocess.check_output(['mtype', '-i', image, '::/' + info_name])
                if actual != info:
                    raise ValueError('Map metadata read-back mismatch')
                # Verify the database root was written, not just the metadata.
                root = subprocess.check_output(['mtype', '-i', image, '::/' + root_name])
                if root != source.read(root_name):
                    raise ValueError('Map database root read-back mismatch')
                partial.rename(output)
            except BaseException:
                partial.unlink(missing_ok=True)
                raise
    report = {'archive': str(archive), 'image': str(output), 'size_bytes': capacity,
              'partition_offset': offset, 'files': len(entries), 'map_bytes': total,
              'dbinfo': info.decode(errors='replace'), 'guest_verified': False}
    output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Map card ready: {output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, default=Path('local-data/maps/navigation-sd.img'))
    parser.add_argument('--size-gib', type=int, default=16)
    args = parser.parse_args()
    prepare(args.archive, args.output, args.size_gib)
