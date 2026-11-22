"""潜兵块的编辑器（2026-11-15，用户要：数据里加上潜兵自己的数据、两种无敌）。

接口同别的编辑器（load / dump / set_visible / dirty）。块的数据：{"god": "off|heal|true", "common": {路径: 倍数}}。
游戏那边是 mod/src/player_params.lua：只管这台电脑控制的潜兵（你和本机 2P），联机时管不到队友。
原版数值来自游戏的潜兵设置表（lua_src/unknown_4d817700197e8ee5.lua）。
"""
from PySide6.QtCore import Qt

import ui
from pages.edit_util import ParamList, ValueSlider, small_button
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

VC = Qt.AlignmentFlag.AlignVCenter
MULTS = [0.25, 0.5, 0.75, 1.25, 1.5, 2, 3, 5, 10, 20]

GOD = [("off", "关"), ("heal", "加血无敌"), ("true", "真无敌")]
GOD_HELP = ("加血无敌：掉血马上补满、倒地马上站起来，但一下打掉太多血（重炮、自己的空袭）还是会死。"
            "真无敌：完全不掉血，掉出地图除外。只管你和本机 2P。")

# (分段, [(路径, 名字, 原版, 说明)])；路径是潜兵设置表里的，按原值乘
ROWS = [
    ("生存", [
        ("health_info.health", "生命值", 100, "血条有多长。改了已经在场的角色马上按比例变。"),
        ("health_info.health_decay", "回血速度（每秒）", 2, "不挨打时每秒回多少血。"),
        ("health_info.armor_max", "装甲", 35, "挨打时能挡掉多少伤害。高了小怪、小口径打不疼你。"),
        ("health_info.constitution", "倒地那一截血", 100,
         "血打空以后倒地，还剩这一截血慢慢掉，掉完才死；这段时间里队友能把你救起来。"),
    ]),
    ("移动", [
        ("character_info.move_speed_jog", "跑步速度（米/秒）", 4, "平时走路（跑步）多快。"),
        ("character_info.move_speed_sprint_max", "冲刺最快（米/秒）", 7, "冲刺跑起来以后的最高速度。"),
        ("character_info.move_speed_sprint_min", "冲刺起步（米/秒）", 5, "刚开始冲刺的速度。"),
        ("character_info.move_speed_aim", "瞄准时移动（米/秒）", 1.5, "举枪瞄准时走多快。"),
        ("character_info.move_speed_carry", "扛东西时移动（米/秒）", 2, "扛着箱子、样本这类东西时走多快。"),
        ("character_info.move_speed_crawl", "匍匐（米/秒）", 1.5, "趴下爬多快。"),
        ("character_info.move_speed_dive", "鱼跃速度", 10, "扑出去的速度（扑得多远）。"),
    ]),
    ("体力", [
        ("character_info.sprint_stamina", "冲刺体力（秒）", 5, "能一口气冲刺多久。"),
    ]),
]
PATHS = {p for _s, rows in ROWS for p, *_ in rows}


def player_command(data):
    """潜兵块 -> player_params.lua 的命令。"""
    data = data or {}
    god = data.get("god") if data.get("god") in ("heal", "true") else "off"
    common = ",".join(f"{p}*{float(m):g}" for p, m in sorted((data.get("common") or {}).items())
                      if p in PATHS and abs(float(m) - 1.0) > 1e-9)
    if god == "off" and not common:
        return "reset"
    return f"god={god};common={common}"


def summary(data):
    data = data or {}
    parts = []
    if data.get("god") in ("heal", "true"):
        parts.append(tr(dict(GOD)[data["god"]]))
    n = len([m for m in (data.get("common") or {}).values() if abs(float(m) - 1.0) > 1e-9])
    if n:
        parts.append(T("{0} 项", n))
    return tr("，").join(parts) or tr("全原版")


def _num(v):
    return f"{v:g}"


class PlayerEditor:
    def __init__(self, app, view):
        self.app, self.view = app, view
        self.common = {}
        self.v_god = ui.Var("off")
        self.dirty = False

        self.card = ui.Card(view, "EDIT", "绝地潜兵", fill=ui.MINT, note="你和本机 2P · 联机时只管自己")
        self.btn_reset = small_button("全部还原", self._reset)
        self.card.head_lay.addSpacing(10)
        self.card.head_lay.addWidget(self.btn_reset, 0, VC)
        self.body_w, self.body_lay = ui.vbox(spacing=0)
        self.card.add(self.body_w, top=4)
        self.rows = [view.row(self.card)]
        self._refresh()

    # ================================================================ 块的读写
    def load(self, data, race=None):
        data = data or {}
        self.common = {p: float(m) for p, m in (data.get("common") or {}).items() if p in PATHS}
        self.v_god.set(data.get("god") if data.get("god") in ("heal", "true") else "off")
        self.dirty = False
        self._refresh()

    def dump(self):
        out = {"common": {p: m for p, m in self.common.items() if abs(m - 1.0) > 1e-9}}
        if self.v_god.get() in ("heal", "true"):
            out["god"] = self.v_god.get()
        return out

    def set_visible(self, on):
        for r in self.rows:
            r.setVisible(on)

    # ================================================================ 界面
    def _refresh(self):
        ui.clear_layout(self.body_lay)
        plist = ParamList(self.body_lay, ui.MINT)
        seg = ui.Segmented(None, GOD, self.v_god, command=self._god_changed, padx=12, pady=3, shadow=2,
                           font=ui.f_zh(10, True))
        plist.row("无敌", seg, help=GOD_HELP)
        for title, rows in ROWS:
            plist.section(title)
            for path, label, orig, help_text in rows:
                m = self.common.get(path, 1.0)
                chip = ValueSlider(self._text(m, orig), abs(m - 1) > 1e-9)
                self._setup(chip, path, orig)
                plist.row(label, chip, T("原版 {0}", _num(orig)), help=help_text)
        self._mark()

    def _mark(self):
        self.btn_reset.set_enabled(bool(self.common) or self.v_god.get() != "off")

    @staticmethod
    def _text(m, orig):
        return tr("原版") if abs(m - 1) < 1e-9 else f"×{m:g} = {_num(orig * m)}"

    def _setup(self, chip, path, orig):
        def choose(val):
            if val is None:
                self.common.pop(path, None)
            else:
                self.common[path] = float(val)
            self._changed()
            m = self.common.get(path, 1.0)
            chip.set_text(self._text(m, orig), abs(m - 1) > 1e-9)

        opts = [(tr("原版"), None)] + [(f"×{m:g} = {_num(orig * m)}", m) for m in MULTS]

        def typed(text):
            try:
                v = float(text.strip().lstrip("×xX*").split("=")[0])
            except ValueError:
                return None
            return min(100.0, max(0.0, v))

        chip.setup(opts, choose, typed, key=lambda v: 1.0 if v is None else float(v), cur=self.common.get(path, 1.0))

    def _god_changed(self, _v=None):
        self._changed()

    def _changed(self):
        self.dirty = True
        self._mark()

    def _reset(self):
        self.common = {}
        self.v_god.set("off")
        self._changed()
        self._refresh()
