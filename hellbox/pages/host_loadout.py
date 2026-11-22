"""「玩法」页的「配装块」（2026-11-18 V0.96 房主配装；V0.97 改成配装块）：房主定一套配装，每一格「固定 / 自由 / 随机」。

V0.97（2026-11-18 用户定，见 docs/任务/HD1-033-玩法页方案.md 第四节 1）：
- 每一格三选一：固定（指定一样，选装备界面照训练场那样锁住）、自由（队友照自己的）、随机（游戏自己的随机配装办法，
  每个人各抽各的，界面显示 ???）。文件里随机写成「?」。
- 可以存成块（起名字，存在 mod/loadout_blocks.json，最多 BLOCK_MAX 块），下次点一下就用；不做官方规则模板。

用户定：每一格可选锁或不锁；定的方式两种都要（一格一格挑 + 「抄我现在这套」）。
开着 HellBox 的队友进你的房间，锁住的格子只能用你定的；没装 HellBox 的人不受影响。

和游戏说话：写 %APPDATA%/Arrowhead/Helldivers/hellbox/host-loadout.txt（HBLO1，键=值：on、perk、primary、s5～s8，
空 = 自由；name.* 是显示名，游戏不看）。游戏写 host-loadout-status.txt（role=host|guest|none、rule=、api=）。
游戏那边是 mod/src/host_loadout.lua。

物品名单（天赋 / 主武器 / 战备的名字和显示名）：HellBox 自带 ai/loadout_items.json（tools/loadout_items.py 从游戏文件生成，
中英文名都有），游戏没开过也能挑（2026-11-18 用户实测：以前要等游戏开着才有名单，没开只有「自由」）。
自带名单读不到时才退回从 profile_feed（游戏里 profile_tool.lua 的状态）拿、存进 loadout-items.json 的那份。
「抄我现在这套」要的「你现在的配装」只能从游戏拿。
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
# 开局就带的四个战略配备（游戏固定在前四格，后四格不能选）
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
    """不是自由的格子数（固定 + 随机）。"""
    return sum(1 for k in SLOTS if cfg.get(k))


def counts(values):
    """六格的值 → (固定几格, 随机几格)。"""
    vals = list(values)
    return sum(1 for v in vals if v and v != RANDOM), sum(1 for v in vals if v == RANDOM)


def mode_of(value):
    return "random" if value == RANDOM else "fixed" if value else "free"


# ---------------------------------------------------------------- 存好的配装块
def load_blocks():
    """[{"name": 名字, "slots": {格子: 值}, "names": {格子: 显示名}}]"""
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
    """profile_feed.read() 的结果 → {"perk": [(key, 显示名)], "primary": [...], "strat": [...], "loadout": [6 个 key] 或 None}。"""
    def pairs(rows, skip=()):
        return [(r["key"], r["name"]) for r in rows if r["key"] and r["key"] not in skip]
    return {"perk": pairs(st.get("perks") or []), "primary": pairs(st.get("weapons") or []),
            "strat": pairs(st.get("strats") or [], STATIC), "loadout": st.get("loadout")}


def save_items(items):
    if not (items["perk"] and items["primary"] and items["strat"]):
        return  # 旧版 MOD 没有天赋名单：不覆盖
    os.makedirs(HB_DIR, exist_ok=True)
    tmp = ITEMS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    os.replace(tmp, ITEMS)


def builtin_items():
    """自带名单 {"perk": [(key, 显示名)], ...}，按当前语言取名字；读不到返回 None。"""
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
