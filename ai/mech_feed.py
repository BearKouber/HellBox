r"""读游戏里 ai_mech mod 写出的"机制表"（HD1-012 机制实测探针）。

表布局见 mod\src\ai_mech.lua，两边要一致（改了把 VERSION 加 1）。
和 ai_bridge 分开一张表、自己的魔数，陪玩程序不用它。

    from mech_feed import MechTable
    m = MechTable.attach(pid)
    frame = m.read()        # MechFrame 或 None（表没更新 / 读到写了一半）
    frame.events            # 上次读以来的新事件（出膛、爆炸、近战命中、挨打、锁血开关）
"""
import ctypes
import math
import struct
import time
from dataclasses import dataclass, field

from bridge import Bridge, k32

VERSION = 1
MAGIC_VALUES = (17320508.5, -244948.625, 1732.0625, 137438953472.375)
MAGIC = struct.pack("<4d", *MAGIC_VALUES)
H = 32
MAX_PLAYERS, PF = 4, 64
MAX_EV, EVF = 256, 16
MAX_STRINGS, SL = 128, 40
ERR_LEN = 200
P0 = H + 1
EV0 = P0 + MAX_PLAYERS * PF
S0 = EV0 + MAX_EV * EVF
ERR0 = S0 + MAX_STRINGS * SL
N = ERR0 + ERR_LEN
MISS = -999

# 按着的动作（第 25 格按位）
BUTTONS = (("sprint", 1), ("melee", 2), ("fire", 4), ("fire_auto", 8), ("dodge", 16), ("reload", 32),
           ("throw", 64), ("interact", 128), ("stratagems", 256), ("map", 512))
HOOKS = (("出膛", 1), ("爆炸", 2), ("近战命中", 4), ("挨打", 8), ("炮弹登记", 16), ("击杀", 32))
EVENT_KINDS = {1: "shot", 2: "explosion", 3: "melee_hit", 4: "hurt", 5: "lock", 6: "kill_by"}  # kill_by：游戏算的谁杀的（HD1-040）
WHO_KIND = {0: "other", 1: "player", 2: "enemy"}


def T(v, i):
    """Lua 下标 -> 值。"""
    return v[i - 1]


def opt(x):
    """-999 = 读不到 -> None。"""
    return None if x == MISS else x


def yaw(x, y):
    """地图方向 -> 角度（度，0 = +x，逆时针）；方向是 0 时 None。"""
    if x is None or y is None or (abs(x) < 1e-6 and abs(y) < 1e-6):
        return None
    return math.degrees(math.atan2(y, x))


@dataclass
class MechPlayer:
    slot: int
    uid: int
    pad: int
    x: float
    y: float
    z: float
    face: float            # 身体朝向（度）
    vel_x: float
    vel_y: float
    vel_z: float
    hp: float
    max_hp: float
    constitution: float    # 血量到这就死透；倒地时血往这掉
    downed: bool
    dead: bool
    dodging: bool
    state: str
    state_since: float     # 进这个状态时的游戏时间
    substate: str
    substate_since: float
    move_x: float          # 游戏读到的移动方向（地图方向，长度 0~1）
    move_y: float
    aim_x: float           # 游戏读到的瞄准方向（键鼠：朝鼠标；没按瞄准 / 开火是 0）
    aim_y: float
    buttons: tuple         # 按着的动作名字
    fire_amount: float
    interact_button: float
    switch_weapon: str
    sprint_amount: float
    wanted_speed: float
    dive_timer: float
    dive_get_up: bool
    get_up_presses: float
    get_up_needed: float
    get_up_reset: float
    aiming: bool
    melee_time: float
    melee_duration: float
    weapon: str
    weapon_id: int
    rounds: float
    mag_size: float
    reloading: bool
    reload_left: float
    launcher: dict = field(default_factory=dict)   # 发射器（雷鸣）的蓄力和连发；不是发射器是 {}
    muzzle: float = None   # 枪口朝向（度）

    @property
    def speed(self):
        return math.hypot(self.vel_x, self.vel_y)

    @property
    def heading(self):
        return yaw(self.vel_x, self.vel_y)

    @property
    def aim(self):
        return yaw(self.aim_x, self.aim_y)


@dataclass
class MechFrame:
    frame: int
    game_time: float
    dt: float
    wall_time: float
    players: list
    events: list           # 新事件（dict）
    lost_events: int       # 读得太慢、被环覆盖掉的事件数
    errors: int
    hook_errors: int
    error_text: str
    hooks: tuple           # 装上的钩子名字
    lock: bool
    lock_key: str          # 锁血键名字（找不到是 ""）
    camera_spin: float
    keyboard_pad: int
    bridge_frame: int


class MechTable:
    def __init__(self, pid, addr):
        self.pid, self.addr = pid, addr
        self.handle = k32.OpenProcess(0x0010 | 0x0400, False, pid)
        self.buf = ctypes.create_string_buffer(N * 8)
        self.strings = {}
        self.last_frame = None
        self.last_seq = None

    @classmethod
    def attach(cls, pid, wait=0.3):
        """找表。多个候选（旧表没被回收）时挑帧号在动的、再挑帧号最大的。"""
        cands = []
        for a in Bridge.scan(pid, magic=MAGIC):
            t = cls(pid, a)
            v = t.raw()
            if v and v[4] == VERSION:
                cands.append((t, v[5]))
            else:
                t.close()
        if not cands:
            return None
        if len(cands) > 1:
            time.sleep(wait)
            moving = [(t, f) for t, f in cands if (t.raw() or [0] * 6)[5] != f]
            cands = moving or cands
        best = max(cands, key=lambda c: c[1])[0]
        for t, _ in cands:
            if t is not best:
                t.close()
        return best

    def alive(self):
        from ctypes import wintypes
        code = wintypes.DWORD()
        return bool(self.handle) and bool(k32.GetExitCodeProcess(self.handle, ctypes.byref(code))) and code.value == 259

    def raw(self):
        got = ctypes.c_size_t()
        if not self.handle or not k32.ReadProcessMemory(self.handle, self.addr, self.buf, N * 8, ctypes.byref(got)) \
                or got.value != N * 8:
            return None
        v = memoryview(self.buf.raw).cast("d")
        if tuple(v[0:4]) != MAGIC_VALUES:
            return None
        return v

    def string(self, v, i):
        i = int(i)
        if i < 0:
            return ""
        s = self.strings.get(i)
        if s is None:
            base = S0 + i * SL
            n = int(T(v, base))
            if n <= 0:
                return f"#{i}"
            s = bytes(int(c) & 0xFF for c in v[base:base + n]).decode("utf-8", errors="replace")
            self.strings[i] = s
        return s

    def read(self, only_new=True):
        """读一帧。表没更新（only_new）、读到写了一半时返回 None。"""
        for _ in range(3):
            v = self.raw()
            if v is None:
                return None
            if T(v, 6) == T(v, 7):
                break
        else:
            return None
        frame = int(T(v, 6))
        if only_new and frame == self.last_frame:
            return None
        self.last_frame = frame
        return self._parse(v, frame)

    def _parse(self, v, frame):
        S = lambda i: self.string(v, T(v, i))  # noqa: E731
        errors, hook_errors = int(T(v, 11)), int(T(v, 12))
        err = ""
        if errors or hook_errors:
            n = int(T(v, ERR0))
            err = bytes(int(c) & 0xFF for c in v[ERR0:ERR0 + n]).decode("utf-8", errors="replace")
        bits = int(T(v, 15))
        spin = T(v, 19)
        mf = MechFrame(frame=frame, game_time=T(v, 9), dt=T(v, 8), wall_time=time.time(), players=[], events=[],
                       lost_events=0, errors=errors, hook_errors=hook_errors, error_text=err,
                       hooks=tuple(name for name, b in HOOKS if bits & b), lock=T(v, 16) == 1,
                       lock_key=S(18) if T(v, 17) == 1 else "",
                       camera_spin=math.degrees(spin) if spin != -99 else -99.0, keyboard_pad=int(T(v, 20)),
                       bridge_frame=int(T(v, 21)))
        for i in range(MAX_PLAYERS):
            b = P0 + i * PF
            if T(v, b) == 1:
                mf.players.append(self._player(v, i, b, S))
        mf.events, mf.lost_events = self._events(v, S)
        return mf

    def _player(self, v, slot, b, S):
        f = lambda k: T(v, b + k)  # noqa: E731
        bits = int(f(25))
        launcher = {}
        if f(46) == 1:
            launcher = dict(charging=f(47) == 1, charge=f(48), burst_round=int(f(49)), burst_timer=f(50),
                            burst_power=opt(f(51)), was_charging=f(52) == 1, wait_release=f(53) == 1,
                            min_charge=f(54), max_charge=f(55), burst_delay=f(56), burst_rounds=f(57),
                            power=f(58), charge_extra=f(59), power_drop=f(60))
        mx, my = opt(f(61)), opt(f(62))
        return MechPlayer(
            slot=slot, uid=int(f(1)), pad=int(f(2)), x=f(3), y=f(4), z=f(5), face=yaw(f(6), f(7)) or 0.0,
            vel_x=f(8), vel_y=f(9), vel_z=f(10), hp=f(11), max_hp=f(12), constitution=f(13), downed=f(14) == 1,
            dead=f(15) == 1, dodging=f(16) == 1, state=S(b + 17), state_since=f(18), substate=S(b + 19),
            substate_since=f(20), move_x=f(21), move_y=f(22), aim_x=f(23), aim_y=f(24),
            buttons=tuple(name for name, k in BUTTONS if bits & k), fire_amount=f(26), interact_button=f(27),
            switch_weapon=S(b + 28) if f(28) >= 0 else "", sprint_amount=f(29), wanted_speed=f(30),
            dive_timer=opt(f(31)), dive_get_up=f(32) == 1, get_up_presses=opt(f(33)), get_up_needed=opt(f(34)),
            get_up_reset=opt(f(35)), aiming=f(36) == 1, melee_time=f(37), melee_duration=opt(f(38)),
            weapon=S(b + 40) if f(39) == 1 else "", weapon_id=int(f(41)) if f(39) == 1 else -1,
            rounds=opt(f(42)), mag_size=opt(f(43)), reloading=f(44) == 1, reload_left=opt(f(45)),
            launcher=launcher, muzzle=yaw(mx, my))

    def _events(self, v, S):
        seq = int(T(v, 14))
        if self.last_seq is None:
            # 第一次读：之前的事件不要（可能是上一局的）
            self.last_seq = seq
            return [], 0
        if seq < self.last_seq:
            # 表重建了（重进游戏）：从头读
            self.last_seq = 0
        lost = max(0, seq - self.last_seq - MAX_EV)
        out = []
        for n in range(max(self.last_seq + 1, seq - MAX_EV + 1), seq + 1):
            b = EV0 + ((n - 1) % MAX_EV) * EVF
            if T(v, b) != n:
                lost += 1
                continue
            out.append(self._event(v, b, n, S))
        self.last_seq = seq
        return out, lost

    def _event(self, v, b, n, S):
        f = lambda k: T(v, b + k)  # noqa: E731
        kind = EVENT_KINDS.get(int(f(2)), str(int(f(2))))
        e = {"seq": n, "gt": f(1), "kind": kind}
        if kind == "shot":
            e.update(who=int(f(3)), round=int(f(4)), x=f(5), y=f(6), z=f(7), dir=[f(8), f(9), f(10)],
                     yaw=yaw(f(8), f(9)), power=opt(f(11)), shot=int(f(12)), charge=opt(f(13)), face=f(14),
                     weapon=S(b + 15))
        elif kind == "explosion":
            e.update(owner=int(f(3)), owner_kind=WHO_KIND.get(int(f(4)), "other"), x=f(5), y=f(6), z=f(7),
                     shot=int(f(8)), proj=int(f(9)), blast_radius=opt(f(10)), center_radius=opt(f(11)),
                     blast_power=opt(f(12)), center_power=opt(f(13)), owner_type=S(b + 14) if f(14) >= 0 else "")
        elif kind == "melee_hit":
            e.update(attacker=int(f(3)), target=int(f(4)), target_kind=WHO_KIND.get(int(f(5)), "other"),
                     target_type=S(b + 6) if f(6) >= 0 else "", power=opt(f(7)), target_hp=opt(f(8)),
                     target_max_hp=opt(f(9)), ax=opt(f(10)), ay=opt(f(11)), tx=opt(f(12)), ty=opt(f(13)),
                     armorpiercing=f(14) == 1)
        elif kind == "hurt":
            e.update(target=int(f(3)), owner=int(f(4)), owner_kind=WHO_KIND.get(int(f(5)), "other"),
                     owner_type=S(b + 6) if f(6) >= 0 else "", power=opt(f(7)), hp_before=opt(f(8)),
                     damage_type=S(b + 9) if f(9) >= 0 else "", healed=f(10) == 1, ox=opt(f(11)), oy=opt(f(12)),
                     was_downed=f(13) == 1, attacker=int(f(14)))
        elif kind == "kill_by":
            e.update(target=int(f(3)), target_kind=WHO_KIND.get(int(f(4)), "other"),
                     target_type=S(b + 5) if f(5) >= 0 else "", owner=int(f(6)),
                     owner_kind=WHO_KIND.get(int(f(7)), "other"), attacker=int(f(8)),
                     damage_type=S(b + 9) if f(9) >= 0 else "", x=opt(f(10)), y=opt(f(11)),
                     owner_type=S(b + 12) if f(12) >= 0 else "", fell=f(13) == 1)
        elif kind == "lock":
            e.update(on=f(3) == 1)
        return e

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None
