"""
关于页：版本、设置、出问题了、鸣谢。
"""
import os
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

import logbook
import paths
import ui
import updater
from pages import data_blocks as db
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

TAPS = 10
TAP_GAP = 1.5

AUTHOR = "07"
HOME_URL = "https://www.nexusmods.com/helldivers/mods/63"
SOURCE_URL = "https://github.com/BearKouber/HellBox"
THANKS = [
    ("UI设计", "91"),
    ("增强数据来源", "吃大份"),
    ("分屏", "HalfSugar"),
    ("QoL Mod", "SomeDoggo"),
    ("Dive Harder", "Oct0pu5"),
    ("文本", "Oct0pu5"),
    ("总体规划与代码", "Claude"),
    ("内测名单", "91、HalfSugar、吃大份、K-ON!、Kent、QiQi、Lhgrzr、Six、海之星"),
]
NOTICE = ("· HellBox 完全免费且开源，源码: https://www.github.com/BearKouber/HellBox。如果你是花钱买到的，请找卖家退款。\n"
          "· 可以自由修改、再发布，但请保留作者 07 的署名和授权说明（LICENSE），并注明原发布页。\n"
          "· 收录的他人作品归原作者，转发时请一并注明。\n"
          "· 非官方 MOD，与游戏官方无关。使用 MOD 有风险，出了问题可以点击上面的「恢复原版」。\n"
          "· 用到的开源组件：Python、PySide6 / Qt、LuaJIT、Silkscreen 字体，授权说明见 LICENSE。")
CLOSING = ("希望大家能在游戏里找到它本身的乐趣，也希望这个工具能让你玩得开心。\n"
           "请不要滥用，不要影响别的玩家的体验。")


class VersionLabel(ui.Label):
    def __init__(self, text, on_tap):
        super().__init__(text, font=ui.f_zh(9), fg=ui.MUTED)
        self.on_tap = on_tap

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.on_tap()


class AboutPage(Page):
    key = "about"
    tab = "关于"
    when = ""
    when_color = ui.MINT

    def build(self):
        a = self.app
        self.taps, self.last_tap = 0, 0.0
        note = " ".join(x for x in (a.version, tr(a.version_note)) if x)
        info = ui.Card(self.view, "HELLBOX", "HellBox", fill=ui.YELLOW)
        info.head_lay.addWidget(VersionLabel(note, self.tap), 0, Qt.AlignmentFlag.AlignVCenter)
        info.add(ui.text(info.body, "HELLDIVERS（1 代）MOD 工具：带箱子上车、给好友点赞、刷新星球、选图、玩法、数据修改、指针、语音、战绩等。"))
        info.row("作者", ui.Label(AUTHOR, font=ui.f_zh(11, True)), help="HellBox 的作者（MOD 开发者）。")
        if HOME_URL:
            info.row("发布页", ui.Button(None, "去看看", self._open_home, font=ui.f_zh(9, True), padx=9, pady=2, shadow=2),
                     sub=HOME_URL, help="HellBox 的发布页：下载新版、看更新说明、反馈问题。")
        info.row("源码", ui.Button(None, "去看看", self._open_source, font=ui.f_zh(9, True), padx=9, pady=2, shadow=2),
                 sub=SOURCE_URL, help="HellBox 的源码（MIT 授权，开源）")
        self.upd_info, self.upd_busy = None, False
        self.upd_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self.btn_update = ui.Button(None, "检查更新", self._update_click, kind="accent", font=ui.f_zh(9, True),
                                    padx=9, pady=2, shadow=2)
        info.row("更新", self.btn_update, sub=self.upd_note,
                 help="去 GitHub 看有没有新版。有新版时点「更新」：自动下载，HellBox 关掉换上新版再自己打开，设置都保留。")
        self.view.row(info)
        a.after(1500, self._update_result)

        s = ui.Card(self.view, "SET", "设置", fill=ui.MINT)
        self.core_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        s.row("核心", a.master, sub=self.core_note,
              help="「核心」是 HellBox 所有功能的总开关：开启后把 HellBox 的脚本和指针安装进游戏，关闭后换回原版文件。切换前请先退出游戏。")
        self.kon_var = ui.Var(a.kon)
        s.row("K-ON!增强UI定制版", ui.Toggle(None, self.kon_var, command=self._kon_flip),
              help="开启后自动关闭开发者模式，左侧只保留「功能」「玩法」「增强」「指针」「关于」五页，并在「增强」页提供坦克出兵增强、增加坦克基数、班长和军团增强、敌人可更密集；关闭后恢复原样。")
        self.dev_var = ui.Var(a.dev)
        self.dev_row = s.row("开发者模式", ui.Toggle(None, self.dev_var, command=self._dev_flip),
                             help=("开启后：数据页可按单个敌人 / 单把武器 / 单个战略配备细改，并可存成多块切换；左侧新增「选图」「分屏」「潜兵」「日志」。关闭后这一行会隐藏。") if db.FULL else
                             ("开启后：数据页可按单个敌人 / 单个出怪来源细改，并可存成多块切换；左侧新增「选图」「分屏」「潜兵」「日志」。关闭后这一行会隐藏。"))
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
        h.row("无法识别游戏文件", a.btn_vanilla, sub=self.vanilla_note,
              help="HellBox 无法识别游戏脚本（可能装过别的 MOD，或其他版本的 HellBox），为安全起见不会修改。点击「恢复原版」：有原版备份就直接换回，没有就让 Steam 检查并修复游戏文件。")
        h.row("卸载", ui.Label("关闭游戏 → 关闭「核心」→ 删除 HellBox 文件夹", font=ui.f_zh(9), fg=ui.MUTED))
        self.view.row(h)

        t = ui.Card(self.view, "THANKS", "鸣谢", fill=ui.TAN)
        for role, names in THANKS:
            t.row(role, ui.Label(names, font=ui.f_zh(10, True)))
        # 2026-11-27 用户：「不分先后」从标题挪到卡片右下角，灰色小字（放在卡片的弹性空白后面 = 贴底）
        order = ui.Label("不分先后", font=ui.f_zh(9), fg=ui.MUTED)
        order.setContentsMargins(2, 0, 16, 10)
        t.lay.addWidget(order, 0, Qt.AlignmentFlag.AlignRight)
        d = ui.Card(self.view, "NOTICE", "声明", fill=ui.SKY)
        d.add(ui.text(d.body, NOTICE, size=9))
        self.view.row(t)
        self.view.row(d)

        last = ui.Card(self.view, "LAST", "写在最后", fill=ui.MINT)
        last.add(ui.text(last.body, CLOSING, size=10))
        last.add(ui.Label("—— " + AUTHOR, font=ui.f_zh(10, True), fg=ui.MUTED), top=4, align=Qt.AlignmentFlag.AlignRight)
        self.view.row(last)

    # ---------------------------------------------------------------- 开发者模式
    def tap(self):
        now = time.monotonic()
        self.taps = self.taps + 1 if now - self.last_tap <= TAP_GAP else 1
        self.last_tap = now
        if self.app.kon:
            if self.taps >= 3:
                self.app.say("K-ON!增强UI定制版已开启，请先关闭定制版再开启开发者模式。", "info")
            return
        if self.app.dev:
            if self.taps >= 3:
                self.app.say("开发者模式已开启（可在「设置」中关闭）。", "info")
            return
        left = TAPS - self.taps
        if left <= 0:
            self.taps = 0
            self.dev_var.set(True)
            self._dev_flip()
        elif left <= 5:
            self.app.say(T("还需点击 {0} 次即可开启开发者模式。", left), "info")

    def _dev_flip(self):
        on = bool(self.dev_var.get())
        self.app.set_dev(on)
        self.dev_row.setVisible(self.app.dev)
        self.app.say("开发者模式已开启：数据页可细改，左侧新增「选图」「分屏」「潜兵」「日志」。" if self.app.dev else "开发者模式已关闭。", "ok")

    def _kon_flip(self):
        on = bool(self.kon_var.get())
        self.app.set_kon(on)
        self.app.say("K-ON!增强UI定制版已开启：已关闭开发者模式，左侧只保留「功能」「玩法」「增强」「指针」「关于」。" if on else "K-ON!增强UI定制版已关闭。", "ok")

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

    # ---------------------------------------------------------------- 检查更新（2026-11-26 用户要）
    def _app_dir(self):
        return paths.EXE_DIR if paths.FROZEN else paths.ROOT

    def _update_click(self):
        if self.upd_busy:
            return
        info = self.upd_info
        if info and info["newer"]:
            self._update_install(info)
        else:
            self._update_check()

    def _update_check(self):
        self.upd_busy = True
        self.btn_update.set_enabled(False)
        self.upd_note.config(text="正在检查…", fg=ui.MUTED)

        def done(ok, res):
            self.upd_busy = False
            self.btn_update.set_enabled(True)
            if not ok:
                self.upd_note.config(text=str(res), fg=ui.BAD)
                self.app.say(T("检查更新失败：{0}", res), "warn")
                return
            self.upd_info = res
            if res["newer"]:
                self.upd_note.config(text=T("有新版 {0}（现在 {1}）", res["version"], self.app.version), fg=ui.BAD)
                self.btn_update.set_text(T("更新到 {0}", res["version"]))
                self.app.say(T("有新版 {0}，点「更新到 {0}」就能更新。", res["version"]), "info")
            else:
                self.upd_note.config(text=T("已经是最新（GitHub 最新是 {0}）", res["version"]), fg=ui.MUTED)
                self.app.say("已经是最新版。", "ok")

        self.app.bg(lambda: updater.check(self.app.version), done)

    def _update_install(self, info):
        app_dir = self._app_dir()
        why = updater.can_self_update(app_dir)
        if why:
            self.app.warn(T("{0}\n\n新版下载页：{1}", why, info["page"]))
            return
        if self.app.busy:
            self.app.say("正在修改游戏文件，请等它做完再更新。", "warn")
            return
        if not self.app.ask(T("更新到 {0}？\n\n下载好以后 HellBox 会自己关掉，换上新版再打开，设置都保留。\n"
                              "游戏开着也没关系，新版的游戏内功能等关掉游戏后自动装上。", info["version"])):
            return
        self.upd_busy = True
        self.btn_update.set_enabled(False)
        self.upd_note.config(text="正在下载…", fg=ui.MUTED)
        last = [0.0]

        def progress(got, total):
            now = time.monotonic()
            if now - last[0] < 0.3 and got < total:
                return
            last[0] = now
            pct = min(100, got * 100 // total)
            self.app.later(lambda: self.upd_note.config(text=T("正在下载… {0}%（{1:.1f} / {2:.1f} MB）", pct, got / 1e6, total / 1e6)))

        def work():
            zip_path = updater.download(info, progress)
            self.app.later(lambda: self.upd_note.config(text="正在解压…"))
            return updater.unpack(zip_path)

        def done(ok, res):
            self.upd_busy = False
            self.btn_update.set_enabled(True)
            if not ok:
                self.upd_note.config(text=str(res), fg=ui.BAD)
                self.app.error(T("更新没完成：{0}\n\n也可以去下载页手动换新版：{1}", res, info["page"]))
                return
            try:
                updater.launch_swap(res, app_dir, info["version"])
            except OSError as e:
                self.app.error(T("更新没完成：{0}", e))
                return
            self.upd_note.config(text="HellBox 马上关掉，换上新版后自动打开…")
            logbook.write("INFO", "HellBox", f"update to {info['version']}: restarting")
            import alive
            from PySide6.QtWidgets import QApplication
            alive.keep_on_exit = True  # 更新完新版接着写心跳，中间不算关
            self.app.after(600, QApplication.quit)

        self.app.bg(work, done)

    def _update_result(self):
        res = updater.take_result()
        if not res:
            return
        status, version, detail = res
        same = updater.parse_version(version) == updater.parse_version(self.app.version)
        if status == "ok" and same:
            updater.cleanup()
            self.app.say(T("已更新到 {0}。", version), "ok")
        elif status == "ok":
            self.app.warn(T("更新到 {0} 好像没成功：现在还是 {1}。可以去下载页手动换新版：{2}", version, self.app.version, updater.PAGE))
        else:
            self.app.error(T("更新到 {0} 没完成（{1}），现在还是旧版，设置没动。\n"
                             "多半是文件被占用：关掉杀毒软件拦截或重启电脑后再点一次，也可以去下载页手动换新版：{2}",
                             version, detail, updater.PAGE))

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
            self.app.say("诊断信息已复制，可直接粘贴到群聊中。", "ok")

        self.app.bg(work, done)

    def sync(self):
        st = self.app.state
        where = st.get("game_dir") or "…"
        drive, rest = os.path.splitdrive(where)
        if drive:
            where = drive.upper() + rest
        self.where.config(text=where)
        self.btn_open.set_enabled(bool(st.get("game_dir")))
        note = self.app.master_note()
        bad = st.get("script") in ("off", "unknown")
        self.core_note.config(text=note, fg=ui.BAD if bad else ui.MUTED)
        unknown = "unknown" in (st.get("script"), st.get("cursor"))
        self.vanilla_note.config(text="无法识别：点击右侧「恢复原版」" if unknown else "现在没问题",
                                 fg=ui.BAD if unknown else ui.MUTED)
