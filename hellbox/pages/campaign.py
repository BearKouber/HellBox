"""
战役页：解锁其他战线、设置报复打击概率、刷新星球。
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

GENOCIDE_OPTIONS = [("0", "0%"), ("", "33% 原版"), ("66", "66%"), ("100", "100%")]


def _genocide_value():
    g = build.get_genocide()
    s = "" if g is None else str(g)
    return s if s in dict(GENOCIDE_OPTIONS) else ""


class CampaignPage(Page):
    key = "campaign"
    tab = "战役"

    def build(self):
        front = ui.Card(self.view, "FRONT", "解锁其他战线", fill=ui.SALMON)
        self.unlock = ui.Var(build.get_front_unlock())
        self.toggle = ui.Toggle(None, self.unlock, command=self.apply_unlock)
        w, lay = ui.hbox()
        lay.addWidget(self.toggle, 0, ui.Qt.AlignmentFlag.AlignVCenter)
        lay.addSpacing(14)
        lay.addWidget(ui.text(None, "未开放的战线也能选择\n尚未出场、已攻破的都算", bold=True), 1)
        front.add(w)
        front.add(ui.text(front.body, "自动检查每条战线：正在战斗的不改动；新赛季尚未出场的直接开放，从起点开始；已攻破的放回攻破前最后一个星区。游戏运行时也能切换，退出战役地图后再进入一次即可生效。",
                          muted=True, size=9), top=12)

        gen = ui.Card(self.view, "STRIKE", "报复打击概率", fill=ui.MINT)
        self.genocide = ui.Var(_genocide_value())
        self.seg = ui.Segmented(None, GENOCIDE_OPTIONS, self.genocide, command=self.apply_genocide, padx=10)
        gen.add(self.seg, align=ui.LEFT)
        gen.add(ui.text(gen.body, "难度 4 以上的新星球，每颗有多大概率带一个报复打击任务（每颗最多一个）。只影响之后新出的星球；想立即生效，再点击一次刷新星球。",
                        muted=True, size=9), top=12)

        planets = ui.Card(self.view, "PLANETS", "刷新星球", fill=ui.YELLOW)
        self.btn_refresh = ui.Button(None, "刷新星球", self.refresh_planets, kind="accent")
        planets.add(self.btn_refresh, align=ui.LEFT)
        self.refresh_hint = planets.add(ui.text(planets.body, "", muted=True, size=9), top=12)

        self.view.row(front, gen)
        self.view.row(planets)

    def _push_live(self):
        if not build.game_running():
            return False
        import room_name_live
        room_name_live.live_set(build.front_mail(), magic=room_name_live.MAGIC_FRONT)
        self.app.pending_install = True
        return True

    def apply_unlock(self):
        on = self.unlock.get()

        def action():
            build.set_front_unlock(on)
            word = tr("已开启") if on else tr("已关闭")
            if self._push_live():
                return T('{0}，退出战役地图再进一次生效。关游戏时 HellBox 别关，会自动记住。', word)
            build.install()
            return T('{0}，下次开游戏生效。', word)

        self.app.run(action)

    def apply_genocide(self, value):
        def action():
            build.set_genocide(int(value) if value else None)
            label = dict(GENOCIDE_OPTIONS)[value]
            if self._push_live():
                return T('报复打击概率改成 {0}，之后新出的星球生效。关游戏时 HellBox 别关，会自动记住。', label)
            build.install()
            return T('报复打击概率改成 {0}，下次开游戏生效。', label)

        self.app.run(action)

    def refresh_planets(self):
        def action():
            if not build.game_running():
                raise RuntimeError("刷新星球需要在游戏运行时点击（在飞船中，未进入任务）。")
            import room_name_live
            room_name_live.live_set("", magic=room_name_live.MAGIC_REFRESH)
            return "已刷新：战役地图打开时立即更换一批新星球；未打开则下次打开地图时更换。"

        self.app.run(action)

    def sync(self):
        running = bool(self.app.state["running"])
        self.toggle.set_enabled(not self.app.busy)
        self.seg.set_enabled(not self.app.busy)
        if not self.app.busy:
            on = build.get_front_unlock()
            if self.unlock.get() != on:
                self.unlock.set(on)
            if self.genocide.get() != _genocide_value():
                self.genocide.set(_genocide_value())
        self.btn_refresh.set_enabled(running and not self.app.busy)
        self.refresh_hint.config(
            text="在飞船中、未进入任务时点击（需要你是房主）。战役地图打开时立即更换，三个种族的星球都换一批新的；地图未打开则下次打开时更换。" if running
            else "需要游戏正在运行才能点击（在飞船中，未进入任务）。")
