"""Helldivers 1 (Bitsquid) bundle 读写：解压/压缩、解析资源表、murmur64 名字哈希。"""
import re
import struct
import zlib

LUA = 0xA14E8DFA2CD117E2
CHUNK = 0x10000


def murmur64a(key: bytes, seed=0) -> int:
    m, r, mask = 0xC6A4A7935BD1E995, 47, (1 << 64) - 1
    h = (seed ^ (len(key) * m)) & mask
    n = len(key) // 8
    for i in range(n):
        k = struct.unpack_from("<Q", key, i * 8)[0]
        k = (k * m) & mask
        k ^= k >> r
        k = (k * m) & mask
        h ^= k
        h = (h * m) & mask
    tail = key[n * 8:]
    if tail:
        for i, b in enumerate(tail):
            h ^= b << (8 * i)
        h = (h * m) & mask
    h ^= h >> r
    h = (h * m) & mask
    h ^= h >> r
    return h


def decompress(data: bytes) -> bytes:
    assert struct.unpack_from("<I", data, 0)[0] == 0xF0000004
    size = struct.unpack_from("<I", data, 4)[0]
    off, out = 12, []
    while off < len(data):
        n = struct.unpack_from("<I", data, off)[0]
        off += 4
        chunk = data[off:off + n]
        off += n
        out.append(chunk if n == CHUNK else zlib.decompress(chunk))
    raw = b"".join(out)
    return raw, size


def _pack_block(block, level):
    z = zlib.compress(block, level)
    return block if len(z) >= CHUNK else z


def compress(raw: bytes, size: int, level: int = 9, parallel: bool = False) -> bytes:
    """parallel=True：每块 64KB 各自压缩，用多个 CPU 核一起压（zlib 压缩时放开 GIL，线程就够），结果和单线程逐字节一样。
    2026-11-19 发行抢先版：第一次装核心鬼城要重压 45 个地图包（1.3GB），单线程玩家机器要好几分钟。"""
    blocks = [raw[i:i + CHUNK].ljust(CHUNK, b"\0") for i in range(0, len(raw), CHUNK)]
    pool_cls = None
    if parallel and len(blocks) > 1:
        try:  # 2026-11-26 用户截图：发行版没带 concurrent，选图「开始」报 No module named 'concurrent'；缺了就单线程压
            from concurrent.futures import ThreadPoolExecutor as pool_cls
        except ImportError:
            pool_cls = None
    if pool_cls is not None:
        import os
        with pool_cls(max_workers=max(1, min(16, os.cpu_count() or 1))) as pool:
            zs = list(pool.map(lambda b: _pack_block(b, level), blocks))
    else:
        zs = [_pack_block(b, level) for b in blocks]
    return b"".join([struct.pack("<III", 0xF0000004, size, 0)] + [struct.pack("<I", len(z)) + z for z in zs])


def parse(raw: bytes):
    """返回资源列表：(type, name, [(lang, data_offset, size)])，offset 指向 raw 内。"""
    n = struct.unpack_from("<I", raw, 0)[0]
    off = 4 + 256 + 16 * n
    res = []
    for _ in range(n):
        t, name, nv, _so = struct.unpack_from("<QQII", raw, off)
        off += 24
        vs = []
        for _ in range(nv):
            vs.append(struct.unpack_from("<III", raw, off))
            off += 12
        variants = []
        for lang, size, _ss in vs:
            variants.append((lang, off, size))
            off += size
        res.append((t, name, variants))
    return res


def lua_paths(raw: bytes):
    return set(m.group().decode() for m in re.finditer(rb"lua/[a-z0-9_/]+", raw))
