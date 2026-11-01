from .binary import f32, i32, u32

NEW_SOUND_RECORD_SIZE = 40

def parse_audio_groups(g):
    if not g.has("AGRP"):
        return []
    off, _ = g.chunk("AGRP")
    d = g.data
    count = i32(d, off)
    groups = []
    for i in range(count):
        p = i32(d, off + 4 + 4 * i)
        groups.append({
            "index": i,
            "name": g.read_name(i32(d, p)),
            "file": g.read_name(i32(d, p + 4)),
        })
    return groups

def parse_sounds(g):
    if not g.has("SOND"):
        return []
    off, size = g.chunk("SOND")
    d = g.data
    count = i32(d, off)
    new_layout = bool(count) and (size - 8) // max(1, count) >= NEW_SOUND_RECORD_SIZE
    sounds = []
    for i in range(count):
        p = i32(d, off + 4 + 4 * i)
        sounds.append({
            "index": i,
            "name": g.read_name(i32(d, p)),
            "flags": u32(d, p + 4),
            "type": g.read_name(i32(d, p + 8)),
            "file": g.read_name(i32(d, p + 12)),
            "volume": f32(d, p + 20),
            "pitch": f32(d, p + 24),
            "group": i32(d, p + 28) if new_layout else 0,
            "audio_id": i32(d, p + 32) if new_layout else i32(d, p + 28),
            "length": f32(d, p + 36) if new_layout else 0.0,
        })
    return sounds

def audio_ext(data):
    if data[:4] == b"RIFF":
        return "wav"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    return "bin"

def read_audiogroup_file(path):
    """Read an external audio group (*.dat). Returns a list of raw audio blobs."""
    with open(path, "rb") as f:
        b = f.read()
    if b[:4] != b"FORM" or b[8:12] != b"AUDO":
        raise ValueError(f"not a GameMaker audio group: {path}")
    count = u32(b, 16)
    items = []
    for i in range(count):
        off = u32(b, 20 + 4 * i)
        if off + 4 > len(b):
            items.append(b"")
            continue
        length = u32(b, off)
        items.append(b[off + 4:off + 4 + length])
    return items

def read_embedded_audio(g):
    off, _ = g.chunk("AUDO")
    d = g.data
    count = i32(d, off)
    items = []
    for i in range(count):
        p = i32(d, off + 4 + 4 * i)
        if p <= 0:
            items.append(b"")
            continue
        length = u32(d, p)
        items.append(d[p + 4:p + 4 + length])
    return items
