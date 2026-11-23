r"""把 mod/src 里改过的 Lua 编译后替换进脚本 bundle，生成新的 bundle 文件。

用法:
    .venv\Scripts\python mod\build.py            # 生成 mod\out\9e13b2414b41b842
    .venv\Scripts\python mod\build.py install    # 生成并覆盖游戏文件（首次自动备份原文件）
    .venv\Scripts\python mod\build.py restore    # 用备份还原游戏文件
    .venv\Scripts\python mod\build.py status     # 查看当前是 on / off
"""
import functools
import hashlib
import os
import re
import struct
import subprocess
import sys

from bundle import LUA, compress, decompress, murmur64a, parse
import hellbox_options
import hellbox_hop
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE_NAME = "9e13b2414b41b842"
STEAM_APP_ID = "394510"
VANILLA_BUNDLE_SHA256 = "5ded3de9994ced0ee70597115c46c3604b754897b10de689c5b127ea8b1750a8"
BACKUP = os.path.join(HERE, "backup", BUNDLE_NAME)
OUT = os.path.join(HERE, "out", BUNDLE_NAME)
# 2026-11-20 HD1-036（用户定：和 Obsidian 能同时装）：装进游戏的不再是整份 OUT，而是 OUT 和原版比出来的补丁
#   （只含改过的脚本），放成 contents\9e13b2414b41b842.patch_N，游戏原文件保持原版。见 patch_files.py。
OUT_PATCH = OUT + ".patch"
# 所有 HellBox（自用版、发行版、不同文件夹的测试版）共用的原版备份（2026-11-14）：
# 各自文件夹里的备份别的 HellBox 看不到，换一份 HellBox 就「无法识别」；放这里大家都找得到。只放核对过是原版的文件。
SHARED_BACKUP = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Arrowhead", "Helldivers", "hellbox",
                             "backup", BUNDLE_NAME)
LUAJIT = os.path.join(HERE, "..", "tools", "luajit-2.0", "src", "luajit.exe")

# 分屏（2026-11-14）：HalfSugar 写的 CameraCTRL，作者同意收进 HellBox。
# 它的桥接和我们改的是同一个脚本文件，所以发行版编完我们的脚本后，把分屏模块叠进去，
# 一个文件里两样都有，MOD 总开关一起装 / 一起还原。它只改一个启动脚本（CAMERA_RES），我们的脚本原样保留。
# 2026-11-21 HD1-037：叠的那一步从它自带的程序（CameraCTRL-bridge.exe prepare）改成 camera_stack.py（照它源码搬的 Python），
#   发行包不再带 exe（被 3 家杀毒软件误报，N 网隔离）；分屏模块 = mod/camera/runtime.luac。和 exe 的输出逐字节一样。
import camera_stack
CAMERA_LUAC = camera_stack.CAMERA_LUAC
CAMERA_RES = 0x37048A618ABDDC81

# 游戏内资源名 -> 源文件列表（相对 mod 目录，按顺序拼接后编译）
# "vanilla:<资源名>" = 这个脚本「没有 HellBox 时」的样子：装的时候从玩家自己游戏的启动包里取出编译好的脚本，用 loadstring 原样跑
# （2026-11-19 HD1-033：发行包和公开源码都不再带反编译出来的原版脚本，见 vanilla_source）
# 2026-11-21 HD1-038（用户定：和 QoL、Dive Harder 都兼容）：取的是游戏当前启动包里的那份（原版，或 Dive Harder 改过的
#   character_state_machine），所以别的 MOD 接在同一个脚本里的代码照样跑，HellBox 的接在后面。见 base_state()。
VANILLA = "vanilla:"
PATCHES = {
    # 箱子上车 mod：原版搬箱子脚本 + 外挂的改动（2026-11-19 以前是整份改过的原版脚本 src/character_state_carry.lua）
    "lua/character_states/character_state_carry": [VANILLA + "lua/character_states/character_state_carry", "src/carry_vehicle.lua"],
    # AI 陪玩的"眼睛"：原版状态机脚本 + 末尾追加 ai_bridge
    "lua/character_states/character_state_machine": [
        VANILLA + "lua/character_states/character_state_machine",
        "src/ai_bridge.lua",
        "src/ai_terrain.lua",  # HD1-007 第 2 步：地形表（地面高度、坠落区、火山），陪玩的地形闸门用
        "src/ai_menu.lua",  # HD1-009（2026-10-12）：界面表（最上层状态、菜单、光标、结算），挂 WorldManager.update
        "src/ai_mech.lua",  # HD1-012（2026-10-13）：机制表（输入、状态计时、发射器连发、出膛 / 爆炸 / 近战 / 挨打事件），录实机操作用
        "src/hb_log.lua",  # 2026-11-14：HellBox 日志本（HellBoxLog 写 hellbox/logs/game.log），要在用它的脚本前面
        "src/hb_probe.lua",  # 2026-11-19：闪退探针（一直写 hellbox/logs/game-probe.txt 现在在干什么；没正常退出 = 可能闪退），要在 hb_log 后面
        "src/hellbox_room_gate.lua",  # 2026-11-23 V1.07：联机限制（当客机时只在有 MOD 的房间开几项功能），要在用它的脚本前面
        "src/recap_guard.lua",  # 2026-10-18：开机战役回顾服务器回 0 张快照时不再闪退（parent:exit 为 nil）
        "src/room_name.lua",  # 2026-10-21：自定义房间名（名字在 room_name.txt）
        "src/hellbox_room_filter.lua",  # 2026-11-21 HD1-038：找房间「筛选」里加「隐藏 HellBox 房间」（认房间名里的 [HellBox）
        "src/self_name.lua",  # 2026-11-08：自定义自己的名字（self_name.txt），要在 p2_name 前面（p2 那层包在外面）
        "src/p2_name.lua",  # 2026-10-22：自定义本地 2P 名字（名字在 p2_name.txt）
        "src/front_unlock.lua",  # 2026-10-22：没开放的战线照样能选（front_unlock.txt）+ 报复打击概率（genocide.txt）
        "src/hellbox_qol.lua",
        "src/hellbox_dh.lua",  # 2026-11-21 HD1-038：来自 Dive Harder（Oct0pu5）的四项，开关在 HellBoxOptions，要在 hellbox_qol 后面
        "src/hellbox_hop.lua",  # 2026-11-20 HD1-035：半糖 HelldiversOptimization + BetterHUD（tools/make_hop.py 生成，设置 hop.txt 热生效）
        "src/hellbox_results.lua",
        "src/planet_refresh.lua",  # 2026-10-22：刷新星球（窗口按钮热发请求，下次打开战役地图重新生成）
        "src/profile_tool.lua",  # 2026-11-08：HellBox「角色」「队友」页：研究点、披风、游戏内右键给好友点赞（commend_friends.txt），状态每秒写回信箱表
        "src/ai_test.lua",  # HD1-021（2026-10-23）：自动测试开关（换种子、训练模式、放弃任务），信箱表热发命令，回显在界面表
        "src/ai_calibration.lua",  # 2026-10-30: opt-in no-enemy training calibration only
        # src/ai_tank_drill.lua（2026-11-01，-tank_drill N）2026-11-07 起不再打包：ai_drill.lua 认同一个老参数，两个一起装会互相抢
        "src/ai_drill.lua",  # 2026-11-07：HellBox 快速开局的出怪练习（-drill_mode only / seq，选中的怪、场上上限、节奏 1,2,…），训练关才生效
        "src/spawn_rules.lua",  # 2026-11-10 HD1-032：HellBox「出怪」页，警报/巡逻/报复关出什么怪热切换（信箱表 MAGIC_SPAWN）
        "src/enemy_params.lua",  # 2026-11-10 HD1-032：HellBox「怪物」页，按怪名改血量等设置（信箱表 MAGIC_PARAMS）
        "src/weapon_params.lua",  # 2026-11-14 V0.91：「数据修改」页武器属性块（data_live.lua 调 WeaponParamsMod.apply）
        "src/strat_params.lua",  # 2026-11-14 V0.91：「数据修改」页战备属性块（data_live.lua 调 StratParamsMod.apply）
        "src/player_params.lua",  # 2026-11-15：「数据」页「潜兵」（血量、速度、两种无敌；data_live.lua 调 PlayerParamsMod.apply）
        "src/data_live.lua",  # 2026-11-14 V0.91：「数据修改」页，每秒读 hellbox/data-live.txt 交给上面两个（要在它们后面）
        "src/ai_start_wave.lua",  # 2026-11-04：启动参数 -start_wave N 的训练关第一波就是第 N 波（冲锋虫第 5 波起才刷）
        "src/ai_clock.lua",  # 2026-11-05 HD1-028：报复关击杀数上方显示日志时间（gt）和剩余命数，看录像好对日志
        "src/ai_overlay.lua",  # 2026-11-11 HD1-030：游戏画面左边的半透明决策框（陪玩程序 ai\overlay.py 写信箱表 MAGIC_OVERLAY）
        "src/camera_link.lua",  # 2026-11-14：分屏（CameraCTRL）在游戏里自己发控制信号，不用开着 HellBox；没装分屏模块时什么都不做
        "src/training_loadout.lua",  # 2026-11-14：HellBox 开的训练关，出发前先弹原版选战备界面（HellBox 写 training-loadout.txt 标记）
        "src/hellbox_start.lua",  # 2026-11-16 V0.95：游戏开着、人在飞船上时 HellBox 训练直接进关（start-training.txt），要在 training_loadout 后面
        "src/hellbox_play.lua",
        "src/hellbox_drone_light.lua",  # 2026-11-20 HD1-035：鬼城里蜜蜂无人机带灯（借 hellbox_play 藏起来的灯，设置在 hop.txt），要在 hellbox_play 后面  # 2026-11-16 V0.95：「玩法」页（真训练场联机版 selected_trial + HellBox 版场上事件 / 换弹换枪，play.txt）
        "src/host_loadout.lua",  # 2026-11-18 V0.96：房主定配装（host-loadout.txt → 房间数据 hellbox_lo → 开 HellBox 的队友锁格子）
        "src/host_loadout_menu.lua",  # 2026-11-18 V0.97：选装备界面按格子画锁 / ???（照抄原版 draw_menu，要在 host_loadout 后面）
        "src/map_preview.lua",  # 2026-11-14：HellBox 训练模式的地图小方块图（按地图编号生成方块布局写到文件）
        "src/cursor_color.lua",  # 2026-11-03：瞄准指针 mod 的脚本部分（飘回角色的小十字换色，设置在 cursor_settings.json）
    ],
}

# 名字长度上限（UTF-8 字节）：
# - 房间名：Steam 房间数据最多 8192 字节，热改名的信箱表也是这么大
#   （room_name_live.NAME_MAX_BYTES、src/room_name.lua / self_name.lua / p2_name.lua 的 MAX_BYTES 要一致）
# - 我的名字、2P~4P 名字：游戏的 player_go 名字字段只存 51 字节（2026-11-08 用户实测，汉字 3 字节 = 17 个字），
#   多的被游戏切掉、别人也看不到（src/self_name.lua / p2_name.lua 的 NAME_BYTES 要一致）
NAME_MAX_BYTES = 8192
PLAYER_NAME_BYTES = 51

# 自定义房间名：一行文字，空 = 用"我的名字"，那个也空 = Steam 昵称（原版）。编译时填进 src/room_name.lua 的 "@ROOM_NAME@"
ROOM_NAME_FILE = os.path.join(HERE, "room_name.txt")

# 自定义自己（主手柄）的名字：空 = Steam 昵称（原版）。编译时填进 src/self_name.lua 的 "@SELF_NAME@"
SELF_NAME_FILE = os.path.join(HERE, "self_name.txt")

# 自定义本地 2P / 3P / 4P 名字（副手柄按加入先后排）：空 = "我的名字 #手柄号"（原版是 "Steam昵称 #手柄号"）。
# 编译时填进 src/p2_name.lua 的 "@P2_NAME@" / "@P3_NAME@" / "@P4_NAME@"
P2_NAME_FILE = os.path.join(HERE, "p2_name.txt")
PN_NAME_FILES = {2: P2_NAME_FILE, 3: os.path.join(HERE, "p3_name.txt"), 4: os.path.join(HERE, "p4_name.txt")}

# 解锁其他战线（已攻破 / 新赛季还没出场的都能选）："1" = 开，空 / 没有文件 = 原版。编译时填进 src/front_unlock.lua 的 "@FRONT_UNLOCK@"
FRONT_UNLOCK_FILE = os.path.join(HERE, "front_unlock.txt")

# 报复打击概率（百分比 0~100），空 = 原版 33%。编译时填进 src/front_unlock.lua 的 "@GENOCIDE@"
# 2026-11-04 以前它跟着战线开关（开 = 100%），所以第一次读到没有这个文件时：战线开着记成 100，关着记成原版
GENOCIDE_FILE = os.path.join(HERE, "genocide.txt")

# 游戏内右键菜单给 Steam 好友点赞："1" = 开，空 / 没有文件 = 原版（好友没有点赞）。编译时填进 src/profile_tool.lua 的 "@COMMEND_FRIENDS@"
COMMEND_FRIENDS_FILE = os.path.join(HERE, "commend_friends.txt")

# 带箱子上车（2026-11-13 用户要 HellBox「MOD 开关」页能单独开关）："0" = 关（搬箱子脚本用原版），空 / 没有文件 = 开
CARRY_VEHICLE_FILE = os.path.join(HERE, "carry_vehicle.txt")
CARRY_RES = "lua/character_states/character_state_carry"

# 瞄准指针 mod 的设置（cursor_mod.py 读写），变了要重编 src/cursor_color.lua
CURSOR_SETTINGS_FILE = os.path.join(HERE, "cursor_settings.json")


def _get_line(path):
    if not os.path.exists(path):
        return ""
    return read_text(path).lstrip("﻿").strip()


def _set_line(path, name, what, limit=NAME_MAX_BYTES):
    name = name.strip()
    if "\n" in name or "\r" in name:
        raise ValueError(T('{0}只能是一行。', what))
    if len(name.encode("utf-8")) > limit:
        raise ValueError(T('{0}太长了（最多 {1} 字节：汉字算 3，英文数字算 1）。', what, limit))
    if name != _get_line(path):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(name + "\n")


def get_carry_vehicle():
    return _get_line(CARRY_VEHICLE_FILE) != "0"


def set_carry_vehicle(on):
    _set_line(CARRY_VEHICLE_FILE, "" if on else "0", "开关", 1)


PRIVATE_SCRIPTS = {
    "ai_bridge.lua", "ai_terrain.lua", "ai_menu.lua", "ai_mech.lua", "ai_test.lua",
    "ai_calibration.lua", "ai_clock.lua", "ai_overlay.lua",
}


def is_public():
    return os.path.isfile(os.path.join(HERE, "public_release"))


def config_paths():
    names = (ROOM_NAME_FILE, SELF_NAME_FILE, *PN_NAME_FILES.values(), COMMEND_FRIENDS_FILE,
             FRONT_UNLOCK_FILE, GENOCIDE_FILE, CURSOR_SETTINGS_FILE, CARRY_VEHICLE_FILE,
             hellbox_options.FILE, __file__, hellbox_options.__file__, hellbox_hop.FILE, hellbox_hop.__file__)
    return [path for path in names if os.path.isfile(path)]


CSM_RES = "lua/character_states/character_state_machine"
# HD1-034（2026-11-19）录制接口：发行版也带 ai_bridge（眼睛）和 ai_mech（机制表），前后包一层休眠开关，
# 录制器开着（心跳文件新鲜）才采集；ai_mech 的锁血在 rec_gate_post 里关死。自用版不装这两个开关，陪玩照常一直采。
REC_SCRIPTS = ("ai_bridge.lua", "ai_mech.lua")
REC_GATE_PRE, REC_GATE_POST = "src/rec_gate_pre.lua", "src/rec_gate_post.lua"


def is_recorder_core():
    """录制器单独装的核心：只有原版状态机 + 录制接口，HellBox 别的功能一样都不带。"""
    return os.path.isfile(os.path.join(HERE, "recorder_core"))


def _with_rec_gate(paths):
    out = []
    for path in paths:
        name = os.path.basename(path)
        if name == "ai_bridge.lua":
            out.append(REC_GATE_PRE)
        out.append(path)
        if name == "ai_mech.lua":
            out.append(REC_GATE_POST)
    return out


def patches():
    """这次要换掉的脚本。"""
    if is_recorder_core():
        return {CSM_RES: _with_rec_gate([p for p in PATCHES[CSM_RES]
                                         if p.startswith(VANILLA) or os.path.basename(p) in REC_SCRIPTS])}
    out = dict(PATCHES)
    if is_public():
        for key, paths in out.items():
            paths = [path for path in paths
                     if os.path.basename(path) not in PRIVATE_SCRIPTS or os.path.basename(path) in REC_SCRIPTS]
            out[key] = _with_rec_gate(paths) if key == CSM_RES else paths
    # 2026-11-14 V0.91：带箱子上车改成热切换，搬箱子脚本一直装着（开关写在 options.txt，脚本里看 HellBoxCarryOn）
    return out


def write_live_options():
    """把 MOD 页的小功能开关 + 带箱子上车写成游戏每秒读的 options.txt（hellbox_qol.lua）。"""
    hellbox_hop.write_live(dev=not is_public())  # 2026-11-20 HD1-035：收进来的 QoL 功能（hop.txt）
    return hellbox_options.write_live(get_carry_vehicle())


def get_room_name():
    return _get_line(ROOM_NAME_FILE)


def set_room_name(name):
    _set_line(ROOM_NAME_FILE, name, "房间名")


def get_self_name():
    return _get_line(SELF_NAME_FILE)


def _player_names(changed=None):
    """当前 我的名字 + 2P~4P 名字（changed = {几P: 新名字}，0 = 我的名字），检查有没有重名（游戏靠名字认人）。"""
    names = {0: get_self_name(), **{n: _get_line(f) for n, f in PN_NAME_FILES.items()}}
    names.update({k: v.strip() for k, v in (changed or {}).items()})
    label = lambda n: "我的名字" if n == 0 else T('{0}P 名字', n)
    seen = {}
    for n in sorted(names):
        v = names[n]
        if v and v in seen:
            raise ValueError(T('{0}和{1}一样了。游戏靠名字认人，不能重名。', label(n), label(seen[v])))
        seen.setdefault(v, n)
    return names


def set_self_name(name):
    _player_names({0: name})
    _set_line(SELF_NAME_FILE, name, "我的名字", PLAYER_NAME_BYTES)


def get_pn_name(n):
    return _get_line(PN_NAME_FILES[n])


def set_pn_name(n, name):
    _player_names({n: name})
    _set_line(PN_NAME_FILES[n], name, T('{0}P 名字', n), PLAYER_NAME_BYTES)


def pn_mail():
    """热改名发给游戏的内容："2P名字\\n3P名字\\n4P名字"（src/p2_name.lua 认这个格式）。"""
    return "\n".join(get_pn_name(n) for n in (2, 3, 4))


def get_p2_name():
    return get_pn_name(2)


def set_p2_name(name):
    set_pn_name(2, name)


def get_commend_friends():
    return _get_line(COMMEND_FRIENDS_FILE) == "1"


def set_commend_friends(on):
    _set_line(COMMEND_FRIENDS_FILE, "1" if on else "", "开关", 1)


# 2026-11-23 用户定（V1.06）：解锁战线三选一。front_unlock.txt 存："" 关 / "1" 普通星区 / "home" 进攻母星 /
#   "se1"～"se3" 保卫超级地球（虫族 / 生化人 / 光能者）。后两种也带普通解锁（被攻破、没出场的战线照样能进）。
FRONT_MODES = ("", "1", "home", "se1", "se2", "se3")


def get_front_mode():
    v = _get_line(FRONT_UNLOCK_FILE)
    return v if v in FRONT_MODES else ""


def set_front_mode(mode):
    if mode not in FRONT_MODES:
        mode = ""
    if not os.path.exists(GENOCIDE_FILE):
        set_genocide(get_genocide())  # 旧设置跟战线走，只迁移一次
    _set_line(FRONT_UNLOCK_FILE, mode, "开关", 1)


def front_event():
    """给 front_unlock.lua 的事件部分："" / "home" / "se1"～"se3"。"""
    m = get_front_mode()
    return m if m != "1" else ""


def get_front_unlock():
    return get_front_mode() != ""


def set_front_unlock(on):
    set_front_mode("1" if on else "")


def get_genocide():
    """报复打击概率百分比（int）；None = 原版。"""
    if not os.path.exists(GENOCIDE_FILE):
        return 100 if get_front_unlock() else None
    s = _get_line(GENOCIDE_FILE)
    if not s.isdigit():
        return None
    return max(0, min(100, int(s)))


def set_genocide(percent):
    """percent = 0~100，None = 原版。"""
    s = "" if percent is None else str(max(0, min(100, int(percent))))
    if not os.path.exists(GENOCIDE_FILE) or s != _get_line(GENOCIDE_FILE):
        with open(GENOCIDE_FILE, "w", encoding="utf-8", newline="\n") as f:
            f.write(s + "\n")


def front_mail():
    """热切换时写进 front_unlock 信箱的内容（格式见 src/front_unlock.lua 文件头）。"""
    g = get_genocide()
    return f"f={1 if get_front_unlock() else 0};g={'' if g is None else g};e={front_event()}"


def lua_quote(text):
    """转成 Lua 字符串字面量：可打印 ASCII 原样，其余字节写成 \\ddd。"""
    out = []
    for b in text.encode("utf-8"):
        c = chr(b)
        out.append(c if 32 <= b < 127 and c not in '"\\' else f"\\{b:03d}")
    return '"' + "".join(out) + '"'


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def source_files(paths):
    """清单里真正在磁盘上的源文件（去掉 vanilla: 那几项），绝对路径。"""
    return [os.path.join(HERE, p) for p in paths if not p.startswith(VANILLA)]


# 录制器打包（ai/make_recorder.py）设成核对过的原版包（解压后）：录制核心只认原版，不看这台电脑游戏里装了什么
BASE_RAW_OVERRIDE = None
_raw_cache = {}


def _base_raw():
    """HellBox 接在哪个包上（解压后）：游戏当前启动包现在的样子，见 base_state()。"""
    if BASE_RAW_OVERRIDE is not None:
        return BASE_RAW_OVERRIDE
    st = base_state()
    if st["problem"]:
        raise RuntimeError(st["problem"])
    if _raw_cache.get("sha") != st["sha"]:
        raw, size = decompress(st["data"])
        _raw_cache.clear()
        _raw_cache.update(sha=st["sha"], raw=raw[:size])
    return _raw_cache["raw"]


def _lua_blob(raw, res):
    """包（解压后）里 res 这个脚本的资源数据（带 8 字节资源头）；没有返回 None。"""
    want = murmur64a(res.encode())
    for t, name, variants in parse(raw):
        if t == LUA and name == want:
            _lang, off, size = variants[0]
            return raw[off:off + size]
    return None


def vanilla_bytecode(res):
    """当前启动包里 res 这个脚本编译好的 bytecode（去掉资源头 8 字节）。"""
    blob = _lua_blob(_base_raw(), res)
    if blob is None:
        raise RuntimeError(f"游戏的启动包里没有 {res}")
    assert blob[8:11] == b"\x1bLJ", res
    return blob[8:]


def vanilla_source(res):
    """一段 Lua：把原版 bytecode 写成字符串常量，用 loadstring 原样跑（参数照传）。
    放在 do ... end 里，不多占拼接后整个文件的局部变量名额。游戏是 LuaJIT 2.0.3，带 loadstring。"""
    parts = []
    for c in vanilla_bytecode(res):
        parts.append(chr(c) if 32 <= c < 127 and c not in (34, 92) else "\\%03d" % c)
    return ("-- HellBox：原版 " + res + "（从玩家自己游戏里的原版脚本包取出，原样运行）\n"
            "do\n\tlocal vanilla = assert(loadstring(\"" + "".join(parts) + "\", \"@" + res + "\"))\n"
            "\tvanilla(...)\nend\n")


def source_text(path):
    """清单里一项的 Lua 文本：vanilla: = 原版（见 vanilla_source），其余读 mod 目录下的文件（去掉 BOM）。"""
    if path.startswith(VANILLA):
        return vanilla_source(path[len(VANILLA):])
    return read_text(os.path.join(HERE, path)).lstrip("﻿")


def steam_roots():
    """从注册表找 Steam 安装目录（可能有多个来源，去重保序）。"""
    import winreg
    roots = []
    for hive, key, value in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
        try:
            with winreg.OpenKey(hive, key) as k:
                path = os.path.normpath(winreg.QueryValueEx(k, value)[0])
        except OSError:
            continue
        if os.path.isdir(path) and path.lower() not in [r.lower() for r in roots]:
            roots.append(path)
    return roots


def steam_libraries():
    libs = []
    for root in steam_roots():
        libs.append(root)
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            for m in re.finditer(r'"path"\s+"([^"]+)"', read_text(vdf)):
                libs.append(os.path.normpath(m.group(1).replace("\\\\", "\\")))
    seen, out = set(), []
    for lib in libs:
        if lib.lower() not in seen and os.path.isdir(lib):
            seen.add(lib.lower())
            out.append(lib)
    return out


@functools.cache
def game_dir():
    """自动定位 Helldivers 安装目录：Steam 各个库里找 appmanifest_394510.acf 的 installdir。"""
    for lib in steam_libraries():
        apps = os.path.join(lib, "steamapps")
        installdir = "Helldivers"
        acf = os.path.join(apps, f"appmanifest_{STEAM_APP_ID}.acf")
        if os.path.exists(acf):
            m = re.search(r'"installdir"\s+"([^"]+)"', read_text(acf))
            if m:
                installdir = m.group(1)
        path = os.path.join(apps, "common", installdir)
        if os.path.exists(os.path.join(path, "contents", BUNDLE_NAME)):
            return path
    raise RuntimeError("没有找到 Helldivers 的安装目录（在 Steam 各个库里都没找到）。")


def game_bundle():
    return os.path.join(game_dir(), "contents", BUNDLE_NAME)


def read(path):
    with open(path, "rb") as f:
        return f.read()


def write(path, data):
    """2026-11-23：直接写。之前先写 .hellbox-tmp 再替换，但某些安全策略不让这个 exe 新建临时文件，
    会报 Permission denied（hop.tmp / ghost-maps.txt.hbtmp）。"""
    with open(path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def safe_copy(src, dst, to_game=False):
    """复制文件，同样先写临时文件再换上。to_game = 往游戏目录里放：换之前再查一次游戏开没开
    （装 MOD 要十几秒，中途有人开了游戏就停下，游戏文件保持原样）。"""
    with open(src, "rb") as f:
        data = f.read()
    if to_game and game_running():
        raise RuntimeError("装的过程中游戏被打开了，已停下，游戏文件没动。请关掉游戏再试。")
    try:
        write(dst, data)
    except PermissionError as e:
        raise RuntimeError("游戏文件被占用（游戏可能正在启动），已停下。请关掉游戏再试。") from e


def compile_lua(res, sources):
    """把 sources 拼接成一个文件（去掉各自的 BOM）后编译成 bytecode。"""
    base = os.path.join(HERE, "out", res.rsplit("/", 1)[-1])
    text = "\n".join(source_text(s) for s in sources)
    text = text.replace('"@ROOM_NAME@"', lua_quote(get_room_name()))
    text = text.replace('"@SELF_NAME@"', lua_quote(get_self_name()))
    for n in (2, 3, 4):
        text = text.replace(f'"@P{n}_NAME@"', lua_quote(get_pn_name(n)))
    text = text.replace('"@COMMEND_FRIENDS@"', lua_quote("1" if get_commend_friends() else ""))
    text = text.replace('"@FRONT_UNLOCK@"',lua_quote("1" if get_front_unlock() else ""))
    text = text.replace('"@FRONT_EVENT@"', lua_quote(front_event()))
    g = get_genocide()
    text = text.replace('"@GENOCIDE@"', lua_quote("" if g is None else str(g)))
    if '"@HELLBOX_OPTIONS@"' in text:
        text = text.replace('"@HELLBOX_OPTIONS@"', hellbox_options.lua_options(lua_quote))
    if '"@HELLBOX_HOP@"' in text:
        text = text.replace('"@HELLBOX_HOP@"', hellbox_hop.lua_defaults(lua_quote, dev=not is_public()))
    if '"@CURSOR_COLOR@"' in text:
        import cursor_mod  # 放这里避免互相 import
        text = text.replace('"@CURSOR_COLOR@"', lua_quote(cursor_mod.lua_setting()))
    with open(base + ".lua", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    # luajit -b 需要在它自己的 src 目录下运行才能找到 jit/bcsave.lua
    subprocess.run([LUAJIT, "-b", "-s", base + ".lua", base + ".ljbc"], check=True, cwd=os.path.dirname(LUAJIT),
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # HellBox.exe 里不闪黑窗口
    return read(base + ".ljbc")


def rebuild(raw, replace):
    """replace: {资源名哈希: 新 bytecode}。重新序列化所有资源，其余字节保持原样。"""
    n = struct.unpack_from("<I", raw, 0)[0]
    head = 4 + 256 + 16 * n
    out = [raw[:head]]
    off = head
    done = set()
    for _ in range(n):
        t, name, nv, so = struct.unpack_from("<QQII", raw, off)
        vs = [struct.unpack_from("<III", raw, off + 24 + 12 * i) for i in range(nv)]
        off += 24 + 12 * nv
        datas = []
        for lang, size, ss in vs:
            datas.append(raw[off:off + size])
            off += size
        if t == LUA and name in replace:
            assert nv == 1, "lua 资源只应有一个变体"
            old = datas[0]
            assert old[8:11] == b"\x1bLJ" and struct.unpack_from("<I", old, 0)[0] == len(old) - 8
            bc = replace[name]
            datas = [struct.pack("<I", len(bc)) + old[4:8] + bc]
            vs = [(vs[0][0], len(datas[0]), vs[0][2])]
            done.add(name)
        out.append(struct.pack("<QQII", t, name, nv, so))
        out += [struct.pack("<III", *v) for v in vs]
        out += datas
    assert done == set(replace), "有资源没找到"
    assert raw[off:].strip(b"\0") == b"", "资源之后的填充不是全 0"
    return b"".join(out)


def camera_enabled():
    """发行版、带了分屏模块时才叠分屏模块（自用版带本地 2P 的 AI，分屏只认一个本地玩家，不装）。"""
    return is_public() and os.path.isfile(CAMERA_LUAC)


VANILLA_BOOT = "resource_packages/boot"
DIVE_HARDER_BOOT = "resource_packages/boot_dh"
# 2026-11-21 HD1-038：装了 Dive Harder 不再停下，HellBox 跟着它的启动包装（见 core_bundle）；只剩启动包文件不在这一种拦
BOOT_MISSING_MSG = ("游戏的启动配置（contents\\settings.ini）指向的启动包不在游戏目录里（可能是别的 MOD 没装完或卸了一半），"
                    "游戏自己也开不了。请重装 / 卸载那个 MOD，或在 Steam 里验证游戏文件完整性，再打开「核心」。游戏文件没动。")
BASE_HAS_HELLBOX_MSG = ("游戏的启动包里已经有 HellBox 的脚本（以前整份替换装的旧版，又找不到原版备份），没法再往上装。"
                        "请在 Steam 里验证游戏文件完整性，再打开「核心」。")
BASE_BAD_MSG = "HellBox 认不出现在游戏的启动包（里面找不到要改的脚本）。请在 Steam 里验证游戏文件完整性，再打开「核心」。"


def boot_package():
    """游戏 contents/settings.ini 里顶层的 boot_package（去掉注释）；读不到返回 None。
    2026-11-19 发行抢先版：有玩家装了 Dive Harder（改成 boot_dh），分屏程序按它去找 Dive Harder 的启动包、报找不到文件；
    而且游戏开机走的不是原版启动包，HellBox 整个不生效。"""
    import re
    try:
        text = read_text(os.path.join(game_dir(), "contents", "settings.ini"))
    except (OSError, RuntimeError, UnicodeDecodeError):
        return None
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    m = re.search(r'^﻿?boot_package\s*=\s*"([^"]*)"', text, flags=re.M)
    return m.group(1) if m else None


def core_bundle():
    """游戏开机读的启动包（contents 里的文件名）。settings.ini 的 boot_package 是包名，文件名 = 包名的 murmur64a：
    原版 resource_packages/boot = 9e13b2414b41b842，Dive Harder 的 resource_packages/boot_dh = 05cd02202827e9a0。
    2026-11-21 HD1-038：HellBox 的核心补丁盖在它上面（以前只认原版那个，装了 Dive Harder 就停下）。读不到 = 原版。"""
    pkg = boot_package()
    if not pkg or pkg == VANILLA_BOOT:
        return BUNDLE_NAME
    return "%016x" % murmur64a(pkg.encode())


def core_path():
    return os.path.join(contents_dir(), core_bundle())


def check_boot():
    """启动配置指向的启动包不在游戏目录里：停下说清楚，什么都不动。"""
    if not os.path.isfile(core_path()):
        raise RuntimeError(BOOT_MISSING_MSG)


def _stamp(path):
    try:
        st = os.stat(path)
        return (path, st.st_size, st.st_mtime_ns)
    except OSError:
        return (path, None, None)


_base_cache = {}


def base_state():
    """HellBox 接在什么上面（2026-11-21 HD1-038）：游戏当前启动包现在的样子。
      - 原版：9e13 原文件；装了 QoL：QoL 换掉的 9e13（它改的 62 个脚本里没有我们改的那几个，补丁只顶替我们那几个）；
      - 装了 Dive Harder：它的 05cd…（9e13 的复制，character_state_machine 里接了它的代码，我们再接在后面）。
      - 以前「整份替换」装的老 HellBox（9e13 里只有我们的脚本和原版不同）：底子用原版备份（install 会先把原文件换回原版）。
    返回 {"bundle", "data"（压缩的整包）, "sha", "old_whole", "problem"（装不了的原因，没有 = None）}。
    按启动包和 9e13 的大小 / 修改时间缓存（状态检查每秒都调）。"""
    contents = contents_dir()
    name = core_bundle()
    path = os.path.join(contents, name)
    key = (_stamp(path), _stamp(game_bundle()), _stamp(BACKUP))
    if _base_cache.get("key") == key:
        return _base_cache["value"]
    st = {"bundle": name, "data": None, "sha": None, "old_whole": False, "problem": None}
    if not os.path.isfile(path):
        st["problem"] = tr(BOOT_MISSING_MSG)
    else:
        data = read(path)
        sha = hashlib.sha256(data).hexdigest()
        if name == BUNDLE_NAME and sha != VANILLA_BUNDLE_SHA256 and old_whole_file(data):
            st["old_whole"] = True
            if os.path.exists(BACKUP) and is_vanilla(BACKUP):
                data, sha = read(BACKUP), VANILLA_BUNDLE_SHA256
        st["data"], st["sha"] = data, sha
        try:
            raw, size = decompress(data)
            raw = raw[:size]
            for res in PATCHES:
                blob = _lua_blob(raw, res)
                if blob is None or blob[8:11] != b"\x1bLJ":
                    st["problem"] = tr(BASE_BAD_MSG)
                    break
                if b"HellBox" in blob:  # 我们每个版本的脚本里都有这个字样，原版 / QoL / Dive Harder 里没有
                    st["problem"] = tr(BASE_HAS_HELLBOX_MSG)
                    break
        except Exception:
            st["problem"] = tr(BASE_BAD_MSG)
    _base_cache["key"], _base_cache["value"] = key, st
    return st


OUT_BASE = OUT + ".base"  # 上次编译接在哪个包上：「包名 sha256」一行。底子变了（装 / 卸 QoL、Dive Harder）要重编


def base_matches():
    """上次编好的东西接的底子就是游戏现在的启动包。"""
    try:
        with open(OUT_BASE, encoding="utf-8") as f:
            text = f.read().split()
    except OSError:
        return False
    st = base_state()
    return text == [st["bundle"], st["sha"] or ""]


def base_kind(st=None):
    """给人看的：现在 HellBox 接在什么上面。"""
    st = st or base_state()
    if st["bundle"] != BUNDLE_NAME:
        return "Dive Harder" if st["bundle"] == "%016x" % murmur64a(DIVE_HARDER_BOOT.encode()) else tr("别的 MOD 的启动包")
    if st["sha"] == VANILLA_BUNDLE_SHA256:
        return tr("原版")
    return tr("改过的启动包（比如 QoL）")


def dive_harder_on():
    """游戏现在是不是从 Dive Harder 的启动包启动（2026-11-21 HD1-038：它在的话 HellBox 里来自它的几项让给它）。认不出就当没有。"""
    try:
        return core_bundle() == "%016x" % murmur64a(DIVE_HARDER_BOOT.encode())
    except Exception:
        return False


def stack_camera(raw):
    """把分屏模块叠进编好的脚本数据（解压后的整包，压缩之前）。2026-11-21 起用 camera_stack.py，不再调分屏 exe。"""
    try:
        return camera_stack.stack(raw)
    except camera_stack.CameraError as e:
        raise RuntimeError("分屏模块叠不进去：" + str(e))


def build():
    """编 HellBox 核心：底子 = 游戏当前启动包（原版 / QoL / Dive Harder，见 base_state），我们的脚本接在它的脚本后面；
    OUT_PATCH = 只含我们改的那几个资源的补丁，盖在当前启动包上。"""
    check_boot()
    st = base_state()
    if st["problem"]:
        raise RuntimeError(st["problem"])
    base = st["data"]
    raw, size = decompress(base)
    assert size <= len(raw)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    replace = {murmur64a(res.encode()): compile_lua(res, srcs) for res, srcs in patches().items()}
    new_raw = rebuild(raw[:size], replace)
    if camera_enabled():
        new_raw = stack_camera(new_raw)
    data = compress(new_raw, len(new_raw))
    write(OUT, data)
    import patch_files
    write(OUT_PATCH, patch_files.diff_patch(base, data))
    with open(OUT_BASE, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{st['bundle']} {st['sha']}\n")
    print(T('已生成 {0}（原始数据 {1} -> {2} 字节{3}）', OUT, size, len(new_raw), '，含分屏模块' if camera_enabled() else ''))
    return OUT


def game_running():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq helldivers.exe", "/NH"],
                       capture_output=True, text=True, errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return "helldivers.exe" in r.stdout.lower()


def only_patched_differ(game):
    """game 和原版备份相比，是否只有 PATCHES 里的脚本不同（= 装的是旧版本的 mod）。"""
    g, gs = decompress(game)
    b, bs = decompress(read(BACKUP))
    g, b = g[:gs], b[:bs]
    pg, pb = parse(g), parse(b)
    if [(t, n) for t, n, _ in pg] != [(t, n) for t, n, _ in pb]:
        return False
    patched = {murmur64a(res.encode()) for res in PATCHES} | {CAMERA_RES}
    for (t, n, vg), (_, _, vb) in zip(pg, pb):
        if [g[o:o + s] for _, o, s in vg] != [b[o:o + s] for _, o, s in vb] and not (t == LUA and n in patched):
            return False
    return True


def is_vanilla(path):
    try:
        return hashlib.sha256(read(path)).hexdigest() == VANILLA_BUNDLE_SHA256
    except OSError:
        return False


def share_backup():
    """本地备份和共用备份互相补齐（只搬核对过是原版的）。返回有没有可用的原版备份。"""
    try:
        if not os.path.exists(BACKUP) and is_vanilla(SHARED_BACKUP):
            os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
            safe_copy(SHARED_BACKUP, BACKUP)
        if os.path.exists(BACKUP) and not os.path.exists(SHARED_BACKUP) and is_vanilla(BACKUP):
            os.makedirs(os.path.dirname(SHARED_BACKUP), exist_ok=True)
            safe_copy(BACKUP, SHARED_BACKUP)
    except (OSError, RuntimeError):
        pass
    return os.path.exists(BACKUP) and is_vanilla(BACKUP)


def has_vanilla_backup():
    return share_backup()


def open_steam_verify():
    """让 Steam 检查并修复 HELLDIVERS 的游戏文件（改过的文件会重新下载原版）。"""
    os.startfile(f"steam://validate/{STEAM_APP_ID}")


def contents_dir():
    return os.path.join(game_dir(), "contents")


def old_whole_file(game):
    """游戏原文件是以前「整份替换」装法装的 HellBox（或录制器的核心）：只有我们改的脚本和原版不同。"""
    if os.path.exists(OUT) and game == read(OUT):
        return True
    return os.path.exists(BACKUP) and only_patched_differ(game)


def status():
    """返回 "on"（已装当前 mod）/ "old"（已装旧版 mod）/ "off"（没装 HellBox）/ "unknown"（对不上）。
    2026-11-20 HD1-036 起装的是补丁：HellBox 的补丁在、游戏读得到、内容是最新编的才算 "on"。
    2026-11-21 HD1-038 起补丁盖在游戏当前启动包上（原版 / QoL / Dive Harder），底子换了也算旧版。
    以前整份替换装的老用户算 "old"（关游戏后自动重装，换成补丁装法）。"""
    import patch_files
    share_backup()
    # 2026-11-21 HD1-038：不再只认原版。装了 QoL（9e13 被换掉）、Dive Harder（启动包换成它的）都照常装，
    #   HellBox 跟着游戏当前启动包走（base_state）。只有认不出启动包 / 里面已经有 HellBox 才算 "unknown"。
    st = base_state()
    if st["old_whole"]:
        return "old"
    if st["problem"]:
        return "unknown"
    contents = contents_dir()
    bundle = st["bundle"]
    if not patch_files.installed(contents, bundle):
        # 我们的核心补丁在别的包上（装上 / 卸掉 Dive Harder 以后启动包换了）→ 旧版，关游戏后自动挪到现在的启动包上
        if any(b != bundle and patch_files.installed(contents, b) for b in patch_files.ours("core")):
            return "old"
        return "off"
    # 补丁不是最新编的 / 被 Obsidian 清除时下面留了洞、游戏读不到 / 底子换了（装上或卸掉 QoL）→ 旧版（关游戏后自动重装）
    if (not os.path.exists(OUT_PATCH) or not patch_files.current(contents, bundle, data=read(OUT_PATCH))
            or not base_matches()):
        return "old"
    # 2026-11-15：新版 HellBox 盖在旧文件夹上时，out 还是旧的那次编译，以前就报「已装好」不更新。
    # 源码比上次编译新 = 游戏里是旧版（关游戏后 HellBox 自动更新）
    # 只看代码（改名字、指针这类设置不算：那些游戏开着也能热改，不该说「旧版」）
    if code_is_stale():
        return "old"
    # 2026-11-18 V0.98：鬼城配色没换好 / 被 Steam 验证改回去了，也当旧版（关游戏后自动重装）。只比文件大小，很快
    import ghost_maps
    return "old" if ghost_maps.stale(contents) else "on"


def code_is_stale():
    """编好的脚本比 MOD 代码旧（新版 HellBox 盖在旧文件夹上、还没重新装过）。不看设置文件。"""
    if not os.path.exists(OUT):
        return False
    t = os.path.getmtime(OUT)
    srcs = [s for paths in patches().values() for s in source_files(paths)]
    # 2026-11-19：分屏换了新的（作者新版 / 我们改镜头；2026-11-21 起看 runtime.luac 和 camera_stack.py）也算旧版，否则一直显示已装好、游戏里还是旧分屏
    if camera_enabled():
        srcs += [CAMERA_LUAC, camera_stack.__file__]
    return any(os.path.isfile(s) and os.path.getmtime(s) > t for s in srcs)


def out_is_stale():
    if not os.path.exists(OUT) or not os.path.exists(OUT_PATCH) or not base_matches():
        return True
    t = os.path.getmtime(OUT)
    srcs = [s for paths in patches().values() for s in source_files(paths)] + [os.path.abspath(__file__)]
    if camera_enabled():
        srcs += [CAMERA_LUAC, camera_stack.__file__]
    srcs += config_paths()
    return any(os.path.getmtime(s) > t for s in srcs)


# 2026-11-19 发行抢先版（用户定）：第一次开核心时弹窗选要不要备份 45 个原版地图包（约 1.3GB）。
#   选了记在 %APPDATA%/…/hellbox/map-backup.txt（1 = 备份，0 = 不备份）；已经有地图备份的老用户当作选了备份、不再问。
#   不备份：装得快，恢复原版时地图包还不回去，要 Steam 验证游戏文件完整性（启动脚本的小备份 2.5MB 照旧都留）。
PROGRESS = None  # HellBox 设成回调：装的时候报「鬼城地图：几 / 45」


def _map_choice_path():
    import ghost_maps
    return os.path.join(ghost_maps.GAME_DIR, "map-backup.txt")


def map_backup_choice():
    """True = 备份地图包，False = 不备份，None = 还没选过（也没有地图备份）。
    2026-11-20 HD1-036 起鬼城配色也是补丁，地图原文件不动、不用备份：永远不再问（返回 False）。"""
    return False
    try:
        v = read_text(_map_choice_path()).strip()
        if v in ("0", "1"):
            return v == "1"
    except OSError:
        pass
    import ghost_maps
    return True if ghost_maps.has_backup() else None


def set_map_backup_choice(on):
    p = _map_choice_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("1" if on else "0")


def install():
    if game_running():
        raise RuntimeError("游戏正在运行，请先关闭游戏。")
    check_boot()  # 启动配置指向的包不在：说清楚、什么都不动
    st = status()
    if st == "unknown":
        raise RuntimeError(base_state()["problem"] or tr(BASE_BAD_MSG))
    import patch_files
    contents = contents_dir()
    if base_state()["old_whole"]:
        # 2026-11-20 HD1-036：以前整份替换装的，先把原文件换回原版，再改用补丁
        share_backup()
        if not (os.path.exists(BACKUP) and is_vanilla(BACKUP)):
            raise RuntimeError("以前的 HellBox 是整份换游戏文件装的，现在改成补丁装法，要先换回原版文件，但没找到原版备份。"
                               "请在 Steam 里验证游戏文件完整性，再打开「核心」。")
        safe_copy(BACKUP, game_bundle(), to_game=True)
    if not os.path.exists(BACKUP) and is_vanilla(game_bundle()):  # 原版脚本包的小备份（2.7MB）：录制器、老用户换回原版要用
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)       # （2026-11-21 起只备份原版；装了 QoL 时不把 QoL 的当原版存）
        safe_copy(game_bundle(), BACKUP)
        print(T('已备份原版到 {0}', BACKUP))
        share_backup()  # 也放一份到共用备份
    if out_is_stale():
        build()
    bundle = base_state()["bundle"]
    patch_files.put(contents, bundle, read(OUT_PATCH), "core", still_ok=lambda: not game_running())
    # 2026-11-21 HD1-038：启动包换过（装上 / 卸掉 Dive Harder）→ 留在旧启动包上的核心补丁拿掉（不碰别人的）
    for old in patch_files.ours("core"):
        if old != bundle:
            try:
                patch_files.take_out(contents, old, still_ok=lambda: not game_running())
            except OSError:
                pass  # 旧启动包连同补丁被别人删了之类：不影响这次装
    # 2026-11-18 V0.98 鬼城：45 个地图包里的配色换成带 ghost_town 的（2026-11-20 起也是补丁，见 ghost_maps.py）
    import ghost_maps
    ghost_maps.install(contents, still_ok=lambda: not game_running(), progress=PROGRESS)
    patch_files.tidy_all(contents)
    try:
        write_live_options()
    except OSError:
        pass
    print("已安装到游戏目录。")


def drop_room_status():
    """删掉游戏回报的房间状态 room-status.txt（只这一个文件）：脚本换回原版后没人再更新它，留着下次开游戏会被当成真房间名。"""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return
    try:
        os.remove(os.path.join(appdata, "Arrowhead", "Helldivers", "hellbox", "room-status.txt"))
    except OSError:
        pass


def restore():
    if game_running():
        raise RuntimeError("游戏正在运行，请先关闭游戏。")
    import patch_files
    contents = contents_dir()
    # 2026-11-20 HD1-036：拿掉我们的补丁（上面还有别的工具的补丁就换成空补丁占位，不留洞）
    # 2026-11-21 HD1-038：核心补丁可能在 9e13 或 Dive Harder 的启动包上，记录里我们的都拿掉
    for bundle in set(patch_files.ours("core")) | {BUNDLE_NAME}:
        try:
            patch_files.take_out(contents, bundle, still_ok=lambda: not game_running())
        except OSError:
            pass
    # 原文件不是原版时，只有「以前整份替换装的 HellBox」才照备份换回；装了 QoL（它换掉的 9e13）等别人的文件一个字节不动
    game = read(game_bundle())
    if hashlib.sha256(game).hexdigest() != VANILLA_BUNDLE_SHA256 and old_whole_file(game):
        if not os.path.exists(BACKUP):
            raise RuntimeError("没有找到原版备份，没法还原（可以用 Steam 验证游戏文件完整性）。")
        if not is_vanilla(BACKUP):
            raise RuntimeError("备份的文件不是原版，没有用它还原。请用 Steam 验证游戏文件完整性。")
        safe_copy(BACKUP, game_bundle(), to_game=True)
    import ghost_maps  # 鬼城：拿掉配色补丁；以前整份换过的地图包照备份拷回去
    _n, left = ghost_maps.restore(contents)
    patch_files.tidy_all(contents)
    drop_room_status()
    print("已还原原版文件。")
    return left  # 没有备份、还不回去的地图包个数（装的时候选了不备份）：HellBox 提示去 Steam 验证


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "restore":
        restore()
    elif cmd == "install":
        install()
    elif cmd == "status":
        print(game_dir())
        print(status())
    else:
        build()


if __name__ == "__main__":
    main()
