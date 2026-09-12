#!/usr/bin/env python3
"""Experimental HSB$ method-4 word-LZSS decoder, validated separately by dumpifs."""
import argparse,json,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
b=a.input.read_bytes();header=b.find(b'HSB$')
if header<0:raise ValueError('HSB$ header absent')
magic,method,checksum,address,field=struct.unpack_from('<4sHHII',b,header)
if method!=4:raise ValueError(f'Unsupported compression {method}')
pos=header+16;out=bytearray();expected=None
while expected is None or len(out)<expected:
 if pos+2>len(b):raise ValueError('Truncated flags')
 flags=struct.unpack_from('<H',b,pos)[0];pos+=2
 for bit in range(16):
  if expected is not None and len(out)>=expected:break
  if pos+2>len(b):raise ValueError('Truncated token')
  word=struct.unpack_from('<H',b,pos)[0];pos+=2
  if flags>>bit&1:out.extend(struct.pack('<H',word))
  else:
   distance=((word&4095)+1)*2;length=((word>>12)+2)*2
   if distance>len(out):raise ValueError('Invalid back-reference')
   for _ in range(length):out.append(out[-distance])
  if expected is None and len(out)>=64:
   if out[8:12]!=bytes.fromhex('eb7eff00'):raise ValueError('No QNX startup at output offset 8')
   expected=8+struct.unpack_from('<I',out,8+36)[0]
   if not 256<=expected<=128*1024*1024:raise ValueError('Invalid stored size')
if len(out)!=expected:raise ValueError('Decoded size overshoot')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(out)
report={'source':str(a.input),'wrapper_offset':header,'method':method,'wrapper_checksum_unverified':checksum,'load_address':hex(address),'wrapper_field':field,'consumed_input':pos,'remaining_input':len(b)-pos,'decoded_bytes':len(out),'startup_offset':8,'entry':hex(struct.unpack_from('<I',out,20)[0])}
a.output.with_suffix(a.output.suffix+'.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
