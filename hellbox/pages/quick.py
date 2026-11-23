"""
选图页：选择地图、出怪方式、运行方式与停止条件，一键启动训练关；后台运行 ai/drill_run.py，状态读 drill_status.json，地图参数在 ai/drill_spec.py。
"""
import copy
import ctypes
import json
import os
import subprocess
import sys
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QBoxLayout, QGridLayout, QVBoxLayout, QWidget

import build
import paths
import ui
from pages.base import Page
from pages import map_thumbs as mt
from pages import training_slots as slots
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

AI_DIR = os.path.join(paths.ROOT, "ai")
if AI_DIR not in sys.path:
    sys.path.insert(0, AI_DIR)
import drill_spec as ds  # noqa: E402
from pages import map_picker  # noqa: E402

PYTHON = os.path.join(paths.ROOT, ".venv", "Scripts", "python.exe")
RUNNER = os.path.join(AI_DIR, "drill_run.py")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
POLL_MS = 500
VC = Qt.AlignmentFlag.AlignVCenter

MODE_TABS = [("vanilla", "原版"), ("only", "只出选中"), ("seq", "按节奏"), ("wave", "从第 N 波")]
MODE_NOTE = {
    "vanilla": "和正常报复关一样出怪。",
    "only": "只出下面勾的怪，场上保持最多几只，少了隔几秒补上。勾了几种就轮流出。",
    "seq": "一批一批出：这批全打死了，隔几秒出下一批。每批几只照下面填的数轮着来，比如 1,2 = 1 只、2 只、1 只、2 只……",
    "wave": "原版出怪，但第一波就是第 N 波（冲锋虫第 5 波起才有机会刷）。",
}
STATE_TEXT = {
    "idle": ("未开始", ui.DISABLED), "starting": ("准备中", ui.YELLOW), "stopping_old": ("关旧游戏", ui.YELLOW),
    "launching": ("开游戏", ui.YELLOW), "loading": ("进关中", ui.YELLOW), "joining": ("等出场", ui.YELLOW),
    "running": ("进行中", ui.MINT), "stopping": ("收尾中", ui.SALMON), "done": ("已结束", ui.SKY),
}


def pid_alive(pid):
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259
    except (OSError, ValueError, TypeError):
        return False


def small(s, size=10, bold=True, fg=ui.INK):
    return ui.Label(s, font=ui.f_zh(size, bold), fg=fg)


class _MapBody(QWidget):

    def __init__(self, left, right, gap=28):
        super().__init__()
        self.left, self.right, self.gap = left, right, gap
        self.lay = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(gap)
        self.lay.addWidget(left, 0, Qt.AlignmentFlag.AlignTop)
        self.lay.addWidget(right, 1)
        self.side = True
        self._need = left.sizeHint().width() + gap + 230

    def resizeEvent(self, e):
        super().resizeEvent(e)
        side = self.width() >= self._need
        if side != self.side:
            self.side = side
            self.lay.setDirection(QBoxLayout.Direction.LeftToRight if side else QBoxLayout.Direction.TopToBottom)
            self.lay.setSpacing(self.gap if side else 10)
            self.updateGeometry()


class _MapRight(QWidget):

    def __init__(self, thumb, text_col):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)
        self.lay.addWidget(thumb, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.lay.addWidget(text_col, 1)


class SlotButton(ui.Clickable):

    def __init__(self, index, command):
        super().__init__()
        self.index, self.command = index, command
        self.data, self.selected = None, False
        self.setFixedHeight(62)
        self.setMinimumWidth(120)

    def set_data(self, data, selected):
        self.data, self.selected = data, selected
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        if self.selected:
            fill = ui.MINT
        elif self.data:
            fill = ui.PLAIN_HOVER if self.hovered else ui.WHITE
        else:
            fill = ui.CARD if self.hovered else ui.INSET
        r = ui.paint_box(p, self.width(), self.height(), fill, 2, 3)
        p.fillRect(r.left(), r.top(), 26, 18, ui.qc(ui.INK))
        p.setFont(ui.f_pixel(8))
        p.setPen(ui.qc(ui.CARD))
        p.drawText(ui.QRect(r.left(), r.top(), 26, 18), Qt.AlignmentFlag.AlignCenter, f"{self.index + 1:02d}")
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if not self.data:
            p.setFont(ui.f_zh(10, True))
            p.setPen(ui.qc(ui.MUTED))
            p.drawText(r.adjusted(34, 0, -6, 0), left, tr("空"))
            return
        cfg = self.data["cfg"]
        th = r.height() - 8
        mt.paint(p, ui.QRect(r.right() - th - 3, r.top() + 4, th, th), mt.load(cfg["seed"]), "")
        r = r.adjusted(0, 0, -(th + 6), 0)
        d = ds.decode(cfg["seed"])
        line1 = T('{0} · 难度 {1}', tr(dict(ds.RACES)[ds.race_key(cfg['seed'])]), d['difficulty'])
        line2 = f"{tr(ds.MISSION_NAME.get(d['mission'], ''))} · {tr(ds.ENVS[d['env']][1])} · {tr(ds.TIMES[d['time']][1])}"
        if not build.is_public():
            line2 += " · " + tr(dict(MODE_TABS).get(cfg["spawn"]["mode"], ""))
        p.setPen(ui.qc(ui.INK))
        p.setFont(ui.f_zh(10, True))
        fm = p.fontMetrics()
        p.drawText(ui.QRect(r.left() + 34, r.top(), r.width() - 40, 18), left,
                   fm.elidedText(line1, Qt.TextElideMode.ElideRight, r.width() - 40))
        p.setFont(ui.f_zh(9))
        p.setPen(ui.qc(ui.MUTED if not self.selected else ui.INK))
        fm = p.fontMetrics()
        p.drawText(ui.QRect(r.left() + 8, r.top() + 22, r.width() - 14, r.height() - 24), left,
                   fm.elidedText(line2, Qt.TextElideMode.ElideRight, r.width() - 14))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.enabled and self.rect().contains(e.position().toPoint()):
            self.command(self.index)


class QuickPage(Page):
    key = "quick"
    tab = "选图"
    when = "游戏未运行：自行启动游戏进入这一关；在飞船上：单人直接进入，有队友则设为下一局"
    when_color = ui.YELLOW

    def build(self):
        self.cfg = ds.load_last()
        if build.is_public() and not os.path.isfile(ds.LAST):
            self.cfg["spawn"]["mode"] = "vanilla"
        self.run_dir = None
        self.proc = None
        self.runner_pid = None
        self.last = {}
        self._race_built = None
        self._poll_timer = None

        d = ds.decode(self.cfg["seed"])
        self.v_mission = ui.Var(str(d["mission"]))
        self.v_race = ui.Var(ds.RACES[d["race"]][0])
        self.v_env = ui.Var(str(d["env"]))
        self.v_time = ui.Var(str(d["time"]))
        self.v_diff = ui.Var(str(d["difficulty"]))
        self.v_seed = ui.Var(str(self.cfg["seed"]))

        sp = self.cfg["spawn"]
        self.v_mode = ui.Var(sp["mode"])
        self.v_max = ui.Var(str(sp["max"]))
        self.v_seq = ui.Var(",".join(map(str, sp["seq"])))
        self.v_gap = ui.Var("%g" % sp["gap"])
        self.v_wave = ui.Var(str(max(2, sp["start_wave"])))
        self.unit_vars = {}

        rn, st = self.cfg["run"], self.cfg["stop"]
        self.v_script = ui.Var(rn["script"])
        self.scripts = []
        self.script_vars = {}
        self.v_primary = ui.Var(bool(rn.get("primary_only")))
        self.v_kill_on = ui.Var(st["kills"] > 0)
        self.v_kills = ui.Var(str(st["kills"] or 20))
        self.v_death = ui.Var(st["first_death"])
        self.v_min_on = ui.Var(st["minutes"] > 0)
        self.v_min = ui.Var("%g" % (st["minutes"] or 10))

        map_card = self._build_map()
        spawn_card = self._build_spawn()
        if build.is_public():
            spawn_card.hide()
            self.view.row(map_card)
            self.view.row(self._build_train())
        else:
            self.view.row(map_card, spawn_card)
            self.view.row(self._build_run(), self._build_status())
        self._rebuild_units()
        self._mode_changed(save=False)
        if not build.is_public():
            self._rebuild_scripts()
            self._attach_current()
        self._refresh_map_text()

    # ------------------------------------------------------------ 训练存档
    def _build_train(self):
        card = ui.Card(self.view, "TRAIN", "存档", fill=ui.MINT)
        self.slots = slots.load()
        self.slot_sel = None
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self.slot_btns = []
        for i in range(slots.COUNT):
            b = SlotButton(i, self._slot_clicked)
            self.slot_btns.append(b)
            grid.addWidget(b, i // 4, i % 4)
        card.add(grid_w)
        self.btn_slot_save = ui.Button(None, "存进选中的格子", self._slot_save, kind="accent", padx=10, pady=3)
        self.btn_slot_clear = ui.Button(None, "清空这一格", self._slot_clear, padx=10, pady=3)
        card.add(ui.line(self.btn_slot_save, 10, self.btn_slot_clear), top=12)
        self._paint_slots()
        return card

    def _paint_slots(self):
        for i, b in enumerate(self.slot_btns):
            b.set_data(self.slots[i], i == self.slot_sel)
        has = self.slot_sel is not None
        self.btn_slot_save.set_enabled(has)
        self.btn_slot_clear.set_enabled(has and bool(self.slots[self.slot_sel]))


    def _slot_clicked(self, i):
        if self.slot_sel == i:
            self.slot_sel = None
            self._paint_slots()
            return
        self.slot_sel = i
        data = self.slots[i]
        if data:
            self._apply_cfg(data["cfg"])
            self.app.say(T('读取了第 {0} 格：{1}', i + 1, ds.describe(self.cfg['seed'])), "ok")
        self._paint_slots()

    def _slot_save(self):
        i = self.slot_sel
        if i is None:
            return
        if self.slots[i] and not self.app.ask(T('第 {0} 格已经有存档了，覆盖吗？', i + 1)):
            return
        self.slots[i] = {"cfg": copy.deepcopy(self._collect())}
        slots.save(self.slots)
        self._paint_slots()
        self.app.say(T('已存进第 {0} 格。', i + 1), "ok")

    def _slot_clear(self):
        i = self.slot_sel
        if i is None or not self.slots[i] or not self.app.ask(T('清空第 {0} 格？', i + 1)):
            return
        self.slots[i] = None
        slots.save(self.slots)
        self._paint_slots()

    def _apply_cfg(self, cfg):
        self.cfg = ds.normalize(copy.deepcopy(cfg))
        sp = self.cfg["spawn"]
        for var, val in ((self.v_mode, sp["mode"]), (self.v_max, str(sp["max"])), (self.v_seq, ",".join(map(str, sp["seq"]))),
                         (self.v_gap, "%g" % sp["gap"]), (self.v_wave, str(max(2, sp["start_wave"])))):
            if var.get() != val:
                var.set(val)
        self._race_built = None
        self._mode_changed(save=False)
        self._set_seed(self.cfg["seed"])

    # ------------------------------------------------------------ 小工具
    def _label(self, text, width=5):
        lab = ui.Label(text, font=ui.f_zh(10, True), fg=ui.MUTED)
        lab.setFixedWidth(max(ui.chars(lab.font(), width), ui._tw(lab.font(), lab.text()) + 8))
        return lab

    def _line(self, card, label=None, pady=4, box=None, left=True):
        w, lay = ui.hbox()
        if left:
            lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if label:
            lay.addWidget(self._label(label), 0, VC)
        if box is None:
            card.add(w, top=pady)
        else:
            if pady:
                box.addSpacing(pady)
            box.addWidget(w)
        lay.row_widget = w
        return lay

    def _seg(self, lay, options, var, command, padx=9):
        s = ui.Segmented(None, options, var, command=command, padx=padx, pady=4, shadow=3, font=ui.f_zh(10, True))
        lay.addWidget(s, 0, VC)
        return s

    # ------------------------------------------------------------ 地图
    def _build_map(self):
        card = ui.Card(self.view, "MAP", "地图", fill=ui.YELLOW)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        self.seg_mission = self._seg(self._line(card, "类型", 0, box=lv), [(str(v), z) for v, z in ds.MISSIONS],
                                     self.v_mission, lambda v: self._map_changed())
        self.seg_race = self._seg(self._line(card, "种族", 8, box=lv), [(k, z) for k, z in ds.RACES], self.v_race,
                                  lambda v: self._map_changed())
        self.seg_env = self._seg(self._line(card, "环境", 8, box=lv), [(str(i), z) for i, (_k, z) in enumerate(ds.ENVS)],
                                 self.v_env, lambda v: self._map_changed(), padx=7)
        self.seg_time = self._seg(self._line(card, "时间", 8, box=lv), [(str(i), z) for i, (_k, z) in enumerate(ds.TIMES)],
                                  self.v_time, lambda v: self._map_changed(), padx=7)
        lay = self._line(card, "难度", 8, box=lv)
        self.st_diff = ui.Stepper(None, self.v_diff, 1, 15, command=self._map_changed, width=3)
        lay.addWidget(self.st_diff, 0, VC)
        lay.addSpacing(6)
        lay.addWidget(small("（1~15）", 9, False, ui.MUTED), 0, VC)

        lv.addStretch(1)

        text_col = QWidget()
        rl = QVBoxLayout(text_col)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        self.map_thumb = map_picker.ClickMap(200, self._pick_terrain)
        rl.addSpacing(4)
        self.map_hint = ui.text(None, tr("点此选择地形（需游戏运行中）"), bold=True, size=10)
        rl.addWidget(self.map_hint)
        rl.addStretch(1)
        w = _MapBody(left, _MapRight(self.map_thumb, text_col))
        card.add(w, top=4)
        self.btn_start = ui.Button(None, "开始", self.start, kind="primary", padx=26, pady=6, font=ui.f_zh(11, True))
        card.add(self.btn_start, top=12, align=ui.LEFT)
        self._map_requested = None
        self.app.after(1000, self._map_tick)
        return card

    def _map_seeds(self):
        seeds = [self.cfg["seed"]]
        for data in getattr(self, "slots", None) or []:
            if data:
                seeds.append(data["cfg"]["seed"])
        return seeds

    def _map_tick(self):
        seeds = self._map_seeds()
        if seeds != self._map_requested:
            self._map_requested = seeds
            mt.request(seeds, owner="quick")
        self.map_thumb.set_cells(mt.load(self.cfg["seed"]))
        if hasattr(self, "slot_btns"):
            for b in self.slot_btns:
                b.update()
        self.app.after(1500, self._map_tick)

    def _map_changed(self):
        base = int(self.v_seed.get()) if ds.valid_seed(self.v_seed.get()) else self.cfg["seed"]
        seed = ds.with_fields(base, race=[k for k, _ in ds.RACES].index(self.v_race.get()), env=int(self.v_env.get()),
                              time=int(self.v_time.get()), difficulty=self.st_diff.value(), mission=int(self.v_mission.get()))
        self._set_seed(seed)

    def _set_seed(self, seed):
        self.cfg["seed"] = seed
        d = ds.decode(seed)
        for var, val in ((self.v_seed, str(seed)), (self.v_mission, str(d["mission"])), (self.v_race, ds.RACES[d["race"]][0]), (self.v_env, str(d["env"])),
                         (self.v_time, str(d["time"])), (self.v_diff, str(d["difficulty"]))):
            if var.get() != val:
                var.set(val)
        self._refresh_map_text()
        self._rebuild_units()
        self._save()

    def _pick_terrain(self):
        def picked(seed):
            self._set_seed(seed)
            self._map_requested = None
            self.app.say(T('换了地形：{0}', ds.describe(seed)), "ok")
        seed = self.cfg["seed"]
        map_picker.MapPicker(self.view, seed, map_picker.candidates(seed), picked,
                             lambda: bool(self.app.state.get("running")), title=ds.describe(seed)).exec()
        self._map_requested = None

    def _default_map(self):
        self._set_seed(ds.DEFAULT["seed"])

    def _refresh_map_text(self):
        self.map_hint.config(text=tr("点此选择地形（需游戏运行中）"))
        if hasattr(self, "map_thumb"):
            self.map_thumb.set_cells(mt.load(self.cfg["seed"]))

    # ------------------------------------------------------------ 出怪
    def _build_spawn(self):
        card = ui.Card(self.view, "SPAWN", "出怪", fill=ui.SALMON)
        self.seg_mode = self._seg(self._line(card, None, 0), MODE_TABS, self.v_mode, lambda v: self._mode_changed())
        self.mode_note = card.add(ui.text(card.body, "", muted=True, size=9), top=6)

        self.units_box = QWidget()
        ub = QVBoxLayout(self.units_box)
        ub.setContentsMargins(0, 0, 0, 0)
        ub.setSpacing(0)
        ub.addSpacing(8)
        self.units_title = ui.text(None, "", bold=True, size=10)
        ub.addWidget(self.units_title)
        ub.addSpacing(2)
        grid_w = QWidget()
        self.units_grid = QGridLayout(grid_w)
        self.units_grid.setContentsMargins(0, 0, 0, 0)
        self.units_grid.setHorizontalSpacing(10)
        self.units_grid.setVerticalSpacing(4)
        self.units_grid.setColumnStretch(0, 1)
        self.units_grid.setColumnStretch(1, 1)
        ub.addWidget(grid_w)
        ub.addSpacing(4)
        self.units_hint = ui.text(None, "", muted=True, size=8)
        ub.addWidget(self.units_hint)
        card.add(self.units_box)

        self.params = QWidget()
        pl = QVBoxLayout(self.params)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(4)
        card.add(self.params, top=6)

        lay = self._line(None, None, 0, box=pl)
        lay.addWidget(self._label("场上最多", 8), 0, VC)
        self.st_max = ui.Stepper(None, self.v_max, 1, 40, command=self._save, width=3)
        lay.addWidget(self.st_max, 0, VC)
        lay.addSpacing(6)
        lay.addWidget(small("只"), 0, VC)
        self.row_max = lay.row_widget

        lay = self._line(None, None, 0, box=pl)
        lay.addWidget(self._label("每批几只", 8), 0, VC)
        self.seq_box = ui.Entry(None, self.v_seq, width=12, font=ui.f_mono(11, True))
        self.e_seq = self.seq_box.edit
        lay.addWidget(self.seq_box, 0, VC)
        self.e_seq.editingFinished.connect(self._seq_typed)
        lay.addSpacing(8)
        lay.addWidget(small("逗号隔开，轮着来", 9, False, ui.MUTED), 0, VC)
        self.row_seq = lay.row_widget

        lay = self._line(None, None, 0, box=pl)
        self.gap_label = self._label("隔几秒", 8)
        lay.addWidget(self.gap_label, 0, VC)
        self.st_gap = ui.Stepper(None, self.v_gap, 0, 60, command=self._save, width=3, is_float=True)
        lay.addWidget(self.st_gap, 0, VC)
        lay.addSpacing(6)
        lay.addWidget(small("秒"), 0, VC)
        self.row_gap = lay.row_widget

        lay = self._line(None, None, 0, box=pl)
        lay.addWidget(self._label("从第", 8), 0, VC)
        self.st_wave = ui.Stepper(None, self.v_wave, 2, 99, command=self._save, width=3)
        lay.addWidget(self.st_wave, 0, VC)
        lay.addSpacing(6)
        lay.addWidget(small("波开打"), 0, VC)
        self.row_wave = lay.row_widget
        return card

    def _rebuild_units(self):
        race = ds.race_key(self.cfg["seed"])
        if race == self._race_built:
            return
        self._race_built = race
        ui.clear_layout(self.units_grid)
        chosen = set(self.cfg["spawn"]["units"].get(race, []))
        ok, removed = ds.pickable(race)
        self.unit_vars = {}
        for i, m in enumerate(ok):
            var = ui.Var(m["path"] in chosen)
            self.unit_vars[m["path"]] = var
            note = "未实测" if m.get("test") == "untested" else None
            cb = ui.CheckBox(None, ds.label(m), var, command=self._units_changed, note=note)
            self.units_grid.addWidget(cb, i // 2, i % 2, Qt.AlignmentFlag.AlignLeft | VC)
        self.units_title.config(text=T('要出的怪（{0}，只能选这张图的种族）', tr(dict(ds.RACES)[race])))
        hint = tr("名字是游戏里显示的，括号里是我们平时的叫法。")
        if removed:
            hint += T('另有 {0} 种实测刷了会崩或刷不出来，已从清单拿掉。', removed)
        if not ok:
            hint = "没读到怪物清单（ai\\drill_monsters.json）。"
        self.units_hint.config(text=hint)

    def _units_changed(self):
        race = ds.race_key(self.cfg["seed"])
        self.cfg["spawn"]["units"][race] = [p for p, v in self.unit_vars.items() if v.get()]
        self._save()

    def _seq_typed(self):
        seq = ds.parse_seq(self.v_seq.get() or "")
        if seq is None:
            self.v_seq.set(",".join(map(str, self.cfg["spawn"]["seq"])))
            self.app.say("每批几只要填 1~40 的数，用逗号隔开，比如 1,2", "warn")
            return
        self.v_seq.set(",".join(map(str, seq)))
        self._save()

    def _mode_changed(self, save=True):
        mode = self.v_mode.get()
        self.mode_note.config(text=MODE_NOTE[mode])
        self.units_box.setVisible(mode in ("only", "seq"))
        self.row_max.setVisible(mode == "only")
        self.row_seq.setVisible(mode == "seq")
        self.row_gap.setVisible(mode in ("only", "seq"))
        self.row_wave.setVisible(mode == "wave")
        self.params.setVisible(mode != "vanilla")
        if mode == "only":
            self.gap_label.config(text="少了隔")
        elif mode == "seq":
            self.gap_label.config(text="死光后隔")
        lab = self.gap_label
        lab.setFixedWidth(max(ui.chars(lab.font(), 8), ui._tw(lab.font(), lab.text()) + 8))
        if save:
            self._save()

    # ------------------------------------------------------------ 运行
    def _build_run(self):
        card = ui.Card(self.view, "RUN", "运行", fill=ui.MINT)
        lay = self._line(card, None, 0, left=False)
        lay.addWidget(small("用哪个 AI 脚本"), 0, VC)
        lay.addStretch(1)
        lay.addWidget(ui.Button(None, "刷新", self._refresh_scripts, padx=8, pady=1, shadow=2, font=ui.f_zh(9, True)),
                      0, VC)
        self.script_w = QWidget()
        self.script_box = QVBoxLayout(self.script_w)
        self.script_box.setContentsMargins(0, 0, 0, 0)
        self.script_box.setSpacing(4)
        card.add(self.script_w, top=6)
        self.what_note = card.add(ui.text(card.body, "", muted=True, size=9), top=4)
        lay = self._line(card, None, 6)
        self.cb_primary = ui.CheckBox(None, "只用主武器", self.v_primary, command=self._save,
                                      note="开局不叫支援武器，背包、补给照叫")
        lay.addWidget(self.cb_primary, 0, VC)

        card.add(ui.text(card.body, "什么时候停（满足任意一条就收尾、关游戏）", bold=True, size=10), top=10)
        lay = self._line(card, None, 4)
        self.cb_kills = ui.CheckBox(None, "打死", self.v_kill_on, command=self._save)
        lay.addWidget(self.cb_kills, 0, VC)
        lay.addSpacing(8)
        self.st_kills = ui.Stepper(None, self.v_kills, 1, 999, command=self._save, width=4)
        lay.addWidget(self.st_kills, 0, VC)
        lay.addSpacing(6)
        lay.addWidget(small("只"), 0, VC)
        lay = self._line(card, None, 4)
        self.cb_death = ui.CheckBox(None, "她第一次死", self.v_death, command=self._save)
        lay.addWidget(self.cb_death, 0, VC)
        lay = self._line(card, None, 4)
        self.cb_min = ui.CheckBox(None, "超过", self.v_min_on, command=self._save)
        lay.addWidget(self.cb_min, 0, VC)
        lay.addSpacing(8)
        self.st_min = ui.Stepper(None, self.v_min, 1, 600, command=self._save, width=4, is_float=True)
        lay.addWidget(self.st_min, 0, VC)
        lay.addSpacing(6)
        lay.addWidget(small("分钟"), 0, VC)
        card.add(ui.text(card.body, "都不勾就只能手动点击「停止」。时间从有人出场算起。", muted=True, size=9), top=4)

        lay = self._line(card, None, 14)
        self.btn_stop = ui.Button(None, "停止", self.stop, kind="danger", padx=26, pady=6, font=ui.f_zh(11, True))
        lay.addWidget(self.btn_stop, 0, VC)
        self.start_hint = card.add(ui.text(card.body, "", muted=True, size=9), top=10)
        return card

    def _refresh_scripts(self):
        self._rebuild_scripts()
        self.app.say(T('AI 脚本列表重新找了一遍：{0} 个（ai\\hellbox_scripts 和带 hellbox-script 标记的脚本）', len(self.scripts)), "ok")

    def _rebuild_scripts(self):
        self.scripts = ds.list_scripts()
        ui.clear_layout(self.script_box)
        self.script_vars = {}
        ok_ids = [e["id"] for e in self.scripts if not e["problems"]]
        cur = self.v_script.get()
        if cur not in ok_ids:
            if cur:
                self.app.say(T('之前选的 AI 脚本（{0}）找不到了，改选「{1}」', cur, self.scripts[0]['name']), "warn")
            cur = ok_ids[1] if len(ok_ids) > 1 else ok_ids[0]
            self.v_script.set(cur)
        for e in self.scripts:
            var = ui.Var(e["id"] == cur)
            self.script_vars[e["id"]] = var
            if e["problems"]:
                note = tr("用不了：") + "；".join(e["problems"])
            elif e["mtime"]:
                note = T('{0} · 改于 {1}', os.path.basename(e['script']), datetime.fromtimestamp(e['mtime']).strftime('%m-%d %H:%M'))
            else:
                note = None
            cb = ui.CheckBox(None, e["name"], var, command=lambda sid=e["id"]: self._script_picked(sid),
                             note=note, radio=True)
            self.script_box.addWidget(cb, 0, Qt.AlignmentFlag.AlignLeft)
            if e["problems"]:
                cb.set_enabled(False)
        self._what_changed(save=False)

    def _script_picked(self, sid):
        for k, v in self.script_vars.items():
            if v.get() != (k == sid):
                v.set(k == sid)
        self.v_script.set(sid)
        self._what_changed()

    def current_script(self):
        return ds.find_script(self.v_script.get(), self.scripts)

    def _what_changed(self, save=True):
        e = self.current_script()
        self.cb_primary.set_enabled(bool(e) and "primary_only" in e["options"])
        solo = bool(e) and e["players"] == "solo"
        self.cb_death.label.config(text="她第一次死" if solo else "第一次有人死")
        self.what_note.config(text=e["desc"] if e else "")
        if save:
            self._save()

    # ------------------------------------------------------------ 状态
    def _build_status(self):
        card = ui.Card(self.view, "STATUS", "运行状态", fill=ui.SKY)
        self.st_square = ui.Square(color=ui.DISABLED, size=22)
        self.st_word = ui.Label("未开始", font=ui.f_zh(16, True))
        card.add(ui.line(self.st_square, 10, self.st_word))
        self.st_msg = card.add(ui.text(card.body, "选好设置，点击「开始」。", size=10), top=6)
        self.st_nums = card.add(ui.Label("", font=ui.f_mono(11, True)), top=8)
        self.st_types = card.add(ui.text(card.body, "", muted=True, size=9), top=4)

        card.add(ui.Label("这次的设置", font=ui.f_zh(10, True), fg=ui.MUTED), top=10)
        self.st_cfg = card.add(ui.text(card.body, "", size=9))
        card.add(ui.Label("记录文件夹", font=ui.f_zh(10, True), fg=ui.MUTED), top=8)
        self.st_dir = card.add(ui.Label("（尚未开始）", font=ui.f_mono(9), wrap=True, breakable=True))
        self.btn_open = card.add(ui.Button(None, "打开记录文件夹", self.open_dir, padx=10, pady=3), top=8, align=ui.LEFT)
        return card

    # ------------------------------------------------------------ 设置读写
    def _collect(self):
        sp = self.cfg["spawn"]
        sp["mode"] = self.v_mode.get()
        sp["max"] = self.st_max.value()
        seq = ds.parse_seq(self.v_seq.get() or "")
        if seq:
            sp["seq"] = seq
        sp["gap"] = self.st_gap.value()
        sp["start_wave"] = self.st_wave.value()
        if not build.is_public():
            self.cfg["run"] = {"script": self.v_script.get(), "primary_only": bool(self.v_primary.get())}
            self.cfg["stop"] = {"kills": self.st_kills.value() if self.v_kill_on.get() else 0,
                                "first_death": bool(self.v_death.get()),
                                "minutes": self.st_min.value() if self.v_min_on.get() else 0}
        self.cfg = ds.normalize(self.cfg)
        return self.cfg

    def _save(self):
        try:
            ds.save_last(self._collect())
        except OSError:
            pass
        if not build.is_public() and not self.running():
            self.st_cfg.config(text=self._cfg_text(self.cfg))

    # ------------------------------------------------------------ 开始 / 停止
    def running(self):
        return bool(self.runner_pid and pid_alive(self.runner_pid))

    def start(self):
        if build.is_public():
            self.start_public()
            return
        if self.running():
            return
        cfg = self._collect()
        bad = ds.problems(cfg)
        if bad:
            self.app.warn("\n".join(bad))
            return
        if self.app.state.get("script") != "on":
            self.app.warn("游戏内的 MOD 不是最新版（或未开启），出怪设置不会生效。\n请先在「关于」页开启「核心」开关（需先关闭游戏）。")
            return
        if not os.path.exists(PYTHON):
            self.app.error(T('找不到 Python：{0}', PYTHON))
            return
        if self.app.state.get("running") and not self.app.ask(
                "游戏正在运行。开始后会先关闭游戏（未保存的进度会丢失），再按这里的设置重新启动。\n确定继续吗？"):
            return
        ds.save_last(cfg)
        run = os.path.join(ds.RUNS, "manual_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(run, exist_ok=True)
        req = os.path.join(run, "drill_request.json")
        with open(req, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        try:
            out = open(os.path.join(run, "drill_runner_stdout.txt"), "w", encoding="utf-8")
            self.proc = subprocess.Popen([PYTHON, "-B", RUNNER, req, "--run", run], cwd=paths.ROOT, stdout=out,
                                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                                         creationflags=NO_WINDOW)
        except OSError as e:
            self.app.error(T('启动失败：{0}', e))
            return
        self.runner_pid = self.proc.pid
        self.run_dir = run
        self.last = {"state": "starting", "msg": "准备中……"}
        self.st_cfg.config(text=self._cfg_text(cfg))
        self.app.say("开始了：先关旧游戏，再开游戏进关。", "info")
        self._show()
        self.sync()
        self._poll_later()

    def start_public(self):
        from pages import training
        cfg = copy.deepcopy(self._collect())
        cfg["spawn"]["mode"] = "vanilla"
        cfg["run"] = {"script": ds.GAME_ONLY}
        cfg["stop"] = {"kills": 0, "first_death": False, "minutes": 0}
        bad = ds.problems(cfg)
        if bad:
            self.app.warn("\n".join(bad))
            return

        def action():
            if build.game_running():
                if build.status() != "on" or build.out_is_stale():
                    raise RuntimeError("游戏里的 MOD 不是最新版，不能在飞船上开。请先在游戏中正常退出，再点击「开始」（会先更新 MOD 再开游戏）。")
                ds.save_last(cfg)
                return training.start_in_game(cfg, self._drop_play_trial)
            if build.status() not in ("on", "old"):
                raise RuntimeError("请先打开「关于」页的「核心」开关。")
            if build.status() != "on" or build.out_is_stale():
                build.install()
            ds.save_last(cfg)
            training.launch_online(cfg, self._drop_play_trial)  # 2026-11-22：正常开游戏（在线），进飞船后自动开图
            return "游戏已启动：进到飞船后自动开这张图（10 分钟内）。"

        self.app.run(action, working="正在进入关卡…")

    def _drop_play_trial(self):
        from pages import play_modes as pm
        cfg = pm.load()
        if not cfg.get("trial"):
            return False
        cfg["trial"] = ""
        pm.save(cfg)
        for page in self.app.pages:
            if page.key == "play" and isinstance(getattr(page, "cfg", None), dict):
                page.cfg["trial"] = ""
        return True

    def stop(self):
        if not self.run_dir:
            return
        try:
            open(os.path.join(self.run_dir, "STOP"), "w").close()
            self.app.say("已请求停止：等她收尾、关游戏……", "info")
        except OSError as e:
            self.app.say(T('停不了：{0}', e), "err")

    def open_dir(self):
        if self.run_dir and os.path.isdir(self.run_dir):
            os.startfile(self.run_dir)

    def _attach_current(self):
        try:
            with open(ds.CURRENT, encoding="utf-8") as f:
                cur = json.load(f)
        except (OSError, ValueError):
            cur = None
        if cur and pid_alive(cur.get("runner_pid")) and os.path.isdir(cur.get("run", "")):
            self.runner_pid = cur["runner_pid"]
            self.run_dir = cur["run"]
            try:
                with open(os.path.join(self.run_dir, "drill_settings.json"), encoding="utf-8") as f:
                    run_cfg = json.load(f)
                self.st_cfg.config(text=self._cfg_text(ds.normalize(run_cfg)))
            except (OSError, ValueError, KeyError, TypeError):
                pass
            self._poll_later()
        self._show()

    def _poll_later(self):
        ui.cancel(self._poll_timer)
        self._poll_timer = self.app.after(POLL_MS, self._poll)

    def _poll(self):
        self._poll_timer = None
        if not self.run_dir:
            return
        try:
            with open(os.path.join(self.run_dir, "drill_status.json"), encoding="utf-8") as f:
                self.last = json.load(f)
        except (OSError, ValueError):
            pass
        alive = self.running()
        if not alive and self.last.get("state") != "done":
            self.last = dict(self.last, state="done",
                             reason=(self.last.get("reason") or "运行程序意外退出（看记录文件夹里的 drill_runner_stdout.txt）")
                             + "；已替它让陪玩程序停下、关游戏")
            self._cleanup_orphans()
        self._show()
        if alive:
            self._poll_later()
        else:
            self.runner_pid = None
            self.proc = None
            self.app.say(tr("这次跑完了：") + tr(self.last.get("reason") or ""), "ok")
            self.sync()

    def _cleanup_orphans(self):
        try:
            open(os.path.join(self.run_dir, "STOP"), "w").close()
        except OSError:
            pass

        def kill_game():
            subprocess.run(["taskkill", "/IM", "helldivers.exe", "/F"], capture_output=True, creationflags=NO_WINDOW)

        self.app.after(5000, lambda: self.app.bg(kill_game))

    def _cfg_text(self, cfg):
        entry = ds.find_script(cfg["run"]["script"], self.scripts)
        return "\n".join([T('地图 {0}：{1}', cfg['seed'], ds.describe(cfg['seed'])), ds.spawn_text(cfg),
                          ds.run_text(cfg, entry) if entry else ds.run_text(cfg), ds.stop_text(cfg)])

    def _mon_names(self):
        if getattr(self, "_mons", None) is None:
            mons = {m["name"]: ds.label(m) for ms in ds.load_monsters().values() for m in ms}
            mons["cyborg_dog"] = mons.get("cyborg_dog_01", "cyborg_dog")
            self._mons = mons
        return self._mons

    def _show(self):
        st = self.last or {}
        state = st.get("state", "idle") if self.run_dir else "idle"
        word, color = STATE_TEXT.get(state, (state, ui.YELLOW))
        self.st_word.config(text=word)
        self.st_square.set_color(color)
        msg = st.get("msg") or ""
        if state == "done" and st.get("reason"):
            msg = tr("停的原因：") + tr(st["reason"])
        self.st_msg.config(text=msg or "选好设置，点击「开始」。")
        if self.run_dir:
            el = st.get("elapsed", 0) or 0
            cl = st.get("cleared") or 0
            self.st_nums.config(text=T('打死 {0}   出了 {1}   死了 {2} 次   {3}:{4:02d}', st.get('kills', 0), st.get('spawned', 0), st.get('deaths', 0), int(el // 60), int(el % 60))
                                     + (T('\n另有 {0} 只是她死 / 重生时游戏清掉的，不算打死', cl) if cl else ""))
            mons = self._mon_names()
            seen, dead = st.get("seen_by") or {}, st.get("dead_by") or {}
            parts = [f"{mons.get(k, k)} {dead.get(k, 0)}/{n}" for k, n in sorted(seen.items(), key=lambda kv: -kv[1])]
            self.st_types.config(text=(tr("各种怪 打死/出了：") + ", ".join(parts)) if parts else "")
            self.st_dir.config(text=self.run_dir)
        else:
            self.st_nums.config(text="")
            self.st_types.config(text="")
            self.st_cfg.config(text=self._cfg_text(self.cfg))
        self.btn_open.set_enabled(bool(self.run_dir))

    def sync(self):
        if build.is_public():
            self.btn_start.set_enabled(not self.app.busy and self.app.state["running"] is not None and self.app.mod_on())
            return
        running = self.running()
        script = self.app.state.get("script")
        self.btn_start.set_enabled(not running and not self.app.busy)
        self.btn_stop.set_enabled(running)
        warn = False
        if running:
            hint = "正在运行。点击「停止」= 让它收尾并关闭游戏（几秒到半分钟）。"
        elif self.app.busy:
            hint = "别的页正在改游戏文件，等它做完。"
        elif script not in (None, "on"):
            hint, warn = "游戏内的 MOD 不是最新版：请先在「关于」页开启「核心」开关，出怪设置才会生效。", True
        else:
            hint = "点击「开始」会先关掉正在运行的游戏，再按这里的设置开游戏、直接进训练关（不碰战役进度）。"
        self.start_hint.config(text=hint, fg=ui.WARN if warn else ui.MUTED)

    def on_show(self):
        if not build.is_public() and not self.running():
            self._rebuild_scripts()
        self.sync()
