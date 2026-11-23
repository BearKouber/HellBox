"""
快捷语音：进关后按 F5～F8（手柄长按十字键）播报游戏自带语音，设置在 mod/src/hellbox_qol.lua 的 voice 部分。
"""
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

import hellbox_options as options
import ui
from pages.base import Page
from pages.options_widgets import apply
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

VOICE_OPTIONS = list(options.VOICE.items())
VC = Qt.AlignmentFlag.AlignVCenter
PAD = {5: "↑", 6: "↓", 7: "←", 8: "→"}


class KeyCap(QWidget):

    def __init__(self, text):
        super().__init__()
        self._text = text
        self.setFont(ui.f_pixel(11))
        self.setFixedSize(54, 44)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(0, 0, 54, 44, ui.qc(ui.INK))
        p.fillRect(2, 2, 50, 34, ui.qc(ui.YELLOW))
        p.fillRect(2, 36, 50, 6, ui.qc("#c9a43a"))
        p.setFont(self.font())
        p.setPen(ui.qc(ui.INK))
        p.drawText(QRect(2, 2, 50, 34), Qt.AlignmentFlag.AlignCenter, self._text)


class VoicePage(Page):
    key = "voice"
    tab = "语音"
    when = "游戏运行时也能修改，立即生效"

    def build(self):
        cfg = options.load()
        card = ui.Card(self.view, "VOICE", "快捷语音", fill=ui.MINT)
        self.enabled = ui.Var(cfg["voice"])
        self.toggle = ui.Toggle(None, self.enabled, command=lambda: apply(self.app, {"voice": bool(self.enabled.get())}))
        card.row("快捷语音", self.toggle, sub="键鼠按 F5～F8，手柄长按十字键",
                 help="键鼠按 F5～F8、手柄按住十字键半秒，播放下面设置好的语音。F1～F4 和十字键单击仍是原版（是 / 否 / 留守 / 移动）。")
        self.vars, self.boxes = {}, {}
        for i in range(5, 9):
            key = f"voice{i}"
            var = ui.Var(cfg[key])
            box = ui.Dropdown(None, VOICE_OPTIONS, var, width=9,
                              command=lambda value, key=key: apply(self.app, {key: value}))
            self.vars[key], self.boxes[key] = var, box
            card.row(T("F{0} / 手柄 {1}", i, PAD[i]), box,
                     help=T("键鼠按 F{0}，或手柄按住十字键 {1} 半秒，喊这一句。", i, PAD[i]))
        self.view.row(card)

    def sync(self):
        cfg = options.load()
        live = self.app.mod_on() and not self.app.busy
        self.toggle.set_enabled(live)
        if not self.app.busy and self.enabled.get() != cfg["voice"]:
            self.enabled.set(cfg["voice"])
        for key, box in self.boxes.items():
            box.set_enabled(live and cfg["voice"])
            if self.vars[key].get() != cfg[key]:
                self.vars[key].set(cfg[key])
