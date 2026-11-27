"""HellBox 收进来的半糖（HalfSugar）HelldiversOptimization 功能设置（2026-11-20 HD1-035）。
2026-11-21 HD1-038 用户定：其中来自 QoL Mod 的全部删掉，只留半糖自己的和鬼城灯光。
2026-11-22 用户：「资料和状态」两项（军械库显示真实数值、显示身上的状态）也是 QoL 的，删了。

功能本体是 HalfSugar（半糖）HelldiversOptimization 的 Lua 模块（mod/hop/，拼成 src/hellbox_hop.lua）。
设置存在 mod/hellbox_hop.json；改了就写 %APPDATA%/Arrowhead/Helldivers/hellbox/hop.txt（HBHOP1，一行一个 键=值），
游戏每秒读一次，挂钩一直装着、每次用的时候看开关 = 热生效。装 MOD 时也把现在的值编进脚本当初始值。

所有值在游戏那边都是字符串：开关 "1" / "0"，数字照写，选项写键名。
"""
import json
import os
from pathlib import Path

import safe_write

FILE = Path(__file__).with_name("hellbox_hop.json")
LIVE = Path(os.environ.get("APPDATA", "")) / "Arrowhead" / "Helldivers" / "hellbox" / "hop.txt"

# (键, 类型, 默认, 附加)：类型 toggle / number（附加 = (最小, 最大, 步长)）/ choice（附加 = 可选键）
SPEC = [
    # ── 名字与画面 ──
    ("long_text", "toggle", True, None),  # 2026-11-26「名字不乱码」：长名字截断 + 字体缺字改用聊天字体（src/hellbox_name_font.lua）；「名字加深色底」用户删了
    # ── 操作 ──
    ("bolt_reload", "toggle", False, None),
    # ── 玩法：鬼城蜜蜂光圈、信标更亮（src/hellbox_drone_light.lua 读；2026-11-20 用户删了探照灯和「在哪里亮」）──
    ("drone_light", "toggle", False, None),
    ("drone_light_percent", "number", 60, (10, 100, 10)),
    ("beacon_light", "toggle", False, None),                   # 2026-11-20 用户：「更亮的信标」
    ("beacon_light_percent", "number", 60, (10, 100, 10)),
    # ── 显示：本机潜兵调亮（src/hellbox_self_bright.lua 读；2026-11-26 用户要：只调亮不发光、拖动条、热修改）──
    ("self_bright", "toggle", False, None),
    ("self_bright_percent", "number", 30, (5, 200, 5)),  # 2026-11-27 上限 200%
]
KIND = {key: kind for key, kind, _, _ in SPEC}
DEFAULT = {key: default for key, _, default, _ in SPEC}
EXTRA = {key: extra for key, _, _, extra in SPEC}

# 自用版（带 AI 陪玩）里不给开的（2026-11-21 起没有了：禁止本机加人是 QoL 的，删了）
DEV_ONLY_OFF = set()


def _clean(key, value):
    kind, extra, default = KIND[key], EXTRA[key], DEFAULT[key]
    if kind == "toggle":
        return value if isinstance(value, bool) else default
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        lo, hi, _ = extra
        return min(max(value, lo), hi)
    return value if value in extra else default


def load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {key: _clean(key, data.get(key, DEFAULT[key])) for key in DEFAULT}


def save(changes):
    data = load()
    for key, value in changes.items():
        if key in DEFAULT:
            data[key] = _clean(key, value)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(FILE, json.dumps(data, ensure_ascii=False, indent=2) + "\n", crlf=True)
    return data


def _text(key, value):
    kind = KIND[key]
    if kind == "toggle":
        return "1" if value else "0"
    if kind == "number":
        return ("%g" % value)
    return str(value)


def _lang():
    """HellBox 界面语言（游戏里的状态提示跟它走）；单独跑 build.py 时没有 i18n，按中文。"""
    try:
        import i18n
        return "en" if i18n.LANG == "en" else "zh"
    except Exception:
        return "zh"


def values(dev=False, lang=None):
    """游戏那边看到的 键 -> 字符串。dev = 自用版（DEV_ONLY_OFF 强制关）。"""
    data = load()
    out = {key: _text(key, data[key]) for key in DEFAULT}
    if dev:
        for key in DEV_ONLY_OFF:
            out[key] = "0"
    for key in yielded():  # 2026-11-20 HD1-036：Obsidian 里开着同样的 MOD，HellBox 这份让出（存的选择不动）
        if key in out:
            out[key] = "0"
    out["lang"] = lang or _lang()
    return out


def yielded():
    """{开关: Obsidian 里的 MOD 名}：这些 HellBox 不开（obsidian_compat.py）。认不出就当没有。"""
    try:
        import obsidian_compat
        return obsidian_compat.yields()
    except Exception:
        return {}


def lua_defaults(quote, dev=False, lang=None):
    return "{" + ",".join(f"{key}={quote(value)}" for key, value in values(dev, lang).items()) + "}"


def write_live(dev=False, lang=None):
    LIVE.parent.mkdir(parents=True, exist_ok=True)
    lines = ["HBHOP1"] + [f"{key}={value}" for key, value in values(dev, lang).items()]
    safe_write.write_text(LIVE, "\n".join(lines) + "\n", crlf=True)
    return LIVE
