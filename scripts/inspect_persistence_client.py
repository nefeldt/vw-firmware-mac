#!/usr/bin/env python3
"""Disassemble exported ARM persistence-client methods without a running VM."""
import argparse
from pathlib import Path
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB


def inspect(path, match="PersClient"):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x01\x01' or struct.unpack_from('<H', data, 18)[0] != 40:
        raise ValueError('Expected a little-endian ELF32 ARM file')
    section_offset = struct.unpack_from('<I', data, 32)[0]
    entry_size, count = struct.unpack_from('<HH', data, 46)
    sections = [struct.unpack_from('<10I', data, section_offset + i*entry_size) for i in range(count)]
    if not sections:
        # QNX IFS executables omit section headers; reconstruct dynamic symbol
        # views from PT_DYNAMIC and the SysV hash table's symbol count.
        phoff = struct.unpack_from('<I', data, 28)[0]
        phsize, phcount = struct.unpack_from('<HH', data, 42)
        segments = [struct.unpack_from('<8I', data, phoff+i*phsize) for i in range(phcount)]
        def file_offset(address):
            for segment in segments:
                if segment[0] == 1 and segment[2] <= address < segment[2]+segment[4]:
                    return segment[1]+address-segment[2]
            raise ValueError(f'Unmapped virtual address {address:#x}')
        dynamic = next(segment for segment in segments if segment[0] == 2)
        tags = {}
        for pos in range(dynamic[1], dynamic[1]+dynamic[4], 8):
            tag, value = struct.unpack_from('<II', data, pos)
            if tag == 0:
                break
            tags[tag] = value
        symbol_count = struct.unpack_from('<I', data, file_offset(tags[4])+4)[0]
        # The synthetic index 2 covers the load segment of each function below.
        sections = [(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                    (0, 3, 0, tags[5], file_offset(tags[5]), tags[10], 0, 0, 0, 0),
                    (0, 11, 0, tags[6], file_offset(tags[6]), symbol_count*tags[11], 1, 0, 0, tags[11])]
    else:
        segments = None
    relocations = {}
    if segments is not None and 23 in tags:
        names_offset = file_offset(tags[5])
        symbols_offset = file_offset(tags[6])
        for pos in range(file_offset(tags[23]), file_offset(tags[23])+tags[2], 8):
            target, info = struct.unpack_from('<II', data, pos)
            name_offset = struct.unpack_from('<I', data, symbols_offset+(info >> 8)*tags[11])[0]
            relocations[target] = data[names_offset+name_offset:].split(b'\0', 1)[0].decode('ascii', errors='replace')
    def branch_name(address):
        if not relocations:
            return ''
        try:
            offset = file_offset(address)
            first, second, third = struct.unpack_from('<3I', data, offset)
        except (ValueError, struct.error):
            return ''
        # Standard ARM PLT: add ip,pc,#imm; add ip,ip,#imm; ldr pc,[ip,#imm]!.
        if first & 0xfffff000 != 0xe28fc000 or second & 0xfffff000 != 0xe28cc000 or third & 0xfffff000 != 0xe5bcf000:
            return ''
        def immediate(word):
            value, rotate = word & 255, ((word >> 8) & 15)*2
            return ((value >> rotate) | (value << (32-rotate))) & 0xffffffff
        target = address+8+immediate(first)+immediate(second)+(third & 4095)
        return relocations.get(target, '')
    seen = set()
    for section in sections:
        if section[1] not in (2, 11):
            continue
        strings = sections[section[6]]
        names = data[strings[4]:strings[4]+strings[5]]
        for pos in range(section[4], section[4]+section[5], section[9]):
            name, address, size, info, other, index = struct.unpack_from('<IIIBBH', data, pos)
            name = names[name:].split(b'\0', 1)[0].decode('ascii', errors='replace')
            if match not in name or info & 15 != 2 or not size or not index:
                continue
            if (address, size) in seen:
                continue
            seen.add((address, size))
            if segments is not None:
                segment = next((s for s in segments if s[0] == 1 and s[2] <= (address & ~1) < s[2]+s[4]), None)
                if segment is None:
                    raise ValueError(f'Unmapped function: {name}')
                source = (0, 1, 0, segment[2], segment[1], segment[4])
            else:
                if index >= count:
                    continue
                source = sections[index]
            offset = source[4] + (address & ~1) - source[3]
            if offset < source[4] or offset + size > source[4]+source[5]:
                raise ValueError(f'Symbol outside section: {name}')
            yield f'\n{name} address=0x{address:x} size={size}'
            decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB if address & 1 else CS_MODE_ARM)
            for instruction in decoder.disasm(data[offset:offset+size], address & ~1):
                annotation = ''
                if instruction.mnemonic in ('bl', 'b') and instruction.op_str.startswith('#0x'):
                    resolved = branch_name(int(instruction.op_str[1:], 16))
                    if resolved:
                        annotation = ' ; '+resolved
                yield f'{instruction.address:08x}  {instruction.mnemonic:8} {instruction.op_str}{annotation}'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--match', default='PersClient', help='Substring of exported symbol names')
    args = parser.parse_args()
    print('\n'.join(inspect(args.library, args.match)))
