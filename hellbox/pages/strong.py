"""
选图页「变强」格子（2026-11-25 用户定；2026-11-27 标题改「我独自升级」）：放在「存档」下面，只在单人打报复关时生效，其他地图不生效
（这一局出现过第二个人、或者扔了救援信标，这一局就不再管；见 mod/src/hellbox_strong.lua）。
  - 从第几波开始：1 = 原版。杀怪数照常从 0 开始数（用户定）。
  - 复活币：最后一条命也死了不判失败，清怪、场上的东西全部清（地上的枪、背包、弹药、补给舱，放下的炮塔、地雷、载具等；
    2026-11-26 用户改，11-25 原来是炮塔、地雷、载具不清）、取消没落地的信标，杀怪数归 0、战备补满、原地复活，
    怪停 15 秒后从上面这一波重新开始。
设置存在选图设置的 "strong" 里（ai/drill_spec.py），开始时随进关请求带进游戏（training.strong_lines → mod/src/hellbox_strong.lua）。
「这一波能抽到什么」从 ai/spawn_tables.json 的报复关表算（tools/spawn_tables.py 从游戏设置文件生成）。
"""
import json
import os

from PySide6.QtCore import Qt

import ui
import drill_spec as ds
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

TABLES = os.path.join(os.path.dirname(os.path.abspath(ds.__file__)), "spawn_tables.json")
VC = Qt.AlignmentFlag.AlignVCenter
_TABLES = None


def _genocide(race):
    global _TABLES
    if _TABLES is None:
        try:
            with open(TABLES, encoding="utf-8") as f:
                _TABLES = json.load(f).get("races", {})
        except (OSError, ValueError):
            _TABLES = {}
    return (_TABLES.get(race) or {}).get("genocide") or []


def _names(groups):
    out = []
    for g in groups:
        for _path, _n, zh in g.get("units") or []:
            if zh not in out:
                out.append(zh)
    return out


def wave_points(difficulty, wave, players=1):
    """【源码】报复关每波点数：难度 × 2 + 波数 × 4 × (人数 / 2)（lua_src unknown_a79edb928a191fd5.lua calculate_wave_points）。"""
    return difficulty * 2 + wave * 4 * (players / 2)


def hint(seed, wave):
    """这一关从第 wave 波开始时，一句话说清能抽到什么、再往后几波会加什么。"""
    d = ds.decode(seed)
    if d["mission"] != ds.GENOCIDE:
        return tr("只对报复关有效，现在选的不是报复关。")
    diff = d["difficulty"]
    fits = [g for g in _genocide(ds.race_key(seed)) if (g.get("min") or 0) <= diff <= (g.get("max") or 99)]
    now = _names([g for g in fits if (g.get("wave_start") or 1) <= wave])
    later = sorted({g.get("wave_start") or 1 for g in fits if (g.get("wave_start") or 1) > wave})
    text = T("第 {0} 波：每波 {1:g} 点（一个人）。能抽到：{2}。", wave, wave_points(diff, wave),
             tr("、").join(tr(n) for n in now) or tr("（没有）"))
    if later:
        nxt = later[0]
        new = [n for n in _names([g for g in fits if (g.get("wave_start") or 1) == nxt]) if n not in now]
        if new:
            text += T("第 {0} 波起再加：{1}。", nxt, tr("、").join(tr(n) for n in new))
    return text


class StrongCard:
    """view：放卡片的页面视图；cfg：选图设置（读 seed 和 strong）；on_change：改了以后调（选图页存设置）。"""

    def __init__(self, view, cfg, on_change):
        self.on_change = on_change
        sg = cfg.get("strong") or {}
        self.v_wave = ui.Var(str(sg.get("wave") or 1))
        self.v_revive = ui.Var(bool(sg.get("revive")))
        self.seed = cfg["seed"]

        card = ui.Card(view, "STRONGER", "我独自升级", fill=ui.SALMON)
        self.card = card
        card.add(ui.text(None, tr("只在单人报复地图生效，其他地图不生效。"), muted=True, size=9))

        w, lay = ui.hbox()
        lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(ui.Label(tr("从第几波开始"), font=ui.f_zh(10, True), fg=ui.MUTED), 0, VC)
        lay.addSpacing(10)
        self.st_wave = ui.Stepper(None, self.v_wave, 1, 99, command=self._changed, width=3)
        lay.addWidget(self.st_wave, 0, VC)
        lay.addSpacing(6)
        lay.addWidget(ui.Label(tr("（1 = 原版；杀怪数还是从 0 开始数）"), font=ui.f_zh(9), fg=ui.MUTED), 0, VC)
        card.add(w, top=10)
        self.wave_hint = ui.text(None, "", size=9)
        card.add(self.wave_hint, top=6)

        w, lay = ui.hbox()
        lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(ui.Label(tr("复活币"), font=ui.f_zh(10, True), fg=ui.MUTED), 0, VC)
        lay.addSpacing(10)
        lay.addWidget(ui.Toggle(None, self.v_revive, command=self._changed), 0, VC)
        card.add(w, top=12)
        card.add(ui.text(None, tr("最后一条命也死了时不算失败：场上的怪、地上的东西（枪、背包、弹药、补给舱）、放下的炮塔、地雷、载具等全部清掉，"
                                  "还没落下来的信标取消，杀怪数归 0、战备补满、原地复活，怪停 15 秒后从上面这一波重新开始。"),
                         muted=True, size=9), top=6)
        self.refresh(self.seed)

    def value(self):
        return {"wave": self.st_wave.value(), "revive": bool(self.v_revive.get())}

    def load(self, cfg):
        sg = cfg.get("strong") or {}
        for var, val in ((self.v_wave, str(sg.get("wave") or 1)), (self.v_revive, bool(sg.get("revive")))):
            if var.get() != val:
                var.set(val)
        self.refresh(cfg["seed"])

    def refresh(self, seed):
        self.seed = seed
        self.wave_hint.config(text=hint(seed, self.st_wave.value()))

    def _changed(self):
        self.refresh(self.seed)
        self.on_change()
