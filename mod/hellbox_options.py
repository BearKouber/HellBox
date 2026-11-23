"""HellBox 的游戏内小功能设置（hellbox_options.json）。装 mod 时编译进 src/hellbox_qol.lua 当初始值；
2026-11-14 V0.91 起改了就写 %APPDATA%/Arrowhead/Helldivers/hellbox/options.txt，游戏每秒读（热生效）。

2026-11-13 用户定：去掉「QoL 增强」总开关（MOD 总开关开着这些就能用）和「高档阴影」；画面加速 ×2～×5 四档。
2026-11-21 HD1-038 用户定：来自 QoL Mod 的六项（手柄改键保护、降级退点、延迟数字、禁用求救信标、过场加速、暂停星球进度）删了。
"""
import json
import os
from pathlib import Path

FILE = Path(__file__).with_name("hellbox_options.json")
VOICE = {
    "taunt": "战吼", "help_me_up_request": "求救", "reload_me_request": "请求协同装填",
    "ammo_empty": "弹药耗尽", "ammo_low": "弹药不足", "take_cover": "寻找掩护",
    "can_not_jump": "无法跳跃", "jumping": "跳跃中", "reloading": "装填中",
    "throwing_grenade": "投掷手雷", "move": "移动", "stay": "留守",
    "yes": "是", "no": "否", "exit_blocked": "出口受阻",
    "friendly_fire_detected": "检测到友军误伤",
}
# 2026-11-16 用户：冲刺、闪避能设成「切换」，那样一进选星界面就一直刷新，删掉
ACTIONS = {"reload": "换弹",
           "switch_weapon": "切换武器", "": "仅桌面手动"}
# 2026-11-16 V0.95 丢战备：键盘可选的键（原版键位都没用到），手柄固定长按交互键
DROP_KEYS = {"x": "X", "z": "Z", "c": "C", "b": "B", "h": "H", "t": "T"}
# 2026-11-19 发行抢先版 用户要求：丢支援装备能选先丢武器还是先丢背包。"" = 原来的（手里拿着支援武器丢它，不然丢背包）
DROP_FIRST = {"": "看手上", "weapon": "先丢武器", "backpack": "先丢背包"}
# 2026-11-19 补给背包热键（Lhgrzr）：键盘可选主键盘 4～9（原版只用了 1～3），默认 5；手柄固定长按换弹键
SUPPLY_KEYS = {"4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9"}
DEFAULT = {
    "refresh": False, "action": "reload", "voice": False,
    "voice5": "taunt", "voice6": "help_me_up_request", "voice7": "reload_me_request",
    "voice8": "ammo_empty",
    # 2026-11-21 HD1-038：来自 Dive Harder（Oct0pu5）的四项（src/hellbox_dh.lua）
    "dh_ping": False, "ping_window": 5, "dh_hidden": False, "dh_friends": True, "dh_qol_fix": True,
    "room_order": "tag",  # 2026-11-21 HD1-038：房间名「[HellBox] 名字」（tag）还是「名字 [HellBox]」（name），pages/room_desc.py 写给游戏
    "drop": False, "drop_key": "x",
    "noslide": False,  # 2026-11-18 V0.96 换弹不滑
    "drop_first": "",
    "supply": False, "supply_key": "5",  # 2026-11-19 补给背包热键（Lhgrzr）
    "hide_samples": False,  # 2026-11-19 隐藏样本描边（Lhgrzr）
    "ime_fix": True,  # 2026-11-19 聊天输入法防闪退（HalfSugar），修闪退的默认开
    # 2026-11-23 用户要回来：过场加速（借鉴 QoL Mod，照 V1.02 那版写；能和 QoL 一起装）
    "speed": False, "speed_factor": 3,
}


ROOM_ORDERS = {"tag": "[HellBox] 名字", "name": "名字 [HellBox]"}
PING_WINDOWS = (3, 5, 10)  # HUD 延迟显示：最近几次取平均（Dive Harder 原版就这三档）
SPEEDS = (2, 3, 4, 5)  # 过场加速倍数
INT_CHOICES = {"ping_window": PING_WINDOWS, "speed_factor": SPEEDS}


def _int(key, value):
    return value if type(value) is int and value in INT_CHOICES[key] else DEFAULT[key]


def _choices(key):
    return {"action": ACTIONS, "drop_key": DROP_KEYS, "drop_first": DROP_FIRST, "supply_key": SUPPLY_KEYS,
            "room_order": ROOM_ORDERS}.get(key, VOICE)


def load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("HellBox 设置应为 JSON 对象。")
    return DEFAULT | {key: data[key] for key in DEFAULT if key in data}


def save(changes):
    # 直接写：先写 .tmp 再 os.replace 在游戏目录被保护 / 杀毒盯着时会 WinError 5（2026-11-23 用户日志里的那次）
    data = load() | changes
    with open(FILE, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def lua_options(quote):
    data = load()
    fields = []
    for key, default in DEFAULT.items():
        value = data[key]
        if isinstance(default, bool):
            value = "true" if value is True else "false"
        elif isinstance(default, int):
            value = str(_int(key, value))
        else:
            value = quote(value if isinstance(value, str) and value in _choices(key) else default)
        fields.append(f"{key}={value}")
    return "{" + ",".join(fields) + "}"


LIVE = Path(os.environ.get("APPDATA", "")) / "Arrowhead" / "Helldivers" / "hellbox" / "options.txt"


def live_text(carry=True):
    data = load()
    lines = ["HBOPT1"]
    for key, default in DEFAULT.items():
        value = data[key]
        if isinstance(default, bool):
            value = "true" if value is True else "false"
        elif isinstance(default, int):
            value = str(_int(key, value))
        else:
            value = value if isinstance(value, str) and value in _choices(key) else default
        lines.append(f"{key}={value}")
    lines.append("carry=" + ("true" if carry else "false"))
    return "\n".join(lines) + "\n"


def write_live(carry=True):
    """写游戏每秒读的开关文件（先写临时文件再换名）。"""
    LIVE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LIVE.with_suffix(".tmp")
    tmp.write_text(live_text(carry), encoding="utf-8")
    os.replace(tmp, LIVE)
    return LIVE
