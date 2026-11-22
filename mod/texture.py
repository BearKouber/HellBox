r"""指针贴图（mouse_cursor 资源）：解析 / 打包 / 改色。

格式（未压缩、无 mipmap），例：hud/cursors/game 共 4116 字节

    0x00  u32 宽
    0x04  u32 高
    0x08  u32 热点 x（点击位置，十字是正中间）
    0x0c  u32 热点 y
    0x10  u32 像素字节数（32*32*4 = 0x1000）
    0x14  像素，每像素 4 字节：B, G, R, A（Windows 指针的顺序，不预乘）

顺序的证据（2026-11-03）：游戏"藏起指针"用的 hud/cursors/invisible，
按 B,G,R,A 读第 4 字节最大只有 1（确实看不见）；第一版当成 A,B,G,R 改，所以装了没效果。
原图都是灰白色，R 和 B 谁在前看不出来——如果游戏里红蓝反了，就是这里要对调。
"""
import struct

HEADER = 20


def parse(data: bytes):
    """返回 (宽, 高, 头 20 字节, [(r, g, b, a), ...])。"""
    w, h, _hx, _hy, size = struct.unpack_from("<5I", data, 0)
    if size != w * h * 4 or len(data) != HEADER + size or not (0 < w <= 128 and 0 < h <= 128):
        raise ValueError(f"不是指针贴图：{w}x{h}，{len(data)} 字节")
    px = []
    for i in range(w * h):
        b, g, r, a = data[HEADER + i * 4:HEADER + i * 4 + 4]
        px.append((r, g, b, a))
    return w, h, bytes(data[:HEADER]), px


def build(header: bytes, pixels) -> bytes:
    out = bytearray(header)
    for r, g, b, a in pixels:
        out += bytes((b, g, r, a))
    return bytes(out)


def recolor(w, h, pixels, color, opacity, outline):
    """改成纯色、统一不透明度。

    color   : (r, g, b)
    opacity : 0~1，图里最不透明的地方就是这个值；淡的部分按原来的比例跟着拉上去，
              所以原版很淡的光斑、过渡帧也会和十字一样清楚。
    outline : True 时在形状外面描一圈黑边（亮地面上也能看出轮廓）；False 时原图自带的暗边也变透明，一点黑都没有。
    """
    top = max((a for _r, _g, _b, a in pixels), default=0)
    if top == 0:
        return list(pixels)
    full = opacity * 255.0
    cr, cg, cb = color
    # 原图是灰白色：亮的地方上色，暗的地方（十字和圆弧之间的缝）保持暗。
    # 亮度按这张图自己最亮的地方算——原版光斑整体是深灰（最亮 99），不这样会整团变黑。
    lums = [r * 0.299 + g * 0.587 + b * 0.114 for r, g, b, a in pixels]
    top_lum = max((l for l, p in zip(lums, pixels) if p[3] > 0), default=0) or 1.0
    out = []
    for lum, (_r, _g, _b, a) in zip(lums, pixels):
        na = min(255, int(round(a / top * full)))
        if na <= 0:
            out.append((0, 0, 0, 0))
            continue
        k = min(1.0, lum / top_lum / 0.6)
        if outline:
            out.append((round(cr * k), round(cg * k), round(cb * k), na))
        else:
            # 不要黑边（2026-11-14 用户实测：关了黑边还有黑边）：原图自带的暗边 / 暗缝不画成黑色，改成按暗的程度变透明
            ka = int(round(na * k))
            out.append((cr, cg, cb, ka) if ka > 0 else (0, 0, 0, 0))
    if outline:
        out = _add_outline(w, h, out, full)
    return out


def _add_outline(w, h, px, full):
    strong = [a >= full * 0.5 for _r, _g, _b, a in px]
    edge_a = int(round(full * 0.9))
    out = list(px)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if strong[i]:
                continue
            near = any(
                strong[yy * w + xx]
                for yy in (y - 1, y, y + 1) if 0 <= yy < h
                for xx in (x - 1, x, x + 1) if 0 <= xx < w
            )
            if near:
                out[i] = (0, 0, 0, max(edge_a, px[i][3]))
    return out
