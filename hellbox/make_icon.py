"""
画 HellBox 图标：像素箱子

运行：python hellbox/make_icon.py
"""
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))

ART = [
    "................",
    ".KKKKKKKKKKKKK..",
    ".KYYKKYYKKYYKK..",
    ".KKYYKKYYKKYYK..",
    ".KKKKKKKKKKKKK..",
    ".KCCCCCCCCCCCK..",
    ".KCKKKKKKKKKCK..",
    ".KCKMKRKYKKKCK..",
    ".KCKKKKKKKKKCK..",
    ".KCCCCCCCCCCCK..",
    ".KCCKKKKKKKCCK..",
    ".KCCCCCCCCCCCK..",
    ".KCCCCCCCCCCCK..",
    ".KKKKKKKKKKKKK..",
    "................",
    "................",
]
COLORS = {
    "K": (28, 28, 28, 255),
    "Y": (246, 212, 105, 255),
    "C": (241, 236, 227, 255),
    "M": (134, 211, 166, 255),
    "R": (240, 113, 82, 255),
}


def pixels():
    grid = [[(0, 0, 0, 0)] * 16 for _ in range(16)]
    for y, row in enumerate(ART):
        for x, ch in enumerate(row):
            if ch in COLORS:
                grid[y][x] = COLORS[ch]
    for y in range(2, 15):
        if grid[y][14][3] == 0:
            grid[y][14] = COLORS["K"]
    for x in range(2, 15):
        if grid[14][x][3] == 0:
            grid[14][x] = COLORS["K"]
    return grid


def png(size):
    grid = pixels()
    s = size // 16
    raw = b""
    for y in range(size):
        row = b"".join(bytes(grid[y // s][x // s]) for x in range(size))
        raw += b"\0" + row

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def ico(sizes=(16, 32, 48, 64, 128, 256)):
    images = [png(s) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, body = b"", b""
    for s, data in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset + len(body))
        body += data
    return head + entries + body


if __name__ == "__main__":
    with open(os.path.join(HERE, "icon.png"), "wb") as f:
        f.write(png(64))
    with open(os.path.join(HERE, "icon.ico"), "wb") as f:
        f.write(ico())
    print("icon.png / icon.ico 已生成")
