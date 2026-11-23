"""
选图页的「挑地形」弹窗：保持类型、种族、环境、时间、难度不变，只换地形随机数，列出所有候选地图供点选。
"""
import os
import sys

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QDialog, QGridLayout, QScrollArea, QVBoxLayout, QWidget

import paths
import ui
from pages import map_thumbs as mt
_AI = os.path.join(paths.ROOT, "ai")
if _AI not in sys.path:
    sys.path.insert(0, _AI)
import drill_spec as ds  # noqa: E402
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

THUMB = 128
COLS = 5
POLL_MS = 500
GENOCIDE_MODES = ("genocide", "provinggrounds_genocide_map")


def candidates(seed):
    base = int(seed) % 10000000
    return [t * 10000000 + base for t in range(ds.MAX_TERRAIN + 1) if t * 10000000 + base <= ds.MAX_SEED]


def signature(layout):
    if not layout:
        return None
    tiles = layout.get("tiles") or []
    if layout.get("mode") in GENOCIDE_MODES:
        return ("g",) + tuple(sorted(t["name"] for t in tiles if not t["edge"]))
    return tuple(sorted((t["name"], t["rot"], t["x"], t["y"], t["sx"], t["sy"]) for t in tiles))


class ClickMap(mt.MapThumb):

    def __init__(self, size, on_click):
        super().__init__(size)
        self.on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("点击挑选地形"))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.on_click()


class _Thumb(ui.Clickable):

    def __init__(self, seed, layout, index, picked, on_pick):
        super().__init__()
        self.seed, self.layout_data, self.index, self.picked, self.on_pick = seed, layout, index, picked, on_pick
        self.setFixedSize(THUMB, THUMB + 22)
        if isinstance(seed, int):
            self.setToolTip(tr(ds.describe(seed)))

    def paintEvent(self, _e):
        p = QPainter(self)
        r = ui.paint_box(p, THUMB, THUMB, ui.INSET, 2, 0)
        mt.paint(p, QRect(r), self.layout_data)
        if self.picked or self.hovered:
            p.setPen(QPen(QColor(ui.YELLOW if self.picked else ui.MINT), 5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRect(r).adjusted(2, 2, -3, -3))
        p.setFont(ui.f_zh(9, True))
        p.setPen(QColor(ui.INK))
        label = T("地形 {0}（现在）", self.index) if self.picked else T("地形 {0}", self.index)
        p.drawText(QRect(0, THUMB + 2, THUMB, 20), Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.on_pick(self.seed)


class MapPicker(QDialog):

    def __init__(self, parent, current, cands, on_pick, game_running, title=""):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.seed, self.on_pick, self.game_running = current, on_pick, game_running
        self.cands = list(cands)
        self.shown = []
        self.picked_sig = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = ui.Box(self, fill=ui.CARD, border=2, shadow=6, pad=(20, 16, 20, 16))
        outer.addWidget(box)
        head, hl = ui.hbox()
        hl.addWidget(ui.Label("挑地形", font=ui.f_zh(12, True)), 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addSpacing(12)
        hl.addWidget(ui.Label(title, font=ui.f_zh(9), fg=ui.MUTED), 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addStretch(1)
        box.lay.addWidget(head)
        box.lay.addSpacing(8)
        self.status = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED, wrap=True)
        box.lay.addWidget(self.status)
        box.lay.addSpacing(8)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setWidget(self.grid_host)
        w = COLS * (THUMB + 10) + 24
        scroll.setFixedSize(w, 3 * (THUMB + 32) + 10)
        box.lay.addWidget(scroll)
        box.lay.addSpacing(12)
        row, rl = ui.hbox(spacing=10)
        rl.addStretch(1)
        rl.addWidget(ui.Button(None, "取消", self.reject))
        box.lay.addWidget(row)

        mt.request(self.cands, owner="picker")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(POLL_MS)
        self._poll()

    def _poll(self):
        picked = mt.load(self.seed)
        sig_now = signature(picked)
        if sig_now != self.picked_sig:
            self.picked_sig = sig_now
            self._rebuild()
        made, seen, unique = 0, set(), []
        for s in self.cands:
            lay = mt.load(s)
            if lay is None:
                continue
            made += 1
            sig = signature(lay)
            if sig not in seen:
                seen.add(sig)
                unique.append((s, lay))
        if [s for s, _ in unique] != [s for s, _ in self.shown]:
            self.shown = unique
            self._rebuild()
        total = len(self.cands)
        if made >= total:
            self.status.config(text=T("一共 {0} 种不同的地形，点一张就换成它。长得一样的只留了一张。", len(unique)))
            self.timer.stop()
        elif not self.game_running():
            self.status.config(text=T("需要游戏正在运行（在飞船或主菜单中）才能拼出地图。已经拼好 {0} / {1} 张。", made, total))
        else:
            self.status.config(text=T("游戏正在拼图：{0} / {1}，已经有 {2} 种不同的地形，可以先挑。", made, total, len(unique)))

    def _rebuild(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, (s, lay) in enumerate(self.shown):
            cell = _Thumb(s, lay, i + 1, signature(lay) == self.picked_sig, self._pick)
            self.grid.addWidget(cell, i // COLS, i % COLS)

    def _pick(self, seed):
        self.timer.stop()
        self.on_pick(seed)
        self.accept()

    def done(self, r):
        self.timer.stop()
        mt.request([], owner="picker")
        super().done(r)

    def showEvent(self, e):
        super().showEvent(e)
        self.adjustSize()
        par = self.parentWidget()
        if par is not None:
            win = par.window()
            c = win.mapToGlobal(win.rect().center())
            self.move(c.x() - self.width() // 2, c.y() - self.height() // 2)

