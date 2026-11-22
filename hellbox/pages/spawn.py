"""出怪：报复关 / 警报 / 巡逻三条来源，同一种改法（mod/src/spawn_rules.lua，2026-11-11 合成一页）。

游戏里三条来源都是"从一份按难度划分的菜单里随机挑"：
  - 报复关：每一波按预算从「套餐」菜单里随机抽几个（GenocideGroupSettings 的捆）；
  - 警报：拉响时按预算从「套餐」菜单里抽（进关时按难度分易 / 中 / 难三档；EnemyGroupSettings 的捆）；
  - 巡逻：从「巡逻清单」里随机挑一条，一条就是一捆（也是 EnemyGroupSettings）。
每个标签同一种布局：选族 + 选难度逻辑 → 列出菜单里每个套餐一共几只 → 点一捆改怪和数量；
模式 原版 / 自己改 / 倍数 / 不出；每条来源自己的同时在场上限。警报和巡逻共用的捆，mod 那边各改各的。
载具 / 首领放兵单独一块（v / uv）。游戏开着就能改（不用进关），进到对应关卡生效；得你是房主。
数据：ai/spawn_tables.json（genocide / encounter / patrol / patrol_cap）。
"""
import copy
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout

import paths
import ui
from pages.edit_util import ParamList, PickGrid, small_button
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

AI = os.path.join(paths.ROOT, "ai")
TABLES = os.path.join(AI, "spawn_tables.json")
ENEMY_SETTINGS = os.path.join(AI, "enemy_settings.json")
POLL_MS = 1500
VC = Qt.AlignmentFlag.AlignVCenter
MAX_DIFF = 15
CAP_MAX = 64

SRCS = [("g", "报复关"), ("a", "警报"), ("p", "巡逻")]
SRC_ZH = dict(SRCS)
RACE_ZH = {"bugs": "虫族", "cyborgs": "生化人", "illuminates": "光能者"}
MISSION_ZH = {"genocide": "报复关", "mission": "普通任务", "provinggrounds": "试炼场",
              "provinggrounds_genocide_map": "试炼场·报复图"}
MODES = [("vanilla", "原版"), ("custom", "自己改"), ("mult", "倍数"), ("none", "不出")]
VEH_MODES = [("vanilla", "原版"), ("only", "只出选中"), ("none", "不出")]
# 原版上限（源码）：报复关 GameSettings.MAX_NUM_ALLOWED_ENEMIES = 16；
# 警报 EncounterSettings.max_num_units（三族都是 N1~4 = 6/8/10/12，之后 12，且不超过 16）；
# 巡逻 PatrolSettings.max_num_units（spawn_tables.json 的 patrol_cap）。
GLOBAL_CAP = 16
ALARM_CAP = {"default": 12, "per_difficulty": [6, 8, 10, 12]}
# 出生时散开（2026-11-16）：spawn_rules.lua spread=0～3
SPREADS = [(0, "原版"), (1, "小"), (2, "中"), (3, "大")]
# 场上上限（2026-11-18 V0.96 用户定）：16 原版～300 固定，最右边隔开的 -1 =「破限」（自动，最多 1000）。三个阵营一起。
CAP_VALUES = tuple(range(16, 301, 4)) + (-1,)


def cap_label(v):
    v = int(v)
    return "破限 ⚠" if v < 0 else ("16（原版）" if v == 16 else T("{0} 只", v))

# 每条来源的命令键：模式、倍数、难度逻辑、改过的捆、上限
KEYS = {"g": ("g", "multg", "glogic", "gmap", "gcap"),
        "a": ("a", "mult", "alogic", "amap", "acap"),
        "p": ("p", "multp", "plogic", "pmap", "pcap")}
INTRO = {
    "g": "报复关每一波按预算从「套餐」菜单里随机抽几个（越往后抽得越多），每个套餐由几「捆」怪组成。",
    "a": "拉响警报时按预算从「套餐」菜单里随机抽几个（离目标越近预算越多），每个套餐由几「捆」怪组成。",
    "p": "巡逻队从「巡逻清单」里随机挑一条放出来，一条就是一捆怪；场上巡逻的总只数有上限。",
}
CAP_NOTE = {
    "g": "报复关场上同时最多几只。一个套餐比上限还大时会自动拆成几小包陆续降（不会再卡波）。",
    "a": "警报的怪同时最多几只。一个套餐比上限还大时会自动拆成几小包陆续来（原版是整次警报作废）。",
    "p": "场上巡逻的怪一共最多几只。一捆比上限还大就永远刷不出来（巡逻没法拆），要么调高上限、要么少放点。",
}


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _num(text, default=0):
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def parse_group_text(text):
    """游戏状态里的 组名=怪*只+...,组名=... -> {组名: {路径: 只数}}

    旧版 mod 在一组里用逗号连怪（组名=a*2,b*1,下一组=...），没有等号的那段算上一组的，免得读回丢怪。"""
    out = {}
    key = None
    for item in (text or "").split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            key, _, body = item.partition("=")
            key = key.strip()
            comp = out.setdefault(key, {})
        elif key is not None:
            body = item
            comp = out[key]
        else:
            continue
        for part in body.split("+"):
            part = part.strip()
            if not part:
                continue
            p, _, n = part.rpartition("*")
            if not p:
                p, n = part, "1"
            count = _num(n, -1)
            if count < 0:
                continue
            p = p.strip()
            if not p.startswith("characters/"):
                p = "characters/" + p
            if count >= 1:
                comp[p] = count
    return out


def parse_units_text(text):
    """游戏状态里的 路径*只,... -> {路径: 只数}"""
    out = {}
    for item in (text or "").split(","):
        item = item.strip()
        if not item:
            continue
        p, _, n = item.rpartition("*")
        if not p:
            p, n = item, "1"
        count = _num(n, -1)
        if count < 1:
            continue
        p = p.strip()
        if not p.startswith("characters/"):
            p = "characters/" + p
        out[p] = count
    return out


class SpawnEditor:
    """出怪逻辑块的编辑器（2026-11-14 V0.91：原「出怪设置」页改成数据修改页里的编辑卡片）。
    卡片直接加在页面的 view 里（self.rows），一块里三个阵营各存一份；load(块数据) / dump() 读写。"""

    # ================================================================ 数据
    def _load_data(self):
        self.tables = load_json(TABLES, {"races": {}})
        self.enemy_settings = load_json(ENEMY_SETTINGS, {"races": {}})
        self.names = {}  # 路径 -> 中文
        self.menus = {s: {} for s, _ in SRCS}  # 来源 -> 族 -> [套餐]
        self.bundles = {"g": {}, "a": {}, "p": {}}  # 来源 -> 捆名 -> {路径: 只数}（原版）
        self.pcap_table = {}
        for race, r in (self.tables.get("races") or {}).items():
            for key in ("genocide", "encounter", "patrol"):
                for w in r.get(key) or []:
                    for u in w.get("units") or []:
                        if len(u) > 2:
                            self.names[u[0]] = u[2]
            self.pcap_table[race] = r.get("patrol_cap") or {}
            for src, key in (("g", "genocide"), ("a", "encounter")):
                pkgs = []
                for w in r.get(key) or []:
                    groups = []
                    for g in w.get("groups") or []:
                        k = g.get("group")
                        if not k:
                            continue
                        groups.append(k)
                        self.bundles[src].setdefault(k, {u[0]: int(u[1]) for u in g.get("units") or []})
                    pkgs.append({"name": w.get("name") or "?", "min": w.get("min"), "max": w.get("max"),
                                 "cost": w.get("cost"), "groups": groups})
                self.menus[src][race] = pkgs
            pkgs = []
            for w in r.get("patrol") or []:
                k = w.get("group")
                if not k:
                    continue
                self.bundles["p"].setdefault(k, {u[0]: int(u[1]) for u in w.get("units") or []})
                pkgs.append({"name": k, "min": w.get("min"), "max": w.get("max"), "cost": None, "groups": [k]})
            self.menus["p"][race] = pkgs
        # 警报和巡逻在游戏里是同一张捆表：两边原版内容互相补齐
        for k, v in self.bundles["a"].items():
            self.bundles["p"].setdefault(k, v)
        for k, v in self.bundles["p"].items():
            self.bundles["a"].setdefault(k, v)
        self.pkg_label = {}  # 套餐名 -> 短中文名（记录里用）
        for src, _ in SRCS:
            for pkgs in self.menus[src].values():
                for w in pkgs:
                    comp = self._sum_groups(src, w["groups"], vanilla=True)
                    if comp and w["name"] not in self.pkg_label:
                        first = next(iter(comp))
                        self.pkg_label[w["name"]] = self._zh(first) + (tr("等") if len(comp) > 1 else "")

    def _zh(self, path):
        return tr(self.names.get(path, path.rsplit("/", 1)[-1]))

    def _fmt(self, comp):
        return tr("、").join(f"{self._zh(p)}×{n}" for p, n in comp.items()) or tr("（不出）")

    def _waves_for(self, src, diff):
        return [w for w in self.menus[src].get(self.race) or []
                if (w.get("min") or 0) <= diff <= (w.get("max") if w.get("max") is not None else 99)]

    def _groups_for(self, src, diff):
        out = []
        for w in self._waves_for(src, diff):
            for k in w["groups"]:
                if k not in out:
                    out.append(k)
        return out

    def _vanilla(self, src, key):
        return dict(self.bundles[src].get(key) or {})

    def _comp(self, src, key):
        s = self.state[src]
        if key in s["map"]:
            return s["map"][key]
        return self._vanilla(src, key)

    def _sum_groups(self, src, groups, vanilla=False):
        """一个套餐（几捆）现在实际出什么：按当前模式算。"""
        s = self.state[src] if not vanilla else None
        comp = {}
        if s and s["mode"] == "none":
            return comp
        for k in groups:
            part = self._comp(src, k) if s and s["mode"] == "custom" else self._vanilla(src, k)
            for p, n in part.items():
                n = int(n)
                if s and s["mode"] == "mult":
                    n = max(1, int(n * s["mult"] + 0.5))
                comp[p] = comp.get(p, 0) + n
        return comp

    def _group_label(self, src, key):
        comp = self._vanilla(src, key)
        if not comp:
            return key
        first = self._zh(next(iter(comp)))
        total = sum(comp.values())
        if len(comp) == 1:
            return f"{first}×{total}"
        return T('{0} 等 {1} 种 ×{2}', first, len(comp), total)

    def _vanilla_cap(self, src):
        """这条来源的原版上限：游戏里读到的优先，没有就按表算（用这张图的难度）。"""
        st = self.st or {}
        diff = self.map_diff or self.state[src]["diff"] or 1
        if src == "g":
            return _num(st.get("glimit"), 0) or GLOBAL_CAP
        if src == "a":
            live = _num(st.get("alimit"), 0)
            if live:
                return min(live, GLOBAL_CAP)
            per = ALARM_CAP["per_difficulty"]
            return min(per[diff - 1] if 1 <= diff <= len(per) else ALARM_CAP["default"], GLOBAL_CAP)
        live = _num(st.get("plimit"), 0)
        if live:
            return live
        t = self.pcap_table.get(self.race) or {}
        per = t.get("per_difficulty") or []
        return per[diff - 1] if 1 <= diff <= len(per) else (t.get("default") or 9)

    def _cap(self, src):
        return self.state[src]["cap"] or self._vanilla_cap(src)

    def _unit_choices(self):
        try:
            import drill_spec as ds
            ok, removed = ds.pickable(self.race)
        except Exception:  # noqa: BLE001
            return [], 0
        return [("characters/" + m["path"], ds.label(m), m) for m in ok], removed

    def _vehicle_units(self):
        data = (self.enemy_settings.get("races") or {}).get(self.race) or {}
        out = []
        for u in data.get("units") or []:
            info = (u.get("settings") or {}).get("enemy_info") or {}
            path = info.get("spawn_unit_path")
            if not isinstance(path, str) or not path:
                continue
            veh = self.names.get("characters/" + str(u.get("path", "")), u.get("name", "载具"))
            out.append({"vehicle": veh, "path": path, "amount": int(info.get("spawn_amount") or 1),
                        "unit": self.names.get(path, path.rsplit("/", 1)[-1])})
        return out

    def _vehicle_defaults(self):
        return {v["path"]: max(1, v["amount"]) for v in self._vehicle_units()}

    # ================================================================ 界面
    def __init__(self, app, view):
        self.app, self.view = app, view
        self.build()

    def build(self):
        self._load_data()
        self.st = {}
        self.live = True  # 编辑块：随时能改（不用游戏开着）
        self.sending = False
        self.map_diff = None
        self.mission = ""
        self.race = "bugs"
        self.src = "g"
        self.per_race = {}
        self.spread = 0
        self.limit = 16
        self._blank_race()
        self.veh_controls = []
        self.controls = []
        self.dirty = False

        # 2026-11-15 新界面（UI 交给 Claude）：三张卡——改哪条来源 / 这条来源怎么出（方式、上限、难度、改哪一捆、菜单
        # 都在一张里）/ 载具放兵。长说明都挪进底栏（鼠标停在那一行上看）。
        seg = dict(padx=12, pady=3, shadow=2, font=ui.f_zh(10, True))

        # ---- 改哪条来源
        src = ui.Card(self.view, "SRC", "改哪条来源", fill=ui.YELLOW, note="一块里三个阵营各存一份")
        self.v_src = ui.Var(self.src)
        self.seg_src = ui.Segmented(None, SRCS, self.v_src, command=self._src_changed, **seg)
        self.row_src = src.row("来源", self.seg_src, help="")
        self.v_race = ui.Var(self.race)
        self.seg_race = ui.Segmented(None, [(k, z) for k, z in RACE_ZH.items()], self.v_race,
                                     command=self._race_changed, **seg)
        src.row("阵营", self.seg_race, help="一块里三个阵营各存一份：进哪个阵营的地图就用哪一份。")
        self.v_spread = ui.Var(self.spread)
        self.seg_spread = ui.Segmented(None, SPREADS, self.v_spread, command=self._spread_changed, **seg)
        src.row("出生时散开", self.seg_spread,
                help="一捆怪刷出来时站得多开（三条来源、载具放兵都管，三个阵营一起）。原版挤在中心几米内、几捆叠在一起；"
                     "小 / 中 / 大 越来越开。")
        self.v_limit = ui.Var(self.limit)
        self.sl_limit = ui.StepSlider(None, [(v, cap_label(v)) for v in CAP_VALUES], self.v_limit,
                                      command=self._limit_changed, width=260, text_width=92, tail=True)
        src.row("场上上限", self.sl_limit,
                help="场上同时最多几只敌人（活的和没消失的尸体一起算，三个阵营一起）。16 是游戏原版。往右拖 = 固定这么多："
                     "改过的来源按这个数整包下，比它大的拆成几包陆续来。最右边隔开的红格「破限」= 按每一波自动放开，"
                     "最多 1000 只，几百只可能会卡。")
        self.src_hint = src.add(ui.text(src.body, "", muted=True, size=9), top=8)

        # ---- 这条来源怎么出
        main = ui.Card(self.view, "MODE", "", fill=ui.SALMON)
        self.main = main
        self.v_mode = ui.Var("vanilla")
        self.seg_mode = ui.Segmented(None, MODES, self.v_mode, command=self._mode_changed, **seg)
        self.btn_src_reset = small_button("这一条全部还原", self._reset_src)
        main.head_lay.addWidget(self.btn_src_reset, 0, VC)
        main.row("方式", self.seg_mode, name_w=90,
                 help="原版 = 照游戏；自己改 = 逐捆换怪和数量；倍数 = 种类照原版、数量翻倍；不出 = 这条来源一只都不出。")
        self.v_cap = ui.Var("16")
        self.cap_step = ui.Stepper(None, self.v_cap, 1, CAP_MAX, command=self._cap_changed)
        self.cap_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self.row_cap = main.row("场上上限", self.cap_note, 10, self.cap_step, name_w=90, help="")
        self.row_cap.hide()  # 2026-11-16 用户定：上限不手填，游戏那边自动（一波 / 一次警报整包下完）
        self.v_diff = ui.Var("12")
        self.diff_step = ui.Stepper(None, self.v_diff, 1, MAX_DIFF, width=3,
                                    command=lambda: self._diff_changed(int(self.diff_step.value())))
        self.diff_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self.row_diff = main.row("看哪套难度", self.diff_note, 10, self.diff_step, name_w=90, help="")
        self.panel_box, self.panel_lay = ui.vbox(spacing=6)
        main.add(self.panel_box, top=4)
        self.menu_box, self.menu_lay = ui.vbox(spacing=0)
        main.add(self.menu_box, top=4)

        # ---- 载具 / 首领放兵
        veh = ui.Card(self.view, "VEH", "载具 / 首领放兵", fill=ui.SKY, note="和上面三条来源互不影响")
        self.v_veh = ui.Var(self.veh_mode)
        self.seg_veh = ui.Segmented(None, VEH_MODES, self.v_veh, command=self._veh_changed, **seg)
        self.row_veh = veh.row("方式", self.seg_veh, name_w=90,
                               help="步兵战车屁股放出来的兵、首领召唤的兵单独算一块：原版是固定放某种怪，这里可以换成你勾的。")
        self.v_veh_count = ui.Var("3")
        self.veh_orig = 3
        self.veh_step = ui.Stepper(None, self.v_veh_count, 1, 50, width=3, command=self._set_veh_count)
        self.veh_count_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self.btn_veh_count = small_button("原版", self._reset_veh_count)
        self.row_veh_count = veh.row("每次放几只", self.veh_count_note, 10, self.btn_veh_count, 8, self.veh_step, name_w=90,
                                     help="步兵战车开门一次放几只兵（原版 3 只）。和怪物属性里载具的「召唤数量」都设了时以这里为准。"
                                          "场上上限满了还是放不出来，要放很多就把「场上上限」拉大。")
        self.veh_box, self.veh_lay = ui.vbox(spacing=6)
        veh.add(self.veh_box, top=6)
        self.veh_hint = veh.add(ui.text(veh.body, "", muted=True, size=9), top=8)

        self.rows = [self.view.row(src), self.view.row(main), self.view.row(veh)]

        self._refresh_src()
        self._rebuild_veh()

    # ================================================================ 块的读写（数据修改页用）
    def _blank_race(self):
        self.state = {s: {"diff": 12 if s == "g" else 5, "mode": "vanilla", "map": {}, "group": None,
                          "mult": 2, "cap": 0} for s, _ in SRCS}
        self.veh_mode = "vanilla"
        self.veh_sel = {}
        self.veh_qty = {}
        self.veh_count = 0  # 2026-11-18 V0.96：步兵战车每次放几只，0 = 原版

    def _stash(self):
        self.per_race[self.race] = {
            "src": {k: {kk: copy.deepcopy(vv) for kk, vv in v.items() if kk != "group"} for k, v in self.state.items()},
            "veh": {"mode": self.veh_mode, "sel": dict(self.veh_sel), "qty": dict(self.veh_qty),
                    "count": self.veh_count},
            "spread": self.spread}

    def _unstash(self, race):
        self._blank_race()
        d = self.per_race.get(race) or {}
        for k, v in (d.get("src") or {}).items():
            if k in self.state and isinstance(v, dict):
                self.state[k].update({kk: copy.deepcopy(vv) for kk, vv in v.items()
                                      if kk in ("diff", "mode", "map", "mult", "cap")})
        veh = d.get("veh") or {}
        if veh.get("mode") in ("vanilla", "only", "none"):
            self.veh_mode = veh["mode"]
        self.veh_sel = dict(veh.get("sel") or {})
        self.veh_qty = dict(veh.get("qty") or self.veh_sel)
        self.veh_count = max(0, min(50, int(veh.get("count") or 0)))

    def load(self, data, race=None):
        """data = {阵营: {"src": {...}, "veh": {...}}}（块里存的）；None = 全原版。"""
        self.per_race = copy.deepcopy(data or {})
        self.spread = max([int((v or {}).get("spread") or 0) for v in self.per_race.values()
                           if isinstance(v, dict)] or [0])
        self.v_spread.set(self.spread)
        caps = [int((v or {}).get("cap") or 0) for v in self.per_race.values() if isinstance(v, dict)]
        caps = [c for c in caps if c < 0 or c > 16]
        self.limit = caps[0] if caps and caps[0] in CAP_VALUES else 16
        self.v_limit.set(self.limit)
        self.sl_limit.changed = self.limit != 16
        if race in RACE_ZH:
            self.race = race
        self.v_race.set(self.race)
        self._unstash(self.race)
        self.v_veh.set(self.veh_mode)
        self.dirty = False
        self._refresh_src()
        self._rebuild_veh()

    def dump(self):
        self._stash()
        cap = 0 if self.limit == 16 else self.limit
        for r in RACE_ZH:  # 散开、上限三个阵营一起：没点开过的阵营也带上
            if self.spread or cap or r in self.per_race:
                d = self.per_race.setdefault(r, {})
                d["spread"] = self.spread
                d["cap"] = cap
        return copy.deepcopy(self.per_race)

    def _spread_changed(self, _v=None):
        self.spread = int(self.v_spread.get() or 0)
        self._mark_pending()

    def _limit_changed(self, _v=None):
        self.limit = int(self.v_limit.get() or 16)
        self.sl_limit.changed = self.limit != 16
        self.sl_limit.update()
        self._mark_pending()

    def set_visible(self, on):
        for r in self.rows:
            r.setVisible(on)


    def _refresh_src(self):
        """切到某条来源：难度下拉、套餐列表、上限、模式面板、记录全按这条来源重画。"""
        src, s = self.src, self.state[self.src]
        self.main.title_lab.config(text=T("{0}怎么出", tr(SRC_ZH[src])))
        self.row_src.set_help(INTRO[src])
        self.row_diff.set_help(tr(INTRO[src]) + " " + tr("选一套难度，下面列出这套菜单（「自己改」/「倍数」时显示改完的只数）。"))
        self.row_cap.set_help(tr(CAP_NOTE[src]) + " " + tr("活怪和没消失的尸体一起算，超过 64 可能卡死或崩溃。"
                                                          "开了分屏的刷怪扩展时，每个玩家各算一份（测试中）。"))
        d = max(1, min(MAX_DIFF, s["diff"] or 1))
        self.v_diff.set(str(d))
        self.diff_note.config(text=T('N{0} 的{1}逻辑', d, tr(SRC_ZH[src])))
        self.v_mode.set(s["mode"])
        self._sync_cap()
        self._src_hint()
        self._refresh_menu()
        self._build_panel()
        self._apply_live()

    def _src_hint(self):
        edited = [T('{0}改过 {1} 捆', tr(z), len(self.state[k]['map'])) for k, z in SRCS if self.state[k]["map"]]
        modes = [T('{0}：{1}', tr(z), tr(dict(MODES)[self.state[k]["mode"]])) for k, z in SRCS]
        self.src_hint.config(text=tr("　").join(modes) + (tr("　") + tr("，").join(edited) if edited else ""))

    def _src_changed(self, src):
        self.src = src
        self._refresh_src()

    def _race_changed(self, race):
        if race == self.race:
            return
        self._stash()
        self.race = race
        self._unstash(race)
        self.v_veh.set(self.veh_mode)
        self._refresh_src()
        self._rebuild_veh()

    def _diff_changed(self, diff):
        if not isinstance(diff, int):
            return
        s = self.state[self.src]
        s["diff"] = diff
        s["group"] = None
        self.diff_note.config(text=T('N{0} 的{1}逻辑', diff, tr(SRC_ZH[self.src])))
        self._refresh_menu()
        self._build_panel()
        self._apply_live()
        self._mark_pending()

    def _refresh_menu(self):
        src, s = self.src, self.state[self.src]
        waves = self._waves_for(src, s["diff"])
        groups = self._groups_for(src, s["diff"])
        ui.clear_layout(self.menu_lay)
        plist = ParamList(self.menu_lay, ui.YELLOW)
        plist.section(T("N{0} 的菜单", s["diff"]))
        if src == "p":
            hint = T('{0} · N{1}：{2} 捆巡逻随机挑。', tr(RACE_ZH.get(self.race, self.race)), s['diff'], len(groups))
        else:
            hint = T('{0} · N{1}：{2} 个套餐、{3} 捆。每次按预算随机抽几个，不是按顺序轮。',
                     tr(RACE_ZH.get(self.race, self.race)), s['diff'], len(waves), len(groups))
        h = ui.text(None, hint, muted=True, size=9)
        h.setContentsMargins(8, 6, 8, 4)
        self.menu_lay.addWidget(h)
        n, seen = 0, set()
        for w in waves:
            if src == "p":  # 巡逻清单里同一捆会有好几条（速度不同），只列一次
                if w["name"] in seen:
                    continue
                seen.add(w["name"])
            n += 1
            if n > 20:
                continue
            comp = self._sum_groups(src, w["groups"])
            total = sum(comp.values())
            edited = s["mode"] == "custom" and any(k in s["map"] for k in w["groups"])
            r, rl = ui.hbox(spacing=10)
            rl.setContentsMargins(8, 3, 8, 3)
            rl.addWidget(ui.ElideLabel(self._fmt(comp), font=ui.f_zh(9)), 1, VC)
            if edited:
                rl.addWidget(ui.Label("改过", font=ui.f_zh(8, True), fg=ui.WARN), 0, VC)
            right = T("共 {0} 只", total)
            if isinstance(w.get("cost"), (int, float)):
                right += "　" + T("价 {0:g}", w["cost"])
            rl.addWidget(ui.Label(right, font=ui.f_zh(8), fg=ui.MUTED), 0, VC)
            self.menu_lay.addWidget(r)
        if n > 20:
            word = "条巡逻" if src == "p" else "个套餐"
            more = ui.text(None, T('……共 {0} {1}', n, tr(word)), muted=True, size=9)
            more.setContentsMargins(8, 4, 8, 0)
            self.menu_lay.addWidget(more)
        if not n:
            e = ui.text(None, T('这套难度没有{0}。', tr(SRC_ZH[src])), muted=True, size=9)
            e.setContentsMargins(8, 4, 8, 0)
            self.menu_lay.addWidget(e)

    # ================================================================ 上限
    def _sync_cap(self):
        s, van = self.state[self.src], self._vanilla_cap(self.src)
        self.v_cap.set(str(s["cap"] or van))
        val = s["cap"] or van
        self.cap_note.config(text=T('原版 {0}', van) if val == van else
                             (T('比原版 {0} 少', van) if val < van else T('比原版 {0} 多', van)),
                             fg=ui.MUTED if val == van else ui.WARN)

    def _cap_changed(self):
        val = _num(self.v_cap.get(), 0)
        if val < 1:
            return
        val = min(CAP_MAX, val)
        s, van = self.state[self.src], self._vanilla_cap(self.src)
        s["cap"] = 0 if val == van else val
        self._sync_cap()
        self._refresh_menu()
        self._mark_pending()

    # ================================================================ 模式面板
    def _mode_changed(self, mode):
        self.state[self.src]["mode"] = mode
        self._refresh_menu()
        self._build_panel()
        self._apply_live()
        self._mark_pending()

    def _reset_src(self):
        s = self.state[self.src]
        s.update(mode="vanilla", map={}, group=None, cap=0)
        self.v_mode.set("vanilla")
        self._sync_cap()
        self._refresh_menu()
        self._build_panel()
        self._src_hint()
        self._apply_live()
        self._mark_pending()

    def _build_panel(self):
        ui.clear_layout(self.panel_lay)
        self.controls = []
        src, s = self.src, self.state[self.src]
        zh = SRC_ZH[src]
        self.btn_src_reset.set_enabled(s["mode"] != "vanilla" or bool(s["map"]) or bool(s["cap"]))
        if s["mode"] in ("vanilla", "none"):
            text = (T('按游戏原版：{0}用这张图难度的菜单、原版的捆。', tr(zh)) if s["mode"] == "vanilla" else
                    T('{0}一只都不出。其它来源不受影响。', tr(zh)))
            t = ui.text(None, text, muted=True, size=9)
            t.setContentsMargins(8, 2, 8, 0)
            self.panel_lay.addWidget(t)
        elif s["mode"] == "mult":
            var = ui.Var(str(s["mult"]))
            st = ui.Stepper(None, var, 1, 20, command=lambda: self._mult_changed(var))
            r = ui.HoverRow("倍数", "每一捆刷出来的数量 × 这个数；种类照原版。")
            r.lay.addWidget(ui.Label("倍数", font=ui.f_zh(11, True)), 0, VC)
            r.lay.addSpacing(40)
            r.lay.addWidget(st, 0, VC)
            r.lay.addWidget(ui.Label("每一捆刷出来的数量 × 这个数", font=ui.f_zh(9), fg=ui.MUTED), 0, VC)
            r.lay.addStretch(1)
            self.panel_lay.addWidget(r)
            self.controls.append(st)
        else:
            self._build_custom_panel()

    def _mult_changed(self, var):
        val = _num(var.get(), 0)
        if val < 1:
            return
        self.state[self.src]["mult"] = min(20, val)
        self._refresh_menu()
        self._mark_pending()

    def _build_custom_panel(self):
        src, s = self.src, self.state[self.src]
        groups = self._groups_for(src, s["diff"])
        if not groups:
            self.panel_lay.addWidget(ui.text(None, T('这套难度没有{0}，没得改。', SRC_ZH[src]), muted=True))
            return
        if s["group"] not in groups:
            s["group"] = groups[0]
        note = tr("同一捆可能被好几个套餐用到，改一捆它们一起变。" if src != "p" else "巡逻一条就是一捆。")
        if src in ("a", "p"):
            note += tr("警报和巡逻在游戏里共用捆，这里各改各的，互不影响。")
        plist = ParamList(self.panel_lay, ui.SALMON)
        plist.section("改哪一捆（名字是捆里第一只怪，绿色方块 = 改过）", top=10)
        picker = PickGrid(self._select_group)
        picker.MIN_W = 200
        picker.set_items([(k, self._group_label(src, k), k in s["map"],
                           T("原版：{0}。", self._fmt(self._vanilla(src, k))) + note) for k in groups], s["group"])
        self.panel_lay.addWidget(picker)
        key = s["group"]
        comp = self._comp(src, key)
        plist.section(T('正在改：{0}', self._group_label(src, key)), top=12)
        head, hl = ui.hbox(spacing=10)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.addWidget(ui.ElideLabel(T('原版：{0}', self._fmt(self._vanilla(src, key))), font=ui.f_zh(9), fg=ui.MUTED), 1, VC)
        btn = small_button("这一捆按原版还原", lambda: self._restore_group(s["group"]))
        btn.set_enabled(key in s["map"])
        hl.addWidget(btn, 0, VC)
        self.panel_lay.addWidget(head)
        self.controls.append(btn)
        choices, removed = self._unit_choices()
        if not choices:
            self.panel_lay.addWidget(ui.text(None, "没读到怪物清单（ai\\drill_monsters.json）。", muted=True))
            return
        egrid_w = ui.QWidget(None)
        egrid = QGridLayout(egrid_w)
        egrid.setContentsMargins(8, 2, 8, 0)
        egrid.setHorizontalSpacing(16)
        egrid.setVerticalSpacing(4)
        for i, (path, label, m) in enumerate(choices):
            var = ui.Var(path in comp)
            weight = ui.Var(str(comp.get(path, 1)))
            cb = ui.CheckBox(None, label, var, command=lambda v=var, p=path: self._set_unit(p, v),
                             note="未实测" if m.get("test") == "untested" else None)
            st = ui.Stepper(None, weight, 1, 40, width=2, command=lambda w=weight, p=path: self._set_qty(p, w))
            egrid.addWidget(cb, i // 2, (i % 2) * 3, Qt.AlignmentFlag.AlignLeft | VC)
            egrid.addWidget(st, i // 2, (i % 2) * 3 + 1, Qt.AlignmentFlag.AlignLeft | VC)
            self.controls += [cb, st]
        egrid.setColumnMinimumWidth(2, 24)
        egrid.setColumnStretch(5, 1)
        self.panel_lay.addWidget(egrid_w)
        if removed:
            t = ui.text(None, T('另有 {0} 种实测刷了会崩，已拿掉。', removed), muted=True, size=9)
            t.setContentsMargins(8, 4, 8, 0)
            self.panel_lay.addWidget(t)

    def _select_group(self, key):
        self.state[self.src]["group"] = key
        self._build_panel()
        self._apply_live()

    def _edit_comp(self):
        s = self.state[self.src]
        key = s["group"]
        return s["map"].setdefault(key, self._vanilla(self.src, key))

    def _set_unit(self, path, var):
        if not self.live:
            self.app.say("游戏没开，不能改出怪。", "warn")
            return
        comp = self._edit_comp()
        if var.get():
            comp[path] = max(1, int(comp.get(path, 1)))
        else:
            comp.pop(path, None)
        self._refresh_menu()
        self._src_hint()
        self._mark_pending()

    def _set_qty(self, path, weight):
        if not self.live:
            return
        n = _num(weight.get(), 0)
        if n < 1:
            return
        comp = self._edit_comp()
        if path in comp:
            comp[path] = n
        self._refresh_menu()
        self._mark_pending()

    def _restore_group(self, key):
        self.state[self.src]["map"].pop(key, None)
        self._refresh_menu()
        self._build_panel()
        self._src_hint()
        self._apply_live()
        self._mark_pending()

    # ================================================================ 载具 / 首领放兵
    def _veh_changed(self, mode):
        self.veh_mode = mode
        self._rebuild_veh()
        self._mark_pending()

    def _rebuild_veh(self):
        ui.clear_layout(self.veh_lay)
        self.veh_controls = []
        info = self._vehicle_units()
        if info:
            parts = [T('{0}放「{1}」×{2}', tr(v['vehicle']), tr(v['unit']), v['amount']) for v in info]
            self.veh_hint.config(text=tr("这一族原版：") + "；".join(parts) + "。")
        else:
            self.veh_hint.config(text="这一族没有写在设置里的载具放兵；首领召唤 / 其它单独刷出来的兵也归这一块管"
                                      "（原版按它们自己的召唤表）。")
        # 2026-11-18 V0.96 用户要求：坦克（步兵战车）屁股下来几只能选（原版 / 只出选中都能设，不出时不显示）
        self.veh_orig = max(1, int(info[0]["amount"])) if info else 3
        self.row_veh_count.setVisible(bool(info) and self.veh_mode != "none")
        self.v_veh_count.set(str(self.veh_count or self.veh_orig))
        self._veh_count_note()
        if self.veh_mode == "vanilla":
            self.veh_lay.addWidget(ui.text(None, "按游戏原版：放哪种兵不动。", muted=True, size=9))
        elif self.veh_mode == "none":
            self.veh_lay.addWidget(ui.text(None, "载具 / 首领一只兵都不放。", muted=True, size=9))
        else:
            if not self.veh_sel:
                self.veh_sel = self._vehicle_defaults()
                self.veh_qty = dict(self.veh_sel)
            choices, _removed = self._unit_choices()
            if not choices:
                self.veh_lay.addWidget(ui.text(None, "没读到怪物清单（ai\\drill_monsters.json）。", muted=True))
            else:
                grid_w = ui.QWidget(None)
                grid = QGridLayout(grid_w)
                grid.setContentsMargins(8, 2, 8, 0)
                grid.setHorizontalSpacing(16)
                grid.setVerticalSpacing(4)
                grid.setColumnMinimumWidth(2, 24)
                grid.setColumnStretch(5, 1)
                for i, (path, label, m) in enumerate(choices):
                    var = ui.Var(path in self.veh_sel)
                    # 2026-11-16 用户定：放几只不在这里设（按怪物属性里载具的「召唤数量」），只勾换成谁
                    cb = ui.CheckBox(None, label, var, command=lambda v=var, p=path: self._set_veh_unit(p, v),
                                     note="未实测" if m.get("test") == "untested" else None)
                    grid.addWidget(cb, i // 2, (i % 2) * 3, Qt.AlignmentFlag.AlignLeft | VC)
                    self.veh_controls += [cb]
                self.veh_lay.addWidget(grid_w)
                self.veh_lay.addWidget(ui.text(None, "勾了谁，放出来的兵就换成谁（勾多个就轮着放）。"
                                                     "一次放几只看上面「每次放几只」。",
                                               muted=True, size=9))
                btn = small_button("按原版重选", self._veh_map_sel)
                self.veh_lay.addWidget(ui.line(btn, "<>"))
                self.veh_controls.append(btn)
        self._apply_live()

    def _veh_count_note(self):
        orig = self.veh_orig
        self.veh_count_note.config(text=T("原版 {0} 只", orig) if not self.veh_count else T("改过（原版 {0}）", orig))
        self.btn_veh_count.set_enabled(bool(self.veh_count))

    def _set_veh_count(self, *_a):
        n = int(self.veh_step.value())
        self.veh_count = 0 if n == self.veh_orig else n
        self._veh_count_note()
        self._mark_pending()

    def _reset_veh_count(self):
        self.v_veh_count.set(str(self.veh_orig))
        self._set_veh_count()

    def _set_veh_unit(self, path, var):
        if not self.live:
            self.app.say("游戏没开，不能改出怪。", "warn")
            return
        if var.get():
            self.veh_sel[path] = max(1, int(self.veh_qty.get(path, 1)))
            self.veh_qty[path] = self.veh_sel[path]
        else:
            self.veh_sel.pop(path, None)
        self._mark_pending()

    def _set_veh_qty(self, path, weight):
        if not self.live:
            return
        n = _num(weight.get(), 0)
        if n < 1:
            return
        self.veh_qty[path] = n
        if path in self.veh_sel:
            self.veh_sel[path] = n
        self._mark_pending()

    def _veh_map_sel(self):
        self.veh_sel = self._vehicle_defaults()
        self.veh_qty = dict(self.veh_sel)
        self._rebuild_veh()
        self._mark_pending()

    # ================================================================ 灯 / 可用性    def _set_lamp(self, kind, text=None):
        pass

    def _mark_pending(self, *_a):
        self.dirty = True
        s = self.state[self.src]
        self.btn_src_reset.set_enabled(s["mode"] != "vanilla" or bool(s["map"]) or bool(s["cap"]))

    def _apply_live(self):
        pass


def race_command(rd, race):
    """块里一个阵营的数据 -> 发给 spawn_rules.lua 的一条命令（三条来源 + 载具放兵都写全）。"""
    rd = rd or {}
    parts = []
    for src, _z in SRCS:
        s = {"diff": 12 if src == "g" else 5, "mode": "vanilla", "map": {}, "mult": 2, "cap": 0}
        s.update((rd.get("src") or {}).get(src) or {})
        k_mode, k_mult, k_logic, k_map, k_cap = KEYS[src]
        if s["mode"] == "none":
            cmd = f"{k_mode}=none;{k_logic}=off;{k_map}="
        elif s["mode"] == "mult":
            cmd = f"{k_mode}=mult;{k_mult}={int(s['mult'])};{k_logic}=off;{k_map}="
        elif s["mode"] == "custom":
            entries = []
            for key, comp in (s.get("map") or {}).items():
                units = "+".join(f"{p}*{int(n)}" for p, n in comp.items() if int(n) >= 1)
                entries.append(f"{key}={units}")
            cmd = f"{k_mode}=vanilla;{k_logic}={race}:{int(s['diff'])};{k_map}=" + ",".join(entries)
        else:
            cmd = f"{k_mode}=vanilla;{k_logic}=off;{k_map}="
        # 2026-11-16 用户定：上限不手填，游戏那边自动（以前块里存的 cap 不再发）
        parts.append(cmd + f";{k_cap}=0")
    veh = rd.get("veh") or {}
    mode = veh.get("mode") if veh.get("mode") in ("vanilla", "only", "none") else "vanilla"
    # 勾了的兵轮着放（每样 1 份）；放几只按怪物属性里载具的「召唤数量」
    units = ",".join(f"{p}*1" for p, n in (veh.get("sel") or {}).items() if int(n) >= 1)
    count = int(veh.get("count") or 0)
    parts.append(f"v={mode};uv={units if mode == 'only' else ''};vn={count if mode != 'none' and 0 < count <= 50 else 0}")
    spread = int(rd.get("spread") or 0)
    parts.append(f"spread={spread if 0 <= spread <= 3 else 0}")
    # 2026-11-18 V0.96 场上上限：0 / 16 = 原版，17～300 固定，-1 = 破限
    cap = int(rd.get("cap") or 0)
    parts.append(f"cap={cap if cap == -1 or 16 < cap <= 300 else 0}")
    return ";".join(parts)


def summary(rd):
    """块里一个阵营改了什么（方块上显示）。"""
    rd = rd or {}
    out = []
    for src, z in SRCS:
        s = (rd.get("src") or {}).get(src) or {}
        mode = s.get("mode") or "vanilla"
        if mode != "vanilla":
            out.append(z)
    veh = rd.get("veh") or {}
    if (veh.get("mode") or "vanilla") != "vanilla" or int(veh.get("count") or 0):
        out.append("载具")
    if int(rd.get("spread") or 0):
        out.append("散开")
    cap = int(rd.get("cap") or 0)
    if cap < 0:
        out.append("破限")
    elif cap > 16:
        out.append(T("上限{0}", cap))
    return out
