import re,sys
txt=open('dump.txt').read()
sec={}
for part in txt.split('=====')[1:]:
    name,_,body=part.partition('\n'); sec[name]=body
# relocs: GOT address -> symbol
got={}
for m in re.finditer(r'^([0-9a-f]{8})\s+R_ARM_JUMP_SLOT\s+(\S+)',sec['RELOCS'],re.M):
    got[int(m.group(1),16)]=m.group(2)
# plt: parse stubs: add ip, pc, #a ; add ip, ip, #b ; ldr pc, [ip, #c]!
plt={}
lines=sec['PLT'].splitlines()
for i,l in enumerate(lines):
    m=re.match(r'\s*([0-9a-f]+):\s+add\s+ip, pc, #(\d+)(?:, 12)?',l)
    if not m: continue
    addr=int(m.group(1),16); a=int(m.group(2))
    m2=re.match(r'\s*[0-9a-f]+:\s+add\s+ip, ip, #(\d+)',lines[i+1])
    m3=re.match(r'\s*[0-9a-f]+:\s+ldr\s+pc, \[ip, #(\d+)\]!',lines[i+2])
    if not(m2 and m3): continue
    target=addr+8+a+int(m2.group(1))+int(m3.group(1))
    plt[addr]=got.get(target,'?%x'%target)
# _init base
m=re.search(r'^([0-9a-f]{8}) T _init$',sec['SYMS'],re.M)
init=int(m.group(1),16)
def repl(m):
    off=int(m.group(1),16); return '<'+plt.get(init+off,'_init+0x%x'%off)+'>'
out=re.sub(r'<_init\+0x([0-9a-f]+)>',repl,sec['FUNCS'])
# resolve literal pool loads: "ldr rX, [pc, #imm]" -> value from disassembly ".word" lines
words={}
for m in re.finditer(r'^\s*([0-9a-f]+):\s+\.word\s+0x([0-9a-f]+)',sec['FUNCS'],re.M):
    words[int(m.group(1),16)]=int(m.group(2),16)
# rodata strings
ro={}
m=re.search(r'Contents of section \.rodata:\n(.*)',sec['RODATA'],re.S)
data=bytearray(); base=None
for l in m.group(1).splitlines():
    mm=re.match(r'\s*([0-9a-f]+) ((?:[0-9a-f]{2,8} ?){1,4})',l)
    if not mm: continue
    a=int(mm.group(1),16)
    if base is None: base=a
    for h in mm.group(2).split(): data+=bytes.fromhex(h)
def rostr(addr):
    if base is None or addr<base or addr>=base+len(data): return None
    e=data.find(b'\0',addr-base); s=data[addr-base:e]
    try: return s.decode()
    except: return None
def repl2(m):
    pcaddr=int(m.group(1),16); imm=int(m.group(3) or 0)
    val=words.get(pcaddr+8+imm)
    if val is None: return m.group(0)
    s=rostr(val)
    return m.group(0)+('   ; =0x%x %s'%(val,repr(s) if s else ''))
out=re.sub(r'^\s*([0-9a-f]+):\s+ldr\s+(\w+), \[pc(?:, #(\d+))?\].*$',repl2,out,flags=re.M)
open('funcs_annotated.txt','w').write(out)
print(len(plt),'plt stubs', len(got),'got entries')
