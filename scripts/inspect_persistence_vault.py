#!/usr/bin/env python3
"""Inspect length-delimited MIB persistence records without printing their values."""
import argparse
import json
from pathlib import Path
import re


def records(data):
    offset = 0
    seen = set()
    while offset < len(data):
        header = re.match(rb'(\d+) (\d+) (\d+) ', data[offset:])
        if not header:
            raise ValueError(f'Invalid record header at byte {offset}')
        namespace, key, length = map(int, header.groups())
        start = offset + header.end()
        end = start + length
        if end > len(data):
            raise ValueError(f'Truncated record at byte {offset}')
        if (namespace, key) in seen:
            raise ValueError(f'Duplicate record {namespace}/{key}')
        seen.add((namespace, key))
        yield namespace, key, data[start:end]
        offset = end
        if offset < len(data):
            if data[offset:offset+1] != b'\n':
                raise ValueError(f'Missing record delimiter at byte {offset}')
            offset += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vault', type=Path)
    args = parser.parse_args()
    result = [{'namespace': n, 'key': k, 'bytes': len(v)} for n,k,v in records(args.vault.read_bytes())]
    print(json.dumps({'records': result, 'hardware_info_present': any(r['namespace']==0x80000001 and r['key']==4 for r in result)}, indent=2))
