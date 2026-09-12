#!/usr/bin/env python3
"""Read-only extraction of the three MBR QNX6 partitions; links stay in manifest."""
import json, stat, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/qnxmount'))
from qnxmount.stream import Stream
from qnxmount.qnx6.interface import QNX6FS
image=ROOT/'extracted/eMMC/emmc.img'
out=ROOT/'extracted/eMMC/filesystems'
records=[]
with image.open('rb') as f: mbr=f.read(512)
for i in range(4):
 entry=mbr[446+16*i:462+16*i]
 start,count=struct.unpack_from('<II',entry,8)
 if not count: continue
 base=out/f'p{i+1}';base.mkdir(parents=True,exist_ok=True)
 with Stream(image,start*512) as stream:
  fs=QNX6FS(stream);seen=set()
  def walk(ino,rel):
   node=fs.get_inode(ino)
   record={'partition':i+1,'path':rel.as_posix(),'inode':ino,'mode':node.mode,'size':node.size}
   records.append(record)
   target=base/rel
   if stat.S_ISDIR(node.mode):
    if ino in seen: return
    seen.add(ino);target.mkdir(parents=True,exist_ok=True)
    for e in fs.get_dir(ino).entries:
     name=e.content.name
     if name in ('.','..'):continue
     if not name or '/' in name or '\0' in name:raise ValueError('invalid directory name')
     walk(e.inode_number,rel/name)
   elif stat.S_ISREG(node.mode):
    with target.open('wb') as f:
     for offset in range(0,node.size,1024*1024):f.write(fs.read_file(node,offset,min(1024*1024,node.size-offset)))
   elif stat.S_ISLNK(node.mode):
    record['link_target']=fs.read_file(node).decode('utf-8',errors='replace')
   if len(records)%1000==0:print(len(records),'entries',flush=True)
  walk(1,Path('.'))
 print('partition',i+1,'complete',flush=True)
(ROOT/'reports/emmc-files.json').write_text(json.dumps(records,indent=2)+'\n')
print('Total',len(records),flush=True)
