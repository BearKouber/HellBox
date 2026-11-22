"""房间名描述（2026-11-18 V0.97 第 ⑤ 步，用户定，docs/任务/HD1-033-玩法页方案.md 第四节 5）。

用 HellBox 当房主，真正的 Steam 房间名自动变成「[HellBox · 鬼城 · 限装备 · 改怪物] 房间名」，没装 HellBox 的人也看得到。
方括号里只写影响平衡的：玩法（鬼城、限装备、随机掉落、其他修正参数、填弹惊喜）和数据修改（出怪、怪物、武器、战略配备、绝地潜兵，
场上上限开了破限单独写）。只开了「功能」页那些自己用的开关或什么都没开 = 「[HellBox] 房间名」。
试验场（联机版）= 「[HellBox · 试验场] 房间名」（写游戏里的叫法）。

谁拼什么：
- 这里（HellBox）拼「描述」：它知道玩法页、配装块、数据修改页的设置，也知道界面语言（描述跟界面语言走），
  拼好写进 %APPDATA%/Arrowhead/Helldivers/hellbox/room-desc.txt（HBROOM1，内容变了才写）。
- 游戏（mod/src/room_name.lua）读这个文件，当房主时拼成真房间名并写进 Steam 房间数据：
  「[HellBox · 描述] 名字」，名字 = 自定义房间名，没设就是我的名字 / Steam 昵称（游戏这边才知道昵称）；太长时按下面的规矩截短。
  游戏里拼的好处：房间名永远是游戏真正在用的设置算出来的（play.txt / host-loadout.txt / data-live.txt 都是游戏自己读的文件），
  不会出现界面和游戏两套判断；这里的预览和游戏里的拼法是同一套规矩（compose 两边一样，room_name_sim 里有同样的例子）。
文件格式：
    HBROOM1
    full=鬼城 · 限装备 · 改怪物     平时用的描述（空 = 只有 [HellBox]）
    short=鬼城 · 限装备 · 改数据     太长时用的简写（同类里有两样以上就合成一个词：修正参数、改数据）
    tfull=试验场 · 改怪物           游戏说下一局 / 这一局是试验场时用这两行
    tshort=试验场 · 改数据
    order=name                      2026-11-21 HD1-038：名字放前面「名字 [HellBox …]」；tag / 没有 = [HellBox …] 在前（原来的样子）

2026-11-22 用户定新规矩（Dive Harder 作者说房间名太长，列表里一栏只显示十几个字）：
  - 开头：开了别人看得出来、影响游戏性的东西 = [Hex …]，否则还是 [HellBox]。算 Hex 的：任何玩法、任何数据修改、
    「功能」页的带箱子上车 / 丢支援装备。试验场（联机版）一律 Hex。
  - 方括号里：鬼城写出来，别的玩法只写个数「鬼城 +3」（没鬼城就是「玩法 +3」）；
    数据改得比原版难（敌人数量、场上上限、怪物属性任何一项超过原版）再加「炼狱」。只改武器 / 战备 / 潜兵这些不写炼狱，开头还是 Hex。
  - room-desc.txt 多两行 tag= / ttag=（Hex 或 HellBox，游戏只认这两个）；full 和 short 现在一样（新写法已经够短）。
长度（compose）：游戏本身不限房间名长度（选房列表里长名字是滚动显示的，menu_screen_campaign_multiplayer.lua draw_looping_scroll），
Steam 房间数据的值最多 8192 字节。为了选房列表里一眼能看全，整个房间名定 MAX_BYTES = 200 字节（约 60 个汉字）：
  1. 「[HellBox · 全部描述] 名字」装得下就用它；
  2. 装不下换简写「[HellBox · 简写] 名字」；
  3. 还装不下就截名字（按整个字切，末尾加「…」），描述不动，所以「[HellBox」开头和「]」一定在。
"""
import json
import os
import time

import paths

HB_DIR = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox")
FILE = os.path.join(HB_DIR, "room-desc.txt")
DATA_LIVE = os.path.join(HB_DIR, "data-live.txt")
WORDS = os.path.join(paths.ROOT, "ai", "room_words.json")
MAX_BYTES = 200
SEP = " · "
ELLIPSIS = "…"

# HellBox 自己的词（游戏里没有对应的短名字）：键 -> (中文, 英文)。
# 英文沿用 HellBox 界面里这些功能的英文名（lang_en.json）。
OWN = {
    "limit": ("限装备", "Limited Loadout"),
    "drop": ("随机掉落", "Random Drops"),
    "m_spawn": ("改出怪", "Mod Spawns"),
    "m_enemy": ("改怪物", "Mod Enemies"),
    "m_weapon": ("改武器", "Mod Weapons"),
    "m_strat": ("改战略配备", "Mod Stratagems"),
    "m_player": ("改绝地潜兵", "Mod Helldivers"),
    "mods": ("改数据", "Data Mods"),
    "uncapped": ("破限", "Uncapped"),
    "saber": ("军刀", "Saber"),  # 2026-11-21 修正参数「副武器换成军刀」
    "modes": ("玩法", "Modes"),  # 2026-11-22 新规矩：没鬼城时「玩法 +3」
    "inferno": ("炼狱", "Inferno"),  # 2026-11-22 数据改得比原版难
}
TAG_BOX, TAG_HEX = "HellBox", "Hex"
ENEMY_FIELDS = os.path.join(paths.ROOT, "ai", "enemy_fields.json")
# 游戏文字资源里取不到时的备用（ai/room_words.json 由 tools/room_words.py 生成）
GAME_FALLBACK = {
    "pg": ("试验场", "Proving Grounds"),
    "ghost_town": ("鬼城", "Ghost Town"),
    "emp": ("电磁脉冲", "EMP"),
    "reload": ("填弹惊喜", "Reload Surprise"),
    # 2026-11-18 V0.97 整理第 1 批：这几个也换成游戏叫法（试验场的修正参数名），英文取游戏英文
    "ammo": ("伤害击中可提供弹药", "Damaging Hits Give Ammo"),
    "marksman": ("只在击中弱点时造成双倍伤害", "Double Damage Weak Spots Only"),
    "boots": ("侦察装甲", "Recon Armor"),
    "retaliate": ("误伤友军已反击", "Friendly Fire Is Returned"),
    "events": ("修正参数", "Modifiers"),  # 合成词；游戏里叫 Modifier（room_words.json 的 modifier），这里加复数
}
# play.txt 事件键 -> 词
EVENT_WORD = {"emp": "emp", "get_ammo_from_hits_double_reload_time": "ammo", "marksman": "marksman",
              "super_boots": "boots", "what_goes_around": "retaliate", "sidearm_saber": "saber"}
MOD_KEYS = ("m_spawn", "m_enemy", "m_weapon", "m_strat", "m_player")


def is_en():
    try:
        from i18n import is_en as _is_en
        return _is_en()
    except ImportError:
        return False


_game_words = None


def game_words():
    global _game_words
    if _game_words is None:
        try:
            with open(WORDS, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        _game_words = {k: tuple(data[k]) if isinstance(data.get(k), list) and len(data[k]) == 2 else v
                       for k, v in GAME_FALLBACK.items()}
        mod = data.get("modifier")  # 「修正参数」合成词：英文加复数
        if isinstance(mod, list) and len(mod) == 2:
            _game_words["events"] = (mod[0], mod[1] + "s")
    return _game_words


def word(key, en):
    pair = OWN.get(key) or game_words().get(key)
    return pair[1 if en else 0] if pair else key


# ---------------------------------------------------------------- 现在开了什么
def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def spawn_mods(cmd):
    """spawn.<阵营> 一条命令 -> (出怪改过没有, 破限开没开)。跟 hellbox_results.lua 的 mod_items 同一套判断：
    三条来源不是原版 / 载具放兵改过 / 出生散开 / 固定上限 17～300 = 改过；cap=-1 = 破限（单独算）。"""
    kv = {}
    for part in (cmd or "").split(";"):
        k, _, v = part.partition("=")
        kv[k.strip()] = v.strip()
    changed = any(kv.get(k) in ("mult", "none") for k in ("g", "a", "p"))
    changed = changed or any(kv.get(k) for k in ("gmap", "amap", "pmap"))  # 自己改：有换掉的套餐
    changed = changed or kv.get("v") in ("only", "none")

    def num(k):
        try:
            return int(float(kv.get(k) or 0))
        except ValueError:
            return 0
    changed = changed or (kv.get("v") != "none" and num("vn") > 0) or num("spread") > 0
    cap = num("cap")
    return changed or 16 < cap <= 300, cap == -1


def data_mods():
    """data-live.txt（HellBox 写给游戏的数据修改）-> 改了哪几类 [m_spawn, ...] + 是不是破限。"""
    lines = {}
    for line in _read(DATA_LIVE).splitlines():
        k, _, v = line.partition("=")
        lines[k.strip()] = v.strip()

    def changed(key):
        return lines.get(key, "reset") not in ("", "reset")
    out = []
    spawn_changed = uncapped = False
    for k, v in lines.items():
        if k.startswith("spawn."):
            c, u = spawn_mods(v)
            spawn_changed, uncapped = spawn_changed or c, uncapped or u
    if spawn_changed:
        out.append("m_spawn")
    if changed("params"):
        out.append("m_enemy")
    if changed("weapon"):
        out.append("m_weapon")
    if any(changed(k) for k in lines if k.startswith("strat.")):
        out.append("m_strat")
    if changed("player"):
        out.append("m_player")
    return out, uncapped


def _kv(cmd, sep=";"):
    kv = {}
    for part in (cmd or "").split(sep):
        k, _, v = part.partition("=")
        kv[k.strip()] = v.strip()
    return kv


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def spawn_harder(cmd):
    """出怪命令比原版难吗：哪条来源按倍数出且倍数 > 1，或者场上上限比原版 16 大 / 破限。"""
    kv = _kv(cmd)
    for mode, mult in (("g", "multg"), ("a", "mult"), ("p", "multp")):
        if kv.get(mode) == "mult" and (_num(kv.get(mult)) or 0) > 1:
            return True
    cap = _num(kv.get("cap")) or 0
    return cap == -1 or cap > 16


_enemy_defaults = None


def enemy_default(name, path):
    """怪物某一项的原版数值（ai/enemy_fields.json）；没有 = None。"""
    global _enemy_defaults
    if _enemy_defaults is None:
        _enemy_defaults = {}
        try:
            with open(ENEMY_FIELDS, encoding="utf-8") as f:
                units = json.load(f).get("units") or {}
            for unit, info in units.items():
                for block in info.get("blocks") or []:
                    for row in block.get("rows") or []:
                        v = row.get("value")
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            _enemy_defaults[(unit, row.get("path"))] = float(v)
        except (OSError, ValueError, AttributeError):
            pass
    return _enemy_defaults.get((name, path))


def enemy_harder(cmd):
    """怪物属性命令（pages/data_blocks.enemy_command）比原版难吗：任何一项超过原版。
    common=路径*倍数,…（倍数 > 1 算）；set=怪.路径*倍数（> 1 算）或 怪.路径=值（比原版数大算，开关和路径不算）。"""
    if not cmd or cmd == "reset":
        return False
    kv = _kv(cmd)
    for item in (kv.get("common") or "").split(","):
        _p, _, m = item.rpartition("*")
        if (_num(m) or 0) > 1:
            return True
    for item in (kv.get("set") or "").split(","):
        if "=" in item:
            key, _, val = item.partition("=")
            name, _, path = key.partition(".")
            v, base = _num(val), enemy_default(name, path)
            if v is not None and base is not None and v > base:
                return True
        elif "*" in item:
            _p, _, m = item.rpartition("*")
            if (_num(m) or 0) > 1:
                return True
    return False


def data_harder():
    """data-live.txt 里出怪或怪物属性有没有改得比原版难（房间名的「炼狱」）。"""
    lines = {}
    for line in _read(DATA_LIVE).splitlines():
        k, _, v = line.partition("=")
        lines[k.strip()] = v.strip()
    if any(spawn_harder(v) for k, v in lines.items() if k.startswith("spawn.")):
        return True
    return enemy_harder(lines.get("params"))


def own_hex():
    """「功能」页里别人看得出来、影响游戏性的开关开着没有：带箱子上车、丢支援装备。"""
    on = False
    try:
        import build
        on = bool(build.get_carry_vehicle())
    except Exception:  # noqa: BLE001 单独跑时没有 build
        pass
    try:
        import hellbox_options
        on = on or bool(hellbox_options.load().get("drop"))
    except Exception:  # noqa: BLE001
        pass
    return on


def play_items():
    """玩法里影响平衡的：[键, ...]（顺序 = 房间名里的顺序）。"""
    from pages import host_loadout as hl
    from pages import play_modes as pm
    cfg, lo = pm.load(), hl.load()
    items = []
    custom = cfg.get("custom") == "1"
    evs = pm.split_list(cfg.get("event"))
    if custom and cfg.get("env") == "ghost_town":
        items.append("ghost_town")
    if lo.get("on") == "1" and hl.locked_count(lo):
        items.append("limit")
    if custom and "drop" in evs and pm.split_list(cfg.get("drop")):
        items.append("drop")
    if custom:
        items += [EVENT_WORD[e] for e in evs if e in EVENT_WORD]
        if cfg.get("cond") == "reload_surprise":
            items.append("reload")
    return items


def describe(en=None):
    """-> {"full", "short", "tfull", "tshort", "tag", "ttag"}（描述不带方括号；tag = 开头写 Hex 还是 HellBox）。
    2026-11-22 用户定的新规矩见文件头。"""
    en = is_en() if en is None else en
    mods, uncapped = data_mods()
    play = play_items()
    hard = data_harder()
    others = len([k for k in play if k != "ghost_town"])
    words = []
    if "ghost_town" in play:
        words.append(word("ghost_town", en) + (f" +{others}" if others else ""))
    elif others:
        words.append(f"{word('modes', en)} +{others}")
    if hard:
        words.append(word("inferno", en))
    trial = [word("pg", en)] + ([word("inferno", en)] if hard else [])
    full, tfull = SEP.join(words), SEP.join(trial)
    tag = TAG_HEX if (play or mods or uncapped or own_hex()) else TAG_BOX
    return {"full": full, "short": full, "tfull": tfull, "tshort": tfull, "tag": tag, "ttag": TAG_HEX}


def name_first():
    """房间名里名字放前面吗（「昵称」页的选项，存在 hellbox_options 的 room_order）。读不到就照原来 [HellBox] 在前。"""
    try:
        import hellbox_options
        return hellbox_options.load().get("room_order") == "name"
    except Exception:
        return False


def text(en=None):
    d = describe(en)
    return ("HBROOM1\n" + "".join(f"{k}={d[k]}\n" for k in ("full", "short", "tfull", "tshort", "tag", "ttag"))
            + "order=" + ("name" if name_first() else "tag") + "\n")


def refresh(en=None):
    """把现在的描述写给游戏（内容变了才写）。任何出错都不影响调用的人。返回写没写。"""
    try:
        new = text(en)
        if _read(FILE) == new:
            return False
        os.makedirs(HB_DIR, exist_ok=True)
        tmp = FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        os.replace(tmp, FILE)
        return True
    except (OSError, ImportError, ValueError, TypeError):
        return False


# ---------------------------------------------------------------- 拼房间名（和 mod/src/room_name.lua 的 compose 一样）
def _cut(s, limit):
    """按整个字切到 limit 字节以内。"""
    while len(s.encode("utf-8")) > limit:
        s = s[:-1]
    return s


def compose(base, full, short, max_bytes=MAX_BYTES, name_first=False, tag=TAG_BOX):
    tag = TAG_HEX if tag == TAG_HEX else TAG_BOX

    def head(d):
        return f"[{tag}{SEP}{d}]" if d else f"[{tag}]"

    def size(s):
        return len(s.encode("utf-8"))

    def join(h, b):
        if not b:
            return h
        return f"{b} {h}" if name_first else f"{h} {b}"
    for d in (full, short):
        h = head(d)
        if size(h) + 1 + size(base) <= max_bytes:
            return join(h, base)
    h = head(short)
    if size(h) + 1 + size(ELLIPSIS) >= max_bytes:  # 简写本身就太长（不会发生）：只留 [HellBox] / [Hex]
        return f"[{tag}]"
    room = max_bytes - size(h) - 1 - size(ELLIPSIS)
    return join(h, f"{_cut(base, room)}{ELLIPSIS}")


def preview(base, en=None, trial=False):
    """界面上预览：现在房间名会显示成什么。base = 名字（空 = 我的名字，再空 = 占位的「Steam 昵称」）。
    trial = 游戏说下一局 / 这一局是试验场（play-status 的 armed / used）。"""
    en = is_en() if en is None else en
    name = (base or "").strip() or (build_self_name() or ("Steam name" if en else "Steam 昵称"))
    d = describe(en)
    return compose(name, d["tfull" if trial else "full"], d["tshort" if trial else "short"], name_first=name_first(),
                   tag=d["ttag" if trial else "tag"])


def build_self_name():
    try:
        import build
        return (build.get_self_name() or "").strip()
    except Exception:  # noqa: BLE001 单独跑时没有 build
        return ""


# ---------------------------------------------------------------- 现在的房间名（2026-11-18 V0.97 整理第 2 批）
# 游戏当房主时把实际写进房间的完整名字回报到 room-status.txt（mod/src/room_name.lua）：
#   HBROOMST1 / role=host|guest|none / name=整个房间名（只有 host 有）/ t=写的时间（os.time）
# 游戏开着时每 10 秒左右刷一次；文件超过 STALE_SECONDS 没刷新 = 游戏脚本不在了（换回原版 / 崩了），不能当真名。
STATUS_FILE = os.path.join(HB_DIR, "room-status.txt")
STALE_SECONDS = 30


def read_status(now=None):
    """游戏回报的 {"role", "name"}；没有 / 文件头不对 / 读不出来 / 太旧 = {}。"""
    try:
        with open(STATUS_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
        mtime = os.path.getmtime(STATUS_FILE)
    except (OSError, ValueError):
        return {}
    if not lines or lines[0] != "HBROOMST1":
        return {}
    st = dict(line.split("=", 1) for line in lines[1:] if "=" in line)
    if st.get("role") not in ("host", "guest", "none"):
        return {}
    try:
        stamp = float(st["t"])
    except (KeyError, ValueError):
        stamp = mtime  # 没有 t 行（旧格式）：用文件修改时间
    if (time.time() if now is None else now) - stamp > STALE_SECONDS:
        return {}
    return st


def _same_as_now(real, en, trial):
    """游戏写的真名和现在这套设置算出来的一致吗：把真名里「] 」后面的名字部分拿出来，按现在的描述重新拼一遍比较。
    （名字部分是游戏那边的，可能是 Steam 昵称，桌面这边不知道，所以只比方括号那一段加长度规矩。）"""
    first = name_first()
    if first:  # 「名字 [HellBox …]」：名字是最后一个「[HellBox」/「[Hex」前面那段
        i = max(real.rfind("[" + TAG_BOX), real.rfind("[" + TAG_HEX))
        if i < 0 or not real.endswith("]"):
            return False
        rest = real[:i]
        rest = rest[:-1] if rest.endswith(" ") else rest
    else:
        if not (real.startswith("[" + TAG_BOX) or real.startswith("[" + TAG_HEX)):
            return False
        i = real.find("]")
        if i < 0:
            return False
        rest = real[i + 1:]
        rest = rest[1:] if rest.startswith(" ") else rest
    d = describe(en)
    k = "t" if trial else ""
    return compose(rest, d[k + "full"], d[k + "short"], name_first=first, tag=d[k + "tag"]) == real


def current(base, running, trial=False, en=None):
    """玩法页 / 昵称页「现在的房间名」那一行：返回 (房间名, 说明键)。
    说明键：real = 游戏里实际的；real_new = 游戏里是这个，但和现在设置不一样，几秒内会更新；
    preview = 预览（游戏没开 / 不在房间 / 读不到）；guest = 你在别人房间里（房间名是房主的），这时显示的名字是预览。"""
    en = is_en() if en is None else en
    st = read_status() if running else {}
    role = st.get("role")
    if role == "host" and st.get("name"):
        real = st["name"]
        return real, ("real" if _same_as_now(real, en, trial) else "real_new")
    return preview(base, en, trial), ("guest" if role == "guest" else "preview")


NOTES = {
    "real": "游戏里实际的",
    "real_new": "游戏里实际的，设置刚改过，几秒内会更新",
    "preview": "预览：你当房主时会是这样",
    "guest": "预览：你现在在别人房间里，房间名是房主的",
}
