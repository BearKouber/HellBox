"""HellBox 录制器用的打分（录完一局在后台算 <名字>.score.json）。源头在主仓库 tools/rec_score/score2.py，改了两边一起改。

HD1-040 第一版打分（2026-11-26；用户定"全部交给模型"后，和 agy Neon 两轮讨论定的方案，见
Neuro\\docs\\讨论\\2026-11-26-训练数据打分分片第二轮-agy-Neon.md）。

原则：
- 录像整份保留，不删不切。打分只决定"每一刻学多少"：每 5 秒一个权重（0.25～2.5），坏的几秒权重 0（训练时照样读局面、不学动作）。
- 每条命（本机的）连续保留；只去掉"有毒"的：自己失误致死的死前段、狂炸队友的命、挂机。
- 15 秒滑窗（步长 5 秒）打分：击杀（单价封顶 8）、没警觉时击杀加分、高压下不挂彩加分、转场保底、做目标 / 叫增援加分；
  挨打（0.5 秒内算一次）、倒地、误伤队友扣分。窗口分阶段（撤离 / 目标 / 高压交战 / 普通交战 / 转场），同阶段内比名次。
- 整局按目标完成、撤离给 0.75～1.35 倍。
- 被队友打死的不算反面教材（用户定），只去掉最后 1.5 秒。
- HD1 没有"扶队友"，叫增援 = 本机扔战备后 15 秒内有队友复活。

用法：python score2.py 录像1.jsonl.gz 录像2.jsonl.gz ... [--out 目录]
输出：每个录像旁边（或 --out 里）一个 <名字>.score.json；屏幕上打一张按分数排的命表。
参数都在 P 里，都是先估的初值，靠用户看名次表校准。
"""
import argparse
import bisect
import collections
import gzip
import json
import math
import os
import sys

COST = {  # 出怪表每波 cost ÷ 个数的中位数（costs.py）；没进出怪表的估的
    "bug_scout": 0.17, "bug_warrior": 1.29, "bug_warrior_elite": 1.8, "bug_warrior_commander": 1.33, "bug_tank": 7.5,
    "bug_tank_heavy": 10.0, "bug_hls": 3.0, "bug_stalker": 3.0, "bug_impaler": 5.0,
    "cyborg_initiate": 0.17, "cyborg_initiate_elite": 0.9, "cyborg_soldier": 0.5, "cyborg_soldier_cannon": 1.75,
    "cyborg_soldier_shield": 0.75, "cyborg_soldier_grenadelauncher": 0.75, "cyborg_dog": 1.5,
    "cyborg_berserker": 2.5, "cyborg_berserker_elite": 3.62, "cyborg_hulk": 4.5, "cyborg_hulk_assassinate": 6.25,
    "cyborg_ifv": 25.0,
    "illuminate_tripod": 1.33, "illuminate_tripod_elite": 1.43, "illuminate_apprentice": 2.0,
    "illuminate_trickster": 3.5, "illuminate_obelisk": 3.33, "illuminate_illusionist_assassinate": 4.5,
    "illuminate_illusionist": 4.5, "illuminate_hunter": 1.5, "illuminate_hunter_elite": 2.0,
}

P = dict(
    cost_cap=8.0,               # 单价封顶（装甲车 25 → 8）
    calm_kill_bonus=1.0,        # 打死还没警觉的敌人（没让它报警）
    sample_hz=5.0,              # 局面采样
    win=15.0, step=5.0,         # 滑窗
    near=12.0, mid=22.0, mid_coef=0.4,     # 威胁：12 米内全算，12～22 米算 0.4
    phase_high=30.0, phase_low=8.0,        # 威胁分档（2026-11-26 按用户 5 局校的：窗口威胁中位 22，P75 36，P25 10）
    pressure_coef=0.15, pressure_cap=6.0,  # 高压下没挂彩（威胁 40 封顶）
    transit_bonus=3.0, transit_disp=8.0,   # 转场保底：15 秒净位移 >= 8 米、干净
    obj_bonus=3.0, obj_lead=30.0,          # 目标完成：完成前 30 秒算"推目标"
    reinforce_bonus=3.0, reinforce_secs=15.0,
    pen_hurt=2.5, pen_down=6.0, pen_ff=4.0, pen_teamkill=15.0,
    pulse=0.5,                  # 0.5 秒内连续挨打算一次（实测一半挨打事件间隔 < 0.1 秒）
    fatal_lookback=20.0, tail_self=6.0, tail_mate=1.5,
    idle_split=20.0, idle_mask=5.0,
    min_span=25.0,
    match_lo=0.75, match_hi=1.35,
    w_lo=0.25, w_hi=2.5, w_obj=1.3, w_transit_floor=0.5,
    mask_down_lead=4.0, mask_ff_lead=2.0, mask_ff_tail=0.5,
    drop_frac=0.20, drop_after_hours=5.0,
)
PASSIVE = ("CharacterStateMap", "CharacterStateCutscene", "CharacterStateStratagems", "CharacterStateExtract",
           "CharacterStateInteract", "CharacterStateInteractObjective", "")
SHOOT_WINDOW, MAX_ANGLE, MAX_DIST, CREDIT_SECS = 0.35, math.radians(30), 45.0, 3.0


def cost(t):
    if t in COST:
        v = COST[t]
    else:
        v = next((COST[k] for k in sorted(COST, key=len, reverse=True) if t and t.startswith(k)), 1.0)
    return min(v, P["cost_cap"])


class Life:
    def __init__(self, uid):
        self.id = uid
        self.local = False
        self.t0 = self.t_active = self.t1 = self.t_dead = None
        self.downs, self.ups = [], []
        self.samples = []           # (t, x, y, threat, idle)
        self.est_kills, self.x_kills = [], []   # (t, type, calm)
        self.hurt = []              # 挨敌人 / 环境打的时间
        self.hurt_by_mate = []      # 挨队友打的时间
        self.ff = []                # 本机打到队友的时间
        self.teamkills = []
        self.throws = []            # 扔战备的时间
        self.last_hurt = None       # (t, 来源是不是队友)
        self.killed_by_mate = None


def read(path, pause=None):
    """读一局：每条命的时间线 + 任务进度。一遍读完。pause：每读一批行调一次（HellBox 里录着下一局时让它停着等）。"""
    lives = {}
    EI = {"id": 0, "type": 1, "x": 2, "y": 3, "hp": 5, "dead": 7, "alert": 9}
    static = {}                     # 敌人编号 -> 种类（fmt 3 的 s.en）
    enemies = []                    # 最近一次的敌人行
    alert = {}
    enemy_hp, last_hit = {}, {}
    pose, last_shoot = {}, {}
    mission = None
    obj_times, extract_t, spawns = [], None, []
    end, first_gt = None, None
    next_sample = None
    n_bb_kills = n_x_enemy = 0

    def life(uid):
        L = lives.get(uid)
        if L is None:
            L = lives[uid] = Life(uid)
        return L

    def best_shooter(gt, x, y, loose=False):
        best, bs = None, None
        for uid, (px, py, fx, fy, alive) in pose.items():
            ls = last_shoot.get(uid)
            if not alive or ls is None or gt - ls > (1.0 if loose else SHOOT_WINDOW):
                continue
            dx, dy = x - px, y - py
            d = math.hypot(dx, dy)
            if d > MAX_DIST:
                continue
            fl = math.hypot(fx, fy)
            if d < 2.5:
                ang = 0.0
            elif fl < 1e-6:
                continue
            else:
                ang = math.acos(max(-1.0, min(1.0, (dx * fx + dy * fy) / (d * fl))))
            if ang > MAX_ANGLE * (1.5 if loose else 1.0):
                continue
            sc = ang + d / 200.0
            if bs is None or sc < bs:
                best, bs = uid, sc
        return best

    def etype(e):
        return static.get(e[EI["id"]]) if "type" not in EI else e[EI["type"]]

    for n_line, line in enumerate(gzip.open(path, "rt", encoding="utf-8")):
        if pause is not None and n_line % 2000 == 0:
            pause()
        d = json.loads(line)
        t = d.get("t")
        if t == "start":
            if d.get("fmt", 2) >= 3:
                cols = d["enemy_cols"]
                EI = {c: cols.index(c) for c in ("id", "x", "y", "hp", "dead", "alert")}
            continue
        if t == "end":
            end = d
            continue
        if t == "f":
            gt = d["gt"]
            first_gt = gt if first_gt is None else first_gt
            s = d.get("s") or {}
            for k, v in (s.get("en") or {}).items():
                static[int(k)] = v[0]
            m = s.get("mission")
            if m and len(m) > 8 and m[1]:
                if mission and m[7] > mission[7] >= 0:
                    obj_times.append(gt)
                if extract_t is None and m[2] == 1:
                    extract_t = gt
                mission = m
            seen = set()
            for p in d["p"]:
                uid = p["id"]
                seen.add(uid)
                L = life(uid)
                L.t0 = gt if L.t0 is None else L.t0
                alive = not p["dead"]
                st = p.get("st") or ""
                inp = p.get("in")
                if alive:
                    if p["pad"] >= 0:
                        L.local = True
                    if L.t_active is None and st not in ("CharacterStateCutscene", ""):
                        L.t_active = gt
                    L.t1 = gt
                shooting = ("Fire" in st) or bool(inp and (inp[0] or inp[6]))
                if shooting and alive:
                    last_shoot[uid] = gt
                if st == "CharacterStateStratagemsThrow" and (not L.throws or gt - L.throws[-1] > 2):
                    L.throws.append(gt)
                pose[uid] = (p["x"], p["y"], p.get("fx") or 0.0, p.get("fy") or 0.0, alive)
                p["_idle"] = alive and not p["dn"] and st not in PASSIVE and not (inp and any(inp)) and not p.get("btn")
            for uid in list(pose):
                if uid not in seen:
                    del pose[uid]
            if "e" in d:
                enemies = d["e"]
                for e in enemies:
                    eid, hp = e[EI["id"]], e[EI["hp"]]
                    alert[eid] = e[EI["alert"]]
                    old = enemy_hp.get(eid)
                    enemy_hp[eid] = hp
                    if old is not None and hp is not None and hp < old - 0.01:
                        who = best_shooter(gt, e[EI["x"]], e[EI["y"]])
                        if who is not None and (not e[EI["dead"]] or eid not in last_hit):
                            last_hit[eid] = (who, gt)
            if next_sample is None or gt >= next_sample:
                next_sample = gt + 1.0 / P["sample_hz"]
                alive_e = [e for e in enemies if not e[EI["dead"]]]
                for p in d["p"]:
                    L = lives[p["id"]]
                    if not L.local or p["dead"]:
                        continue
                    thr = 0.0
                    for e in alive_e:
                        dist = math.hypot(e[EI["x"]] - p["x"], e[EI["y"]] - p["y"])
                        if dist <= P["near"]:
                            thr += cost(etype(e))
                        elif dist <= P["mid"]:
                            thr += P["mid_coef"] * cost(etype(e))
                    L.samples.append((gt, p["x"], p["y"], thr, p["_idle"]))
            continue
        if t != "ev":
            continue
        k, gt = d.get("k"), d.get("gt")
        if k == "kill":
            n_bb_kills += 1
            eid = d.get("enemy")
            h = last_hit.get(eid)
            who = h[0] if h and gt - h[1] <= CREDIT_SECS and h[0] in lives else best_shooter(gt, d.get("x", 0), d.get("y", 0), True)
            if who is not None:
                lives[who].est_kills.append((gt, d.get("type"), not alert.get(eid, 0)))
        elif k == "kill_by":
            o, tg = d.get("owner"), d.get("target")
            if d.get("target_kind") == "enemy":
                n_x_enemy += 1
                if o in lives:
                    lives[o].x_kills.append((gt, d.get("target_type") or "?", not alert.get(tg, 0)))
            elif d.get("target_kind") == "player" and o in lives and o != tg:
                lives[o].teamkills.append(gt)
                if tg in lives:
                    lives[tg].killed_by_mate = True
        elif k == "melee_hit":
            a = d.get("attacker")
            if a in lives and d.get("target_kind") == "enemy":
                last_hit[d.get("target")] = (a, gt)
        elif k == "hurt":
            tg, o = d.get("target"), d.get("owner")
            if tg in lives:
                mate = o in lives and o != tg
                (lives[tg].hurt_by_mate if mate else lives[tg].hurt).append(gt)
                lives[tg].last_hurt = (gt, mate)
                if mate:
                    lives[o].ff.append(gt)
        elif k == "downed" and d.get("who") in lives:
            lives[d["who"]].downs.append(gt)
        elif k == "up" and d.get("who") in lives:
            lives[d["who"]].ups.append(gt)
        elif k == "dead" and d.get("who") in lives:
            L = lives[d["who"]]
            L.t_dead = gt
            L.t1 = gt
        elif k == "spawn":
            spawns.append((gt, d.get("who")))
    exact = n_x_enemy >= max(5, 0.3 * n_bb_kills)
    for L in lives.values():
        L.kills = L.x_kills if exact else L.est_kills
    g = (end or {}).get("game") or {}
    if mission:
        g.setdefault("objectives", [mission[7], mission[6], mission[8]])
    return {"file": os.path.abspath(path), "lives": lives, "obj_times": obj_times, "extract_t": extract_t,
            "spawns": spawns, "exact": exact, "game": g, "lost_frames": (end or {}).get("lost_frames") or 0,
            "frames": (end or {}).get("frames") or 1, "first_gt": first_gt}


def pulses(ts, gap):
    out = []
    for t in sorted(ts):
        if not out or t - out[-1] > gap:
            out.append(t)
    return out


def count_in(ts, a, b):
    return bisect.bisect_right(ts, b) - bisect.bisect_left(ts, a)


def score_game(G):
    """一局 → 每条本机命的连续段、窗口、权重（名次和最终权重要等所有录像一起算）。"""
    g = G["game"]
    done, total, failed = [v or 0 for v in (g.get("objectives") or [0, 0, 0])]
    m_match = min(P["match_hi"], max(P["match_lo"], P["match_lo"] + 0.35 * done / max(1, total)
                  + 0.15 * (g.get("result") in ("completed", "extracted")) + 0.10 * (g.get("result") == "extracted")
                  - 0.05 * failed))
    others = [L for L in G["lives"].values() if not L.local]
    spawn_ts = sorted(t for t, who in G["spawns"] if who in G["lives"] and not G["lives"][who].local
                      and G["first_gt"] is not None and t - G["first_gt"] > 30)
    obj_ts = sorted(G["obj_times"])
    spans, tails, rejected = [], [], []
    for L in G["lives"].values():
        if not L.local or L.t_active is None or L.t1 is None:
            continue
        hurt = pulses(L.hurt, P["pulse"])
        ff = pulses(L.ff, P["pulse"])
        kills = sorted(L.kills)
        kill_t = [k[0] for k in kills]
        # 死前：从让这次死掉的第一次倒地算（倒地后没起来）；被队友打死只去最后 1.5 秒、不进反面
        t_end, death = L.t1, None
        if L.t_dead is not None:
            t_fatal = L.t_dead
            for td in sorted(L.downs, reverse=True):
                if L.t_dead - td > P["fatal_lookback"]:
                    break
                if not any(td < tu < L.t_dead for tu in L.ups):
                    t_fatal = td
            # 被队友打死：游戏记的凶手是队友，或者致命前 3 秒内挨过队友打（实测有"队友连打几下、最后一下是怪"的）
            mate = L.killed_by_mate or any(t_fatal - 3.0 <= h <= t_fatal for h in L.hurt_by_mate)
            death = "teammate" if mate else "self_or_enemy"
            if mate:
                t_end = t_fatal - P["tail_mate"]
            else:
                t_end = t_fatal - P["tail_self"]
                tails.append({"life": L.id, "t0": max(L.t_active, t_end), "t1": L.t_dead})
        # 挂机：>= 20 秒拆开，5～20 秒不学
        idle_runs, run = [], None
        for (t, x, y, thr, idle) in L.samples:
            if L.t_active <= t <= t_end and idle:
                run = [t, t] if run is None else [run[0], t]
            elif run:
                idle_runs.append(run)
                run = None
        if run:
            idle_runs.append(run)
        cuts = [r for r in idle_runs if r[1] - r[0] >= P["idle_split"]]
        pieces, a = [], L.t_active
        for r in cuts:
            pieces.append((a, r[0]))
            a = r[1]
        pieces.append((a, t_end))
        for (t0, t1) in pieces:
            secs = t1 - t0
            if secs < P["min_span"]:
                rejected.append({"life": L.id, "t0": t0, "t1": t1, "why": "too_short"})
                continue
            mins = secs / 60
            tk = count_in(sorted(L.teamkills), t0, t1)
            nff = count_in(ff, t0, t1)
            if (tk >= 2 and tk / mins >= 0.4) or nff / mins >= 8.0:
                rejected.append({"life": L.id, "t0": t0, "t1": t1, "why": "heavy_ff"})
                continue
            samp = [s for s in L.samples if t0 <= s[0] <= t1]
            samp_t = [s[0] for s in samp]
            wins = []
            w0 = t0
            while w0 < t1 - 1e-6:
                w1 = min(w0 + P["win"], t1)
                i0, i1 = bisect.bisect_left(samp_t, w0), bisect.bisect_right(samp_t, w1)
                ws = samp[i0:i1]
                thr = sum(s[3] for s in ws) / len(ws) if ws else 0.0
                disp = math.hypot(ws[-1][1] - ws[0][1], ws[-1][2] - ws[0][2]) if len(ws) > 1 else 0.0
                idle_any = any(s[4] for s in ws)
                k0, k1 = bisect.bisect_left(kill_t, w0), bisect.bisect_right(kill_t, w1)
                kw = kills[k0:k1]
                kill_score = sum(cost(k[1]) for k in kw) + P["calm_kill_bonus"] * sum(1 for k in kw if k[2])
                n_hurt = count_in(hurt, w0, w1)
                n_down = sum(1 for td in L.downs if w0 <= td <= w1 and not (L.hurt_by_mate and any(abs(td - h) < 3 for h in L.hurt_by_mate)))
                n_ff = count_in(ff, w0, w1)
                n_tk = count_in(sorted(L.teamkills), w0, w1)
                n_obj = count_in(obj_ts, w0, w1)
                n_reinf = sum(1 for th in L.throws if w0 <= th <= w1 and count_in(spawn_ts, th, th + P["reinforce_secs"]))
                ext = G["extract_t"] is not None and w1 >= G["extract_t"]
                near_obj = any(w0 <= to <= w1 + P["obj_lead"] for to in obj_ts)
                if ext:
                    phase = "extraction"
                elif near_obj or n_reinf:
                    phase = "objective"
                elif thr >= P["phase_high"]:
                    phase = "combat_high"
                elif thr >= P["phase_low"]:
                    phase = "combat_low"
                else:
                    phase = "transit"
                pressure = min(P["pressure_cap"], P["pressure_coef"] * thr) if (n_hurt == 0 and n_down == 0) else 0.0
                transit = P["transit_bonus"] if (phase == "transit" and disp >= P["transit_disp"] and not n_ff and not idle_any) else 0.0
                support = P["obj_bonus"] * n_obj + P["reinforce_bonus"] * n_reinf
                pen = P["pen_hurt"] * n_hurt + P["pen_down"] * n_down + P["pen_ff"] * n_ff + P["pen_teamkill"] * n_tk
                raw = kill_score + pressure + transit + support - pen
                wins.append({"t0": round(w0, 2), "t1": round(w1, 2), "phase": phase, "raw": round(raw, 2),
                             "threat": round(thr, 2), "disp": round(disp, 1), "kills": len(kw),
                             "clean_transit": bool(transit)})
                w0 += P["step"]
            masks = []
            for td in L.downs:
                if t0 <= td <= t1:
                    up = next((tu for tu in sorted(L.ups) if tu > td), td + 5)
                    by_mate = any(abs(td - h) < 3 for h in L.hurt_by_mate)
                    masks.append({"t0": round(td if by_mate else td - P["mask_down_lead"], 2), "t1": round(up, 2),
                                  "why": "ff_downed_crawl" if by_mate else "self_downed"})
            for tf in ff:
                if t0 <= tf <= t1:
                    masks.append({"t0": round(tf - P["mask_ff_lead"], 2), "t1": round(tf + P["mask_ff_tail"], 2),
                                  "why": "friendly_fire"})
            for r in idle_runs:
                if t0 <= r[0] and r[1] <= t1 and P["idle_mask"] <= r[1] - r[0] < P["idle_split"]:
                    masks.append({"t0": round(r[0], 2), "t1": round(r[1], 2), "why": "idle"})
            mean_raw = sum(w["raw"] for w in wins) / len(wins) if wins else 0.0
            # 命级撤离加分先不加：录像里认不准（用户说没撤离的局，角色也进过 Extract 状态）；撤离靠整局系数和撤离阶段
            s_life = mean_raw * min(1.0, secs / 60) + 2.0 * sum(1 for w in wins if w["phase"] == "objective") / max(1, len(wins)) \
                - 8.0 * len([t for t in L.teamkills if t0 <= t <= t1])
            spans.append({"life": L.id, "t0": round(t0, 2), "t1": round(t1, 2), "secs": round(secs, 1), "death": death,
                          "s_life": round(s_life, 3), "kills": count_in(kill_t, t0, t1),
                          "points": round(sum(cost(k[1]) for k in kills if t0 <= k[0] <= t1), 1),
                          "hurt": count_in(hurt, t0, t1), "downs": sum(1 for td in L.downs if t0 <= td <= t1),
                          "ff": count_in(ff, t0, t1), "teamkills": count_in(sorted(L.teamkills), t0, t1),
                          "windows": wins, "masks": masks})
    return {"file": G["file"], "faction": g.get("enemy"), "difficulty": g.get("difficulty"),
            "players": g.get("players"), "objectives": [done, total, failed], "result": g.get("result"),
            "kill_credit": "exact" if G["exact"] else "estimated", "match_mult": round(m_match, 3),
            "lost_frac": round(G["lost_frames"] / max(1, G["frames"]), 4), "spans": spans,
            "negative_tails": tails, "rejected": rejected, "obj_times": obj_ts}


def pct(vals, v):
    if not vals:
        return 0.5
    return (bisect.bisect_left(vals, v) + bisect.bisect_right(vals, v)) / (2 * len(vals))


def finish(games):
    """所有录像一起：组内名次 → 每个窗口的权重。组 = (阵营, 难度档, 单人 / 多人, 击杀准不准)；组太小就并成一组。"""
    def group(gm):
        d = gm["difficulty"] or 0
        return (gm["faction"], 0 if d <= 6 else 1 if d <= 11 else 2, (gm["players"] or 1) > 1, gm["kill_credit"])
    by = collections.defaultdict(list)
    for gm in games:
        for sp in gm["spans"]:
            by[group(gm)].append((gm, sp))
    if any(len(v) < 15 for v in by.values()):
        by = {"all": [x for v in by.values() for x in v]}
    total_h = sum(sp["secs"] for gm in games for sp in gm["spans"]) / 3600
    for members in by.values():
        lifev = sorted(sp["s_life"] for _, sp in members)
        phasev = collections.defaultdict(list)
        for _, sp in members:
            for w in sp["windows"]:
                phasev[w["phase"]].append(w["raw"])
        for v in phasev.values():
            v.sort()
        for gm, sp in members:
            sp["pct_life"] = round(pct(lifev, sp["s_life"]), 3)
            sp["dropped"] = (total_h >= P["drop_after_hours"] and sp["pct_life"] < P["drop_frac"]
                             and not any(w["phase"] in ("objective", "extraction") for w in sp["windows"]))
            for w in sp["windows"]:
                w["pct"] = round(pct(phasev[w["phase"]], w["raw"]), 3)
                x = gm["match_mult"] * (0.5 + 0.8 * sp["pct_life"]) * (0.6 + 0.8 * w["pct"])
                if w["phase"] in ("objective", "extraction"):
                    x *= P["w_obj"]
                if w["clean_transit"]:
                    x = max(x, P["w_transit_floor"])
                w["weight"] = round(min(P["w_hi"], max(P["w_lo"], x)), 3)
            ws = [w["weight"] for w in sp["windows"]]
            sp["mean_weight"] = round(sum(ws) / len(ws), 3) if ws else 0
            sp["masked_secs"] = round(sum(m["t1"] - m["t0"] for m in sp["masks"]), 1)
    return total_h


def summary(gm):
    """给列表看的：这局本机活着多少分钟、其中"好教材"（权重 >= 1）多少分钟。每个窗口代表它开头的一个步长。"""
    total = good = 0.0
    for sp in gm["spans"]:
        if sp.get("dropped"):
            continue
        for w in sp["windows"]:
            span = min(P["step"], w["t1"] - w["t0"])
            total += span
            if w.get("weight", 0) >= 1.0:
                good += span
    return {"good_min": round(good / 60, 1), "total_min": round(total / 60, 1), "spans": len(gm["spans"]),
            "kill_credit": gm.get("kill_credit")}


def score_name(rec_path):
    return os.path.basename(rec_path).replace(".jsonl.gz", "") + ".score.json"


def _write(gm, out_dir):
    gm["params"] = P
    gm["summary"] = summary(gm)
    dst = os.path.join(out_dir, score_name(gm["file"]))
    with open(dst + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(gm, fh, ensure_ascii=False)
    os.replace(dst + ".tmp", dst)


def score_into(rec_path, out_dir, pause=None):
    """HellBox 录制器用：算一局，写 <名字>.score.json；再把文件夹里所有评分一起重排名次、重算权重。返回这局的 summary。"""
    gm = score_game(read(rec_path, pause))
    games = [gm]
    for f in os.listdir(out_dir):
        if f.endswith(".score.json") and f != score_name(rec_path):
            try:
                with open(os.path.join(out_dir, f), encoding="utf-8") as fh:
                    old = json.load(fh)
            except (OSError, ValueError):
                continue
            if "spans" in old and old.get("file") and os.path.exists(old["file"]):   # 出错的、录像删了的不算
                games.append(old)
    finish(games)
    for g in games:
        _write(g, out_dir)
    return gm["summary"]


def load_summary(out_dir, rec_file):
    try:
        with open(os.path.join(out_dir, score_name(rec_file)), encoding="utf-8") as fh:
            return json.load(fh).get("summary")
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    games = []
    for f in a.files:
        games.append(score_game(read(f)))
        print("读完", os.path.basename(f), flush=True)
    total_h = finish(games)
    for gm in games:
        _write(gm, a.out or os.path.dirname(gm["file"]))
    rows = [(gm, sp) for gm in games for sp in gm["spans"]]
    rows.sort(key=lambda r: -r[1]["s_life"])
    print(f"\n本机有效段 {len(rows)} 条，共 {total_h * 60:.0f} 分钟")
    for gm, sp in rows:
        ph = collections.Counter(w["phase"] for w in sp["windows"])
        n = max(1, sum(ph.values()))
        print(f"{os.path.basename(gm['file'])[13:19]} 命{sp['life']:>6} {sp['secs'] / 60:4.1f}分 名次{sp['pct_life']:.2f} "
              f"分{sp['s_life']:6.2f} 杀{sp['kills']:4d} 挨打{sp['hurt']:3d} 倒地{sp['downs']} 误伤{sp['ff']} "
              f"权重{sp['mean_weight']:.2f} 不学{sp['masked_secs']:.0f}秒 结束:{sp['death'] or '活着'} "
              f"高压{ph['combat_high'] / n:.0%} 交战{ph['combat_low'] / n:.0%} 转场{ph['transit'] / n:.0%} "
              f"目标{ph['objective'] / n:.0%} 撤离{ph['extraction'] / n:.0%}")


if __name__ == "__main__":
    main()
