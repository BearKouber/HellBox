"""
HellBox 外观：复古方块风

控件：
    Box         带黑边和硬阴影的盒子（卡片、主面板的底子），里面放布局
    Button      方块按钮，按下去会"陷进"阴影里
    Toggle      ON / OFF 开关
    Slider      方块滑条
    Segmented   一排互斥的方块（顶部标签、二选一）
    Dropdown    方块下拉框（选项多、一排放不下时用）
    CheckBox    方块勾选框 / 圆点单选
    Stepper     [-] 数字 [+]
    Entry       白底黑边输入框
    Card        带标签牌的卡片
    Chip        小状态牌（色块 + 文字）
    Tag         像素字小牌子
    Square      带黑边的色块（状态灯）
    Label       文字（可自动折行）
    DotPage     点阵背景的页面，卡片按行排，放不下时能滚
    Var         代替 tk 的 StringVar / BooleanVar：get / set / trace
"""
import os

from i18n import LANG, tr as _tr  # 英文版：控件显示文字时自动换成英文（i18n.py）
from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QScrollBar, QSizePolicy,
                               QVBoxLayout, QWidget)

# ---------------------------------------------------------------- 颜色
BG = "#d9d1c4"        # 窗口外圈
PANEL = "#ebe4d8"     # 主面板
HEADER = "#ddd5c7"    # 顶栏 / 底栏
CARD = "#f1ece3"      # 卡片
INSET = "#e2dbcf"     # 卡片里的凹槽
WHITE = "#fbf8f2"     # 输入框
INK = "#1c1c1c"       # 黑边、正文
MUTED = "#6f6a62"     # 说明文字
DOT = "#c9c0b1"       # 背景点阵
MINT = "#86d3a6"
MINT_HOVER = "#9ddcb6"
YELLOW = "#f6d469"
YELLOW_HOVER = "#f8de8a"
SALMON = "#f07152"
SALMON_HOVER = "#f38c72"
SKY = "#c8d2e3"
TAN = "#e3b38c"
PLAIN_HOVER = "#f6f2ea"
DISABLED = "#d6cfc3"
GOOD = "#2e8a56"      # 文字里的绿（成功）
BAD = "#c4432a"       # 文字里的红（失败）
WARN = "#9a6b00"


def px(n):
    return int(n)


# ---------------------------------------------------------------- 字体
PIXEL = "Silkscreen"
ZH = "Microsoft YaHei UI"
MONO = "Consolas"
_FONTS = {}


def load_fonts(folder):
    ok = False
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if name.lower().endswith(".ttf"):
                ok |= QFontDatabase.addApplicationFont(os.path.join(folder, name)) >= 0
    return ok


def _font(families, size, bold, pixel=False):
    key = (tuple(families), size, bold)
    f = _FONTS.get(key)
    if f is None:
        f = QFont()
        f.setFamilies(list(families))
        f.setPointSizeF(size)
        f.setBold(bold)
        if pixel:
            f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        _FONTS[key] = f
    return QFont(f)


def f_pixel(size=10, bold=True):
    return _font([PIXEL], size, bold, pixel=True)


def f_zh(size=10, bold=False):
    return _font([ZH], size, bold)


def f_mono(size=10, bold=False):
    return _font([MONO, ZH], size, bold)


def _fm(font):
    return QFontMetrics(font)


def _tw(font, s):
    return _fm(font).horizontalAdvance(s)


def _lh(font):
    return _fm(font).height()


def qc(c):
    return QColor(c)


# ---------------------------------------------------------------- 变量、定时、跨线程
class Var:

    def __init__(self, value=None):
        self._v = value
        self._subs = []

    def get(self):
        return self._v

    def set(self, v):
        self._v = v
        for f in list(self._subs):
            try:
                f()
            except RuntimeError as e:
                if "already deleted" not in str(e):
                    raise
                if f in self._subs:
                    self._subs.remove(f)

    def trace(self, fn):
        self._subs.append(fn)


_TIMERS = set()


def after(ms, fn):
    t = QTimer()
    t.setSingleShot(True)
    t.timeout.connect(fn)
    t.timeout.connect(lambda: _TIMERS.discard(t))
    _TIMERS.add(t)
    t.start(ms)
    return t


def cancel(t):
    if t is not None:
        t.stop()
        _TIMERS.discard(t)


class Bridge(QObject):
    call = Signal(object)

    def __init__(self):
        super().__init__()
        self.call.connect(lambda fn: fn())


# ---------------------------------------------------------------- 画盒子
def paint_box(p, w, h, fill, border=2, shadow=4, pressed=False):
    bw, bh = w - shadow, h - shadow
    if pressed:
        x0 = y0 = shadow
    else:
        x0 = y0 = 0
        if shadow:
            p.fillRect(shadow, shadow, bw, bh, qc(INK))
    p.fillRect(x0, y0, bw, bh, qc(INK))
    p.fillRect(x0 + border, y0 + border, bw - 2 * border, bh - 2 * border, qc(fill))
    return QRect(x0 + border, y0 + border, bw - 2 * border, bh - 2 * border)


class Box(QWidget):

    def __init__(self, parent=None, fill=CARD, border=2, shadow=4, pad=(0, 0, 0, 0), vertical=True):
        super().__init__(parent)
        self.fill, self.border, self.shadow = fill, border, shadow
        self.lay = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        self.lay.setSpacing(0)
        l, t, r, b = pad
        self.lay.setContentsMargins(border + l, border + t, border + shadow + r, border + shadow + b)

    def set_fill(self, fill):
        if fill != self.fill:
            self.fill = fill
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        paint_box(p, self.width(), self.height(), self.fill, self.border, self.shadow)


def filled(widget, color):
    """给一个普通 QWidget 铺底色。"""
    widget.setAutoFillBackground(True)
    pal = widget.palette()
    pal.setColor(QPalette.ColorRole.Window, qc(color))
    widget.setPalette(pal)
    return widget


def ink_line(height=2):
    w = QWidget()
    w.setFixedHeight(height)
    return filled(w, INK)


def hbox(parent=None, spacing=0, margins=(0, 0, 0, 0)):
    w = QWidget(parent)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return w, lay


def vbox(parent=None, spacing=0, margins=(0, 0, 0, 0)):
    w = QWidget(parent)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return w, lay


# ---------------------------------------------------------------- 文字
class Label(QLabel):

    def __init__(self, text="", font=None, fg=INK, wrap=False, parent=None, breakable=False):
        super().__init__(parent)
        self._breakable = breakable
        self._raw = None
        self.setFont(font or f_zh(10))
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setContentsMargins(2, 2, 2, 2)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._fg = None
        self.config(text=text, fg=fg)
        if wrap:
            self.setWordWrap(True)
            sp = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            sp.setHeightForWidth(True)
            self.setSizePolicy(sp)
            self.setMinimumWidth(40)

    def config(self, text=None, fg=None):
        text = _tr(text)
        if text is not None and text != self._raw:
            self._raw = text
            if self._breakable:
                for ch in "\\/_.-":
                    text = text.replace(ch, ch + "​")
            self.setText(text)
        if fg is not None and fg != self._fg:
            self._fg = fg
            pal = self.palette()
            pal.setColor(QPalette.ColorRole.WindowText, qc(fg))
            self.setPalette(pal)

    configure = config


def text(parent, s, size=10, muted=False, bold=False, wrap=True, **_kw):
    """一段文字（和 tk 版同名）。"""
    return Label(s, font=f_zh(size, bold), fg=MUTED if muted else INK, wrap=wrap, parent=parent)


class ElideLabel(QWidget):

    def __init__(self, text="", font=None, fg=INK, align_right=False, parent=None):
        super().__init__(parent)
        self._text, self._fg, self._right = _tr(text), fg, align_right
        self._tip = ""
        self.setFont(font or f_mono(10))
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_lh(self.font()) + 6)

    def config(self, text=None, fg=None):
        if text is not None:
            self._text = _tr(text)
            self._update_tip(self._shown_full())
        if fg is not None:
            self._fg = fg
        self.update()

    def set_tip(self, tip):
        self._tip = _tr(tip) if tip else ""
        self._update_tip(self._shown_full())

    def _shown_full(self):
        w = self.rect().adjusted(3, 0, -3, 0).width()
        return _fm(self.font()).elidedText(self._text, Qt.TextElideMode.ElideRight, w) == self._text

    def _update_tip(self, full):
        parts = ([] if full else [self._text]) + ([self._tip] if self._tip else [])
        tip = "\n\n".join(p for p in parts if p)
        if self.toolTip() != tip:
            self.setToolTip(tip)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_tip(self._shown_full())

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(qc(self._fg))
        r = self.rect().adjusted(3, 0, -3, 0)
        s = _fm(self.font()).elidedText(self._text, Qt.TextElideMode.ElideRight, r.width())
        self._update_tip(s == self._text)
        al = (Qt.AlignmentFlag.AlignRight if self._right else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter
        p.drawText(r, al, s)


# ---------------------------------------------------------------- 按钮
KINDS = {
    "primary": (MINT, MINT_HOVER),
    "accent": (YELLOW, YELLOW_HOVER),
    "danger": (SALMON, SALMON_HOVER),
    "plain": (WHITE, PLAIN_HOVER),
}


class Clickable(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self.hovered = False
        self.widget = self
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, _e):
        self.hovered = True
        self.update()

    def leaveEvent(self, _e):
        self.hovered = False
        self.update()

    def set_enabled(self, on):
        on = bool(on)
        if on != self.enabled:
            self.enabled = on
            self.setCursor(Qt.CursorShape.PointingHandCursor if on else Qt.CursorShape.ArrowCursor)
            self.update()


class Button(Clickable):

    def __init__(self, parent, text, command, kind="plain", under=None, font=None, padx=16, pady=5, shadow=3):
        super().__init__(parent)
        self.command, self._text = command, _tr(text)
        self.fill, self.hover = KINDS[kind]
        self.shadow, self.padx, self.pady = shadow, padx, pady
        self.setFont(font or f_zh(10, True))
        self._down = False
        self._resize()

    def _resize(self):
        f = self.font()
        self.setFixedSize(_tw(f, self._text) + 2 * self.padx + 8 + self.shadow,
                          _lh(f) + 2 * self.pady + 8 + self.shadow)

    def paintEvent(self, _e):
        p = QPainter(self)
        color = (self.hover if self.hovered else self.fill) if self.enabled else DISABLED
        r = paint_box(p, self.width(), self.height(), color, 2, self.shadow, pressed=self._down)
        p.setFont(self.font())
        p.setPen(qc(INK if self.enabled else MUTED))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._text)

    def leaveEvent(self, e):
        self._down = False
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.enabled:
            self._down = True
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self._down:
            return
        self._down = False
        self.update()
        if self.rect().contains(e.position().toPoint()) and self.enabled and self.command:
            self.command()

    def set_text(self, text):
        self._text = _tr(text)
        self._resize()
        self.update()


# ---------------------------------------------------------------- 开关
class Toggle(Clickable):

    def __init__(self, parent, variable, command=None, under=None):
        super().__init__(parent)
        self.W, self.H = 70, 28
        self.setFixedSize(self.W + 3, self.H + 3)
        self.var, self.command = variable, command
        variable.trace(self.update)

    def paintEvent(self, _e):
        p = QPainter(self)
        on = bool(self.var.get())
        w, h, b, m = self.W, self.H, 2, 5
        p.fillRect(3, 3, w, h, qc(INK))  # 阴影
        fill = (MINT if on else WHITE) if self.enabled else DISABLED
        p.fillRect(0, 0, w, h, qc(INK))
        p.fillRect(b, b, w - 2 * b, h - 2 * b, qc(fill))
        k = h - 2 * m
        kx = w - k - m + 1 if on else m
        p.fillRect(kx, m, k, k, qc(INK))
        if not on:
            p.fillRect(kx + b, m + b, k - 2 * b, k - 2 * b, qc(CARD))
        tx0, tx1 = (m, kx) if on else (kx + k, w)
        p.setFont(f_pixel(8))
        p.setPen(qc(INK if self.enabled else MUTED))
        p.drawText(QRect(tx0, 0, tx1 - tx0, h), Qt.AlignmentFlag.AlignCenter, "ON" if on else "OFF")

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if not self.enabled:
            if getattr(self, "blocked", None):
                self.blocked()
            return
        self.var.set(not bool(self.var.get()))
        if self.command:
            self.command()


# ---------------------------------------------------------------- 「?」说明
def tip_html(text):
    import html
    body = html.escape(_tr(text) or "").replace("\n", "<br>")
    return f"<table width=300><tr><td>{body}</td></tr></table>"


TIP_STYLE = (f"QToolTip{{background:{CARD};color:{INK};border:2px solid {INK};padding:6px 8px;}}")


class Help(Clickable):

    def __init__(self, text, parent=None, size=18):
        super().__init__(parent)
        self._text = text
        self.setFixedSize(size + 2, size + 2)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)

    def set_text(self, text):
        self._text = text

    def paintEvent(self, _e):
        p = QPainter(self)
        r = paint_box(p, self.width(), self.height(), YELLOW if self.hovered else CARD, 2, 2)
        p.setFont(f_zh(9, True))
        p.setPen(qc(INK))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "?")

    def _show(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QToolTip
        if self._text:
            QToolTip.showText(self.mapToGlobal(QPoint(self.width() + 4, self.height() + 2)), tip_html(self._text), self)

    def enterEvent(self, e):
        super().enterEvent(e)
        self._show()

    def leaveEvent(self, e):
        from PySide6.QtWidgets import QToolTip
        super().leaveEvent(e)
        QToolTip.hideText()

    def mousePressEvent(self, _e):
        self._show()


# ---------------------------------------------------------------- 左侧页面导航
class SideTabs(Clickable):

    def __init__(self, parent, options, variable, command=None, font=None, width=None, pady=8, color=MINT):
        super().__init__(parent)
        self.var, self.command, self.color = variable, command, color
        self.setFont(font or f_zh(11, True))
        self.setMouseTracking(True)
        self._hover = None
        f = self.font()
        self._cells = []
        y = 2
        ch = _lh(f) + 2 * pady
        for i, (value, txt) in enumerate(options):
            if i:
                y += 2
            self._cells.append((value, _tr(txt), y, y + ch))
            y += ch
        w = width or max(_tw(f, t) for _v, t, _a, _b in self._cells) + 36
        self.setFixedSize(w + 2 + 4, y + 2 + 4)
        variable.trace(self.update)

    def _at(self, pos):
        for value, _t, y0, y1 in self._cells:
            if y0 <= pos.y() < y1 and 2 <= pos.x() < self.width() - 4 - 2:
                return value
        return None

    def paintEvent(self, _e):
        p = QPainter(self)
        paint_box(p, self.width(), self.height(), INK, 2, 4)
        cur = self.var.get()
        p.setFont(self.font())
        x1 = self.width() - 4 - 2
        for value, txt, y0, y1 in self._cells:
            sel = value == cur
            bg = self.color if sel else (PLAIN_HOVER if value == self._hover else CARD)
            r = QRect(2, y0, x1 - 2, y1 - y0)
            p.fillRect(r, qc(bg))
            if sel:
                p.fillRect(2, y0, 5, y1 - y0, qc(INK))
            p.setPen(qc(INK))
            p.drawText(r.adjusted(16, 0, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)

    def mouseMoveEvent(self, e):
        v = self._at(e.position().toPoint())
        if v != self._hover:
            self._hover = v
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        v = self._at(e.position().toPoint())
        if v is not None and v != self.var.get():
            self.var.set(v)
            if self.command:
                self.command(v)


# ---------------------------------------------------------------- 档位滑条
class StepSlider(Clickable):

    TAIL_GAP, TAIL_W = 14, 26

    def __init__(self, parent, options, variable, command=None, width=200, text_width=None, fill=SALMON, tail=False):
        super().__init__(parent)
        self.var, self.command, self.fill, self.tail = variable, command, fill, bool(tail)
        self.options = []
        self.current, self.changed = None, False
        self.bw = width
        self._min_tw = text_width
        self.setFont(f_zh(9, True))
        self._drag_i = None
        self.set_options(options)
        variable.trace(self.update)

    def set_options(self, options):
        self.options = [(v, _tr(t)) for v, t in options]
        self._fit()

    def _fit(self):
        texts = [t for _v, t in self.options] + ([self.current] if self.current else [])
        tw = max([_tw(self.font(), t) for t in texts] + [40]) + 14
        if self._min_tw:
            tw = max(tw, self._min_tw)
        self.tw = tw
        self.setFixedSize(self._end() + 10 + self.tw, 30)
        self.update()

    def set_current(self, text, changed=None):
        self.current = _tr(text) if text else None
        if changed is not None:
            self.changed = bool(changed)
        self._fit()

    def _index(self):
        if self._drag_i is not None:
            return self._drag_i
        cur = self.var.get()
        for i, (v, _t) in enumerate(self.options):
            if v == cur:
                return i
        return 0

    def _label(self):
        if self._drag_i is None and self.current:
            return self.current
        return self.options[self._index()][1] if self.options else ""

    def _end(self):
        return self.bw + (self.TAIL_GAP + self.TAIL_W if self.tail else 0)

    def _main_n(self):
        return len(self.options) - (1 if self.tail and len(self.options) > 1 else 0)

    def _is_tail(self, i):
        return self.tail and len(self.options) > 1 and i == len(self.options) - 1

    def _x(self, i):
        if self._is_tail(i):
            return self.bw + self.TAIL_GAP + self.TAIL_W / 2
        n = max(1, self._main_n() - 1)
        return 8 + (self.bw - 16) * i / n

    def paintEvent(self, _e):
        p = QPainter(self)
        y0, y1, b = 10, 20, 2
        p.fillRect(0, y0, self.bw, y1 - y0, qc(INK))
        p.fillRect(b, y0 + b, self.bw - 2 * b, y1 - y0 - 2 * b, qc(WHITE if self.enabled else DISABLED))
        n = self._main_n()
        for i in range(n if n <= 24 else 0):
            tx = int(round(self._x(i)))
            p.fillRect(tx, y1 + 1, 2, 3, qc(MUTED))
        i = self._index()
        on_tail = self._is_tail(i)
        x = int(round(self._x(i)))
        if self.tail:
            tx0 = self.bw + self.TAIL_GAP
            p.fillRect(tx0, y0, self.TAIL_W, y1 - y0, qc(INK))
            p.fillRect(tx0 + b, y0 + b, self.TAIL_W - 2 * b, y1 - y0 - 2 * b,
                       qc(BAD if self.enabled and on_tail else (SALMON_HOVER if self.enabled else DISABLED)))
            for k in range(3):
                p.fillRect(self.bw + 2 + k * 4, (y0 + y1) // 2 - 1, 2, 2, qc(MUTED))
        if self.enabled:
            fx = self.bw - b if on_tail else x
            p.fillRect(b, y0 + b, max(0, fx - b), y1 - y0 - 2 * b, qc(BAD if on_tail else self.fill))
        p.fillRect(x - 5, 3, 10, 24, qc(INK if self.enabled else MUTED))
        p.fillRect(x - 2, 7, 4, 16, qc(YELLOW if (self.hovered or self._drag_i is not None) and self.enabled else CARD))
        p.setFont(self.font())
        label = self._label()
        tr_ = QRect(self._end() + 10, 0, self.tw, self.height())
        if self.changed and self._drag_i is None:
            p.fillRect(QRect(tr_.left() - 4, 5, _tw(self.font(), label) + 8, self.height() - 10), qc(YELLOW_HOVER))
        p.setPen(qc((BAD if on_tail else INK) if self.enabled else MUTED))
        p.drawText(tr_, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

    def _pick(self, e):
        n = len(self.options)
        if not n:
            return
        if self.tail and n > 1 and e.position().x() > self.bw + self.TAIL_GAP / 2:
            i = n - 1
        else:
            t = (e.position().x() - 8) / max(1, self.bw - 16)
            i = int(round(max(0.0, min(1.0, t)) * (self._main_n() - 1)))
        if i != self._drag_i:
            self._drag_i = i
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.enabled and e.position().x() <= self._end() + 4:
            self._pick(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and self._drag_i is not None:
            self._pick(e)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._drag_i is None:
            return
        v = self.options[self._drag_i][0]
        self._drag_i = None
        if v != self.var.get():
            self.var.set(v)
            if self.command:
                self.command(v)
        self.update()

    def wheelEvent(self, e):
        e.ignore()


# ---------------------------------------------------------------- 滑条
class Slider(Clickable):

    def __init__(self, parent, variable, lo, hi, command=None, width=260, under=None, fill=SALMON):
        super().__init__(parent)
        self.var, self.lo, self.hi, self.command, self.w, self.fill = variable, lo, hi, command, width, fill
        self.setFixedSize(width, 30)
        variable.trace(self.update)

    def _x(self, v):
        return 8 + (self.w - 16) * (v - self.lo) / (self.hi - self.lo)

    def paintEvent(self, _e):
        p = QPainter(self)
        y0, y1, b = 9, 21, 2
        p.fillRect(0, y0, self.w, y1 - y0, qc(INK))
        p.fillRect(b, y0 + b, self.w - 2 * b, y1 - y0 - 2 * b, qc(WHITE))
        x = int(round(self._x(int(self.var.get()))))
        p.fillRect(b, y0 + b, x - b, y1 - y0 - 2 * b, qc(self.fill))
        p.fillRect(x - 6, 2, 12, 26, qc(INK))
        p.fillRect(x - 3, 6, 6, 18, qc(CARD))

    def _drag(self, e):
        t = (e.position().x() - 8) / max(1, self.w - 16)
        v = round(self.lo + max(0.0, min(1.0, t)) * (self.hi - self.lo))
        if v != int(self.var.get()):
            self.var.set(v)
            if self.command:
                self.command(final=False)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._drag(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.command:
            self.command(final=True)


# ---------------------------------------------------------------- 一排互斥方块
class Segmented(Clickable):

    def __init__(self, parent, options, variable, command=None, under=None, font=None, color=MINT,
                 padx=18, pady=6, shadow=4, allowed=None):
        super().__init__(parent)
        self.var, self.command, self.color, self.shadow = variable, command, color, shadow
        self.allowed = allowed
        self.setFont(font or f_zh(10, True))
        self.setMouseTracking(True)
        self._hover = None
        f = self.font()
        self._cells = []
        x = 2
        for i, (value, txt) in enumerate(options):
            txt = _tr(txt)
            if i:
                x += 2
            w = _tw(f, txt) + 2 * padx + 4
            self._cells.append((value, txt, x, x + w))
            x += w
        self._ch = _lh(f) + 2 * pady + 4
        self.setFixedSize(x + 2 + shadow, self._ch + 4 + shadow)
        variable.trace(self.update)

    def _cell_on(self, value):
        return self.enabled and (self.allowed is None or value in self.allowed)

    def _at(self, pos):
        for value, _t, x0, x1 in self._cells:
            if x0 <= pos.x() < x1 and 2 <= pos.y() < 2 + self._ch:
                return value
        return None

    def paintEvent(self, _e):
        p = QPainter(self)
        paint_box(p, self.width(), self.height(), INK, 2, self.shadow)
        cur = self.var.get()
        p.setFont(self.font())
        for value, txt, x0, x1 in self._cells:
            sel = value == cur
            on = self._cell_on(value)
            if on:
                bg = self.color if sel else (PLAIN_HOVER if value == self._hover else CARD)
            else:
                bg = DISABLED if sel else CARD
            r = QRect(x0, 2, x1 - x0, self._ch)
            p.fillRect(r, qc(bg))
            p.setPen(qc(INK if on else MUTED))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, txt)

    def mouseMoveEvent(self, e):
        v = self._at(e.position().toPoint())
        if v is not None and not self._cell_on(v):
            v = None
        if v != self._hover:
            self._hover = v
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self.enabled:
            return
        v = self._at(e.position().toPoint())
        if v is not None and self._cell_on(v) and v != self.var.get():
            self.var.set(v)
            if self.command:
                self.command(v)


# ---------------------------------------------------------------- 下拉框
class Dropdown(Clickable):

    ARROW = 22

    def __init__(self, parent, options, variable, command=None, width=None, font=None, allowed=None, shadow=3):
        super().__init__(parent)
        self.var, self.command, self.shadow, self._chars = variable, command, shadow, width
        self.setFont(font or f_zh(10, True))
        self.options, self.allowed = [], allowed
        self.set_options(options, allowed)
        variable.trace(self.update)

    def set_options(self, options, allowed=None):
        self.options, self.allowed = [(v, _tr(t)) for v, t in options], allowed
        f = self.font()
        if self._chars:
            tw = _tw(f, "中") * self._chars
        else:
            tw = max([_tw(f, t) for _v, t in self.options] or [40])
        self.setFixedSize(tw + 2 * 10 + self.ARROW + 6 + self.shadow, _lh(f) + 2 * 5 + 4 + self.shadow)
        self.update()

    def _ok(self, value):
        return self.allowed is None or value in self.allowed

    def text(self):
        cur = self.var.get()
        return next((t for v, t in self.options if v == cur), "—")

    def paintEvent(self, _e):
        p = QPainter(self)
        r = paint_box(p, self.width(), self.height(), (PLAIN_HOVER if self.hovered else WHITE) if self.enabled
                      else DISABLED, 2, self.shadow)
        ax = r.right() + 1 - self.ARROW
        p.fillRect(ax - 2, r.top(), 2, r.height(), qc(INK))
        color = INK if self.enabled else MUTED
        cx, cy = ax + self.ARROW // 2, r.center().y()
        for i in range(4):
            p.fillRect(cx - 4 + i, cy - 2 + i, 8 - 2 * i, 1, qc(color))
        p.setFont(self.font())
        p.setPen(qc(color))
        tr = QRect(r.left() + 10, r.top(), ax - 2 - r.left() - 14, r.height())
        s = _fm(self.font()).elidedText(self.text(), Qt.TextElideMode.ElideRight, tr.width())
        p.drawText(tr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, s)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self.enabled or not self.options:
            return
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setFont(self.font())
        menu.setStyleSheet(
            f"QMenu{{background:{CARD};border:2px solid {INK};padding:2px;}}"
            f"QMenu::item{{padding:5px 18px 5px 12px;color:{INK};background:transparent;}}"
            f"QMenu::item:selected{{background:{MINT};}}"
            f"QMenu::item:disabled{{color:{MUTED};}}")
        menu.setMinimumWidth(self.width() - self.shadow)
        cur = self.var.get()
        for value, label in self.options:
            act = menu.addAction(("■  " if value == cur else "    ") + label)
            act.setData(value)
            act.setEnabled(self._ok(value))
        chosen = menu.exec(self.mapToGlobal(QPoint(0, self.height() - self.shadow)))
        if chosen is None:
            return
        value = chosen.data()
        if value != self.var.get():
            self.var.set(value)
            if self.command:
                self.command(value)


# ---------------------------------------------------------------- 勾选框
class CheckBox(Clickable):

    S = 18

    def __init__(self, parent, text, variable, command=None, under=None, font=None, note=None, radio=False):
        super().__init__(parent)
        self.var, self.command, self.radio = variable, command, radio
        self._text, self._note = _tr(text), _tr(note)
        self.setFont(font or f_zh(10, True))
        self._nfont = f_zh(8)
        self.label = self
        variable.trace(self.update)
        self._resize()

    def config(self, text=None, **_kw):
        text = _tr(text)
        if text is not None and text != self._text:
            self._text = text
            self._resize()
            self.update()

    def _resize(self):
        f = self.font()
        self._lw = _tw(f, self._text) + 6
        w = self.S + 2 + 6 + self._lw
        if self._note:
            w += 4 + _tw(self._nfont, self._note) + 6
        self.setFixedSize(w, max(self.S + 2, _lh(f) + 6))

    def paintEvent(self, _e):
        p = QPainter(self)
        s, b = self.S, 2
        y = (self.height() - (s + 2)) // 2
        fill = WHITE if self.enabled else DISABLED
        dot = INK if self.enabled else MUTED
        if self.radio:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(INK))
            p.drawEllipse(2, y + 2, s, s)
            p.drawEllipse(0, y, s, s)
            p.setBrush(qc(fill))
            p.drawEllipse(b, y + b, s - 2 * b, s - 2 * b)
            if self.var.get():
                p.setBrush(qc(dot))
                p.drawEllipse(5, y + 5, s - 10, s - 10)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        else:
            p.fillRect(2, y + 2, s, s, qc(INK))
            p.fillRect(0, y, s, s, qc(INK))
            p.fillRect(b, y + b, s - 2 * b, s - 2 * b, qc(fill))
            if self.var.get():
                p.fillRect(5, y + 5, s - 10, s - 10, qc(dot))
        x = s + 2 + 6
        p.setFont(self.font())
        p.setPen(qc(INK if self.enabled else MUTED))
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        p.drawText(QRect(x + 3, 0, self._lw, self.height()), left, self._text)
        if self._note:
            p.setFont(self._nfont)
            p.setPen(qc(MUTED))
            p.drawText(QRect(x + self._lw + 4 + 3, 0, self.width(), self.height()), left, self._note)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self.enabled:
            return
        if e.position().x() > self.S + 2 + 6 + self._lw:
            return
        self.var.set(True if self.radio else not bool(self.var.get()))
        if self.command:
            self.command()


# ---------------------------------------------------------------- 输入框
class Entry(Box):

    def __init__(self, parent, variable, width=28, font=None, shadow=3, pad=(8, 5), center=False, expand=False):
        super().__init__(parent, fill=WHITE, shadow=shadow, pad=(pad[0], pad[1], pad[0], pad[1]))
        self.var = variable
        self._self_set = False
        self.widget = self
        self.edit = QLineEdit(self)
        self.edit.setFrame(False)
        self.edit.setFont(font or f_zh(11))
        self.edit.setStyleSheet(f"QLineEdit{{background:transparent;border:none;color:{INK};padding:0px;"
                                f"selection-background-color:{MINT};selection-color:{INK}}}"
                                f"QLineEdit:disabled{{color:{MUTED}}}")
        if center:
            self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay.addWidget(self.edit)
        self.edit.setText(str(variable.get() if variable.get() is not None else ""))
        self.edit.textEdited.connect(self._typed)
        variable.trace(self._pull)
        cw = _tw(self.edit.font(), "0") * width + 4
        if expand:
            self.edit.setMinimumWidth(cw // 3)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.edit.setFixedWidth(cw)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.edit.setFixedHeight(_lh(self.edit.font()) + 2)

    def _typed(self, s):
        self._self_set = True
        try:
            self.var.set(s)
        finally:
            self._self_set = False

    def _pull(self):
        if self._self_set:
            return
        v = self.var.get()
        s = "" if v is None else str(v)
        if s != self.edit.text():
            self.edit.setText(s)

    def set_enabled(self, on):
        self.edit.setEnabled(bool(on))
        self.set_fill(WHITE if on else DISABLED)


# ---------------------------------------------------------------- 数字框
class Stepper(QWidget):

    def __init__(self, parent, variable, lo, hi, step=1, width=4, under=None, command=None, is_float=False):
        super().__init__(parent)
        self.var, self.lo, self.hi, self.step, self.command, self.is_float = variable, lo, hi, step, command, is_float
        self.enabled = True
        self.widget = self
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.minus = Button(self, "−", lambda: self.bump(-1), padx=7, pady=1, shadow=2, font=f_mono(10, True))
        self.box = Entry(self, variable, width=width, font=f_mono(11, True), shadow=2, pad=(4, 3), center=True)
        self.plus = Button(self, "+", lambda: self.bump(1), padx=7, pady=1, shadow=2, font=f_mono(10, True))
        for w in (self.minus, self.box, self.plus):
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)
        self.entry = self.box.edit
        self.entry.editingFinished.connect(self.commit)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _fmt(self, v):
        return ("%g" % v) if self.is_float else str(int(v))

    def value(self):
        try:
            v = float(self.var.get()) if self.is_float else int(float(self.var.get()))
        except (ValueError, TypeError):
            v = self.lo
        return max(self.lo, min(self.hi, v))

    def commit(self):
        v = self.value()
        if self.var.get() != self._fmt(v):
            self.var.set(self._fmt(v))
        if self.command:
            self.command()

    def bump(self, d):
        if not self.enabled:
            return
        self.var.set(self._fmt(max(self.lo, min(self.hi, self.value() + d * self.step))))
        if self.command:
            self.command()

    def set_enabled(self, on):
        self.enabled = bool(on)
        self.minus.set_enabled(on)
        self.plus.set_enabled(on)
        self.box.set_enabled(on)


# ---------------------------------------------------------------- 小部件
class Tag(QWidget):

    def __init__(self, parent, text, fill=YELLOW, font=None):
        super().__init__(parent)
        self._text, self.fill = text, fill
        self.setFont(font or f_pixel(9))
        f = self.font()
        self.setFixedSize(_tw(f, text) + 20 + 4, _lh(f) + 6 + 4)

    def paintEvent(self, _e):
        p = QPainter(self)
        r = paint_box(p, self.width(), self.height(), self.fill, 2, 0)
        p.setFont(self.font())
        p.setPen(qc(INK))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._text)


class Square(QWidget):

    def __init__(self, parent=None, color=DISABLED, size=22):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(size + 4, size + 4)

    def set_color(self, color):
        if color != self.color:
            self.color = color
            self.update()

    def paintEvent(self, _e):
        paint_box(QPainter(self), self.width(), self.height(), self.color, 2, 0)


class Chip(QWidget):

    def __init__(self, parent, title, under=None):
        super().__init__(parent)
        self.title, self.value, self.color = _tr(title), "…", DISABLED
        self.tf, self.vf = f_mono(9, True), f_zh(9, True)
        self._resize()

    def _resize(self):
        tw = _tw(self.tf, self.title) + 6
        vw = _tw(self.vf, self.value) + 16
        h = max(10, _lh(self.tf) + 6, _lh(self.vf) + 8)
        self._geo = (tw, vw, h)
        self.setFixedSize(2 + 8 + 10 + 6 + tw + 2 + vw + 4 + 2, h + 4)

    def set(self, text, color):
        text = _tr(text)
        if (text, color) != (self.value, self.color):
            self.value, self.color = text, color
            self._resize()
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        paint_box(p, self.width(), self.height(), CARD, 2, 0)
        tw, vw, h = self._geo
        x = 2 + 8
        p.fillRect(x, 2 + (h - 10) // 2, 10, 10, qc(self.color))
        x += 10 + 6
        p.setFont(self.tf)
        p.setPen(qc(MUTED))
        p.drawText(QRect(x, 2, tw, h), Qt.AlignmentFlag.AlignCenter, self.title)
        x += tw + 2
        p.setFont(self.vf)
        p.setPen(qc(INK))
        p.drawText(QRect(x, 2, vw, h), Qt.AlignmentFlag.AlignCenter, self.value)


class Card(Box):

    def __init__(self, parent, tag_text, title, fill=YELLOW, under=None, note=None):
        super().__init__(parent, fill=CARD, border=2, shadow=5)
        self.widget = self
        head, hl = hbox(self)
        hl.setContentsMargins(16, 13, 16, 0)
        self.title_lab = Label(title, font=f_zh(12, True), parent=head)
        hl.addWidget(self.title_lab, 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addStretch(1)
        self.note_lab = None
        if note:
            self.note_lab = Label(note, font=f_zh(9), fg=MUTED, parent=head)
            hl.addWidget(self.note_lab, 0, Qt.AlignmentFlag.AlignVCenter)
        self.head_lay = hl
        self.n_rows = 0
        self.lay.addWidget(head)
        self.body = QWidget(self)
        self.blay = QVBoxLayout(self.body)
        self.blay.setContentsMargins(16, 10, 16, 14)
        self.blay.setSpacing(0)
        self.lay.addWidget(self.body)
        self.lay.addStretch(1)

    def add(self, widget, top=0, align=None):
        if top:
            self.blay.addSpacing(top)
        if align is None:
            self.blay.addWidget(widget)
        else:
            self.blay.addWidget(widget, 0, align)
        return widget

    def row(self, name, *controls, help=None, sub=None, name_w=None, credit=None):
        sep = None
        if self.n_rows:
            sep = QWidget()
            sep.setFixedHeight(1)
            filled(sep, DISABLED)
            self.blay.addWidget(sep)
        self.n_rows += 1
        r = HoverRow(name, help)
        r.sep = sep
        lab = Label(name, font=f_zh(11, True))
        if name_w:
            lab.setFixedWidth(name_w)
        r.name_lab = lab
        if credit:
            col = QWidget()
            cl = QVBoxLayout(col)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)
            cl.addWidget(lab)
            cl.addWidget(Label(credit, font=f_zh(8), fg=MUTED))
            r.lay.addWidget(col, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            r.lay.addWidget(lab, 0, Qt.AlignmentFlag.AlignVCenter)
        r.sub = None
        if sub is not None:
            r.sub = sub if isinstance(sub, QWidget) else Label(sub, font=f_zh(9), fg=MUTED)
            r.lay.addSpacing(4)
            r.lay.addWidget(r.sub, 0, Qt.AlignmentFlag.AlignVCenter)
        r.lay.addStretch(1)
        for c in controls:
            if isinstance(c, int):
                r.lay.addSpacing(c)
            elif c is not None:
                r.lay.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
        self.blay.addWidget(r)
        return r


# ---------------------------------------------------------------- 底栏说明
_HINT = {"show": None, "hide": None}


def set_hint_target(show, hide):
    _HINT["show"], _HINT["hide"] = show, hide


def show_hint(title, text):
    title = title() if callable(title) else title
    text = text() if callable(text) else text
    if _HINT["show"] and text:
        text = _tr(text).rstrip()
        if text and text[-1] not in "。！？.!?":
            text += "。" if LANG == "zh" else "."
        _HINT["show"](_tr(title), text)


def hide_hint():
    if _HINT["hide"]:
        _HINT["hide"]()


class _HoverHelp(QObject):
    def __init__(self, widget, title, text):
        super().__init__(widget)
        self.title, self.text = title, text

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.Type.Enter:
            show_hint(self.title, self.text)
        elif ev.type() == QEvent.Type.Leave:
            hide_hint()
        return False


def hover_help(widget, title, text):
    widget.installEventFilter(_HoverHelp(widget, title, text))
    return widget


class HoverRow(QWidget):

    def __init__(self, title="", help_text=None, parent=None):
        super().__init__(parent)
        self.title, self.help = title, help_text
        self.hov = False
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(8, 7, 8, 7)
        self.lay.setSpacing(10)

    def set_help(self, text):
        self.help = text

    def enterEvent(self, _e):
        self.hov = True
        if self.help:
            self.update()
            show_hint(self.title, self.help)

    def leaveEvent(self, _e):
        self.hov = False
        if self.help:
            self.update()
            hide_hint()

    def paintEvent(self, _e):
        if self.hov and self.help:
            p = QPainter(self)
            p.fillRect(self.rect(), qc(PLAIN_HOVER))
            p.fillRect(0, 0, 3, self.height(), qc(YELLOW))


# ---------------------------------------------------------------- 左侧导航
class NavList(QWidget):

    IH, GH, W = 35, 27, 150

    def __init__(self, groups, bottom, command):
        super().__init__()
        self.groups, self.bottom, self.command = groups, bottom, command
        self.cur, self.hover, self.hidden = None, None, set()
        self.setMouseTracking(True)
        self.setFixedWidth(self.W)
        self.f_item, self.f_sel, self.f_group = f_zh(11), f_zh(11, True), f_zh(8, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.off, self.ch = 0, 0
        self.bar = QScrollBar(Qt.Orientation.Vertical, self)
        self.bar.setStyleSheet(
            f"QScrollBar:vertical{{background:transparent;width:7px;margin:0px;border:none}}"
            f"QScrollBar::handle:vertical{{background:{INK};min-height:28px;border:none}}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;border:none;background:none}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none}")
        self.bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bar.valueChanged.connect(self._scrolled)
        self.bar.hide()

    def set_hidden(self, keys):
        self.hidden = set(keys)
        self._sync()
        self.update()

    def select(self, key):
        self.cur = key
        for kind, k, _t, r in self._cells():
            if kind == "i" and k == key:
                if r.top() < self.off:
                    self.bar.setValue(max(0, r.top() - 8))
                elif r.bottom() > self.off + self.height():
                    self.bar.setValue(r.bottom() - self.height() + 8)
        self.update()

    def _scrolled(self, v):
        self.off = v
        self.update()

    def _sync(self):
        self.ch = max((r.bottom() + 1 for _k, _key, _t, r in self._cells()), default=0) + 14
        room = max(0, self.ch - self.height())
        self.bar.setRange(0, room)
        self.bar.setPageStep(self.height())
        self.bar.setSingleStep(self.IH)
        self.off = min(self.off, room)
        self.bar.setValue(self.off)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._sync()

    def wheelEvent(self, e):
        if self.bar.maximum() > 0:
            self.bar.setValue(self.bar.value() - e.angleDelta().y() // 3)
            e.accept()
        else:
            e.ignore()

    def _cells(self):
        out, y, w = [], 16, self.width()
        for title, items in self.groups:
            vis = [it for it in items if it[0] not in self.hidden]
            if not vis:
                continue
            out.append(("g", None, _tr(title), QRect(0, y, w, self.GH)))
            y += self.GH
            for key, text in vis:
                out.append(("i", key, _tr(text), QRect(12, y, w - 12, self.IH)))
                y += self.IH
            y += 6
        vis_b = [it for it in self.bottom if it[0] not in self.hidden]
        yb = max(self.height() - 14, y + 8 + self.IH * len(vis_b))
        for key, text in reversed(vis_b):
            yb -= self.IH
            out.append(("i", key, _tr(text), QRect(12, yb, w - 12, self.IH)))
        return out

    def paintEvent(self, _e):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, qc(HEADER))
        p.translate(0, -self.off)
        h = h + self.off
        sel = None
        for kind, key, text, r in self._cells():
            if kind == "g":
                p.setFont(self.f_group)
                p.setPen(qc(MUTED))
                p.drawText(r.adjusted(24, 0, 0, -5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, text)
                continue
            if key == self.cur:
                sel = (r, text)
                continue
            if key == self.hover:
                p.fillRect(r.adjusted(0, 3, -6, -3), qc(PLAIN_HOVER))
            p.setFont(self.f_item)
            p.setPen(qc(INK))
            p.drawText(r.adjusted(26, 0, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        if sel:
            r = sel[0]
            p.fillRect(w - 2, 0, 2, r.top(), qc(INK))
            p.fillRect(w - 2, r.bottom() + 1, 2, h - r.bottom() - 1, qc(INK))
            p.fillRect(r, qc(PANEL))
            p.fillRect(r.left(), r.top(), r.width(), 2, qc(INK))
            p.fillRect(r.left(), r.bottom() - 1, r.width(), 2, qc(INK))
            p.fillRect(r.left(), r.top(), 2, r.height(), qc(INK))
            cy = r.center().y()
            p.fillRect(r.left() + 12, cy - 5, 10, 10, qc(INK))
            p.fillRect(r.left() + 14, cy - 3, 6, 6, qc(MINT))
            p.setFont(self.f_sel)
            p.setPen(qc(INK))
            p.drawText(r.adjusted(30, 0, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sel[1])
        else:
            p.fillRect(w - 2, 0, 2, h, qc(INK))

    def _at(self, pos):
        pos = QPoint(pos.x(), pos.y() + self.off)
        for kind, key, _t, r in self._cells():
            if kind == "i" and r.contains(pos):
                return key
        return None

    def mouseMoveEvent(self, e):
        k = self._at(e.position().toPoint())
        if k != self.hover:
            self.hover = k
            self.update()

    def leaveEvent(self, _e):
        self.hover = None
        self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        k = self._at(e.position().toPoint())
        if k and k != self.cur:
            self.command(k)


# ---------------------------------------------------------------- 底栏
class Footer(QWidget):

    COLORS = {"ok": MINT, "err": SALMON, "warn": YELLOW, "info": SKY}
    WORD = {"ok": "完成", "err": "没有完成", "warn": "注意", "info": "提示"}
    IDLE = ("就绪", "鼠标停留于选项上，获得更多详细信息")

    def __init__(self):
        super().__init__()
        filled(self, HEADER)
        self.setFixedHeight(72)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 6)
        lay.setSpacing(10)
        col = QWidget()
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(1)
        self.title = ElideLabel("", font=f_zh(10, True))
        self.body = Label("", font=f_zh(9), fg=MUTED, wrap=True)
        self.body.setFixedHeight(QFontMetrics(self.body.font()).lineSpacing() * 2 + 2)
        self._raw_body = ""
        cl.addWidget(self.title)
        cl.addWidget(self.body)
        cl.addStretch(1)
        lay.addWidget(col, 1)
        self.badge = Chip(None, "MODE")
        self.badge.hide()
        lay.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status = (_tr(self.IDLE[0]), _tr(self.IDLE[1]), DISABLED, INK)
        self.hinting = False
        self._show(*self.status)

    def _show(self, title, body, color, fg=INK):
        self.title.config(text=title, fg=fg)
        self._raw_body = (body or "").replace("\n", " ")
        self.body.config(text=self._fit(self._raw_body))

    def _fit(self, text):
        fm = QFontMetrics(self.body.font())
        w = max(200, self.body.width() or self.width() - 60)
        return fm.elidedText(text, Qt.TextElideMode.ElideRight, int(w * 2 - fm.averageCharWidth() * 6))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.body.config(text=self._fit(self._raw_body))

    def hint(self, title, body):
        self.hinting = True
        self._show(title, body, YELLOW)

    def unhint(self):
        self.hinting = False
        self._show(*self.status)

    def set_badge(self, text, color=YELLOW):
        if text:
            self.badge.set(text, color)
        self.badge.setVisible(bool(text))

    def say(self, text, kind="info"):
        text = (_tr(text) or "").replace("\n", " ")
        fg = {"err": BAD, "warn": WARN}.get(kind, INK)
        color = self.COLORS.get(kind, SKY)
        if len(text) <= 34:
            self.status = (text, "", color, fg)
        else:
            self.status = (_tr(self.WORD.get(kind, "提示")), text, color, fg)
        if not self.hinting:
            self._show(*self.status)


class MessageDialog(QDialog):

    TITLES = {"ask": "确认", "warn": "注意", "error": "没有完成", "info": "提示"}
    COLORS = {"ask": YELLOW, "warn": YELLOW, "error": SALMON, "info": SKY}

    def __init__(self, parent, text, kind="info", ok="确定", cancel=None, second=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.result_ok = False
        self.choice = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = Box(self, fill=CARD, border=2, shadow=6, pad=(20, 16, 20, 16))
        outer.addWidget(box)
        head, hl = hbox()
        hl.addWidget(Label(self.TITLES.get(kind, "提示"), font=f_zh(12, True)), 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addStretch(1)
        box.lay.addWidget(head)
        box.lay.addSpacing(12)
        msg = Label(_tr(text), font=f_zh(10), wrap=True)
        msg.setMinimumWidth(px(360))
        msg.setMaximumWidth(px(520))
        box.lay.addWidget(msg)
        box.lay.addSpacing(18)
        row, rl = hbox(spacing=10)
        rl.addStretch(1)
        self.btn_ok = Button(None, ok, self._ok, kind="danger" if kind == "error" and not cancel else "accent")
        rl.addWidget(self.btn_ok)
        if second:
            rl.addWidget(Button(None, second, self._second, kind="accent"))
        if cancel:
            rl.addWidget(Button(None, cancel, self.reject))
        box.lay.addWidget(row)

    def _ok(self):
        self.result_ok = True
        self.choice = "ok"
        self.accept()

    def _second(self):
        self.choice = "second"
        self.accept()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._ok()
        else:
            super().keyPressEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        self.adjustSize()
        par = self.parentWidget()
        if par is not None:
            win = par.window()
            c = win.mapToGlobal(win.rect().center())
            self.move(c.x() - self.width() // 2, c.y() - self.height() // 2)


def message(parent, text, kind="info", ok="确定", cancel=None):
    d = MessageDialog(parent, text, kind, ok, cancel)
    d.exec()
    return d.result_ok


def choose(parent, text, first, second, cancel="取消", kind="ask"):
    d = MessageDialog(parent, text, kind, first, cancel, second=second)
    d.exec()
    return {"ok": "first", "second": "second"}.get(d.choice)


LEFT = Qt.AlignmentFlag.AlignLeft
CENTER = Qt.AlignmentFlag.AlignHCenter
TOP = Qt.AlignmentFlag.AlignTop
RIGHT = Qt.AlignmentFlag.AlignRight


def chars(font, n):
    return _tw(font, "0") * n + 6


def line(*items, stretch=True):
    w, lay = hbox()
    w.lay = lay
    for x in items:
        if isinstance(x, int):
            lay.addSpacing(x)
        elif x == "<>":
            lay.addStretch(1)
        else:
            lay.addWidget(x, 0, Qt.AlignmentFlag.AlignVCenter)
    if stretch:
        lay.addStretch(1)
    return w


# ---------------------------------------------------------------- 点阵页面
class _DotCanvas(QWidget):
    STEP = 16

    def __init__(self):
        super().__init__()
        self._tile = None
        self._tile_dpr = None

    def _make_tile(self):
        dpr = self.devicePixelRatioF()
        if self._tile is None or self._tile_dpr != dpr:
            s = self.STEP
            pm = QPixmap(int(round(s * dpr)), int(round(s * dpr)))
            pm.setDevicePixelRatio(dpr)
            pm.fill(qc(PANEL))
            p = QPainter(pm)
            c = s // 2 - 1
            p.fillRect(c, c, 2, 2, qc(DOT))
            p.end()
            self._tile, self._tile_dpr = pm, dpr
        return self._tile

    def paintEvent(self, e):
        p = QPainter(self)
        r = e.rect()
        s = self.STEP
        x0, y0 = r.x() - r.x() % s, r.y() - r.y() % s
        p.drawTiledPixmap(QRect(x0, y0, r.right() - x0 + 1 + s, r.bottom() - y0 + 1 + s), self._make_tile())


class DotPage(QScrollArea):

    PAD, GAP = 22, 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        filled(self, PANEL)
        self.canvas = _DotCanvas()
        self.vlay = QVBoxLayout(self.canvas)
        self.vlay.setContentsMargins(self.PAD, self.PAD, self.PAD, self.PAD)
        self.vlay.setSpacing(self.GAP)
        self.vlay.addStretch(1)
        self.setWidget(self.canvas)
        filled(self.viewport(), PANEL)
        sb = self.verticalScrollBar()
        sb.setSingleStep(40)
        self.bar = QScrollBar(Qt.Orientation.Vertical, self)
        self.bar.setStyleSheet(
            f"QScrollBar:vertical{{background:transparent;width:7px;margin:0px;border:none}}"
            f"QScrollBar::handle:vertical{{background:{INK};min-height:28px;border:none}}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;border:none;background:none}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none}")
        self.bar.setCursor(Qt.CursorShape.PointingHandCursor)
        sb.rangeChanged.connect(self._sync_bar)
        sb.valueChanged.connect(self.bar.setValue)
        self.bar.valueChanged.connect(sb.setValue)
        self.bar.hide()

    def _sync_bar(self, lo, hi):
        sb = self.verticalScrollBar()
        self.bar.setRange(lo, hi)
        self.bar.setPageStep(sb.pageStep())
        self.bar.setSingleStep(sb.singleStep())
        self.bar.setValue(sb.value())
        self.bar.setVisible(hi > lo)
        self._place_bar()

    def _place_bar(self):
        top = self._pin_h()
        self.bar.setGeometry(self.width() - 11, top + 4, 7, max(10, self.height() - top - 8))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_pin()
        self._place_bar()

    # ---- 顶上固定区
    def pin(self, *widgets):
        holder = QWidget(self)
        filled(holder, PANEL)
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(self.PAD, 14, self.PAD, 12)
        lay.setSpacing(10)
        for w in widgets:
            lay.addWidget(w)
        line = ink_line(2)
        line.setParent(holder)
        holder.line = line
        self.pinned, self.pin_lay = holder, lay
        holder.installEventFilter(self)
        self._place_pin()
        return holder

    def _pin_h(self):
        h = getattr(self, "pinned", None)
        return h.sizeHint().height() if h is not None and not h.isHidden() else 0

    def _place_pin(self):
        h = getattr(self, "pinned", None)
        if h is None:
            return
        ph = self._pin_h()
        self.setViewportMargins(0, ph, 0, 0)
        if ph:
            h.setGeometry(0, 0, self.width(), ph)
            h.line.setGeometry(0, ph - 2, self.width(), 2)
            h.raise_()
            self.bar.raise_()

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if obj is getattr(self, "pinned", None) and ev.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Show,
                                                                    QEvent.Type.Hide):
            ui_after = after
            ui_after(0, lambda: (self._place_pin(), self._place_bar()))
        return super().eventFilter(obj, ev)

    def row(self, *widgets, weights=None):
        weights = weights or [1] * len(widgets)
        w, lay = hbox(self.canvas, spacing=self.GAP)
        for child, wt in zip(widgets, weights):
            child.setParent(w)
            sp = child.sizePolicy()
            sp.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            sp.setHorizontalStretch(int(wt))
            child.setSizePolicy(sp)
            lay.addWidget(child, int(wt))
        self.vlay.insertWidget(self.vlay.count() - 1, w)
        return w

    def yview_moveto(self, frac):
        sb = self.verticalScrollBar()
        sb.setValue(int(sb.minimum() + frac * (sb.maximum() - sb.minimum())))


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())
