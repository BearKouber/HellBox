"""武器属性块的编辑器（2026-11-14 V0.91，数据修改页里的编辑卡片，接口同 EnemyEditor）。

每把武器列哪些参数、书面名称、选项方式、原版值来自 ai/weapon_fields.json（tools/weapon_fields.py 生成，
HD1-033 武器属性清单：只列游戏代码实际会读的参数）。游戏这边是 mod/src/weapon_params.lua。
选项方式同怪物属性：
  倍率 mult      ×0～×100（原版值为 0 的给具体数值档）；散布按度显示
  秒数 time      0、0.1、0.25、0.5、1、2、3、5、10、30 秒
  数量 count     0～10、15、20、30
  是否 bool / 角度 angle（电弧扇区）
数值那一格平时是一块小方块，点到才变成下拉框（同怪物属性）。
块的数据：{"common": {组: 倍数}, "ov": {单位短名: {路径: 值}}}；值 '*2' = 按原值乘，其它 = 绝对值（数 / true / false）。
单位短名是武器（wep_*）或它打出去的弹头 / 炸药包（equipment_impact_grenade_02 等），和 Lua 那边的 KEYS 一致。
"""
import copy
import math
import os

from PySide6.QtCore import Qt

import paths
import ui
from pages.edit_util import (NUMERIC_KINDS, ParamList, PickGrid, ValueSlider, eff_key, is_num, load_json, num,
                             small_button, styled_combo, swap_combo, open_popup, COMBO_W)
from pages.enemy_editor import COUNTS, MULTS, TIMES, ValueChip
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

FIELDS = os.path.join(paths.ROOT, "ai", "weapon_fields.json")
VC = Qt.AlignmentFlag.AlignVCenter
LEFT_VC = Qt.AlignmentFlag.AlignLeft | VC
ALL = "__all__"
ANGLES = [15, 30, 45, 60, 90, 120]
KIND_TIP = {
    "mult": "按原版数值的倍数修改（×0～×100）；也可直接输入数值，输入 ×3 表示 3 倍。",
    "zero": "原版数值为 0，按具体数值设定；可直接输入数值。",
    "time": "单位：秒。可直接输入秒数。",
    "count": "数量。可直接输入整数。",
    "bool": "是 / 否。",
    "angle": "单位：度。可直接输入角度。",
}

_DATA = None


def fields():
    """ai/weapon_fields.json（读一次）。"""
    global _DATA
    if _DATA is None:
        _DATA = load_json(FIELDS, {}) or {}
        idx = {}
        for short in _DATA.get("order") or []:
            for b in (_DATA.get("weapons") or {}).get(short, {}).get("blocks") or []:
                for r in b["rows"]:
                    idx.setdefault((r["unit"], r["path"]), r)
        _DATA["_index"] = idx
    return _DATA


def _fix(row, v):
    """和 Lua 那边一样：取整、下限。"""
    if row.get("int"):
        v = math.floor(v + 0.5)
    if row.get("min") is not None and v < row["min"]:
        v = row["min"]
    return v


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------------------------------------------------------------- 块 -> 命令（给 data_blocks 用）
def weapon_command(data):
    """武器属性块 -> weapon_params.lua 的命令。「全部武器」的组在这里展开成每把武器的倍率
    （发射器的发射力度之类不该跟着变的行，清单里没标组就不会被带上）；单把设了的那一项以单把为准。
    设置里本来没有、按代码缺省值显示的行，倍率换算成绝对值发过去（游戏那边没有原值可乘）。"""
    data = data or {}
    meta = fields()
    idx = meta.get("_index") or {}
    ov = data.get("ov") or {}
    out = {}

    def emit(unit, path, val):
        row = idx.get((unit, path))
        val = str(val)
        if val.startswith("*") and row and row.get("default") and _is_num(row.get("value")):
            v = _fix(row, row["value"] * float(val[1:]))
            out[(unit, path)] = f"{unit}.{path}={v:g}"
        elif val.startswith("*"):
            out[(unit, path)] = f"{unit}.{path}*{float(val[1:]):g}"
        else:
            out[(unit, path)] = f"{unit}.{path}={val}"

    for unit, f in ov.items():
        for path, val in (f or {}).items():
            emit(unit, path, val)
    groups = {g: float(m) for g, m in (data.get("common") or {}).items() if abs(float(m) - 1.0) > 1e-9}
    if groups:
        for (unit, path), row in idx.items():
            g = row.get("common")
            if g in groups and (unit, path) not in out and path not in (ov.get(unit) or {}):
                emit(unit, path, f"*{groups[g]:g}")
    if not out:
        return "reset"
    return "common=;set=" + ",".join(out[k] for k in sorted(out))


def summary(data):
    data = data or {}
    meta = fields()
    n_common = len([m for m in (data.get("common") or {}).values() if abs(float(m) - 1.0) > 1e-9])
    ov = {u: f for u, f in (data.get("ov") or {}).items() if f}
    owners = set()
    for short, w in (meta.get("weapons") or {}).items():
        units = {r["unit"] for b in w.get("blocks") or [] for r in b["rows"]}
        if units & set(ov):
            owners.add(short)
    parts = []
    if n_common:
        parts.append(f"全部武器 {n_common} 项")
    if owners:
        parts.append(f"{len(owners)} 把武器 {sum(len(f) for f in ov.values())} 项")
    return "，".join(parts) or "全原版"


def _upgrade_text(items):
    """「扩展弹匣：325」这样的升级说明逐段翻（英文版升级名、是 / 否、标点都换成英文）。"""
    try:
        from i18n import is_en
        en = is_en()
    except ImportError:
        en = False
    out = []
    for s in items:
        name, sep, val = str(s).partition("：")
        out.append(tr(name) + (((": " if en else "：") + tr(val)) if sep else ""))
    return ("; " if en else "；").join(out)


# ---------------------------------------------------------------- 编辑器
class WeaponEditor:
    def __init__(self, app, view):
        self.app, self.view = app, view
        meta = fields()
        self.weapons = meta.get("weapons") or {}
        self.order = [s for s in meta.get("order") or [] if s in self.weapons]
        self.groups = [tuple(g) for g in meta.get("groups") or []] or [("primary", "主武器")]
        self.common_groups = meta.get("common") or []
        self.group = self.groups[0][0]
        self.weapon = ALL
        self.common = {}
        self.ov = {}
        self.dirty = False
        self._open = None  # 正在下拉的那一格 (combo, chip, choose, typed)

        # 2026-11-15 新界面：选武器 = 平的等宽格子（绿方块 = 改过），参数 = 一行一项、说明进底栏
        pick = ui.Card(view, "PICK", "选武器", fill=ui.YELLOW, note="绿色方块 = 改过")
        self.v_group = ui.Var(self.group)
        self.seg_group = ui.Segmented(None, self.groups, self.v_group, command=self._group_changed,
                                      padx=12, pady=3, shadow=2, font=ui.f_zh(10, True))
        pick.add(ui.line(self.seg_group), top=2)
        self.picker = PickGrid(self._select)
        pick.add(self.picker, top=10)

        self.card = ui.Card(view, "EDIT", "", fill=ui.SALMON, note=" ")
        self.btn_reset = small_button("全部还原", self._reset_weapon)
        self.card.head_lay.addSpacing(10)
        self.card.head_lay.addWidget(self.btn_reset, 0, VC)
        self.notes = self.card.add(ui.text(self.card.body, "", muted=True, size=9))
        self.body_w, self.body_lay = ui.vbox(spacing=0)
        self.card.add(self.body_w, top=6)

        self.rows = [view.row(pick), view.row(self.card)]
        self._refresh()

    # ================================================================ 块的读写
    def load(self, data, race=None):  # race 没用，和 EnemyEditor 接口一致
        data = data or {}
        self.common = {g: float(m) for g, m in (data.get("common") or {}).items()}
        self.ov = copy.deepcopy(data.get("ov") or {})
        self.weapon = ALL
        self.dirty = False
        self._refresh()

    def dump(self):
        return {"common": {g: m for g, m in self.common.items() if abs(m - 1.0) > 1e-9},
                "ov": {u: dict(f) for u, f in self.ov.items() if f}}

    def set_visible(self, on):
        for r in self.rows:
            r.setVisible(on)

    # ================================================================ 选武器
    def _group_changed(self, group):
        self.group = group
        self.weapon = ALL
        self._refresh()

    def _select(self, short):
        self.weapon = short
        self._refresh()

    def _units(self, short):
        return {r["unit"] for b in self.weapons[short].get("blocks") or [] for r in b["rows"]}

    def _changed_weapon(self, short):
        return any(self.ov.get(u) for u in self._units(short))

    def _pick_items(self):
        items = [(ALL, "全部武器", bool(self.common),
                  "全部武器（主武器、副武器、支援武器一起）：按每把武器自己的原版数值乘；单把武器设了的那一项以单把为准。"
                  "倍率按装上升级后的数值乘。")]
        items += [(s, self.weapons[s]["zh"], self._changed_weapon(s),
                   "\n".join(self.weapons[s].get("notes") or []) or "点开改这把武器的参数。")
                  for s in self.order if self.weapons[s].get("group") == self.group]
        return items

    def _refresh(self):
        self._close_open(apply=False)
        ui.clear_layout(self.body_lay)
        self.plist = ParamList(self.body_lay, ui.SALMON)
        if self.weapon == ALL:
            self._build_common()
        else:
            self._build_weapon(self.weapon)
        self.notes.setVisible(bool(self.notes.text()))
        self._mark()

    # ================================================================ 全部武器
    def _build_common(self):
        self.card.title_lab.config(text="全部武器")
        self.card.note_lab.config(text="主武器、副武器、支援武器一起，按每把自己的原版数值乘")
        self.notes.config(text="")
        for g in self.common_groups:
            key, label = g["key"], g["label"]
            m = self.common.get(key, 1.0)
            chip = ValueSlider("×1（原版）" if abs(m - 1) < 1e-9 else f"×{m:g}", abs(m - 1) > 1e-9)
            self._setup_common(chip, key)  # 2026-11-15 下拉换成滑条
            self.plist.row(label, chip, help=" ".join(t for t in (tr(g.get("tip", "")), tr(KIND_TIP["mult"])) if t))

    def _setup_common(self, chip, key):
        def choose(val):
            if val is None:
                self.common.pop(key, None)
            else:
                self.common[key] = float(val)
            self._changed()
            m = self.common.get(key, 1.0)
            chip.set_text("×1（原版）" if abs(m - 1) < 1e-9 else f"×{m:g}", abs(m - 1) > 1e-9)

        opts = [("×1（原版）", None)] + [(f"×{m:g}", m) for m in MULTS]

        def typed(text):
            v = self._num(text.lstrip("×xX*"))
            return None if v is None else min(100.0, max(0.0, v))

        chip.setup(opts, choose, typed, key=lambda v: 1.0 if v is None else float(v), cur=self.common.get(key, 1.0))

    # ================================================================ 单把武器
    def _build_weapon(self, short):
        w = self.weapons[short]
        self.card.title_lab.config(text=w["zh"])
        self.card.note_lab.config(text=dict(self.groups).get(w.get("group"), ""))
        self.notes.config(text="\n".join(w.get("notes") or []))
        for block in w.get("blocks") or []:
            self.plist.section(block["title"])
            for row in block["rows"]:
                kind = self._kind(row)
                tip = [tr(row.get("tip", "")), T("原版：{0}", self._show(row, row["value"])) + "。"]
                if row.get("default"):
                    tip.append(tr("（设置里没写，这是游戏代码的缺省值）"))
                if row.get("upgrades"):
                    tip.append(tr("升级后：") + _upgrade_text(row["upgrades"]) + "。")
                tip.append(tr(KIND_TIP[kind]))
                text, changed = self._current(row)
                orig = T("原版 {0}", self._show(row, row["value"]))
                if row.get("upgrades"):
                    orig += tr("（有升级）")
                self.plist.row(row["label"], self._value_widget(row, kind, text, changed, None, None), orig,
                               help=" ".join(t for t in tip if t))

    def _kind(self, row):
        if row["kind"] == "mult" and _is_num(row["value"]) and row["value"] == 0:
            return "zero"
        return row["kind"]

    # ---------------------------------------------------------------- 显示
    def _show(self, row, v):
        kind = row["kind"]
        if isinstance(v, bool):
            return tr("是" if v else "否")
        if not _is_num(v):
            return str(v)
        if kind == "angle":
            return f"{math.degrees(v) if row.get('scale') == 'rad' else v:.0f}°"
        if kind == "time":
            return T("{0} 秒", f"{v:g}")
        if kind == "count" or row.get("int"):
            return str(int(round(v)))
        if row.get("scale") == "rad":
            return f"{math.degrees(v):.3g}°"
        if row.get("scale") == "deg":
            return f"{v:.3g}°"
        return num(v)

    def _current(self, row):
        own = (self.ov.get(row["unit"]) or {}).get(row["path"])
        base = row["value"]
        if own is not None:
            own = str(own)
            if own.startswith("*"):
                m = float(own[1:])
                shown = self._show(row, _fix(row, base * m)) if _is_num(base) else "?"
                return f"×{m:g} = {shown}", True
            return self._show(row, self._parse(own)), True
        m = self.common.get(row.get("common"))
        if m is not None and _is_num(base):
            return T("跟全部武器 ×{0:g} = {1}", m, self._show(row, _fix(row, base * m))), True
        return tr("原版"), False  # 2026-11-15 新界面：原版的数在这一行最右边

    @staticmethod
    def _parse(text):
        if text == "true":
            return True
        if text == "false":
            return False
        try:
            return float(text)
        except ValueError:
            return text

    @staticmethod
    def _num(text):
        try:
            v = float(str(text).strip())
        except ValueError:
            return None
        return v if math.isfinite(v) else None

    # ---------------------------------------------------------------- 下拉的选项
    def _store(self, row, v):
        """给人看的数（度 / 秒 / 个）-> 存的文字（设置里的单位）。"""
        if row.get("scale") == "rad":
            v = math.radians(v)
        v = _fix(row, max(0.0, v))
        return f"{v:.6g}"

    def _options(self, row, kind):
        base = row["value"]
        orig = (T("原版（{0}）", self._show(row, base)), None)

        def as_shown(t):
            return self._num(str(t).replace("秒", "").replace("°", "").replace("个", "").strip().rstrip("sS").strip())  # 英文版显示「5s」

        if kind == "mult":
            opts = [orig] + [(f"×{m:g} = {self._show(row, _fix(row, base * m))}", f"*{m:g}") for m in MULTS]

            def typed(text):
                text = text.strip()
                if text[:1] in "×xX*":
                    v = self._num(text[1:])
                    return None if v is None else f"*{min(100.0, max(0.0, v)):g}"
                v = as_shown(text)
                if v is None:
                    return None
                return self._store(row, v)
            return opts, typed
        if kind == "zero":
            vals = row.get("zero") or [0.5, 1, 2, 5, 10]
            shown = [(self._show(row, math.radians(v) if row.get("scale") == "rad" else v),
                      self._store(row, v)) for v in vals]
            opts = [orig] + shown
            return opts, lambda t: None if as_shown(t) is None else self._store(row, as_shown(t))
        if kind == "time":
            opts = [orig] + [(T("{0} 秒", f"{v:g}"), f"{v:g}") for v in TIMES]
            return opts, lambda t: None if as_shown(t) is None else f"{max(0.0, as_shown(t)):g}"
        if kind == "count":
            opts = [orig] + [(str(v), str(v)) for v in COUNTS if row.get("min") is None or v >= row["min"]]
            return opts, lambda t: None if as_shown(t) is None else str(int(_fix(row, max(0.0, as_shown(t)))))
        if kind == "angle":
            rad = row.get("scale") == "rad"

            def store(deg):
                return f"{math.radians(deg):.6g}" if rad else f"{deg:g}"
            opts = [orig] + [(f"{a}°", store(a)) for a in ANGLES]
            return opts, lambda t: None if as_shown(t) is None else store(max(0.0, min(360.0, as_shown(t))))
        if kind == "bool":
            return [(tr("是" if v else "否") + (tr("（原版）") if v == base else ""),
                     None if v == base else ("true" if v else "false")) for v in (True, False)], None
        return [orig], None

    # ---------------------------------------------------------------- 点开 / 选好
    def _value_widget(self, row, kind, text, changed, grid, r):
        """数值类：滑条（2026-11-15 用户要求）；是否这种：点了变下拉框的小方块。"""
        base = row["value"]
        if kind in NUMERIC_KINDS and is_num(base):
            w = ValueSlider(text, changed)
            opts, choose, typed = self._row_handlers(w, row)
            key = eff_key(base)
            own = (self.ov.get(row["unit"]) or {}).get(row["path"])
            m = self.common.get(row.get("common"))
            try:
                cur = key(own) if own is not None else (base * m if m is not None else base)
            except (TypeError, ValueError):
                cur = base
            if w.setup(opts, choose, typed, key, cur):
                return w
        w = ValueChip(text, None, changed)
        w.command = lambda c=w: self._open_row(c, row, grid, r)
        return w

    def _open_row(self, chip, row, grid, r):
        self._open_combo(chip, grid, r, *self._row_handlers(chip, row))

    def _row_handlers(self, chip, row):
        opts, typed = self._options(row, self._kind(row))

        def choose(val):
            f = self.ov.setdefault(row["unit"], {})
            if val is None:
                f.pop(row["path"], None)
            else:
                f[row["path"]] = val
            if not f:
                self.ov.pop(row["unit"], None)
            self._changed()
            chip.set_text(*self._current(row))

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

    def _drop(self, c, chip):
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
                    self.app.say("这里要填一个数。", "warn")
            self._drop(c, chip)
        except RuntimeError:
            pass

    # ================================================================ 改动
    def _reset_weapon(self):
        if self.weapon == ALL:
            self.common = {}
        else:
            for u in self._units(self.weapon):
                self.ov.pop(u, None)
        self._changed()
        self._refresh()

    def _changed(self):
        self.dirty = True
        self._mark()

    def _mark(self):
        """选武器格子上的绿方块、「全部还原」能不能点。"""
        self.picker.set_items(self._pick_items(), self.weapon)
        self.btn_reset.set_enabled(bool(self.common) if self.weapon == ALL else self._changed_weapon(self.weapon))
