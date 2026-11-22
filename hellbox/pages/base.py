import ui


class Page:
    """一页。子类填 key（内部名）、tab（导航上的字），在 build() 里往 self.view 加卡片。

    2026-11-15 新界面：每页顶上固定一行 = 页面名 + 这页什么时候生效（when / when_color），
    右边可以放按钮（self.head_lay）；运行中要改这行用 self.set_when(文字, 颜色)。
    页面里不再用「?」：卡片一行一个设置用 card.row(名字, 控件…, help=说明)，鼠标停上去说明显示在底栏。

    self.app.state  = {"running": 游戏开没开, "script": 脚本 mod 状态, "cursor": 指针 mod 状态, "game_dir": ...}
    self.app.busy   = 有改游戏文件的操作在跑
    self.app.run(action, ok_msg)  跑会改游戏文件的操作（一次一个，跑时全部按钮变灰）
    self.app.bg(work, done)       后台跑不改文件的事（读取之类）
    self.app.say(文字, "ok"/"err"/"warn"/"info")  底栏提示
    self.app.after(毫秒, fn)       过一会儿在界面线程调 fn（代替 tk 的 after）
    self.app.warn / error / ask(文字)  弹窗（ask 返回 True/False）
    self.app.dev    = 开发者模式开着没有

    界面是 Qt（PySide6）：控件都从 ui 里拿（ui.Card、ui.Button、ui.Var……），卡片用 card.add(控件, top=间距) 往下加，
    self.view.row(卡片1, 卡片2, weights=(2, 1)) 排一行。不要直接用 QWidget 的 setEnabled，用控件的 set_enabled。
    """

    key = ""
    tab = ""
    when = ""             # 顶上那行：这页什么时候生效
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
        self.when_lab = ui.ElideLabel(self.when, font=ui.f_zh(10), fg=ui.MUTED)
        hl.addWidget(self.when_lab, 1, VC)
        hl.addSpacing(10)
        self.when_sq.setVisible(bool(self.when))
        self.head_lay = hl
        self.view.pin(head)
        self.build()

    def set_when(self, text, color=None):
        self.when_lab.config(text=text, fg=ui.MUTED)
        self.when_sq.set_color(color or self.when_color)
        self.when_sq.setVisible(bool(text))

    def build(self):
        pass

    def sync(self):
        """按 app.state / app.busy 重算按钮可不可用、状态文字。"""

    def on_show(self):
        pass

    def set_dev(self, on):
        """开发者模式开 / 关（数据页换样子用）。"""
