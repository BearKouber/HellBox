"""
训练地图小图：游戏按编号拼图，MOD 负责拼好写进 maps2/<编号>.txt，这里从玩家游戏文件里取地块贴图画出来。
"""
import math
import os
import struct

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

import ui
from i18n import tr

DIR = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox")
MAPS = os.path.join(DIR, "maps2")
TILES = os.path.join(DIR, "tiles3")
REQUESTS = os.path.join(DIR, "map-requests.txt")
BACKGROUND = "#23221e"

MATERIAL = 0xEAC0B497876ADEDF
ENV_BUNDLES = {
    "env_desert/": "13f6367c7c48c087", "env_forest/": "280d4ef7353a0233", "env_lava/": "78b8776a7a8ac4d1",
    "env_snow/": "29538f17d3220c55", "env_city/": "27dcbb4888c161c9", "env_provinggrounds/": "aadc00a12587254a",
}

_layouts = {}
_tiles = {}
_bundles = {}


# ------------------------------------------------------------ 请求 / 读布局
_wanted = {}


def trial_key(race, tod, diff, chal, terrain):
    return f"t {race} {tod} {diff} {chal} {int(terrain)}", f"t_{race}_{tod}_{diff}_{chal}_{int(terrain)}"


def _line(item):
    return item[0] if isinstance(item, tuple) else str(int(item))


def request(seeds, owner="main"):
    _wanted[owner] = [s for s in seeds if s is not None]
    order = [k for k in _wanted if k != "picker"] + (["picker"] if "picker" in _wanted else [])
    lines = list(dict.fromkeys(_line(s) for k in order for s in _wanted[k]))
    try:
        os.makedirs(MAPS, exist_ok=True)
        tmp = REQUESTS + ".tmp"
        with open(tmp, "w", encoding="ascii") as f:
            f.write("".join(f"{s}\n" for s in lines))
        os.replace(tmp, REQUESTS)
    except OSError:
        pass


def load(seed):
    if seed is None:
        return None
    seed = seed[1] if isinstance(seed, tuple) else int(seed)
    if seed in _layouts:
        return _layouts[seed]
    try:
        with open(os.path.join(MAPS, f"{seed}.txt"), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    if not lines or lines[0] != "HBMAP2":
        return None
    out = {"env": "", "mode": "", "tiles": []}
    for line in lines[1:]:
        parts = line.split()
        if parts[:1] == ["env"]:
            out["env"] = parts[1] if len(parts) > 1 else ""
        elif parts[:1] == ["mode"]:
            out["mode"] = parts[1] if len(parts) > 1 else ""
        elif parts[:1] == ["tile"] and len(parts) == 9:
            try:
                out["tiles"].append({"name": parts[1], "rot": int(parts[2]) % 4, "x": int(parts[3]), "y": int(parts[4]),
                                     "sx": int(parts[5]), "sy": int(parts[6]), "mult": float(parts[7]),
                                     "edge": parts[8] == "1"})
            except ValueError:
                pass
    if not out["tiles"]:
        return None
    _layouts[seed] = out
    return out


# ------------------------------------------------------------ 从游戏文件取贴图
def _bundle(env):
    if env in _bundles:
        return _bundles[env]
    _bundles[env] = None
    name = ENV_BUNDLES.get(env)
    if not name:
        return None
    try:
        import build
        import cursor_patch as cp
        with open(os.path.join(build.game_dir(), "contents", name), "rb") as f:
            raw, _blocks, _size = cp.decompress_all(f.read())
    except Exception:  # noqa: BLE001
        return None
    n = struct.unpack_from("<I", raw, 0)[0]
    off = 4 + 256 + 16 * n
    material, res = None, {}
    for _ in range(n):
        t, h, nv, _so = struct.unpack_from("<QQII", raw, off)
        off += 24
        sizes = [struct.unpack_from("<III", raw, off + 12 * i)[1] for i in range(nv)]
        off += 12 * nv
        for size in sizes:
            if t == MATERIAL and material is None:
                material = raw[off:off + size]
            elif size:
                res.setdefault(h, raw[off:off + size])
            off += size
    _bundles[env] = (material, res) if material else None
    return _bundles[env]


def _texture_for(env, name):
    got = _bundle(env)
    if not got:
        return None
    material, res = got
    import cursor_patch as cp
    key = struct.pack("<I", cp.murmur64a(name.encode()) >> 32)
    pos = material.find(key)
    while pos >= 0:
        if pos % 4 == 0:
            for extra in range(8, 72, 4):
                if pos + extra + 8 <= len(material):
                    h = struct.unpack_from("<Q", material, pos + extra)[0]
                    if h in res and res[h][:4] == b"DDS ":
                        return res[h]
        pos = material.find(key, pos + 1)
    return None


def _rgb565(c):
    return ((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31


def decode_dds(blob):
    if blob[:4] != b"DDS ":
        return None
    h, w = struct.unpack_from("<II", blob, 12)
    four = blob[84:88]
    data = blob[128:]
    if four not in (b"DXT1", b"DXT5") or w <= 0 or h <= 0:
        return None
    bs = 8 if four == b"DXT1" else 16
    px = bytearray(w * h * 4)
    bw, bh = (w + 3) // 4, (h + 3) // 4
    if len(data) < bw * bh * bs:
        return None
    off = 0
    for by in range(bh):
        for bx in range(bw):
            alpha = None
            if bs == 16:
                a0, a1 = data[off], data[off + 1]
                bits = int.from_bytes(data[off + 2:off + 8], "little")
                if a0 > a1:
                    table = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
                else:
                    table = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
                alpha = [table[(bits >> (3 * i)) & 7] for i in range(16)]
                coff = off + 8
            else:
                coff = off
            c0, c1, idx = struct.unpack_from("<HHI", data, coff)
            r0, r1 = _rgb565(c0), _rgb565(c1)
            if c0 > c1 or bs == 16:
                cols = [r0 + (255,), r1 + (255,),
                        tuple((2 * a + b) // 3 for a, b in zip(r0, r1)) + (255,),
                        tuple((a + 2 * b) // 3 for a, b in zip(r0, r1)) + (255,)]
            else:
                cols = [r0 + (255,), r1 + (255,), tuple((a + b) // 2 for a, b in zip(r0, r1)) + (255,), (0, 0, 0, 0)]
            for i in range(16):
                x, y = bx * 4 + (i & 3), by * 4 + (i >> 2)
                if x < w and y < h:
                    r, g, b, a = cols[(idx >> (2 * i)) & 3]
                    if alpha is not None:
                        a = alpha[i]
                    p = (y * w + x) * 4
                    px[p:p + 4] = bytes((b, g, r, a))
            off += bs
    img = QImage(bytes(px), w, h, w * 4, QImage.Format.Format_ARGB32)
    return img.copy()


def tile_image(env, name):
    key = (env, name)
    if key in _tiles:
        return _tiles[key]
    png = os.path.join(TILES, (env.strip("/") + "__" + name + ".png"))
    img = QImage(png) if os.path.isfile(png) else QImage()
    if img.isNull():
        blob = _texture_for(env, name)
        img = decode_dds(blob) if blob else None
        if img is not None:
            try:
                os.makedirs(TILES, exist_ok=True)
                img.save(png)
            except OSError:
                pass
    else:
        pass
    _tiles[key] = img if img is not None and not img.isNull() else None
    return _tiles[key]


# ------------------------------------------------------------ 画
def _placements(layout):
    genocide = layout["mode"] in ("genocide", "provinggrounds_genocide_map")
    out = []
    for t in layout["tiles"]:
        m = 1.0
        x, y = float(t["x"]), float(t["y"] + 1)
        if genocide:
            if t["edge"]:
                continue
            m = t["mult"]
            x += (m - 1) * 0.5
            y += (m - 1) * 0.5
        rot = t["rot"]
        if rot == 1:
            x, y = x + 1, y - (m - 1)
        elif rot == 2:
            x, y = x + 1, y + 1
        elif rot == 3:
            x, y = x - (m - 1), y + 1
        else:
            x, y = x - (m - 1), y - (m - 1)
        out.append((t, x + 1, y, t["sx"] * m, t["sy"] * m, rot))
    return out


def _corners(px, py, w, h, rot):
    a = math.radians(-rot * 90)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for cx, cy in ((0, -h), (w, -h), (w, 0), (0, 0)):
        pts.append((px + cx * ca - cy * sa, -py + cx * sa + cy * ca))
    return pts


def paint(p, rect, layout, empty_text="开游戏后显示"):
    p.fillRect(rect, ui.qc(BACKGROUND if layout else ui.INSET))
    if not layout:
        if empty_text:
            p.setFont(ui.f_zh(8))
            p.setPen(ui.qc(ui.MUTED))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, tr(empty_text))
        return
    img = _rendered(layout, rect.width(), rect.height())
    if img is not None:
        p.drawImage(rect.topLeft(), img)


_cache = {}


def _rendered(layout, w, h):
    key = (id(layout), w, h)
    if key in _cache:
        return _cache[key]
    places = _placements(layout)
    pts = [c for pl in places for c in _corners(*pl[1:])]
    if not pts or w < 4 or h < 4:
        return None
    pad = 3
    x0, x1 = min(c[0] for c in pts), max(c[0] for c in pts)
    y0, y1 = min(c[1] for c in pts), max(c[1] for c in pts)
    s = min((w - 2 * pad) / max(x1 - x0, 1e-6), (h - 2 * pad) / max(y1 - y0, 1e-6))
    ox = (w - s * (x1 - x0)) / 2 - s * x0
    oy = (h - s * (y1 - y0)) / 2 - s * y0
    terrain = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    terrain.fill(0)
    p = QPainter(terrain)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for t, px, py, tw, th, rot in places:
        p.save()
        p.translate(QPointF(ox + s * px, oy - s * py))
        p.rotate(-rot * 90)
        target = QRectF(0, -th * s, tw * s, th * s)
        img = tile_image(layout["env"], t["name"])
        if img is not None:
            p.drawImage(target, img)
        else:
            p.fillRect(target, QColor("#6d6250"))
        p.restore()
    p.end()
    terrain = terrain.mirrored(False, True)
    sil = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    sil.fill(0)
    p = QPainter(sil)
    p.drawImage(0, 0, terrain)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(0, 0, w, h, QColor(12, 10, 8))
    p.end()
    out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(ui.qc(BACKGROUND))
    p = QPainter(out)
    d = max(1, round(min(w, h) / 160))
    for dx in (-d, 0, d):
        for dy in (-d, 0, d):
            if dx or dy:
                p.drawImage(dx, dy, sil)
    p.drawImage(0, 0, terrain)
    p.end()
    if len(_cache) > 64:
        _cache.clear()
    _cache[key] = out
    return out


class MapThumb(QWidget):

    def __init__(self, size=112):
        super().__init__()
        self.setFixedSize(size, size)
        self.layout_data = None

    def set_cells(self, layout):
        if layout is not self.layout_data:
            self.layout_data = layout
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        r = ui.paint_box(p, self.width(), self.height(), ui.INSET, 2, 0)
        paint(p, QRect(r), self.layout_data)
