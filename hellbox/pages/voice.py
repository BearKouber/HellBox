"""快捷语音：进关后按 F5～F8（手柄长按十字键 上下左右）喊一句游戏自带的语音（mod 里是 src/hellbox_qol.lua 的 voice 部分）。

2026-11-13 用户说原来的下拉框太丑：改成四个键帽 + 方块下拉框，和其他页一个风格。
2026-11-21 HD1-038：来自 QoL Mod 的「快捷语音冷却」「换弹语音别太吵」删了。
"""
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

import hellbox_options as options
import ui
from pages.base import Page
from pages.options_widgets import apply
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

VOICE_OPTIONS = list(options.VOICE.items())
VC = Qt.AlignmentFlag.AlignVCenter
PAD = {5: "↑", 6: "↓", 7: "←", 8: "→"}  # 手柄：长按十字键这个方向 = 这个 F 键


class KeyCap(QWidget):
    """一个键帽（F5 这种）：黄底黑边、下沿厚一点，像键盘上的键。"""

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
    when = "游戏开着也能改，马上生效"

    def build(self):
        cfg = options.load()
        # 2026-11-15 新界面：一行一个键，原来的「说明」卡拆进每行的说明（鼠标停上去看）
        card = ui.Card(self.view, "VOICE", "快捷语音", fill=ui.MINT)
        self.enabled = ui.Var(cfg["voice"])
        self.toggle = ui.Toggle(None, self.enabled, command=lambda: apply(self.app, {"voice": bool(self.enabled.get())}))
        card.row("快捷语音", self.toggle, sub="键鼠按 F5～F8，手柄长按十字键",
                 help="键鼠按 F5～F8、手柄按住十字键半秒，喊下面设好的话。F1～F4 和十字键点一下还是原版"
                      "（是 / 否 / 留守 / 移动）。")
        self.vars, self.boxes = {}, {}
        for i in range(5, 9):
            key = f"voice{i}"
            var = ui.Var(cfg[key])
            box = ui.Dropdown(None, VOICE_OPTIONS, var, width=9,
                              command=lambda value, key=key: apply(self.app, {key: value}))
            self.vars[key], self.boxes[key] = var, box
            card.row(T("F{0}　/　手柄 {1}", i, PAD[i]), box,
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
