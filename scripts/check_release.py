#!/usr/bin/env python3
"""Audit the Git index for private inputs and non-source artifacts before publishing."""
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parent.parent
FORBIDDEN={'firmware','extracted','reports','vendor','preview','.venv','build','__pycache__'}
SUFFIXES={'.so','.dylib','.jxe','.jar','.class','.img','.qcow2','.ifs','.bin','.boot','.ttf','.otf','.png','.heic','.log','.iso','.7z'}
def audit():
    result=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True)
    if result.returncode:raise SystemExit('Run inside a Git checkout. Stage the intended public source before auditing.')
    files=[p for p in result.stdout.decode().split('\0') if p];errors=[]
    if not files:errors.append('No tracked source files: stage the intended public files first')
    for name in files:
        path=Path(name)
        if any(part in FORBIDDEN for part in path.parts) or path.name.lower() in ('claude.md','agent.md') or path.suffix.lower() in SUFFIXES or name.startswith('guest/dsi/include/'):
            errors.append(f'Private/generated artifact: {name}');continue
        data=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
        if len(data)>1024*1024:errors.append(f'Unexpected large file: {name}')
        if b'\0' in data:errors.append(f'Binary content: {name}')
        text=data.decode('utf-8',errors='replace')
        for pattern in (r'/Users/[A-Za-z0-9_.-]+/',r'/private/var/folders/',r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}'):
            if re.search(pattern,text):errors.append(f'Personal path or credential pattern: {name}');break
    for name in ('claude.md','agent.md','firmware/example.7z','extracted/eMMC/emmc.img','reports/hmi-render.png','guest/dsi/include/jni.h'):
        check=subprocess.run(['git','check-ignore','--quiet',name],cwd=ROOT)
        if check.returncode:errors.append(f'Expected private path is not ignored: {name}')
    if errors:raise SystemExit('\n'.join(errors))
    print(f'Public source audit passed: {len(files)} tracked files; private inputs excluded.')
if __name__=='__main__':audit()
