"""
「玩法 → HellBox 版」的「我的玩法」：把配装块、场上事件、随机掉落、环境、换弹惊喜存成一个玩法，存在 mod/my_plays.json。
"""
import json
import os

import paths
from pages import host_loadout as hl
from pages import play_modes as pm

FILE = os.path.join(paths.MOD, "my_plays.json")
MAX = 20


def empty(name=""):
    return {"name": name, "slots": {k: "" for k in hl.SLOTS}, "names": {k: "" for k in hl.SLOTS},
            "events": [], "drop": [], "env": "", "surprise": False}


def clean(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("name"), str) or not raw["name"].strip():
        return None
    p = empty(raw["name"].strip())
    lo = raw.get("loadout") if isinstance(raw.get("loadout"), dict) else {}
    slots = lo.get("slots") if isinstance(lo.get("slots"), dict) else {}
    names = lo.get("names") if isinstance(lo.get("names"), dict) else {}
    for k in hl.SLOTS:
        v = slots.get(k)
        p["slots"][k] = v.strip() if isinstance(v, str) else ""
        n = names.get(k)
        p["names"][k] = n if isinstance(n, str) and hl.mode_of(p["slots"][k]) == "fixed" else ""
    evs = raw.get("events") if isinstance(raw.get("events"), list) else []
    evs = [e for e in pm.CUSTOM_KEYS if e in evs]
    for a, b in pm.CONFLICTS.items():
        if a in evs and b in evs:
            evs.remove(b)
    p["events"] = evs
    drop = raw.get("drop") if isinstance(raw.get("drop"), list) else []
    known = {r[0] for _c, rows in pm.drop_pool() for r in rows}
    p["drop"] = list(dict.fromkeys(d for d in drop if isinstance(d, str) and d not in pm.DROP_BAN and (not known or d in known)))
    env = raw.get("env")
    p["env"] = env if isinstance(env, str) and env in pm.ENV_KEYS else ""
    p["surprise"] = raw.get("surprise") is True
    return p


def load(path=None):
    try:
        with open(path or FILE, encoding="utf-8") as f:
            d = json.load(f)
        out = [p for p in (clean(r) for r in d.get("plays") or []) if p]
        return out[:MAX]
    except (OSError, ValueError, TypeError, AttributeError):
        return []


def save(plays, path=None):
    path = path or FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = [{"name": p["name"], "loadout": {"slots": p["slots"], "names": p["names"]}, "events": p["events"],
             "drop": p["drop"], "env": p["env"], "surprise": p["surprise"]} for p in plays[:MAX]]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"version": 1, "plays": rows}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def key_of(p):
    return (tuple(p["slots"][k] for k in hl.SLOTS), tuple(p["events"]), tuple(sorted(p["drop"])), p["env"], bool(p["surprise"]))
