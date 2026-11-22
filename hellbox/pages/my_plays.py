"""「玩法 → HellBox 版」的「我的玩法」（2026-11-18 V0.97 第 ④ 步）。

把配装块（六格各自固定 / 自由 / 随机 + 固定的是哪样）、场上事件（选了哪几个）、随机掉落名单、环境、换弹惊喜
合起来存成一个玩法，起名字，下次点一下全部用上（用法和配装块的「存好的块」一样）。
只存在自己电脑上（mod/my_plays.json，最多 MAX 个），不做分享、不做导入导出，不进发行包（换版本时属于个人文件）。
配装存的是六格的内容本身，不是引用「存好的块」的名字：块删了玩法照样能用。
不存各个「开启」开关：用上一个玩法时由界面把开关打开（见 play.py）。

读文件时不崩：文件坏了 / 版本旧缺字段，缺的项按默认补（事件空、掉落空、环境原版、换弹惊喜关、配装六格自由），
名字不认识的事件、战备丢掉，不能一起开的事件留前一个。
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
    """读到的一项 → 补全、去掉不认识的以后的玩法；名字不对返回 None。"""
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
    known = {r[0] for _c, rows in pm.drop_pool() for r in rows}  # 名单读不到时不筛，只去掉落不了的
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
    """用来比「现在的设置是不是这个玩法」：不含名字和各个开关。"""
    return (tuple(p["slots"][k] for k in hl.SLOTS), tuple(p["events"]), tuple(sorted(p["drop"])), p["env"], bool(p["surprise"]))
