r"""只替换指针贴图、其余字节一个不动的 bundle 补丁器。

不重新压缩整个 bundle（353MB，要 14 秒 + 500MB 内存），做法：
  1. 解压一遍拿资源表，算出贴图在解压流里的绝对偏移；
  2. 只把覆盖到的那些 64KB 块解压、改掉里面的像素、重新压缩；
  3. 其它块原样拷贝。

贴图尺寸不变 → 每个块仍是 64KB → 块表不变 → 文件总大小不变。

注意：这个 bundle 是全局共用的（大量其它 bundle 都引用它），
所以只认「类型 = CURSOR_TEX_TYPE 且名字正好在 CURSOR_NAMES 里」的资源，别扩大范围。
"""
import struct
import zlib

CHUNK = 0x10000
MAGIC = 0xF0000004

CURSOR_BUNDLE = "95b2365a6369ee36"
CURSOR_TEX_TYPE = 0xB277B11FE4A61D37

# 局内指针（2026-11-03 重查 lua/managers/cursor_manager）：
#   按住瞄准 = game（十字，原版不透明白色）；"准星总是可见"打开时不瞄准 = game_inactive（一团淡光斑，最多 23% 不透明）；
#   两者切换时每 0.035 秒换一张 game_transition_01~05（一张比一张淡）。
#   设置里开"大光标"时全部换成 _64 版——第一版漏了这 7 张。
# 菜单 / 设置界面 / 飞船里的箭头 = menu（大光标时 menu_64），保持箭头形状，只改颜色深浅。
#   menu 在小 bundle 750d99512279ecd0 里还有一份一模一样的，两份都改。
# 不改：invisible / invisible_64（游戏藏指针用的全透明图，改了指针就藏不住）。
# bundle 里还有 2 个指针资源没认出名字，局内脚本没用到。
SIZES = ("", "_64")
STATES = ["game", "game_inactive"] + [f"game_transition_0{i}" for i in range(1, 6)]
CURSOR_NAMES = [f"hud/cursors/{s}{z}" for z in SIZES for s in STATES]
MENU_NAMES = ["hud/cursors/menu", "hud/cursors/menu_64"]
ALL_NAMES = CURSOR_NAMES + MENU_NAMES

# 哪个 bundle 里改哪几张
BUNDLES = {
    CURSOR_BUNDLE: ALL_NAMES,
    "750d99512279ecd0": ["hud/cursors/menu"],
}


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


def block_table(data: bytes):
    """返回 ([(块数据起始偏移, 压缩后长度)], 解压后总长度)。"""
    magic, size, _ = struct.unpack_from("<III", data, 0)
    if magic != MAGIC:
        raise ValueError("不是 bundle 文件")
    blocks, off = [], 12
    while off < len(data):
        n = struct.unpack_from("<I", data, off)[0]
        blocks.append((off + 4, n))
        off += 4 + n
    if off != len(data) or len(blocks) * CHUNK < size:
        raise ValueError("bundle 块表损坏")
    return blocks, size


def read_block(data: bytes, blocks, index: int) -> bytes:
    start, n = blocks[index]
    chunk = data[start:start + n]
    return chunk if n == CHUNK else zlib.decompress(chunk)


def decompress_all(data: bytes):
    """解压整个 bundle（496MB 常驻，1.8 秒）。"""
    blocks, size = block_table(data)
    return b"".join(read_block(data, blocks, i) for i in range(len(blocks))), blocks, size


def find_textures(raw: bytes, names):
    """在解压流里找这些指针贴图，返回 {名字: (绝对偏移, 长度)}。"""
    n = struct.unpack_from("<I", raw, 0)[0]
    off = 4 + 256 + 16 * n
    want = {murmur64a(name.encode()): name for name in names}
    found = {}
    for _ in range(n):
        t, name, nv, _so = struct.unpack_from("<QQII", raw, off)
        off += 24
        vs = []
        for _ in range(nv):
            _lang, vsize, _ss = struct.unpack_from("<III", raw, off)
            off += 12
            vs.append(vsize)
        for vsize in vs:
            if name in want and t == CURSOR_TEX_TYPE and want[name] not in found:
                found[want[name]] = (off, vsize)
            off += vsize
    missing = [x for x in names if x not in found]
    if missing:
        raise ValueError("找不到这些指针贴图：" + "、".join(missing))
    return found


def read_texture(data: bytes, blocks, offset: int, length: int) -> bytes:
    """从解压流里读一段（可能跨块）。"""
    out, pos, remain = [], offset, length
    while remain > 0:
        idx = pos // CHUNK
        inner = pos % CHUNK
        chunk = read_block(data, blocks, idx)
        take = min(remain, CHUNK - inner)
        out.append(chunk[inner:inner + take])
        pos += take
        remain -= take
    return b"".join(out)


def plan_spans(data: bytes, replacements):
    """算出要改的 (偏移, 长度, 新数据) 和涉及的块号。"""
    raw, blocks, _size = decompress_all(data)
    found = find_textures(raw, list(replacements))
    del raw
    spans, touched = [], set()
    for name, new in replacements.items():
        if name not in found:
            raise ValueError(f"没有这张贴图：{name}")
        offset, length = found[name]
        if len(new) != length:
            raise ValueError(f"{name} 数据长度变了：{len(new)} != {length}")
        spans.append((offset, length, new))
        touched.update(range(offset // CHUNK, (offset + length - 1) // CHUNK + 1))
    return spans, touched


def patch(data: bytes, replacements) -> bytes:
    """replacements: {贴图名: 新数据}。尺寸必须不变。返回新的 bundle 字节。"""
    blocks, _size = block_table(data)
    spans, touched = plan_spans(data, replacements)

    chunks = {i: bytearray(read_block(data, blocks, i)) for i in sorted(touched)}
    for offset, length, new in spans:
        for i in range(offset // CHUNK, (offset + length - 1) // CHUNK + 1):
            base = i * CHUNK
            lo, hi = max(offset, base), min(offset + length, base + CHUNK)
            chunks[i][lo - base:hi - base] = new[lo - offset:hi - offset]

    out = [data[:12]]
    for i, (start, n) in enumerate(blocks):
        if i in chunks:
            z = zlib.compress(bytes(chunks[i]), 9)
            if len(z) >= CHUNK:
                z = bytes(chunks[i])
            out.append(struct.pack("<I", len(z)) + z)
        else:
            out.append(data[start - 4:start + n])
    return b"".join(out)


def verify(patched: bytes, original: bytes, replacements) -> int:
    """读后校验：替换的贴图内容正确，且只有受影响的块变了。返回改动块数。"""
    b_new, _ = block_table(patched)
    b_old, _ = block_table(original)
    if len(b_new) != len(b_old):
        raise ValueError("块数变了")
    spans, touched = plan_spans(patched, replacements)
    for offset, length, new in spans:
        if read_texture(patched, b_new, offset, length) != new:
            raise ValueError("写进去的数据不对")
    for i in sorted(touched):
        if read_block(original, b_old, i) == read_block(patched, b_new, i):
            raise ValueError(f"块 {i} 应该被改但没有变")
    return len(touched)
