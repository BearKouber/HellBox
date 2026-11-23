"""
房间名描述：把 HellBox 的玩法与数据修改拼成 Steam 房间名的方括号部分，格式与 mod/src/room_name.lua 一致。
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
    "saber": ("军刀", "Saber"),
    "modes": ("玩法", "Modes"),
    "inferno": ("炼狱", "Inferno"),
}
TAG_BOX, TAG_HEX = "HellBox", "Hex"
ENEMY_FIELDS = os.path.join(paths.ROOT, "ai", "enemy_fields.json")
GAME_FALLBACK = {
    "pg": ("试验场", "Proving Grounds"),
    "ghost_town": ("鬼城", "Ghost Town"),
    "emp": ("电磁脉冲", "EMP"),
    "reload": ("填弹惊喜", "Reload Surprise"),
    "ammo": ("伤害击中可提供弹药", "Damaging Hits Give Ammo"),
    "marksman": ("只在击中弱点时造成双倍伤害", "Double Damage Weak Spots Only"),
    "boots": ("侦察装甲", "Recon Armor"),
    "retaliate": ("误伤友军已反击", "Friendly Fire Is Returned"),
    "events": ("修正参数", "Modifiers"),
}
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
        mod = data.get("modifier")
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
    kv = {}
    for part in (cmd or "").split(";"):
        k, _, v = part.partition("=")
        kv[k.strip()] = v.strip()
    changed = any(kv.get(k) in ("mult", "none") for k in ("g", "a", "p"))
    changed = changed or any(kv.get(k) for k in ("gmap", "amap", "pmap"))
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
    kv = _kv(cmd)
    for mode, mult in (("g", "multg"), ("a", "mult"), ("p", "multp")):
        if kv.get(mode) == "mult" and (_num(kv.get(mult)) or 0) > 1:
            return True
    cap = _num(kv.get("cap")) or 0
    return cap == -1 or cap > 16


_enemy_defaults = None


def enemy_default(name, path):
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
    lines = {}
    for line in _read(DATA_LIVE).splitlines():
        k, _, v = line.partition("=")
        lines[k.strip()] = v.strip()
    if any(spawn_harder(v) for k, v in lines.items() if k.startswith("spawn.")):
        return True
    return enemy_harder(lines.get("params"))


def own_hex():
    on = False
    try:
        import build
        on = bool(build.get_carry_vehicle())
    except Exception:  # noqa: BLE001
        pass
    try:
        import hellbox_options
        on = on or bool(hellbox_options.load().get("drop"))
    except Exception:  # noqa: BLE001
        pass
    return on


def play_items():
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
    try:
        import hellbox_options
        return hellbox_options.load().get("room_order") == "name"
    except Exception:
        return False


def text(en=None):
    empty = str()
    d = {"full": empty, "short": empty, "tfull": empty, "tshort": empty, "tag": TAG_BOX, "ttag": TAG_BOX}
    return ("HBROOM1\n" + "".join(f"{k}={d[k]}\n" for k in ("full", "short", "tfull", "tshort", "tag", "ttag"))
            + "order=" + ("name" if name_first() else "tag") + "\n")


def refresh(en=None):
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


# ---------------------------------------------------------------- 拼房间名
def _cut(s, limit):
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
    if size(h) + 1 + size(ELLIPSIS) >= max_bytes:
        return f"[{tag}]"
    room = max_bytes - size(h) - 1 - size(ELLIPSIS)
    return join(h, f"{_cut(base, room)}{ELLIPSIS}")


def preview(base, en=None, trial=False):
    en = is_en() if en is None else en
    name = (base or "").strip() or (build_self_name() or ("Steam name" if en else "Steam 昵称"))
    return compose(name, str(), str(), name_first=name_first(), tag=TAG_BOX)


def build_self_name():
    try:
        import build
        return (build.get_self_name() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------- 现在的房间名
STATUS_FILE = os.path.join(HB_DIR, "room-status.txt")
STALE_SECONDS = 30


def read_status(now=None):
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
        stamp = mtime
    if (time.time() if now is None else now) - stamp > STALE_SECONDS:
        return {}
    return st


def _same_as_now(real, en, trial):
    first = name_first()
    if first:
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
    return compose(rest, str(), str(), name_first=first, tag=TAG_BOX) == real


def current(base, running, trial=False, en=None):
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
