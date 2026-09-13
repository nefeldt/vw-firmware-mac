#!/usr/bin/env python3
"""Decode the original client's syncConfigure payload; no service emulation."""
import argparse
import json
from pathlib import Path
import struct


def decode(data):
    if len(data) < 16:
        raise ValueError('Truncated configuration header')
    header0, header1, header2, count = struct.unpack_from('<4I', data)
    if len(data) != 16 + count*20:
        raise ValueError('Configuration length does not match record count')
    requests = []
    for offset in range(16, len(data), 20):
        namespace, key, field8, field12, field16 = struct.unpack_from('<5I', data, offset)
        if field8 > 0xffff or field16 > 0xffff:
            raise ValueError('Serialized 16-bit field exceeds its native range')
        requests.append(dict(namespace=namespace, key=key,
                             field_08=field8, field_0c=field12, field_10=field16))
    return dict(header=[header0, header1, header2], requests=requests)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=Path)
    args = parser.parse_args()
    print(json.dumps(decode(args.payload.read_bytes()), indent=2))
