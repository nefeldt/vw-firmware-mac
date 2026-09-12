#!/usr/bin/env python3
"""Decode captured native DSI persistence request headers; never sends packets."""
import argparse
import json
import re
import struct
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('trace', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
mapping = json.loads((root/'reports/dsi-persistence-wire-map.json').read_text())
names = {event: item['method'] for item in mapping['methods']
         for event in item['event_candidates']}
names.update({0: 'notifyForAttributes', 3839: 'notifyForAttribute'})
packets = []
for direction, length, hexdata in re.findall(
        r'(JNI_TX|TX|RX) len=(\d+) hex=([0-9a-f]*)', args.trace.read_text(errors='replace')):
    data = bytes.fromhex(hexdata)
    if len(data) < 12:
        continue
    route, version, event = struct.unpack_from('<III', data)
    if version != mapping['version_hash']:
        continue
    item = dict(direction=direction, length=int(length), route=hex(route),
                event=event, method=names.get(event, 'unknown'), prefix=hexdata)
    if event in (1001, 1003, 1005, 1007, 1009, 1019, 1020, 1021, 1022, 1023) and len(data) >= 24:
        item['namespace'], item['key'] = struct.unpack_from('<IQ', data, 12)
    packets.append(item)
print(json.dumps(packets, indent=2))
