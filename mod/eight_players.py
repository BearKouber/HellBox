"""8 人房间（HD1-039，2026-11-26 用户定：上限 8 人、不用选人数、开了就是 8 人；有原版玩家在就按 4 人）。

游戏脚本里「4 个玩家」是写死的数字。这里不重写原版函数：装的时候取玩家自己游戏里编译好的原版脚本，
只把指定位置的 4 改成 8（字节长度不变），其余一个字节不动。规则部分（原版玩家在就按 4 人、救援一次最多 4 人、
第 5～8 人的颜色和面板位置、装备界面先画自己那一栏）在 src/hellbox_8p.lua。

每个脚本先核对是不是原版（sha256）；被别的 MOD 改过就不装，告诉玩家是哪个脚本。
位置怎么找的：.work/hd1-039（Neuro 文档仓库）里的 sites.py / show8.py，按「函数序号 / 指令序号」记。
"""
import hashlib
import struct

import ljbc
from bundle import LUA, murmur64a, parse

# 资源名 -> 原版 bytecode 的 sha256
VANILLA_SHA = {
    "lua/hud/hud": "e8d30b08182c91b4a28a319175cc0242273f5a0251196164f9e0798360d76384",
    "lua/states/state_game": "cc8012866f578bc34fa6c1e251ad3b83c55e57df39ffe0d00eab1eb59bd91494",
    "lua/states/state_menu": "da14bc28a003c2e126381a74f52d9efd055f12e044c4342fb483e260805a24df",
    "lua/states/state_mission_start": "9e6f89081fbbe33883de2cdc7c5f5bdac59604c2ea42c1076fdeed303c55e809",
    "lua/states/state_mission_end": "7c15df5e20d46d81badcd8c0fe42dd266a8098396a6820f85362047a6a5afdb3",
    "lua/states/state_season_end": "f413f389323bff28b2617d0b9d481768c15ff7702812a18a12a0c6313b52748e",
    "lua/menu/menu_screen_loadout": "541f1724e2ea37644af893442fb0db056a743cc6ca197e59f71a898c7626d1e0",
    "lua/menu/menu_screen_campaign_multiplayer": "cb4b74291bdc9a1d4716b25dedb5dd79206b77f87146b66910103c88ca5c26a9",
    "lua/menu/menu_screen_multiplayer_back": "6968e67c482e29b481d721f96df4f4c8f4e1e77295c2617ddeb283f7bee0e2ae",
}

# KSHORT r 4 -> KSHORT r 8：(函数序号, 指令序号)
KSHORT_SITES = {
    # 每人一块面板、地图界面、对话框的 GUI 和循环
    "lua/hud/hud": [(4, 33), (5, 66), (7, 62), (25, 10), (25, 45), (64, 1)],
    # 玩家表 8 格；手柄中途加入；有人申请加入 / 换关卡重进时的人数检查
    "lua/states/state_game": [(2, 516), (13, 246), (57, 50), (60, 51)],
    "lua/states/state_menu": [(4, 1335), (12, 155), (74, 62), (80, 62)],
    "lua/states/state_mission_start": [(3, 494), (22, 46), (22, 151)],
    "lua/states/state_mission_end": [(1, 1169), (47, 38)],
    "lua/states/state_season_end": [(3, 590)],
    # 装备界面：8 份选装备数据和 GUI（画出来的还是 4 栏，第 4 个函数的第 99 条画 4 块底板，不改）
    "lua/menu/menu_screen_loadout": [(1, 75), (1, 156), (4, 2), (4, 39)],
    # 好友加入 / 本地手柄加入的人数检查、找房间时服务器那头「人数 < 8」、建房人数
    # （房间列表「x/4」、进房前「4 - 房间人数」、隐藏满员房间：2026-11-26 改成按每个房间自己的上限，见 ROOM_MAX 和 hellbox_8p.lua）
    "lua/menu/menu_screen_campaign_multiplayer": [(6, 370), (8, 266), (8, 453), (24, 147), (26, 606)],
    "lua/menu/menu_screen_multiplayer_back": [(3, 71)],
}

# 数字常量 4 -> 8：(函数序号, 常量序号)。2026-11-26 起没有了：原来改的「4 - 房间人数」「隐藏满员：人数 == 4」
#   让原版房间也按 8 人算（显示 n/8、4 人时进不去），改成 hellbox_8p.lua 按每个房间的上限算
KN_SITES = {}
# 房间列表「x/4」：draw_rooms_info 里 string_format(..., "#MAX_PLAYERS", 4) 的 4（KSHORT 44 4），
#   改成读这个房间的 room["#MAX_PLAYERS"]（TGETS 44 31 "#MAX_PLAYERS"；房间表在 31 号寄存器，
#   前两条 TGETS 42 31 "num_players" 核对；键名借这个函数里已有的字符串常量）。hellbox_8p.lua 给每个房间填 8 / 4。
ROOM_MAX = ("lua/menu/menu_screen_campaign_multiplayer", 13, 433, 44, 31, "#MAX_PLAYERS", 431, 42, "num_players")

# 装备界面画哪 4 栏：原版是写死的表 {1, 2, 3, 4}（TDUP），第 5～8 人自己那一栏画不出来、选的装备也发不出去。
#   改成读全局变量（GGET），名字借这个函数里已有的字符串常量 favorite_loadout_index（游戏里没有同名全局变量），
#   src/hellbox_8p.lua 每帧把「自己的栏在前、再按顺序补满 4 栏」写进去。
LOADOUT_ORDER = ("lua/menu/menu_screen_loadout", 4, 177, 10, 28, "favorite_loadout_index")


class NotVanilla(RuntimeError):
    pass


def _set_kshort(buf, p, k):
    at, op, _a, d = ljbc.ins(buf, p, k)
    if op != "KSHORT" or d != 4:
        raise RuntimeError(f"位置不对：第 {k} 条是 {op} {d}")
    struct.pack_into("<H", buf, at + 2, 8)


def _set_kn(buf, p, i):
    value, at, is_int = p.kn[i]
    if not is_int or value != 4 or buf[at] != 0x08:
        raise RuntimeError(f"常量不对：第 {i} 个是 {value}")
    buf[at] = 0x10  # 整数常量的写法是 (值 << 1)，4 -> 8 都是一个字节


def _set_order(buf, ps):
    _res, pi, k, a, d, name = LOADOUT_ORDER
    p = ps[pi]
    at, op, ra, rd = ljbc.ins(buf, p, k)
    if op != "TDUP" or ra != a or rd != d or ljbc.kgc_str(p, rd) != ("table",):
        raise RuntimeError(f"装备界面的栏位表不对：第 {k} 条是 {op} {ra} {rd}")
    nd = ljbc.kgc_index(p, name)
    if nd is None:
        raise RuntimeError("装备界面里找不到常量 " + name)
    buf[at] = ljbc.OP["GGET"]
    struct.pack_into("<H", buf, at + 2, nd)


def _set_room_max(buf, ps):
    _res, pi, k, a, room, key, k_chk, a_chk, key_chk = ROOM_MAX
    p = ps[pi]
    _at, op, ca, cd = ljbc.ins(buf, p, k_chk)
    if op != "TGETS" or ca != a_chk or cd >> 8 != room or ljbc.kgc_str(p, cd & 0xFF) != key_chk:
        raise RuntimeError(f"房间列表的房间寄存器不对：第 {k_chk} 条是 {op} {ca} {cd}")
    at, op, ra, rd = ljbc.ins(buf, p, k)
    if op != "KSHORT" or ra != a or rd != 4:
        raise RuntimeError(f"房间列表的人数上限不对：第 {k} 条是 {op} {ra} {rd}")
    c = ljbc.kgc_index(p, key)
    if c is None or c > 0xFF:
        raise RuntimeError("房间列表里找不到常量 " + key)
    buf[at] = ljbc.OP["TGETS"]
    buf[at + 2] = c  # ABC 格式：op A C B
    buf[at + 3] = room


def patch(res, bc):
    """原版 bytecode -> 8 人版 bytecode（长度不变）。"""
    if hashlib.sha256(bc).hexdigest() != VANILLA_SHA[res]:
        raise NotVanilla(res)
    buf = bytearray(bc)
    ps = ljbc.protos(bc)
    for pi, k in KSHORT_SITES.get(res, ()):
        _set_kshort(buf, ps[pi], k)
    for pi, i in KN_SITES.get(res, ()):
        _set_kn(buf, ps[pi], i)
    if res == LOADOUT_ORDER[0]:
        _set_order(buf, ps)
    if res == ROOM_MAX[0]:
        _set_room_max(buf, ps)
    assert len(buf) == len(bc)
    return bytes(buf)


def replacements(raw):
    """raw = 解压后的启动包。返回 {资源名哈希: 8 人版 bytecode}，给 build.rebuild 用。
    哪个脚本不是原版就抛 NotVanilla（参数是资源名）。"""
    want = {murmur64a(res.encode()): res for res in VANILLA_SHA}
    out = {}
    for t, name, variants in parse(raw):
        if t == LUA and name in want:
            _lang, off, size = variants[0]
            blob = raw[off:off + size]
            out[name] = patch(want[name], bytes(blob[8:]))
    missing = set(want) - set(out)
    if missing:
        raise NotVanilla(want[missing.pop()])
    return out


if __name__ == "__main__":
    # 自检：用原版备份走一遍，数一数改了几个字节
    import os
    import sys
    from bundle import decompress
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup", "9e13b2414b41b842")
    raw, size = decompress(open(path, "rb").read())
    raw = raw[:size]
    names = {murmur64a(r.encode()): r for r in VANILLA_SHA}
    olds = {}
    for t, name, variants in parse(raw):
        if t == LUA and name in names:
            _l, off, sz = variants[0]
            olds[name] = raw[off + 8:off + sz]
    total = 0
    for name, new in replacements(raw).items():
        diff = sum(1 for a, b in zip(olds[name], new) if a != b)
        total += diff
        print(f"{names[name]}: {diff} 字节")
    print("合计", total, "字节")
