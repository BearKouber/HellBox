"""战备属性块的编辑器（2026-11-14 V0.91，数据修改页「战备 · 蓝 / 红 / 绿 / 车辆 / 黄」的编辑卡片）。

一类一个编辑器：StratEditor(app, view, cat)，cat = blue / red / green / vehicle / yellow。接口同怪物属性编辑器
（load / dump / set_visible / dirty），手感也一样：数值格平时是小方块，点到才变下拉框。

每个战备列哪些参数、书面名称、原版值、选项方式来自 ai/strat_fields.json（tools/strat_fields.py 生成；
HD1-033 战备属性清单：只列游戏代码实际会读的参数）。
选项方式：
  倍率 mult      ×0～×100（原版值为 0 的给具体数值档）
  秒数 time      0～300 秒的常用档；也可输入 ×2 表示 2 倍
  数量 count     0～10、15、20、30、50、100；也可输入 ×2
  是否 bool；text = 只显示（按键序列）
块的数据：{"common": {路径: 倍数}, "ov": {战备名: {路径: 值}}}；值 '*2' = 按原值乘，其它 = 绝对值（所有升级等级都用它）。
路径：战备表里的项直接写（cooldown_time）；投下来的东西写 @单位路径@设置路径（格式见 mod/src/strat_params.lua）。
"""
import copy
import math
import os

from PySide6.QtCore import Qt

import paths
import ui
from pages.edit_util import (NUMERIC_KINDS, ParamList, PickGrid, ValueSlider, eff_key, is_num, load_json, num,
                             small_button, styled_combo, swap_combo, open_popup, COMBO_W)
from pages.enemy_editor import ValueChip, parse_raw
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

FIELDS = os.path.join(paths.ROOT, "ai", "strat_fields.json")
VC = Qt.AlignmentFlag.AlignVCenter
LEFT_VC = Qt.AlignmentFlag.AlignLeft | VC

CATS = ("blue", "red", "green", "vehicle", "yellow")
ALL = "__all__"
MULTS = [0, 0.25, 0.5, 0.75, 1.25, 1.5, 2, 3, 5, 10, 20, 50, 100]
TIMES = [0, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 300]
COUNTS = list(range(0, 11)) + [15, 20, 30, 50, 100]
ZERO_DIST = [0.5, 1, 2, 5, 10, 20]
ZERO_PLAIN = [0.5, 1, 2, 5, 10, 50, 100, 500, 1000]
COLS = 4

KIND_TIP = {
    "mult": "按原版数值的倍数修改（×0～×100，每个升级等级各按自己的原值乘）；也可直接输入数值（所有升级等级都用这个数）。",
    "zero": "原版数值为 0，按具体数值设定；可直接输入数值。",
    "time": "单位：秒。可直接输入秒数（所有升级等级都用这个数），输入 ×2 表示按原值的 2 倍。",
    "count": "数量。可直接输入整数（所有升级等级都用这个数），输入 ×2 表示按原值的 2 倍。",
    "bool": "是 / 否。",
    "text": "只显示，不开放修改。",
}

_FIELDS_CACHE = None


def fields():
    global _FIELDS_CACHE
    if _FIELDS_CACHE is None:
        _FIELDS_CACHE = load_json(FIELDS, {}) or {}
    return _FIELDS_CACHE


def _num(text):
    try:
        v = float(str(text).strip())
    except ValueError:
        return None
    return v if math.isfinite(v) else None


# ---------------------------------------------------------------- 块 -> 命令（data_blocks.live_text 调）
def strat_command(data, cat):
    """战备属性块 -> strat_params.lua 的命令（只带这一类的战备）。
    data = {"common": {路径: 倍数}, "ov": {战备名: {路径: 值}}}；值 '*2' = 按原值乘，其它 = 绝对值。"""
    data = data or {}
    names = set((fields().get("cats") or {}).get(cat, {}).get("strats") or [])
    common = ",".join(f"{p}*{float(m):g}" for p, m in sorted((data.get("common") or {}).items())
                      if abs(float(m) - 1.0) > 1e-9)
    sets = []
    for name, rows in sorted((data.get("ov") or {}).items()):
        if names and name not in names:
            continue
        for path, val in sorted(rows.items()):
            val = str(val)
            sets.append(f"{name}.{path}{val}" if val.startswith("*") else f"{name}.{path}={val}")
    if not common and not sets:
        return "reset"
    return f"common={common};set={','.join(sets)}"


def summary(data):
    """方块上的一句话。"""
    data = data or {}
    n_common = len([m for m in (data.get("common") or {}).values() if abs(float(m) - 1.0) > 1e-9])
    n_strats = len([f for f in (data.get("ov") or {}).values() if f])
    n_rows = sum(len(f) for f in (data.get("ov") or {}).values())
    parts = []
    if n_common:
        parts.append(f"本类 {n_common} 项")
    if n_strats:
        parts.append(f"{n_strats} 个战略配备 {n_rows} 项")
    return "，".join(parts) or "全原版"


class StratEditor:
    def __init__(self, app, view, cat):
        self.app, self.view, self.cat = app, view, cat
        f = fields()
        self.info = (f.get("cats") or {}).get(cat) or {"zh": cat, "strats": []}
        self.strats = f.get("strats") or {}
        self.names = [n for n in self.info.get("strats") or [] if n in self.strats]
        self.common_rows = f.get("common") or []
        self.common_paths = {r["path"] for r in self.common_rows}
        self.sel = ALL
        self.common = {}
        self.ov = {}
        self.dirty = False
        self._open = None  # 正在下拉的那一格 (combo, chip, choose, typed)

        # 2026-11-15 新界面：选战备 = 平的等宽格子（绿方块 = 改过），参数 = 一行一项、说明进底栏
        pick = ui.Card(view, "PICK", T("选战略配备 · {0}", tr(self.info.get("zh", ""))), fill=ui.YELLOW,
                       note="绿色方块 = 改过")
        if self.info.get("desc"):
            pick.add(ui.text(pick.body, self.info["desc"], muted=True, size=9))
        self.picker = PickGrid(self._select)
        pick.add(self.picker, top=8)

        self.card = ui.Card(view, "EDIT", "", fill=ui.SALMON, note=" ")
        self.btn_reset = small_button("全部还原", self._reset_sel)
        self.card.head_lay.addSpacing(10)
        self.card.head_lay.addWidget(self.btn_reset, 0, VC)
        self.notes = self.card.add(ui.text(self.card.body, "", muted=True, size=9))
        self.body_w, self.body_lay = ui.vbox(spacing=0)
        self.card.add(self.body_w, top=6)

        self.rows = [view.row(pick), view.row(self.card)]
        self._refresh()

    # ================================================================ 块的读写
    def load(self, data, race=None):
        data = data or {}
        self.common = {p: float(m) for p, m in (data.get("common") or {}).items() if p in self.common_paths}
        self.ov = {n: dict(f) for n, f in copy.deepcopy(data.get("ov") or {}).items() if n in self.strats and f}
        self.sel = ALL
        self.dirty = False
        self._refresh()

    def dump(self):
        return {"common": {p: m for p, m in self.common.items() if abs(m - 1.0) > 1e-9},
                "ov": {n: dict(f) for n, f in self.ov.items() if f}}

    def set_visible(self, on):
        for r in self.rows:
            r.setVisible(on)

    # ================================================================ 选战备
    def _select(self, name):
        self.sel = name
        self._refresh()

    def _zh(self, name):
        return (self.strats.get(name) or {}).get("zh") or name

    def _items(self):
        items = [(ALL, "本类全部", bool(self.common),
                  "本类全部：按每个战略配备自己的原版数值乘（升级后的数值也按各自原值乘）；单个战略配备设了的那一项以单个为准。")]
        items += [(n, self._zh(n), bool(self.ov.get(n)),
                   "\n".join((self.strats.get(n) or {}).get("notes") or []) or "点开改这个战略配备的参数。")
                  for n in self.names]
        return items

    def _refresh(self):
        self._close_open(apply=False)
        ui.clear_layout(self.body_lay)
        self.plist = ParamList(self.body_lay, ui.SALMON)
        if self.sel == ALL:
            self._build_common()
        else:
            self._build_strat(self.sel)
        self.notes.setVisible(bool(self.notes.text()))
        self._mark_buttons()

    def _mark_buttons(self):
        """选战备格子上的绿方块、「全部还原」能不能点。"""
        self.picker.set_items(self._items(), self.sel)
        self.btn_reset.set_enabled(bool(self.common) if self.sel == ALL else bool(self.ov.get(self.sel)))

    # ================================================================ 本类全部
    def _build_common(self):
        self.card.title_lab.config(text=T("{0} · 本类全部", tr(self.info.get("zh", ""))))
        self.card.note_lab.config(text="按每个战略配备自己的原版数值乘")
        self.notes.config(text="冷却、呼叫时间下次扔信标起生效；已经放下的炮台只有伤害、射程这类开火时读的项马上变。"
                               "联机时只对自己（和本机 2P）的战略配备确定生效，建议全队用同一份设置。")
        for row in self.common_rows:
            path = row["path"]
            m = self.common.get(path, 1.0)
            chip = ValueSlider(self._mult_text(m), abs(m - 1) > 1e-9)
            self._setup_common(chip, path)  # 2026-11-15 下拉换成滑条
            self.plist.row(row["label"], chip,
                           help=" ".join(t for t in (tr(row.get("tip", "")), tr(KIND_TIP["mult"])) if t))

    @staticmethod
    def _mult_text(m):
        return "×1（原版）" if abs(m - 1) < 1e-9 else f"×{m:g}"

    def _setup_common(self, chip, path):
        def choose(val):
            if val is None:
                self.common.pop(path, None)
            else:
                self.common[path] = float(val)
            self._changed()
            m = self.common.get(path, 1.0)
            chip.set_text(self._mult_text(m), abs(m - 1) > 1e-9)

        opts = [("×1（原版）", None)] + [(f"×{m:g}", m) for m in MULTS]

        def typed(text):
            v = _num(text.lstrip("×xX*"))
            return None if v is None else min(100.0, max(0.0, v))

        chip.setup(opts, choose, typed, key=lambda v: 1.0 if v is None else float(v), cur=self.common.get(path, 1.0))

    # ================================================================ 单个战备
    def _build_strat(self, name):
        info = self.strats.get(name) or {}
        title = self._zh(name)
        if info.get("en") and info.get("en") != title:
            title += f"（{info['en']}）"
        self.card.title_lab.config(text=title)
        self.card.note_lab.config(text=tr(self.info.get("zh", "")))
        self.notes.config(text="\n".join(info.get("notes") or []))
        for block in info.get("blocks") or []:
            self.plist.section(block["title"])
            for row in block["rows"]:
                base = row.get("value")
                kind = self._kind(row, base)
                if kind == "text":
                    w = ui.Label(self._show(row, base) + tr("（不开放）"), font=ui.f_zh(9), fg=ui.MUTED)
                else:
                    text, changed = self._current(name, row, base)
                    w = self._value_widget(name, row, base, kind, text, changed, None, None)
                help_text = " ".join(t for t in (tr(row.get("tip", "")), T("原版：{0}", self._orig_text(row)) + "。",
                                                  tr(KIND_TIP[kind])) if t)
                self.plist.row(row["label"], w, T("原版 {0}", self._orig_text(row)) if kind != "text" else None,
                               help=help_text)

    @staticmethod
    def _kind(row, base):
        kind = row["kind"]
        if kind == "mult" and isinstance(base, (int, float)) and not isinstance(base, bool) and base == 0:
            return "zero"
        return kind

    # ---------------------------------------------------------------- 显示
    def _show(self, row, v):
        kind = row["kind"]
        if v is None:
            return tr("无")
        if isinstance(v, bool):
            return tr("是" if v else "否")
        if not isinstance(v, (int, float)):
            return str(v)
        if kind == "time":
            return T("{0} 秒", num(v))
        if kind == "count":
            return str(int(round(v)))
        return num(v)

    def _orig_text(self, row):
        text = self._show(row, row.get("value"))
        ups = row.get("ups")
        if ups:
            text += T("（升级后 {0}）", " / ".join(self._show(row, u) for u in ups))
        return text

    def _current(self, name, row, base):
        own = (self.ov.get(name) or {}).get(row["path"])
        if own is not None:
            if own.startswith("*"):
                m = float(own[1:])
                if isinstance(base, (int, float)) and not isinstance(base, bool):
                    v = base * m
                    if row["kind"] == "count":
                        v = math.floor(v + 0.5)
                    return f"×{m:g} = {self._show(row, v)}", True
                return f"×{m:g}", True
            return self._show(row, parse_raw(own)), True
        m = self.common.get(row["path"])
        if m is not None and isinstance(base, (int, float)) and not isinstance(base, bool):
            v = base * m
            if row["path"] == "num_uses":
                v = math.floor(v + 0.5)
            return T("跟本类 ×{0:g} = {1}", m, self._show(row, v)), True
        return tr("原版"), False  # 2026-11-15 新界面：原版的数在这一行最右边

    # ---------------------------------------------------------------- 下拉的选项
    def _options(self, row, base, kind):
        """[(文字, 存的值 / None = 原版)]，和「打字怎么解析」。"""
        orig = (T("原版（{0}）", self._show(row, base)), None)

        def mult_or_abs(text, integer=False):
            text = text.strip().replace("秒", "").strip().rstrip("sS").strip()  # 英文版显示「5s」
            if text[:1] in "×xX*":
                v = _num(text[1:])
                return None if v is None else f"*{min(100.0, max(0.0, v)):g}"
            v = _num(text)
            if v is None:
                return None
            v = max(0.0, v)
            return str(int(round(v))) if integer else f"{v:g}"

        if kind == "mult":
            opts = [orig] + [(f"×{m:g} = {self._show(row, base * m)}", f"*{m:g}") for m in MULTS]
            return opts, mult_or_abs
        if kind == "zero":
            vals = ZERO_DIST if "米" in row["label"] else ZERO_PLAIN
            if "秒" in row["label"]:
                vals = TIMES
            opts = [orig] + [(self._show(row, v), f"{v:g}") for v in vals]
            return opts, lambda t: None if _num(t) is None else f"{max(0.0, _num(t)):g}"
        if kind == "time":
            opts = [orig] + [(T("{0} 秒", f"{v:g}"), f"{v:g}") for v in TIMES if v != base]
            return opts, mult_or_abs
        if kind == "count":
            opts = [orig] + [(str(v), str(v)) for v in COUNTS if v != base]
            return opts, lambda t: mult_or_abs(t, integer=True)
        if kind == "bool":
            return [(tr("是" if v else "否") + (tr("（原版）") if v == base else ""),
                     None if v == base else ("true" if v else "false")) for v in (True, False)], None
        return [orig], None

    # ---------------------------------------------------------------- 点开 / 选好
    def _value_widget(self, name, row, base, kind, text, changed, grid, r):
        """数值类：滑条（2026-11-15 用户要求）；是否这种：点了变下拉框的小方块。"""
        if kind in NUMERIC_KINDS and is_num(base):
            w = ValueSlider(text, changed)
            opts, choose, typed = self._row_handlers(w, name, row, base)
            key = eff_key(base)
            own = (self.ov.get(name) or {}).get(row["path"])
            m = self.common.get(row["path"])
            try:
                cur = key(own) if own is not None else (base * m if m is not None else base)
            except (TypeError, ValueError):
                cur = base
            if w.setup(opts, choose, typed, key, cur):
                return w
        w = ValueChip(text, None, changed)
        w.command = lambda c=w: self._open_row(c, name, row, base, grid, r)
        return w

    def _open_row(self, chip, name, row, base, grid, r):
        self._open_combo(chip, grid, r, *self._row_handlers(chip, name, row, base))

    def _row_handlers(self, chip, name, row, base):
        kind = self._kind(row, base)
        opts, typed = self._options(row, base, kind)

        def choose(val):
            rows = self.ov.setdefault(name, {})
            if val is None:
                rows.pop(row["path"], None)
            else:
                rows[row["path"]] = val
            if not rows:
                self.ov.pop(name, None)
            self._changed()
            chip.set_text(*self._current(name, row, base))

        return opts, choose, typed

    def _open_combo(self, chip, grid, r, opts, choose, typed):
        self._close_open(apply=False)
        c = styled_combo(editable=typed is not None, width=COMBO_W, mono=False)
        for label, val in opts:
            c.addItem(tr(label), val)
        if typed is not None:
            c.setEditText(chip.text)
        swap_combo(chip, c)
        self._open = (c, chip, choose, typed)

        def picked(i):
            self._open = None
            choose(c.itemData(i))
            self._drop(c, chip)

        def edited():
            if self._open and self._open[0] is c:
                self._close_open(apply=True)

        c.activated.connect(picked)
        if typed is not None:
            c.lineEdit().editingFinished.connect(edited)
            c.lineEdit().selectAll()
        open_popup(c, chip, cancel=lambda: self._open and self._open[0] is c and self._close_open(apply=False))

    @staticmethod
    def _drop(c, chip):
        c.hide()
        c.deleteLater()
        chip.show()

    def _close_open(self, apply):
        if not self._open:
            return
        c, chip, choose, typed = self._open
        self._open = None
        try:
            text = c.currentText().strip()
            if apply and typed is not None and text and text != chip.text:
                val = typed(text)
                if val is not None:
                    choose(val)
                else:
                    self.app.say("这里要填一个数（或 ×倍数）。", "warn")
            self._drop(c, chip)
        except RuntimeError:
            pass

    # ================================================================ 改动
    def _reset_sel(self):
        if self.sel == ALL:
            self.common = {}
        else:
            self.ov.pop(self.sel, None)
        self._changed()
        self._refresh()

    def _changed(self):
        self.dirty = True
        self._mark_buttons()
