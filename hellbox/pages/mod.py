"""
功能页：HellBox 装进游戏的各个小功能，按用途分组显示，鼠标悬停时底栏显示说明。
"""
import build
import hellbox_options as options
import ui
from pages import profile_feed
from pages.base import Page
from pages.hop_rows import HopRows
from pages.options_widgets import apply
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

POLL_MS = 2000
LHGRZR = "来自 Lhgrzr"
HALFSUGAR = "来自 半糖（HalfSugar）"
OCT = "来自 Oct0pu5"
DOGGO_OCT = "来自 SomeDoggo & Oct0pu5"
DH_YIELD = "此项已由 DH 提供"

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


ROW_NAMES = {}


class ModPage(Page):
    key = "mod"
    tab = "功能"
    when = "游戏运行时也能修改，立即生效"

    def build(self):
        cfg = options.load()
        self.controls = []
        self.flags = {}
        self.live_actions = None
        self.dh_rows = {}
        self.reading_actions = False

        self.off_card = ui.Box(None, fill=ui.SALMON, border=2, shadow=4, pad=(14, 10, 14, 10), vertical=False)
        self.off_card.lay.addWidget(ui.Label("「核心」未开启，本页功能不可用。", font=ui.f_zh(10, True)), 0,
                                    ui.Qt.AlignmentFlag.AlignVCenter)
        self.off_card.lay.addStretch(1)
        self.off_card.lay.addWidget(ui.Button(None, "去「关于」打开", lambda: self.app.show_page("about"),
                                              font=ui.f_zh(9, True), padx=9, pady=2, shadow=2), 0,
                                    ui.Qt.AlignmentFlag.AlignVCenter)
        self.off_row = self.view.row(self.off_card)

        self.obs_card = ui.Box(None, fill=ui.SKY, border=2, shadow=4, pad=(14, 10, 14, 10))
        self.obs_card.lay.addWidget(ui.Label("游戏里也装着 Obsidian，两边一起用", font=ui.f_zh(10, True)))
        self.obs_text = ui.Label("", font=ui.f_zh(9), wrap=True)
        self.obs_card.lay.addWidget(self.obs_text)
        self.obs_row = self.view.row(self.obs_card)
        self.obs_row.setVisible(False)
        self.obs_key = None

        self.st = None
        self.reading = False
        mission = ui.Card(self.view, "MISSION", "任务中", fill=ui.SALMON)
        self.carry_on = ui.Var(build.get_carry_vehicle())
        self.carry_toggle = self._ctl(ui.Toggle(None, self.carry_on, command=self.apply_carry))
        self._row(mission, "带箱子上车", "搬箱子时对着载具按 E，能带着箱子上车。下车后箱子会卡在手上，到传送带前可交互放下。",
                  toggle=self.carry_toggle)
        self.drop_key = ui.Var(cfg["drop_key"] if cfg["drop_key"] in options.DROP_KEYS else "x")
        self.seg_drop = self._ctl(ui.Segmented(None, DROP_KEYS, self.drop_key, command=self.set_drop_key,
                                               font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(mission, "丢支援装备", "丢下支援武器和背包：手里拿着支援武器就丢它，不然丢背包。手柄需要按住交互键（A）0.6 秒。",
                  extras=(self.seg_drop,), flag="drop")
        self.drop_first = ui.Var(cfg["drop_first"] if cfg["drop_first"] in options.DROP_FIRST else "")
        self.seg_drop_first = self._ctl(ui.Segmented(None, DROP_FIRST, self.drop_first, command=self.set_drop_first,
                                                     font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(mission, "先丢哪个", "",
                  extras=(self.seg_drop_first,))
        self.supply_key = ui.Var(cfg["supply_key"] if cfg["supply_key"] in options.SUPPLY_KEYS else "5")
        self.seg_supply = self._ctl(ui.Segmented(None, SUPPLY_KEYS, self.supply_key, command=self.set_supply_key,
                                                 font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(mission, "补给背包自己用", "背着补给背包时随时给自己补一次弹药"
                                       "手柄按住换弹键（RB）0.6 秒。",
                  extras=(self.seg_supply,), flag="supply", credit=LHGRZR)
        self._row(mission, "隐藏样本描边", "样本发光轮廓不显示。",
                  flag="hide_samples", credit=LHGRZR)
        h = self.hop = HopRows(self)
        h.toggle(mission, "bolt_reload", "建构连续装填", "M2016 “建构” 按一下 R 就一发接一发换弹直到装满，"
                 "中途开枪就停。", credit=HALFSUGAR)
        self.ping_window = ui.Var(cfg["ping_window"] if cfg["ping_window"] in options.PING_WINDOWS else 5)
        self.seg_ping = self._ctl(ui.Segmented(None, PING_WINDOWS, self.ping_window, command=self.set_ping_window,
                                               font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._dh_row(mission, "HUD 显示延迟", "在队友的状态卡片下标注延迟。",
                     "dh_ping", OCT, extras=(self.seg_ping,))
        self._dh_row(mission, "自动定位任务位置", "黄色问号表示的未定位目标一开局就显示在地图上。", "dh_hidden", OCT)
        self.view.row(mission)

        ship = ui.Card(self.view, "SHIP", "星图和飞船", fill=ui.YELLOW)
        self.flags["refresh"] = ui.Var(cfg["refresh"])
        self.refresh_key = ui.Var(cfg["action"] or "reload")
        self.seg_key = self._ctl(ui.Segmented(None, REFRESH_KEYS, self.refresh_key, command=self.set_key,
                                              font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self.btn_refresh = self._ctl(ui.Button(None, "现在刷新", self.refresh_now, font=ui.f_zh(9, True),
                                               padx=7, pady=2, shadow=2))
        self.key_hint = ui.Label("", font=ui.f_zh(9), fg=ui.BAD)
        self._row(ship, "刷新星球", "在飞船的选星界面按选好的键换一批星球：右边「现在刷新」三个阵营全刷。需为房主，刷到的星球中未完成的进度会被清除。",
                  note=self.key_hint, extras=(self.seg_key, self.btn_refresh), flag="refresh")
        self.strike = ui.Var(_strike_value())
        self.seg_strike = self._ctl(ui.Segmented(None, STRIKE_OPTIONS, self.strike, command=self.set_strike,
                                                 font=ui.f_zh(9, True), padx=7, pady=2, shadow=2))
        self._row(ship, "报复关数量", "每颗星球固定带几个报复关。原版：难度 4 以上每颗星球 33% 带 1 个。只影响之后新出的星球。",
                  extras=(self.seg_strike,))
        if not build.is_public():
            self.front_on = ui.Var(build.get_front_unlock())
            self.front_toggle = self._ctl(ui.Toggle(None, self.front_on, command=self.set_front))
            self._row(ship, "解锁其他战线", "未开放的战线也能选择，尚未出场、已攻破的都算。尚未出场的直接开放，从起点开始；已攻破的放回攻破前最后一个星区。游戏运行时可切换，退出战役地图后再进入一次即可生效。",
                      toggle=self.front_toggle)
        self.view.row(ship)

        coop = ui.Card(self.view, "COOP", "联机和操作", fill=ui.SKY)
        self.cf_on = ui.Var(build.get_commend_friends())
        self.cf_toggle = self._ctl(ui.Toggle(None, self.cf_on, command=self.apply_commend))
        self.cf_left = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self._row(coop, "给好友点赞", "游戏里右键 Steam 好友也能点赞。每周 10 次",
                  note=self.cf_left, toggle=self.cf_toggle)
        self._dh_row(coop, "好友列表自动刷新", "多人界面切到「好友」马上刷新一次。", "dh_friends", OCT)
        self.view.row(coop)

        fix = ui.Card(self.view, "FIX", "Bug 修复", fill=ui.MINT)
        self._row(fix, "冲刺时换弹不往前滑", "原版冲刺中换弹会锁着方向往前冲一段。开了以后换弹时松开摇杆 / 方向键就停。",
                  flag="noslide")
        self._row(fix, "聊天输入法防闪退", "原版换房间后第一次在聊天框用中文输入法打字可能直接闪退，开了就不会。。",
                  flag="ime_fix", credit=HALFSUGAR)
        self._dh_row(fix, "配合 QoL 的两处修正", "只在游戏里装了 QoL Mod 时有用：结算、星球奖励界面的名字照 QoL「名字用聊天字体」的设置；"
                                              "QoL 的选项名不再显示成「LOC:……」，统一装进 MOD SETTINGS 列表。",
                     "dh_qol_fix", DOGGO_OCT)
        self.view.row(fix)
        self.app.after(300, self._tick)

    # ------------------------------------------------------------ 小工具
    def _ctl(self, w):
        self.controls.append(w)
        return w

    def _row(self, card, title, help_text, note=None, extras=(), toggle=None, flag=None, first=False, credit=None):
        if flag:
            self.flags[flag] = ui.Var(options.load()[flag])
            toggle = self._ctl(ui.Toggle(None, self.flags[flag], command=lambda: self._flag(flag)))
        items = []
        for x in extras:
            items += [x, 6]
        if toggle is None:
            gap = ui.QWidget()
            gap.setFixedSize(73, 1)
            toggle = gap
        items.append(toggle)
        return card.row(title, *items, help=help_text, sub=note, credit=credit)

    def _dh_row(self, card, title, help_text, flag, credit, extras=()):
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

    def refresh_now(self):
        from room_name_live import MAGIC_REFRESH, live_set

        def action():
            if not build.game_running():
                raise RuntimeError("刷新星球需要在游戏运行时点击（在飞船中，未进入任务）。")
            live_set("", magic=MAGIC_REFRESH)
            return "已刷新：战役地图打开时立即更换一批新星球；未打开则下次打开地图时更换。"

        self.app.run(action)

    def set_front(self):
        on = self.front_on.get()
        self._campaign(lambda: build.set_front_unlock(on))

    def set_strike(self, value):
        self._campaign(lambda: build.set_genocide(int(value) if value else None))

    def _campaign(self, update):
        def action():
            update()
            if build.game_running():
                from room_name_live import MAGIC_FRONT, live_set
                live_set(build.front_mail(), magic=MAGIC_FRONT)
                self.app.pending_install = True
                return "已改，之后新出的星球生效。"
            if build.status() in ("on", "old"):
                build.install()
            return "已改，下次开游戏生效。"

        self.app.run(action)

    def _read_actions(self):
        from room_name_live import MAGIC_REFRESH, live_read
        try:
            sequence, text = live_read(MAGIC_REFRESH, tries=1)
        except RuntimeError:
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
            build.write_live_options()
            word = tr("打开") if on else tr("关闭")
            if build.game_running():
                return T("带箱子上车已{0}，游戏内立即生效。", word)
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
                return T('好友点赞已{0}，下次打开右键菜单生效。', word)
            if build.status() in ("on", "old"):
                build.install()
            return T('好友点赞已{0}，下次开游戏生效。', word)

        self.app.run(action)

    # ------------------------------------------------------------ 同步
    def _sync_obsidian(self):
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
            lines = [T("HellBox 的补丁和 Obsidian 的放在一起，互不干扰。")]
            if given:
                lines.append(T("HellBox 这几项让给 Obsidian：{0}",
                               "、".join(T("{0}（Obsidian已开启 {1}）", tr(ROW_NAMES.get(k, k)), v) for k, v in given.items())))
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
                var.set(cfg[key])
        for var, val in ((self.carry_on, build.get_carry_vehicle()), (self.cf_on, build.get_commend_friends()),
                         (self.strike, _strike_value()),
                         (self.ping_window, cfg["ping_window"] if cfg["ping_window"] in options.PING_WINDOWS else 5)):
            if var.get() != val:
                var.set(val)
        if hasattr(self, "front_on") and self.front_on.get() != build.get_front_unlock():
            self.front_on.set(build.get_front_unlock())
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
        if self.live_actions is None:
            hint = ""
        elif cfg["action"] not in self.live_actions:
            hint = "这个键在你用的键盘 / 手柄上用不了。"
        else:
            hint = ""
        self.key_hint.config(text=hint)
        self.key_hint.setVisible(bool(hint))
