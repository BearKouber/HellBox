r"""录制器的后台（HD1-025）：按快捷键开始 / 结束，一局录一个文件，给以后训练用。界面在 recorder_app.py。

只读游戏，不按手柄、不拦按键。编码沿用 blackbox.py，文件格式相同（见 HD1开发经验.md "黑匣子"一节），
差别是不留在内存里循环，而是每 10 秒一段接到文件尾巴上，所以长度不限；开头那行没有时长和标记，放在最后的 end 行。
每段都是完整的 gzip 块，程序中途没了，已经写下去的段照样能用 blackbox.rows 读。

    rec = Recorder()
    threading.Thread(target=rec.run, daemon=True).start()
    rec.toggle()      # 开始 / 结束；界面的按钮用，快捷键在 run 里自己看
    rec.shutdown()    # 退出：录着的先收好
"""
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

from blackbox import (BRIDGE_VERSION, CHUNK_SECS, ENEMY_COLS, LOG_DIR as BB_DIR, REATTACH_SECS, VK_SUBTRACT,
                      WEAPON_COLS, BlackBox, Beeper, Buffer, Encoder, Keys)
from bridge import Bridge, find_pid
from mech_feed import MechTable

# 打包成 exe（发给别人，HD1-034）时录像放在 exe 旁边，好找、好打包；源码跑时照旧放 ai/logs/recordings
REC_DIR = (os.path.join(os.path.dirname(sys.executable), "recordings") if getattr(sys, "frozen", False)
           else os.path.join(os.path.dirname(BB_DIR), "recordings"))
INDEX = "index.jsonl"       # 每录完一个文件追加一行汇总，界面列表用
PROCESS = "helldivers.exe"
REC_HZ = 240                # 录制中查表的频率（比游戏帧率高才不漏帧）
IDLE_HZ = 20                # 没在录时只刷界面用
FIND_SECS = 6.0             # 没连上时隔这么久找一次（找表要扫一遍游戏内存）
GAP_SECS = 2.0              # 这么久没新帧（读图、回菜单）算断开，另起一段，空白不算进时长
MAX_GAP_FRAMES = 120        # 帧号跳得比这还多是换了表，不算漏帧
# HD1-034 心跳：录制器开着就每隔 BEAT_SECS 往这里写当前时间；发行版核心看它新不新决定休眠（mod/src/rec_gate_post.lua）
HEARTBEAT = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Arrowhead", "Helldivers", "hellbox",
                         "recorder-alive.txt")
BEAT_SECS = 5.0
# HD1-034 自动录：进关卡（任务区有种子和难度）就开，离开关卡这么久（读图、结算、回飞船都没有新帧）就收
AUTO_END_SECS = 15.0
RUMBLER = "mortar"          # 雷鸣（M-25 雷鸣者）：战略配备 stratagem_mortar、武器 wep_mortar / wepicon_mortar

# HD1-040 训练用的精简格式（fmt 3）。黑匣子（开发查问题用）还是全量的 fmt 2，这里只改录像。
# 2026-11-26 用户 5 局实测：一分钟约 10MB，九成以上是敌人：弹道原始格子（s 里的 bl…）约 30%、敌人 logic 数组占敌人 46%、
# 每帧重复的种类名 16%；玩家只占 5%。所以：玩家每帧全记；敌人每 ENEMY_EVERY 帧记一次、只留下面这几列；
# 种类 / 名字 / 最大血量每个敌人只记一次（s.en）；不记弹道；掉落物、信标、镜头、危险区每 SLOW_EVERY 帧才看变没变。
FMT = 3
ENEMY_EVERY = 3             # 游戏约 200 帧 / 秒，敌人每 3 帧一次 ≈ 60 多次 / 秒
SLOW_EVERY = 30             # ≈ 7 次 / 秒
ENEMY_KEEP = ("id", "x", "y", "hp", "dead", "st", "alert", "tgt", "rot", "st_t", "charge_cd", "area_cd")
ENEMY_STATIC = ("type", "name", "mhp")
SLOW_KEYS = ("drops", "beacons", "camera", "hazards")
SLOW_PREFIX = ("sg",)       # 每人的战略配备格子（冷却每帧在走，占缩小后的 11%）
_KEEP_I = tuple(ENEMY_COLS.index(c) for c in ENEMY_KEEP)
_STATIC_I = tuple(ENEMY_COLS.index(c) for c in ENEMY_STATIC)


class TrainEncoder(Encoder):
    """黑匣子的编码器减肥版（fmt 3）。事件（击杀、死亡、开火……）照常每帧认，只是写出去的东西少。"""

    def __init__(self):
        super().__init__()
        self.n = 0
        self.fresh = True       # 段开头第一帧：所有东西都写全，段可以单独读
        self.known = set()      # 这段里已经写过种类的敌人

    def reset(self):
        super().reset()
        self.fresh = True
        self.known = set()

    def _put(self, s, key, val):
        if (key in SLOW_KEYS or key.startswith(SLOW_PREFIX)) and not self.fresh and self.n % SLOW_EVERY:
            return
        super()._put(s, key, val)

    def _put_raw(self, s, key, cells, n=3):
        if key.startswith("bl"):
            return
        super()._put_raw(s, key, cells, n)

    def encode(self, snap, mf=None):
        self.n += 1
        row, evs = super().encode(snap, mf)
        es = row.pop("e")
        if self.fresh or self.n % ENEMY_EVERY == 0:
            new = {}
            for e in es:
                if e[0] not in self.known:
                    self.known.add(e[0])
                    new[e[0]] = [e[i] for i in _STATIC_I]
            row["e"] = [[e[i] for i in _KEEP_I] for e in es]
            if new:
                row.setdefault("s", {})["en"] = new
        self.fresh = False
        return row, evs


def gz_line(rec):
    return gzip.compress((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))


class DiskBuffer(Buffer):
    """压好的段直接写进文件，内存里只留段的时长和标记。写盘失败记在 error 里，由 Recorder 结束这次录制。"""

    def __init__(self, path, head):
        self.fh = open(path, "xb")
        self.fh.write(gz_line(head))
        self.size = self.fh.tell()
        self.error = None
        super().__init__(chunk_secs=CHUNK_SECS)

    def _run(self):
        while True:
            c = self.q.get()
            try:
                if c is None:
                    return
                self._finish(c)
            except OSError as e:
                self.error = str(e)
            finally:
                self.q.task_done()

    def _finish(self, c):
        data = gzip.compress(("\n".join(c.lines) + "\n").encode("utf-8"), compresslevel=6)
        c.lines = None
        if self.error is None:
            self.fh.write(data)
            self.fh.flush()
        with self.lock:
            self.done.append(c)
            self.size += len(data)

    def seal(self, tail):
        """等后台写完，补上最后一行，关文件。"""
        self.q.put(None)
        self.q.join()
        if tail is not None:
            self.fh.write(gz_line(tail))
        self.fh.close()


def mission_key(snap):
    """这一帧在不在任务里：返回任务种子（不在任务里返回 None）。任务区第 0 格区版本、第 1 格写好了、第 9 格种子、第 10 格难度。"""
    c = snap.mission_cells if snap is not None else ()
    if len(c) > 12 and c[0] >= 1 and c[1] and c[9] >= 0 and c[10] >= 0:
        return int(c[9])
    return None


class Match:
    """一局的摘要（HD1-034）：难度、任务、结果、本机玩家是谁、每人死几次、带了什么。写进文件最后一行和录像列表。"""

    def __init__(self):
        self.seed = self.difficulty = self.mission_type = self.enemy = None
        self.obj_total = self.obj_done = self.obj_failed = None
        self.extracted = self.completed = False
        # HD1-040 改：按角色编号（一条命一个编号）记，不按槽位。槽位是按出生先后排的，复活后会变，
        # 多人局以前会把全队的死都算成本机的（实测一局显示死 42 次）。
        # 本机的命 = 活着时手柄编号 >= 0（联机别人的是 -1；死了以后本机的也变 -1，所以只看活着的时候）
        self.local = set()          # 本机的角色编号
        self.lives = set()          # 出现过的所有角色编号
        self.most = 0               # 同一帧里最多几个玩家
        self.died = set()           # 死过的角色编号
        self.dead = {}              # 角色编号 -> 上一帧死没死
        self.strats = {}            # 角色编号 -> 战略配备名
        self.weapons = {}           # 角色编号 -> 主 / 副 / 支援武器名
        self.lock = False           # 机制表报过锁血（只有自用版会有）

    def feed(self, snap, mf):
        c = snap.mission_cells
        if mission_key(snap) is not None:
            if self.seed is None:
                self.seed, self.difficulty = int(c[9]), int(c[10])
                self.mission_type, self.enemy = int(c[11]), int(c[12])
            self.extracted = self.extracted or bool(c[3])
            self.completed = self.completed or bool(c[4])
            if c[6] >= 0:
                self.obj_total, self.obj_done, self.obj_failed = int(c[6]), int(c[7]), int(c[8])
        alive = 0
        for p in snap.players:
            uid = p.unit_id
            self.lives.add(uid)
            if not p.dead:
                alive += 1
                if p.pad >= 0:
                    self.local.add(uid)
            was = self.dead.get(uid)
            if p.dead and was is False:
                self.died.add(uid)
            self.dead[uid] = p.dead
            if p.strat_raw:
                names = self.strats.setdefault(uid, set())
                names.update(n for n in p.strat_raw[0::6] if isinstance(n, str) and n)
            if p.weapons_raw:
                names = self.weapons.setdefault(uid, set())
                names.update(n for n in p.weapons_raw[1::14] if isinstance(n, str) and n)
        self.most = max(self.most, alive)
        if mf is not None and mf.lock:
            self.lock = True

    def result(self):
        if self.seed is None:
            return "none"           # 没进过任务（飞船上、菜单）
        if self.extracted:
            return "extracted"
        if self.completed:
            return "completed"      # 任务完成了但没看到撤离
        return "left"               # 没完成就结束了（失败、放弃、掉线）

    def summary(self):
        def kit(ids, table):
            return sorted({n for u in ids for n in table.get(u, ())})
        others = self.lives - self.local
        mine = kit(self.local, self.strats) + kit(self.local, self.weapons)
        team = mine + kit(others, self.strats) + kit(others, self.weapons)
        return {"seed": self.seed, "difficulty": self.difficulty, "mission_type": self.mission_type, "enemy": self.enemy,
                "result": self.result(), "objectives": [self.obj_done, self.obj_total, self.obj_failed],
                "local_ids": sorted(self.local), "players": self.most,
                "local_deaths": len(self.died & self.local), "team_deaths": len(self.died),
                "strats": {"local": kit(self.local, self.strats), "others": kit(others, self.strats)},
                "weapons": {"local": kit(self.local, self.weapons), "others": kit(others, self.weapons)},
                "rumbler": any(RUMBLER in n for n in mine), "team_rumbler": any(RUMBLER in n for n in team),
                "lock_seen": self.lock}


class Take(BlackBox):
    """一次录制 = 一个文件。"""

    def __init__(self, path, beep, auto=False, core=None):
        head = {"t": "start", "fmt": FMT, "bridge": BRIDGE_VERSION, "started": datetime.now().isoformat(timespec="seconds"),
                "enemy_cols": ENEMY_KEEP, "enemy_static": ENEMY_STATIC, "enemy_every": ENEMY_EVERY,
                "slow_every": SLOW_EVERY, "weapon_cols": WEAPON_COLS, "auto": auto, "core": core}
        super().__init__(os.path.dirname(path), beep, echo=False, buf=DiskBuffer(path, head))
        self.enc = TrainEncoder()
        self.path = path
        self.auto = auto            # 自动开的（进关卡开、离开关卡收）
        self.core = core            # 游戏里是哪种核心（rec_core.status()），发行版 = hellbox / ours
        self.match = Match()
        self.on = True
        self.t0 = time.time()
        self.frames = self.lost_frames = self.lost_events = 0
        self.has_mech = False
        self.prev_frame = self.prev_wall = None

    def feed(self, snap, mf=None):
        if self.prev_wall is not None and snap.wall_time - self.prev_wall > GAP_SECS:
            self._close()
        if self.prev_frame is not None and 1 < snap.frame - self.prev_frame <= MAX_GAP_FRAMES:
            self.lost_frames += snap.frame - self.prev_frame - 1
        self.prev_frame, self.prev_wall = snap.frame, snap.wall_time
        self.frames += 1
        self.match.feed(snap, mf)
        if mf is not None:
            self.has_mech = True
            self.lost_events += mf.lost_events
        super().feed(snap, mf)

    def finish(self):
        """收尾。返回写进索引的汇总；一帧都没录到时删掉文件，返回 None。"""
        self.on = False
        self._close()
        self.buf.q.join()
        chunks = self.buf.snapshot()
        if not chunks:
            self.buf.seal(None)
            os.remove(self.path)
            return None
        game = self.match.summary()
        end = {"t": "end", **self.summary(chunks), "lost_frames": self.lost_frames, "lost_events": self.lost_events,
               "has_mech": self.has_mech, "auto": self.auto, "core": self.core, "game": game}
        self.buf.seal(end)
        info = {k: end[k] for k in ("saved", "secs", "frames", "lost_frames", "has_mech", "auto", "core", "game")}
        info.update(file=os.path.basename(self.path), marks=len(end["marks"]), size=os.path.getsize(self.path))
        with open(os.path.join(self.out_dir, INDEX), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(info, ensure_ascii=False) + "\n")
        return info


def _score_summary(out_dir, name):
    """评分文件（rec_score.py 写的 <名字>.score.json）里的汇总；还没算就是 None。"""
    try:
        with open(os.path.join(out_dir, name.replace(".jsonl.gz", "") + ".score.json"), encoding="utf-8") as fh:
            return json.load(fh).get("summary")
    except (OSError, ValueError):
        return None


def recordings(out_dir=REC_DIR, n=None):
    """录好的文件，新的在前：[{file, path, saved, secs, frames, lost_frames, marks, size, ok}]。ok = 正常结束的。"""
    known = {}
    try:
        with open(os.path.join(out_dir, INDEX), encoding="utf-8") as fh:
            for line in fh:
                try:
                    i = json.loads(line)
                except json.JSONDecodeError:
                    continue
                known[i["file"]] = i
    except OSError:
        pass
    try:
        names = sorted((f for f in os.listdir(out_dir) if f.startswith("rec_") and f.endswith(".jsonl.gz")), reverse=True)
    except OSError:
        return []
    out = []
    for name in names[:n]:
        path = os.path.join(out_dir, name)
        i = dict(known.get(name) or {"file": name})
        i.update(path=path, ok=name in known, size=os.path.getsize(path), score=_score_summary(out_dir, name))
        out.append(i)
    return out


class Recorder:
    def __init__(self, out_dir=REC_DIR, process=PROCESS, hotkey=VK_SUBTRACT, sound=True, auto=True, core_check=None):
        self.out_dir, self.process = out_dir, process
        self.sound = sound
        self.auto = auto            # HD1-034：进关卡自动开录、离开关卡自动收
        self.core_check = core_check    # 查游戏里核心的函数（rec_core.status），没有就不查
        self.core = None            # 最近一次查到的核心状态
        self._beeper = Beeper()
        self.keys = Keys(toggle=hotkey, save=None)
        self.cmds = queue.SimpleQueue()
        self.quit = threading.Event()
        self.done = threading.Event()
        self.bridge = self.mech = self.last_mf = None
        self.take = None
        self.last_snap = None
        self.link = "no_game"       # no_game / no_table / version / linked / error
        self.other_version = None   # link = version 时，游戏里表的版本
        self.fps = 0.0
        self.note = ("", ())        # 最近一件事：(中文模板, 参数)，界面翻译后 format
        self.saved_seq = 0          # 每收好一个文件加 1，界面看到变了就刷新列表
        self._finding = False
        self._found = None
        self._next_find = 0.0
        self._last_new = 0.0
        self._fps_t, self._fps_f = 0.0, None
        self._next_beat = 0.0
        self._skip_seed = None      # 手动停掉的那一局，自动录不再重开（换了任务才开）
        self._last_in_mission = 0.0
        self._scoring = False       # 后台正在给录像打分

    # ---------- 给界面用（别的线程调） ----------

    def toggle(self):
        self.cmds.put("toggle")

    def set_hotkey(self, vk):
        self.cmds.put(("hotkey", vk))

    def set_auto(self, on):
        self.cmds.put(("auto", bool(on)))

    def recheck_core(self):
        self.cmds.put("core")

    def shutdown(self):
        self.quit.set()
        self.done.wait(30)

    def beep(self, name):
        if self.sound:
            self._beeper(name)

    def say(self, template, *args):
        self.note = (template, args)

    @property
    def mech_ok(self):
        return self.mech is not None

    # ---------- 心跳（发行版核心靠它醒来） ----------

    def _beat(self, now):
        if now < self._next_beat:
            return
        self._next_beat = now + BEAT_SECS
        try:
            os.makedirs(os.path.dirname(HEARTBEAT), exist_ok=True)
            with open(HEARTBEAT, "w", encoding="ascii") as fh:
                fh.write(f"{int(time.time())}\n")
        except OSError:
            pass

    @staticmethod
    def _stop_beat():
        try:
            os.remove(HEARTBEAT)
        except OSError:
            pass

    def _check_core(self):
        if self.core_check is None:
            return

        def run():
            try:
                self.core = self.core_check()
            except Exception:
                self.core = "unknown"
        threading.Thread(target=run, daemon=True).start()

    # ---------- 录制 ----------

    def _start(self, auto=False):
        os.makedirs(self.out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, n = os.path.join(self.out_dir, f"rec_{stamp}.jsonl.gz"), 1
        while os.path.exists(path):
            n += 1
            path = os.path.join(self.out_dir, f"rec_{stamp}_{n}.jsonl.gz")
        try:
            self.take = Take(path, self.beep, auto=auto, core=self.core)
        except OSError as e:
            self.say("打不开文件：{0}", str(e))
            self.beep("no")
            return
        self.take.last_snap = self.last_snap
        self.take.seed = mission_key(self.last_snap)
        self.beep("start")
        if auto:
            self.say("进关卡了，自动开始录制")
        else:
            self.say("开始录制" if self.link == "linked" else "开始录制，等游戏连上后才有数据")

    def _stop(self, wait=False):
        take, self.take = self.take, None

        def finish():
            try:
                info = take.finish()
            except OSError as e:
                self.say("收尾失败：{0}", str(e))
                self.beep("no")
                return
            if info is None:
                self.say("没录到数据，没存文件")
                self.beep("no")
            else:
                mins, secs = divmod(int(info["secs"]), 60)
                self.say("存好了：{0} 分 {1} 秒，{2:.1f} MB", mins, secs, info["size"] / 1e6)
                self.beep("saved")
            self.saved_seq += 1
            if not wait:
                self._score_pending()

        if wait:
            finish()
        else:
            threading.Thread(target=finish, daemon=True).start()

    # ---------- 打分（HD1-040，2026-11-26）：录完一局在后台算评分文件，录像本身不动 ----------

    def _score_pending(self):
        """给还没有评分的录像打分（新的先算）。一次只跑一个；正在录下一局时停着等，不抢游戏的 CPU。出错不影响录制。"""
        if self._scoring:
            return
        self._scoring = True

        def pause():
            while self.take is not None:
                if self.quit.is_set():
                    raise InterruptedError
                time.sleep(1.0)
            if self.quit.is_set():
                raise InterruptedError

        def run():
            try:
                import rec_score
                todo = [i for i in recordings(self.out_dir) if i.get("ok") and i.get("score") is None]
                for i in todo:
                    try:
                        rec_score.score_into(i["path"], self.out_dir, pause)
                    except InterruptedError:
                        return
                    except Exception as e:  # 坏文件读不了：记一个出错的评分（列表不再显示"评分中"），别卡住后面的
                        try:
                            dst = os.path.join(self.out_dir, i["file"].replace(".jsonl.gz", "") + ".score.json")
                            with open(dst, "w", encoding="utf-8") as fh:
                                json.dump({"summary": {"error": str(e)[:200]}}, fh, ensure_ascii=False)
                        except OSError:
                            pass
                    self.saved_seq += 1
            except Exception:
                pass
            finally:
                self._scoring = False
        threading.Thread(target=run, daemon=True).start()

    def _toggle(self):
        if self.take is None:
            self._skip_seed = None
            self._start()
        else:
            if self.take.auto:      # 自动开的被手动停：这一局不再自动重开
                self._skip_seed = self.take.seed or mission_key(self.last_snap)
            self._stop()

    def _mark(self, n):
        if self.take is None:
            self.beep("no")
            self.say("标记 {0} 没记：现在没在录", n)
        else:
            self.take.mark(n)
            self.say("标记：看 {0} 号玩家", n)

    def _auto(self, now):
        """进关卡开、换任务另起一个文件、离开关卡（读图、结算、回飞船）够久就收。"""
        fresh = self.bridge is not None and now - self._last_new < GAP_SECS
        seed = mission_key(self.last_snap) if fresh else None
        if seed is not None:
            self._last_in_mission = now
        take = self.take
        if take is not None and take.auto:
            if seed is not None and take.seed is not None and seed != take.seed:
                self._stop()
                take = None
            elif seed is None and now - self._last_in_mission > AUTO_END_SECS:
                self._stop()
                return
            elif take.seed is None and seed is not None:
                take.seed = seed
        if take is None and self.auto and seed is not None and seed != self._skip_seed:
            self._start(auto=True)
        if seed is not None and self._skip_seed is not None and seed != self._skip_seed:
            self._skip_seed = None

    # ---------- 连游戏 ----------

    def _find(self):
        """在单独的线程里跑：扫内存要一两秒，不能卡住快捷键。"""
        try:
            pid = find_pid(self.process)
            if not pid:
                self.link = "no_game"
                return
            if not Bridge.scan(pid):
                self.link = "no_table"
                return
            found = Bridge.attach(self.process, pid=pid)
            if found is None:
                self.link = "version"
                self.other_version = self._table_version(pid)
                return
            self._found = found, MechTable.attach(pid)
        except Exception as e:      # 游戏刚好退出等，下一轮再找
            self.link = "error"
            self.say("连游戏出错：{0}", str(e))
        finally:
            self._finding = False

    @staticmethod
    def _table_version(pid):
        for a in Bridge.scan(pid):
            t = Bridge(pid, a)
            v = t._raw()
            t.close()
            if v:
                return int(v[4])
        return None

    def _drop_link(self):
        if self.bridge is not None:
            self.bridge.close()
        if self.mech is not None:
            self.mech.close()
        self.bridge = self.mech = self.last_mf = None
        self.last_snap = None
        self._fps_f = None
        self.fps = 0.0

    def _keep_linked(self, now):
        if self._found is not None:
            found, self._found = self._found, None
            self._drop_link()
            self.bridge, self.mech = found
            self.link = "linked"
            self._last_new = now
        if self.bridge is not None and not self.bridge.alive():
            self._drop_link()
            self.link = "no_game"
            self._check_core()      # 游戏关了：可能要去装 / 卸核心，重新看一眼
        stale = self.bridge is not None and now - self._last_new > REATTACH_SECS
        if (self.bridge is None or stale) and not self._finding and now >= self._next_find:
            self._next_find = now + (REATTACH_SECS if stale else FIND_SECS)
            self._finding = True
            threading.Thread(target=self._find, daemon=True).start()

    def _read(self, now):
        snap = self.bridge.read()
        if snap is None:
            return
        self._last_new = now
        mf = self.mech.read() if self.mech is not None else None
        if mf is not None:
            self.last_mf = mf
        elif self.last_mf is not None:
            mf = dataclasses.replace(self.last_mf, events=[], lost_events=0)
        self.last_snap = snap
        if self.take is not None:
            self.take.feed(snap, mf)
            err = self.take.buf.error
            if err:
                self.say("写盘失败，已停止：{0}", err)
                self._stop()
        if self._fps_f is None:
            self._fps_t, self._fps_f = now, snap.frame
        elif now - self._fps_t >= 1:
            self.fps = (snap.frame - self._fps_f) / (now - self._fps_t)
            self._fps_t, self._fps_f = now, snap.frame

    # ---------- 主循环 ----------

    def _tick(self):
        while not self.cmds.empty():
            c = self.cmds.get()
            if c == "toggle":
                self._toggle()
            elif c == "core":
                self._check_core()
            elif c[0] == "auto":
                self.auto = c[1]
            else:
                self.keys.toggle = c[1]
                self.keys.down.clear()
        for k in self.keys.poll():
            if k == "toggle":
                self._toggle()
            else:
                self._mark(k)
        now = time.time()
        self._beat(now)
        self._keep_linked(now)
        if self.bridge is not None:
            self._read(now)
        self._auto(now)

    def run(self):
        self._check_core()
        self._score_pending()       # 上次没算完的（比如录完就关了 HellBox）
        while not self.quit.is_set():
            try:
                self._tick()
            except Exception as e:
                self.say("出错：{0}", str(e))
                time.sleep(0.5)
            time.sleep(1 / (REC_HZ if self.take is not None else IDLE_HZ))
        if self.take is not None:
            self._stop(wait=True)
        self._stop_beat()
        self.done.set()


def key_name(vk):
    """虚拟键码 -> 系统的键名（如 Num -、F7）。"""
    user32 = ctypes.WinDLL("user32")
    scan = user32.MapVirtualKeyW(vk, 0)
    if 0x21 <= vk <= 0x2E:      # PageUp、方向键这些是扩展键，不加这一位会读成小键盘
        scan |= 0x100
    buf = ctypes.create_unicode_buffer(32)
    n = user32.GetKeyNameTextW(scan << 16, buf, 32)
    return buf.value if n else f"键 {vk}"
