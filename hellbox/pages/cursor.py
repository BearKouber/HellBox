"""
指针页：调整指针颜色、不透明度和黑边，实时预览；设置只在安装或恢复时保存。
"""
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QColorDialog, QGridLayout, QWidget

import cursor_mod
import ui
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

SCALE = 2
GROUNDS = [("雪地", (232, 236, 239)), ("沙地", (181, 154, 106)), ("暗处", (40, 52, 38))]
ROWS = [("game", "瞄准"), ("game_inactive", "不瞄准"), ("menu", "菜单箭头")]


def compose(w, h, px, bg):
    px = px[:w * h]
    seen = [i for i, (_r, _g, _b, a) in enumerate(px) if a > 8]
    dx = dy = 0
    if seen:
        xs = [i % w for i in seen]
        ys = [i // w for i in seen]
        dx = (w - 1 - max(xs) - min(xs)) // 2
        dy = (h - 1 - max(ys) - min(ys)) // 2
    buf = bytearray(bytes(bg) * (w * h))
    for i, (r, g, b, a) in enumerate(px):
        if not a:
            continue
        x, y = i % w + dx, i // w + dy
        if 0 <= x < w and 0 <= y < h:
            t = a / 255.0
            j = (y * w + x) * 3
            buf[j] = round(r * t + bg[0] * (1 - t))
            buf[j + 1] = round(g * t + bg[1] * (1 - t))
            buf[j + 2] = round(b * t + bg[2] * (1 - t))
    return QImage(bytes(buf), w, h, w * 3, QImage.Format.Format_RGB888).mirrored(False, True)


class Swatch(ui.Clickable):

    def __init__(self, rgb, on_pick):
        super().__init__()
        self.S = 30
        self.setFixedSize(self.S + 6, self.S + 6)
        self.rgb = tuple(rgb)
        self.on_pick = on_pick
        self.selected = False

    def draw(self, selected):
        self.selected = selected
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        s, b = self.S, 2
        ink = ui.qc(ui.INK)
        if self.selected:
            p.fillRect(0, 0, s + 6, s + 6, ink)
            p.fillRect(b, b, s + 6 - 2 * b, s + 6 - 2 * b, ui.qc(ui.CARD))
        p.fillRect(3, 3, s, s, ink)
        p.fillRect(3 + b, 3 + b, s - 2 * b, s - 2 * b, QColor(*self.rgb))
        if self.selected:
            c = (s + 6) // 2
            p.fillRect(c - 5, c - 5, 10, 10, ink)
            p.fillRect(c - 5 + b, c - 5 + b, 10 - 2 * b, 10 - 2 * b, ui.qc(ui.WHITE))

    def mousePressEvent(self, _e):
        self.on_pick(self.rgb)


class Tile(QWidget):

    def __init__(self, bg):
        super().__init__()
        self.bg = bg
        self.pm = None
        self.setFixedSize(32 * SCALE + 4, 32 * SCALE + 4)

    def set_image(self, img):
        dpr = self.devicePixelRatioF()
        self.pm = QPixmap.fromImage(img.scaled(img.width() * SCALE, img.height() * SCALE))
        self.pm.setDevicePixelRatio(dpr)
        self.setFixedSize(int(round(self.pm.width() / dpr)) + 4, int(round(self.pm.height() / dpr)) + 4)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), ui.qc(ui.INK))
        p.fillRect(QRect(2, 2, self.width() - 4, self.height() - 4), QColor(*self.bg))
        if self.pm is not None:
            p.drawPixmap(2, 2, self.pm)


CURSOR_STATE = {"on": ("已替换", ui.GOOD), "old": ("待更新", ui.WARN), "off": ("原版", ui.MUTED),
                "unknown": ("无法识别", ui.BAD)}


class CursorPage(Page):
    key = "cursor"
    tab = "指针"
    when = "需先关闭游戏；装好后重新打开游戏生效"
    when_color = ui.MINT

    def build(self):
        cfg = cursor_mod.load()
        self.state_lab = ui.Label("", font=ui.f_zh(10, True))
        self.head_lay.addWidget(self.state_lab, 0, ui.Qt.AlignmentFlag.AlignVCenter)
        self.color = tuple(cfg["color"])
        self.opacity = ui.Var(cfg["opacity"])
        self.outline = ui.Var(cfg["outline"])
        self._pending = None

        # ---- 左：设置
        card = ui.Card(self.view, "CURSOR", "指针设置", fill=ui.MINT)
        self._label(card, "颜色")
        sw, swl = ui.hbox()
        self.swatches = []
        for _name, rgb in cursor_mod.PRESETS.items():
            s = Swatch(rgb, self.set_color)
            swl.addWidget(s)
            swl.addSpacing(4)
            self.swatches.append(s)
        self.custom = Swatch(self.color, lambda _c: self.pick_color())
        swl.addSpacing(4)
        swl.addWidget(self.custom)
        swl.addSpacing(10)
        self.btn_pick = ui.Button(None, "自选", self.pick_color, padx=10, pady=2, font=ui.f_zh(9, True))
        swl.addWidget(self.btn_pick, 0, ui.Qt.AlignmentFlag.AlignVCenter)
        swl.addStretch(1)
        card.add(sw)

        self._label(card, "不透明度")
        self.op_text = ui.Label("", font=ui.f_mono(12, True))
        self.op_text.setFixedWidth(ui.chars(self.op_text.font(), 5))
        card.add(ui.line(ui.Slider(None, self.opacity, 30, 100, command=lambda final: self.schedule(), width=250),
                         8, self.op_text))

        self._label(card, "黑边")
        w, lay = ui.hbox()
        lay.addWidget(ui.Toggle(None, self.outline, command=self.refresh), 0, ui.Qt.AlignmentFlag.AlignVCenter)
        lay.addSpacing(10)
        card.add(w)

        self.btn_install = ui.Button(None, "装到游戏里", self.install, kind="primary")
        self.btn_restore = ui.Button(None, "恢复原版", self.restore)
        card.add(ui.line(self.btn_install, 14, self.btn_restore), top=18)
        self.hint = card.add(ui.text(card.body, "", muted=True, size=9), top=10)

        # ---- 右：预览
        pv = ui.Card(self.view, "PREVIEW", "预览", fill=ui.YELLOW)
        gw = QWidget()
        grid = QGridLayout(gw)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for c, (name, _bg) in enumerate(GROUNDS):
            grid.addWidget(ui.Label(name, font=ui.f_zh(9, True), fg=ui.MUTED), 0, c + 1, ui.Qt.AlignmentFlag.AlignCenter)
        self.tiles = {}
        for r, (key, name) in enumerate(ROWS):
            lab = ui.Label(name, font=ui.f_zh(9, True), fg=ui.MUTED)
            lab.setMinimumWidth(ui._tw(lab.font(), lab.text()) + 8)
            grid.addWidget(lab, r + 1, 0,
                           ui.Qt.AlignmentFlag.AlignRight | ui.Qt.AlignmentFlag.AlignVCenter)
            for c in range(len(GROUNDS)):
                t = Tile(GROUNDS[c][1])
                grid.addWidget(t, r + 1, c + 1)
                self.tiles[(key, c)] = t
        pv.add(gw, align=ui.CENTER)
        self.pv_note = pv.add(ui.text(pv.body, "", muted=True, size=9), top=10)

        self.view.row(card, pv, weights=(5, 4))
        self.update_labels()
        self.app.bg(cursor_mod.load_textures, self._loaded)

    def _label(self, card, s):
        card.add(ui.Label(s, font=ui.f_zh(10, True)), top=10 if card.blay.count() else 0)
        card.blay.addSpacing(4)

    # ---- 设置
    def current(self):
        cfg = cursor_mod.load()
        cfg.update(color=list(self.color), opacity=int(self.opacity.get()),
                   outline=bool(self.outline.get()))
        return cfg

    def set_color(self, rgb):
        self.color = tuple(rgb)
        self.refresh()

    def pick_color(self):
        c = QColorDialog.getColor(QColor(*self.color), self.app, "选指针颜色")
        if c.isValid():
            self.set_color((c.red(), c.green(), c.blue()))

    def update_labels(self):
        self.op_text.config(text=f"{int(self.opacity.get())}%")
        for s in self.swatches:
            s.draw(s.rgb == self.color)
        custom = self.color not in [s.rgb for s in self.swatches]
        self.custom.rgb = self.color
        self.custom.draw(True)
        self.custom.setVisible(custom)

    def schedule(self):
        self.op_text.config(text=f"{int(self.opacity.get())}%")
        ui.cancel(self._pending)
        self._pending = ui.after(60, self.refresh)

    def refresh(self):
        self._pending = None
        self.update_labels()
        if not cursor_mod.ready():
            return
        cfg = self.current()
        for key, _name in ROWS:
            w, h, px = cursor_mod.make_pixels(cfg, "hud/cursors/" + key)
            for c, (_g, bg) in enumerate(GROUNDS):
                self.tiles[(key, c)].set_image(compose(w, h, px, bg))

    def _loaded(self, ok, res):
        if ok:
            self.pv_note.config(text="")
            self.refresh()
        else:
            self.pv_note.config(text=T('读不到原版指针：{0}', tr(str(res))), fg=ui.BAD)
        self.sync()

    # ---- 装 / 还原
    def install(self):
        cfg = self.current()

        def action():
            cursor_mod.save(cfg)
            return cursor_mod.install() + "重新打开游戏就生效。"

        self.app.run(action, working="正在装指针…（大概十几秒）")

    def restore(self):
        cfg = self.current()

        def action():
            cursor_mod.save(cfg)
            return cursor_mod.restore() + "重新打开游戏就生效。"

        self.app.run(action, working="正在恢复原版指针…")

    def sync(self):
        running = bool(self.app.state["running"])
        ok = not self.app.busy and not running and cursor_mod.ready()
        self.btn_install.set_enabled(ok)
        self.btn_restore.set_enabled(ok and self.app.state["cursor"] != "off")
        self.hint.config(text="游戏正在运行，请先关闭游戏再安装。" if running else "", fg=ui.WARN)
        self.hint.setVisible(running)
        text, color = CURSOR_STATE.get(self.app.state.get("cursor"), ("…", ui.MUTED))
        self.state_lab.config(text=T("现在：{0}", tr(text)), fg=color)
