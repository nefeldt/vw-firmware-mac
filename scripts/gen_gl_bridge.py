#!/usr/bin/env python3
"""Generate a separately selectable GLES RPC implementation and ABI manifest."""
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
source=(ROOT/'guest/shim/src/libGLESv2_stub.c').read_text()
prefix=source[:source.index('static GLuint stub_array_buffer;')]
prefix+='\n#include "gl_rpc.h"\nstatic GLuint array_buffer, element_buffer;\n'
functions=re.findall(r'^([\w *]+?) (gl\w+)\(([^\n]*)\) \{',source,re.M)
manifest={}
output=[prefix]
for op,(result,name,declaration) in enumerate(functions,1):
    params=[]
    if declaration!='void':
        for param in declaration.split(','):
            match=re.match(r'\s*(.*?)\s*(\w+)\s*$',param)
            params.append((match[1].strip(),match[2]))
    body=[]; descriptors=[]; supported=True
    for typ,arg in params:
        mode=0; size=f'sizeof({arg})'; pointer=f'&{arg}'
        if '*' in typ:
            pointer=arg; mode=1
            if name=='glShaderSource' and arg=='string':
                pointer='joined';size='joined_size'
            elif name=='glShaderSource' and arg=='length':pointer='0';size='0'
            elif 'char' in typ and 'const' in typ:size=f'{arg} ? strlen({arg})+1 : 0'
            elif name.startswith(('glGen','glDelete')):size='n*sizeof(GLuint)';mode=2 if name.startswith('glGen') else 1
            elif name in ('glBufferData','glBufferSubData'):size='size'
            elif name in ('glTexImage2D','glTexSubImage2D','glReadPixels'):
                size='pixel_bytes(width,height,format,type)';mode=2 if name=='glReadPixels' else 1
            elif name.startswith('glCompressedTex'):size='imageSize'
            elif name=='glVertexAttribPointer':mode=0;pointer='&ptr';size='sizeof(ptr)'
            elif name=='glDrawElements':
                mode='element_buffer ? 0 : 1';pointer='element_buffer ? (void *)&indices : (void *)indices';size='element_buffer ? sizeof(indices) : count*(type==GL_UNSIGNED_BYTE?1:2)'
            elif name.startswith('glUniformMatrix'):
                dim=int(name[len('glUniformMatrix')]);size=f'count*{dim*dim}*sizeof(GLfloat)'
            elif re.match(r'glUniform[1-4][fi]v$',name):size=f'count*{name[9]}*4'
            elif name in ('glGetIntegerv','glGetFloatv','glGetBooleanv'):
                size=f'(pname==GL_VIEWPORT || pname==GL_SCISSOR_BOX || pname==GL_COLOR_WRITEMASK ? 4 : pname==GL_MAX_VIEWPORT_DIMS || pname==GL_ALIASED_LINE_WIDTH_RANGE || pname==GL_ALIASED_POINT_SIZE_RANGE ? 2 : 1)*sizeof(*{arg})';mode=2
            elif name in ('glGetActiveAttrib','glGetActiveUniform'):
                size='bufsize' if arg=='name' else f'sizeof(*{arg})';mode=2
            elif name in ('glGetProgramInfoLog','glGetShaderInfoLog','glGetShaderSource'):
                size='bufsize' if arg in ('infolog','source') else f'sizeof(*{arg})';mode=2
            elif name in ('glGetProgramiv','glGetShaderiv','glGetBufferParameteriv','glGetRenderbufferParameteriv','glGetFramebufferAttachmentParameteriv'):
                size=f'sizeof(*{arg})';mode=2
            elif name=='glGetShaderPrecisionFormat':size='2*sizeof(GLint)' if arg=='range' else 'sizeof(GLint)';mode=2
            elif name.startswith('glVertexAttrib') and name.endswith('fv'):size=f'{name[14]}*sizeof(GLfloat)'
            else:supported=False;size='0'
        descriptors.append(f'{{(void *)({pointer}), {size}, {mode}}}')
    if '*' in result and name!='glGetString':supported=False
    manifest[str(op)]={'name':name,'result':result,'params':params,'supported':supported}
    output.append(f'{result} {name}({declaration}) {{')
    if name=='glGetError':body.append('if(rpc_error) { GLenum e=rpc_error; rpc_error=0; return e; }')
    if name=='glBindBuffer':body.append('if(target==GL_ARRAY_BUFFER) array_buffer=buffer; if(target==GL_ELEMENT_ARRAY_BUFFER) element_buffer=buffer;')
    if name=='glVertexAttribPointer':body.append('if(!array_buffer && ptr) { rpc_error=GL_INVALID_OPERATION; stub_log("Client vertex arrays unsupported"); return; }')
    if name=='glShaderSource':
        body.append('unsigned joined_size=1; int i; char *joined,*cursor; for(i=0;i<count;i++) joined_size+=(length && length[i]>=0)?length[i]:strlen(string[i]); joined=malloc(joined_size); if(!joined) { rpc_error=GL_OUT_OF_MEMORY; return; } cursor=joined; for(i=0;i<count;i++) { unsigned n=(length && length[i]>=0)?length[i]:strlen(string[i]); memcpy(cursor,string[i],n); cursor+=n; } *cursor=0;')
    body.append('RpcArg args[] = {'+(','.join(descriptors) or '{0,0,0}')+'};')
    if supported:
        if name=='glGetString':
            body.append(f'static char strings[5][65536]; unsigned slot=name==GL_VENDOR?0:name==GL_RENDERER?1:name==GL_VERSION?2:name==GL_EXTENSIONS?3:4; rpc({op},{len(params)},args,strings[slot],sizeof(strings[slot])); return (const GLubyte *)strings[slot];')
        else:
            body.append(f'uint32_t result=rpc({op},{len(params)},args,0,0);')
            if name=='glShaderSource':body.append('free(joined);')
            if result!='void':body.append(f'return ({result})(uintptr_t)result;')
    else:
        body.append(f'stub_log("Unsupported GL bridge call: {name}"); rpc_error=GL_INVALID_OPERATION;')
        if result!='void':body.append(f'return ({result})0;')
    output.extend('    '+line for line in body);output.append('}\n')
(ROOT/'guest/shim/src/libGLESv2_bridge.c').write_text('\n'.join(output))
(ROOT/'runtime/graphics/gl_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Generated {len(functions)} entry points; {sum(m["supported"] for m in manifest.values())} supported')
