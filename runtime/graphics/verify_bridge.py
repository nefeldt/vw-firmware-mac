"""Validate marshalled shader, buffer, reflection, uniform and draw commands."""
import json
import struct
from gl_server import Bridge, MANIFEST

ops={spec['name']:int(op) for op,spec in MANIFEST.items()}
def integer(value):return (0,4,struct.pack('<I',value & 0xffffffff))
def floating(value):return (0,4,struct.pack('<f',value))
def blob(value):return (1,len(value),value)
def output(size):return (2,size,b'')
def null():return (1,0,b'')

bridge=Bridge()
try:
    def call(name,*args):return bridge.execute(ops[name],list(args))
    shaders=[]
    for kind,source in [(0x8B31,b'#version 100\nattribute vec2 position; void main(){gl_Position=vec4(position,0.,1.);}'),
                        (0x8B30,b'#version 100\nprecision mediump float; uniform vec4 color; void main(){gl_FragColor=color;}')]:
        shader=call('glCreateShader',integer(kind))[0]
        call('glShaderSource',integer(shader),integer(1),blob(source+b'\0'),null())
        call('glCompileShader',integer(shader))
        status=call('glGetShaderiv',integer(shader),integer(0x8B81),output(4))[2][0]
        assert struct.unpack('<i',status)[0]==1
        shaders.append(shader)
    program=call('glCreateProgram')[0]
    for shader in shaders:call('glAttachShader',integer(program),integer(shader))
    call('glLinkProgram',integer(program))
    active=call('glGetActiveUniform',integer(program),integer(0),integer(64),output(4),output(4),output(4),output(64))[2]
    assert active[3].split(b'\0')[0]==b'color',active
    assert struct.unpack('<I',active[2])[0]==0x8B52
    call('glUseProgram',integer(program))
    location=call('glGetUniformLocation',integer(program),blob(b'color\0'))[0]
    call('glUniform4f',integer(location),floating(.25),floating(.5),floating(.75),floating(1))
    attribute=call('glGetAttribLocation',integer(program),blob(b'position\0'))[0]
    buffer=struct.unpack('<I',call('glGenBuffers',integer(1),output(4))[2][0])[0]
    call('glBindBuffer',integer(0x8892),integer(buffer))
    vertices=struct.pack('<6f',-1,-1,3,-1,-1,3)
    call('glBufferData',integer(0x8892),integer(len(vertices)),blob(vertices),integer(0x88E4))
    call('glVertexAttribPointer',integer(attribute),integer(2),integer(0x1406),(0,1,b'\0'),integer(8),integer(0))
    call('glEnableVertexAttribArray',integer(attribute))
    call('glDrawArrays',integer(4),integer(0),integer(3))
    pixels=bridge.renderer.read_rgba()
    center=tuple(pixels[(240*800+400)*4:(240*800+400)*4+4])
    assert all(abs(a-b)<=1 for a,b in zip(center,(64,128,191,255))),center
    bad=call('glCreateShader',integer(0x8B31))[0]
    call('glShaderSource',integer(bad),integer(1),blob(b'not a valid shader\0'),null())
    call('glCompileShader',integer(bad))
    failed=call('glGetShaderiv',integer(bad),integer(0x8B81),output(4))[2][0]
    assert failed==b'\0'*4
    print(json.dumps(dict(commands=bridge.commands,center_pixel=center,
                         reflection_verified=True,invalid_shader_rejected=True,
                         hmi_connected=False),indent=2))
finally:bridge.close()
