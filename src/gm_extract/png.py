import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

def write_png(path, width, height, rgba, level=6):
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        body = tag + payload
        return (struct.pack(">I", len(payload)) + body +
                struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    png = PNG_SIGNATURE
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), level))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)

def crop_rgba(rgba, page_w, page_h, x, y, w, h):
    x = max(0, min(x, page_w))
    y = max(0, min(y, page_h))
    w = max(0, min(w, page_w - x))
    h = max(0, min(h, page_h - y))
    out = bytearray(w * h * 4)
    stride = page_w * 4
    for row in range(h):
        src = (y + row) * stride + x * 4
        out[row * w * 4:(row + 1) * w * 4] = rgba[src:src + w * 4]
    return bytes(out), w, h

def place_on_canvas(rgba, w, h, canvas_w, canvas_h, dx, dy):
    out = bytearray(canvas_w * canvas_h * 4)
    for row in range(h):
        if not 0 <= dy + row < canvas_h:
            continue
        x0 = max(0, dx)
        x1 = min(canvas_w, dx + w)
        if x1 <= x0:
            continue
        src = row * w * 4 + (x0 - dx) * 4
        dst = ((dy + row) * canvas_w + x0) * 4
        out[dst:dst + (x1 - x0) * 4] = rgba[src:src + (x1 - x0) * 4]
    return bytes(out), canvas_w, canvas_h

def decode_png(buf, offset=0):
    """Decode an 8-bit RGB or RGBA PNG starting at offset. Returns (w, h, rgba)."""
    pos = offset + 8
    width = height = None
    color_type = None
    idat = bytearray()
    while True:
        length = struct.unpack_from(">I", buf, pos)[0]
        kind = buf[pos + 4:pos + 8]
        body = buf[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height = struct.unpack_from(">II", body, 0)
            bit_depth = body[8]
            color_type = body[9]
            if bit_depth != 8 or color_type not in (2, 6):
                raise ValueError("only 8-bit RGB/RGBA PNG is supported")
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break

    raw = zlib.decompress(bytes(idat))
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    out = bytearray(width * height * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        filter_type = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa = abs(b - c)
                pb = abs(a - c)
                pc = abs(a + b - 2 * c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        prev = line
        row = y * width * 4
        if channels == 4:
            out[row:row + width * 4] = line
        else:
            for x in range(width):
                out[row + x * 4:row + x * 4 + 4] = bytes(
                    (line[x * 3], line[x * 3 + 1], line[x * 3 + 2], 255))
    return width, height, bytes(out)
