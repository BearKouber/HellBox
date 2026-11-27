"""
「玩法」页的数据：训练场的目标、装备规则、场上事件，哪些组合游戏不允许，以及和游戏之间的通信格式。
"""
import json
import os
import random
import uuid

import paths
import safe_write

HB_DIR = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox")
PLAY = os.path.join(HB_DIR, "play.txt")
STATUS = os.path.join(HB_DIR, "play-status.txt")

CHALLENGES = [
    ("exterminate_determined_by_enemy", "歼灭", "把指定的敌人清掉。"),
    ("survivors", "护送幸存者", "把幸存者带到撤离点。"),
    ("activate_sam_site", "启动防空装置", "启动地图上的防空导弹站。"),
    ("active_and_defend_launchpad", "防守火箭发射台", "启动发射台并守到发射。"),
    ("undetonated_shells", "拆除哑弹", "找到没爆的炮弹拆掉。"),
    ("assasinate_determined_by_enemy", "暗杀", "干掉指定的目标。"),
    ("secure_flagpost", "升旗", "占住旗杆守一段时间。"),
    ("single_point_fortify", "报复", "守一个点打一波波敌人，像报复关。只有困难难度能选。"),
]

CONDITIONS = [
    ("reload_surprise", "weapon_expertise", "换弹惊喜", "每次换弹，手里的枪随机换成另一把。", "self"),
    ("random_weapons", "weapon_expertise", "随机武器", "主武器和副武器随机。", None),
    ("pistols_only", "weapon_expertise", "只用手枪", "无主武器，副武器随机。", None),
    ("anti_tank_pistols_only", "weapon_expertise", "手枪+反坦克", "无主武器，副武器随机，战略配备随机反坦克。", None),
    ("flamethrower_or_tox_avenger", "weapon_expertise", "喷火 / 喷毒", "主武器是喷火器，战略配备是喷火器或杀虫剂。", None),
    ("double_barrel_and_grenades", "weapon_expertise", "双管+手雷", "双管，无副武器，手雷天赋，战略配备地雷。", None),
    ("support_weapons_strats_only", "weapon_expertise", "只有支援武器", "无主武器，副武器和天赋随机，战略配备随机支援武器。", None),
    ("community_favorites", "weapon_expertise", "社区最爱", "从几套社区经典武装配置里随机一套。", None),
    ("liberty_day_veteran", "weapon_expertise", "自由日老兵", "建构+强心剂。", None),
    ("one_armed_angel", "weapon_expertise", "独臂天使", "冲锋枪 + 重甲；补给、医疗无人机、眩晕雷、地雷。", None),
    ("new_and_improved", "weapon_expertise", "新式装备", "达姆+强臂，战略配备包含护卫犬或天使。", None),
    ("no_primary", "stratagem_mastery", "没有主武器", "没有主武器。", None),
    ("defensive_strats_only", "stratagem_mastery", "只有防御战略配备", "无主武器，副武器和天赋随机，战略配备随机防御。", None),
    ("random_stratagems", "stratagem_mastery", "随机战略配备", "随机战略配备。", None),
    ("vehicles_stratagems_only", "stratagem_mastery", "只有载具", "无主武器，副武器和天赋随机，战略配备随机载具。", None),
    ("mines_and_machineguns", "stratagem_mastery", "地雷+步枪", "战略配备随机地雷，主武器为步枪或盟友。", None),
    ("nailgun_and_support_or_strike", "stratagem_mastery", "钉枪", "钉枪 + 重甲；战略配备是支援和打击类。", None),
    ("melee_only", "wildcard", "只有近战", "军刀+强臂，无副武器，战略配备无杀伤能力。", None),
]

MODIFIERS = [
    # 真试炼场：键要在游戏 ProvinggroundsSettings 的修正参数表里（军刀 sidearm_saber 不在，只在 HellBox 版有）；
    # 侦察兵在这里是游戏原版规则（跑快 40%、挨怪打翻倍），HellBox 版的心肺 + 受伤 +50% 不管真试炼场
    ("ghost_town", "鬼城", "深夜作战，只能用手电筒和无人机探照。", None),
    ("orbital_bombardments", "轨道轰炸", "隔一阵在队友身边落一发打击类战略配备。", "team"),
    ("orbital_support", "超级地球支援", "隔一阵在队友身边落一个战略配备。", "team"),
    ("emp", "电磁干扰", "每55秒遭到15秒电磁干扰。", "team"),
    ("get_ammo_from_hits_double_reload_time", "命中补给", "打中敌人回子弹，但弹匣只有一半。", None),
    ("marksman", "精确打击", "只有打中弱点才有伤害，打中加倍。", None),
    ("super_boots", "侦察兵", "跑得快 40%，挨怪打伤害翻倍。", None),
    ("what_goes_around", "以牙还牙", "你打到队友的伤害，同样打回你自己。", None),
]

# ---------------------------------------------------------------- HellBox 版的场上事件
CUSTOM_EVENTS = [
    ("drop", "超级地球支援", "隔一阵在队友身边落一个战略配备。", "team"),
    ("emp", "电磁干扰", "每55秒遭到15秒电磁干扰。", "team"),
    ("get_ammo_from_hits_double_reload_time", "命中补给", "打中敌人回子弹，但弹匣只有一半。", "self"),
    ("marksman", "精确打击", "只有打中弱点才有伤害，打中加倍。", "self"),
    ("super_boots", "侦察兵", "自带心肺加速器，但受到伤害+50%。", "self"),
    ("what_goes_around", "以牙还牙", "你打到队友的伤害，同样打回你自己。", "self"),
    ("sidearm_saber", "军刀", "把副武器替换为军刀。", "self"),
]
CUSTOM_KEYS = [e[0] for e in CUSTOM_EVENTS]
CONFLICTS = {}  # 2026-11-23：侦察兵改走 HellBox 自己的 boots_update，不再和以牙还牙抢 command_master，可以一起开

# ---------------------------------------------------------------- HellBox 版的环境
ENVS = [
    ("", "原版", "照关卡本来的时间段光照。", None),
    ("ghost_town", "鬼城", "深夜作战，只能用手电筒和无人机探照。", "self"),
]
ENV_KEYS = [e[0] for e in ENVS]

DROP_COLORS = [("red", "红色", "offensive"), ("blue", "蓝色", "supply"), ("green", "绿色", "defensive"),
               ("yellow", "黄色", "special")]
DROP_BAN = {
    "stratagem_reinforce": "增援落下来要带上扔它的人（游戏发复活消息时用），随机落的没有，可能出错。",
    "stratagem_emergency_beacon": "求救信标一落就会把房间改成公开，不让随机落。",
}
STRAT_FIELDS = os.path.join(paths.ROOT, "ai", "strat_fields.json")


def drop_pool():
    try:
        with open(STRAT_FIELDS, encoding="utf-8") as f:
            strats = json.load(f).get("strats") or {}
    except (OSError, ValueError):
        return []
    out = []
    for color, _name, typ in DROP_COLORS:
        rows = [(k, v.get("zh") or k, v.get("en") or v.get("zh") or k, v.get("cat") == "vehicle")
                for k, v in strats.items() if v.get("type") == typ]
        rows.sort(key=lambda r: r[3])
        out.append((color, rows))
    return out


def split_list(text):
    return [x for x in (text or "").replace(" ", "").split(",") if x]


UNLOCKS = os.path.join(HB_DIR, "strat-unlocks.txt")


def read_unlocks():
    try:
        with open(UNLOCKS, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "HBUNLK1":
        return None
    for line in lines[1:]:
        if line.startswith("on="):
            return set(split_list(line[3:]))
    return None


RACES = [("bugs", "虫族"), ("cyborgs", "生化人"), ("illuminates", "光能者")]
TIMES = [("dawn", "黎明"), ("day", "白天"), ("dusk", "黄昏"), ("night", "夜晚")]
DIFFS = [("1", "简单"), ("2", "中等"), ("3", "困难")]
TERRAINS = 214

DIFF_BLACK = {"1": {"single_point_fortify"}, "2": {"single_point_fortify"},
              "3": {"pistols_only", "wildcard", "melee_only"}}
CHAL_BLACK = {
    "exterminate_determined_by_enemy": {"random_stratagems"},
    "active_and_defend_launchpad": {"orbital_bombardments", "orbital_support"},
    "assasinate_determined_by_enemy": {"melee_only", "pistols_only", "random_stratagems", "one_armed_angel"},
    "single_point_fortify": {"melee_only", "what_goes_around"},
}
COND_BLACK = {
    "flamethrower_or_tox_avenger": {"marksman"},
    "support_weapons_strats_only": {"marksman"},
    "melee_only": {"get_ammo_from_hits_double_reload_time", "marksman"},
}
COND_GROUP = {c[0]: c[1] for c in CONDITIONS}
NAMES = {**{c[0]: c[1] for c in CHALLENGES}, **{c[0]: c[2] for c in CONDITIONS}, **{m[0]: m[1] for m in MODIFIERS}, **{e[0]: e[1] for e in CUSTOM_EVENTS},
         "weapon_expertise": "武器类规则", "stratagem_mastery": "战略配备类规则", "wildcard": "近战规则"}
DIFF_NAMES = dict(DIFFS)


def blocked(diff, chal, cond, mod):
    sources = [(DIFF_BLACK.get(diff, set()), f"{DIFF_NAMES.get(diff, diff)}难度"),
               (CHAL_BLACK.get(chal, set()), NAMES.get(chal, chal)),
               (COND_BLACK.get(cond, set()), NAMES.get(cond, cond))]
    for names, who in sources:
        for item in (chal, cond, COND_GROUP.get(cond), mod):
            if item and item in names:
                return item, who
    return None


DEFAULT = {"custom": "0", "follow": "1", "cond": "reload_surprise", "event": "drop", "drop": "", "env": "", "trial": "",
           "race": "bugs", "tod": "night", "diff": "1", "chal": "exterminate_determined_by_enemy",
           "pcond": "reload_surprise", "pmod": "ghost_town", "terrain": ""}
ORDER = ["custom", "follow", "cond", "event", "drop", "env", "trial", "race", "tod", "diff", "chal", "pcond", "pmod", "terrain"]


def _migrate_events(cfg):
    evs = split_list(cfg.get("event"))
    drops = split_list(cfg.get("drop"))
    pool = {c: rows for c, rows in drop_pool()}
    if "orbital_bombardments" in evs:
        drops += [r[0] for r in pool.get("red", [])]
    if "orbital_support" in evs:
        drops += [r[0] for r in pool.get("blue", []) if not r[3] and r[0] != "stratagem_resupply"]
    if ("orbital_bombardments" in evs or "orbital_support" in evs) and "drop" not in evs:
        evs.append("drop")
    if not drops and "drop" not in (cfg.get("drop_seen") or ""):
        drops = [r[0] for r in pool.get("red", [])]
    evs = [e for e in CUSTOM_KEYS if e in evs]
    for a, b in CONFLICTS.items():
        if a in evs and b in evs:
            evs.remove(b)
    cfg["event"] = ",".join(evs)
    cfg["drop"] = ",".join(dict.fromkeys(d for d in drops if d not in DROP_BAN))


def load():
    cfg = dict(DEFAULT)
    try:
        with open(PLAY, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = ""
    if text.startswith("HBPLAY1"):
        for line in text.splitlines()[1:]:
            k, _, v = line.partition("=")
            if k in cfg:
                cfg[k] = v.strip()
    try:
        idx = int(cfg["terrain"]) // 10000000
    except ValueError:
        idx = random.randrange(TERRAINS)
    cfg["terrain"] = str(max(0, min(TERRAINS - 1, idx)) * 10000000)
    if cfg["env"] not in ENV_KEYS:
        cfg["env"] = ""
    if cfg["pmod"] not in [m[0] for m in MODIFIERS]:
        cfg["pmod"] = DEFAULT["pmod"]
    had_drop_line = "\ndrop=" in text
    if not had_drop_line:
        _migrate_events(cfg)
    else:
        cfg["drop_seen"] = "drop"
        _migrate_events(cfg)
        cfg.pop("drop_seen", None)
    return cfg


def save(cfg):
    os.makedirs(HB_DIR, exist_ok=True)
    text = "HBPLAY1\n" + "".join(f"{k}={cfg.get(k, '')}\n" for k in ORDER)
    safe_write.write_text(PLAY, text)


def new_trial_id():
    return uuid.uuid4().hex[:10]


def read_status():
    try:
        with open(STATUS, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return {}
    if not lines or lines[0] != "HBPLAYST1":
        return {}
    return dict(line.split("=", 1) for line in lines[1:] if "=" in line)


def parse_host(raw):
    parts = (raw or "").split("|")
    if len(parts) < 5 or parts[0] != "1":
        return None
    return {"custom": parts[1] == "1", "cond": parts[2] if parts[2] == "reload_surprise" else "",
            "events": [e for e in CUSTOM_KEYS if e in split_list(parts[3])],
            "env": parts[4] if parts[4] in ENV_KEYS else ""}
