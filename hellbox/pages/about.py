"""关于页（2026-11-15 新界面）：版本、设置（核心开关、开发者模式、游戏位置）、出问题了、鸣谢。

开发者模式藏起来（2026-11-15 用户要求）：在版本号上连点 10 次打开，打开后「设置」里才看得到它的开关；
关掉开关，这一行也跟着藏回去。
"""
import os
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

import logbook
import ui
from pages import data_blocks as db
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

TAPS = 10          # 连点几次打开开发者模式
TAP_GAP = 1.5      # 两次点击最多隔几秒，超过就从头数

AUTHOR = "07"      # 2026-11-19 用户定的作者名（MOD 开发者）
HOME_URL = "https://www.nexusmods.com/helldivers/mods/63"  # 发布页（2026-11-19 用户给的 N 网页面；空着就不显示这一行）
SOURCE_URL = "https://github.com/BearKouber/HellBox"  # 源码（2026-11-21 HD1-037 开源，MIT）
# 鸣谢（2026-11-19 用户给的名单，顺序照原文）
THANKS = [
    ("外层 UI 设计", "91"),
    ("高难增强数据指导", "吃大份"),
    ("分屏、聊天输入法防闪退", "HalfSugar"),  # 2026-11-19 用户要求：半糖的功能贡献单开一行
    # 2026-11-20 用户要求写进鸣谢（同日增强 HUD 整个删掉，Alomare 那行也删）；2026-11-21 HD1-038：QoL 的功能删了，
    #   名字原来误写 SomeDogge；Dive Harder 作者同意收进它的几项，加一行
    ("QoL Mod", "SomeDoggo"),
    ("Dive Harder（延迟显示、隐藏目标、好友列表刷新）", "Oct0pu5"),
    ("协助测试", "91、HalfSugar、吃大份、K-ON!、Kent、QiQi"),
    ("总体 UI 规划、代码设计", "Claude"),
]
NOTICE = ("· HellBox 完全免费，按 MIT 授权开源，源码在 GitHub：github.com/BearKouber/HellBox。如果你是花钱买到的，请找卖家退款。\n"
          "· 可以自由修改、再发布，但请保留作者 07 的署名和授权说明（LICENSE.txt），并注明原发布页。\n"
          "· 收录的别人的作品（比如分屏、半糖的优化功能、Dive Harder 的几项）归原作者，转发时请一并注明。\n"
          "· 非官方 MOD，和游戏官方无关。用 MOD 有风险，出了问题可以点上面的「恢复原版」。\n"
          "· 用到的开源组件：Python、PySide6 / Qt（LGPL-3.0）、LuaJIT、Silkscreen 字体，授权说明见 LICENSE.txt。")
CLOSING = ("希望大家能在游戏里找到它本身的乐趣，也希望这个工具能让你玩得开心。\n"
           "请不要滥用，不要影响别的玩家的体验。")


class VersionLabel(ui.Label):
    """版本号：点了数次数（开发者模式的暗门）。"""

    def __init__(self, text, on_tap):
        super().__init__(text, font=ui.f_zh(9), fg=ui.MUTED)
        self.on_tap = on_tap

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.on_tap()


class AboutPage(Page):
    key = "about"
    tab = "关于"
    when = "版本、设置、出问题怎么办"
    when_color = ui.DISABLED

    def build(self):
        a = self.app
        self.taps, self.last_tap = 0, 0.0
        note = " ".join(x for x in (a.version, tr(a.version_note)) if x)
        info = ui.Card(self.view, "HELLBOX", "HellBox", fill=ui.YELLOW)
        info.head_lay.addWidget(VersionLabel(note, self.tap), 0, Qt.AlignmentFlag.AlignVCenter)
        info.add(ui.text(info.body, "HELLDIVERS（1 代）MOD 工具：带箱子上车、给好友点赞、刷新星球、选图、玩法、数据修改、指针、语音、战绩等。"))
        info.add(ui.text(info.body, "1.0 正式版。遇到问题欢迎反馈。", muted=True, size=9), top=6)
        # 2026-11-19 用户定：作者名 07；以后发到 Nmod，链接补进 HOME_URL 就会多出「发布页」一行
        info.row("作者", ui.Label(AUTHOR, font=ui.f_zh(11, True)), help="HellBox 的作者（MOD 开发者）。")
        if HOME_URL:
            info.row("发布页", ui.Button(None, "去看看", self._open_home, font=ui.f_zh(9, True), padx=9, pady=2, shadow=2),
                     sub=HOME_URL, help="HellBox 的发布页：下载新版、看更新说明、反馈问题。")
        info.row("源码", ui.Button(None, "去看看", self._open_source, font=ui.f_zh(9, True), padx=9, pady=2, shadow=2),
                 sub=SOURCE_URL, help="HellBox 的源码（MIT 授权，开源）：可以自己看、改、编译，也能在那里反馈问题。")
        self.view.row(info)

        s = ui.Card(self.view, "SET", "设置", fill=ui.MINT)
        self.core_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        s.row("核心", a.master, sub=self.core_note,
              help="HellBox 所有功能的总开关。打开 = 把 HellBox 的脚本和指针装进游戏；关闭 = 游戏换回原版文件。"
                   "要先关游戏才能拨。")
        # 2026-11-19 用户要：K-ON!增强UI定制版，一直看得到（和藏起来的开发者模式不一样）
        self.kon_var = ui.Var(a.kon)
        s.row("K-ON!增强UI定制版", ui.Toggle(None, self.kon_var, command=self._kon_flip),
              sub="只留 功能 / 玩法 / 数据 / 指针 / 关于",
              help="打开后左边只有「功能」「玩法」「数据」「指针」「关于」五页，别的页面藏起来（开着开发者模式也一样）。"
                   "只是界面变简单，已经设好的功能在游戏里照常生效。关掉就回到原来的样子。")
        self.dev_var = ui.Var(a.dev)
        self.dev_row = s.row("开发者模式", ui.Toggle(None, self.dev_var, command=self._dev_flip),
                             help=("打开后：数据页能按单只怪、单把枪、单个战略配备细改，存成几块换着用；左边多出「选图」「分屏」「潜兵」「日志」。"
                                   "关掉后这一行会藏起来。") if db.FULL else
                             ("打开后：数据页能按单只怪、单个出怪来源细改，存成几块换着用；左边多出「选图」「分屏」「潜兵」「日志」。"
                              "关掉后这一行会藏起来。"))
        self.dev_row.setVisible(a.dev)
        self.where = ui.Label("", font=ui.f_mono(9), fg=ui.MUTED)
        self.btn_open = ui.Button(None, "打开文件夹", self._open_game, font=ui.f_zh(9, True), padx=9, pady=2, shadow=2)
        s.row("游戏位置", self.btn_open, sub=self.where, help="HellBox 自己找到的游戏文件夹。")
        self.view.row(s)

        h = ui.Card(self.view, "HELP", "出问题了", fill=ui.SALMON)
        h.row("发给作者", ui.Button(None, "复制诊断信息", self._copy_diag, kind="accent", font=ui.f_zh(9, True),
                                  padx=9, pady=2, shadow=2),
              help="把版本、游戏状态和最近的日志一起复制下来，反馈问题时直接粘贴就行。")
        self.vanilla_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        h.row("游戏文件认不出", a.btn_vanilla, sub=self.vanilla_note,
              help="游戏文件被别的 MOD 或其他版本的 HellBox 改过时，HellBox 为安全起见不动它。"
                   "点「恢复原版」：有原版备份就直接换回，没有就让 Steam 检查修复游戏文件。")
        h.row("卸载", ui.Label("关游戏 → 关掉「核心」→ 删掉 HellBox 文件夹", font=ui.f_zh(9), fg=ui.MUTED))
        self.view.row(h)

        # 2026-11-19 用户给的鸣谢名单；以前这里写的分屏 / QoL Mod 挪到对应功能下面（分屏页、功能页、语音页的灰色小字）
        t = ui.Card(self.view, "THANKS", "鸣谢", fill=ui.TAN, note="借鉴别人的功能，来源写在那个功能下面")
        for role, names in THANKS:
            t.row(role, ui.Label(names, font=ui.f_zh(10, True)))
        # 声明（2026-11-19 用户要求「写上限制意思一下」）
        d = ui.Card(self.view, "NOTICE", "声明", fill=ui.SKY)
        d.add(ui.text(d.body, NOTICE, size=9))
        self.view.row(t)
        self.view.row(d)

        # 写在最后（用户原话的意思，署名 07）
        last = ui.Card(self.view, "LAST", "写在最后", fill=ui.MINT)
        last.add(ui.text(last.body, CLOSING, size=10))
        last.add(ui.Label("—— " + AUTHOR, font=ui.f_zh(10, True), fg=ui.MUTED), top=4, align=Qt.AlignmentFlag.AlignRight)
        self.view.row(last)

    # ---------------------------------------------------------------- 开发者模式
    def tap(self):
        now = time.monotonic()
        self.taps = self.taps + 1 if now - self.last_tap <= TAP_GAP else 1
        self.last_tap = now
        if self.app.dev:
            if self.taps >= 3:
                self.app.say("开发者模式已经开着（在「设置」里关）。", "info")
            return
        left = TAPS - self.taps
        if left <= 0:
            self.taps = 0
            self.dev_var.set(True)
            self._dev_flip()
        elif left <= 5:
            self.app.say(T("再点 {0} 次打开开发者模式。", left), "info")

    def _dev_flip(self):
        on = bool(self.dev_var.get())
        self.app.set_dev(on)
        self.dev_row.setVisible(on)
        self.app.say("开发者模式已打开：数据页能细改了，左边多了「选图」「分屏」「潜兵」「日志」。" if on else "开发者模式已关闭。", "ok")

    def _kon_flip(self):
        on = bool(self.kon_var.get())
        self.app.set_kon(on)
        self.app.say("K-ON!增强UI定制版已打开：左边只留 功能 / 玩法 / 数据 / 指针 / 关于。" if on else "K-ON!增强UI定制版已关闭。", "ok")

    def set_dev(self, on):
        if self.dev_var.get() != on:
            self.dev_var.set(on)
        self.dev_row.setVisible(on)

    # ---------------------------------------------------------------- 其他
    def _open_home(self):
        import webbrowser
        webbrowser.open(HOME_URL)

    def _open_source(self):
        import webbrowser
        webbrowser.open(SOURCE_URL)

    def _open_game(self):
        d = self.app.state.get("game_dir")
        if d and os.path.isdir(d):
            os.startfile(d)

    def _copy_diag(self):
        st = self.app.state
        head = [f"HellBox {self.app.version} {self.app.version_note}",
                f"script={st.get('script')} cursor={st.get('cursor')} running={st.get('running')}",
                f"game_dir={st.get('game_dir')}", f"dev={self.app.dev}", ""]

        def work():
            from pages.logs import line
            return [line(r) for r in logbook.entries()[-200:]]

        def done(ok, lines):
            text = "\n".join(head + (lines if ok else [f"(读日志失败：{lines})"]))
            QGuiApplication.clipboard().setText(text)
            self.app.say("诊断信息已复制，直接粘贴到群里就行。", "ok")

        self.app.bg(work, done)

    def sync(self):
        st = self.app.state
        self.where.config(text=st.get("game_dir") or "…")
        self.btn_open.set_enabled(bool(st.get("game_dir")))
        note = self.app.master_note()
        bad = st.get("script") in ("off", "unknown")
        self.core_note.config(text=note, fg=ui.BAD if bad else ui.MUTED)
        unknown = "unknown" in (st.get("script"), st.get("cursor"))
        self.vanilla_note.config(text="认不出：点右边恢复" if unknown else "现在没问题",
                                 fg=ui.BAD if unknown else ui.MUTED)
