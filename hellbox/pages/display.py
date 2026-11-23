"""
显示页：只调整自己画面的显示（军械库 / 百科数值、状态提示、名字），功能来自 HalfSugar 的 HelldiversOptimization，全部热生效。
"""
import ui
from pages.base import Page
from pages.hop_rows import HALFSUGAR, HopRows


class DisplayPage(Page):
    key = "display"
    tab = "显示"
    when = "游戏运行时也能修改，立即生效；只影响你自己的画面"

    def build(self):
        h = self.hop = HopRows(self)

        self.off_card = ui.Box(None, fill=ui.SALMON, border=2, shadow=4, pad=(14, 10, 14, 10), vertical=False)
        self.off_card.lay.addWidget(ui.Label("「核心」未开启，本页功能不可用。", font=ui.f_zh(10, True)), 0,
                                    ui.Qt.AlignmentFlag.AlignVCenter)
        self.off_card.lay.addStretch(1)
        self.off_card.lay.addWidget(ui.Button(None, "去「关于」打开", lambda: self.app.show_page("about"),
                                              font=ui.f_zh(9, True), padx=9, pady=2, shadow=2), 0,
                                    ui.Qt.AlignmentFlag.AlignVCenter)
        self.off_row = self.view.row(self.off_card)

        # ---- 名字
        names = ui.Card(self.view, "NAMES", "名字", fill=ui.SKY)
        h.toggle(names, "name_background", "名字加深色底", "头顶名字下面垫一块深色底，亮地面上也看得清。", credit=HALFSUGAR)
        h.toggle(names, "long_text", "长名字不乱码", "名字太长被截短时按整个字截，不会截出半个汉字的乱码。", credit=HALFSUGAR)
        self.view.row(names)

    def sync(self):
        on = self.app.mod_on()
        self.off_row.setVisible(self.app.state["script"] is not None and not on)
        self.hop.sync(on and not self.app.busy)
