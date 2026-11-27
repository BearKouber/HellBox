r"""对局录制黑匣子（HD1-016）：后台录真人的打法，按键存下最近 10 分钟，拿来和她的大脑对比。

只读游戏（mod 的 ai_bridge 表 + ai_mech 机制表），不按手柄、不拦按键。小键盘（要开 NumLock）：
    -     开始 / 暂停录制（刚打开时没在录；暂停期间不进缓冲）
    +     把缓冲里最近 10 分钟存成一个文件（存完缓冲照样留着、接着录；可以存很多次）
    1~4   标记"这里看 N 号玩家"（可以打多个；同一刻按 1 又按 3 = 1 号、3 号都要看）
    0     不碰（游戏里 mod 的锁血开关）
每个键都有声音：开始一声高音、暂停一声低音、存好两声、标记一声短音（1~4 音高越来越高）、不行（没在录 / 缓冲是空的）一声低沉长音。

用法：
    P:\Claude\Helldivers\.venv\Scripts\python P:\Claude\Helldivers\ai\blackbox.py      （或双击 黑匣子.bat）
    ...\python ai\blackbox.py show 文件.jsonl.gz       看一个存好的文件：时长、玩家、每个标记在第几秒
按 Ctrl+C 结束（没存的缓冲就丢了）。

存出的文件 ai\logs\blackbox\bb_<时间>.jsonl.gz（gzip 的 JSON 行，用 frames() 读），格式见 HD1开发经验.md "黑匣子"一节：
    第 1 行 start：格式版本、mod 表版本、时长、标记列表、虫子列名 ENEMY_COLS、武器补充列名 WEAPON_COLS
    chunk：一段的开头（每段约 10 秒；段开头那帧把所有"变了才记"的区都记全）
    f：每帧一行（ai_bridge 的帧号 f、游戏时间 gt；p 所有玩家，e 所有虫子，s 这帧变了的区）
    ev：事件（开火 / 停火、近战、扑倒、倒地、起来、死亡、换枪、挨打、近战命中、出膛、爆炸、虫子死、新角色）
    mark：标记（n = 几号玩家，players = 当时场上每个角色的槽位 / 手柄 / 编号）
    rec：开始 / 暂停录制
    end：录制器（recorder.py）写的文件才有，放在最后：时长、标记这些开头还不知道的数
"""
import argparse
import collections
import ctypes
import dataclasses
import gzip
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bridge import VERSION as BRIDGE_VERSION, Bridge, Weapon, find_pid  # noqa: E402

FMT = 2                 # 2 = 补上视线、弧线、运动参数、弹道、虫子内部计时、武器全字段（都是加字段，读老文件不受影响）
WINDOW = 600.0          # 缓冲留最近多少秒（录制中的时间，暂停的时间不算）
CHUNK_SECS = 10.0       # 每段多少秒压一次
FIRE_GAP = 0.5          # 两发之间隔这么久没开枪，算停火
HP_DROP = 0.5           # 没有机制表时，血掉这么多算挨打
REATTACH_SECS = 10.0    # 连着这么久没新帧，重新找表（重进关卡表会换地方）
RETRY_SECS = 3.0        # 没连上时隔这么久找一次（找表要扫一遍游戏内存）
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "blackbox")

VK_ADD, VK_SUBTRACT, VK_NUMLOCK = 0x6B, 0x6D, 0x90
VK_MARK = {0x60 + n: n for n in range(1, 5)}

ENEMY_COLS = ("id", "type", "x", "y", "z", "hp", "mhp", "dead", "st", "alert", "alarm_t", "patrol", "tgt", "trig",
              "rot", "name", "st_t", "onscr", "see", "look", "charge_cd", "area_cd", "logic")
WEAPON_COLS = tuple(f.name for f in dataclasses.fields(Weapon) if f.name not in (
    "name", "kind", "weapon_id", "rounds", "mag_size", "mags", "reloading", "reload_left", "heat", "spread",
    "fire_wait", "range", "firerate"))     # 手上那把枪 d["w"] 里没有的字段，放 s 的 wf<编号>


def r(x, n=3):
    return round(x, n) if isinstance(x, float) else x


def rl(xs, n=3):
    return None if xs is None else [r(x, n) for x in xs]


def b(x):
    return 1 if x else 0


def wall(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]


# ---------- 按键 ----------

class Keys:
    """小键盘 - + 1~4：按下那一下算一次（GetAsyncKeyState 只看不拦，游戏照样收得到）。getter 换掉就能离线测。"""

    def __init__(self, getter=None, toggle=VK_SUBTRACT, save=VK_ADD):
        if getter is None:
            user32 = ctypes.WinDLL("user32")
            getter = lambda vk: bool(user32.GetAsyncKeyState(vk) & 0x8000)  # noqa: E731
        self.getter = getter
        self.toggle, self.save = toggle, save     # save = None：不要"存"这个键
        self.down = set()

    def poll(self):
        hits = []
        for vk in (self.toggle, self.save, *VK_MARK):
            if vk is None:
                continue
            on = self.getter(vk)
            if on and vk not in self.down:
                hits.append("toggle" if vk == self.toggle else "save" if vk == self.save else VK_MARK[vk])
            if on:
                self.down.add(vk)
            else:
                self.down.discard(vk)
        return hits

    @staticmethod
    def numlock():
        return bool(ctypes.WinDLL("user32").GetKeyState(VK_NUMLOCK) & 1)


# ---------- 声音 ----------

SOUNDS = {"start": [(1400, 150)], "pause": [(500, 250)], "saved": [(1000, 90), (0, 60), (1000, 90)],
          "no": [(250, 450)], 1: [(700, 70)], 2: [(850, 70)], 3: [(1000, 70)], 4: [(1150, 70)]}


class Beeper:
    """在单独的线程里响（winsound.Beep 会卡住调用的线程）。"""

    def __init__(self, enabled=True):
        self.q = queue.Queue()
        self.enabled = enabled
        if enabled:
            threading.Thread(target=self._run, daemon=True).start()

    def __call__(self, name):
        if self.enabled:
            self.q.put(SOUNDS[name])

    def _run(self):
        import winsound
        while True:
            for freq, ms in self.q.get():
                if freq:
                    winsound.Beep(freq, ms)
                else:
                    time.sleep(ms / 1000)


# ---------- 一帧变成一行 ----------

class Encoder:
    """把 ai_bridge 的一帧（Snapshot）+ 同一刻的机制表（MechFrame，可以没有）编成一行，顺便认出事件。
    "变了才记"的区（任务、飞船、掉落物、每人的武器栏 / 战略配备 / 石头……）放在行的 s 里，段开头 reset() 后全记一次。"""

    def __init__(self):
        self.sec = {}
        self.raw = {}           # 整块的原始格子（比 sec 便宜：元组直接比，变了才转）
        self.prev = {}          # uid -> 上一帧这个人的 dict（认事件用）
        self.fire = {}          # uid -> [开火开始 gt, 最后一发 gt, 几帧出了子弹, 枪名]
        self.enemy_dead = {}    # 虫子 id -> 死了没
        self.has_mech = False

    def reset(self):
        self.sec = {}
        self.raw = {}

    def _put(self, s, key, val):
        j = json.dumps(val, separators=(",", ":"))
        if self.sec.get(key) != j:
            self.sec[key] = j
            s[key] = val

    def _put_raw(self, s, key, cells, n=3):
        if self.raw.get(key) != cells:
            self.raw[key] = cells
            s[key] = rl(cells, n)

    def encode(self, snap, mf=None):
        """返回 (帧行, [事件行])。"""
        gt = snap.game_time
        mech = {p.uid: p for p in mf.players} if mf is not None else {}
        self.has_mech = mf is not None
        s = {}
        self._put(s, "spin", r(snap.camera_spin, 2))
        if mf is not None:
            self._put(s, "mech", [mf.keyboard_pad, b(mf.lock), list(mf.hooks)])
        self._put(s, "mission", rl(snap.mission_cells))
        self._put(s, "ship", rl(snap.ship_cells))
        for key in ("drops_raw", "team_raw", "beacons_raw", "camera_raw", "hazards_raw"):
            self._put(s, key[:-4], rl(getattr(snap, key), 2))
        ps, evs = [], []
        for p in snap.players:
            d = self._player(p, mech.get(p.unit_id), s)
            ps.append(d)
            evs += self._player_events(p, d, gt, snap.frame)
        es = []
        for e in snap.enemies:
            x = e.extra_raw
            es.append([e.unit_id, e.type, r(e.x, 2), r(e.y, 2), r(e.z, 2), r(e.hp, 1), r(e.max_hp, 1), b(e.dead),
                       e.state, b(e.alerted), r(e.alarm_timer, 2), b(e.patroling), e.target_slot, b(e.triggered),
                       r(e.rotation, 3),
                       *((x[4], r(x[5], 2), x[1], x[2], x[3], r(x[8], 2), r(x[9], 2)) if x else (None,) * 7),
                       rl(e.logic_raw, 2)])
            self._put_raw(s, f"bl{e.unit_id}", e.ballistic_raw, 2)
            if e.dead and not self.enemy_dead.get(e.unit_id, True):
                evs.append({"t": "ev", "k": "kill", "gt": r(gt, 3), "f": snap.frame, "enemy": e.unit_id,
                            "type": e.type, "x": r(e.x, 2), "y": r(e.y, 2)})
            self.enemy_dead[e.unit_id] = e.dead
        if len(self.enemy_dead) > 2000:
            alive = {e.unit_id for e in snap.enemies}
            self.enemy_dead = {k: v for k, v in self.enemy_dead.items() if k in alive}
        row = {"t": "f", "f": snap.frame, "gt": r(gt, 4), "dt": r(snap.dt, 4), "w": r(snap.wall_time, 3),
               "p": ps, "e": es, "et": snap.enemies_total}
        if mf is not None:
            row["mf"] = mf.bridge_frame
            for ev in mf.events:
                ev = {k: (rl(v) if isinstance(v, list) else r(v)) for k, v in ev.items()}
                ev["k"] = ev.pop("kind")
                ev.update(t="ev", f=snap.frame)
                evs.append(ev)
        if snap.errors or snap.extra_errors or snap.weapon_errors:
            self._put(s, "err", [snap.errors, snap.extra_errors, snap.weapon_errors, snap.error_text[:200]])
        if s:
            row["s"] = s
        return row, evs

    def _player(self, p, m, s):
        d = {"s": p.slot, "pad": p.pad, "id": p.unit_id, "x": r(p.x, 3), "y": r(p.y, 3), "z": r(p.z, 3),
             "fx": r(p.face_x), "fy": r(p.face_y), "vx": r(p.vel_x), "vy": r(p.vel_y), "ax": r(p.aim_x),
             "ay": r(p.aim_y), "hp": r(p.hp, 1), "mhp": r(p.max_hp, 1), "dn": b(p.downed), "dead": b(p.dead),
             "dg": b(p.dodging), "st": p.state, "mel": r(p.melee_time), "mdur": r(p.melee_duration),
             "mrad": r(p.melee_radius), "stam": r(p.stamina, 2), "aiming": b(p.aiming),
             "tos": r(p.time_outside_screen)}
        if getattr(p, "velocity_gated", False):
            d["vg"] = [r(p.raw_vel_x), r(p.raw_vel_y)]
        w = p.weapon
        d["w"] = None if w is None else {
            "name": w.name, "kind": w.kind, "id": w.weapon_id, "rnd": w.rounds, "mag": w.mag_size, "mags": w.mags,
            "rl": w.reloading, "rl_t": r(w.reload_left), "heat": r(w.heat), "spr": r(w.spread, 2),
            "wait": r(w.fire_wait), "range": r(w.range, 1), "rate": r(w.firerate, 1)}
        i = p.input
        d["in"] = None if i is None else [b(i.fire), b(i.aim), r(i.move_x), r(i.move_y), r(i.aim_x), r(i.aim_y),
                                          b(i.shot)]
        st = p.status
        d["ss"] = None if st is None else [r(st.presses, 2), r(st.needed, 2), r(st.downed_for), r(st.prone_for),
                                           r(st.reset_timer), r(st.getup_left), st.burning, r(st.slow, 2),
                                           st.slow_source, st.poisoned, r(st.since_hit)]
        # 第 14 版 M18 盾量：盾量、盾上限、盾开着、充能计时器（没背盾 / 旧 mod / 读不到是 null，整项 None 就不写）
        if getattr(p, "shield_pts", None) is not None or getattr(p, "shield_on", None) is not None:
            d["sh"] = [r(getattr(p, "shield_pts", None), 2), r(getattr(p, "shield_max", None), 2),
                       None if getattr(p, "shield_on", None) is None else b(p.shield_on),
                       r(getattr(p, "shield_timer", None), 3)]
        if m is not None:
            d.update(btn=list(m.buttons), sub=m.substate, st_t=r(m.state_since), con=r(m.constitution, 1),
                     sprint=r(m.sprint_amount), fire_amt=r(m.fire_amount), want=r(m.wanted_speed),
                     mz=None if m.muzzle is None else r(m.muzzle, 1), sw=m.switch_weapon, vz=r(m.vel_z),
                     sub_t=r(m.substate_since), ib=r(m.interact_button))
            if m.dive_timer is not None:
                d["dive"] = [r(m.dive_timer), b(m.dive_get_up)]
            if m.get_up_presses is not None:
                d["gu"] = [r(m.get_up_presses, 2), r(m.get_up_needed, 2), r(m.get_up_reset, 2)]
            if m.launcher:
                ln = m.launcher
                d["ln"] = [b(ln["charging"]), r(ln["charge"]), ln["burst_round"], r(ln["burst_timer"]),
                           b(ln["wait_release"])]
        uid = p.unit_id
        self._put(s, f"wx{uid}", rl(p.weapons_raw, 3))
        self._put(s, f"sg{uid}", rl(p.strat_raw, 2))
        self._put(s, f"rk{uid}", rl(p.rocks, 1))
        if w is not None:
            self._put(s, f"wf{uid}", [r(getattr(w, c, None)) for c in WEAPON_COLS])
        self._put_raw(s, f"si{uid}", p.sight)
        self._put_raw(s, f"ar{uid}", p.arc)
        self._put_raw(s, f"mv{uid}", p.motion_raw)
        return d

    def _player_events(self, p, d, gt, f):
        uid = p.unit_id
        old = self.prev.get(uid)
        self.prev[uid] = d
        if len(self.prev) > 64:
            self.prev = {k: v for k, v in self.prev.items() if k == uid or not v["dead"]}
        ev = lambda k, **kw: {"t": "ev", "k": k, "gt": r(gt, 3), "f": f, "who": uid, "slot": p.slot, "pad": p.pad,  # noqa: E731
                              "x": d["x"], "y": d["y"], **kw}
        out = []
        if old is None:
            return [ev("spawn", st=p.state)]
        if p.state != old["st"]:
            st = p.state
            if "Melee" in st and "Melee" not in old["st"]:
                out.append(ev("melee", st=st))
            if st == "CharacterStateDodge":
                out.append(ev("dive"))
        if d["dn"] and not old["dn"]:
            out.append(ev("downed"))
        if old["dn"] and not d["dn"] and not d["dead"]:
            out.append(ev("up"))
        if d["dead"] and not old["dead"]:
            out.append(ev("dead"))
        name, oname = (d["w"] or {}).get("name"), (old["w"] or {}).get("name")
        if name and oname and name != oname:
            out.append(ev("switch", frm=oname, to=name))
        if not self.has_mech and old["hp"] - d["hp"] >= HP_DROP and not d["dead"]:
            out.append(ev("hp_drop", hp=d["hp"], lost=r(old["hp"] - d["hp"], 1)))
        shot = d["in"] is not None and d["in"][6]
        fs = self.fire.get(uid)
        if shot:
            if fs is None:
                self.fire[uid] = [gt, gt, 1, name]
                out.append(ev("fire", weapon=name))
            else:
                fs[1] = gt
                fs[2] += 1
        elif fs is not None and gt - fs[1] > FIRE_GAP:
            del self.fire[uid]
            out.append(ev("fire_end", weapon=fs[3], secs=r(fs[1] - fs[0], 2), shot_frames=fs[2]))
        return out


# ---------- 缓冲 ----------

class Chunk:
    __slots__ = ("lines", "wall0", "wall1", "gt0", "gt1", "frames", "marks", "data")

    def __init__(self):
        self.lines, self.marks = [], []
        self.wall0 = self.wall1 = self.gt0 = self.gt1 = None
        self.frames = 0
        self.data = None

    @property
    def dur(self):
        return 0.0 if self.wall0 is None else self.wall1 - self.wall0


class Buffer:
    """一段一段攒行：每段约 10 秒，满了交给后台线程压成一个 gzip 块（多个 gzip 块直接接起来还是合法的 gzip 文件）。
    只留录制时间加起来最近 WINDOW 秒的段。sync=True 时不开线程（离线测试用）。"""

    def __init__(self, window=WINDOW, chunk_secs=CHUNK_SECS, sync=False):
        self.window, self.chunk_secs, self.sync = window, chunk_secs, sync
        self.done = collections.deque()     # 压好的段
        self.lock = threading.Lock()
        self.cur = None
        self.q = None if sync else queue.Queue()
        if not sync:
            threading.Thread(target=self._run, daemon=True).start()

    def add(self, line, wall_t=None, gt=None, frame=False):
        if self.cur is None:
            self.cur = Chunk()
        c = self.cur
        c.lines.append(line)
        if wall_t is not None:
            if c.wall0 is None:
                c.wall0, c.gt0 = wall_t, gt
            c.wall1, c.gt1 = wall_t, gt
        if frame:
            c.frames += 1

    def full(self):
        return self.cur is not None and self.cur.dur >= self.chunk_secs

    def close(self):
        """收尾当前段（换段、暂停、存之前都要调）。"""
        c, self.cur = self.cur, None
        if c is None or not c.frames:
            return
        if self.sync:
            self._finish(c)
        else:
            self.q.put(c)

    def _run(self):
        while True:
            c = self.q.get()
            try:
                self._finish(c)
            finally:
                self.q.task_done()

    def _finish(self, c):
        c.data = gzip.compress(("\n".join(c.lines) + "\n").encode("utf-8"), compresslevel=6)
        c.lines = None
        with self.lock:
            self.done.append(c)
            total = sum(x.dur for x in self.done)
            while len(self.done) > 1 and total - self.done[0].dur >= self.window:
                total -= self.done.popleft().dur

    def wait(self):
        if self.q is not None:
            self.q.join()

    def snapshot(self):
        with self.lock:
            return list(self.done)

    def stats(self):
        """(缓冲里录了几秒, 压好后多少字节)，当前段也算进秒数。"""
        with self.lock:
            secs = sum(c.dur for c in self.done)
            size = sum(len(c.data) for c in self.done)
        if self.cur is not None:
            secs += self.cur.dur
        return secs, size


# ---------- 黑匣子 ----------

class BlackBox:
    def __init__(self, out_dir=LOG_DIR, beep=None, window=WINDOW, chunk_secs=CHUNK_SECS, sync=False, echo=True, buf=None):
        self.out_dir = out_dir
        self.beep = beep or (lambda name: None)
        self.buf = buf or Buffer(window, chunk_secs, sync)
        self.enc = Encoder()
        self.on = False
        self.echo = echo
        self.last_snap = None
        self.saves = []
        self.pending_marks = []     # 这段里的标记（关段时带走，存文件时写进开头那行）

    def say(self, msg):
        if self.echo:
            print(msg, flush=True)

    def _line(self, rec, frame=False, snap=None):
        self.buf.add(json.dumps(rec, ensure_ascii=False, separators=(",", ":")),
                     snap.wall_time if snap else None, snap.game_time if snap else None, frame)

    def _close(self):
        if self.buf.cur is not None:
            self.buf.cur.marks += self.pending_marks
        self.pending_marks = []
        self.buf.close()

    def _rec(self, on):
        s = self.last_snap
        self._line({"t": "rec", "on": on, "wall": wall(time.time()), "gt": r(s.game_time, 3) if s else None,
                    "f": s.frame if s else None})

    def toggle(self):
        if self.on:
            self._rec(False)
            self._close()
            self.on = False
            self.beep("pause")
            self.say(">> 暂停录制（缓冲留着，按 + 还能存）")
        else:
            self.on = True
            self.beep("start")
            self.say(">> 开始录制")

    def mark(self, n):
        if not self.on:
            self.beep("no")
            self.say(f">> 标记 {n} 没记：现在没在录（先按小键盘 -）")
            return
        s = self.last_snap
        players = [[p.slot, p.pad, p.unit_id, b(p.dead)] for p in s.players] if s else []
        m = {"t": "mark", "n": n, "wall": wall(time.time()), "gt": r(s.game_time, 3) if s else None,
             "f": s.frame if s else None, "players": players}
        self._line(m)
        self.pending_marks.append(m)
        self.beep(n)
        live = " ".join(f"[槽{p.slot} 手柄{p.pad}{' 死' if p.dead else ''}]" for p in s.players) if s else "（还没连上游戏）"
        self.say(f">> 标记：看 {n} 号玩家  游戏时间 {m['gt']}  场上 {live}")

    def feed(self, snap, mf=None):
        """新的一帧。没在录时只记住它（标记要用），不进缓冲。"""
        self.last_snap = snap
        if not self.on:
            return
        if self.buf.full():
            self._close()
        if self.buf.cur is None or not self.buf.cur.frames:
            self.enc.reset()
            self._line({"t": "chunk", "wall": wall(snap.wall_time), "gt": r(snap.game_time, 3), "f": snap.frame})
        row, evs = self.enc.encode(snap, mf)
        self._line(row, frame=True, snap=snap)
        for e in evs:
            self._line(e)

    def summary(self, chunks):
        """这几段的时长、帧数、标记：存文件时写进记录。"""
        marks = [m for c in chunks for m in c.marks]
        return {"saved": datetime.now().isoformat(timespec="seconds"), "secs": r(sum(c.dur for c in chunks), 1),
                "frames": sum(c.frames for c in chunks), "chunks": len(chunks), "gt0": r(chunks[0].gt0, 3),
                "gt1": r(chunks[-1].gt1, 3), "wall0": wall(chunks[0].wall0), "wall1": wall(chunks[-1].wall1),
                "marks": [{k: m[k] for k in ("n", "gt", "f", "wall")} for m in marks]}

    def save(self, wait=True):
        """把缓冲存成文件。当前段在调用的线程里收尾（和 feed 同一个线程调）；等压完、写盘在后台线程（wait=False 时）。
        返回文件路径；缓冲是空的返回 None（wait=False 时只能从提示音 / 窗口看出来）。"""
        self._close()
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, datetime.now().strftime("bb_%Y%m%d_%H%M%S.jsonl.gz"))
        n = 1
        while os.path.exists(path) or path in self.saves:
            n += 1
            path = os.path.join(self.out_dir, datetime.now().strftime(f"bb_%Y%m%d_%H%M%S_{n}.jsonl.gz"))

        def write():
            self.buf.wait()
            chunks = self.buf.snapshot()
            if not chunks:
                self.beep("no")
                self.say(">> 没东西可存：缓冲是空的（先按小键盘 - 开始录）")
                self.saves.remove(path)
                return None
            head = {"t": "start", "fmt": FMT, "bridge": BRIDGE_VERSION, **self.summary(chunks),
                    "window": self.buf.window, "enemy_cols": ENEMY_COLS, "weapon_cols": WEAPON_COLS}
            tmp = path + ".part"
            with open(tmp, "wb") as fh:
                fh.write(gzip.compress((json.dumps(head, ensure_ascii=False) + "\n").encode("utf-8")))
                for c in chunks:
                    fh.write(c.data)
            os.replace(tmp, path)
            self.beep("saved")
            mins, secs = divmod(int(head["secs"]), 60)
            self.say(f">> 存好了：{path}\n   {mins} 分 {secs} 秒，{head['frames']} 帧，标记 {len(head['marks'])} 个，"
                     f"{os.path.getsize(path) / 1e6:.1f} MB")
            return path

        self.saves.append(path)     # 先占住文件名，连按两下 + 不会撞名
        if wait:
            return write()
        threading.Thread(target=write, daemon=True).start()
        return path


# ---------- 读存好的文件 ----------

def rows(path):
    """一行一行读（dict）。录到一半断电时最后一段可能是残的，读到那里就停。"""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        try:
            for line in fh:
                if line.strip():
                    yield json.loads(line)
        except (EOFError, json.JSONDecodeError):
            return


def frames(path):
    """读文件，"变了才记"的区接着往下带：每行给出 (行, 到这一行为止每个区最新的值)。虫子行可以用 enemy(行里一只) 变成 dict。"""
    sec = {}
    for row in rows(path):
        if row["t"] == "chunk":
            sec = {}
        elif row["t"] == "f":
            sec.update(row.get("s", {}))
        yield row, sec


def enemy(cells):
    return dict(zip(ENEMY_COLS, cells))


def show(path):
    head = None
    players, evs = {}, collections.Counter()
    for row in rows(path):
        t = row["t"]
        if t == "start":
            head = row
        elif t == "end":
            head.update(row)
        elif t == "f":
            for p in row["p"]:
                players.setdefault(p["id"], (p["s"], p["pad"]))
        elif t == "ev":
            evs[row["k"]] += 1
    if "saved" not in head:
        print(f"{path}\n  这个文件没有正常结束（录制时程序被关掉了）；数据能读，没有时长和标记汇总。")
        return
    print(f"{path}\n  存于 {head['saved']}，{head['secs']} 秒（墙钟 {head['wall0']} ~ {head['wall1']}，"
          f"游戏时间 {head['gt0']} ~ {head['gt1']}），{head['frames']} 帧")
    print("  出现过的角色（编号: 槽位, 手柄）：" + "，".join(f"{k}: {v}" for k, v in players.items()))
    print("  事件：" + "，".join(f"{k} {v}" for k, v in evs.most_common()))
    for m in head["marks"]:
        off = None if m["gt"] is None or head["gt0"] is None else r(m["gt"] - head["gt0"], 1)
        print(f"  标记 {m['n']} 号：游戏时间 {m['gt']}（开头后 {off} 秒，含暂停）墙钟 {m['wall']} 帧 {m['f']}")


# ---------- 主循环 ----------

def status_line(bx, snap, fps):
    secs, size = bx.buf.stats()
    rec = "●录制中" if bx.on else "○没在录"
    mins, s = divmod(int(secs), 60)
    parts = [f"{rec} 缓冲 {mins}:{s:02d}/{int(WINDOW // 60)}:00 {size / 1e6:.0f}MB"]
    if snap is not None:
        parts.append(f"游戏 {fps:.0f}fps 玩家 {len(snap.players)} 虫 {len(snap.enemies)}")
    return " ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "show"))
    ap.add_argument("file", nargs="?")
    ap.add_argument("--process", default="helldivers.exe")
    ap.add_argument("--hz", type=float, default=240, help="轮询频率（比游戏帧率高才不漏帧）")
    ap.add_argument("--no-beep", action="store_true")
    args = ap.parse_args()
    if args.cmd == "show":
        show(args.file)
        return

    from mech_feed import MechTable
    beep = Beeper(not args.no_beep)
    bx = BlackBox(beep=beep)
    keys = Keys()
    print(f"存到：{LOG_DIR}")
    print("小键盘：- 开始 / 暂停录制，+ 存最近 10 分钟，1~4 标记看几号玩家（要开 NumLock）。Ctrl+C 结束（没存的就丢了）。")
    if not Keys.numlock():
        print("!! NumLock 没开：标记 1~4 认不到，请按一下 NumLock")
        beep("no")
    bridge = mech = last_mf = None
    waiting = None
    last_new = time.time()
    last_try = 0.0
    last_print = 0.0
    fps_t, fps_f, fps = time.time(), None, 0.0
    try:
        while True:
            for k in keys.poll():
                if k == "toggle":
                    bx.toggle()
                elif k == "save":
                    bx.save(wait=False)
                else:
                    bx.mark(k)
            now = time.time()
            stale = bridge is not None and now - last_new > REATTACH_SECS and now - last_try > REATTACH_SECS
            dead = bridge is not None and not bridge.alive()
            if (bridge is None and now - last_try >= RETRY_SECS) or dead or stale:
                last_try = now
                pid = find_pid(args.process)
                if bridge is not None:
                    bridge.close()
                bridge = Bridge.attach(args.process, pid=pid) if pid else None
                if mech is not None:
                    mech.close()
                mech = MechTable.attach(pid) if pid and bridge else None
                last_mf = None
                if bridge is None:
                    msg = "等待游戏……（要先装 mod，进关卡后有角色才有表）"
                    if msg != waiting:
                        print(msg, flush=True)
                        waiting = msg
                else:
                    waiting = None
                    last_new = now
                    print(f"已连接 pid={bridge.pid} 表=0x{bridge.addr:X}，"
                          f"机制表{'有' if mech else '没找到（只录 ai_bridge 的数）'}", flush=True)
            if bridge is None:
                time.sleep(1 / args.hz)
                continue
            snap = bridge.read()
            if snap is not None:
                last_new = now
                mf = mech.read() if mech is not None else None
                if mf is not None:
                    last_mf = mf
                elif last_mf is not None:
                    # 机制表这一刻还没写新帧：玩家那几样沿用上一帧，事件留到下次读（不重复记）
                    mf = dataclasses.replace(last_mf, events=[], lost_events=0)
                bx.feed(snap, mf)
                if fps_f is None:
                    fps_t, fps_f = now, snap.frame
                elif now - fps_t >= 2:
                    fps = (snap.frame - fps_f) / (now - fps_t)
                    fps_t, fps_f = now, snap.frame
            if now - last_print >= 1:
                last_print = now
                print(status_line(bx, bx.last_snap, fps), flush=True)
            time.sleep(1 / args.hz)
    except KeyboardInterrupt:
        pass
    print("结束。" + (f"这次存了 {len(bx.saves)} 个文件。" if bx.saves else "这次没存文件。"))


if __name__ == "__main__":
    main()
