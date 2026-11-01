import struct

from .binary import i32, u16

MAX_FRAMES = 1000
MAX_GLYPHS = 20000

def parse_sprites(g):
    off, _ = g.chunk("SPRT")
    d = g.data
    count = i32(d, off)
    sprites = []
    for i in range(count):
        p = i32(d, off + 4 + 4 * i)
        v = [i32(d, p + 4 * k) for k in range(14)]
        marker = i32(d, p + 56)

        tex_ptrs = []
        sprite_type = 0
        version = 0
        if marker == -1:
            version = i32(d, p + 60)
            sprite_type = i32(d, p + 64)
            cur = 76
            if version >= 2:
                cur += 4
            if version >= 3:
                cur += 4
            if sprite_type == 0:
                n = i32(d, p + cur)
                if 0 <= n <= MAX_FRAMES:
                    tex_ptrs = [i32(d, p + cur + 4 + 4 * k) for k in range(n)]
        else:
            n = marker
            if 0 <= n <= MAX_FRAMES:
                tex_ptrs = [i32(d, p + 60 + 4 * k) for k in range(n)]

        sprites.append({
            "index": i, "name": g.read_name(v[0]),
            "width": v[1], "height": v[2],
            "origin_x": v[12], "origin_y": v[13],
            "sprite_type": sprite_type, "version": version,
            "textures": tex_ptrs,
        })
    return sprites

def parse_backgrounds(g):
    """Tilesets (BGND chunk)."""
    if not g.has("BGND"):
        return []
    off, size = g.chunk("BGND")
    d = g.data
    count = i32(d, off)
    tilesets = []
    for i in range(count):
        p = i32(d, off + 4 + 4 * i)
        if i + 1 < count:
            record_size = i32(d, off + 4 + 4 * (i + 1)) - p
        else:
            record_size = size - (p - off)

        if record_size >= 72:
            base = 40
        else:
            base = 32
        tilesets.append({
            "index": i,
            "name": g.read_name(i32(d, p)),
            "tex_ptr": i32(d, p + 16),
            "tileset_version": i32(d, p + 20),
            "tile_w": i32(d, p + 24),
            "tile_h": i32(d, p + 28),
            "border_x": i32(d, p + base),
            "border_y": i32(d, p + base + 4),
            "columns": i32(d, p + base + 8),
            "items_per_tile": i32(d, p + base + 12),
            "tile_count": i32(d, p + base + 16),
        })
    return tilesets

def _parse_glyph(d, gp):
    if gp <= 0 or gp + 18 > len(d):
        return None
    char, x, y, w, h, shift, offset = struct.unpack_from("<5H2h", d, gp)
    kern = u16(d, gp + 16)
    if kern > 200:
        kern = u16(d, gp + 14)
    return {
        "char": char, "x": x, "y": y, "w": w, "h": h,
        "shift": shift, "offset": offset, "kern": kern,
    }

def _find_glyphs(d, p, chunk_start, chunk_end):
    """The glyph list offset depends on the runtime version, so probe the known candidates."""
    for cur in (40, 44, 48, 52, 56):
        if p + cur + 4 > chunk_end:
            continue
        count = i32(d, p + cur)
        if not 0 < count < MAX_GLYPHS:
            continue
        ptrs = []
        for k in range(count):
            q = i32(d, p + cur + 4 + 4 * k)
            if not chunk_start < q < chunk_end:
                break
            ptrs.append(q)
        if len(ptrs) != count:
            continue
        if any(_parse_glyph(d, q) is None for q in ptrs[:4]):
            continue
        return [gl for gl in (_parse_glyph(d, q) for q in ptrs) if gl]
    return []

def parse_fonts(g):
    if not g.has("FONT"):
        return []
    off, size = g.chunk("FONT")
    d = g.data
    count = i32(d, off)
    chunk_end = off + size
    fonts = []
    for i in range(count):
        p = i32(d, off + 4 + 4 * i)
        fonts.append({
            "index": i,
            "name": g.read_name(i32(d, p)),
            "display_name": g.read_name(i32(d, p + 4)),
            "tex_ptr": i32(d, p + 28),
            "glyphs": _find_glyphs(d, p, off, chunk_end),
        })
    return fonts
