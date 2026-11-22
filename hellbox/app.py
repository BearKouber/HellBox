"""HellBox：HD1 工具箱。左侧导航切换页面（2026-11-15 从顶部标签改成左侧竖排），一页一个功能，页面登记在 pages/__init__.py。

界面用 Qt（PySide6，2026-11-07 从 tkinter 换过来，拖窗口不卡了）。
运行：  .venv\\Scripts\\pythonw hellbox\\app.py [--page quick]      打包：  python hellbox\\make_exe.py
"""
import io
import os
import sys
import threading
from contextlib import redirect_stdout
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
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

VERSION = "V1.04"  # 2026-11-22 用户定：房间名新规矩（[Hex]、鬼城 +3、炼狱）、选图点小地图挑地形、Dive Harder 作者的几处措辞，这一版叫 1.04； 2026-11-22 用户定：能和 QoL / Dive Harder 一起装、QoL 的功能删掉、Dive Harder 四项、隐藏 HellBox 房间筛选、房间名顺序这一版叫 1.03； 2026-11-21 用户定：开源（MIT）、分屏不带 exe、HUD 透明度闪退修好、填弹惊喜卡片、副武器换成军刀这一版叫 1.02； 2026-11-20 用户定：QoL 全部收进来、蜜蜂灯、补丁装法（能和 Obsidian 一起装）、鸣谢加 Alomare / SomeDogge 这一版叫 1.01； 2026-11-19 用户定：正式版 V1.0（补给背包 / 样本描边 / 输入法防闪退 / 片头跳过、「训练」改「选图」能设为下一局）； 2026-11-19 用户定：不再叫群友测试版，起名 1.0pre（新分屏、鸣谢 / 声明、潜兵页进开发者模式、坦克投放单位只列本种族）； 2026-11-18 用户定：真鬼城（装核心时换地图包配色）、普通模式加「坦克屁股出兵」这一版叫 V0.99； 2026-11-18 用户定：发行测试版——导航滚动条藏起来只用滚轮、「数据」页只留怪物属性和出怪逻辑（1.0 再分带全部数据 / 不带两份）这一版叫 V0.98； 2026-11-18 用户定：玩法页大改（武装配置块单格固定 / 自由 / 随机、修正参数叠加 + 随机掉落、鬼城、我的玩法、真房间名、客机跟随房主）+ 整体整理（用词跟游戏、玩法页重排、导航滚动）这一版叫 V0.97； 2026-11-18 用户定：V0.95 实测后的发布前修正（换弹不滑、场上上限滑条 + 破限、载具放兵数、玩法描述、房间记号、客机不生效、房主配装）这一版叫 V0.96； 2026-11-16 用户定：丢战备、训练在飞船上直接进、「玩法」页（真训练场联机版 + HellBox 版模式块）这一版叫 V0.95； 2026-11-16 用户定：出怪自动上限 / 散开、盾数值、战绩写改了什么、[HellBox] 房间这一版叫 V0.94； 2026-11-15 用户定：潜兵页、潜兵数据、分屏 2.0 这一版叫 V0.93；V0.92 = 新界面（UI 交给 Claude）；V0.91 = 数据修改页、战绩修复等
VERSION_NOTE = ""  # 2026-11-19 V1.0 正式版不再带「发行抢先版」； 版本说明（2026-11-14 用户要求）；2026-11-19 起不再写「群友测试版」；2026-11-19 用户：「还是叫发行抢先版吧」
POLL_MS = 2000
MASTER_HELP = ("核心：HellBox 所有功能的总开关。\n打开 = 把 HellBox 的脚本和指针装进游戏；关闭 = 游戏换回原版文件。"
               "\n要先关游戏才能拨。")
DEV_FILE = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox", "dev.txt")


def load_dev():
    """开发者模式存在 %APPDATA%\\Arrowhead\\Helldivers\\hellbox\\dev.txt（"1" = 开）。"""
    try:
        with open(DEV_FILE, encoding="ascii") as f:
            return f.read().strip() == "1"
    except (OSError, ValueError):
        return False


# 2026-11-19 用户要：「K-ON!增强UI定制版」开关（「关于 · 设置」里）。开着时左边只有 功能 / 玩法 / 数据 / 指针 / 关于，
#   优先于普通 / 开发者模式（开发者模式照样管数据页的样子、分屏在游戏里开不开）。存在 hellbox\kon.txt（"1" = 开）。
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
UNKNOWN_HELP = ("HellBox 认不出现在的游戏脚本（可能装过别的 MOD，或其他版本的 HellBox），为安全起见不修改。"
                "点「核心」开关旁边的「恢复原版」：有原版备份就直接换回，没有就让 Steam 检查修复游戏文件。")
CURSOR_TEXT = {  # 2026-11-15 用户要求顶栏字短：原版 / 替换
    "on": ("替换", ui.MINT),
    "old": ("待更新", ui.YELLOW),
    "off": ("原版", ui.DISABLED),
    "unknown": ("无法识别", ui.SALMON),
}


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.busy = False
        self.busy_text = ""  # 正在做什么（底栏显示，带已用秒数）
        self.busy_since = 0.0
        self.state = {"running": None, "script": None, "cursor": None, "game_dir": ""}
        self.pending_install = False  # 游戏开着时热改过设置：等游戏关了自动装一次
        self.auto_updated = False  # 装的是旧版 mod 时自动更新过了没有
        self.old_told = False  # 「游戏里是旧版 MOD」在状态栏说过了没有（2026-11-15）
        self.unknown_told = False  # 「认不出游戏脚本」的处理办法在状态栏说过一次了没有
        self.bridge = ui.Bridge()  # 后台线程把"回到界面线程要做的事"发到这里
        self.pages = []
        self.current = None
        self.root = self  # 老代码里的 app.root
        self.version, self.version_note = VERSION, VERSION_NOTE  # 「关于」页用

        note = VERSION_NOTE
        if not note and os.path.isfile(os.path.join(paths.MOD, "data_full")):  # 2026-11-19 自用全数据版
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
        self.dev = load_dev()  # 开发者模式（藏起来的：「关于」页版本号连点 10 次打开）
        self.kon = load_kon()  # K-ON!增强UI定制版（「关于 · 设置」里的开关）
        lay.addWidget(self._build_header())
        lay.addWidget(ui.ink_line(3))
        # 2026-11-15 新界面（UI 交给 Claude 设计，群友认可）：左侧导航平铺分组、嵌在背景里，右边整块给页面
        body, bl = ui.hbox()
        self.nav_slot, self.nav_lay = ui.vbox()
        bl.addWidget(self.nav_slot)
        self.stage = QStackedWidget()
        bl.addWidget(self.stage, 1)
        lay.addWidget(body, 1)
        lay.addWidget(ui.ink_line(2))
        # 底栏两行：最近一条消息；鼠标停在某一项上时换成它的说明（代替原来的「?」）
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
        """顶栏一行（2026-11-15 新界面）：HELLBOX 版本号 [DEV] …… [核心没开 →] CN/EN  游戏 运行中/未运行。
        「核心」开关、恢复原版、游戏位置挪进「关于 · 设置」（self.master / self.btn_vanilla 在这里建、关于页摆）；
        指针状态挪到指针页顶上。核心没开 / 认不出游戏文件时，顶栏才冒出红色按钮，点了去「关于」。"""
        head, hl = ui.hbox(margins=(20, 0, 18, 0))
        head.setFixedHeight(52)
        ui.filled(head, ui.HEADER)
        VC = Qt.AlignmentFlag.AlignVCenter
        hl.addWidget(ui.Label("HELLBOX", font=ui.f_pixel(15)), 0, VC)
        hl.addSpacing(10)
        hl.addWidget(ui.Tag(head, VERSION, fill=ui.CARD, font=ui.f_pixel(8, False)), 0, VC)
        hl.addSpacing(8)
        self.dev_tag = ui.Tag(head, "DEV", fill=ui.SALMON, font=ui.f_pixel(8))
        ui.hover_help(self.dev_tag, "开发者模式", "开着：数据页按单只怪、单把枪细改，左边多了「日志」。在「关于 · 设置」里关。")
        hl.addWidget(self.dev_tag, 0, VC)
        hl.addSpacing(6)
        self.kon_tag = ui.Tag(head, "K-ON!", fill=ui.SKY, font=ui.f_pixel(8))
        ui.hover_help(self.kon_tag, "K-ON!增强UI定制版", "开着：左边只有 功能 / 玩法 / 数据 / 指针 / 关于。在「关于 · 设置」里关。")
        hl.addWidget(self.kon_tag, 0, VC)
        self.kon_tag.setVisible(self.kon)
        hl.addStretch(1)
        self.core_warn = ui.Button(head, "核心没开 →", lambda: self.show_page("about"), kind="danger",
                                   font=ui.f_zh(9, True), padx=10, pady=2, shadow=3)
        self.core_warn.setVisible(False)
        hl.addWidget(self.core_warn, 0, VC)
        hl.addSpacing(14)
        # 中英文切换（2026-11-14 用户要求）：点另一个就切，HellBox 自己重开一次
        self.lang = ui.Var(i18n.LANG)
        hl.addWidget(ui.Segmented(head, [("zh", "CN"), ("en", "EN")], self.lang, command=self._switch_lang,
                                  font=ui.f_mono(9, True), padx=7, pady=2, shadow=2), 0, VC)
        hl.addSpacing(14)
        self.chip_game = ui.Chip(head, "游戏")
        hl.addWidget(self.chip_game, 0, VC)
        # 「核心」开关和［恢复原版］：在这里建好，「关于」页把它们摆进「设置」「出问题了」两张卡
        self.master_on = ui.Var(False)
        self.master = ui.Toggle(None, self.master_on, command=self._flip_master)
        self.master.blocked = self._master_blocked
        self.btn_vanilla = ui.Button(None, "恢复原版", self._restore_vanilla, font=ui.f_zh(9, True),
                                     padx=9, pady=2, shadow=2)
        return head

    # ------------------------------------------------------------ 开发者模式
    def set_dev(self, on, quiet=False):
        """开 / 关开发者模式：顶栏 DEV 牌、导航里的「潜兵」「日志」「分屏」、数据页的样子；存下来，下次打开还是这样。
        分屏在游戏里也跟着这个开关（mod/src/camera_link.lua 读 dev.txt，2026-11-19）。"""
        self.dev = bool(on)
        if not quiet:
            save_dev(self.dev)
        self.dev_tag.setVisible(self.dev)
        for p in self.pages:
            p.set_dev(self.dev)
        self._apply_nav()

    def set_kon(self, on):
        """开 / 关「K-ON!增强UI定制版」：左边只留 功能 / 玩法 / 数据 / 指针 / 关于（2026-11-19 用户要）；存下来。"""
        self.kon = bool(on)
        save_kon(self.kon)
        self.kon_tag.setVisible(self.kon)
        self._apply_nav()

    def hidden_pages(self):
        """现在左边藏起来的页面：K-ON! 开着 = 除了 KON_PAGES 全藏（盖过开发者模式）；否则普通模式藏 DEV_ONLY。"""
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
        """核心开关现在为什么点不了（灰着被点时在底栏说；鼠标停上去也看得到）。"""
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
            cursor_mod.apply_saved()  # 2026-11-20：指针按存过的设置，没存过 = 原版（以前这里会强行打开改色、默认亮绿）
            return "MOD 已装上。"

        def restore_all():
            import build
            import cursor_mod
            left = build.restore()
            cursor_mod.restore(keep_setting=True)  # 指针换回原版，但记住玩家的设置，下次开核心照样装回去
            if left:
                return T("已恢复原版。有 {0} 个地图文件当初选了不备份，还是鬼城配色（不影响正常玩）；"
                         "要完全恢复原版，请在 Steam 里验证游戏文件完整性。", left)
            return "已恢复原版。"

        if on:
            if not self._ask_map_backup():
                self.master_on.set(False)  # 取消了：开关拨回去，什么都不动
                return
            self.run(install_all, working="正在安装 MOD（第一次要几分钟，机械硬盘更久），先别开游戏…")
        else:
            self.run(restore_all, working="正在还原成原版，先别开游戏…")

    MAP_BACKUP_TEXT = (
        "第一次打开「核心」，要给 45 个地图文件换上鬼城配色。先选一下要不要备份原版地图：\n\n"
        "· 备份地图：多占约 1.3GB，第一次更慢一些；以后在「关于」里关掉「核心」就能一键恢复原版。\n"
        "· 不备份：快很多；以后要恢复原版地图，需要在 Steam 里「验证游戏文件完整性」"
        "（Steam 会重新下载改过的 45 个地图文件）。\n\n"
        "不管选哪个，游戏脚本的小备份都会留着；以后更新 HellBox 也不受影响。")

    def _ask_map_backup(self):
        """2026-11-19 发行抢先版（用户定）：第一次开核心、还没选过也没有地图备份时，弹窗选备不备份原版地图。取消 = False。"""
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
        """认不出游戏脚本时：有核对过的原版备份就直接换回；没有就请 Steam 检查修复游戏文件（2026-11-14 用户要求）。"""
        if self.busy or self.state["running"] is not False:
            self.say("请先关闭游戏再恢复。", "warn")
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
            return "已恢复原版，现在可以打开「核心」开关了。"

        def done(ok, has):
            import build
            if not ok:
                self.error(T('没有完成：{0}', has))
            elif has:
                if self.ask("找到了原版备份（已核对是未改过的原版文件）。\n用它把认不出的游戏文件换回原版吗？"):
                    self.run(restore_parts, working="正在恢复原版，先别开游戏…")
            elif self.ask("这台电脑上没有原版备份。\n要让 Steam 检查并修复游戏文件吗？"
                          "Steam 会把改过的文件重新下载成原版，一般一两分钟。"):
                try:
                    build.open_steam_verify()
                except OSError as e:
                    self.error(T('打不开 Steam：{0}', e))
                    return
                self.say("已让 Steam 检查游戏文件，完成后这里会自动刷新。", "info")
                self._steam_wait(120)

        self.bg(check, done)

    def _steam_wait(self, left):
        """Steam 修复期间每 5 秒重读一次状态，认出来了（或 10 分钟到了）就停。"""
        if "unknown" not in (self.state.get("script"), self.state.get("cursor")) or left <= 0:
            if self.state.get("script") == "off":
                self.say("Steam 已修复游戏文件，现在可以打开「核心」开关了。", "ok")
            return
        if not self.busy:
            self.refresh_status()
        self.after(5000, lambda: self._steam_wait(left - 1))

    def _switch_lang(self, lang):
        """换语言：存下来，带着当前页重开 HellBox（界面文字是建页面时定的，重开最稳）。"""
        if self.busy:
            self.lang.set(i18n.LANG)
            self.say("正在改游戏文件，做完再切换语言。", "warn")
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
        """「核心」开关（原 MOD 总开关）是不是开着（各页用来决定控件能不能点）。"""
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
        """「关于 · 设置」里核心那一行的灰字：现在的状态 / 为什么点不了。"""
        script = self.state["script"]
        reason = self._master_reason()
        if reason:
            return reason
        if script == "old":
            return "MOD 有新版本，关闭游戏后会自动更新。"
        return {"on": "已装好", "off": "没开：游戏是原版", "unknown": "认不出游戏文件"}.get(script, "")

    def sync(self):
        """状态变了：顶栏状态牌、每一页的按钮可不可用都重算。"""
        running = self.state["running"]
        if running is None:
            self.chip_game.set("…", ui.DISABLED)
        else:
            self.chip_game.set("运行中" if running else "未运行", ui.YELLOW if running else ui.DISABLED)
        script = self.state["script"]
        unknown = "unknown" in (script, self.state.get("cursor"))
        # 顶栏只在出问题时冒出红色按钮：核心没开 / 认不出游戏文件
        self.core_warn.set_text("认不出游戏文件 →" if unknown else "核心没开 →")
        self.core_warn.setVisible(not self.busy and (unknown or script == "off"))
        if not self.busy and self.master_on.get() != self.mod_on():
            self.master_on.set(self.mod_on())  # 失败时开关弹回实际状态
        self.master.set_enabled(not self.busy and running is False and script not in (None, "unknown"))
        self.btn_vanilla.set_enabled(unknown and not self.busy and running is False)
        tip = tr(UNKNOWN_HELP) if unknown and not self.busy else ""
        if tip and not self.unknown_told:
            self.unknown_told = True
            self.say(UNKNOWN_HELP, "warn")
        if script == "old" and running and not self.old_told:
            self.old_told = True
            self.say("游戏里还是旧版 MOD，新加的功能在游戏里用不了。关掉游戏后 HellBox 会自动更新。", "warn")
        if script == "old" and running is False and not self.busy and not self.auto_updated:
            import build
            self.auto_updated = True  # 一次会话只自动更新一次，失败了不反复试
            self.after(0, lambda: self.run(build.install, "MOD 已更新到最新版本。", "MOD 是旧版本，正在更新…"))
        for p in self.pages:
            p.sync()

    # ------------------------------------------------------------ 后台任务
    def later(self, fn):
        """后台线程里调用：fn 回到界面线程执行。"""
        try:
            self.bridge.call.emit(fn)
        except RuntimeError:
            pass  # 窗口已经关了，后台活干完没处可回（2026-11-16 日志里的 Signal source has been deleted）

    def after(self, ms, fn):
        """ms 毫秒后在界面线程调 fn（代替 tk 的 root.after）。"""
        return ui.after(ms, fn)

    def bg(self, work, done=None):
        """在后台跑 work()，不锁界面；done(ok, 结果) 回到界面线程。"""
        def go():
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    res = (True, work())
            except Exception as e:  # noqa: BLE001
                logbook.exception("HellBox", e)  # 后台任务失败：带出错位置记进日志本
                res = (False, e)
            if done:
                self.later(lambda: done(*res))
        threading.Thread(target=go, daemon=True).start()

    def _busy_hint(self):
        import time
        sec = int(time.monotonic() - self.busy_since)
        step = getattr(self, "busy_step", None)
        if step:  # 2026-11-19：装核心时报到第几个地图包了
            return T('{0}（鬼城地图：{1} / {2}，{3} 秒）', self.busy_text.rstrip('…'), step[0], step[1], sec)
        return T('{0}（{1} 秒）', self.busy_text.rstrip('…'), sec)

    def _busy_tick(self):
        """忙的时候每秒刷新底栏（已用秒数），让人知道没卡住。"""
        if not self.busy:
            return
        self.footer.say(self._busy_hint(), "warn")
        self.after(1000, self._busy_tick)

    def run(self, action, ok_msg=None, working="处理中…"):
        """会改游戏文件的操作：一次只跑一个，跑的时候所有按钮变灰。action 返回字符串就当提示显示。"""
        import time
        if self.busy:
            return
        self.busy = True
        self.busy_text = working
        self.busy_since = time.monotonic()
        self.busy_step = None
        try:  # 装核心时鬼城每做完一个地图包报一次（后台线程里只改这个元组，底栏每秒自己读）
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
                except Exception:  # noqa: BLE001
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
                self.refresh_status()  # 游戏开了 / 关了（包括崩了）：重新读一遍游戏文件，状态牌和开关跟着对上
        if running is False and changed:
            # 2026-11-19 闪退探针：游戏刚关 / HellBox 刚开时游戏没在运行 → 看上次是不是闪退了（logbook.check_probe）
            def told(ok, msg):
                if ok and msg:
                    self.say(msg, "warn")
            self.bg(logbook.check_probe, told)
        if not running and self.pending_install and not self.busy:
            import build
            self.pending_install = False
            self.run(build.install, "游戏关了，新设置已装进 mod，下次开游戏也是这样。", "游戏关了，正在把新设置装进 mod…")


def main():
    if sys.platform == "win32":  # 任务栏图标用 HellBox 自己的，不跟 python 合并
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HellBox.HD1")
        except (AttributeError, OSError):
            pass
    logbook.install()
    qapp = QApplication(sys.argv[:1])
    qapp.setWheelScrollLines(1)  # 滚轮一格 = 40 像素（DotPage 里的步长）
    ui.load_fonts(paths.FONTS)
    qapp.setFont(ui.f_zh(10))
    qapp.setStyleSheet(ui.TIP_STYLE)  # 鼠标提示统一成方块风
    app = App()
    if "--page" in sys.argv and app.pages:  # HellBox.exe --page quick：直接打开某一页
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
