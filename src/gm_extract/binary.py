import struct

def u16(buf, offset):
    return struct.unpack_from("<H", buf, offset)[0]

def u32(buf, offset):
    return struct.unpack_from("<I", buf, offset)[0]

def i32(buf, offset):
    return struct.unpack_from("<i", buf, offset)[0]

def f32(buf, offset):
    return struct.unpack_from("<f", buf, offset)[0]

def to_s32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value
