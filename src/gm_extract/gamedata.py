import bz2
import os
import struct

from .binary import i32, u16, u32
from .png import PNG_SIGNATURE, decode_png
from .qoi import decode_qoi

class GameData:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.dir = os.path.dirname(self.path)
        with open(self.path, "rb") as f:
            self.data = f.read()

        self.chunks = {}
        self._parse_chunks()

        self.strings = []
        self._parse_strings()

        self.tpag_by_addr = {}
        self._parse_tpag()

        self.textures = []
        self._parse_txtr()

        self.game_name = self._read_game_name()
        self.bytecode = self.data[17] if len(self.data) > 17 else 0

    def _parse_chunks(self):
        d = self.data
        if d[:4] != b"FORM":
            raise ValueError("not a data.win file: missing FORM signature")
        total = 8 + u32(d, 4)
        pos = 8
        while pos + 8 <= min(total, len(d)):
            name = d[pos:pos + 4].decode("latin1")
            size = u32(d, pos + 4)
            self.chunks[name] = (pos + 8, size)
            pos += 8 + size

    def chunk(self, name):
        if name not in self.chunks:
            raise KeyError(f"chunk {name} not found in file")
        return self.chunks[name]

    def has(self, name):
        return name in self.chunks

    def _read_len_string(self, offset):
        n = i32(self.data, offset)
        if n < 0 or offset + 4 + n > len(self.data):
            return None
        return self.data[offset + 4:offset + 4 + n].decode("utf-8", "replace")

    def _parse_strings(self):
        if not self.has("STRG"):
            return
        off, _ = self.chunk("STRG")
        count = i32(self.data, off)
        for i in range(count):
            ptr = i32(self.data, off + 4 + 4 * i)
            s = self._read_len_string(ptr)
            self.strings.append(s if s is not None else "")

    def read_name(self, ptr):
        """Read a resource name. Some builds point at a length prefix, others at the text."""
        d = self.data
        if not ptr or ptr <= 0 or ptr >= len(d):
            return ""
        n = i32(d, ptr)
        if 0 <= n <= 512 and ptr + 4 + n <= len(d):
            raw = d[ptr + 4:ptr + 4 + n]
            if b"\x00" not in raw:
                try:
                    s = raw.decode("utf-8")
                    if s and all(ch >= " " or ch in "\t\r\n" for ch in s):
                        return s
                except UnicodeDecodeError:
                    pass
        end = d.find(b"\x00", ptr, min(len(d), ptr + 512))
        if end < 0:
            end = min(len(d), ptr + 512)
        return d[ptr:end].decode("utf-8", "replace")

    def _parse_tpag(self):
        off, _ = self.chunk("TPAG")
        count = i32(self.data, off)
        for i in range(count):
            ptr = i32(self.data, off + 4 + 4 * i)
            # srcX, srcY, srcW, srcH, dstX, dstY, dstW, dstH, bboxW, bboxH, page
            self.tpag_by_addr[ptr] = struct.unpack_from("<11H", self.data, ptr)

    def tpag(self, ptr):
        return self.tpag_by_addr.get(ptr)

    def _parse_txtr(self):
        off, _ = self.chunk("TXTR")
        count = i32(self.data, off)
        for i in range(count):
            ptr = i32(self.data, off + 4 + 4 * i)
            # scaled, mips, blockSize, width, height, indexInGroup, blobPtr
            _, _, block_size, width, height, _, blob = struct.unpack_from("<7i", self.data, ptr)
            self.textures.append({
                "offset": ptr, "width": width, "height": height,
                "blob": blob, "block_size": block_size,
            })

    def _read_game_name(self):
        if not self.has("GEN8"):
            return ""
        off, _ = self.chunk("GEN8")
        return self.read_name(i32(self.data, off + 4))

    def resource_names(self, chunk):
        if not self.has(chunk):
            return []
        off, _ = self.chunk(chunk)
        count = i32(self.data, off)
        if count < 0 or count > 200000:
            return []
        names = []
        for i in range(count):
            p = i32(self.data, off + 4 + 4 * i)
            names.append(self.read_name(i32(self.data, p)) if 0 < p < len(self.data) else "")
        return names

    def decode_page(self, index):
        """Decode a texture page. Returns (width, height, rgba)."""
        tex = self.textures[index]
        blob = tex["blob"]
        if blob <= 0:
            raise ValueError("texture is stored externally (blob pointer is 0)")
        d = self.data

        if d[blob:blob + 8] == PNG_SIGNATURE:
            return decode_png(d, blob)

        if d[blob:blob + 4] == b"2zoq":
            header = 8 if d[blob + 8:blob + 11] == b"BZh" else 12
            raw = bz2.decompress(d[blob + header:blob + tex["block_size"]])
            return decode_qoi(raw)

        if d[blob:blob + 4] == b"fioq":
            return decode_qoi(d[blob:blob + tex["block_size"]])

        raise ValueError(f"unknown texture format at offset 0x{blob:X}")
