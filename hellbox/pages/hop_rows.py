"""收进来的半糖 HelldiversOptimization 功能（hellbox_hop.json / hop.txt）在各页上的行：开关、滑条、方块、下拉框都从这里建。

2026-11-20 HD1-035：功能本体是 HalfSugar 的 HelldiversOptimization（+ BetterHUD），全部热生效：
改了马上存、马上写 hop.txt，游戏开着的话下一秒就按新设置走。

用法（在页面 build 里）：
    self.hop = HopRows(self)
    self.hop.toggle(card, "better_hud", "增强 HUD", "说明……", credit=...)
    seg = self.hop.seg("hud_numbers", [("off", "关"), ...], needs="better_hud")
    self.hop.toggle(card, "hud_ammo", "弹匣子弹数", "……", extras=(seg,), needs="better_hud")
页面 sync 里调 self.hop.sync()。
"""
import build
import hellbox_hop as hop
import ui
from i18n import T

# 功能来源小字（2026-11-20 用户定：只写一个来源；来自工具就写工具名，半糖自己的写「来自 半糖（HalfSugar）」）
HALFSUGAR = "来自 半糖（HalfSugar）"


def apply_hop(app, changes):
    def action():
        hop.save(changes)
        build.write_live_options()
        if build.game_running():
            return "已生效（游戏里下一秒就按新设置）。"
        if build.status() in ("on", "old"):
            return "已保存，下次进游戏生效。"
        return "已保存，打开「核心」开关时一起装。"

    app.run(action)


class HopRows:
    def __init__(self, page):
        self.page = page
        self.vars = {}      # 键 -> Var
        self.widgets = []   # (控件, 依赖的开关键 或 None)
        self.toggles = {}   # 键 -> 这一行自己的开关
        self.rows = {}      # 键 -> (行, 原来的小注)：让给 Obsidian 时小注换成原因（2026-11-20 HD1-036）

    def _var(self, key):
        if key not in self.vars:
            self.vars[key] = ui.Var(hop.load()[key])
        return self.vars[key]

    def _add(self, widget, needs):
        self.widgets.append((widget, needs))  # 不进页面的 controls：可不可用全由 sync 算（还要看依赖的开关）
        return widget

    # ---- 控件
    def toggle_widget(self, key, needs=None):
        var = self._var(key)
        w = ui.Toggle(None, var, command=lambda: apply_hop(self.page.app, {key: bool(var.get())}))
        self.toggles[key] = w
        return self._add(w, needs)

    def seg(self, key, options, needs=None):
        w = ui.Segmented(None, options, self._var(key), command=lambda v: apply_hop(self.page.app, {key: v}),
                         font=ui.f_zh(9, True), padx=7, pady=2, shadow=2)
        return self._add(w, needs)

    def drop(self, key, options, needs=None, width=None):
        w = ui.Dropdown(None, options, self._var(key), command=lambda v: apply_hop(self.page.app, {key: v}),
                        width=width, font=ui.f_zh(9, True), shadow=2)
        return self._add(w, needs)

    def steps(self, key, options, needs=None, width=150):
        w = ui.StepSlider(None, options, self._var(key), command=lambda v: apply_hop(self.page.app, {key: v}),
                          width=width)
        return self._add(w, needs)

    # ---- 一行
    def toggle(self, card, key, title, help_text, extras=(), needs=None, credit=None, note=None):
        """一行：名字 ……［extras］［开关］。needs = 要另一个开关开着这行才能动（比如 HUD 子项要先开增强 HUD）。"""
        t = self.toggle_widget(key, needs)
        items = []
        for x in extras:
            items += [x, 6]
        items.append(t)
        row = card.row(title, *items, help=help_text, credit=credit, sub=note or "")
        self.rows[key] = (row, note or "")
        return row

    def plain(self, card, title, help_text, extras=(), credit=None, note=None):
        """没有自己开关的一行（只有选项），右边空出开关的位置对齐。"""
        items = []
        for x in extras:
            items += [x, 6]
        gap = ui.QWidget()
        gap.setFixedSize(73, 1)
        items.append(gap)
        return card.row(title, *items, help=help_text, credit=credit, sub=note)

    # ---- 同步
    def sync(self, live):
        cfg = hop.load()
        if not self.page.app.busy:
            for key, var in self.vars.items():
                if var.get() != cfg[key]:
                    var.set(cfg[key])
        given = hop.yielded()  # 2026-11-20 HD1-036：Obsidian 里开着同样的 MOD → 这一行让出（变灰、写原因）
        for key, (row, note) in self.rows.items():
            if row.sub is not None:
                row.sub.config(text=T("已让给 Obsidian 的 {0}", given[key]) if key in given else note)
        mine = {w: k for k, w in self.toggles.items()}
        for w, needs in self.widgets:
            ok = live and mine.get(w) not in given
            for k in ([needs] if isinstance(needs, str) else (needs or ())):
                ok = ok and bool(cfg.get(k)) and k not in given
            w.set_enabled(ok)


def numbers(lo, hi, step, unit=""):
    """滑条的档位：[(值, "值单位"), ...]"""
    try:
        from i18n import is_en
        if unit == "秒" and is_en():
            unit = " s"
    except ImportError:
        pass
    out = []
    v = lo
    while v <= hi + 1e-9:
        val = int(v) if float(v).is_integer() else round(v, 2)
        out.append((val, f"{val:g}{unit}"))
        v += step
    return out
