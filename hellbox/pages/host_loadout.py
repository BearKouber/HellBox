"""
「玩法」页的配装块：房主为六格各选固定 / 自由 / 随机，可存成块，存在 mod/loadout_blocks.json。
"""
import json
import os

import paths

HB_DIR = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox")
RULE = os.path.join(HB_DIR, "host-loadout.txt")
STATUS = os.path.join(HB_DIR, "host-loadout-status.txt")
ITEMS = os.path.join(HB_DIR, "loadout-items.json")
BUILTIN = os.path.join(paths.ROOT, "ai", "loadout_items.json")

SLOTS = ("perk", "primary", "s5", "s6", "s7", "s8")
RANDOM = "?"
BLOCKS = os.path.join(paths.MOD, "loadout_blocks.json")
BLOCK_MAX = 20
STATIC = {"stratagem_metaldetector", "stratagem_hellbomb", "stratagem_emergency_beacon", "stratagem_reinforce"}


def default():
    return {"on": "0", **{k: "" for k in SLOTS}, **{"name." + k: "" for k in SLOTS}}


def load():
    cfg = default()
    try:
        with open(RULE, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return cfg
    if text.startswith("HBLO1"):
        for line in text.splitlines()[1:]:
            k, _, v = line.partition("=")
            if k in cfg:
                cfg[k] = v.strip()
    return cfg


def save(cfg):
    os.makedirs(HB_DIR, exist_ok=True)
    keys = ["on", *SLOTS, *("name." + k for k in SLOTS)]
    text = "HBLO1\n" + "".join(f"{k}={cfg.get(k, '')}\n" for k in keys)
    tmp = RULE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, RULE)


def locked_count(cfg):
    return sum(1 for k in SLOTS if cfg.get(k))


def counts(values):
    vals = list(values)
    return sum(1 for v in vals if v and v != RANDOM), sum(1 for v in vals if v == RANDOM)


def mode_of(value):
    return "random" if value == RANDOM else "fixed" if value else "free"


# ---------------------------------------------------------------- 存好的配装块
def load_blocks():
    try:
        with open(BLOCKS, encoding="utf-8") as f:
            d = json.load(f)
        out = []
        for b in d.get("blocks") or []:
            if isinstance(b, dict) and isinstance(b.get("name"), str) and b["name"].strip():
                slots = b.get("slots") or {}
                out.append({"name": b["name"].strip(), "slots": {k: str(slots.get(k) or "") for k in SLOTS},
                            "names": {k: str((b.get("names") or {}).get(k) or "") for k in SLOTS}})
        return out[:BLOCK_MAX]
    except (OSError, ValueError, TypeError, AttributeError):
        return []


def save_blocks(blocks):
    os.makedirs(os.path.dirname(BLOCKS), exist_ok=True)
    tmp = BLOCKS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "blocks": blocks[:BLOCK_MAX]}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, BLOCKS)


def read_status():
    try:
        with open(STATUS, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return {}
    return dict(line.split("=", 1) for line in lines if "=" in line)


def items_from_feed(st):
    def pairs(rows, skip=()):
        return [(r["key"], r["name"]) for r in rows if r["key"] and r["key"] not in skip]
    return {"perk": pairs(st.get("perks") or []), "primary": pairs(st.get("weapons") or []),
            "strat": pairs(st.get("strats") or [], STATIC), "loadout": st.get("loadout")}


def save_items(items):
    if not (items["perk"] and items["primary"] and items["strat"]):
        return
    os.makedirs(HB_DIR, exist_ok=True)
    tmp = ITEMS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    os.replace(tmp, ITEMS)


def builtin_items():
    try:
        with open(BUILTIN, encoding="utf-8") as f:
            d = json.load(f)
        try:
            from i18n import is_en
            en = is_en()
        except ImportError:
            en = False
        out = {k: [(r[0], r[2] if en else r[1]) for r in d.get(k) or []] for k in ("perk", "primary", "strat")}
    except (OSError, ValueError, TypeError, IndexError):
        return None
    return out if all(out.values()) else None


def load_items():
    b = builtin_items()
    if b:
        return b | {"loadout": None}
    try:
        with open(ITEMS, encoding="utf-8") as f:
            d = json.load(f)
        return {k: [tuple(p) for p in d.get(k) or []] for k in ("perk", "primary", "strat")} | {"loadout": d.get("loadout")}
    except (OSError, ValueError, TypeError):
        return {"perk": [], "primary": [], "strat": [], "loadout": None}


def kind_of(slot):
    return slot if slot in ("perk", "primary") else "strat"
