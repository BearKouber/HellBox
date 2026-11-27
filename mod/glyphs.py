"""游戏字体里有哪些字（2026-11-26 用户要：名字乱码自己研究着修）。

研究结果（游戏启动包 dd5d5b00fde9b0fb 里的 5 个字体，按语言各一份）：
  - HUD、菜单用的 handel_small / handel_normal / insignia_headliner / insignia_headliner_large
    只收了游戏自己文字用到的字：简体中文版 1964 个左右（汉字 1842 个），连「龙」「喵」「萌」都没有；英文版 167 个，一个汉字都没有。
  - 聊天框用的 chat 只有一份，38915 个字：常用汉字 4E00～9FA5 全部、韩文 11172 个全部、日文假名、俄文。
  - 名字里有字体没有的字，游戏就画成乱码。
所以装 MOD 时从玩家自己的游戏里读出每个字体（每种语言）有哪些字，编进脚本；游戏里画字之前查一下，
有缺的字就这一段改用 chat 字体画（src/hellbox_name_font.lua）。不带任何游戏文件，全是装的时候现读。

字体资源格式（自己拆的）：u32 版本 5、几个 float、偏移 0x18 是字数 n，0x40 起每个字 32 字节，前 4 字节是 Unicode 码位。
"""
import json
import os
import struct
import zlib

from bundle import murmur64a

FONT_BUNDLE = "dd5d5b00fde9b0fb"
FONT_TYPE = murmur64a(b"font")
FONTS = ["fonts/handel_small", "fonts/handel_normal", "fonts/insignia_headliner", "fonts/insignia_headliner_large",
         "fonts/chat"]
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "out", "glyphs_cache.json")
CACHE_VERSION = 1


class _Lazy:
    """边解压边读：字体在包的最前面，读到就停，不用解压整个 46MB 的包。"""

    def __init__(self, f):
        self.f = f
        self.buf = bytearray()
        self.done = False
        head = f.read(12)
        if len(head) < 12 or struct.unpack_from("<I", head, 0)[0] != 0xF0000004:
            raise ValueError("不是游戏资源包")

    def need(self, end):
        while len(self.buf) < end and not self.done:
            h = self.f.read(4)
            if len(h) < 4:
                self.done = True
                break
            n = struct.unpack_from("<I", h, 0)[0]
            chunk = self.f.read(n)
            self.buf += chunk if n == 0x10000 else zlib.decompress(chunk)
        if len(self.buf) < end:
            raise ValueError("资源包读到头了")
        return self.buf


def _codepoints(data):
    n = struct.unpack_from("<I", data, 0x18)[0]
    if 0x40 + 32 * n > len(data):
        raise ValueError("字体格式不认识")
    return sorted({struct.unpack_from("<I", data, 0x40 + 32 * i)[0] for i in range(n)})


def read_fonts(path):
    """{字体名: {语言号: [码位...]}}"""
    want = {murmur64a(name.encode()): name for name in FONTS}
    out = {}
    with open(path, "rb") as f:
        lz = _Lazy(f)
        buf = lz.need(4)
        count = struct.unpack_from("<I", buf, 0)[0]
        off = 4 + 256 + 16 * count
        for _ in range(count):
            buf = lz.need(off + 24)
            t, name, nv, _ = struct.unpack_from("<QQII", buf, off)
            off += 24
            buf = lz.need(off + 12 * nv)
            vs = [struct.unpack_from("<III", buf, off + 12 * i) for i in range(nv)]
            off += 12 * nv
            for lang, size, _ in vs:
                if t == FONT_TYPE and name in want:
                    buf = lz.need(off + size)
                    out.setdefault(want[name], {})[lang] = _codepoints(bytes(buf[off:off + size]))
                off += size
            if len(out) == len(FONTS):
                break
    return out


def ranges(cps):
    """[码位...] -> "4e00-9fa5,ff01" 这种十六进制区间串（Lua 那边解开）"""
    parts, start, prev = [], None, None
    for c in cps:
        if start is None:
            start = prev = c
        elif c == prev + 1:
            prev = c
        else:
            parts.append(f"{start:x}" if start == prev else f"{start:x}-{prev:x}")
            start = prev = c
    if start is not None:
        parts.append(f"{start:x}" if start == prev else f"{start:x}-{prev:x}")
    return ",".join(parts)


def table(game_dir):
    """给 Lua 的数据 {字体名: {语言号: 区间串}}；读不到（没装游戏 / 格式变了）返回 None，游戏里就只做长名字截断。"""
    path = os.path.join(game_dir, "contents", FONT_BUNDLE)
    try:
        st = os.stat(path)
        key = [CACHE_VERSION, st.st_size, int(st.st_mtime)]
        try:
            with open(CACHE, encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("key") == key:
                return cached["fonts"]
        except (OSError, ValueError, KeyError, AttributeError):
            pass
        fonts = {name: {str(lang): ranges(cps) for lang, cps in langs.items()}
                 for name, langs in read_fonts(path).items()}
        if "fonts/chat" not in fonts or len(fonts) < 2:
            return None
        try:
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            tmp = CACHE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"key": key, "fonts": fonts}, f)
            os.replace(tmp, CACHE)
        except OSError:
            pass
        return fonts
    except (OSError, ValueError, struct.error, zlib.error):
        return None


def lua_table(game_dir, lua_quote):
    fonts = table(game_dir)
    if not fonts:
        return "nil"
    items = []
    for name in sorted(fonts):
        langs = ", ".join(f"[{int(lang)}] = {lua_quote(text)}" for lang, text in sorted(fonts[name].items(), key=lambda kv: int(kv[0])))
        items.append(f"[{lua_quote(name)}] = {{{langs}}}")
    return "{" + ", ".join(items) + "}"
