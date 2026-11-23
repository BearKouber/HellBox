"""
页面基类：子类填 key、tab、when，在 build() 里往 self.view 加卡片；sync() 在状态变化时重算控件，set_dev() 响应开发者模式开关。
"""

import ui


class Page:

    key = ""
    tab = ""
    when = ""
    when_color = ui.MINT

    def __init__(self, app, parent):
        self.app = app
        self.view = ui.DotPage(parent)
        head, hl = ui.hbox()
        VC = ui.Qt.AlignmentFlag.AlignVCenter
        self.head_title = ui.Label(self.tab, font=ui.f_zh(16, True))
        hl.addWidget(self.head_title, 0, VC)
        hl.addSpacing(18)
        self.when_sq = ui.Square(None, self.when_color, 9)
        hl.addWidget(self.when_sq, 0, VC)
        hl.addSpacing(7)
        self.when_lab = ui.ElideLabel("", font=ui.f_zh(10), fg=ui.MUTED)
        hl.addWidget(self.when_lab, 1, VC)
        hl.addSpacing(10)
        self.when_sq.setVisible(True)
        self.head_lay = hl
        self.view.pin(head)
        self.build()

    def set_when(self, text, color=None):
        pass

    def build(self):
        pass

    def sync(self):
        pass

    def on_show(self):
        pass

    def set_dev(self, on):
        pass
