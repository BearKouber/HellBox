"""数据修改页几个编辑器共用的小工具：读 JSON、按路径取值、给人看的数、不偷滚轮的下拉框。

2026-11-14 V0.91：原来在旧「怪物」页 enemies.py 里；旧页被「数据修改」页替代后删掉，工具挪到这里。
"""
import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QWidget

import ui


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def get_path(settings, path):
    cur = settings
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and 0 < int(part) <= len(cur):
            cur = cur[int(part) - 1]
        else:
            return None
    return cur


def num(v):
    """给人看的数：最多 4 位有效数字，大数不写成 1e+04。"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if abs(v) >= 1000:
        return str(int(round(v)))
    return f"{v:.4g}"


class NoWheelCombo(QComboBox):
    """没点开下拉列表时，滚轮交给页面去滚，不偷偷改值。on_hide = 列表收起来以后调（open_popup 用）。"""

    on_hide = None

    def wheelEvent(self, event):
        if self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()

    def hidePopup(self):
        super().hidePopup()
        if self.on_hide:
            QTimer.singleShot(0, self.on_hide)  # 等点选的 activated 先处理完


COMBO_W = 240  # 下拉框和弹出列表都是这个宽（长的选项省略号）


def open_popup(c, chip, cancel=None):
    """2026-11-15 用户反馈的三个下拉问题：
    - 有时弹出列表跑到软件外面：原来下拉框刚塞进布局、还没摆好位置就弹列表，位置按 (0,0) 算了。改成等布局摆好（下一轮事件）再弹。
    - 点开会把已经选的变成空：原来特意清空了当前项。改成选中现在这一项；不在选项里的（比如打字输入过的数）显示成灰字占位。
    - 宽度忽宽忽窄：原来跟着这一格原来的宽度、列表又按最长的选项撑。改成下拉框、列表都固定 COMBO_W。
    cancel：没选就收起列表时调（只对不能打字的下拉框；能打字的收起列表后还可以接着打）。"""
    cur = getattr(chip, "text", "") or ""
    if callable(cur):
        cur = cur()
    i = c.findText(cur)
    if i >= 0:
        c.setCurrentIndex(i)
    else:
        c.setCurrentIndex(-1)
        if c.isEditable():
            c.setEditText(cur)  # 能打字的：框里留着现在的值
        else:
            c.setPlaceholderText(cur)
    # 2026-11-15 用户第二次反馈：点开后框变长了，要和没点开时一样宽 → 用这一格原来的宽度（列表也一样宽）
    w = chip.width() if chip.width() > 60 else COMBO_W
    c.setFixedWidth(w)
    v = c.view()
    v.setFixedWidth(w)
    v.setTextElideMode(Qt.TextElideMode.ElideRight)
    if cancel is not None and not c.isEditable():
        c.on_hide = cancel

    def show():
        try:
            if c.isVisible():
                c.setFocus()
                c.showPopup()
        except RuntimeError:  # 已经被删了
            pass

    QTimer.singleShot(0, show)


NUMERIC_KINDS = ("mult", "zero", "time", "count", "angle", "elev")


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def eff_key(base):
    """存的值 -> 实际数（排档位、找滑块位置用）：None = 原版，'*2' = 原值 ×2，其它 = 绝对值。"""
    def key(stored):
        if stored is None:
            return float(base)
        s = str(stored)
        if s.startswith("*"):
            return float(base) * float(s[1:])
        return float(s)
    return key


class ValueSlider(ui.StepSlider):
    """数值格（2026-11-15 用户要求：下拉换成能拖的滑条）。按档位吸附，原版是其中一档；松手就改。
    双击右边的字可以直接打一个数（和原来下拉框里打字一样）。.set_text(文字, 改过没) 和原来的 ValueChip 一样用。"""

    def __init__(self, text, changed=False):
        self._v = ui.Var(0)
        super().__init__(None, [], self._v, command=self._picked, width=170)
        self.items = []  # (实际数, 存的值)
        self.choose = self.typed = None
        self.key = None
        self._edit = None
        self.set_text(text, changed)

    def set_text(self, text, changed=None):
        self.set_current(text, changed)

    def setup(self, opts, choose, typed, key, cur):
        """opts = [(文字, 存的值)]（原版那档的存的值是 None）；key(存的值) -> 实际数；cur = 现在的实际数。"""
        seen, items = set(), []
        for label, stored in opts:
            try:
                k = round(float(key(stored)), 9)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            if k in seen:
                continue
            seen.add(k)
            items.append((k, label, stored))
        items.sort(key=lambda it: it[0])
        self.items = [(k, stored) for k, _l, stored in items]
        self.choose, self.typed, self.key = choose, typed, key
        self.set_options([(i, label) for i, (_k, label, _s) in enumerate(items)])
        self._place(cur)
        return len(items) >= 2

    def _place(self, cur):
        if not self.items:
            return
        try:
            c = float(cur)
            i = min(range(len(self.items)), key=lambda j: abs(self.items[j][0] - c))
        except (TypeError, ValueError):
            i = 0
        self._v._v = i  # 不触发 command
        self.update()

    def _picked(self, i):
        if self.choose and 0 <= i < len(self.items):
            self.choose(self.items[i][1])

    # ---- 双击右边的字：直接打数
    def mouseDoubleClickEvent(self, e):
        if not self.enabled or self.typed is None or e.position().x() < self.bw:
            return
        from PySide6.QtWidgets import QLineEdit
        ed = QLineEdit(self)
        ed.setFont(ui.f_zh(9))
        ed.setText(self.current or "")
        ed.setGeometry(self.bw + 6, 3, max(80, self.tw), self.height() - 6)
        ed.setStyleSheet(f"QLineEdit{{background:{ui.WHITE};border:2px solid {ui.INK};color:{ui.INK};padding:0 3px;}}")
        ed.selectAll()
        ed.show()
        ed.setFocus()
        self._edit = ed

        def done():
            if self._edit is not ed:
                return
            self._edit = None
            text = ed.text().strip()
            ed.hide()
            ed.deleteLater()
            if not text or text == (self.current or ""):
                return
            val = self.typed(text)
            if val is None:
                return
            self.choose(val)
            try:
                self._place(self.key(val))
            except (TypeError, ValueError):
                pass

        ed.editingFinished.connect(done)


# ---------------------------------------------------------------- 2026-11-15 编辑器新界面（UI 交给 Claude）
class PickGrid(ui.Clickable):
    """选怪 / 选武器 / 选战备：平的等宽格子（不再是一堆带阴影的按钮）。
    每格 = 小方块（改过 = 绿）+ 名字；选中那格白底黑框；鼠标停上去底栏显示 help。
    items = [(值, 文字, 改过没, 说明)]；点了调 command(值)。"""

    H = 34
    MIN_W = 150

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.items, self.sel = [], None
        self.hover_i = None
        self.setMouseTracking(True)
        self.setMinimumWidth(self.MIN_W)
        self.setFixedHeight(self.H)

    def set_items(self, items, sel):
        self.items, self.sel = list(items), sel
        self._fit()
        self.update()

    def _cols(self):
        return max(1, self.width() // self.MIN_W)

    def _fit(self):
        rows = max(1, (len(self.items) + self._cols() - 1) // self._cols())
        self.setFixedHeight(rows * self.H)

    def resizeEvent(self, e):
        self._fit()
        super().resizeEvent(e)

    def _rect(self, i):
        from PySide6.QtCore import QRect
        cols = self._cols()
        cw = self.width() / cols
        c, r = i % cols, i // cols
        return QRect(int(c * cw), r * self.H + 2, int(cw) - 6, self.H - 4)

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        for i, (key, label, changed, _help) in enumerate(self.items):
            r = self._rect(i)
            if key == self.sel:
                p.fillRect(r, ui.qc(ui.INK))
                p.fillRect(r.adjusted(2, 2, -2, -2), ui.qc(ui.WHITE))
            elif i == self.hover_i:
                p.fillRect(r, ui.qc(ui.PLAIN_HOVER))
            sq = 10
            y = r.center().y() - sq // 2
            p.fillRect(r.left() + 9, y, sq, sq, ui.qc(ui.INK))
            p.fillRect(r.left() + 11, y + 2, sq - 4, sq - 4, ui.qc(ui.MINT if changed else ui.CARD))
            p.setFont(ui.f_zh(10, key == self.sel or i == 0))
            p.setPen(ui.qc(ui.INK))
            text = p.fontMetrics().elidedText(ui._tr(label), Qt.TextElideMode.ElideRight, r.width() - 32)
            p.drawText(r.adjusted(26, 0, -4, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

    def _at(self, e):
        pos = e.position().toPoint()
        for i in range(len(self.items)):
            if self._rect(i).contains(pos):
                return i
        return None

    def mouseMoveEvent(self, e):
        i = self._at(e)
        if i != self.hover_i:
            self.hover_i = i
            self.update()
            if i is None:
                ui.hide_hint()
            else:
                _key, label, _changed, help_text = self.items[i]
                ui.show_hint(label, help_text)

    def leaveEvent(self, e):
        self.hover_i = None
        self.update()
        ui.hide_hint()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        i = self._at(e)
        if e.button() == Qt.MouseButton.LeftButton and i is not None:
            self.command(self.items[i][0])


class ParamList:
    """参数表（2026-11-15 新界面）：一行一个参数 = 名字 …… 滑条 / 选择 …… 原版值；行间细线，
    分段标题是小色块 + 粗字；鼠标停在一行上，底栏显示这一项的说明（代替原来的鼠标提示框）。"""

    NAME_W = 190

    def __init__(self, lay, color=None):
        self.lay, self.color = lay, color or ui.SALMON
        self.n = 0

    def section(self, title, top=14):
        self.lay.addSpacing(top if self.lay.count() else 0)
        head, hl = ui.hbox(spacing=7)
        hl.setContentsMargins(0, 0, 0, 4)
        hl.addWidget(ui.Square(None, self.color, 8), 0, Qt.AlignmentFlag.AlignVCenter)
        en = ui._tr("■ " + title)  # 英文版：分段标题以前是带「■ 」翻的
        title = en[2:] if en != "■ " + title else title
        hl.addWidget(ui.Label(title, font=ui.f_zh(10, True)), 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addStretch(1)
        self.lay.addWidget(head)
        line = QWidget()
        line.setFixedHeight(2)
        ui.filled(line, ui.INK)
        self.lay.addWidget(line)
        self.n = 0

    def row(self, label, widget, orig=None, help=None):
        if self.n:
            sep = QWidget()
            sep.setFixedHeight(1)
            ui.filled(sep, ui.DISABLED)
            self.lay.addWidget(sep)
        self.n += 1
        r = ui.HoverRow(label, help)
        r.lay.setContentsMargins(8, 5, 8, 5)
        lab = ui.Label(label, font=ui.f_zh(10))
        lab.setFixedWidth(self.NAME_W)
        r.lay.addWidget(lab, 0, Qt.AlignmentFlag.AlignVCenter)
        if widget is not None:
            r.lay.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        r.lay.addStretch(1)
        if orig:
            r.lay.addWidget(ui.Label(orig, font=ui.f_zh(8), fg=ui.MUTED), 0, Qt.AlignmentFlag.AlignVCenter)
        self.lay.addWidget(r)
        return r


def swap_combo(chip, combo):
    """点开的下拉框放在小方块原来的位置（小方块先藏起来，关掉下拉框再露出来）。"""
    lay = chip.parentWidget().layout()
    lay.insertWidget(lay.indexOf(chip), combo, 0, Qt.AlignmentFlag.AlignVCenter)
    chip.hide()


def small_button(text, command, kind="plain"):
    return ui.Button(None, text, command, kind=kind, font=ui.f_zh(9, True), padx=9, pady=2, shadow=2)


def styled_combo(editable, width=150, mono=True):
    c = NoWheelCombo(None)
    c.setEditable(editable)
    c.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    c.setFont(ui.f_mono(9) if mono else ui.f_zh(9))
    c.setMinimumWidth(width)
    c.setStyleSheet(
        "QComboBox{background:#fffdf2;border:2px solid #1b1b1b;border-radius:0;color:#1b1b1b;padding:1px 3px;}"
        "QComboBox:disabled{background:#d6cfc3;color:#6f6a62;}"
        "QComboBox::drop-down{border-left:2px solid #1b1b1b;width:18px;}"
        "QComboBox QAbstractItemView{background:#fffdf2;border:2px solid #1b1b1b;"
        "selection-background-color:#bfe3c6;selection-color:#1b1b1b;color:#1b1b1b;}")
    return c
