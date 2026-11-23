"""
中英文切换（2026-11-14 用户要求：右上角点 CN / EN 切换）。

- 界面上的字照旧用中文写在代码里；英文版时 tr(中文) 查 lang_en.json 换成英文，查不到就原样显示中文。
- 控件（ui.Label、Button、Segmented……）显示文字时自动调 tr，页面代码不用改。
- 带数字的句子写成模板：T("本周还剩 {0} 次。", n)，模板本身是查表的键。
- 语言优先存 %LOCALAPPDATA%/HellBox/language.txt；旧位置 %APPDATA%/Arrowhead/Helldivers/hellbox/language.txt 仍读；都写不进去时再试程序目录。切换后 HellBox 自己重开一次。
- 没选过语言时默认中文（2026-11-23）。
"""
import json
import os
import sys

FILE = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox", "language.txt")
LANGS = ("zh", "en")


def _lang_files():
    """语言文件按优先级：自己的 LocalAppData → 旧位置 → 程序目录；读的时候取修改时间最新的一个。"""
    out = []
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        out.append(os.path.join(base, "HellBox", "language.txt"))
    out.append(FILE)
    if getattr(sys, "frozen", False):
        out.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "language.txt"))
    else:
        out.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "language.txt"))
    seen = set()
    files = []
    for p in out:
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen:
            seen.add(key)
            files.append(p)
    return files


def _res_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


def _system_lang():
    """没选过语言时默认中文；保留函数名给旧调用。"""
    return "zh"


def _load_lang():
    """点过右上角 CN / EN 的（language.txt）照用；没选过 / 文件坏了默认中文。"""
    best = None
    for path in _lang_files():
        try:
            stamp = os.stat(path).st_mtime
            with open(path, encoding="ascii") as f:
                lang = f.read().strip()
            if lang in LANGS and (best is None or stamp > best[0]):
                best = (stamp, lang)
        except (OSError, ValueError):
            pass
    if best is not None:
        return best[1]
    return _system_lang()


LANG = _load_lang()
_EN = {}
if LANG == "en":
    try:
        with open(os.path.join(_res_dir(), "lang_en.json"), encoding="utf-8") as f:
            _EN = json.load(f)
    except (OSError, ValueError):
        _EN = {}
    for _k, _v in list(_EN.items()):  # 拼在别的句子后面的（以换行开头的那种）按行查时也能查到
        if _k.startswith("\n"):
            _EN.setdefault(_k.lstrip("\n"), _v.lstrip("\n"))

def _add_monster_names():
    """怪名用游戏自己的英文名（ai\\drill_monsters.json 里的 en；叫法 nick 也映射过去）。"""
    try:
        import paths
        with open(os.path.join(paths.ROOT, "ai", "drill_monsters.json"), encoding="utf-8") as f:
            races = json.load(f).get("races", {})
    except (ImportError, OSError, ValueError):
        return
    for info in races.values():
        for u in info.get("units", []):
            en = (u.get("en") or "").title()
            if not en:
                continue
            for zh in (u.get("zh"), u.get("nick")):
                if zh:
                    _EN.setdefault(zh, en)


def _game_title(s):
    """游戏英文资源里有的是全大写（升级名 EXTENDED MAGAZINE）：转成首字母大写，介词 / 连词小写。"""
    if not s or not s.isupper():
        return s
    small = {"of", "and", "or", "the", "a", "an", "to", "in", "on", "for"}
    words = s.title().split(" ")
    return " ".join(w.lower() if i and w.lower() in small else w for i, w in enumerate(words))


def _add_data_names():
    """数据修改页：武器 / 战备 / 怪物名用游戏自己的英文名（ai\\weapon_fields.json、strat_fields.json、enemy_fields.json 的 en），
    武器升级名用 upgrades_en。战备标题「中文（English）」的写法也映射成英文。"""
    try:
        import paths
    except ImportError:
        return

    def load(name):
        try:
            with open(os.path.join(paths.ROOT, "ai", name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    pairs, ups = [], {}
    for w in (load("weapon_fields.json").get("weapons") or {}).values():
        pairs.append((w.get("zh"), w.get("en")))
        for zh, en in zip(w.get("upgrades") or [], w.get("upgrades_en") or []):
            if zh and en and zh != en:
                cnt = ups.setdefault(zh, {})
                cnt[_game_title(en)] = cnt.get(_game_title(en), 0) + 1
    for s in (load("strat_fields.json").get("strats") or {}).values():
        pairs.append((s.get("zh"), s.get("en")))
    for u in (load("enemy_fields.json").get("units") or {}).values():
        pairs.append((u.get("zh"), u.get("en")))
    for zh, en in pairs:
        if not zh or not en or zh == en:
            continue
        _EN.setdefault(zh, _game_title(en))
        _EN.setdefault(f"{zh}（{en}）", _game_title(en))
    for zh, cnt in ups.items():  # 同一个中文对几个英文（穿甲弹）时取用得最多的
        _EN.setdefault(zh, max(cnt, key=cnt.get))


if LANG == "en":
    _add_monster_names()
    _add_data_names()

MISSING = set()  # 英文版里没查到的（开发时看漏了哪些）


def is_en():
    return LANG == "en"


def tr(s):
    """中文 -> 当前语言。不是字符串、中文版、或查不到时原样返回。多行的整句查不到就一行一行查。"""
    if LANG != "en" or not isinstance(s, str) or not s:
        return s
    got = _EN.get(s)
    if got is not None:
        return got
    if "\n" in s:
        lines = s.split("\n")
        out = [_EN.get(ln, ln) if ln else ln for ln in lines]
        if out != lines:
            return "\n".join(out)
    if any("一" <= ch <= "鿿" for ch in s):
        MISSING.add(s)
    return s


def T(template, *args, **kw):
    """带数字的句子：模板先翻译再填数。"""
    return tr(template).format(*args, **kw)


def set_lang(lang):
    last = None
    for path in _lang_files():
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="ascii") as f:
                f.write(lang)
            return
        except OSError as e:
            last = e
    raise last or OSError("no writable language file")
