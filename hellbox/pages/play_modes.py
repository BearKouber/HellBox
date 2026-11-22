"""「玩法」页的数据：训练场的目标 / 装备规则 / 场上事件，哪些组合游戏不让开，和游戏怎么说话（2026-11-16 V0.95）。

名字和效果是照游戏源码写的（mod/lua_src/lua__proving_grounds__provinggrounds_settings.lua、
provinggrounds_conditions.lua 的 construct_loadout、provinggrounds_modifiers_manager.lua）。
黑名单照 provinggrounds_settings.lua：难度、目标、装备规则三份合起来，名字（含装备规则的大类名）在里面就不能选。
游戏这边是 mod/src/hellbox_play.lua（同一份规矩它也会再查一遍）。

和游戏说话：写 %APPDATA%/Arrowhead/Helldivers/hellbox/play.txt（游戏每 0.5 秒看一次，内容变了才重读），
读 play-status.txt（游戏写：真训练场设好没有、这一关在跑什么事件）。play.txt 本身也当这一页的存档。
"""
import json
import os
import random
import uuid

import paths

HB_DIR = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox")
PLAY = os.path.join(HB_DIR, "play.txt")
STATUS = os.path.join(HB_DIR, "play-status.txt")

# 目标（sub_challenge）
CHALLENGES = [
    ("exterminate_determined_by_enemy", "歼灭", "把指定的敌人清掉。"),
    ("survivors", "护送幸存者", "把幸存者带到撤离点。"),
    ("activate_sam_site", "启动防空", "启动地图上的防空导弹站。"),
    ("active_and_defend_launchpad", "守住发射台", "启动发射台并守到发射。"),
    ("undetonated_shells", "拆除哑弹", "找到没爆的炮弹拆掉。"),
    ("assasinate_determined_by_enemy", "暗杀", "干掉指定的目标。"),
    ("secure_flagpost", "占领旗点", "占住旗杆守一段时间。"),
    ("single_point_fortify", "据点防守", "守一个点打一波波敌人，像报复关。只有困难难度能选。"),
]

# 装备规则（sub_condition），大类名（黑名单会写大类名，比如 wildcard），HellBox 版能不能用：
#   "self" = 能用，只对装了 HellBox 并开着的人有效；None = 只有真训练场有
# 2026-11-18 V0.96 用户发现描述不对（「武器照自己选的」进去是定好的）：按 construct_loadout 重写。训练场的配装是
#   先拿 LoadoutSettings.default_loadout（AR19 解放者 + P2 和平制造者 + 默认天赋、战备），规则再换掉一部分，
#   选装备界面不能改；没被换的就是默认的，不是自己选的。
CONDITIONS = [
    ("reload_surprise", "weapon_expertise", "填弹惊喜", "每次换弹，手里的枪随机换成另一把。试验场里开局主武器、手枪也随机，战略配备是随机打击类。", "self"),
    ("random_weapons", "weapon_expertise", "随机武器", "主武器、手枪、天赋、战略配备全随机。", None),
    ("pistols_only", "weapon_expertise", "只用手枪", "没有主武器，一把随机手枪；战略配备是随机打击类，一定带补给。", None),
    ("anti_tank_pistols_only", "weapon_expertise", "手枪 + 反坦克", "没有主武器，一把随机手枪；战略配备全是随机反坦克类。", None),
    ("flamethrower_or_tox_avenger", "weapon_expertise", "喷火 / 喷毒", "主武器是火焰喷射器或毒液喷射器（二选一）；战略配备是地雷和打击类，一定带补给。", None),
    ("double_barrel_and_grenades", "weapon_expertise", "双管 + 手雷", "双管霰弹枪、没有手枪，天赋是一种手雷（眩晕 / 烟雾 / 燃烧）；战略配备是地雷类，一定带补给。", None),
    ("support_weapons_strats_only", "weapon_expertise", "只用支援武器", "没有主武器，随机手枪和天赋；战略配备全是支援武器。", None),
    ("community_favorites", "weapon_expertise", "社区最爱", "从几套社区经典武装配置里随机一套（主武器、天赋、四个战略配备）。", None),
    ("liberty_day_veteran", "weapon_expertise", "自由日老兵", "栓动步枪 + 肾上腺素；一次性机枪、重型扫射、烟雾炮击、榴弹哨戒炮。", None),
    ("one_armed_angel", "weapon_expertise", "独臂天使", "冲锋枪 + 重甲；补给、医疗无人机、眩晕雷、地雷。", None),
    ("new_and_improved", "weapon_expertise", "新式装备", "20mm 机炮 + 强臂；补给、医疗或防御无人机（二选一）、喷火器、机枪塔。", None),
    ("no_primary", "stratagem_mastery", "没有主武器", "没有主武器，手枪、天赋、战略配备都是游戏默认武装配置。", None),
    ("defensive_strats_only", "stratagem_mastery", "只有防御战略配备", "没有主武器，随机手枪和天赋；战略配备全是防御类。", None),
    ("random_stratagems", "stratagem_mastery", "随机战略配备", "战略配备全随机；武器和天赋是游戏默认武装配置，不能自己选。", None),
    ("vehicles_stratagems_only", "stratagem_mastery", "只有载具", "没有主武器，随机手枪和天赋；战略配备全是载具。", None),
    ("mines_and_machineguns", "stratagem_mastery", "地雷 + 步枪", "战略配备全是地雷类；主武器在三把步枪和一把轻机枪里随机。", None),
    ("nailgun_and_support_or_strike", "stratagem_mastery", "钉枪", "钉枪 + 重甲；战略配备是支援和打击类。", None),
    ("melee_only", "wildcard", "只能近战", "军刀 + 强臂、没有手枪；战略配备只有不伤人的，一定带一种护盾。", None),
]

# 场上事件 / 常驻效果（sub_modifier），HellBox 版能不能用："team" = 能用，你当房主全队都有
MODIFIERS = [
    ("orbital_bombardments", "外层空间轨道轰炸", "每 15 秒左右，在某个队友身边 4～10 米随机落一发打击类战略配备。", "team"),
    ("orbital_support", "外层空间轨道支援", "每 20 秒，在某个队友身边随机落一个支援武器或背包。", "team"),
    ("emp", "电磁脉冲", "一会儿叫不了战略配备（15 秒）、一会儿能叫（40 秒），轮着来。", "team"),
    ("get_ammo_from_hits_double_reload_time", "伤害击中可提供弹药", "打中敌人回子弹，但弹匣只有一半。", None),
    ("super_boots", "侦察装甲", "跑得快 40%，挨怪打伤害翻倍。", None),
    ("what_goes_around", "误伤友军已反击", "你打到队友的伤害，同样打回你自己。", None),
    ("marksman", "只在击中弱点时造成双倍伤害", "只有打中弱点才有伤害，打中加倍。", None),
    ("ghost_town", "鬼城", "比夜晚还黑的试验场。", None),
]

# ---------------------------------------------------------------- HellBox 版的场上事件（2026-11-18 V0.97，用户定：可以叠加）
# (键, 名字, 效果, 谁有) ："team" = 你当房主全队都有；"self" = 只对装了 HellBox 并开着的人。
# 随机掉落 drop 代替原来的红色轰炸 / 蓝色支援（会掉哪些自己挑，见 DROP_*）。
# 超级靴子和以牙还牙在游戏的同一段代码（HealthComponent.command_master）里判断，一次只能认一个 → 不能一起开（CONFLICTS）。
CUSTOM_EVENTS = [
    ("drop", "随机掉落", "隔一阵在队友身边落一个战略配备，掉哪些在下面挑。", "team"),
    ("emp", "电磁脉冲", "叫不了战略配备 15 秒，能叫 40 秒，轮着来。", "team"),
    ("get_ammo_from_hits_double_reload_time", "伤害击中可提供弹药", "打中敌人回子弹，但弹匣只有一半。", "self"),
    ("marksman", "只在击中弱点时造成双倍伤害", "只有打中弱点才有伤害，打中加倍。", "self"),
    ("super_boots", "侦察装甲", "跑得快 40%，挨怪打伤害翻倍。", "self"),
    ("what_goes_around", "误伤友军已反击", "你打到队友的伤害，同样打回你自己。", "self"),
    # 2026-11-21 用户要：手枪格换成军刀（游戏「只能近战」那把，放在主武器格；军刀自己标着能当手枪用）。游戏那边见 hellbox_play.lua saber_update
    ("sidearm_saber", "副武器换成军刀", "手枪那一格换成军刀（近战）。", "self"),
]
CUSTOM_KEYS = [e[0] for e in CUSTOM_EVENTS]
CONFLICTS = {"super_boots": "what_goes_around", "what_goes_around": "super_boots"}

# ---------------------------------------------------------------- HellBox 版的环境（2026-11-18 V0.97 第 ③ 步，二选一，默认原版）
# (键, 名字, 效果, 谁有)：键 "" = 原版（不改）。鬼城只对装了 HellBox 并选了它的人有效（没装的人看到正常光照）。
# 游戏那边：地图照常生成（随机数不变），只是不装时间段灯光；角色 / 载具开手电筒（见 mod/src/hellbox_play.lua 的 spawn_levels 挂钩）。
ENVS = [
    ("", "原版", "照关卡本来的时间段光照。", None),
    ("ghost_town", "鬼城", "时间段灯光藏起来，比夜晚还黑；角色和载具自带手电筒；挡视线的雾一起去掉。", "self"),
]
ENV_KEYS = [e[0] for e in ENVS]

# 随机掉落：战备名单从 ai/strat_fields.json 来（中英文名、游戏里的类型）。颜色照游戏：
#   offensive 进攻 = 红、supply 补给 = 蓝（载具也是补给类）、defensive 防御 = 绿、special 特殊 = 黄
DROP_COLORS = [("red", "红色", "offensive"), ("blue", "蓝色", "supply"), ("green", "绿色", "defensive"),
               ("yellow", "黄色", "special")]
# 落不了的：游戏落下来时没有「扔它的人」
DROP_BAN = {
    "stratagem_reinforce": "增援落下来要带上扔它的人（游戏发复活消息时用），随机落的没有，可能出错。",
    "stratagem_emergency_beacon": "求救信标一落就会把房间改成公开，不让随机落。",
}
STRAT_FIELDS = os.path.join(paths.ROOT, "ai", "strat_fields.json")


def drop_pool():
    """[(颜色键, [(战备名, 中文名, 英文名, 是不是载具), …]), …]，按游戏里的顺序。读不到返回 []。"""
    try:
        with open(STRAT_FIELDS, encoding="utf-8") as f:
            strats = json.load(f).get("strats") or {}
    except (OSError, ValueError):
        return []
    out = []
    for color, _name, typ in DROP_COLORS:
        rows = [(k, v.get("zh") or k, v.get("en") or v.get("zh") or k, v.get("cat") == "vehicle")
                for k, v in strats.items() if v.get("type") == typ]
        rows.sort(key=lambda r: r[3])  # 载具排在蓝色最后
        out.append((color, rows))
    return out


def split_list(text):
    return [x for x in (text or "").replace(" ", "").split(",") if x]


# 2026-11-19 发行抢先版 用户定：随机掉落只能选自己解锁了的战略配备（等级 / DLC / 奖励，开局就带的算解锁），
#   没解锁的灰掉，就算以前勾上了也不生效（游戏里 hellbox_play.lua 同样跳过）。名单由游戏写（profile_tool.lua：
#   strat-unlocks.txt，HBUNLK1 / on=逗号串，变了才写），游戏关着时按上次看到的。
UNLOCKS = os.path.join(HB_DIR, "strat-unlocks.txt")


def read_unlocks():
    """解锁了的战备名 set；还没有这个文件（新版核心还没进过游戏）返回 None = 不知道。"""
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


RACES = [("bugs", "虫族"), ("cyborgs", "赛博人"), ("illuminates", "光能族")]
TIMES = [("dawn", "黎明"), ("day", "白天"), ("dusk", "黄昏"), ("night", "夜晚")]
DIFFS = [("1", "简单"), ("2", "中等"), ("3", "困难")]
TERRAINS = 214  # 地图编号高位 floor(n / 10000000)，0～213

# 游戏的黑名单（照 provinggrounds_settings.lua）
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
    """这个组合游戏让不让开：返回 None = 可以；否则 (被挡的那一样, 是谁挡的)。"""
    sources = [(DIFF_BLACK.get(diff, set()), f"{DIFF_NAMES.get(diff, diff)}难度"),
               (CHAL_BLACK.get(chal, set()), NAMES.get(chal, chal)),
               (COND_BLACK.get(cond, set()), NAMES.get(cond, cond))]
    for names, who in sources:
        for item in (chal, cond, COND_GROUP.get(cond), mod):
            if item and item in names:
                return item, who
    return None


# follow：2026-11-18 V0.97 第 ⑥ 步「跟随房主的玩法」（默认 1）：你进别人房间当客机时，配装块 / 换弹惊喜 / 装了才有的事件 / 鬼城照房主的，
#   自己这页的设置不生效；0 = 这些都不开，照普通方式玩。自己当房主 / 单机 / 本机分屏不受它管。
DEFAULT = {"custom": "0", "follow": "1", "cond": "reload_surprise", "event": "drop", "drop": "", "env": "", "trial": "",
           "race": "bugs", "tod": "night", "diff": "1", "chal": "exterminate_determined_by_enemy",
           "pcond": "reload_surprise", "pmod": "orbital_bombardments", "terrain": ""}
ORDER = ["custom", "follow", "cond", "event", "drop", "env", "trial", "race", "tod", "diff", "chal", "pcond", "pmod", "terrain"]


def _migrate_events(cfg):
    """V0.96 以前 HellBox 版 event 只有一个：红色轰炸 / 蓝色支援换成「随机掉落」+ 对应颜色的战备；
    drop 是空的（新装）时默认掉全部红色。只留 HellBox 版认识的事件。"""
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
    """读 play.txt（这一页的存档）；没有就用默认值。地形没有就随机一个。"""
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
    tmp = PLAY + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, PLAY)


def new_trial_id():
    return uuid.uuid4().hex[:10]


def read_status():
    """游戏写的 play-status.txt：{"trial", "state", "why", "events"，V0.97 第 ⑥ 步多 "role"（host / guest / none）、"follow"、
    "host_state"（ok 读到 / old 房主是 V0.96 / none 房主没装 / err 读不到）、"host"（房主写的原串）}；没有返回 {}。"""
    try:
        with open(STATUS, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return {}
    if not lines or lines[0] != "HBPLAYST1":
        return {}
    return dict(line.split("=", 1) for line in lines[1:] if "=" in line)


def parse_host(raw):
    """房主房间数据 hellbox_play 的原串（1|开着没|换弹惊喜|事件逗号串|环境）→ {"custom", "cond", "events", "env"}；认不出返回 None。"""
    parts = (raw or "").split("|")
    if len(parts) < 5 or parts[0] != "1":
        return None
    return {"custom": parts[1] == "1", "cond": parts[2] if parts[2] == "reload_surprise" else "",
            "events": [e for e in CUSTOM_KEYS if e in split_list(parts[3])],
            "env": parts[4] if parts[4] in ENV_KEYS else ""}
