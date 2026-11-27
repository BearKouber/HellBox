r"""读取游戏里 ai_bridge mod 写出的状态表（"眼睛"）。

mod 在游戏内每帧把玩家/敌人状态写进一张固定大小的 Lua 数字表（每格一个 double）。
这里在游戏进程内存里找一次表头魔数，之后每次直接整块读出来。只读，不写游戏内存。
表布局见 mod\src\ai_bridge.lua，两边要一致。

    from bridge import Bridge
    b = Bridge.attach()          # 默认找 helldivers.exe
    snap = b.read()              # Snapshot 或 None（表还没更新）
"""
import ctypes
import math
import struct
import time
from ctypes import wintypes
from dataclasses import dataclass, field

VERSION = 16
# 能读的表的版本：16 = 8 个玩家（HellBox 8 人房间，各"每人一块"的区都变 8 块，起点跟着挪；任务区、飞船区里第 5～8 个人
# 的那几格在表尾 M20 区），15 = 再带冲锋虫射线区（M19），14 = 带盾量区（M18），13 = 没装新 mod 的旧表（盾量当“读不到”）。
# 旧表只读到自己的表尾为止，多读会读到表的后面别人的内存，所以各版长度分开算（LAYOUTS）。
VERSIONS = (13, 14, 15, 16)
MAGIC_VALUES = (48151623.5, -271828.125, 7340.0078125, 1099511627776.25)
MAGIC = struct.pack("<4d", *MAGIC_VALUES)
PF = 24
MAX_ENEMIES, EF = 96, 16
WF = 40
MAX_STRINGS, SL = 512, 40   # 第 7 版从 128 条加到 512 条（字符串区后面各区的起点都跟着挪了）
ERR_LEN = 200
MF = 140                 # 第 4 版（2026-10-12）：任务区，归任务撤离线，格子含义见 ai_bridge.lua 的 write_mission
SHF = 80                 # 第 5 版（2026-10-12）：飞船区，空投舱座位和"互动"对着什么，格子含义见 ai_bridge.lua 的 write_ship
# 第 6 版（2026-10-13，情况总方案第二阶段，只加 P0 的三区；格子含义见 ai_bridge.lua 的 write_input / write_status / write_sight）
INF = 8                  # M1 玩家输入区：区版本 + 每人 INF
STF = 12                 # M2 玩家状态补充区：区版本 + 每人 STF
SIF = 115                # M4 视线区：区版本、出错次数、留空 + 每人 SIF（sight.feed_block 解）
# 第 7 版（2026-10-14，情况总方案 P1 第一批；格子含义见 ai_bridge.lua 的 write_status / write_weapons_extra / write_bugs /
# write_drops / write_team / write_strats / write_camera 上面）。每区第 0 格是区版本（1 = 写好了），交给各组的 *_raw 都去掉了这一格。
WXW = 14
WXF = 1 + 3 * WXW        # M3 武器补充区：每人 unit_id + 3 把 × WXW
EXF = 15                 # M6 虫子补充区：96 只 × EXF（和敌人区同序）
MAX_DROPS, DRF = 32, 9   # M8 掉落物区
TMF = 6                  # M9 队友和增援区：每人 TMF + 全队 3 格
MAX_STRATS, STW = 8, 6
SGF = 1 + MAX_STRATS * STW   # M10 战略配备区：每人 unit_id + 8 × STW，之后信标 MAX_BEACONS × BCF
MAX_BEACONS, BCF = 8, 8
CMF = 8                  # M12 镜头区
# 第 8 版（2026-10-14 / 15，情况总方案 P1 第三批；三条改 mod 的合成一版，区顺序 M11 → M15 → M5，2026-10-15 合并时排）
MAX_HAZ, HZF = 32, 13    # M11 友方伤害源区
RK_RAYS = 16
RKF = 1 + RK_RAYS        # M15 石头区：每人 unit_id + 16 个方向距离
ARF = 15                 # M5 弧线区：每人 unit_id + 14 格（arc.arc_result 解；格子含义见 ai_bridge.lua 的 write_arc 上面）
BLF = 49  # 基础 8 格 + 受伤区数量（-1 未知）+ 8 个 (enabled,min,max,armor_min,max)
LGF, MVF = 18, 10
# 第 14 版（2026-11-01，HD1-023 冲锋虫节奏模块）：M18 玩家盾量区，接在表尾，格子含义见 ai_bridge.lua 的 write_shield
SDF = 5                  # 每个玩家：unit_id + 盾量 + 盾上限 + 盾开着 + 充能计时器
# 第 15 版（2026-11-04，HD1-023 冲锋虫冲不冲）：M19 冲锋虫射线区，接在表尾，格子含义见 ai_bridge.lua 的 write_tankrays
MAX_TR, TRF = 8, 10      # 每只：unit_id、前 / 左 / 右触须、左 / 右肩通、离最近的人、目标角（弧度）、减速、本机算的
# 第 16 版（2026-11-26，HD1-039 8 人房间）：M20 第 5～8 个人在任务区、飞船区放不下的那几格，每人 XF 格：
# +0 +1 名单手柄编号、已上机 +2 +3 +4 在碰什么、x、y +5 +6 互动对着不对着舱、第几个舱
XF, FIX_PLAYERS = 7, 4


def _layout(mp):
    """mp 个玩家时各区的起点（Lua 下标，和 ai_bridge.lua 一样的算法）。"""
    class L:
        pass
    L.MAX_PLAYERS = mp
    L.P0 = 17
    L.E0 = L.P0 + mp * PF
    L.W0 = L.E0 + MAX_ENEMIES * EF
    L.S0 = L.W0 + mp * WF
    L.ERR0 = L.S0 + MAX_STRINGS * SL
    L.M0 = L.ERR0 + ERR_LEN
    L.SH0 = L.M0 + MF
    L.IN0 = L.SH0 + SHF
    L.ST0 = L.IN0 + 1 + mp * INF
    L.SI0 = L.ST0 + 1 + mp * STF
    L.WX0 = L.SI0 + 3 + mp * SIF
    L.EX0 = L.WX0 + 1 + mp * WXF
    L.DR0 = L.EX0 + 1 + MAX_ENEMIES * EXF
    L.TM0 = L.DR0 + 1 + MAX_DROPS * DRF
    L.SG0 = L.TM0 + 1 + mp * TMF + 3
    L.CM0 = L.SG0 + 1 + mp * SGF + MAX_BEACONS * BCF
    L.HZ0 = L.CM0 + 1 + CMF
    L.RK0 = L.HZ0 + 1 + MAX_HAZ * HZF
    L.AR0 = L.RK0 + 1 + mp * RKF
    L.BL0 = L.AR0 + 1 + mp * ARF
    L.LG0 = L.BL0 + 1 + MAX_ENEMIES * BLF
    L.MV0 = L.LG0 + 1 + MAX_ENEMIES * LGF
    L.N13 = L.MV0 + 1 + mp * MVF         # 第 13 版表的长度
    L.SD0 = L.N13 + 1                    # M18：+0 区版本 +1 本区出错次数，之后每人 SDF 格
    L.N14 = L.SD0 + 1 + mp * SDF         # 第 14 版表的长度
    L.TR0 = L.N14 + 1                    # M19：+0 区版本 +1 本区出错次数，之后 MAX_TR × TRF 格
    L.N15 = L.TR0 + 1 + MAX_TR * TRF     # 第 15 版表的长度
    L.X0 = L.N15 + 1                     # M20（第 16 版）：+0 区版本，之后 (mp - 4) × XF 格
    L.N16 = L.X0 + 1 + (mp - FIX_PLAYERS) * XF
    return L


L4, L8 = _layout(4), _layout(8)
# 版本 → (布局, 表长)
LAYOUTS = {13: (L4, L4.N13), 14: (L4, L4.N14), 15: (L4, L4.N15), 16: (L8, L8.N16)}
MAX_PLAYERS = L8.MAX_PLAYERS    # 最多几个玩家（第 16 版的；旧表 4 个）
HEAD = 8                        # 表头格数：魔数 4 + 版本 + 帧号 + 帧号副本 + dt
PLAYER_SPEED_LIMIT = 12.0  # 正常地面速度留足冲刺、位移技能余量；首次同步会短暂出现数百 m/s

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.WORD),
                ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]


def find_pid(name):
    import pymem.process
    p = pymem.process.process_from_name(name)
    return p.th32ProcessID if p else None


def sanitize_player_velocity(vel_x, vel_y, limit=PLAYER_SPEED_LIMIT):
    """远端首次同步时速度会由数百 m/s 指数衰减，但位置不动；坏值不能进入跟随和危险预测。"""
    if (
        math.isfinite(vel_x)
        and math.isfinite(vel_y)
        and math.hypot(vel_x, vel_y) <= limit
    ):
        return vel_x, vel_y, False
    return 0.0, 0.0, True


@dataclass
class PlayerInput:
    """游戏这一帧读到的这个人的按键（mod申请清单 M1）。"""
    fire: bool          # 开火键按着
    aim: bool           # 举枪（瞄准键 / 右摇杆）
    move_x: float       # 移动方向（-1~1）
    move_y: float
    aim_x: float        # 瞄准方向（-1~1）
    aim_y: float
    shot: bool          # 这一帧开出了子弹（同一把枪弹匣比上一帧少）


@dataclass
class PlayerStatus:
    """玩家状态补充（mod申请清单 M2；读不到是 -99）。第 7 版补上 P1 的几样（老 mod 时是默认值 -99）。"""
    presses: float      # 倒地自救已按几下
    needed: float       # 要按几下
    downed_for: float   # 倒地多久（秒），没倒地 -1
    prone_for: float    # 趴下多久（秒），没趴 -1
    reset_timer: float  # 自救清零倒计时
    getup_left: float = -99.0   # 第 7 版：趴下后起身还剩多久（秒），没在起身 -1
    burning: int = -99          # 第 7 版：着火 1 / 0
    slow: float = -99.0         # 第 7 版：减速倍率（1 = 不减速；水 0.55、雪 0.65）
    slow_source: str = ""       # 第 7 版：减速来源（status 模板名，如 difficult_water；不减速或读不到是空串）
    poisoned: int = -99         # 第 7 版：中毒 / 持续伤害（damage 类状态）1 / 0
    since_hit: float = -99.0    # 第 7 版：最近一次挨打距今（秒，mod 看血量变少算的），没挨过打 -1


@dataclass
class Player:
    slot: int
    pad: int            # 手柄编号：-1 = 没有（键盘），0.. = 手柄
    x: float
    y: float
    z: float
    face_x: float
    face_y: float
    vel_x: float
    vel_y: float
    aim_x: float
    aim_y: float
    hp: float
    max_hp: float
    downed: bool
    dead: bool
    dodging: bool       # 趴下/闪避中（敌人发现距离减半，特斯拉塔会跳过）
    state: str          # 角色状态，如 CharacterStateIdle / CharacterStateMelee
    melee_time: float   # 近战冷却剩余秒数，<= 0 可以再出近战；-99 = 没有近战武器
    melee_duration: float
    melee_radius: float
    stamina: float
    time_outside_screen: float
    unit_id: int
    aiming: bool
    weapon: Weapon = None   # 手上那把枪；没拿东西是 None
    input: PlayerInput = None    # 第 6 版 M1：游戏读到的按键；读不到是 None
    status: PlayerStatus = None  # 第 6 版 M2：自救进度、倒地 / 趴下计时；读不到是 None
    sight: tuple = None          # 第 6 版 M4：从这个人身上拉的视线，原样 115 格（sight.feed_block 解）；这一块没数是 None
    # 第 7 版 M3：这个人的主武器、副武器、支援武器，3 × 14 格（去掉了 unit_id），每把的格子见 ai_bridge.lua write_weapons_extra：
    #   +0 有没有 +1 武器名（已换成字符串）+2 手上那把 +3 威力 +4 破甲 +5 弹匣剩 +6 弹匣容量 +7 备用弹匣 +8 射速
    #   +9 换到这把要多久 +10 初速 +11 重力 +12 溅射半径 +13 武器编号。区没写 / unit_id 对不上是 None
    weapons_raw: tuple = None
    # 第 7 版 M10：这个人的战略配备，8 × 6 格（去掉了 unit_id），每条：+0 名字（已换成字符串）+1 指令（上1下2左3右4 拼成的数）
    #   +2 冷却还剩 +3 还能叫几次（-1 不限）+4 能不能叫（1 / 0 / -1 不确定）+5 种类（0 补给 1 装备 2 攻击 3 防御 4 复活 5 其他）
    strat_raw: tuple = None
    # 第 8 版 M15：这个人的 16 个水平方向障碍物距离（米，-1 = 没碰着；None = 没数据）
    rocks: tuple = None
    # 第 8 版 M5：这个人手上会飞的弹的弧线，15 格（unit_id + 14 格，格子见 ai_bridge.lua write_arc）；区没写 / unit_id 对不上是 None
    arc: tuple = None
    # 速度门控前的原值和是否触发门控（只用于日志核实；消费方只读 vel_x / vel_y）
    raw_vel_x: float = None
    raw_vel_y: float = None
    velocity_gated: bool = False
    motion_raw: tuple = None  # M17 player motion parameters, uid first
    # 第 14 版 M18：她背着的盾（盾组件 state，只读；没背 / 旧 mod / 读不到都是 None = “拿不准”）。
    # 属性名照 sustain.SHIELD_FIELDS 取，sustain.shield_seed 直接能用：
    #   shield_pts 盾量 shieldpoints、shield_max 盾上限 max_shieldpoints、
    #   shield_on 盾开着 shield_activated（None = 组件没设这个字段）、shield_timer 充能计时器 shield_regen_timer（秒）
    shield_pts: float = None
    shield_max: float = None
    shield_on: bool = None
    shield_timer: float = None


WEAPON_KINDS = {0: "其他", 1: "普通枪", 2: "激光", 3: "电弧", 4: "火焰", 5: "会飞的弹", 6: "近战", 7: "投掷"}


@dataclass
class Weapon:
    """玩家手上那把枪，mod 每帧现读（换枪、捡枪、重生、换升级都会马上变）。读不到的数是 -1。
    布尔配置三种值：1 = 是，0 = 否，-1 = 配置里没写（读不到）。"""
    kind: int            # 见 WEAPON_KINDS
    name: str            # 武器图标名，如 wepicon_shotgun_01（破裂者）
    weapon_id: int       # 这把枪的编号，换了一把就变
    upgrade: int         # 升级值（按位：第 1 位是第一个升级……），-1 = 不能升级
    unstoppable: int     # 子弹穿透（破裂者 flechette、轨道枪、正义的升级）
    piercing: int        # 另一种穿透（打死了才穿过去），玩家武器里没见到开着的
    pellets: float       # 每发几颗弹丸
    spread: float        # 当前散布（度，半角）
    spread_min: float
    spread_max: float
    fixed_spread: int    # 1 = 散布不随连射变（喷子）
    spread_shots_max: float    # 连射几发散布涨满
    spread_shots_decay: float  # 停手后散布每秒回落几发
    spread_shots: float  # 现在累计到第几发
    range: float         # 射程（米）。普通枪：子弹从 1.5 米高斜着往下，平地上在这么远落地
    firerate: float      # 射速（发/分）
    semi_auto: int
    full_auto: int
    burst: float         # 自带点射几发，-1 = 没有
    rounds: float        # 弹匣剩几发
    mag_size: float
    mags: float          # 备用弹匣
    reloading: int
    reload_left: float
    heat: float          # 激光、电弧的热量（0~1）
    turn_aim: float      # 举枪时转身速度倍率
    turn_fire: float     # 开火时转身速度倍率
    move_aim: float      # 举枪时移动速度倍率
    arc_first_jump: float
    arc_jump_in: float
    arc_jump_out: float
    arc_jumps: float
    arc_angle: float     # 电弧第一跳的扇区角度（度）
    explosive: int
    fire_wait: float     # 离下一发还要几秒
    min_range: float     # 火焰最近喷多远、电弧最近
    base_spread: float   # 配置里的散布（度），激光喷子、电弧用
    arc_ok: bool = False  # 第 8 版：会飞的弹这一步能不能开火（companion 每帧按 arc.py 写；别的种类不看它）
    arc_note: str = ""    # 弧线闸门的一句话原因（日志用）

    @property
    def kind_name(self):
        return WEAPON_KINDS.get(self.kind, str(self.kind))

    @property
    def round_delay(self):
        """两发之间几秒；读不到射速时 -1。"""
        return 60.0 / self.firerate if self.firerate > 0 else -1.0


@dataclass
class Enemy:
    unit_id: int
    type: str           # 如 bug_warrior
    x: float
    y: float
    z: float
    hp: float
    max_hp: float
    dead: bool
    state: str
    alerted: bool       # 正在报警（停下来叫援军）
    alarm_timer: float  # 报警倒计时，< 0 时援军已被叫来；-99 = 没在报警
    patroling: bool
    target_slot: int    # 正在追的玩家槽位，-1 = 没有
    triggered: bool     # 已经叫来援军
    rotation: float
    patrol_range: float
    # 第 7 版 M6：这只虫的补充 15 格（含 unit_id，见 ai_bridge.lua write_bugs）：+0 unit_id +1 在屏幕里 +2 看得到目标
    #   +3 看的哪个玩家槽位 +4 真名（已换成字符串，如 bug_warrior_elite）+5 进当前状态多久 +6~+7 出手（P2，-99）
    #   +8 冲锋冷却 +9 范围攻击冷却 +10~+14 跳扑、钻地（P2，-99）。区没写 / unit_id 对不上是 None
    extra_raw: tuple = None
    ballistic_raw: tuple = None
    logic_raw: tuple = None  # M17 source clocks/child handles; remote clocks are unknown
    # 第 15 版 M19（只有冲锋虫有）：它自己冲锋前射线的结果 10 格（含 unit_id），见 ai_bridge.lua write_tankrays：
    #   +0 unit_id +1 前触须 +2 左触须 +3 右触须（没碰到 1000，没有 -1）+4 左肩通 +5 右肩通（1/0，-1 没算过）
    #   +6 离最近的人 +7 目标角（弧度，-99 没有）+8 减速中（1/0/-1）+9 本机算的（1/0）。旧 mod / 不是冲锋虫是 None
    rays_raw: tuple = None


@dataclass
class Snapshot:
    frame: int
    game_time: float
    dt: float
    wall_time: float
    players: list = field(default_factory=list)
    enemies: list = field(default_factory=list)
    enemies_total: int = 0
    camera_spin: float = -99.0  # 镜头水平转角（度）：手柄方向转这么多 = 地图方向。关卡 -45，飞船 15；-99 = 读不到
    errors: int = 0
    error_text: str = ""
    weapon_errors: int = 0  # 读武器出错的次数（不影响其他数据）
    mission_cells: tuple = ()   # 任务区原样的 140 格（第 0 格是区版本），用 escort.parse_mission 解开
    ship_cells: tuple = ()      # 飞船区原样的 80 格（第 0 格 1 = 写好了），用 ship.parse_ship 解开
    extra_errors: int = 0       # 第 6 版起的新区（输入、状态补充、视线，第 7 版的五区）一共出错几次
    # 第 7 版的全局区，原样格子（去掉区版本那一格；字符串编号已换成字符串；读不到 -99、没有 -1 照原样）。区没写 / 老 mod 是 None
    drops_raw: tuple = None     # M8 掉落物 32 × 9：+0 unit_id（-1 = 空位）+1 种类（0 弹药 1 补给箱 3 支援武器 4 背包 5 样本）
                                #   +2 +3 +4 x y z +5 谁叫的（槽位）+6 名字 +7 还剩多少 +8 出现多久
    team_raw: tuple = None      # M9 4 × 6 + 3：每个槽位 +0 死了 +1 死了多久 +2 +3 尸体 x y +4 在等复活 +5 手柄编号（活着时的）；
                                #   全队 [24] 还剩几次增援（-1 不限）[25] 复活冷却还剩 [26] 有复活球在飞
    beacons_raw: tuple = None   # M10 场上信标 8 × 8：+0 unit_id（-1 = 空位）+1 谁扔的 +2 名字 +3 +4 x y +5 还有多久落地
                                #   +6 危险半径（-99）+7 已落地
    camera_raw: tuple = None    # M12 8 格：+0 +1 屏幕中心地面点 x y +2 半宽 +3 半高 +4 转角（度）+5 缩放 +6 中心到远边 +7 中心到近边
    hazards_raw: tuple = None   # M11 伤害源 32 × 13（末四格：待落击、冷却、来源、锁定槽）：+0 unit_id +1 种类 +2 +3 x y +4 朝向 +5 在开火/放电 +6 射程/半径 +7 扇区半角 +8 谁放的
    shield_errors: int = 0      # 第 14 版 M18 盾量区读写错的次数（旧 mod 没有这一区，一直是 0）

    def living_players(self):
        """死掉的角色尸体还会留在列表里（pad 变成 -1），重生的是新角色。这里只返回活着的。"""
        return [p for p in self.players if not p.dead]

    def player_by_pad(self, pad):
        return next((p for p in self.living_players() if p.pad == pad), None)


class Bridge:
    def __init__(self, pid, addr):
        self.pid = pid
        self.addr = addr
        self.handle = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "打不开进程")
        self.buf = ctypes.create_string_buffer(max(n for _, n in LAYOUTS.values()) * 8)
        self.L = L4                # 这一帧的表是哪种布局（_raw 按表头的版本挑）
        self.version = None
        self.shield_cells = None   # 这一帧的盾量区格子（区版本在最前面）；没读到 / 旧表是 None
        self.tankray_cells = None  # 这一帧的冲锋虫射线区格子（区版本在最前面）；没读到 / 第 15 版以前是 None
        self.last_frame = None
        self.strings = {}

    # ---------- 找表 ----------

    @staticmethod
    def scan(pid, low_only=True, magic=MAGIC):
        """在进程内存里找所有魔数位置（= 表的第 1 格地址）。LuaJIT 2.0 的对象都在低 4GB。
        magic 换成别的表的魔数，就能找别的表（比如地形探针 terrain_probe.py）。"""
        h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not h:
            raise OSError(ctypes.get_last_error(), "打不开进程")
        hits = []
        try:
            mbi = MEMORY_BASIC_INFORMATION()
            addr = 0x10000
            limit = 0x100000000 if low_only else 0x7FFFFFFF0000
            chunk = 16 << 20
            while addr < limit and k32.VirtualQueryEx(h, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)):
                base, size = mbi.BaseAddress or 0, mbi.RegionSize
                if mbi.State == MEM_COMMIT and (mbi.Protect & 0xFF) in READABLE and not mbi.Protect & PAGE_GUARD:
                    off = 0
                    while off < size:
                        n = min(chunk + 32, size - off)
                        buf = ctypes.create_string_buffer(n)
                        got = ctypes.c_size_t()
                        if k32.ReadProcessMemory(h, base + off, buf, n, ctypes.byref(got)) and got.value:
                            data = buf.raw[:got.value]
                            i = data.find(magic)
                            while i >= 0:
                                if i % 8 == 0 and base + off + i not in hits:
                                    hits.append(base + off + i)
                                i = data.find(magic, i + 1)
                        off += chunk
                addr = base + size
        finally:
            k32.CloseHandle(h)
        return hits

    @classmethod
    def attach(cls, name="helldivers.exe", pid=None, wait=0.5):
        """找进程和表。多个候选时选帧号在增长的那个。找不到返回 None。"""
        pid = pid or find_pid(name)
        if not pid:
            return None
        hits = cls.scan(pid)
        cands = []
        for a in hits:
            b = cls(pid, a)
            v = b._raw()
            if v and int(v[4]) in VERSIONS:
                cands.append((b, v[5]))
            else:
                b.close()
        if not cands:
            return None
        if len(cands) > 1:
            time.sleep(wait)
            moving = [(b, f) for b, f in cands if (b._raw() or [0] * 6)[5] != f]
            if moving:
                cands = moving
        best = max(cands, key=lambda c: c[1])[0]
        for b, _ in cands:
            if b is not best:
                b.close()
        return best

    # ---------- 读取 ----------

    def alive(self):
        code = wintypes.DWORD()
        return bool(k32.GetExitCodeProcess(self.handle, ctypes.byref(code))) and code.value == 259

    def _raw(self):
        """先读表头看版本，再按这一版的表长整张读（旧表后面不是我们的内存，多读可能读不到或者读到别的数）。
        版本认不得时只返回表头（attach 看了版本会跳过它）。"""
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.handle, self.addr, self.buf, HEAD * 8, ctypes.byref(got)) or got.value != HEAD * 8:
            return None
        ver = int(memoryview(ctypes.string_at(self.buf, HEAD * 8)).cast("d")[4])
        self.shield_cells = None
        self.tankray_cells = None
        if ver not in LAYOUTS:
            self.version = None
            return memoryview(ctypes.string_at(self.buf, HEAD * 8)).cast("d")
        L, n = LAYOUTS[ver]
        if not k32.ReadProcessMemory(self.handle, self.addr, self.buf, n * 8, ctypes.byref(got)) or got.value != n * 8:
            return None
        v = memoryview(ctypes.string_at(self.buf, n * 8)).cast("d")
        if int(v[4]) != ver:          # 两次读之间 mod 换了表（换 mod 没重开游戏），下一帧再说
            return None
        self.L, self.version = L, ver
        if ver >= 14:
            self.shield_cells = tuple(v[L.N13:L.N14])          # 从区版本那一格开始
        if ver >= 15:
            self.tankray_cells = tuple(v[L.N14:L.N15])
        return v

    def string(self, v, i):
        L = self.L
        if i < 0:
            return ""
        s = self.strings.get(i)
        if s is None:
            base = L.S0 + i * SL - 1
            n = int(v[base])
            if n <= 0:
                return f"#{i}"
            s = "".join(chr(int(c)) for c in v[base + 1:base + 1 + n])
            self.strings[i] = s
        return s

    def read(self, only_new=True):
        """读一帧。表没更新（only_new）、读到写了一半、或者魔数不对时返回 None。"""
        for _ in range(3):
            v = self._raw()
            if v is None or tuple(v[0:4]) != MAGIC_VALUES or self.version is None:
                return None
            if v[5] == v[6]:
                break
        else:
            return None
        L = self.L
        frame = int(v[5])
        if only_new and frame == self.last_frame:
            return None
        self.last_frame = frame
        T = lambda i: v[i - 1]  # noqa: E731  Lua 下标 -> 数组下标
        snap = Snapshot(frame=frame, dt=T(8), game_time=T(9), wall_time=time.time(),
                        enemies_total=int(T(12)), errors=int(T(13)), weapon_errors=int(T(16)),
                        camera_spin=math.degrees(T(15)) if T(15) != -99 else -99.0)
        if snap.errors or snap.weapon_errors:
            n = int(T(L.ERR0))
            snap.error_text = "".join(chr(int(c)) for c in v[L.ERR0:L.ERR0 + n])
        snap.mission_cells = tuple(v[L.M0 - 1:L.M0 - 1 + MF])
        snap.ship_cells = tuple(v[L.SH0 - 1:L.SH0 - 1 + SHF])
        if L.MAX_PLAYERS > FIX_PLAYERS and v[L.X0 - 1] == 1:
            # 第 5～8 个人放不下的那几格（M20）接在任务区、飞船区后面，escort.parse_mission / ship.parse_ship 认长度
            rows = [v[L.X0 + k * XF:L.X0 + (k + 1) * XF] for k in range(L.MAX_PLAYERS - FIX_PLAYERS)]
            snap.mission_cells += tuple(c for r in rows for c in r[0:2]) + tuple(c for r in rows for c in r[2:5])
            snap.ship_cells += tuple(c for r in rows for c in r[5:7])
        snap.extra_errors = int(T(L.SI0 + 1))
        if self.shield_cells:
            snap.shield_errors = int(self.shield_cells[1])   # M18 的 +1 格（本区出错次数；旧表没有这一区）
        if T(L.DR0) == 1:
            snap.drops_raw = self._strs(v, v[L.DR0:L.DR0 + MAX_DROPS * DRF], DRF, (6,))
        if T(L.TM0) == 1:
            snap.team_raw = tuple(v[L.TM0:L.TM0 + L.MAX_PLAYERS * TMF + 3])
        if T(L.SG0) == 1:
            b = L.SG0 + 1 + L.MAX_PLAYERS * SGF
            snap.beacons_raw = self._strs(v, v[b - 1:b - 1 + MAX_BEACONS * BCF], BCF, (2,))
        if T(L.CM0) == 1:
            snap.camera_raw = tuple(v[L.CM0:L.CM0 + CMF])
        if T(L.HZ0) == 1:
            snap.hazards_raw = tuple(v[L.HZ0:L.HZ0 + MAX_HAZ * HZF])
        for i in range(int(T(10))):
            b = L.P0 + i * PF
            if T(b) != 1:
                continue
            raw_vel_x, raw_vel_y = T(b + 7), T(b + 8)
            vel_x, vel_y, velocity_gated = sanitize_player_velocity(
                raw_vel_x, raw_vel_y
            )
            snap.players.append(Player(
                slot=i, pad=int(T(b + 1)), x=T(b + 2), y=T(b + 3), z=T(b + 4), face_x=T(b + 5), face_y=T(b + 6),
                vel_x=vel_x, vel_y=vel_y, aim_x=T(b + 9), aim_y=T(b + 10), hp=T(b + 11), max_hp=T(b + 12),
                downed=T(b + 13) == 1, dead=T(b + 14) == 1, dodging=T(b + 15) == 1, state=self.string(v, int(T(b + 16))),
                melee_time=T(b + 17), melee_duration=T(b + 18), melee_radius=T(b + 19), stamina=T(b + 20),
                time_outside_screen=T(b + 21), unit_id=int(T(b + 22)), aiming=T(b + 23) == 1,
                weapon=self._weapon(v, T, L.W0 + i * WF), raw_vel_x=raw_vel_x, raw_vel_y=raw_vel_y,
                velocity_gated=velocity_gated))
            self._extra(v, T, i, snap.players[-1])
            self._shield_fill(i, snap.players[-1])
            b = L.MV0+1+i*MVF
            if T(L.MV0) == 1 and T(b) == snap.players[-1].unit_id:
                snap.players[-1].motion_raw = tuple(v[b-1:b-1+MVF])
        for i in range(int(T(11))):
            b = L.E0 + i * EF
            snap.enemies.append(Enemy(
                unit_id=int(T(b)), type=self.string(v, int(T(b + 1))), x=T(b + 2), y=T(b + 3), z=T(b + 4),
                hp=T(b + 5), max_hp=T(b + 6), dead=T(b + 7) == 1, state=self.string(v, int(T(b + 8))),
                alerted=T(b + 9) == 1, alarm_timer=T(b + 10), patroling=T(b + 11) == 1, target_slot=int(T(b + 12)),
                triggered=T(b + 13) == 1, rotation=T(b + 14), patrol_range=T(b + 15)))
            x = L.EX0 + 1 + i * EXF
            if T(L.EX0) == 1 and int(T(x)) == snap.enemies[-1].unit_id:
                snap.enemies[-1].extra_raw = self._strs(v, v[x - 1:x - 1 + EXF], EXF, (4,))
            b = L.BL0 + 1 + i * BLF
            if v[L.BL0 - 1] == 1 and int(v[b - 1]) == snap.enemies[-1].unit_id:
                snap.enemies[-1].ballistic_raw = tuple(v[b - 1:b - 1 + BLF])
            b = L.LG0+1+i*LGF
            if T(L.LG0) == 1 and T(b) == snap.enemies[-1].unit_id:
                snap.enemies[-1].logic_raw = tuple(v[b-1:b-1+LGF])
        tr = self.tankray_cells
        if tr and int(tr[0]) == 1:
            by = {e.unit_id: e for e in snap.enemies}
            for k in range(MAX_TR):
                row = tr[2 + k * TRF:2 + (k + 1) * TRF]
                e = by.get(int(row[0])) if len(row) == TRF and row[0] >= 0 else None
                if e is not None:
                    e.rays_raw = tuple(row)
        return snap

    def _strs(self, v, cells, stride, idx):
        """cells 每 stride 格一条，每条第 idx 里那几格是字符串编号：>= 0 的换成字符串，负数（-1 没有、-2 字符串表满了、
        -99 读不到）照原样。返回 tuple。"""
        out = list(cells)
        for base in range(0, len(out), stride):
            for k in idx:
                if out[base + k] >= 0:
                    out[base + k] = self.string(v, int(out[base + k]))
        return tuple(out)

    def _extra(self, v, T, i, p):
        """第 6 版起各区里这个人的那几格（unit_id 对得上才算）。"""
        L = self.L
        b = L.IN0 + 1 + i * INF
        if T(L.IN0) == 1 and int(T(b)) == p.unit_id:
            p.input = PlayerInput(fire=T(b + 1) == 1, aim=T(b + 2) == 1, move_x=T(b + 3), move_y=T(b + 4),
                                  aim_x=T(b + 5), aim_y=T(b + 6), shot=T(b + 7) == 1)
        b = L.ST0 + 1 + i * STF
        if T(L.ST0) == 1 and int(T(b)) == p.unit_id:
            src = int(T(b + 8))
            p.status = PlayerStatus(presses=T(b + 1), needed=T(b + 2), downed_for=T(b + 3), prone_for=T(b + 4),
                                    reset_timer=T(b + 11), getup_left=T(b + 5), burning=int(T(b + 6)), slow=T(b + 7),
                                    slow_source=self.string(v, src) if src >= 0 else "", poisoned=int(T(b + 9)),
                                    since_hit=T(b + 10))
        b = L.SI0 + 3 + i * SIF
        if T(L.SI0) == 1 and T(b) == 1:
            p.sight = tuple(v[b - 1:b - 1 + SIF])
        b = L.WX0 + 1 + i * WXF
        if T(L.WX0) == 1 and int(T(b)) == p.unit_id:
            p.weapons_raw = self._strs(v, v[b:b + 3 * WXW], WXW, (1,))
        b = L.SG0 + 1 + i * SGF
        if T(L.SG0) == 1 and int(T(b)) == p.unit_id:
            p.strat_raw = self._strs(v, v[b:b + MAX_STRATS * STW], STW, (0,))
        b = L.RK0 + 1 + i * RKF
        if T(L.RK0) == 1 and int(T(b)) == p.unit_id:
            p.rocks = tuple(v[b:b + RK_RAYS])
        b = L.AR0 + 1 + i * ARF
        if T(L.AR0) == 1 and int(T(b)) == p.unit_id:
            p.arc = tuple(v[b - 1:b - 1 + ARF])

    def _shield(self, i):
        """M18 盾量区里第 i 个玩家（0 基）的 5 格（0 是 unit_id）；旧 mod 的表没有这一区、区版本不是 1、或者
        这一小段没读到时返回 None（陪玩那边当“没盾 / 拿不准”）。"""
        cells = self.shield_cells
        if not cells or int(cells[0]) != 1:
            return None
        base = 2 + i * SDF          # +0 区版本、+1 出错次数，之后每玩家 SDF 格
        return cells[base:base + SDF]

    def _shield_fill(self, i, p):
        """把 M18 盾量区第 i 个玩家的 4 个数填进 Player；单位对不上 / 读不到就保持 None（拿不准）。"""
        sc = self._shield(i)
        if sc is None or int(sc[0]) != p.unit_id:
            return
        pts, mx, on, timer = sc[1], sc[2], sc[3], sc[4]
        if pts >= 0:            # -1 = 这一格没读到（或没盾）
            p.shield_pts = pts
        if mx > 0:
            p.shield_max = mx
        if on >= 0:
            p.shield_on = bool(on)
        if timer >= 0:
            p.shield_timer = timer

    def _weapon(self, v, T, b):
        if T(b) != 1:
            return None
        f = [T(b + k) for k in range(WF)]
        return Weapon(kind=int(f[1]), name=self.string(v, int(f[2])), weapon_id=int(f[3]), upgrade=int(f[4]),
                      unstoppable=int(f[5]), piercing=int(f[6]), pellets=f[7], spread=f[8], spread_min=f[9],
                      spread_max=f[10], fixed_spread=int(f[11]), spread_shots_max=f[12], spread_shots_decay=f[13],
                      spread_shots=f[14], range=f[15], firerate=f[16], semi_auto=int(f[17]), full_auto=int(f[18]),
                      burst=f[19], rounds=f[20], mag_size=f[21], mags=f[22], reloading=int(f[23]), reload_left=f[24],
                      heat=f[25], turn_aim=f[26], turn_fire=f[27], move_aim=f[28], arc_first_jump=f[29],
                      arc_jump_in=f[30], arc_jump_out=f[31], arc_jumps=f[32], arc_angle=f[33], explosive=int(f[34]),
                      fire_wait=f[35], min_range=f[36], base_spread=f[37])

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None
