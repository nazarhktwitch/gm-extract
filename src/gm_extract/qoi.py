from .binary import to_s32, u16, u32

MAX_DIMENSION = 16384

def decode_qoi(buf):
    """Decode the GameMaker QOI variant (magic 'fioq'). Returns (w, h, rgba)."""
    if buf[:4] != b"fioq":
        raise ValueError("not a GameMaker QOI image (expected magic 'fioq')")
    w = u16(buf, 4)
    h = u16(buf, 6)
    if not (0 < w <= MAX_DIMENSION and 0 < h <= MAX_DIMENSION):
        raise ValueError(f"invalid QOI dimensions: {w}x{h}")
    length = u32(buf, 8)
    src = buf[12:12 + length]

    out = bytearray(w * h * 4)
    total = w * h
    px = 0
    pos = 0
    run = 0
    r = g = b = 0
    a = 255
    index = bytearray(64 * 4)

    while px < total:
        if run > 0:
            n = min(run, total - px)
            out[px * 4:(px + n) * 4] = bytes((r, g, b, a)) * n
            px += n
            run -= n
            continue
        if pos >= len(src):
            break
        b1 = src[pos]
        pos += 1

        if b1 & 0xC0 == 0x00:
            ip = b1 << 2
            r, g, b, a = index[ip], index[ip + 1], index[ip + 2], index[ip + 3]
        elif b1 & 0xE0 == 0x40:
            run = b1 & 0x1F
        elif b1 & 0xE0 == 0x60:
            b2 = src[pos]
            pos += 1
            run = (((b1 & 0x1F) << 8) | b2) + 32
        elif b1 & 0xC0 == 0x80:
            r = (r + (to_s32((b1 & 48) << 26) >> 30)) & 0xFF
            g = (g + (to_s32((b1 & 12) << 28) >> 22 >> 8)) & 0xFF
            b = (b + (to_s32((b1 & 3) << 30) >> 14 >> 16)) & 0xFF
        elif b1 & 0xE0 == 0xC0:
            b2 = src[pos]
            pos += 1
            merged = (b1 << 8) | b2
            r = (r + (to_s32((merged & 7936) << 19) >> 27)) & 0xFF
            g = (g + (to_s32((merged & 240) << 24) >> 20 >> 8)) & 0xFF
            b = (b + (to_s32((merged & 15) << 28) >> 12 >> 16)) & 0xFF
        elif b1 & 0xF0 == 0xE0:
            b2 = src[pos]
            b3 = src[pos + 1]
            pos += 2
            merged = (b1 << 16) | (b2 << 8) | b3
            r = (r + (to_s32((merged & 1015808) << 12) >> 27)) & 0xFF
            g = (g + (to_s32((merged & 31744) << 17) >> 19 >> 8)) & 0xFF
            b = (b + (to_s32((merged & 992) << 22) >> 11 >> 16)) & 0xFF
            a = (a + (to_s32((merged & 31) << 27) >> 3 >> 24)) & 0xFF
        elif b1 & 0xF0 == 0xF0:
            if b1 & 8:
                r = src[pos]
                pos += 1
            if b1 & 4:
                g = src[pos]
                pos += 1
            if b1 & 2:
                b = src[pos]
                pos += 1
            if b1 & 1:
                a = src[pos]
                pos += 1

        out[px * 4:px * 4 + 4] = bytes((r, g, b, a))
        px += 1
        ip = ((r ^ g ^ b ^ a) & 63) << 2
        index[ip:ip + 4] = bytes((r, g, b, a))

    return w, h, bytes(out)
