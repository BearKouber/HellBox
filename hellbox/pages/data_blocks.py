"""「数据修改」页的存档和写给游戏的文件（2026-11-14 V0.91，用户定）。

存档 mod/data_blocks.json：
  {"version": 1, "seq": 写过几次,
   "blocks": {类型: [8 格，空格 null，一格 = {"name": 名字, "data": 块的数据}]},
   "live": {类型: 放在右边「当前对局数据」里的是第几格（0～7），null = 原版}}
类型：player 潜兵（2026-11-15 加）、enemy 怪物属性、spawn 出怪逻辑、weapon 武器属性、strat_blue/red/green/vehicle/yellow 战备属性（2026-11-14 全部能用）。

写给游戏：%APPDATA%/Arrowhead/Helldivers/hellbox/data-live.txt（格式见 mod/src/data_live.lua），游戏每秒读一次；
游戏处理完写回 data-live-ack.txt（seq、在哪、阵营、两边的结果）。
"""
import copy
import json
import os
from pathlib import Path

import paths
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

COUNT = 8
FILE = Path(paths.MOD) / "data_blocks.json"
GAME_DIR = Path(os.environ.get("APPDATA", "")) / "Arrowhead" / "Helldivers" / "hellbox"
LIVE = GAME_DIR / "data-live.txt"
ACK = GAME_DIR / "data-live-ack.txt"
RACES = ("bugs", "cyborgs", "illuminates")
STRAT_CATS = ("blue", "red", "green", "vehicle", "yellow")

# (类型, 名字, 颜色, 做好了没有)
TYPES = [
    ("player", "绝地潜兵", "#8fd3c1", True),  # 2026-11-15 用户要：数据里加上潜兵自己的数据
    ("enemy", "怪物属性", "#c3a6e0", True),
    ("spawn", "出怪逻辑", "#e3b38c", True),
    ("weapon", "武器属性", "#a9bccf", True),
    ("strat_blue", "战略配备 · 蓝", "#7fa8e0", True),
    ("strat_red", "战略配备 · 红", "#ec7a60", True),
    ("strat_green", "战略配备 · 绿", "#86c98f", True),
    ("strat_vehicle", "战略配备 · 车辆", "#b5ada0", True),
    ("strat_yellow", "战略配备 · 黄", "#f6d469", True),
]
TYPE_NAME = {t: n for t, n, _c, _r in TYPES}
TYPE_COLOR = {t: c for t, _n, c, _r in TYPES}
READY = {t for t, _n, _c, r in TYPES if r}

# 2026-11-18 V0.98 用户定：发行测试版的「数据」页只留怪物属性和出怪逻辑（其它会影响玩家体验）。
# 1.0 打两份：带全部数据的、不带的。带全部 = mod 文件夹里放一个空文件 data_full（make_exe 以后按版本放）。
# 存档里别的类型的块和滑条照样留着（不删玩家的东西），只是不显示、不写给游戏（写给游戏的一律原版）。
FULL = os.path.isfile(os.path.join(paths.MOD, "data_full"))
OPEN_KINDS = {t for t, *_ in TYPES} if FULL else {"enemy", "spawn"}
OPEN_GROUPS = {"player", "enemy", "weapon", "strat"} if FULL else {"enemy"}  # 普通模式的滑条卡（敌人卡里含出怪那几条）
SHOWN = [t for t in TYPES if t[0] in OPEN_KINDS]


# ---------------------------------------------------------------- 普通模式的滑条（2026-11-15 新界面）
# 不开开发者模式时，数据页就是一页滑条：全局倍数，叠在开发者模式放进去的块上面（两边都设了就相乘）。
# (键, 名字, 档位, 原版那档, 改的东西, 说明)；改的东西：enemy/weapon/strat = 「所有怪 / 全部武器 / 全部战备」的路径或组，
# spawn.count = 三条来源里还是原版的都换成「倍数」，spawn.spread = 出生时散开（块里没设时）。
# 2026-11-16 用户定：场上上限不让手填，游戏那边自动（spawn_rules.lua 自动上限），以前存的 spawn.cap 不再用。
# 2026-11-18 V0.96 用户改主意：上限写出来。spawn.limit = 场上上限滑条：16（原版）～300，最右边隔开的 -1 =「破限」
#   （自动、最多 1000）。用新键名，免得以前存的 spawn.cap 又生效。
CAP_VALUES = tuple(range(16, 301, 4)) + (-1,)
MULT_BIG = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0)
MULT_MID = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
MULT_SPEED = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
PLAYER_SPEED = ["character_info.move_speed_jog", "character_info.move_speed_sprint_min",
                "character_info.move_speed_sprint_max", "character_info.move_speed_aim", "character_info.move_speed_carry",
                "character_info.move_speed_crawl"]
GOD_LABEL = {0: "关", 1: "加血无敌", 2: "真无敌"}
GOD_KEY = {0: "off", 1: "heal", 2: "true"}
SPREAD_LABEL = {0: "原版", 1: "小", 2: "中", 3: "大"}
SIMPLE = [
    ("player", "绝地潜兵", "#8fd3c1", "你自己（和本机 2P），联机时只管自己", [
        ("player.god", "无敌", (0, 1, 2), 0, ("player", "god"),
         "加血无敌：掉血马上补满、倒地马上站起来，但一下打掉太多血（重炮、自己的空袭）还是会死。"
         "真无敌：完全不掉血，掉出地图除外。只管你和本机 2P。"),
        ("player.hp", "血量", MULT_BIG, 1.0, ("player", ["health_info.health"]), "你的血条有多长，按原版 100 乘。"),
        ("player.speed", "移动速度", MULT_SPEED, 1.0, ("player", PLAYER_SPEED), "跑步、冲刺、瞄准、扛东西、匍匐一起按倍数乘。"),
        ("player.stamina", "冲刺体力", MULT_BIG, 1.0, ("player", ["character_info.sprint_stamina"]),
         "能一口气冲刺多久，按原版 5 秒乘。"),
    ]),
    ("enemy", "敌人", "#ec7a60", "三个种族一起改", [
        ("enemy.hp", "血量", MULT_BIG, 1.0, ("enemy", ["health_info.health"]),
         "所有敌人的生命值，按每只自己的原版数值乘。"),
        ("enemy.armor", "装甲", MULT_BIG, 1.0, ("enemy", ["health_info.armor_max", "health_info.armor_min"]),
         "正面、背面装甲一起按倍数乘。装甲高了，小口径打不动。"),
        ("enemy.speed", "移动速度", MULT_SPEED, 1.0, ("enemy", ["enemy_info.movement_speed"]), "敌人跑得多快。"),
        ("enemy.damage", "攻击伤害", MULT_BIG, 1.0, ("enemy", ["melee_info.power", "weapon_info.power"]),
         "近战和武器伤害一起按倍数乘。"),
        ("spawn.count", "敌人数量", (1, 2, 3, 4, 5), 1, ("spawn", "count"),
         "报复关每一波、每次警报、每支巡逻队来的怪按倍数多出。倍数开大时把下面的「场上上限」也拉大，"
         "不然超过上限的会拆成小包一点一点补。"),
        ("spawn.limit", "场上上限", CAP_VALUES, 16, ("spawn", "limit"),
         "场上同时最多几只敌人（活的和没消失的尸体一起算）。16 是游戏原版。往右拖 = 固定这么多：改过的报复关 / 警报"
         "按这个数整包下，比它大的拆成几包陆续来。最右边隔开的红格「破限」= 不设固定数，按每一波自动放开，最多 1000 只；"
         "几百只同时在场可能会卡。只有房主的设置管用。"),
        ("spawn.spread", "出生时散开", (0, 1, 2, 3), 0, ("spawn", "spread"),
         "一捆怪刷出来时站得多开。原版挤在中心几米内，几捆叠在一起；小 / 中 / 大 越来越开。"),
    ]),
    ("weapon", "武器", "#f6d469", "主武器、副武器、支援武器一起改", [
        ("weapon.damage", "伤害", MULT_BIG, 1.0, ("weapon", ["damage"]), "子弹、激光、电弧、爆炸伤害一起按倍数乘。"),
        ("weapon.firerate", "射速", MULT_MID, 1.0, ("weapon", ["firerate"]), "每分钟打多少发。"),
        ("weapon.magazine", "弹匣容量", MULT_BIG, 1.0, ("weapon", ["magazine"]), "一个弹匣装多少发。"),
        ("weapon.reserve", "备用弹匣", MULT_BIG, 1.0, ("weapon", ["reserve"]), "带多少个备用弹匣。原版是 0 的还是 0。"),
        ("weapon.reload", "换弹时间", MULT_MID, 1.0, ("weapon", ["reload"]), "换弹要多久。倍数小 = 换得快。"),
    ]),
    ("strat", "战略配备", "#86c98f", "所有战略配备一起改", [
        ("strat.cooldown", "冷却时间", MULT_MID, 1.0, ("strat", ["cooldown_time"]),
         "叫完一次要等多久才能再叫。倍数小 = 等得短。"),
        ("strat.activation", "呼叫时间", MULT_MID, 1.0, ("strat", ["activation_time"]), "信标落地到东西下来要多久。"),
        ("strat.uses", "使用次数", MULT_BIG, 1.0, ("strat", ["num_uses"]),
         "有次数限制的战略配备每局能叫几次。没有次数限制的不受影响。"),
    ]),
]
SIMPLE_ROWS = {r[0]: r for _g, _t, _c, _n, rows in SIMPLE for r in rows}
SIMPLE_SHOWN = [g for g in SIMPLE if g[0] in OPEN_GROUPS]
if not FULL:  # 只剩敌人这张卡时拆成两张，名字和开发者模式的两类一样
    _er = next(g[4] for g in SIMPLE if g[0] == "enemy")
    SIMPLE_SHOWN = [("enemy", "怪物属性", TYPE_COLOR["enemy"], "三个种族一起改", [r for r in _er if r[0].startswith("enemy.")]),
                    ("spawn", "出怪逻辑", TYPE_COLOR["spawn"], "三个种族一起改", [r for r in _er if r[0].startswith("spawn.")])]
SHOWN_ROWS = {r[0] for _g, _t, _c, _n, rows in SIMPLE_SHOWN for r in rows}


# 2026-11-18 V0.99 用户要：普通模式「出怪逻辑」下面加一块坦克屁股出兵（有人不喜欢复杂的），和开发者模式出怪逻辑里的
# 「载具 / 首领放兵」一样：方式（原版 / 只出选中 / 不出）、勾放哪些怪、每次放几只。只管生化人（步兵战车只有生化人有）。
# 存在 data["veh"] = {"mode": ..., "sel": {怪路径: 1}, "count": 0 = 原版 / 1～50}
VEH_RACE = "cyborgs"
VEH_MODES = ("vanilla", "only", "none")


def clean_veh(v):
    v = v if isinstance(v, dict) else {}
    mode = v.get("mode") if v.get("mode") in VEH_MODES else "vanilla"
    sel = {k: 1 for k in (v.get("sel") or {}) if isinstance(k, str) and k.startswith("characters/")}
    try:
        count = int(v.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    return {"mode": mode, "sel": sel, "count": count if 1 <= count <= 50 else 0}


def simple_veh(data):
    """普通模式坦克屁股要发给游戏的那份（没改 = None）。「只出选中」一只没勾当原版。"""
    v = clean_veh(data.get("veh"))
    if v["mode"] == "only" and not v["sel"]:
        v["mode"] = "vanilla"
    if v["mode"] == "none":
        v["count"] = 0
    if v["mode"] == "vanilla" and not v["count"]:
        return None
    return v


def shown_simple(data):
    """普通模式里现在这版能看到、会生效的滑条值。"""
    return {k: v for k, v in (data.get("simple") or {}).items() if k in SHOWN_ROWS}


def effective(data):
    """写给游戏用的那份：这版没开放的类型当原版（块不放、滑条不算）。"""
    out = dict(data)
    out["live"] = {k: (v if k in OPEN_KINDS else None) for k, v in (data.get("live") or {}).items()}
    out["simple"] = shown_simple(data)
    out["veh"] = clean_veh(data.get("veh"))
    return out


def blank():
    return {"version": 1, "seq": 0, "blocks": {t: [None] * COUNT for t, *_ in TYPES},
            "live": {t: None for t, *_ in TYPES}, "simple": {}, "veh": clean_veh(None)}


def load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    out = blank()
    if not isinstance(data, dict):
        return out
    out["seq"] = int(data.get("seq") or 0)
    for t, *_ in TYPES:
        cells = (data.get("blocks") or {}).get(t)
        if isinstance(cells, list):
            cells = [c if isinstance(c, dict) and isinstance(c.get("name"), str) else None for c in cells[:COUNT]]
            out["blocks"][t] = cells + [None] * (COUNT - len(cells))
        live = (data.get("live") or {}).get(t)
        if isinstance(live, int) and 0 <= live < COUNT and out["blocks"][t][live]:
            out["live"][t] = live
    for key, val in (data.get("simple") or {}).items():
        row = SIMPLE_ROWS.get(key)
        if row and isinstance(val, (int, float)) and val in row[2] and val != row[3]:
            out["simple"][key] = val
    out["veh"] = clean_veh(data.get("veh"))
    return out


def simple_adds(data, group):
    """普通模式里某一类（enemy / weapon / strat）要乘的 {路径或组: 倍数}。"""
    out = {}
    for key, val in (data.get("simple") or {}).items():
        row = SIMPLE_ROWS.get(key)
        if row and row[4][0] == group and isinstance(row[4][1], list):
            for path in row[4][1]:
                out[path] = out.get(path, 1.0) * float(val)
    return out


def _with_common(d, adds):
    """块的数据 + 普通模式的倍数（相乘）。"""
    d = copy.deepcopy(d or {})
    if adds:
        common = dict(d.get("common") or {})
        for path, m in adds.items():
            common[path] = float(common.get(path, 1.0)) * m
        d["common"] = common
    return d


def _with_spawn(rd, data, race=None):
    """一个阵营的出怪数据 + 普通模式的「敌人数量」「出生时散开」：块里还是原版的来源才换成倍数；块里没设散开才用这里的。"""
    simple = data.get("simple") or {}
    count, spread = int(simple.get("spawn.count") or 1), int(simple.get("spawn.spread") or 0)
    limit = int(simple.get("spawn.limit") or 16)
    rd = copy.deepcopy(rd or {})
    if limit != 16 and not rd.get("cap"):  # 块里没设上限才用滑条的
        rd["cap"] = limit
    sv = simple_veh(data)
    if race == VEH_RACE and sv:  # 普通模式的坦克屁股：块里的载具放兵还是原版才用这里的
        veh = rd.get("veh") or {}
        if (veh.get("mode") or "vanilla") == "vanilla" and not int(veh.get("count") or 0):
            rd["veh"] = copy.deepcopy(sv)
    if count <= 1 and not spread:
        return rd
    src = rd.setdefault("src", {})
    for s in ("g", "a", "p"):
        e = src.setdefault(s, {})
        if count > 1 and (e.get("mode") or "vanilla") == "vanilla":
            e["mode"], e["mult"] = "mult", count
    if spread and not rd.get("spread"):
        rd["spread"] = spread
    return rd


def simple_summary(data):
    """普通模式改了哪些（开发者模式里提示用）。"""
    parts = []
    for key, val in shown_simple(data).items():
        row = SIMPLE_ROWS.get(key)
        if row:
            parts.append(T("{0} {1}", tr(row[1]), simple_label(row, val)))
    sv = simple_veh(data)
    if sv:
        parts.append(tr("坦克屁股出兵改过"))
    return tr("、").join(parts)


def simple_label(row, val, mark="（原版）"):
    """滑条上显示的值（已翻译）。mark = 等于原版时后面加的字。"""
    if row[0] == "player.god":
        base = tr(GOD_LABEL.get(int(val), "关"))
    elif row[0] == "spawn.limit":
        if int(val) < 0:
            return tr("破限 ⚠")
        base = T("{0} 只", int(val))
    elif row[0] == "spawn.spread":
        base = tr(SPREAD_LABEL.get(int(val), "原版"))
        mark = "" if val == row[3] else mark
    else:
        base = f"×{val:g}"
    return base + (tr(mark) if val == row[3] else "")


def save(data):
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, FILE)


# ---------------------------------------------------------------- 块 -> 命令
def enemy_command(d):
    """怪物属性块 -> enemy_params.lua 的命令。d = {"common": {路径: 倍数}, "ov": {怪名: {路径: 值}}}；
    值是文字：'*2' = 按这只怪的原值乘，其它 = 绝对值（数 / true / false / 路径）。"""
    d = d or {}
    common = ",".join(f"{p}*{float(m):g}" for p, m in sorted((d.get("common") or {}).items())
                      if abs(float(m) - 1.0) > 1e-9)
    sets = []
    for name, fields in sorted((d.get("ov") or {}).items()):
        for path, val in sorted(fields.items()):
            val = str(val)
            sets.append(f"{name}.{path}{val}" if val.startswith("*") else f"{name}.{path}={val}")
    if not common and not sets:
        return "reset"
    return f"common={common};set={','.join(sets)}"


def live_text(data):
    """当前对局数据（放进去的块 + 普通模式的滑条）-> data-live.txt 的内容。"""
    from pages import spawn  # 出怪命令的拼法在出怪编辑器那边
    lines = ["HBDATA1", f"seq={data['seq']}"]
    data = effective(data)

    def cell_data(kind):
        i = data["live"].get(kind)
        cell = data["blocks"][kind][i] if i is not None else None
        return (cell or {}).get("data") or {}

    from pages.player_editor import player_command
    pd = _with_common(cell_data("player"), simple_adds(data, "player"))
    god = GOD_KEY.get(int((data.get("simple") or {}).get("player.god") or 0), "off")
    if god != "off":  # 普通模式的无敌开着就用它，没开就照块里的
        pd["god"] = god
    lines.append("player=" + player_command(pd))
    lines.append("params=" + enemy_command(_with_common(cell_data("enemy"), simple_adds(data, "enemy"))))
    sp = cell_data("spawn")
    for race in RACES:
        rd = _with_spawn(sp.get(race), data, race)
        lines.append(f"spawn.{race}=" + (spawn.race_command(rd, race) if rd else "reset"))
    from pages.weapon_editor import weapon_command
    lines.append("weapon=" + weapon_command(_with_common(cell_data("weapon"), simple_adds(data, "weapon"))))
    from pages import strat_editor  # 战备命令的拼法在战备编辑器那边
    for c in STRAT_CATS:
        d = _with_common(cell_data("strat_" + c), simple_adds(data, "strat"))
        lines.append(f"strat.{c}=" + strat_editor.strat_command(d, c))
    return "\n".join(lines) + "\n"


def write_live(data):
    """seq 加 1，写 data-live.txt（先写临时文件再换名，游戏不会读到半截），再存档。"""
    data["seq"] = int(data.get("seq") or 0) + 1
    GAME_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LIVE.with_suffix(".tmp")
    tmp.write_text(live_text(data), encoding="utf-8")
    os.replace(tmp, LIVE)
    save(data)


def read_ack():
    """游戏写回的结果 {seq, where, race, params, spawn}；没有文件返回 {}。"""
    try:
        text = ACK.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return {}
    out = {}
    for line in text.splitlines():
        k, _, v = line.partition("=")
        if k:
            out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------- 方块上的一句话
def enemy_summary(d):
    d = d or {}
    n_common = len([m for m in (d.get("common") or {}).values() if abs(float(m) - 1.0) > 1e-9])
    n_units = len([f for f in (d.get("ov") or {}).values() if f])
    n_rows = sum(len(f) for f in (d.get("ov") or {}).values())
    parts = []
    if n_common:
        parts.append(f"全体 {n_common} 项")
    if n_units:
        parts.append(f"{n_units} 只怪 {n_rows} 项")
    return "，".join(parts) or "全原版"


def spawn_summary(d):
    from pages import spawn
    zh = {"bugs": "虫", "cyborgs": "生", "illuminates": "光"}
    parts = []
    for race in RACES:
        s = spawn.summary((d or {}).get(race))
        if s:
            parts.append(zh[race] + "：" + "/".join(s))
    return "；".join(parts) or "全原版"


def summary(kind, cell):
    if not cell:
        return ""
    if kind == "enemy":
        return enemy_summary(cell.get("data"))
    if kind == "player":
        from pages.player_editor import summary as player_summary
        return player_summary(cell.get("data"))
    if kind == "spawn":
        return spawn_summary(cell.get("data"))
    if kind == "weapon":
        from pages.weapon_editor import summary as weapon_summary
        return weapon_summary(cell.get("data"))
    if kind.startswith("strat_"):
        from pages import strat_editor
        return strat_editor.summary(cell.get("data"))
    return ""
