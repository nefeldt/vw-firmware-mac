"""Offscreen Mac OpenGL backend for a future QNX GLES command bridge.

This module does not emulate the HMI or generate replacement UI assets.
The guest transport is not connected yet.
"""
import ctypes as C
import re

U = C.c_uint
I = C.c_int
P = C.c_void_p


class MacRenderer:
    def __init__(self, width=800, height=480):
        self.width, self.height = width, height
        self.gl = C.CDLL('/System/Library/Frameworks/OpenGL.framework/OpenGL')
        self.pixel_format, self.context = P(), P()
        self._call('CGLChoosePixelFormat', I,
                   [C.POINTER(I), C.POINTER(P), C.POINTER(I)],
                   (I * 11)(99, 0x1000, 8, 24, 11, 8, 12, 24, 13, 8, 0),
                   C.byref(self.pixel_format), C.byref(I()), check=True)
        try:
            self._call('CGLCreateContext', I, [P, P, C.POINTER(P)],
                       self.pixel_format, None, C.byref(self.context), check=True)
            self._call('CGLSetCurrentContext', I, [P], self.context, check=True)
            self.texture, self.framebuffer, self.depth = U(), U(), U()
            self._call('glGenTextures', None, [I, C.POINTER(U)], 1, C.byref(self.texture))
            self._call('glBindTexture', None, [U, U], 0x0DE1, self.texture.value)
            self._call('glTexImage2D', None, [U, I, I, I, I, I, U, U, P],
                       0x0DE1, 0, 0x8058, width, height, 0, 0x1908, 0x1401, None)
            self._call('glGenFramebuffersEXT', None, [I, C.POINTER(U)], 1, C.byref(self.framebuffer))
            self._call('glBindFramebufferEXT', None, [U, U], 0x8D40, self.framebuffer.value)
            self._call('glFramebufferTexture2DEXT', None, [U, U, U, U, I],
                       0x8D40, 0x8CE0, 0x0DE1, self.texture.value, 0)
            self._call('glGenRenderbuffersEXT', None, [I, C.POINTER(U)], 1, C.byref(self.depth))
            self._call('glBindRenderbufferEXT', None, [U, U], 0x8D41, self.depth.value)
            self._call('glRenderbufferStorageEXT', None, [U, U, I, I],
                       0x8D41, 0x88F0, width, height)
            for attachment in (0x8D00, 0x8D20):
                self._call('glFramebufferRenderbufferEXT', None, [U, U, U, U],
                           0x8D40, attachment, 0x8D41, self.depth.value)
            status = self._call('glCheckFramebufferStatusEXT', U, [U], 0x8D40)
            if status != 0x8CD5:
                raise RuntimeError(f'Incomplete offscreen framebuffer: {status:#x}')
            self._call('glViewport', None, [I, I, I, I], 0, 0, width, height)
            self.assert_no_error()
        except BaseException:
            self.close()
            raise

    def _call(self, name, result, arguments, *values, check=False):
        fn = getattr(self.gl, name)
        fn.restype, fn.argtypes = result, arguments
        value = fn(*values)
        if check and value:
            raise RuntimeError(f'{name} failed: {value}')
        return value

    def info(self):
        return {name: self._call('glGetString', C.c_char_p, [U], token).decode()
                for name, token in [('vendor', 0x1F00), ('renderer', 0x1F01),
                                    ('version', 0x1F02), ('glsl', 0x8B8C)]}

    @staticmethod
    def translate_shader(source):
        """Translate the ES 1.00 precision syntax for desktop GLSL 1.20.

        Other shader differences are deliberately not guessed. Real compiler
        failures must be returned to the guest by the eventual bridge.
        """
        source = re.sub(r'^\s*#version\s+100\s*$', '#version 120', source, flags=re.M)
        source = re.sub(r'\bprecision\s+(?:lowp|mediump|highp)\s+\w+\s*;', '', source)
        return re.sub(r'\b(?:lowp|mediump|highp)\b', '', source)

    def compile_shader(self, kind, source):
        shader = self._call('glCreateShader', U, [U], kind)
        encoded = self.translate_shader(source).encode()
        pointer = C.c_char_p(encoded)
        size = I(len(encoded))
        self._call('glShaderSource', None, [U, I, C.POINTER(C.c_char_p), C.POINTER(I)],
                   shader, 1, C.byref(pointer), C.byref(size))
        self._call('glCompileShader', None, [U], shader)
        status = I()
        self._call('glGetShaderiv', None, [U, U, C.POINTER(I)], shader, 0x8B81, C.byref(status))
        if not status.value:
            log = C.create_string_buffer(8192)
            self._call('glGetShaderInfoLog', None, [U, I, C.POINTER(I), P],
                       shader, len(log), None, log)
            self._call('glDeleteShader', None, [U], shader)
            raise RuntimeError(log.value.decode(errors='replace'))
        return shader

    def link_program(self, shaders):
        program = self._call('glCreateProgram', U, [])
        for shader in shaders:
            self._call('glAttachShader', None, [U, U], program, shader)
        self._call('glLinkProgram', None, [U], program)
        status = I()
        self._call('glGetProgramiv', None, [U, U, C.POINTER(I)], program, 0x8B82, C.byref(status))
        if not status.value:
            log = C.create_string_buffer(8192)
            self._call('glGetProgramInfoLog', None, [U, I, C.POINTER(I), P],
                       program, len(log), None, log)
            self._call('glDeleteProgram', None, [U], program)
            raise RuntimeError(log.value.decode(errors='replace'))
        return program

    def read_rgba(self):
        data = (C.c_ubyte * (self.width*self.height*4))()
        self._call('glReadPixels', None, [I, I, I, I, U, U, P],
                   0, 0, self.width, self.height, 0x1908, 0x1401, data)
        self.assert_no_error()
        raw, stride = bytes(data), self.width*4
        return b''.join(raw[y*stride:(y+1)*stride] for y in reversed(range(self.height)))

    def assert_no_error(self):
        error = self._call('glGetError', U, [])
        if error:
            raise RuntimeError(f'OpenGL error: {error:#x}')

    def close(self):
        if self.context:
            self._call('CGLSetCurrentContext', I, [P], None)
            self._call('CGLDestroyContext', I, [P], self.context)
            self.context = P()
        if self.pixel_format:
            self._call('CGLDestroyPixelFormat', I, [P], self.pixel_format)
            self.pixel_format = P()


def verify_backend():
    """Exercise real shader compilation, drawing and pixel readback internally."""
    renderer = MacRenderer(32, 32)
    try:
        vertex = renderer.compile_shader(0x8B31, '''#version 100
precision highp float;
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
''')
        fragment = renderer.compile_shader(0x8B30, '''#version 100
precision mediump float;
void main() { gl_FragColor = vec4(0.25, 0.5, 0.75, 1.0); }
''')
        program = renderer.link_program([vertex, fragment])
        renderer._call('glUseProgram', None, [U], program)
        location = renderer._call('glGetAttribLocation', I, [U, C.c_char_p], program, b'position')
        vertices = (C.c_float*6)(-1, -1, 3, -1, -1, 3)
        renderer._call('glVertexAttribPointer', None, [U, I, U, C.c_ubyte, I, P],
                       location, 2, 0x1406, 0, 0, vertices)
        renderer._call('glEnableVertexAttribArray', None, [U], location)
        renderer._call('glDrawArrays', None, [U, I, I], 4, 0, 3)
        pixels = renderer.read_rgba()
        center = tuple(pixels[(16*32+16)*4:(16*32+16)*4+4])
        expected = (64, 128, 191, 255)
        if any(abs(a-b)>1 for a, b in zip(center, expected)):
            raise RuntimeError(f'Unexpected rendered pixel: {center}')
        return dict(renderer.info(), test='shader draw and readback', center_pixel=center,
                    hmi_connected=False)
    finally:
        renderer.close()


if __name__ == '__main__':
    import json
    print(json.dumps(verify_backend(), indent=2))
