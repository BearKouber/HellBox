r"""HellBox 的改动写成游戏的补丁文件 <包名>.patch_N，不再整份替换游戏原文件（2026-11-20 HD1-036，用户定：和 Obsidian 能同时装）。

游戏怎么读补丁：每个包（contents\<16 位十六进制>）旁边，引擎从 .patch_0 往上一个个读，读到缺的编号就停；
  补丁里的资源（按 类型 + 名字）顶替包里同名的，编号大的赢。补丁文件格式和包一样，只是只放改动的资源，
  开头 256 字节的属性照抄原包。Obsidian（github.com/Alomare/ObsidianLauncher）就是这么装 MOD 的。
和 Obsidian 怎么相处（读过它的 core/src/deploy.rs）：
  - 它把不是自己写的补丁当「其他补丁」，从不删；自己的放在最小的空编号上。
  - 编号中间不能有空洞（游戏读到空洞就停，上面的都失效）。所以 HellBox 拿掉自己的补丁时：上面没有别人的就删掉，
    上面还有别人的就换成一个空补丁（没有资源，什么都不改）占住编号；以后它变成最上面一个了再删。
  - Obsidian 清除（Purge）只删自己的，不补洞：它在 0 号、我们在 1 号时清除，我们的就读不到了 → reachable() 为 False，
    HellBox 当「旧版」，关游戏后自动重装，挪到 0 号。
哪些补丁是我们的：记在 %APPDATA%\Arrowhead\Helldivers\hellbox\patches.json（所有 HellBox 共用），
  {包名: {"slot": 编号, "sha256": 内容指纹, "size": 字节数, "empty": 是不是占位空补丁, "what": "core" / "ghost" / "cursor"}}；
  文件内容和记的指纹对不上就不是我们的了（被别人换掉），不碰。
"""
import hashlib
import json
import os
import re
import struct

from bundle import compress, decompress

GAME_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Arrowhead", "Helldivers", "hellbox")
RECORD = os.path.join(GAME_DIR, "patches.json")
PATCH_RE = re.compile(r"^([0-9a-f]{16})\.patch_(\d+)$")


# ---------- 读写包内容 ----------

def read_entries(path, want=None):
    """读一个包（或补丁）：返回 (属性 256 字节, {(类型, 名字): (flags, [(语言, 数据, stream 大小)])})。
    want = {(类型, 名字)} 时只留这些（大包也要整个解压，但只留要的那几块）。"""
    with open(path, "rb") as f:
        data = f.read()
    return entries_of(data, want)


def entries_of(data, want=None):
    raw, size = decompress(data)
    raw = raw[:size]
    n = struct.unpack_from("<I", raw, 0)[0]
    props = raw[4:260]
    off = 4 + 256 + 16 * n
    out = {}
    for _ in range(n):
        t, name, nv, flags = struct.unpack_from("<QQII", raw, off)
        heads = [struct.unpack_from("<III", raw, off + 24 + 12 * i) for i in range(nv)]
        off += 24 + 12 * nv
        variants = []
        for lang, vsize, ss in heads:
            variants.append((lang, raw[off:off + vsize], ss))
            off += vsize
        if want is None or (t, name) in want:
            out[(t, name)] = (flags, variants)
    if raw[off:].strip(b"\0"):
        raise RuntimeError("游戏文件格式认不出")
    return props, out


def make_patch(props, entries):
    """entries = {(类型, 名字): (flags, [(语言, 数据, stream 大小)])} → 补丁文件内容。按 (类型, 名字) 排序（和 Obsidian 一样）。
    只收不带 stream 的资源（stream 部分在 .stream 文件里，我们改的脚本、配色、指针贴图都没有）。"""
    keys = sorted(entries)
    head = [struct.pack("<I", len(keys)), bytes(props)]
    head += [struct.pack("<QQ", t, n) for t, n in keys]
    body = []
    for t, n in keys:
        flags, variants = entries[(t, n)]
        if any(ss for _l, _d, ss in variants):
            raise RuntimeError("这个资源有 stream 部分，补丁装法还不支持")
        body.append(struct.pack("<QQII", t, n, len(variants), flags))
        body += [struct.pack("<III", lang, len(d), 0) for lang, d, _ss in variants]
        body += [d for _l, d, _ss in variants]
    raw = b"".join(head + body)
    return compress(raw, len(raw), level=6, parallel=len(raw) > (1 << 20))


def diff_patch(base_data, new_data):
    """两份完整的包 → 只含不一样的资源的补丁；完全一样返回 None。"""
    props, base = entries_of(base_data)
    _p, new = entries_of(new_data)
    changed = {k: v for k, v in new.items() if base.get(k) != v}
    return make_patch(props, changed) if changed else None


def empty_patch(props):
    return make_patch(props, {})


def props_of(path):
    """包开头的 256 字节属性（只解压第一块）。"""
    with open(path, "rb") as f:
        head = f.read(16 + 0x10000 + 64)
    import zlib
    n = struct.unpack_from("<I", head, 12)[0]
    chunk = head[16:16 + n]
    block = chunk if n == 0x10000 else zlib.decompressobj().decompress(chunk)
    return block[4:260]


# ---------- 编号和记录 ----------

def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_record():
    try:
        with open(RECORD, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_record(rec):
    os.makedirs(GAME_DIR, exist_ok=True)
    tmp = RECORD + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    os.replace(tmp, RECORD)


def path_of(contents, bundle, slot):
    return os.path.join(contents, f"{bundle}.patch_{slot}")


def slots(contents, bundle):
    """游戏里这个包现有的补丁编号（升序）。"""
    out = []
    try:
        names = os.listdir(contents)
    except OSError:
        return out
    for name in names:
        m = PATCH_RE.match(name.lower())
        if m and m.group(1) == bundle.lower():
            out.append(int(m.group(2)))
    return sorted(out)


def _ours(contents, bundle, rec=None, quick=False):
    """我们记着的补丁还在、内容没被换：返回记录；否则 None。quick=True 只比大小（状态检查用，快）。"""
    rec = load_record() if rec is None else rec
    r = rec.get(bundle)
    if not r:
        return None
    p = path_of(contents, bundle, r["slot"])
    try:
        if os.path.getsize(p) != r["size"]:
            return None
        if not quick and _file_sha(p) != r["sha256"]:
            return None
    except OSError:
        return None
    return r


def reachable(contents, bundle, slot):
    """游戏读得到这个编号：下面 0 ~ slot-1 一个不缺。"""
    have = set(slots(contents, bundle))
    return all(i in have for i in range(slot + 1))


def current(contents, bundle, data=None, sha=None):
    """我们的补丁在、游戏读得到、内容就是 data（或指纹 sha）、不是占位空补丁。只比大小和记录，不读文件。"""
    r = _ours(contents, bundle, quick=True)
    if not r or r.get("empty") or not reachable(contents, bundle, r["slot"]):
        return False
    if data is not None:
        return r["size"] == len(data) and r["sha256"] == _sha(data)
    if sha is not None:
        return r["sha256"] == sha
    return True


def installed(contents, bundle):
    """我们有这个包的（非占位）补丁，不管读不读得到。"""
    r = _ours(contents, bundle, quick=True)
    return bool(r and not r.get("empty"))


def _write(path, data):
    with open(path, "wb") as f:
        f.write(data)


def put(contents, bundle, data, what, still_ok=lambda: True, extra=None):
    """把补丁 data 放进游戏。已经是一样的就不写。返回编号。
    放在哪：我们原来那个编号（还是我们的、游戏读得到）→ 原地换；否则放最小的空编号（填洞，和 Obsidian 一样）。"""
    rec = load_record()
    r = _ours(contents, bundle, rec)
    sha = _sha(data)
    if r and reachable(contents, bundle, r["slot"]):
        slot = r["slot"]
        if r["sha256"] == sha and not r.get("empty"):
            if extra and any(r.get(k) != v for k, v in extra.items()):
                rec[bundle] = {**r, **extra}
                _save_record(rec)
            return slot
    else:
        have = set(slots(contents, bundle))
        if r:  # 我们的还在、但下面缺了号（比如 Obsidian 清除了它下面的）：把我们的挪下来
            have.discard(r["slot"])
        slot = 0
        while slot in have:
            slot += 1
    if not still_ok():
        raise RuntimeError("装的过程中游戏被打开了，已停下。请关掉游戏再试。")
    try:
        _write(path_of(contents, bundle, slot), data)
    except PermissionError as e:
        raise RuntimeError("游戏文件被占用（游戏可能正在启动），已停下。请关掉游戏再试。") from e
    if r and r["slot"] != slot:
        _drop_file(contents, bundle, r["slot"])
    rec[bundle] = {"slot": slot, "sha256": sha, "size": len(data), "empty": False, "what": what, **(extra or {})}
    _save_record(rec)
    _tidy(contents, bundle)
    return slot


def _drop_file(contents, bundle, slot):
    """删掉我们的一个旧编号；上面还有别人的就换成空补丁占位（不留洞）。"""
    p = path_of(contents, bundle, slot)
    if any(s > slot for s in slots(contents, bundle)):
        _write(p, empty_patch(props_of(os.path.join(contents, bundle))))
    else:
        try:
            os.remove(p)
        except OSError:
            pass


def take_out(contents, bundle, still_ok=lambda: True):
    """拿掉我们的补丁（游戏这个包回到不带 HellBox 的样子）。不是我们的不碰。"""
    rec = load_record()
    r = _ours(contents, bundle, rec)
    if not r:
        rec.pop(bundle, None)
        _save_record(rec)
        return
    if not still_ok():
        raise RuntimeError("游戏被打开了，已停下。请关掉游戏再试。")
    slot = r["slot"]
    if any(s > slot for s in slots(contents, bundle)):
        if not r.get("empty"):
            data = empty_patch(props_of(os.path.join(contents, bundle)))
            _write(path_of(contents, bundle, slot), data)
            rec[bundle] = {"slot": slot, "sha256": _sha(data), "size": len(data), "empty": True, "what": r.get("what", "")}
    else:
        os.remove(path_of(contents, bundle, slot))
        rec.pop(bundle, None)
    _save_record(rec)


def _tidy(contents, bundle):
    """以前留下的占位空补丁如果已经是最上面一个了，就删掉（现在 put 过就不会有了，这里只是保险）。"""
    rec = load_record()
    r = rec.get(bundle)
    if r and r.get("empty") and _ours(contents, bundle, rec) and slots(contents, bundle)[-1:] == [r["slot"]]:
        os.remove(path_of(contents, bundle, r["slot"]))
        rec.pop(bundle, None)
        _save_record(rec)


def tidy_all(contents):
    """所有占位空补丁：变成最上面一个的删掉。装 / 卸的时候顺手调。"""
    for bundle, r in list(load_record().items()):
        if r.get("empty"):
            _tidy(contents, bundle)


def ours(what=None):
    """记录里我们的补丁 {包名: 记录}（what 过滤 core / ghost / cursor）。"""
    return {b: r for b, r in load_record().items() if what is None or r.get("what") == what}


def foreign(contents, bundle):
    """这个包上不是我们的补丁编号（别的工具，比如 Obsidian）。"""
    r = load_record().get(bundle)
    mine = r["slot"] if r else None
    return [s for s in slots(contents, bundle) if s != mine]
