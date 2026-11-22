"""「显示」页（2026-11-20 HD1-035）：只改自己画面的东西——军械库 / 百科数值、状态提示、名字、画面。
同日用户：「给增强 hud 全部删除……准星那个也删除，我们的指针已经很完善了」。

用户 2026-11-20：「其他文字显示什么的感觉也可以加到功能里面了」「都做到功能里面」。
功能来自 HalfSugar 的 HelldiversOptimization，全部热生效（hop.txt）。
「功能」页已经很长，显示类单独一页，和「功能」挨着。
2026-11-21 HD1-038 用户定：来自 QoL Mod 的全部删掉（QoL 作者希望两个 MOD 各自独立、能一起装），「画面」那组整组没了。
2026-11-22 用户：「资料和状态」那组（军械库显示真实数值、显示身上的状态）也是 QoL 的，整组删了。
"""
import ui
from pages.base import Page
from pages.hop_rows import HALFSUGAR, HopRows


class DisplayPage(Page):
    key = "display"
    tab = "显示"
    when = "游戏开着也能改，下一秒生效；只改你自己的画面"

    def build(self):
        h = self.hop = HopRows(self)

        self.off_card = ui.Box(None, fill=ui.SALMON, border=2, shadow=4, pad=(14, 10, 14, 10), vertical=False)
        self.off_card.lay.addWidget(ui.Label("「核心」没开，这页的功能都用不了。", font=ui.f_zh(10, True)), 0,
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
