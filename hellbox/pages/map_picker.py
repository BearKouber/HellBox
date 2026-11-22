"""选图页「挑地形」弹窗（2026-11-22 用户定，Dive Harder 作者的建议：编号对玩家没意义、「换一张图」靠碰运气）。

2026-11-22 用户：「挑地形」按钮也不要，只留点地图；玩法页「试验场」的地图也一样点开挑（候选由调用的页面给）。
点地图卡右边的小地图 = 打开这个窗口：把「类型 · 种族 · 环境 · 时间 · 难度」都不变、只换地形随机数（0～214）的
所有图一次列出来，看着形状挑一张，点了就换成它、窗口关掉。

为什么要开着游戏：游戏拼图用的随机数是拿整个地图编号起的头（GeneratedLevel.initialize 里 Randomizer(编号)），
同一个地形数换了难度、时间也是另一张图，没法提前做一张固定的表；所以每次打开都让游戏现拼这 215 张
（mod/src/map_preview.lua，拼好写 maps2/<编号>.txt，已经拼过的不再拼），拼出来一张显示一张。
长得一样的只留一张（地形数小的那个）：报复关中间是一整块现成的场地，按场地算（每个种族 + 环境两块，转了方向也算同一块）；
大图、首领战按整张拼法算。
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
if _AI not in sys.path:  # drill_spec 在 ai 目录（玩法页可能比选图页先加载）
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
    """选图页：这张图只换地形随机数的全部编号（编号超出范围的去掉），地形数从小到大。"""
    base = int(seed) % 10000000
    return [t * 10000000 + base for t in range(ds.MAX_TERRAIN + 1) if t * 10000000 + base <= ds.MAX_SEED]


def signature(layout):
    """两张图看起来一样吗：报复关按中间那块场地（不管转向）；别的按整张拼法。"""
    if not layout:
        return None
    tiles = layout.get("tiles") or []
    if layout.get("mode") in GENOCIDE_MODES:
        return ("g",) + tuple(sorted(t["name"] for t in tiles if not t["edge"]))
    return tuple(sorted((t["name"], t["rot"], t["x"], t["y"], t["sx"], t["sy"]) for t in tiles))


class ClickMap(mt.MapThumb):
    """页面上的小地图，点了打开「挑地形」（选图页、玩法页试验场共用）。"""

    def __init__(self, size, on_click):
        super().__init__(size)
        self.on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("点一下挑地形"))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.on_click()


class _Thumb(ui.Clickable):
    """弹窗里的一格：小地图 + 下面「地形 N」；现在选的那张黄底粗框。"""

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
        if self.picked or self.hovered:  # 小地图把底色盖满了，选中 / 悬停另外画一圈框
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
    """挑地形的窗口。cands = 候选的图（map_thumbs 的键：编号或试验场的 (请求行, 文件名)），current = 现在那张，
    on_pick(候选) 在点了一张时调用，title = 标题旁的小字。"""

    def __init__(self, parent, current, cands, on_pick, game_running, title=""):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.seed, self.on_pick, self.game_running = current, on_pick, game_running
        self.cands = list(cands)
        self.shown = []  # [(编号, 布局)]，已经放进格子的
        self.picked_sig = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = ui.Box(self, fill=ui.CARD, border=2, shadow=6, pad=(20, 16, 20, 16))
        outer.addWidget(box)
        head, hl = ui.hbox()
        hl.addWidget(ui.Square(None, ui.YELLOW, 12), 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addSpacing(9)
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
            self.status.config(text=T("要开着游戏（在飞船或主菜单里）才能把图拼出来。已经拼好 {0} / {1} 张。", made, total))
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
        mt.request([], owner="picker")  # 别让游戏接着拼没人要的图
        super().done(r)

    def showEvent(self, e):
        super().showEvent(e)
        self.adjustSize()
        par = self.parentWidget()
        if par is not None:
            win = par.window()
            c = win.mapToGlobal(win.rect().center())
            self.move(c.x() - self.width() // 2, c.y() - self.height() // 2)

