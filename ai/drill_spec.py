r"""出怪练习（HellBox「快速开局」页 + ai\drill_run.py 共用，2026-11-07）：地图编号怎么拼、默认设置、游戏和陪玩程序的参数。

只用标准库（HellBox 打包后从磁盘 import 它）。

地图编号（游戏的 -autohost 参数，按位拼，见 mod\lua_src\lua__settings__difficulty_settings.lua 的 modulate_seed / get_mission_params）：
    千万位以上 = 地形随机数（0~214，整个编号不能超过 2147483646）
    百万位 = 时间（0 黎明 1 白天 2 黄昏 3 夜晚）
    十万位 = 光照（0~2；3~5 是阵营专用）
    万位   = 环境（0 沙漠 1 森林 2 雪地 3 熔岩 4 城市）
    千位   = 环境变体（0~2；3~5 是阵营专用）
    百位   = 阵营（0 虫族 1 生化人 2 光能者）
    末两位 = 任务类型 × 20 + 难度（0 普通任务 / 大图、1 首领战、2 报复关；难度 1~15）
地图怎么长（地形、出生点）由整个编号决定（GeneratedLevel 用它当随机种子），同一个编号每次都是同一张图。

AI 脚本列表（「运行」里选用哪个 AI 脚本跑，每次打开页面 / 点「刷新」都重新从磁盘找，HellBox 不用改代码）：
  1. ai\hellbox_scripts\*.json：一个文件一条（同一个程序配不同参数，比如 companion.py 单人测试 / 你也上场）
  2. ai\*.py、ai\hellbox_scripts\*.py 开头 40 行里有一行  # hellbox-script: {...}  的（新写的 AI 脚本自己带上）
  两种写法的内容一样（JSON）：
    name     列表里的名字（中文）                desc     一句话说明
    script   要跑的 .py（相对 ai\，用第 2 种写法时不用填，就是文件自己）
    args     参数列表，可用 {run}（记录文件夹）{seed}（地图编号）{primary_only}（勾了「只用主武器」= --primary-only，没勾就去掉）
    players  "solo" = 只有她（进关 3 分钟没人出场算失败；「第一次死」= 她死）；"you" = 你也上场（不限时等人出场；「第一次死」= 任何人死）
    stop     "file" = 停的时候在记录文件夹放 STOP 等它自己退出；"kill" = 直接结束它
    options  ["primary_only"] = 这个脚本支持「只用主武器」
    order    排序（小的在前）
  跑的时候一律走 drill_run.py：关旧游戏 → 带地图 / 出怪参数开游戏 → 接上脚本 → 到停止条件 → 关游戏。
  AI 代码改了不用做什么：每次都是从磁盘上现跑；列表里显示程序文件最后改的时间。
"""
import copy
import json
import os
import random
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MONSTERS = os.path.join(HERE, "drill_monsters.json")
RUNS = os.path.join(HERE, "logs", "runs")
LAST = os.path.join(HERE, "logs", "drill_last.json")        # HellBox 上次的选择
CURRENT = os.path.join(HERE, "logs", "drill_current.json")  # 正在跑的那次（runner 写，跑完删）

RACES = [("bugs", "虫族"), ("cyborgs", "生化人"), ("illuminates", "光能者")]  # 2026-11-14 按游戏百科全书
ENVS = [("desert", "沙漠"), ("forest", "森林"), ("snow", "雪地"), ("lava", "熔岩"), ("city", "城市")]
TIMES = [("dawn", "黎明"), ("day", "白天"), ("dusk", "黄昏"), ("night", "夜晚")]
GENOCIDE = 2
# 训练能选的任务类型（2026-11-15 用户要求：除了报复关，还要大图（普通任务）和首领战）。值 = 编号里的任务类型
MISSIONS = [(GENOCIDE, "报复关"), (0, "大图"), (1, "首领战")]
MISSION_NAME = dict(MISSIONS)
MAX_TERRAIN = 214
MAX_SEED = 2147483646

SPAWN_MODES = [("vanilla", "原版出怪"), ("only", "只出选中的"), ("seq", "按节奏出"), ("wave", "从第 N 波开打")]

SCRIPTS_DIR = os.path.join(HERE, "hellbox_scripts")
SCRIPT_MARK = "# hellbox-script:"
GAME_ONLY = "game"              # 内置的「只开游戏自己玩」（不跑 AI 脚本）
DEFAULT_SCRIPT = "companion_solo"
OLD_WHAT = {"game": GAME_ONLY, "solo": DEFAULT_SCRIPT}  # 旧设置 run.what -> 脚本 id
RUN_WHAT = [("game", "只开游戏自己玩"), ("solo", "陪玩单人测试")]  # 只给旧版 HellBox 页面用（exe 重新打包前），新页面不用

DEFAULT = {
    "seed": 1860102045,
    "spawn": {"mode": "seq", "units": {"bugs": ["bug_tank/bug_tank"], "cyborgs": [], "illuminates": []},
              "max": 1, "seq": [1, 2], "gap": 3, "start_wave": 5},
    "run": {"script": DEFAULT_SCRIPT, "primary_only": True},
    "stop": {"kills": 20, "first_death": True, "minutes": 0},
    # 2026-11-25 用户定「变强」（选图存档下面一格，只在一个人打报复关时生效）：从第几波开始（1 = 原版）、复活币开关
    "strong": {"wave": 1, "revive": False},
}


# ---------------------------------------------------------------- AI 脚本列表
def _builtin_game():
    return {"id": GAME_ONLY, "name": "只开游戏自己玩", "players": "you", "stop": None, "options": [], "order": -1,
            "desc": "不跑 AI，只开游戏进关卡，你自己玩。加载好以后在游戏里按 E（手柄 A）出场。",
            "script": None, "args": [], "source": "HellBox 内置", "mtime": None, "problems": []}


def _entry(raw, eid, source, default_script=None):
    e = {"id": eid, "source": source, "problems": []}
    e["name"] = str(raw.get("name") or eid)
    e["desc"] = str(raw.get("desc") or "")
    script = raw.get("script") or default_script
    e["script"] = os.path.normpath(os.path.join(HERE, script)) if script else None
    args = raw.get("args", [])
    e["args"] = [str(a) for a in args] if isinstance(args, list) else []
    e["players"] = raw.get("players") if raw.get("players") in ("solo", "you") else "solo"
    e["stop"] = raw.get("stop") if raw.get("stop") in ("file", "kill") else "kill"
    e["options"] = [o for o in (raw.get("options") or []) if o == "primary_only"]
    try:
        e["order"] = float(raw.get("order", 50))
    except (TypeError, ValueError):
        e["order"] = 50.0
    if not isinstance(args, list):
        e["problems"].append("args 要是列表")
    e["mtime"] = None
    if not e["script"]:
        e["problems"].append("没写 script")
    elif not os.path.isfile(e["script"]):
        e["problems"].append(T('找不到程序 {0}', script))
    else:
        e["mtime"] = os.path.getmtime(e["script"])
    return e


def _header(path):
    """.py 开头 40 行里的  # hellbox-script: {...}，没有返回 None。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for _ in range(40):
                line = f.readline()
                if not line:
                    break
                if line.startswith(SCRIPT_MARK):
                    raw = json.loads(line[len(SCRIPT_MARK):].strip())
                    return raw if isinstance(raw, dict) else {"name": os.path.basename(path), "_bad": True}
    except (OSError, ValueError):
        return {"name": os.path.basename(path), "_bad": True}
    return None


def list_scripts():
    """「运行」里能选的 AI 脚本。每次调用都重新扫磁盘（见文件开头的说明）。第一条永远是「只开游戏自己玩」。"""
    out = [_builtin_game()]
    seen = {GAME_ONLY}
    if os.path.isdir(SCRIPTS_DIR):
        for name in sorted(os.listdir(SCRIPTS_DIR)):
            eid = os.path.splitext(name)[0]
            if not name.endswith(".json") or eid in seen:
                continue
            p = os.path.join(SCRIPTS_DIR, name)
            try:
                with open(p, encoding="utf-8") as f:
                    raw = json.load(f)
                e = _entry(raw if isinstance(raw, dict) else {}, eid, p)
            except (OSError, ValueError) as ex:
                e = _entry({"name": name}, eid, p)
                e["problems"].insert(0, T('文件读不了：{0}', ex))
            out.append(e)
            seen.add(eid)
    for folder in (HERE, SCRIPTS_DIR):
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            eid = os.path.splitext(name)[0]
            if not name.endswith(".py") or eid in seen:
                continue
            p = os.path.join(folder, name)
            raw = _header(p)
            if raw is None:
                continue
            e = _entry(raw, eid, p, default_script=p)
            if raw.get("_bad"):
                e["problems"].insert(0, "开头那行 hellbox-script 不是合法的 JSON")
            out.append(e)
            seen.add(eid)
    out.sort(key=lambda e: (e["order"], e["name"]))
    return out


def find_script(sid, scripts=None):
    for e in scripts if scripts is not None else list_scripts():
        if e["id"] == sid:
            return e
    return None


def script_args(cfg, run, entry):
    """把脚本参数里的 {run} {seed} {primary_only} 换成这次的值。返回 [程序路径, 参数...]（前面由调用方加 python）。"""
    po = bool(cfg["run"].get("primary_only")) and "primary_only" in entry["options"]
    out = []
    for a in entry["args"]:
        if a == "{primary_only}":
            if po:
                out.append("--primary-only")
            continue
        out.append(a.replace("{run}", run).replace("{seed}", str(cfg["seed"])))
    return [entry["script"]] + out


# ---------------------------------------------------------------- 地图编号
def decode(seed):
    seed = int(seed)
    return {
        "terrain": seed // 10000000,
        "time": seed // 1000000 % 10 % 4,
        "shading": seed // 100000 % 10 % 6,
        "env": seed // 10000 % 10 % 6,
        "variant": seed // 1000 % 10 % 6,
        "race": seed // 100 % 10 % 3,
        "mission": seed % 100 // 20 % 5,
        "difficulty": min(15, max(1, seed % 100 % 20)),
    }


def encode(terrain, time, shading, env, variant, race, difficulty, mission=GENOCIDE):
    seed = (int(terrain) * 10000000 + int(time) % 4 * 1000000 + int(shading) % 6 * 100000 + int(env) % 6 * 10000
            + int(variant) % 6 * 1000 + int(race) % 3 * 100 + int(mission) % 5 * 20 + min(15, max(1, int(difficulty))))
    return seed


def with_fields(seed, **kw):
    """改编号里的某几样（race=、env=、difficulty=、time=、mission=），别的不动。任务类型不是训练能选的就当报复关。"""
    d = decode(seed)
    d.update(kw)
    if d["mission"] not in MISSION_NAME:
        d["mission"] = GENOCIDE
    return encode(**d)


def new_terrain(seed, rng=random):
    """换一张图：地形随机数、光照、环境变体重新随机，种族、环境、难度、时间不变。"""
    return with_fields(seed, terrain=rng.randint(0, MAX_TERRAIN), shading=rng.randint(0, 2), variant=rng.randint(0, 2))


def valid_seed(seed):
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        return False
    d = decode(seed)
    return 0 <= seed <= MAX_SEED and d["mission"] in MISSION_NAME and d["env"] < len(ENVS)


def race_key(seed):
    return RACES[decode(seed)["race"]][0]


def describe(seed):
    d = decode(seed)
    env = ENVS[d["env"]][1] if d["env"] < len(ENVS) else T('环境{0}', d['env'])
    kind = MISSION_NAME.get(d["mission"]) or T('任务类型{0}', d['mission'])
    return T('{0} · {1} · {2} · {3} · 难度 {4}', tr(RACES[d['race']][1]), tr(kind), tr(env), tr(TIMES[d['time']][1]),
             d['difficulty'])


# ---------------------------------------------------------------- 怪物清单
def load_monsters():
    """{race: [怪, ...]}，怪 = drill_monsters.json 里的一行（path、zh、nick、test、part……）。读不到返回 {}。"""
    try:
        with open(MONSTERS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {race: info.get("units", []) for race, info in data.get("races", {}).items()}


_FAMILY_EN = None  # 英文版：同类的中文名 -> 游戏英文名


def label(m):
    """界面上的名字：游戏名（叫法）；没有游戏名的：同类的游戏名·内部名后缀（如 生化兵·squadleader）。"""
    if tr("虫族") != "虫族":  # 英文版（2026-11-14）：用游戏自己的英文名，没有就用内部名
        en = m.get("en") or ""
        if en:
            return en.title()
        global _FAMILY_EN
        if _FAMILY_EN is None:
            _FAMILY_EN = {u.get("zh"): u.get("en") for us in load_monsters().values() for u in us
                          if u.get("zh") and u.get("en")}
        fam = _FAMILY_EN.get(m.get("family_zh")) or ""
        return (fam.title() + "·" + m["name"].split("_")[-1]) if fam else (m.get("name") or m.get("path", ""))
    s = m.get("zh") or m.get("name") or m.get("path", "")
    if m.get("nick") and m["nick"] != s:
        s += f"（{m['nick']}）"
    elif m.get("family_zh") and m.get("name_from") == "internal":
        parts = m["name"].split("_")
        s = f"{m['family_zh']}·{parts[-1]}"
    return s


# ---------------------------------------------------------------- 设置
def normalize(cfg):
    """补齐缺的项、去掉不合法的值。返回新的一份。"""
    out = copy.deepcopy(DEFAULT)
    cfg = cfg or {}
    if valid_seed(cfg.get("seed")):
        out["seed"] = int(cfg["seed"])
    for k in ("spawn", "run", "stop", "strong"):
        if isinstance(cfg.get(k), dict):
            out[k].update(cfg[k])
    sg = out["strong"]
    try:
        sg["wave"] = max(1, min(99, int(sg.get("wave") or 1)))
    except (TypeError, ValueError):
        sg["wave"] = 1
    sg["revive"] = bool(sg.get("revive"))
    rn = out["run"]
    if "what" in rn:  # 旧设置（只有 只开游戏 / 陪玩单人测试 两种）
        old = rn.pop("what")
        if not (isinstance(cfg.get("run"), dict) and cfg["run"].get("script")):
            rn["script"] = OLD_WHAT.get(old, DEFAULT_SCRIPT)
    if not isinstance(rn.get("script"), str) or not rn["script"]:
        rn["script"] = DEFAULT_SCRIPT
    rn["primary_only"] = bool(rn.get("primary_only"))
    rn["what"] = "game" if rn["script"] == GAME_ONLY else "solo"  # 旧版页面还读这一项
    sp = out["spawn"]
    if sp["mode"] not in dict(SPAWN_MODES):
        sp["mode"] = DEFAULT["spawn"]["mode"]
    if not isinstance(sp.get("units"), dict):
        sp["units"] = copy.deepcopy(DEFAULT["spawn"]["units"])
    for race, _ in RACES:
        sp["units"].setdefault(race, [])
    sp["max"] = max(1, min(40, int(sp.get("max") or 1)))
    sp["seq"] = [max(1, min(40, int(n))) for n in (sp.get("seq") or [1])][:40] or [1]
    sp["gap"] = max(0.0, min(60.0, float(sp.get("gap") or 0)))
    sp["start_wave"] = max(1, min(99, int(sp.get("start_wave") or 1)))
    st = out["stop"]
    st["kills"] = max(0, int(st.get("kills") or 0))
    st["minutes"] = max(0.0, float(st.get("minutes") or 0))
    st["first_death"] = bool(st.get("first_death"))
    # 只数这一种怪的击杀（考场用，2026-11-11：如 "bug_tank" = 打死几只冲锋虫才停，小虫不算）；空 = 什么怪都算
    st["kill_type"] = st.get("kill_type") if isinstance(st.get("kill_type"), str) else ""
    return out


def parse_seq(text):
    """"1,2 1" -> [1, 2, 1]；不合法返回 None。"""
    parts = [p for p in text.replace("，", ",").replace("、", ",").replace(" ", ",").split(",") if p.strip()]
    try:
        seq = [int(p) for p in parts]
    except ValueError:
        return None
    if not seq or any(n < 1 or n > 40 for n in seq):
        return None
    return seq


def selected_units(cfg):
    """这张图种族、这次要出的怪（path 列表）。实测刷了会崩 / 刷不出来的（test = bad）、部件不算。"""
    race = race_key(cfg["seed"])
    bad = {m["path"] for m in load_monsters().get(race, []) if m.get("test") == "bad" or m.get("part")}
    return [p for p in cfg["spawn"]["units"].get(race, []) if p not in bad]


def pickable(race):
    """界面上能勾的怪（去掉部件和实测不行的），和拿掉了几种。"""
    ms = load_monsters().get(race, [])
    ok = [m for m in ms if not m.get("part") and m.get("test") != "bad"]
    return ok, len(ms) - len(ok)


def problems(cfg):
    """开始前检查，返回要告诉用户的问题（空 = 可以开始）。"""
    out = []
    if not valid_seed(cfg["seed"]):
        out.append("地图编号不对（要是报复关的编号）。")
    sp = cfg["spawn"]
    if sp["mode"] in ("only", "seq") and not selected_units(cfg):
        out.append("出怪选了「只出选中的 / 按节奏出」，但这个种族一只怪都没勾。")
    entry = find_script(cfg["run"]["script"])
    if entry is None:
        out.append(T('选的 AI 脚本（{0}）找不到了，点「刷新」重新选一个。', cfg['run']['script']))
    elif entry["problems"]:
        out.append(T('AI 脚本「{0}」有问题：', entry['name']) + "；".join(entry["problems"]))
    return out


def game_args(cfg):
    """开游戏的参数（经 Steam 传进去）。只带自动建房：2026-11-12 晚起游戏只要多带任何启动参数（连 -foo bar 也算）
    就常在主菜单自动建房时崩（0xC0000005），只带 -autohost 不崩。出怪设置改由 drill_command 开游戏后写进 mod 信箱。"""
    return ["--skip_splash", "--no_tutorial", "-autohost", str(cfg["seed"])]


def drill_command(cfg):
    """出怪设置 -> 写进 mod 信箱的命令（mod\\src\\ai_drill.lua 文件头"信箱"）；原版出怪返回 None。"""
    sp = cfg["spawn"]
    if sp["mode"] in ("only", "seq"):
        return (f"drill_mode={sp['mode']};drill_units={','.join(selected_units(cfg))};drill_max={sp['max']};"
                f"drill_seq={','.join(str(n) for n in sp['seq'])};drill_gap={'%g' % sp['gap']}")
    if sp["mode"] == "wave" and sp["start_wave"] >= 2:
        return f"start_wave={sp['start_wave']}"
    return None


def spawn_text(cfg):
    sp = cfg["spawn"]
    mons = {m["path"]: label(m) for ms in load_monsters().values() for m in ms}
    names = "、".join(mons.get(p, p) for p in selected_units(cfg)) or "（没选）"
    if sp["mode"] == "only":
        return T('只出 {0}，场上最多 {1} 只，少了隔 {2:g} 秒补', names, sp['max'], sp['gap'])
    if sp["mode"] == "seq":
        return T('按节奏出 {0}：每批 {1}……，全打死隔 {2:g} 秒出下一批', names, '、'.join(map(str, sp['seq'])), sp['gap'])
    if sp["mode"] == "wave":
        return T('原版出怪，从第 {0} 波开打', sp['start_wave'])
    return "原版出怪"


def stop_text(cfg):
    st = cfg["stop"]
    parts = []
    if st["kills"]:
        parts.append(T('打死 {0} 只', st['kills']))
    if st["first_death"]:
        e = find_script(cfg["run"]["script"])
        parts.append(tr("她第一次死" if e and e["players"] == "solo" else "第一次有人死"))
    if st["minutes"]:
        parts.append(T('{0:g} 分钟', st['minutes']))
    return tr("、").join(parts) + tr("就停（也能手动停）") if parts else tr("手动停")


def run_text(cfg, entry=None):
    entry = entry or find_script(cfg["run"]["script"])
    if entry is None:
        return T('AI 脚本 {0}（找不到了）', cfg['run']['script'])
    what = entry["name"]
    if cfg["run"].get("primary_only") and "primary_only" in entry["options"]:
        what += "（只用主武器）"
    return what


def load_last():
    try:
        with open(LAST, encoding="utf-8") as f:
            return normalize(json.load(f))
    except (OSError, ValueError, TypeError):
        return normalize(None)


def save_last(cfg):
    os.makedirs(os.path.dirname(LAST), exist_ok=True)
    with open(LAST, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
