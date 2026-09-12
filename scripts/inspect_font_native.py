import struct
from pathlib import Path
p=Path('extracted/P0480T/hmi/tsd/tmp/hmi/libtsd.mibstd2.hmi.dsi.native.so');b=p.read_bytes()
so=struct.unpack_from('<I',b,32)[0];sz,n=struct.unpack_from('<HH',b,46);secs=[struct.unpack_from('<10I',b,so+i*sz) for i in range(n)]

from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
md=Cs(CS_ARCH_ARM,CS_MODE_ARM);md.detail=True
symbols={};got={}
for s in secs:
 if s[1] not in (2,11):continue
 st=secs[s[6]];strings=b[st[4]:st[4]+st[5]];tab=[]
 for pos in range(s[4],s[4]+s[5],s[9]):
  name,value,size,info,other,ndx=struct.unpack_from('<IIIBBH',b,pos);name=strings[name:strings.find(b'\0',name)].decode(errors='replace');tab.append(name)
  if value:symbols[value]=name
 for rel in secs:
  if rel[1]==9 and secs[rel[6]]==s:
   for pos in range(rel[4],rel[4]+rel[5],8):
    addr,info=struct.unpack_from('<II',b,pos);got[addr]=tab[info>>8]
def read(addr,n=4):
 s=next(s for s in secs if s[1]!=8 and s[3]<=addr<s[3]+s[5]);return b[s[4]+addr-s[3]:s[4]+addr-s[3]+n]
for addr in range(0x7c000,0x85000,4):
 try:
  ins=list(md.disasm(read(addr,12),addr))
  if len(ins)==3 and ins[0].mnemonic=='add' and ins[0].op_str.startswith('ip, pc,') and ins[1].mnemonic=='add' and ins[2].mnemonic=='ldr':
   def imm(i):
    v=i.operands[2].imm;r=i.operands[3].imm if len(i.operands)>3 else 0;return ((v>>r)|(v<<(32-r)))&0xffffffff if r else v
   target=addr+8+imm(ins[0])+imm(ins[1])+ins[2].operands[1].mem.disp
   if target in got:symbols[addr]=got[target]
 except (StopIteration,IndexError):pass
for start,length in [(0x8e4dc,2044),(0x8f174,676)]:
 for i in md.disasm(read(start,length),start):
  note=''
  if i.mnemonic in ('bl','b') and i.operands[0].type==2:note=symbols.get(i.operands[0].imm,'')
  if i.mnemonic=='ldr' and len(i.operands)>1 and i.operands[1].type==3 and i.reg_name(i.operands[1].mem.base)=='pc':
   value=struct.unpack('<I',read(i.address+8+i.operands[1].mem.disp))[0];note=hex(value)
  print(hex(i.address),i.mnemonic,i.op_str,note)
for i in md.disasm(read(0x7f8c0,12),0x7f8c0): print(i.mnemonic,i.op_str,[(o.type,o.imm) for o in i.operands])
print('GOT',list(got.items())[:3])
base=0x8e4f4+8+0x4c3af8
for delta in (0xffe362bc,0xffe362c4,0xfffdeaec):
 addr=(base+delta)&0xffffffff;print(hex(addr),read(addr,150).split(b'\0')[0])
