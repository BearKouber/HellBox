"""
显示页：只调整自己画面的显示（军械库 / 百科数值、状态提示、名字），功能来自 HalfSugar 的 HelldiversOptimization，全部热生效。
"""
import build
import hellbox_options as options
import ui
from pages.base import Page
from pages.hop_rows import HALFSUGAR, HopRows, numbers
from pages.options_widgets import apply
try:
    from i18n import tr
except ImportError:
    def tr(s):
        return s

LHGRZR = "来自 Lhgrzr"
OCT = "来自 Oct0pu5"
DH_YIELD = "此项已由 DH 提供"
PING_WINDOWS = [(n, f"{n} 次") for n in options.PING_WINDOWS]


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
        # 2026-11-26 用户：「名字加深色底」删了；「长名字不乱码」改成「名字不乱码」，同一个开关加上字体缺字改用聊天字体（src/hellbox_name_font.lua）
        h.toggle(names, "long_text", "名字不乱码", "游戏字体只有游戏自己用到的字，名字里有别的字（比如「龙」「喵」、韩文）在头顶、状态栏、消息、"
                 "加载页、结算页、ESC 菜单里会变成乱码或问号。开着时这段名字改用聊天框的字体画，原版能显示的字不变；名字太长被截短时也按整个字截。",
                 credit=HALFSUGAR)
        self.view.row(names)

        # ---- 自己（2026-11-26 用户要：本机潜兵更亮；拖动条；热修改。盔甲着色器没有底色亮度，用户选「边缘反光加强」）
        #      2026-11-27 用户：拖动条上限 100% → 200%
        me = ui.Card(self.view, "ME", "自己", fill=ui.MINT)
        bright = h.steps("self_bright_percent", numbers(5, 200, 5, "%"), needs="self_bright", width=200)
        h.toggle(me, "self_bright", "潜兵调亮",
                 "把你自己的潜兵调亮一些（本机所有玩家都算，键盘和手柄都包括），在一群人里更好找。"
                 "做法是加强盔甲的边缘反光，轮廓和侧面更亮；拖动条调强弱，游戏开着也能调。只影响你自己的画面。",
                 extras=(bright,))
        self.view.row(me)

        # ---- 任务画面（2026-11-26 用户：「隐藏样本描边」「HUD 显示延迟」从「功能」页挪过来；设置还是 options 那两项，热生效）
        cfg = options.load()
        hud = ui.Card(self.view, "HUD", "任务画面", fill=ui.SALMON)
        self.samples = ui.Var(cfg["hide_samples"])
        self.samples_toggle = ui.Toggle(None, self.samples, command=lambda: self._flag("hide_samples", self.samples))
        hud.row("隐藏样本描边", self.samples_toggle, help="样本发光轮廓不显示。", credit=LHGRZR)
        self.ping = ui.Var(cfg["dh_ping"])
        self.ping_toggle = ui.Toggle(None, self.ping, command=lambda: self._flag("dh_ping", self.ping))
        self.ping_window = ui.Var(cfg["ping_window"] if cfg["ping_window"] in options.PING_WINDOWS else 5)
        self.seg_ping = ui.Segmented(None, PING_WINDOWS, self.ping_window,
                                     command=lambda v: apply(self.app, {"ping_window": int(v)}),
                                     font=ui.f_zh(9, True), padx=7, pady=2, shadow=2)
        self.ping_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self.ping_note.setVisible(False)
        hud.row("HUD 显示延迟", self.seg_ping, 6, self.ping_toggle, help="在队友的状态卡片下标注延迟，右边选取最近几次的平均。",
                sub=self.ping_note, credit=OCT)
        self.view.row(hud)

    def _flag(self, key, var):
        apply(self.app, {key: bool(var.get())})

    def sync(self):
        on = self.app.mod_on()
        live = on and not self.app.busy
        self.off_row.setVisible(self.app.state["script"] is not None and not on)
        self.hop.sync(live)
        if self.app.busy:
            return
        cfg = options.load()
        dh = build.dive_harder_on()  # 装了 Dive Harder 时延迟显示由它自己提供
        for var, val in ((self.samples, cfg["hide_samples"]), (self.ping, cfg["dh_ping"]),
                         (self.ping_window, cfg["ping_window"] if cfg["ping_window"] in options.PING_WINDOWS else 5)):
            if var.get() != val:
                var.set(val)
        self.samples_toggle.set_enabled(live)
        self.ping_toggle.set_enabled(live and not dh)
        self.seg_ping.set_enabled(live and cfg["dh_ping"] and not dh)
        text = tr(DH_YIELD) if dh else ""
        if self.ping_note.text() != text:
            self.ping_note.config(text=text)
            self.ping_note.setVisible(bool(text))
