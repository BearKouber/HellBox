"""
HellBox：HD1 工具箱

运行：  .venv\\Scripts\\pythonw hellbox\\app.py [--page quick]
打包：  python hellbox\\make_exe.py
"""

import io
import os
import sys
import threading
from contextlib import redirect_stdout
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget  # noqa: E402

import i18n  # noqa: E402
import logbook  # noqa: E402
import ui  # noqa: E402

VERSION = "V1.08"  # 2026-11-23 版本号改为 1.08；合并上游 1.07（PR #1 界面文字整理 + 联机限制）； 2026-11-23 用户定：解锁战线三选一（普通星区 / 进攻母星 / 保卫超级地球，假事件不报服务器、能刷新）这一版叫 1.06； 2026-11-22 用户定：解锁其他战线进发布版、选图游戏关着时也在线、打包去掉套娃压缩包这一版叫 1.05； 2026-11-22 用户定：房间名新规矩（[Hex]、鬼城 +3、炼狱）、选图点小地图挑地形、Dive Harder 作者的几处措辞，这一版叫 1.04
VERSION_NOTE = ""
POLL_MS = 2000
MASTER_HELP = ("核心：HellBox 总开关\n打开 = 安装 HellBox；关闭 = 游戏换回原版文件"
               "\n调整时游戏不能启动")
DEV_FILE = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox", "dev.txt")


def load_dev():
    """开发者模式存在 %APPDATA%\\Arrowhead\\Helldivers\\hellbox\\dev.txt（"1" = 开）。"""
    try:
        with open(DEV_FILE, encoding="ascii") as f:
            return f.read().strip() == "1"
    except (OSError, ValueError):
        return False

KON_FILE = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox", "kon.txt")


def load_kon():
    try:
        with open(KON_FILE, encoding="ascii") as f:
            return f.read().strip() == "1"
    except (OSError, ValueError):
        return False


def save_kon(on):
    try:
        os.makedirs(os.path.dirname(KON_FILE), exist_ok=True)
        with open(KON_FILE, "w", encoding="ascii") as f:
            f.write("1" if on else "0")
    except OSError:
        pass


def save_dev(on):
    try:
        os.makedirs(os.path.dirname(DEV_FILE), exist_ok=True)
        with open(DEV_FILE, "w", encoding="ascii") as f:
            f.write("1" if on else "0")
    except OSError:
        pass

SCRIPT_TEXT = {
    "on": ("已开启", ui.MINT),
    "old": ("待更新", ui.YELLOW),
    "off": ("原版", ui.DISABLED),
    "unknown": ("无法识别", ui.SALMON),
}
UNKNOWN_HELP = ("HellBox 无法识别游戏脚本（可能装过别的 MOD，或其他版本的 HellBox），为安全起见不会修改。"
                "点击「核心」开关旁边的「恢复原版」：有原版备份就直接换回，没有就让 Steam 检查并修复游戏文件。")
CURSOR_TEXT = {
    "on": ("替换", ui.MINT),
    "old": ("待更新", ui.YELLOW),
    "off": ("原版", ui.DISABLED),
    "unknown": ("无法识别", ui.SALMON),
}


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.busy = False
        self.busy_text = ""
        self.busy_since = 0.0
        self.state = {"running": None, "script": None, "cursor": None, "game_dir": ""}
        self.pending_install = False
        self.auto_updated = False
        self.old_told = False
        self.unknown_told = False
        self.bridge = ui.Bridge()
        self.pages = []
        self.current = None
        self.root = self
        self.version, self.version_note = VERSION, VERSION_NOTE

        note = VERSION_NOTE
        if not note and os.path.isfile(os.path.join(paths.MOD, "data_full")):
            note = "全数据版"
        self.version_note = note
        self.setWindowTitle(" ".join(x for x in ("HellBox", VERSION, tr(note)) if x))
        ui.filled(self, ui.BG)
        self.resize(980, 700)
        self.setMinimumSize(880, 600)
        for name in ("icon.ico", "icon.png"):
            path = os.path.join(paths.RES, name)
            if os.path.exists(path):
                self.setWindowIcon(QIcon(path))
                break

        outer = ui.QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 12, 12)
        panel = ui.Box(self, fill=ui.PANEL, border=3, shadow=7)
        outer.addWidget(panel)
        lay = panel.lay
        self.dev = load_dev()
        self.kon = load_kon()
        lay.addWidget(self._build_header())
        lay.addWidget(ui.ink_line(3))

        body, bl = ui.hbox()
        self.nav_slot, self.nav_lay = ui.vbox()
        bl.addWidget(self.nav_slot)
        self.stage = QStackedWidget()
        bl.addWidget(self.stage, 1)
        lay.addWidget(body, 1)
        lay.addWidget(ui.ink_line(2))

        self.footer = ui.Footer()
        ui.set_hint_target(self.footer.hint, self.footer.unhint)
        lay.addWidget(self.footer)

        err = paths.setup()
        if err:
            self._fatal(err)
            return

        from pages import DEV_ONLY, KON_PAGES, NAV, NAV_BOTTOM, PAGES
        self.dev_only = DEV_ONLY
        self.kon_pages = KON_PAGES
        self.pages = [P(self, self.stage) for P in PAGES]
        for p in self.pages:
            self.stage.addWidget(p.view)
        names = {p.key: p.tab for p in self.pages}
        groups = [(title, [(k, names[k]) for k in keys if k in names]) for title, keys in NAV]
        listed = {k for _t, keys in NAV for k in keys} | set(NAV_BOTTOM)
        extra = [(p.key, p.tab) for p in self.pages if p.key not in listed]
        if extra:
            groups.append(("其他", extra))
        self.nav = ui.NavList(groups, [(k, names[k]) for k in NAV_BOTTOM if k in names], self.show_page)
        self.nav_lay.addWidget(self.nav, 1)
        self.set_dev(self.dev, quiet=True)
        self.show_page(self.pages[0].key)
        self.refresh_status()
        self._poll_game()

    # ------------------------------------------------------------ 顶栏
    def _build_header(self):
        head, hl = ui.hbox(margins=(20, 0, 18, 0))
        head.setFixedHeight(52)
        ui.filled(head, ui.HEADER)
        VC = Qt.AlignmentFlag.AlignVCenter
        hl.addWidget(ui.Label("HELLBOX", font=ui.f_pixel(15)), 0, VC)
        hl.addSpacing(10)
        hl.addWidget(ui.Tag(head, VERSION, fill=ui.CARD, font=ui.f_pixel(8, False)), 0, VC)
        hl.addSpacing(8)
        self.dev_tag = ui.Tag(head, "DEV", fill=ui.SALMON, font=ui.f_pixel(8))
        ui.hover_help(self.dev_tag, "开发者模式", "开启：数据页可修改敌人和武器数据，新增「日志」")
        hl.addWidget(self.dev_tag, 0, VC)
        hl.addSpacing(6)
        self.kon_tag = ui.Tag(head, "K-ON!", fill=ui.SKY, font=ui.f_pixel(8))
        ui.hover_help(self.kon_tag, "K-ON!增强UI定制版", "开启：左边只有功能 / 玩法 / 数据 / 指针 / 关于")
        hl.addWidget(self.kon_tag, 0, VC)
        self.kon_tag.setVisible(self.kon)
        hl.addStretch(1)
        self.core_warn = ui.Button(head, "核心没开 →", lambda: self.show_page("about"), kind="danger",
                                   font=ui.f_zh(9, True), padx=10, pady=2, shadow=3)
        self.core_warn.setVisible(False)
        hl.addWidget(self.core_warn, 0, VC)
        hl.addSpacing(14)

        self.lang = ui.Var(i18n.LANG)
        hl.addWidget(ui.Segmented(head, [("zh", "CN"), ("en", "EN")], self.lang, command=self._switch_lang,
                                  font=ui.f_mono(9, True), padx=7, pady=2, shadow=2), 0, VC)
        hl.addSpacing(14)
        self.chip_game = ui.Chip(head, "游戏")
        hl.addWidget(self.chip_game, 0, VC)

        self.master_on = ui.Var(False)
        self.master = ui.Toggle(None, self.master_on, command=self._flip_master)
        self.master.blocked = self._master_blocked
        self.btn_vanilla = ui.Button(None, "恢复原版", self._restore_vanilla, font=ui.f_zh(9, True),
                                     padx=9, pady=2, shadow=2)
        return head

    # ------------------------------------------------------------ 开发者模式
    def set_dev(self, on, quiet=False):
        self.dev = bool(on)
        if not quiet:
            save_dev(self.dev)
        self.dev_tag.setVisible(self.dev)
        for p in self.pages:
            p.set_dev(self.dev)
        self._apply_nav()

    def set_kon(self, on):
        self.kon = bool(on)
        save_kon(self.kon)
        self.kon_tag.setVisible(self.kon)
        self._apply_nav()

    def hidden_pages(self):
        if getattr(self, "kon", False):
            return {p.key for p in getattr(self, "pages", ()) if p.key not in self.kon_pages}
        return set() if self.dev else set(getattr(self, "dev_only", ()))

    def _apply_nav(self):
        hidden = self.hidden_pages()
        if getattr(self, "nav", None) is not None:
            self.nav.set_hidden(hidden)
        if self.current is not None and self.current.key in hidden:
            self.show_page("about")

    def _master_reason(self):
        script = self.state["script"]
        if self.busy:
            return self._busy_hint()
        if script == "unknown":
            return "游戏脚本被其他 MOD 改过，暂不修改；可点「恢复原版」。"
        if self.state.get("cursor") == "unknown":
            return "指针文件被其他 MOD 改过，暂不修改；可点「恢复原版」。"
        if self.state["running"]:
            return "请先关闭游戏再切换。"
        if script is None or self.state["running"] is None:
            return "正在读取游戏状态…"
        return ""

    def _master_blocked(self):
        reason = self._master_reason()
        if reason:
            self.say(reason, "warn")

    def _flip_master(self):
        on = bool(self.master_on.get())

        def install_all():
            import build
            import cursor_mod
            build.install()
            cursor_mod.apply_saved()
            return "HellBox 已安装"

        def restore_all():
            import build
            import cursor_mod
            left = build.restore()
            cursor_mod.restore(keep_setting=True)
            if left:
                return T("已恢复原版。有 {0} 个地图文件当初选了不备份，还是鬼城配色（不影响正常玩）；"
                         "要完全恢复原版，请在 Steam 里验证游戏文件完整性。", left)
            return "已恢复原版。"

        if on:
            if not self._ask_map_backup():
                self.master_on.set(False)
                return
            self.run(install_all, working="正在安装 HellBox（第一次可能需要几分钟），请先别开游戏")
        else:
            self.run(restore_all, working="正在还原游戏")

    MAP_BACKUP_TEXT = (
        "第一次开启「核心」时，要给 45 个地图文件换上鬼城配色。请选择是否备份原版地图：\n\n"
        "· 备份地图：多占约 1.3GB，第一次更慢；以后在「关于」中关闭「核心」即可一键恢复原版。\n"
        "· 不备份：快很多；以后要恢复原版地图，需要在 Steam 中「验证游戏文件完整性」"
        "（Steam 会重新下载改过的 45 个地图文件）。\n\n"
        "无论选哪个，游戏脚本的小备份都会保留；以后更新 HellBox 也不受影响。")

    def _ask_map_backup(self):
        import build
        try:
            if build.map_backup_choice() is not None:
                return True
        except OSError:
            return True
        pick = ui.choose(self, self.MAP_BACKUP_TEXT, "备份地图", "不备份")
        if pick is None:
            return False
        try:
            build.set_map_backup_choice(pick == "first")
        except OSError as e:
            self.error(T("没存上：{0}", e))
            return False
        return True

    def _restore_vanilla(self):
        if self.busy or self.state["running"] is not False:
            self.say("请先关闭游戏。", "warn")
            return

        fix_script = self.state.get("script") == "unknown"
        fix_cursor = self.state.get("cursor") == "unknown"

        def check():
            import build
            import cursor_mod
            return ((not fix_script or build.has_vanilla_backup())
                    and (not fix_cursor or cursor_mod.has_vanilla_backup()))

        def restore_parts():
            import build
            import cursor_mod
            if fix_script:
                build.restore()
            if fix_cursor:
                cursor_mod.restore()
            return "已恢复原版"

        def done(ok, has):
            import build
            if not ok:
                self.error(T('没有完成：{0}', has))
            elif has:
                if self.ask("找到了原版备份\n用它还原游戏吗？"):
                    self.run(restore_parts, working="正在恢复原版")
            elif self.ask("这台电脑上没有原版备份。\n要让 Steam 检查并修复游戏文件吗？"):
                try:
                    build.open_steam_verify()
                except OSError as e:
                    self.error(T('打不开 Steam：{0}', e))
                    return
                self.say("已开始验证游戏完整性", "info")
                self._steam_wait(120)

        self.bg(check, done)

    def _steam_wait(self, left):
        if "unknown" not in (self.state.get("script"), self.state.get("cursor")) or left <= 0:
            if self.state.get("script") == "off":
                self.say("Steam 已还原游戏文件", "ok")
            return
        if not self.busy:
            self.refresh_status()
        self.after(5000, lambda: self._steam_wait(left - 1))

    def _switch_lang(self, lang):
        if self.busy:
            self.lang.set(i18n.LANG)
            self.say("正在修改游戏文件，请勿操作", "warn")
            return
        try:
            i18n.set_lang(lang)
        except OSError as e:
            self.lang.set(i18n.LANG)
            self.say(T("没有完成：{0}", e), "err")
            return
        from PySide6.QtCore import QProcess
        extra = ["--page", self.current.key] if self.current else []
        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, extra)
        else:
            QProcess.startDetached(sys.executable, [os.path.abspath(__file__), *extra])
        QApplication.quit()

    def mod_on(self):
        return self.state["script"] in ("on", "old")

    def _fatal(self, err):
        page = ui.DotPage()
        self.stage.addWidget(page)
        card = ui.Card(page, "ERROR", "打不开", fill=ui.SALMON)
        card.add(ui.text(card.body, err))
        page.row(card)
        self.say(err.splitlines()[0], "err")

    # ------------------------------------------------------------ 页面
    def show_page(self, key):
        if key in self.hidden_pages():
            key = "about"
        for p in self.pages:
            if p.key == key:
                if self.current is not p:
                    self.current = p
                    self.stage.setCurrentWidget(p.view)
                    self.nav.select(key)
                    p.on_show()
                return

    def master_note(self):
        script = self.state["script"]
        reason = self._master_reason()
        if reason:
            return tr(reason)
        if script == "old":
            return tr("MOD 有新版本，关闭游戏后会自动更新")
        return tr({"on": "已装好", "off": "没开：游戏是原版", "unknown": "无法识别游戏文件"}.get(script, ""))

    def sync(self):
        running = self.state["running"]
        if running is None:
            self.chip_game.set("…", ui.DISABLED)
        else:
            self.chip_game.set("运行中" if running else "未运行", ui.YELLOW if running else ui.DISABLED)
        script = self.state["script"]
        unknown = "unknown" in (script, self.state.get("cursor"))

        self.core_warn.set_text("无法识别游戏文件 →" if unknown else "核心没开 →")
        self.core_warn.setVisible(not self.busy and (unknown or script == "off"))
        if not self.busy and self.master_on.get() != self.mod_on():
            self.master_on.set(self.mod_on())
        self.master.set_enabled(not self.busy and running is False and script not in (None, "unknown"))
        self.btn_vanilla.set_enabled(unknown and not self.busy and running is False)
        tip = tr(UNKNOWN_HELP) if unknown and not self.busy else ""
        if tip and not self.unknown_told:
            self.unknown_told = True
            self.say(UNKNOWN_HELP, "warn")
        if script == "old" and running and not self.old_told:
            self.old_told = True
            self.say("游戏里还是旧版 MOD，新加的功能在游戏里用不了。关掉游戏后 HellBox 会自动更新。", "warn")
        if script == "old" and running is False and not self.busy and not self.auto_updated and "--check-ui" not in sys.argv:
            import build
            self.auto_updated = True
            self.after(0, lambda: self.run(build.install, "HellBox 已更新到最新版本。", "HellBox 是旧版本，正在更新…"))
        for p in self.pages:
            p.sync()

    # ------------------------------------------------------------ 后台任务
    def later(self, fn):
        try:
            self.bridge.call.emit(fn)
        except RuntimeError:
            pass

    def after(self, ms, fn):
        return ui.after(ms, fn)

    def bg(self, work, done=None):
        def go():
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    res = (True, work())
            except Exception as e:
                logbook.exception("HellBox", e)
                res = (False, e)
            if done:
                self.later(lambda: done(*res))
        threading.Thread(target=go, daemon=True).start()

    def _busy_hint(self):
        import time
        sec = int(time.monotonic() - self.busy_since)
        step = getattr(self, "busy_step", None)
        if step:
            return T('{0}（鬼城地图：{1} / {2}，{3} 秒）', self.busy_text.rstrip('…'), step[0], step[1], sec)
        return T('{0}（{1} 秒）', self.busy_text.rstrip('…'), sec)

    def _busy_tick(self):
        if not self.busy:
            return
        self.footer.say(self._busy_hint(), "warn")
        self.after(1000, self._busy_tick)

    def run(self, action, ok_msg=None, working="处理中…"):
        import time
        if self.busy:
            return
        self.busy = True
        self.busy_text = working
        self.busy_since = time.monotonic()
        self.busy_step = None
        try:
            import build
            build.PROGRESS = lambda i, n: setattr(self, "busy_step", (i, n))
        except ImportError:
            pass
        self.say(working, "info")
        self.sync()
        self._busy_tick()

        def done(ok, res):
            self.busy = False
            self.busy_text = ""
            if ok:
                self.say(res if isinstance(res, str) else (ok_msg or "完成。"), "ok")
            else:
                self.say(T('没有完成：{0}', i18n.tr(str(res))), "err")
                ui.message(self, str(res), "error")
            self.refresh_status()

        self.bg(action, done)

    def say(self, text, kind="info"):
        if kind == "err":
            logbook.error("HellBox", text)
        elif kind == "warn":
            logbook.warn("HellBox", text)
        self.footer.say(text, kind)

    # ------------------------------------------------------------ 弹窗（页面用）
    def warn(self, text):
        logbook.warn("HellBox", text)
        ui.message(self, text, "warn")

    def error(self, text):
        logbook.error("HellBox", text)
        ui.message(self, text, "error")

    def ask(self, text):
        return ui.message(self, text, "ask", ok="是", cancel="否")

    # ------------------------------------------------------------ 状态
    def refresh_status(self):
        def work():
            import build
            import cursor_mod
            out = {"game_dir": build.game_dir()}
            for key, fn in (("script", build.status), ("cursor", cursor_mod.status)):
                try:
                    out[key] = fn()
                except Exception:
                    out[key] = "unknown"
            return out

        def done(ok, res):
            if ok:
                self.state.update(res)
            else:
                self.say(T('读取游戏失败：{0}', res), "err")
            self.sync()

        self.bg(work, done)

    def _poll_game(self):
        def work():
            import build
            return build.game_running()

        def done(ok, running):
            if ok:
                self._on_game(running)
            self.after(POLL_MS, self._poll_game)

        self.bg(work, done)

    def _on_game(self, running):
        changed = running != self.state["running"]
        self.state["running"] = running
        if changed:
            self.sync()
            if not self.busy:
                self.refresh_status()
        if running is False and changed:
            def told(ok, msg):
                if ok and msg:
                    self.say(msg, "warn")
            self.bg(logbook.check_probe, told)
        if not running and self.pending_install and not self.busy:
            import build
            self.pending_install = False
            self.run(build.install, "新设置已安装", "正在安装新设置")


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HellBox.HD1")
        except (AttributeError, OSError):
            pass
        if "--check-ui" not in sys.argv:
            # 游戏以管理员（High）开着时，Medium 的 HellBox 连它的写句柄都打不开（热改名会失败），
            # 所以默认以管理员身份运行；判据是实测一次写句柄，不看 IsUserAnAdmin（关 UAC 时它会说谎）
            try:
                import elevate
                elevate.ensure_admin()
            except OSError as e:
                logbook.warn("HellBox", T("没法以管理员身份启动：{0}", e))
    logbook.install()
    qapp = QApplication(sys.argv[:1])
    qapp.setWheelScrollLines(1)
    ui.load_fonts(paths.FONTS)
    qapp.setFont(ui.f_zh(10))
    qapp.setStyleSheet(ui.TIP_STYLE)
    app = App()
    if "--page" in sys.argv and app.pages:
        i = sys.argv.index("--page") + 1
        key = sys.argv[i] if i < len(sys.argv) else ""
        if any(p.key == key for p in app.pages):
            app.show_page(key)
    app.show()
    if "--check-ui" in sys.argv:
        qapp.processEvents()
        for page in app.pages:
            app.show_page(page.key)
            page.sync()
            qapp.processEvents()
        raise SystemExit(0 if app.pages else 1)
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
