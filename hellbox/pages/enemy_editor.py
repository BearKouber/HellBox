"""
怪物属性块的编辑器：每只怪列哪些参数、名称与选项方式来自 ai/enemy_fields.json，原版数值来自 ai/enemy_settings.json。
"""
import copy
import math
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGridLayout

import paths
import ui
from pages import enemy_zh as zh
from pages.edit_util import (NUMERIC_KINDS, ParamList, PickGrid, ValueSlider, eff_key, get_path, is_num, load_json,
                             num, small_button, styled_combo, swap_combo, open_popup, COMBO_W)
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

AI = os.path.join(paths.ROOT, "ai")
FIELDS = os.path.join(AI, "enemy_fields.json")
SETTINGS = os.path.join(AI, "enemy_settings.json")
VC = Qt.AlignmentFlag.AlignVCenter
LEFT_VC = Qt.AlignmentFlag.AlignLeft | VC

RACE_ZH = {"bugs": "虫族", "cyborgs": "生化人", "illuminates": "光能者"}
ALL = "__all__"
MULTS = [0, 0.25, 0.5, 0.75, 1.25, 1.5, 2, 3, 5, 10, 20, 50, 100]
ANGLES = [30, 60, 90, 180, 270, 360]
ELEVS = [15, 30, 45, 60, 75]
TIMES = [0, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 30]
COUNTS = list(range(0, 11)) + [15, 20, 30]
ZERO_DIST = [0.5, 1, 2, 5, 10, 20]
ZERO_PLAIN = [0.5, 1, 2, 5, 10, 50, 100]

COMMON = [
    ("health_info.health", "生命值"),
    ("health_info.armor_max", "正面装甲"),
    ("health_info.armor_min", "背面装甲"),
    ("enemy_info.movement_speed", "移动速度（米/秒）"),
    ("enemy_info.turn_speed", "转向速度"),
    ("enemy_info.aggro_range", "索敌距离（米）"),
    ("enemy_info.attack_range", "攻击距离（米）"),
    ("weapon_info.range", "武器射程（米）"),
    ("melee_info.power", "近战伤害"),
    ("weapon_info.power", "武器伤害"),
    ("weapon_info.firerate", "射速（发/秒）"),
]
COMMON_NAME = dict(COMMON)

IMMUNE = [
    ("elements", "poison", "毒素", "免疫毒素类效果（中毒掉血、中毒减速）。"),
    ("elements", "fire", "火焰", "免疫火焰引燃。"),
    ("elements", "lightning", "电击", "免疫电击类效果（电击减速、电击定身）。"),
    ("elements", "generic_stun", "闪光 / 震荡", "免疫闪光、震荡及子弹硬直造成的眩晕与减速。"),
    ("elements", "psychic", "精神干扰", "免疫精神干扰（操作混乱、移动反向）。"),
    ("elements", "environment", "地形减速", "免疫水体、雪地等地形造成的减速。"),
    ("statuses", "slow", "减速", "免疫任何来源的减速。"),
    ("statuses", "stun", "眩晕", "免疫任何来源的眩晕。"),
    ("statuses", "burn", "燃烧", "免疫任何来源的燃烧。"),
    ("statuses", "damage", "持续伤害", "免疫中毒、铁丝网等持续伤害。"),
]

KIND_TIP = {
    "mult": "按原版数值的倍数修改（×0～×100）；也可直接输入数值，输入 ×3 表示 3 倍。",
    "zero": "原版数值为 0，按具体数值设定；可直接输入数值。",
    "angle": "单位：度。可直接输入角度。",
    "elev": "投掷仰角，单位：度。可直接输入角度。",
    "time": "单位：秒。可直接输入秒数。",
    "count": "数量。可直接输入整数。",
    "bool": "是 / 否。",
    "unit": "从列表中选择。",
    "status": "从列表中选择。",
    "text": "暂不开放修改。",
}


def same_race(name, path):
    if not name or not path.startswith("characters/"):
        return True
    return name.split("_", 1)[0] == path[len("characters/"):].split("_", 1)[0]


def parse_raw(text):
    if text == "true":
        return True
    if text == "false":
        return False
    try:
        return float(text)
    except (TypeError, ValueError):
        return text


class ValueChip(ui.Clickable):

    def __init__(self, text, command, changed=False):
        super().__init__()
        self.command, self.changed = command, changed
        self.setFont(ui.f_zh(9, changed))
        self.set_text(text)

    def set_text(self, text, changed=None):
        self.text = tr(text)
        if changed is not None:
            self.changed = changed
            self.setFont(ui.f_zh(9, changed))
        fm = self.fontMetrics()
        self.setFixedSize(max(150, fm.horizontalAdvance(self.text) + 34), fm.height() + 12)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        fill = ui.YELLOW_HOVER if self.changed else (ui.PLAIN_HOVER if self.hovered else ui.WHITE)
        if not self.enabled:
            fill = ui.DISABLED
        r = ui.paint_box(p, self.width(), self.height(), fill, 2, 2)
        p.setFont(self.font())
        p.setPen(ui.qc(ui.INK if self.enabled else ui.MUTED))
        p.drawText(r.adjusted(8, 0, -16, 0), Qt.AlignmentFlag.AlignLeft | VC, self.text)
        cx, cy = r.right() - 9, r.center().y()
        for i in range(3):
            p.fillRect(cx - 3 + i, cy - 1 + i, 7 - 2 * i, 1, ui.qc(ui.MUTED))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.enabled and self.rect().contains(e.position().toPoint()):
            self.command()


class EnemyEditor:
    def __init__(self, app, view):
        self.app, self.view = app, view
        self.fields = load_json(FIELDS, {}).get("units") or {}
        races = load_json(SETTINGS, {"races": {}}).get("races") or {}
        self.units = {}
        self.settings = {}
        self.path_zh = dict(zh.THING_ZH)
        self.unit_paths = []
        for race, r in races.items():
            for u in r.get("units") or []:
                self.settings[u["name"]] = u.get("settings") or {}
                if u.get("path"):
                    p = "characters/" + u["path"]
                    self.path_zh[p] = (self.fields.get(u["name"]) or {}).get("zh") or u.get("zh") or u["name"]
                    self.unit_paths.append(p)
        for race in RACE_ZH:
            names = [n for n, f in self.fields.items()
                     if f.get("race") == RACE_ZH[race] and n in self.settings]
            self.units[race] = names
        self.race = "bugs"
        self.enemy = ALL
        self.common = {}
        self.ov = {}
        self.dirty = False
        self._open = None

        pick = ui.Card(view, "PICK", "选怪", fill=ui.YELLOW)
        self.v_race = ui.Var(self.race)
        self.seg_race = ui.Segmented(None, list(RACE_ZH.items()), self.v_race, command=self._race_changed,
                                     padx=12, pady=3, shadow=2, font=ui.f_zh(10, True))
        pick.add(ui.line(self.seg_race), top=2)
        self.picker = PickGrid(self._select)
        pick.add(self.picker, top=10)

        self.card = ui.Card(view, "EDIT", "", fill=ui.SALMON)
        self.btn_reset = small_button("还原", self._reset_unit)
        self.card.head_lay.addSpacing(10)
        self.card.head_lay.addWidget(self.btn_reset, 0, VC)
        self.notes = self.card.add(ui.text(self.card.body, "", muted=True, size=9))
        self.body_w, self.body_lay = ui.vbox(spacing=0)
        self.card.add(self.body_w, top=6)

        self.rows = [view.row(pick), view.row(self.card)]
        self._refresh()

    def load(self, data, race=None):
        data = data or {}
        self.common = {p: float(m) for p, m in (data.get("common") or {}).items()}
        self.ov = copy.deepcopy(data.get("ov") or {})
        if race in RACE_ZH:
            self.race = race
            self.v_race.set(race)
        self.enemy = ALL
        self.dirty = False
        self._refresh()

    def dump(self):
        return {"common": {p: m for p, m in self.common.items() if abs(m - 1.0) > 1e-9},
                "ov": {n: dict(f) for n, f in self.ov.items() if f}}

    def set_visible(self, on):
        for r in self.rows:
            r.setVisible(on)

    def _race_changed(self, race):
        self.race = race
        self.enemy = ALL
        self._refresh()

    def _select(self, name):
        self.enemy = name
        self._refresh()

    def _zh(self, name):
        f = self.fields.get(name) or {}
        return (f.get("zh") or name) + ("（首领战）" if f.get("boss") else "")

    def _pick_items(self):
        items = [(ALL, "所有怪", bool(self.common),
                  "所有怪（三个阵营一起）：按每只怪自己的原版数值乘；单只怪设了的那一项以单只为准。")]
        for n in self.units.get(self.race, []):
            notes = (self.fields.get(n) or {}).get("notes") or []
            items.append((n, self._zh(n), bool(self.ov.get(n)), "\n".join(notes) or "点击展开以修改这只怪的参数。"))
        return items

    def _refresh(self):
        self._close_open(apply=False)
        self.picker.set_items(self._pick_items(), self.enemy)
        ui.clear_layout(self.body_lay)
        self.plist = ParamList(self.body_lay, ui.SALMON)
        if self.enemy == ALL:
            self._build_common()
        else:
            self._build_unit(self.enemy)
        self.notes.setVisible(bool(self.notes.text()))
        self._mark_buttons()

    def _build_common(self):
        self.card.title_lab.config(text="所有怪")
        self.notes.config(text="")
        for path, label in COMMON:
            m = self.common.get(path, 1.0)
            chip = ValueSlider("×1（原版）" if abs(m - 1) < 1e-9 else f"×{m:g}", abs(m - 1) > 1e-9)
            self._setup_common(chip, path)
            self.plist.row(label, chip, help=tr(KIND_TIP["mult"]) + " " + tr("没有这一项的怪不受影响。"))

    def _setup_common(self, chip, path):
        def choose(val):
            if val is None:
                self.common.pop(path, None)
            else:
                self.common[path] = float(val)
            self._changed()
            m = self.common.get(path, 1.0)
            chip.set_text("×1（原版）" if abs(m - 1) < 1e-9 else f"×{m:g}", abs(m - 1) > 1e-9)

        opts = [("×1（原版）", None)] + [(f"×{m:g}", m) for m in MULTS]

        def typed(text):
            v = self._num(text.lstrip("×xX*"))
            return None if v is None else min(100.0, max(0.0, v))

        chip.setup(opts, choose, typed, key=lambda v: 1.0 if v is None else float(v), cur=self.common.get(path, 1.0))

    def _build_unit(self, name):
        f = self.fields.get(name) or {}
        settings = self.settings.get(name) or {}
        self.card.title_lab.config(text=self._zh(name))
        self.notes.config(text="\n".join(f.get("notes") or []))
        for block in f.get("blocks") or []:
            self.plist.section(block["title"])
            for row in block["rows"]:
                base = get_path(settings, row["path"])
                if base is None:
                    base = row.get("value")
                kind = self._kind(row, base)
                text, changed = self._current(name, row, base)
                if kind == "text":
                    w = ui.Label(text + tr("（暂不开放）"), font=ui.f_zh(9), fg=ui.MUTED)
                else:
                    w = self._value_widget(name, row, base, kind, text, changed, None, None)
                tip = T("原版：{0}", self._show(row, base)) + "。" + tr(KIND_TIP[kind])
                if kind == "unit" and row.get("key") not in zh.SUMMON_FIELDS:
                    tip += tr("只列这个种族的（一张图只装一个种族，选别的种族会闪退）。")
                if name == "cyborg_ifv" and row.get("key") in ("spawn_unit_path", "spawn_amount"):
                    tip += tr("「出怪逻辑」的「载具 / 首领放兵」（普通模式叫「坦克屁股出兵」）选了「只出选中」或「不出」、或设了每次放几只时，以那边为准。")
                self.plist.row(row["label"], w, T("原版 {0}", self._show(row, base)), help=tip)
        self._build_immune(name, settings)

    def _value_widget(self, name, row, base, kind, text, changed, grid, r):
        if kind in NUMERIC_KINDS and is_num(base):
            w = ValueSlider(text, changed)
            opts, choose, typed = self._unit_handlers(w, name, row, base)
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
        w.command = lambda c=w: self._open_unit(c, name, row, base, grid, r)
        return w

    def _kind(self, row, base):
        kind = row["kind"]
        if kind == "mult" and isinstance(base, (int, float)) and not isinstance(base, bool) and base == 0:
            return "zero"
        return kind

    # ---------------------------------------------------------------- 显示
    def _show(self, row, v):
        kind = row["kind"]
        if isinstance(v, bool):
            return tr("是" if v else "否")
        if isinstance(v, str):
            if kind == "status":
                return tr(zh.STATUS_FX.get(v, v))
            return tr(self.path_zh.get(v, v.rsplit("/", 1)[-1]))
        if not isinstance(v, (int, float)):
            return str(v)
        if kind == "angle":
            deg = math.degrees(v) if row.get("unit") == "rad" else v
            return f"{deg:.0f}°"
        if kind == "elev":
            return f"{math.degrees(math.atan(v)):.0f}°"
        if kind == "time":
            return T("{0} 秒", f"{v:g}")
        if kind == "count":
            return str(int(round(v)))
        return num(v)

    def _current(self, name, row, base):
        own = (self.ov.get(name) or {}).get(row["path"])
        if own is not None:
            if own.startswith("*"):
                m = float(own[1:])
                shown = self._show(row, base * m) if isinstance(base, (int, float)) else "?"
                return f"×{m:g} = {shown}", True
            return self._show(row, parse_raw(own)), True
        m = self.common.get(row["path"])
        if m is not None and isinstance(base, (int, float)) and not isinstance(base, bool):
            return T("跟所有怪 ×{0:g} = {1}", m, self._show(row, base * m)), True
        return tr("原版"), False

    # ---------------------------------------------------------------- 下拉的选项
    def _options(self, row, base, kind, name=""):
        orig = (T("原版（{0}）", self._show(row, base)), None)
        if kind == "mult":
            opts = [orig] + [(f"×{m:g} = {self._show(row, base * m)}", f"*{m:g}") for m in MULTS]

            def typed(text):
                text = text.strip()
                if text[:1] in "×xX*":
                    v = self._num(text[1:])
                    return None if v is None else f"*{min(100.0, max(0.0, v)):g}"
                v = self._num(text)
                return None if v is None else f"{max(0.0, v):g}"
            return opts, typed
        if kind == "zero":
            vals = ZERO_DIST if "米" in row["label"] else ZERO_PLAIN
            if "秒" in row["label"]:
                vals = TIMES
            opts = [orig] + [(self._show(row, v), f"{v:g}") for v in vals]
            return opts, lambda t: None if self._num(t) is None else f"{max(0.0, self._num(t)):g}"
        if kind == "time":
            opts = [orig] + [(T("{0} 秒", f"{v:g}"), f"{v:g}") for v in TIMES]
            return opts, lambda t: None if self._num(t.replace("秒", "").strip().rstrip("sS")) is None else \
                f"{max(0.0, self._num(t.replace('秒', '').strip().rstrip('sS'))):g}"
        if kind == "count":
            opts = [orig] + [(str(v), str(v)) for v in COUNTS]
            return opts, lambda t: None if self._num(t) is None else str(max(0, int(self._num(t))))
        if kind == "angle":
            rad = row.get("unit") == "rad"

            def store(deg):
                return f"{math.radians(deg):.6g}" if rad else f"{deg:g}"
            opts = [orig] + [(f"{a}°", store(a)) for a in ANGLES]
            return opts, lambda t: None if self._num(t.rstrip("°")) is None else store(self._num(t.rstrip("°")))
        if kind == "elev":
            def slope(deg):
                return f"{math.tan(math.radians(max(0.0, min(85.0, deg)))):.6g}"
            opts = [orig] + [(f"{a}°", slope(a)) for a in ELEVS]
            return opts, lambda t: None if self._num(t.rstrip("°")) is None else slope(self._num(t.rstrip("°")))
        if kind == "bool":
            return [(tr("是" if v else "否") + (tr("（原版）") if v == base else ""), None if v == base else
                     ("true" if v else "false")) for v in (True, False)], None
        if kind == "status":
            return [orig] + [(label, key) for key, label in zh.STATUS_FX.items() if key != base], None
        if kind == "unit":
            key = row.get("key") or ""
            if key in zh.SUMMON_FIELDS:
                keys = [k for k in zh.THING_ZH if k.startswith("gameobjects/")]
            elif key in zh.PROJECTILE_FIELDS:
                keys = [k for k in zh.THING_ZH if k.endswith(("_grenade", "_bomb"))]
            else:
                keys = list(self.unit_paths)
                if key == "burrow_tentacle_unit_path":
                    keys = ["characters/bug_impaler/bug_impaler_tentacle"] + keys
            keys = [k for k in keys if same_race(name, k)]
            return [orig] + [(self.path_zh.get(k, k.rsplit("/", 1)[-1]), k) for k in keys if k != base], None
        return [orig], None

    @staticmethod
    def _num(text):
        try:
            v = float(str(text).strip())
        except ValueError:
            return None
        return v if math.isfinite(v) else None

    # ---------------------------------------------------------------- 点开 / 选好
    def _open_unit(self, chip, name, row, base, grid, r):
        self._open_combo(chip, grid, r, *self._unit_handlers(chip, name, row, base))

    def _unit_handlers(self, chip, name, row, base):
        kind = self._kind(row, base)
        opts, typed = self._options(row, base, kind, name)

        def choose(val):
            fields = self.ov.setdefault(name, {})
            if val is None:
                fields.pop(row["path"], None)
            else:
                fields[row["path"]] = val
            if not fields:
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

    # ---------------------------------------------------------------- 免疫
    def _build_immune(self, name, settings):
        info = settings.get("status_info") or {}
        if not info:
            return
        self.plist.section("免疫（勾上 = 不受这种效果影响）")
        for group, title in (("elements", "按来源"), ("statuses", "按效果")):
            box = ui.QWidget(None)
            g_lay = QGridLayout(box)
            g_lay.setContentsMargins(0, 0, 0, 0)
            g_lay.setHorizontalSpacing(18)
            g_lay.setVerticalSpacing(6)
            n = 0
            for g, key, label, tip in IMMUNE:
                if g != group:
                    continue
                path = f"status_info.{group}.{key}.immune"
                default = bool(get_path(settings, path))
                cur = (self.ov.get(name) or {}).get(path)
                on = (cur == "true") if cur is not None else default
                var = ui.Var(on)
                cb = ui.CheckBox(None, label, var, font=ui.f_zh(9, True), note=("已改" if on != default else None),
                                 command=lambda v=var, p=path, d=default: self._set_immune(name, p, v.get(), d))
                ui.hover_help(cb, label, tr(tip) + tr("\n原版：免疫" if default else "\n原版：不免疫").replace("\n", " "))
                g_lay.addWidget(cb, n // 3, n % 3, LEFT_VC)
                n += 1
            g_lay.setColumnStretch(3, 1)
            self.plist.row(title, box)

    def _set_immune(self, name, path, on, default):
        fields = self.ov.setdefault(name, {})
        if on == default:
            fields.pop(path, None)
        else:
            fields[path] = "true" if on else "false"
        if not fields:
            self.ov.pop(name, None)
        self._changed()

    def _reset_unit(self):
        if self.enemy == ALL:
            self.common = {}
        else:
            self.ov.pop(self.enemy, None)
        self._changed()
        self._refresh()

    def _changed(self):
        self.dirty = True
        self._mark_buttons()

    def _mark_buttons(self):
        self.picker.set_items(self._pick_items(), self.enemy)
        self.btn_reset.set_enabled(bool(self.common) if self.enemy == ALL else bool(self.ov.get(self.enemy)))
