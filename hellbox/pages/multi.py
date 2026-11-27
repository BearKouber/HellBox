"""
多人页（HD1-039，2026-11-26 用户定：单独一页、只在开发者模式显示）：8 人房间开关 + 状态栏摆法。
开关存在 mod/eight_players.txt，状态栏存在 mod/eight_players_hud.txt（摆法 rows / small 二选一 + 只看自己开关，如 small+solo），装核心时一起装（mod/eight_players.py 改原版脚本 + mod/src/hellbox_8p.lua 管规则），所以要在游戏关着时切换。
"""
import build
import ui
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

# 状态栏（用户 2026-11-26）：摆法二选一（两排 / 小一号一排），「只看自己」单独开关，两种摆法都能配
HUD_OPTIONS = [("rows", "两排"), ("small", "小一号一排")]
HUD_HINTS = {
    "rows": "1～4 号照原版，第 5～8 人在原来那排的正上方。",
    "small": "8 个人的状态栏都缩小，在屏幕下方排成一排（地图、呼叫支援也跟着变小）。",
}
SOLO_HINT = "任务里只显示本机玩家的状态栏，按 Tab 打开地图时才显示其他人；飞船里都显示。"

RULES = [
    "房间里有没开 8 人房间的玩家时，最多 4 人（他们的游戏只有 4 个位置）；他们走了，再放开到 8 人。",
    "第 5～8 人的颜色是红、白、青、粉。",
    "救援一次最多复活 4 人，先救死得早的，没复活的等下一次救援。",
    "装备界面只有 4 栏：有人坐 5～8 号时，先显示你自己的那一栏。",
    "开着也能进别人的普通房间，那时和原版一样最多 4 人。",
]


class MultiPage(Page):
    key = "multi"
    tab = "多人"
    when = "游戏关着时切换"

    def build(self):
        room = ui.Card(self.view, "ROOM", "8 人房间", fill=ui.SKY)
        self.eight = ui.Var(build.get_eight_players())
        self.toggle = ui.Toggle(None, self.eight, command=self.apply)
        self.toggle.blocked = self._blocked
        w, lay = ui.hbox()
        lay.addWidget(self.toggle, 0, ui.Qt.AlignmentFlag.AlignVCenter)
        lay.addSpacing(14)
        lay.addWidget(ui.text(None, "房间最多 8 人\n同样开了的玩家才能当第 5～8 人", bold=True), 1)
        room.add(w)
        self.hint = room.add(ui.text(room.body, "", muted=True, size=9), top=12)

        layout, solo = build.get_eight_hud()
        room.add(ui.text(room.body, "状态栏", bold=True), top=16)
        self.hud = ui.Var(layout)
        self.seg = ui.Segmented(None, HUD_OPTIONS, self.hud, command=lambda _v: self.apply_hud(), padx=10)
        room.add(self.seg, align=ui.LEFT, top=6)
        self.hud_hint = room.add(ui.text(room.body, "", muted=True, size=9), top=6)
        self.solo = ui.Var(solo)
        self.solo_toggle = ui.Toggle(None, self.solo, command=self.apply_hud)
        self.solo_toggle.blocked = self._blocked
        w2, lay2 = ui.hbox()
        lay2.addWidget(self.solo_toggle, 0, ui.Qt.AlignmentFlag.AlignVCenter)
        lay2.addSpacing(14)
        lay2.addWidget(ui.text(None, "只看自己\n开地图（Tab）时才显示其他人", bold=True), 1)
        room.add(w2, top=12)
        self.solo_hint = room.add(ui.text(room.body, tr(SOLO_HINT), muted=True, size=9), top=6)

        rules = ui.Card(self.view, "RULES", "怎么算", fill=ui.YELLOW)
        for i, line in enumerate(RULES):
            rules.add(ui.text(rules.body, "· " + tr(line), size=9), top=0 if i == 0 else 6)

        self.view.row(room, rules)

    def _reason(self):
        if self.app.busy:
            return self.app._busy_hint()
        if self.app.state["running"]:
            return "请先关闭游戏再切换。"
        if self.app.state["running"] is None:
            return "正在读取游戏状态…"
        return ""

    def _blocked(self):
        reason = self._reason()
        if reason:
            self.app.say(reason, "warn")

    def apply(self):
        on = bool(self.eight.get())
        core = self.app.mod_on()

        def action():
            build.set_eight_players(on)
            word = tr("已开启") if on else tr("已关闭")
            if not core:
                return T("8 人房间{0}，打开核心时一起装。", word)
            try:
                build.install()
            except Exception:
                build.set_eight_players(not on)
                raise
            return T("8 人房间{0}，下次开游戏生效。", word)

        self.app.run(action)

    def apply_hud(self, *_):
        old = build.get_eight_hud()
        if self._reason():
            self._blocked()
            self.hud.set(old[0])
            self.solo.set(old[1])
            return
        layout, solo = self.hud.get(), bool(self.solo.get())
        core = self.app.mod_on() and build.get_eight_players()

        def action():
            build.set_eight_hud(layout, solo)
            name = tr(dict(HUD_OPTIONS)[layout]) + (tr(" + 只看自己") if solo else "")
            if not core:
                return T("状态栏改成「{0}」，开 8 人房间、打开核心时一起装。", name)
            try:
                build.install()
            except Exception:
                build.set_eight_hud(*old)
                raise
            return T("状态栏改成「{0}」，下次开游戏生效。", name)

        self.app.run(action)

    def sync(self):
        reason = self._reason()
        self.toggle.set_enabled(not reason)
        self.seg.set_enabled(not reason)
        self.solo_toggle.set_enabled(not reason)
        if not self.app.busy:
            on = build.get_eight_players()
            if self.eight.get() != on:
                self.eight.set(on)
            layout, solo = build.get_eight_hud()
            if self.hud.get() != layout:
                self.hud.set(layout)
            if bool(self.solo.get()) != solo:
                self.solo.set(solo)
        self.hud_hint.config(text=tr(HUD_HINTS.get(self.hud.get(), "")))
        if self.app.state["running"] is None or self.app.state["script"] is None:
            text = "正在读取游戏状态…"
        elif self.app.state["running"]:
            text = "游戏运行中：现在的设置在这次游戏里有效，要切换请先关闭游戏。"
        elif not self.app.mod_on():
            text = "核心没开：开关会记住，打开核心时一起装。"
        else:
            text = "切换后会马上重装 MOD，下次开游戏生效。关闭 = 和原版一样最多 4 人。"
        self.hint.config(text=tr(text))
