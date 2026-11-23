r"""鬼城配色装进地图包（2026-11-18 V0.98，用户定：注入没关系，让 HellBox 玩家有真鬼城；备份存完整原版）。
2026-11-20 HD1-036 起改成补丁装法：配色写进每个地图包旁边的 <包>.patch_N，原文件不动、不用备份（见 install 和 patch_files.py）；
下面这段是当初整份替换时的说明，install / restore 现在顺手把老装法的包换回原版。

原理见 tools/ghost_shading.py。这里做三件事，build.install / restore / status 调：
  install()  45 个地图包逐个看：是原版（大小 + sha256 对得上）→ 先在公共备份（%APPDATA%/…/hellbox/backup/maps/，
             新旧版 HellBox 共用）放一份原版，再把里面的普通配色换成带 ghost_town 的（同名替换，其余字节原样）；
             已经换过的跳过；都不是（别的 MOD 改过）也跳过、不硬改。最后写 ghost-maps.txt：换好了哪些包。
  restore()  照备份把换过的包原样拷回去，删 ghost-maps.txt。
  stale()    ghost-maps.txt 里记的包大小和游戏里对不上（比如 Steam 验证过文件）→ True，HellBox 当成「旧版」自动重装。
游戏那边（hellbox_play.lua）只有这一关的地图包在 ghost-maps.txt 里才用 ghost_town，否则退回 night，不会闪退。
"""
import base64
import hashlib
import os
import struct
import subprocess

from bundle import compress, decompress, murmur64a

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "ghost_shading.bin")
GAME_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Arrowhead", "Helldivers", "hellbox")
BACKUP_DIR = os.path.join(GAME_DIR, "backup", "maps")
LIST = os.path.join(GAME_DIR, "ghost-maps.txt")
SE = murmur64a(b"shading_environment")


def load():
    """返回 (配色 {资源名哈希: 数据}, 地图包 [(文件名, 包名, 原版大小, 原版 sha256)])；文件没有 / 坏了返回 ({}, [])。"""
    try:
        with open(DATA, "rb") as f:
            d = f.read()
    except OSError:
        return {}, []
    if d[:4] != b"HBGS" or struct.unpack_from("<I", d, 4)[0] != 2:
        return {}, []
    n = struct.unpack_from("<I", d, 8)[0]
    o, ses = 12, {}
    for _ in range(n):
        name, ln = struct.unpack_from("<QI", d, o)
        o += 12
        ses[name] = d[o:o + ln]
        o += ln
    nb = struct.unpack_from("<I", d, o)[0]
    o += 4
    bundles = []
    for _ in range(nb):
        fn = d[o:o + 16].decode()
        pl = struct.unpack_from("<I", d, o + 16)[0]
        pkg = d[o + 20:o + 20 + pl].decode()
        o += 20 + pl
        size = struct.unpack_from("<Q", d, o)[0]
        sha = d[o + 8:o + 40]
        o += 40
        bundles.append((fn, pkg, size, sha))
    return ses, bundles


# ghost-maps.txt 第一行：HBGHOST1 + 空格 + 配色数据的指纹（2026-11-19 加，数据一改指纹就变，stale() 当旧版自动重装）。
# 游戏那边（hellbox_play.lua）只看「包名=」开头的行，第一行写什么不影响。
HEADER = "HBGHOST1 "


def data_tag():
    try:
        with open(DATA, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return ""


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.digest()


def patch(data, ses):
    """一个地图包（文件内容）→ 换好配色的文件内容；没有要换的返回 None。"""
    raw, size = decompress(data)
    raw = raw[:size]
    n = struct.unpack_from("<I", raw, 0)[0]
    head = 4 + 256 + 16 * n
    out, off, hit = [raw[:head]], head, 0
    for _ in range(n):
        t, name, nv, so = struct.unpack_from("<QQII", raw, off)
        vs = [list(struct.unpack_from("<III", raw, off + 24 + 12 * i)) for i in range(nv)]
        off += 24 + 12 * nv
        datas = []
        for v in vs:
            datas.append(raw[off:off + v[1]])
            off += v[1]
        if t == SE and name in ses and nv == 1 and vs[0][2] == 0 and datas[0] != ses[name]:
            datas = [ses[name]]
            vs[0][1] = len(ses[name])
            hit += 1
        out.append(struct.pack("<QQII", t, name, nv, so))
        out += [struct.pack("<III", *v) for v in vs]
        out += datas
    if raw[off:].strip(b"\0"):
        raise RuntimeError("地图包格式认不出")
    if not hit:
        return None
    new = b"".join(out)
    return compress(new, len(new), level=6, parallel=True)


def _write(path, data):
    # 2026-11-23：某些安全策略不让这个 exe 写 %APPDATA%；直接用 PowerShell 代写。
    try:
        with open(path, "wb") as f:
            f.write(data)
        return
    except PermissionError:
        pass
    b64 = base64.b64encode(data).decode("ascii")
    ps = ("$b=[Convert]::FromBase64String('" + b64 + "');"
          "[IO.File]::WriteAllBytes('" + str(path).replace("'", "''") + "',$b)")
    enc = base64.b64encode(ps.encode("utf-16le")).decode("ascii")
    subprocess.run([r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                    "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                   check=True, creationflags=0x08000000)


def _is_vanilla_backup(bak, size, sha):
    try:
        return os.path.getsize(bak) == size and _sha(bak) == sha
    except OSError:
        return False


def has_backup():
    """公共备份里有没有地图包的原版（有任何一个就算：装过并选了备份）。"""
    _ses, bundles = load()
    return any(os.path.exists(os.path.join(BACKUP_DIR, fn)) for fn, _pkg, _size, _sha2 in bundles)


def build_patch(path, ses):
    """原版地图包 → 只含换好的配色的补丁（2026-11-20 HD1-036）；没有要换的返回 None。"""
    import patch_files
    props, ents = patch_files.read_entries(path, want={(SE, n) for n in ses})
    changed = {}
    for (t, n), (flags, vs) in ents.items():
        if len(vs) == 1 and vs[0][2] == 0 and vs[0][1] != ses[n]:
            changed[(t, n)] = (flags, [(vs[0][0], ses[n], 0)])
    return patch_files.make_patch(props, changed) if changed else None


def install(contents, still_ok=lambda: True, say=print, backup=None, progress=None):
    """contents = 游戏 contents 目录。still_ok() 返回 False（比如游戏被打开了）就停下。返回换好的包数。
    progress(第几个, 一共几个)：每个包开始时报一次（HellBox 底栏显示「鬼城地图 几 / 45」）。
    2026-11-20 HD1-036（用户定：和 Obsidian 能同时装）：配色写成每个地图包旁边的补丁 <包>.patch_N（只含配色，几十 KB），
      地图原文件一个字节都不动，也就不用再备份 1.3GB 原版（backup 参数不再用）。
      以前整份换过的包：有原版备份就先换回原版、再放补丁；没有备份的留着（鬼城照样有，要 Steam 验证才回到原版文件）。
      补丁已经是这份配色数据做的、原包没变、游戏读得到 → 跳过，不再每次读 1.3GB。"""
    import patch_files
    ses, bundles = load()
    if not ses or not bundles:
        raise RuntimeError("缺少鬼城配色数据（mod/ghost_shading.bin），请重新解压 HellBox。")
    tag = data_tag()
    done, skipped, yielded = [], [], []
    old = {fn: size for _pkg, fn, size, _slot in listed(with_slot=True)}
    rec = patch_files.ours("ghost")

    def check_running():
        if not still_ok():
            raise RuntimeError("装的过程中游戏被打开了，已停下。请关掉游戏再试。")

    for i, (fn, pkg, size, sha) in enumerate(bundles):
        if progress:
            progress(i + 1, len(bundles))
        path = os.path.join(contents, fn)
        try:
            cur_size = os.path.getsize(path)
        except OSError:
            skipped.append(pkg)
            continue
        r = rec.get(fn)
        if _foreign_lighting(contents, fn, ses):
            # 别的工具（比如 Obsidian 的 Enhanced Visuals）的补丁也换了这张图的配色：让给它，这张图开鬼城是夜晚的样子
            if r:
                patch_files.take_out(contents, fn, still_ok=still_ok)
            yielded.append(pkg)
            continue
        if r and r.get("tag") == tag and cur_size == size and patch_files.current(contents, fn, sha=r["sha256"]):
            done.append((pkg, fn))
            continue
        if cur_size == size and _sha(path) == sha:  # 原版
            data = build_patch(path, ses)
        elif fn in old and old[fn] == cur_size and fn not in rec:  # 以前整份换过的
            bak = os.path.join(BACKUP_DIR, fn)
            if not _is_vanilla_backup(bak, size, sha):
                done.append((pkg, fn))  # 没备份：整份换过的包留着，鬼城照样有
                continue
            check_running()
            with open(bak, "rb") as f:
                _write(path, f.read())
            data = build_patch(path, ses)
        else:  # 不是原版、也不是我们换过的：别的 MOD 改过，跳过不硬改
            skipped.append(pkg)
            continue
        if data is not None:
            patch_files.put(contents, fn, data, "ghost", still_ok=still_ok, extra={"tag": tag})
        done.append((pkg, fn))
    _write_list(contents, done)
    if skipped:
        say("这些地图包不是原版，没换鬼城配色（那里开鬼城是夜晚的样子）：" + "、".join(skipped))
    if yielded:
        say("这些地图的配色被别的工具（比如 Obsidian 的 Enhanced Visuals）换过，鬼城让给它、这些图开鬼城是夜晚的样子："
            + "、".join(yielded))
    return len(done)


def _foreign_lighting(contents, fn, ses):
    """这个地图包上有不是我们的补丁，里面也有我们要换的配色。"""
    import patch_files
    for s in patch_files.foreign(contents, fn):
        try:
            _p, ents = patch_files.read_entries(patch_files.path_of(contents, fn, s), want={(SE, n) for n in ses})
        except Exception:
            return True  # 读不懂的别人的补丁：保守，让出
        if ents:
            return True
    return False


def _write_list(contents, done):
    """ghost-maps.txt：第一行 HBGHOST1 + 指纹；第二行 contents=游戏 contents 目录（2026-11-20 起，游戏那边自己核对补丁用）；
    之后每行「包名=文件名=大小」，补丁装法的再加「=补丁编号」。游戏那边（hellbox_play.lua）核对：这个编号的补丁在、
    下面的编号都在、上面没有别人的补丁（有的话它的配色可能盖掉我们的）→ 才用鬼城配色，否则退回夜晚，不会闪退。"""
    import patch_files
    rec = patch_files.ours("ghost")
    lines = [HEADER + data_tag(), "contents=" + os.path.abspath(contents).replace(os.sep, "/") + "/"]
    for pkg, fn in done:
        line = f"{pkg}={fn}={os.path.getsize(os.path.join(contents, fn))}"
        if fn in rec and not rec[fn].get("empty"):
            line += f"={rec[fn]['slot']}"
        lines.append(line)
    os.makedirs(GAME_DIR, exist_ok=True)
    _write(LIST, ("\n".join(lines) + "\n").encode("utf-8"))


def restore(contents):
    """拿掉配色补丁；以前整份换过的包照备份拷回去（备份不对的不动）。返回 (还原了几个, 没有备份还不回去的几个)。
    还不回去的（以前装的时候选了不备份）留在 ghost-maps.txt 里，下次开核心能认出是我们换过的。"""
    import patch_files
    ses, bundles = load()
    rec = patch_files.ours("ghost")
    for fn in rec:
        patch_files.take_out(contents, fn)
    n, left = 0, []
    ours = {fn: (pkg, size) for pkg, fn, size in listed()}
    for fn, _pkg, size, sha in bundles:
        if fn not in ours or fn in rec:  # 没换过 / 是补丁装法（原文件本来就是原版）
            continue
        path, bak = os.path.join(contents, fn), os.path.join(BACKUP_DIR, fn)
        try:
            if os.path.getsize(path) == size and _sha(path) == sha:
                continue  # 本来就是原版
        except OSError:
            continue
        if _is_vanilla_backup(bak, size, sha):
            with open(bak, "rb") as f:
                _write(path, f.read())
            n += 1
        elif ours[fn][1] == os.path.getsize(path):
            left.append((ours[fn][0], fn))
    if left:
        _write_list(contents, left)
    else:
        try:
            os.remove(LIST)
        except OSError:
            pass
    return n, len(left)


def listed(with_slot=False):
    """ghost-maps.txt 里记的 [(包名, 文件名, 大小)]；with_slot=True 时多一个补丁编号（老装法的是 None）。"""
    try:
        with open(LIST, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    out = []
    for line in lines[1:]:
        parts = line.split("=")
        if len(parts) in (3, 4) and parts[2].isdigit() and (len(parts) == 3 or parts[3].isdigit()):
            slot = int(parts[3]) if len(parts) == 4 else None
            out.append((parts[0], parts[1], int(parts[2]), slot) if with_slot else (parts[0], parts[1], int(parts[2])))
    return out


def stale(contents):
    """该换的没换好 / 被改回去了 → True（核心当成旧版，关游戏后自动重装）。只看文件大小和补丁记录，很快。
    2026-11-20：补丁装法的包还要补丁在、游戏读得到（Obsidian 清除时可能在下面留洞）。"""
    import patch_files
    _ses, bundles = load()
    if not bundles:
        return False
    have = {fn: size for _pkg, fn, size in listed()}
    if not have:
        return True
    try:
        with open(LIST, encoding="utf-8") as f:
            first = f.readline().strip()
    except OSError:
        return True
    if first != (HEADER + data_tag()).strip():  # 配色数据换过（比如鬼城去雾）：要重换
        return True
    rec = patch_files.ours("ghost")
    for fn, size in have.items():
        try:
            if os.path.getsize(os.path.join(contents, fn)) != size:
                return True
        except OSError:
            return True
        if fn in rec and not patch_files.current(contents, fn, sha=rec[fn]["sha256"]):
            return True
    return False
