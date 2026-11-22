"""功能页（原 MOD 开关页）：装进 mod 的各个小功能。2026-11-15 新界面：按用途分组，一行一个功能，鼠标停上去底栏出说明。

2026-11-13 用户定（发行版调整）：
- 总开关和「游戏开没开」挪到标签栏右边（app._build_master），这一页不再放「脚本 mod」「游戏」两张卡；
  总开关没开时，这一页的控件全是灰的。
- 去掉「QoL 增强」总开关和「高档阴影」。
- 刷新星球、报复关都用一排方块选（和原来「报复打击概率」一样），不用下拉框。
- 报复关：原来的报复打击概率换成「每颗星球固定几个报复关」（原版 / 0 / 1 / 2 / 3）。
2026-11-14 V0.91：小功能开关和带箱子上车改成热生效（写 options.txt，游戏每秒读）；名字、战线、点赞走信箱热发，
关游戏时 HellBox 开着的话再自动装一次记住（app.pending_install）。
2026-11-21 HD1-038 用户定：来自 QoL Mod 的功能全部删掉（QoL 作者希望两个 MOD 各自独立、能一起装）；只留我们自己先做的刷新星球、报复关数量、
解锁其他战线，不再标来源。
"""
import build
import hellbox_options as options
import ui
from pages import profile_feed
from pages.base import Page
from pages.hop_rows import HopRows
from pages.options_widgets import apply
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

POLL_MS = 2000
LHGRZR = "来自 Lhgrzr"  # 2026-11-19 补给背包热键、隐藏样本描边（用户给的署名）
HALFSUGAR = "来自 半糖（HalfSugar）"  # 2026-11-19 聊天输入法防闪退（和分屏一样署 HalfSugar）
# 2026-11-21 HD1-038：Dive Harder 作者同意收进来。它独有的署 Oct0pu5；修 QoL 的两处署两个人（用户原话「doggo & oct0pu5」）
OCT = "来自 Oct0pu5"
DOGGO_OCT = "来自 SomeDoggo & Oct0pu5"
# 2026-11-22 Dive Harder 作者建议：简化成一句（下面这几行的名字也是他建议的）
DH_YIELD = "此项已由 DH 提供"
QOL_BASED = "借鉴 QoL Mod"  # 2026-11-23 用户：过场加速写回来，「标注是借鉴qol并需要给跟qol兼容」
SPEED_OPTIONS = [(n, f"×{n}") for n in options.SPEEDS]

# 2026-11-23 V1.06：解锁战线三选一（build.FRONT_MODES）；保卫超级地球再选种族
FRONT_OPTIONS = [("", "关"), ("1", "普通星区"), ("home", "进攻母星"), ("se", "保卫超级地球")]
SE_RACES = [("1", "虫族"), ("2", "赛博人"), ("3", "光能族")]

# 报复关：存进 genocide.txt 的值沿用以前的百分比档位（mod 里 0/33/66/100 = 固定 0/1/2/3 个），"" = 原版
STRIKE_OPTIONS = [("", "原版"), ("0", "0 个"), ("33", "1 个"), ("66", "2 个"), ("100", "3 个")]
REFRESH_KEYS = [(k, v) for k, v in options.ACTIONS.items() if k]
DROP_KEYS = list(options.DROP_KEYS.items())
DROP_FIRST = list(options.DROP_FIRST.items())
SUPPLY_KEYS = list(options.SUPPLY_KEYS.items())
PING_WINDOWS = [(n, f"{n} 次") for n in options.PING_WINDOWS]


def _strike_value():
    g = build.get_genocide()
    s = "" if g is None else str(g)
    return s if s in dict(STRIKE_OPTIONS) else ""


# 让给 Obsidian 的开关在界面上叫什么（obsidian_compat.YIELDS 的键）
ROW_NAMES = {}  # 让给 Obsidian 的开关的中文名（2026-11-20 增强 HUD、醒目准星删了以后暂时没有）


class ModPage(Page):
    key = "mod"
    tab = "功能"
    when = "游戏开着也能改，下一秒生效"

    def build(self):
        cfg = options.load()
        self.controls = []  # 核心没开 / 忙的时候一起变灰
        self.flags = {}     # 开关型设置：key -> Var
        self.live_actions = None
        self.dh_rows = {}   # 来自 Dive Harder 的开关：key -> (开关, 灰字说明)；游戏里装了 Dive Harder 时变灰让给它
        self.reading_actions = False

        # 核心没开：页面最上面一条红色提示，点按钮去「关于」开
        self.off_card = ui.Box(None, fill=ui.SALMON, border=2, shadow=4, pad=(14, 10, 14, 10), vertical=False)
        self.off_card.lay.addWidget(ui.Label("「核心」没开，这页的功能都用不了。", font=ui.f_zh(10, True)), 0,
                                    ui.Qt.AlignmentFlag.AlignVCenter)
        self.off_card.lay.addStretch(1)
        self.off_card.lay.addWidget(ui.Button(None, "去「关于」打开", lambda: self.app.show_page("about"),
                                              font=ui.f_zh(9, True), padx=9, pady=2, shadow=2), 0,
                                    ui.Qt.AlignmentFlag.AlignVCenter)
        self.off_row = self.view.row(self.off_card)

        # 2026-11-20 HD1-036：游戏里装着 Obsidian（Alomare 的 MOD 管理器）时，说明 HellBox 让出了什么、哪里可能重叠
        self.obs_card = ui.Box(None, fill=ui.SKY, border=2, shadow=4, pad=(14, 10, 14, 10))
        self.obs_card.lay.addWidget(ui.Label("游戏里也装着 Obsidian，两边一起用", font=ui.f_zh(10, True)))
        self.obs_text = ui.Label("", font=ui.f_zh(9), wrap=True)
        self.obs_card.lay.addWidget(self.obs_text)
        self.obs_row = self.view.row(self.obs_card)
        self.obs_row.setVisible(False)
        self.obs_key = None

        # 2026-11-15 新界面：按用途分组（任务中 / 星图和飞船 / 联机和操作），一行一个功能，鼠标停上去底栏出说明
        self.st = None
        self.reading = False
        mission = ui.Card(self.view, "MISSION", "任务中", fill=ui.SALMON)
        self.carry_on = ui.Var(build.get_carry_vehicle())
        self.carry_toggle = self._ctl(ui.Toggle(None, self.carry_on, command=self.apply_carry))
        self._row(mission, "带箱子上车", "搬箱子时对着载具按 E，能带着箱子上车。下车后箱子会卡在手上，但到传送带前照样能交互放下。",
                  toggle=self.carry_toggle)
        # 2026-11-16 V0.95 丢战备：用户要求放「任务中」，键盘和手柄都能用（手柄没有空键，长按交互键）
        self.drop_key = ui.Var(cfg["drop_key"] if cfg["drop_key"] in options.DROP_KEYS else "x")
        self.seg_drop = self._ctl(ui.Segmented(None, DROP_KEYS, self.drop_key, command=self.set_drop_key,
                                               font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(mission, "丢支援装备", "丢的是支援武器和背包（不是战略配备）：手里拿着支援武器就丢它，不然丢背包。键盘按右边选的键；"
                                     "手柄身边没东西可交互时按住交互键（A）0.6 秒。倒地、搬箱子、坐车时不会触发。"
                                     "丢下的东西你和队友都能捡回来，队友不用装 HellBox。",
                  extras=(self.seg_drop,), flag="drop")
        # 2026-11-19 发行抢先版 用户要求：能选先丢武器还是先丢背包
        self.drop_first = ui.Var(cfg["drop_first"] if cfg["drop_first"] in options.DROP_FIRST else "")
        self.seg_drop_first = self._ctl(ui.Segmented(None, DROP_FIRST, self.drop_first, command=self.set_drop_first,
                                                     font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(mission, "先丢哪个", "丢支援装备时先丢哪一样。看手上：手里拿着支援武器就丢武器，不然丢背包（原来的做法）；"
                                   "先丢武器：有支援武器就丢武器，没有才丢背包；先丢背包：有背包就丢背包，没有才丢武器。",
                  extras=(self.seg_drop_first,))
        # 2026-11-19 用户要求收进来：Lhgrzr 写的补给背包热键（手柄改成长按换弹）和隐藏样本描边
        self.supply_key = ui.Var(cfg["supply_key"] if cfg["supply_key"] in options.SUPPLY_KEYS else "5")
        self.seg_supply = self._ctl(ui.Segmented(None, SUPPLY_KEYS, self.supply_key, command=self.set_supply_key,
                                                 font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(mission, "补给背包自己用", "背着补给背包时给自己补一次弹药，背包少一格，会做一下原本从背包拿弹药的动作（约 1 秒，这时收枪）。键盘按右边选的数字键（字母上面那排，小键盘不算）；"
                                       "手柄按住换弹键（RB）0.6 秒，换弹照常换。弹药满了、背包空了不会扣次数；"
                                       "倒地、搬箱子、坐车、打字时不会触发。",
                  extras=(self.seg_supply,), flag="supply", credit=LHGRZR)
        self._row(mission, "隐藏样本描边", "地上样本外面那圈发光的轮廓不显示。样本本身照样看得见、捡得起，侦察装备在地图上标样本照常。只改你自己的画面。",
                  flag="hide_samples", credit=LHGRZR)
        # 2026-11-20 HD1-035：HalfSugar 的 HelldiversOptimization（hop.txt 热生效）
        h = self.hop = HopRows(self)
        h.toggle(mission, "bolt_reload", "建构连续装填", "M2016「建构」按一下 R 就一发接一发装满（原版每装一发要再按）。"
                 "中途开枪就停。不改装填速度和弹药。", credit=HALFSUGAR)
        # 2026-11-21 HD1-038：来自 Dive Harder 的两项
        self.ping_window = ui.Var(cfg["ping_window"] if cfg["ping_window"] in options.PING_WINDOWS else 5)
        self.seg_ping = self._ctl(ui.Segmented(None, PING_WINDOWS, self.ping_window, command=self.set_ping_window,
                                               font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._dh_row(mission, "HUD 显示延迟", "任务里每个网上队友的状态卡片下面写他的延迟（往返毫秒数），"
                                                 "按最近几次取平均（右边选几次），不会一跳一跳。暂停菜单玩家列表里的延迟也改成往返，和这里对得上。"
                                                 "本机的人（你自己、分屏的 2P）不写。",
                     "dh_ping", OCT, extras=(self.seg_ping,))
        self._dh_row(mission, "自动定位任务位置", "任务里打问号的隐藏目标一开局就显示在地图上，不用先走过去发现。", "dh_hidden", OCT)
        self.view.row(mission)

        ship = ui.Card(self.view, "SHIP", "星图和飞船", fill=ui.YELLOW)
        self.flags["refresh"] = ui.Var(cfg["refresh"])
        self.refresh_key = ui.Var(cfg["action"] or "reload")
        self.seg_key = self._ctl(ui.Segmented(None, REFRESH_KEYS, self.refresh_key, command=self.set_key,
                                              font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self.btn_refresh = self._ctl(ui.Button(None, "现在刷新", self.refresh_now, font=ui.f_zh(9, True),
                                               padx=7, pady=2, shadow=2))
        self.key_hint = ui.Label("", font=ui.f_zh(9), fg=ui.BAD)
        self._row(ship, "刷新星球", "在飞船的选星界面按选好的键换一批星球：某个阵营的选星球界面只刷这个阵营（另外两个阵营不动）；"
                                    "星球里面只重抽这颗星的三关；右边「现在刷新」三个阵营全刷。要当房主，刷到的星球没打完的进度会清掉。灰掉的键：你用的键盘 / 手柄上它和菜单冲突，或者没有这个键（键盘没有单独的切换武器键）。",
                  note=self.key_hint, extras=(self.seg_key, self.btn_refresh), flag="refresh")
        self.strike = ui.Var(_strike_value())
        self.seg_strike = self._ctl(ui.Segmented(None, STRIKE_OPTIONS, self.strike, command=self.set_strike,
                                                 font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(ship, "报复关数量", "每颗星球固定带几个报复关（母星那 5 关也算，难度 3 那关不会是报复关）。原版：难度 4 以上每颗星球 33% 带 1 个。"
                                      "只影响之后新出的星球。",
                  extras=(self.seg_strike,))
        self.speed = ui.Var(cfg["speed_factor"] if cfg["speed_factor"] in options.SPEEDS else 3)
        self.seg_speed = self._ctl(ui.Segmented(None, SPEED_OPTIONS, self.speed, command=self.set_speed,
                                                font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(ship, "过场加速", "结算、进关过场、星球扫描这些过场按选的倍数快放；开着的话，开游戏时的片头动画直接跳过（视频没法快放）。能和 QoL Mod 一起装。",
                  extras=(self.seg_speed,), flag="speed", credit=QOL_BASED)
        # 2026-11-22 用户定：解锁其他战线发布版也有（以前只有自用版）
        mode = build.get_front_mode()
        self.front_mode = ui.Var("se" if mode.startswith("se") else mode)
        self.se_race = ui.Var(mode[2:] if mode.startswith("se") else "1")
        self.seg_front = self._ctl(ui.Segmented(None, FRONT_OPTIONS, self.front_mode, command=self.set_front,
                                                font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self.seg_se = self._ctl(ui.Segmented(None, SE_RACES, self.se_race, command=self.set_front,
                                             font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(ship, "解锁其他战线", "没开放的战线也能选：还没出场的从起点开始，已攻破的放回攻破前最后一个星区，正在打的不动。选「进攻母星」或「保卫超级地球」时，那颗星和 5 关（难度 3～15）直接出来，能用刷新键重抽；这些关只在自己游戏里打，不算进银河战争。游戏开着也能切，退出战役地图再进一次生效。",
                  extras=(self.seg_front, self.seg_se))
        self.view.row(ship)

        coop = ui.Card(self.view, "COOP", "联机和操作", fill=ui.SKY)
        self.cf_on = ui.Var(build.get_commend_friends())
        self.cf_toggle = self._ctl(ui.Toggle(None, self.cf_on, command=self.apply_commend))
        self.cf_left = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self._row(coop, "给好友点赞", "游戏里右键 Steam 好友也能点赞（原版不能给好友点赞）。次数照原版：每周 10 次，所有人共用；同一个人每周只能点一次（好友、路人都算，开关关着也算）。",
                  note=self.cf_left, toggle=self.cf_toggle)
        self._dh_row(coop, "好友列表自动刷新", "找房间时切到「好友」那一下马上刷新一次，好友的房间信息不用等原版自己刷。", "dh_friends", OCT)
        self.view.row(coop)

        # 2026-11-18 V0.96 用户定：修原版毛病的开关单独一组「Bug 修复」
        fix = ui.Card(self.view, "FIX", "Bug 修复", fill=ui.MINT)  # 2026-11-22 DH 作者建议：标题旁那句说明删掉
        self._row(fix, "冲刺时换弹不往前滑", "原版冲刺中换弹会锁着方向往前冲一段。开了以后换弹时松开摇杆 / 方向键就停，"
                                             "往哪推就往哪走。只管你自己的绝地潜兵，当客机也能用。",
                  flag="noslide")
        self._row(fix, "聊天输入法防闪退", "原版换房间后第一次在聊天框用中文输入法打字可能直接闪退，开了就不会；"
                                         "关聊天时顺手清掉输入法残留，免得输入法卡住键盘。",
                  flag="ime_fix", credit=HALFSUGAR)
        self._dh_row(fix, "配合 QoL 的两处修正", "只在游戏里装了 QoL Mod 时有用：结算、星球奖励界面的名字也照 QoL「名字用聊天字体」的设置；"
                                              "QoL 的选项名不再显示成「LOC:……」这种代码，改成能看懂的英文。没装 QoL 时什么都不改。",
                     "dh_qol_fix", DOGGO_OCT)
        self.view.row(fix)
        self.app.after(300, self._tick)

    # ------------------------------------------------------------ 小工具
    def _ctl(self, w):
        self.controls.append(w)
        return w

    def _row(self, card, title, help_text, note=None, extras=(), toggle=None, flag=None, first=False, credit=None):
        """一行：名字（+ 灰色小注）……［其他控件］［开关］。flag = 开关型设置的键（自动建开关）。
        credit = 功能来源（2026-11-19 用户要求标在对应功能下面；V0.9 时「下面功能借鉴 QoL Mod」那一组都标 QOL）。
        鼠标停在这一行上，底栏显示 help_text（2026-11-15 新界面，代替「?」）。"""
        if flag:
            self.flags[flag] = ui.Var(options.load()[flag])
            toggle = self._ctl(ui.Toggle(None, self.flags[flag], command=lambda: self._flag(flag)))
        items = []
        for x in extras:
            items += [x, 6]
        if toggle is None:
            gap = ui.QWidget()
            gap.setFixedSize(73, 1)  # 没开关的行也让右边的控件对齐
            toggle = gap
        items.append(toggle)
        return card.row(title, *items, help=help_text, sub=note, credit=credit)

    def _dh_row(self, card, title, help_text, flag, credit, extras=()):
        """来自 Dive Harder 的一行：和普通开关一样，多一行灰字（装了 Dive Harder 时写让给它）。"""
        note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self._row(card, title, help_text, note=note, extras=extras, flag=flag, credit=credit)
        self.dh_rows[flag] = (self.controls[-1], note)
        note.setVisible(False)

    def _flag(self, key):
        apply(self.app, {key: bool(self.flags[key].get())})

    # ------------------------------------------------------------ 刷新星球 / 报复关 / 丢装备 / 补给键
    def set_key(self, value):
        apply(self.app, {"action": value})

    def set_drop_key(self, value):
        apply(self.app, {"drop_key": value})

    def set_drop_first(self, value):
        apply(self.app, {"drop_first": value})

    def set_supply_key(self, value):
        apply(self.app, {"supply_key": value})

    def set_ping_window(self, value):
        apply(self.app, {"ping_window": int(value)})

    def set_speed(self, value):
        apply(self.app, {"speed_factor": int(value)})

    def refresh_now(self):
        from room_name_live import MAGIC_REFRESH, live_set

        def action():
            if not build.game_running():
                raise RuntimeError("刷新星球要在游戏开着时点（在飞船里，没进任务）。")
            live_set("", magic=MAGIC_REFRESH)
            return "已刷新：战役地图开着就当场换一批新星球；没开的话下次打开地图时换。"

        self.app.run(action)

    def set_front(self, _value=None):
        mode = self.front_mode.get()
        if mode == "se":
            mode = "se" + (self.se_race.get() or "1")
        self._campaign(lambda: build.set_front_mode(mode))

    def set_strike(self, value):
        self._campaign(lambda: build.set_genocide(int(value) if value else None))

    def _campaign(self, update):
        def action():
            update()
            if build.game_running():
                from room_name_live import MAGIC_FRONT, live_set
                live_set(build.front_mail(), magic=MAGIC_FRONT)
                self.app.pending_install = True
                return "已改，之后新出的星球生效。关游戏时 HellBox 别关，会自动记住。"
            if build.status() in ("on", "old"):
                build.install()
            return "已改，下次开游戏生效。"

        self.app.run(action)

    def _read_actions(self):
        from room_name_live import MAGIC_REFRESH, live_read
        try:
            sequence, text = live_read(MAGIC_REFRESH, tries=1)
        except RuntimeError:
            # 游戏正在开 / 关、或者还是旧版 MOD：读不到就当没读到，下次再试（2026-11-16 别再记进日志吓人）
            return None
        if not sequence:
            return None
        return tuple(a for a in text.split(",") if a and a in options.ACTIONS)

    def _got_actions(self, ok, result):
        self.reading_actions = False
        if ok and result is not None:
            self.live_actions = result
        self.sync()

    # ------------------------------------------------------------ 带箱子上车 / 点赞
    def apply_carry(self):
        on = self.carry_on.get()

        def action():
            build.set_carry_vehicle(on)
            build.write_live_options()  # 2026-11-14 V0.91：热切换，游戏每秒读 options.txt
            word = tr("打开") if on else tr("关闭")
            if build.game_running():
                return T('带箱子上车已{0}，游戏里下一秒生效。', word)
            return T('带箱子上车已{0}。', word)

        self.app.run(action)

    def _tick(self):
        running = self.app.state["running"]
        if self.app.current is self and running and not self.reading:
            self.reading = True
            self.app.bg(profile_feed.read, self._got)
        elif not running:
            self._show_cf(None)
        if self.app.current is self and running and not self.reading_actions:
            self.reading_actions = True
            self.app.bg(self._read_actions, self._got_actions)
        self.app.after(POLL_MS, self._tick)

    def on_show(self):
        if self.app.state["running"] and not self.reading:
            self.reading = True
            self.app.bg(profile_feed.read, self._got)

    def _got(self, ok, st):
        self.reading = False
        self._show_cf(st if ok else None)

    def _show_cf(self, st):
        self.st = st
        if st and st["ok"]:
            self.cf_left.config(text=T('本周还剩 {0} 次。', st['cl']), fg=ui.MUTED if st["cl"] > 0 else ui.BAD)
        else:
            self.cf_left.config(text="", fg=ui.MUTED)

    def apply_commend(self):
        on = self.cf_on.get()

        def action():
            build.set_commend_friends(on)
            word = tr("打开") if on else tr("关闭")
            if build.game_running():
                profile_feed.send("cf=1" if on else "cf=0")
                self.app.pending_install = True
                return T('好友点赞已{0}，下次打开右键菜单生效。关游戏时 HellBox 别关，会自动记住。', word)
            if build.status() in ("on", "old"):
                build.install()
            return T('好友点赞已{0}，下次开游戏生效。', word)

        self.app.run(action)

    # ------------------------------------------------------------ 同步
    def _sync_obsidian(self):
        """Obsidian 那张卡：内容变了才去后台重算（要读补丁文件），算完再填。"""
        try:
            import obsidian_compat
            st = obsidian_compat.state()
        except Exception:
            st = {"deployed": False, "mods": {}}
        key = (st["deployed"], tuple(sorted((k, tuple(sorted(v.items()))) for k, v in st["mods"].items())))
        if key == self.obs_key:
            return
        self.obs_key = key
        if not st["deployed"]:
            self.obs_row.setVisible(False)
            return

        def work():
            import obsidian_compat
            given = obsidian_compat.yields()
            lines = [T("HellBox 的补丁和 Obsidian 的放在一起，谁也不删谁；同一处都改了的，排在后面的那个算数。")]
            if given:
                lines.append(T("HellBox 这几项让给 Obsidian（那边关掉就自动恢复）：{0}",
                               "、".join(T("{0}（那边开着 {1}）", tr(ROW_NAMES.get(k, k)), v) for k, v in given.items())))
            lines += obsidian_compat.notes()
            return "\n".join("· " + x for x in lines)

        def done(ok, text):
            if ok:
                self.obs_text.config(text=text)
                self.obs_row.setVisible(True)

        self.app.bg(work, done)

    def sync(self):
        on = self.app.mod_on()
        live = on and not self.app.busy
        self.off_row.setVisible(self.app.state["script"] is not None and not on)
        self._sync_obsidian()
        for w in self.controls:
            w.set_enabled(live)
        self.hop.sync(live)
        if self.app.busy:
            return
        cfg = options.load()
        for key, var in self.flags.items():
            if var.get() != cfg[key]:
                var.set(cfg[key])  # 失败时开关弹回实际状态
        for var, val in ((self.carry_on, build.get_carry_vehicle()), (self.cf_on, build.get_commend_friends()),
                         (self.strike, _strike_value()),
                         (self.ping_window, cfg["ping_window"] if cfg["ping_window"] in options.PING_WINDOWS else 5),
                         (self.speed, cfg["speed_factor"] if cfg["speed_factor"] in options.SPEEDS else 3)):
            if var.get() != val:
                var.set(val)
        mode = build.get_front_mode()
        if self.front_mode.get() != ("se" if mode.startswith("se") else mode):
            self.front_mode.set("se" if mode.startswith("se") else mode)
        if mode.startswith("se") and self.se_race.get() != mode[2:]:
            self.se_race.set(mode[2:])
        self.seg_se.set_enabled(live and mode.startswith("se"))
        drop_key = cfg["drop_key"] if cfg["drop_key"] in options.DROP_KEYS else "x"
        if self.drop_key.get() != drop_key:
            self.drop_key.set(drop_key)
        self.seg_drop.set_enabled(live and cfg["drop"])
        drop_first = cfg["drop_first"] if cfg["drop_first"] in options.DROP_FIRST else ""
        if self.drop_first.get() != drop_first:
            self.drop_first.set(drop_first)
        self.seg_drop_first.set_enabled(live and cfg["drop"])
        supply_key = cfg["supply_key"] if cfg["supply_key"] in options.SUPPLY_KEYS else "5"
        if self.supply_key.get() != supply_key:
            self.supply_key.set(supply_key)
        self.seg_supply.set_enabled(live and cfg["supply"])
        if cfg["action"] and self.refresh_key.get() != cfg["action"]:
            self.refresh_key.set(cfg["action"])
        # 和菜单键（翻页、返回、确认……）冲突的键灰掉：游戏开着时 mod 会报哪些键能用
        self.seg_key.allowed = self.live_actions if self.live_actions is not None else None
        self.seg_key.set_enabled(live and cfg["refresh"])
        self.seg_key.update()
        self.btn_refresh.set_enabled(live and bool(self.app.state["running"]))
        dh = build.dive_harder_on()
        for key, (toggle, note) in self.dh_rows.items():
            if dh:
                toggle.set_enabled(False)
            text = tr(DH_YIELD) if dh else ""
            if note.text() != text:
                note.config(text=text)
                note.setVisible(bool(text))
        self.seg_ping.set_enabled(live and cfg["dh_ping"] and not dh)
        self.seg_speed.set_enabled(live and cfg["speed"])
        if self.live_actions is None:
            hint = ""
        elif cfg["action"] not in self.live_actions:
            hint = "这个键在你用的键盘 / 手柄上用不了，换一个。"
        else:
            hint = ""
        self.key_hint.config(text=hint)
        self.key_hint.setVisible(bool(hint))
