"""
半糖 HelldiversOptimization 功能在各页上的行（开关、滑条、方块、下拉框）；设置写进 hellbox_hop.json / hop.txt，热生效。
"""
import build
import hellbox_hop as hop
import ui
from i18n import T

HALFSUGAR = "来自 半糖（HalfSugar）"


def apply_hop(app, changes):
    def action():
        hop.save(changes)
        build.write_live_options()
        if build.game_running():
            return "已生效（游戏内立即按新设置运行）。"
        if build.status() in ("on", "old"):
            return "已保存，下次进游戏生效。"
        return "已保存，打开「核心」开关时一起装。"

    app.run(action)


class HopRows:
    def __init__(self, page):
        self.page = page
        self.vars = {}
        self.widgets = []
        self.toggles = {}
        self.rows = {}

    def _var(self, key):
        if key not in self.vars:
            self.vars[key] = ui.Var(hop.load()[key])
        return self.vars[key]

    def _add(self, widget, needs):
        self.widgets.append((widget, needs))
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
        t = self.toggle_widget(key, needs)
        items = []
        for x in extras:
            items += [x, 6]
        items.append(t)
        row = card.row(title, *items, help=help_text, credit=credit, sub=note or "")
        self.rows[key] = (row, note or "")
        return row

    def plain(self, card, title, help_text, extras=(), credit=None, note=None):
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
        given = hop.yielded()
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
