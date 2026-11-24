"""
「玩法」页：训练场的特殊玩法（HellBox 版与真训练场）；模式和规则在 pages/play_modes.py，游戏端是 mod/src/hellbox_play.lua。
"""
import random

import build
import ui
from pages import host_loadout as hl
from pages import map_picker
from pages import map_thumbs as mt
from pages import my_plays as mp
from pages import play_modes as pm
from pages import profile_feed
from pages import room_desc
from pages.base import Page
from pages.hop_rows import HopRows, numbers
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QTextLayout, QTextOption
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QVBoxLayout, QWidget

try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

POLL_MS = 1000
COLS = 4

TAG_TEXT = {"team": "共享", "self": "客机需装", None: "只有试炼场"}


def two_lines(text, font, width):
    lay = QTextLayout(text, font)
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    lay.setTextOption(opt)
    lay.beginLayout()
    starts = []
    while True:
        ln = lay.createLine()
        if not ln.isValid():
            break
        ln.setLineWidth(width)
        starts.append((ln.textStart(), ln.textLength()))
    lay.endLayout()
    if len(starts) <= 2:
        return [text[a:a + n].rstrip() for a, n in starts]
    first = text[starts[0][0]:starts[0][0] + starts[0][1]].rstrip()
    rest = text[starts[1][0]:]
    return [first, QFontMetrics(font).elidedText(rest, Qt.TextElideMode.ElideRight, width)]


class ModeCell(ui.Clickable):

    H = 98

    def __init__(self, key, title, desc, command, hint, big=False, show_desc=True):
        super().__init__(None)
        self.key, self.title, self.desc = key, title, desc
        self.command, self.hint = command, hint
        self.big, self.show_desc = big, show_desc
        self.selected = False
        self.tag = ""
        self.setMinimumWidth(130)
        self.setFixedHeight(self.H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ui.hover_help(self, lambda: self.title, lambda: self.hint(self))

    def set_state(self, selected, enabled, tag):
        if (selected, enabled, tag) != (self.selected, self.enabled, self.tag):
            self.selected, self.tag = selected, tag
            self.set_enabled(enabled)
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        if not self.enabled:
            fill = ui.DISABLED
        elif self.selected:
            fill = ui.MINT_HOVER if self.hovered else ui.MINT
        else:
            fill = ui.PLAIN_HOVER if self.hovered else ui.CARD
        r = ui.paint_box(p, self.width(), self.height(), fill, 2, 3)
        ink = ui.INK if self.enabled else ui.MUTED
        x, w = r.x() + 8, r.width() - 16
        f = ui.f_zh(14 if self.big else 10, True)
        p.setFont(f)
        p.setPen(ui.qc(ink))
        tl = two_lines(tr(self.title), f, w)
        th = QFontMetrics(f).lineSpacing() + 2
        for i, t in enumerate(tl):
            p.drawText(QRect(x, r.y() + 5 + i * th, w, th), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t)
        if self.show_desc:
            dy = 5 + len(tl) * th + 2
            f = ui.f_zh(8)
            p.setFont(f)
            p.setPen(ui.qc(ui.MUTED if not self.selected else ui.INK))
            lh = QFontMetrics(f).lineSpacing()
            for i, s in enumerate(two_lines(tr(self.desc), f, w)):
                p.drawText(QRect(x, r.y() + dy + i * lh, w, lh), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, s)
        if self.tag:
            p.setFont(ui.f_zh(8, True))
            p.setPen(ui.qc(ink))
            p.drawText(QRect(x, r.bottom() - 16, r.width() - 14, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, tr(self.tag))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.enabled and self.rect().contains(e.position().toPoint()):
            self.command(self.key)


def _card_sep(card):
    if card.n_rows:
        sep = QWidget()
        sep.setFixedHeight(1)
        ui.filled(sep, ui.DISABLED)
        card.blay.addWidget(sep)
    card.n_rows += 1


def grid(cells):
    w = QWidget()
    lay = QGridLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setHorizontalSpacing(10)
    lay.setVerticalSpacing(10)
    for i, c in enumerate(cells):
        lay.addWidget(c, i // COLS, i % COLS)
    for col in range(COLS):
        lay.setColumnStretch(col, 1)
    return w


class PlayPage(Page):
    key = "play"
    tab = "玩法"
    when = "游戏运行时可修改"

    def build(self):
        self.cfg = pm.load()
        self.status = {}
        self.finished = False

        top = ui.Card(self.view, "MODE", "模式", fill=ui.YELLOW)
        self.view_var = ui.Var("custom")
        self.seg_view = ui.Segmented(None, [("custom", "HellBox 版"), ("trial", "试炼场")],
                                     self.view_var, command=self._switch, font=ui.f_zh(10, True), padx=12, pady=4, shadow=3)
        self.custom_on = ui.Var(self.cfg["custom"] == "1")
        self.custom_toggle = ui.Toggle(None, self.custom_on, command=self._custom_toggled)
        ui.hover_help(self.custom_toggle, "HellBox 版", self._custom_help)
        self.custom_sub = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED, wrap=True)
        _card_sep(top)
        r1 = ui.HoverRow("", None)
        r1.lay.addWidget(self.seg_view, 0, Qt.AlignmentFlag.AlignVCenter)
        r1.lay.addStretch(1)
        r1.lay.addWidget(self.custom_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        top.blay.addWidget(r1)
        top.blay.addWidget(self.custom_sub)
        self.custom_sub.setContentsMargins(10, 0, 10, 6)
        self.follow_var = ui.Var("0" if self.cfg["follow"] == "0" else "1")
        self.seg_follow = ui.Segmented(None, [("1", "跟随房主"), ("0", "照原版")], self.follow_var, command=self._follow_picked,
                                       font=ui.f_zh(9, True), padx=9, pady=2, shadow=2)
        self.follow_row = top.row("进别人房间时", self.seg_follow,
                                  help="跟随房主 = 武装配置、换弹惊喜、修正参数、鬼城都照房主的（你这页的设置回自己房间才用）。"
                                       "照原版 = 这些都不开，不用退房。出怪、怪物属性、随机掉落、电磁干扰由房主那边做，开不开都有。")
        self.view_note = top.add(ui.text(top.body, "", muted=True, size=9), top=8)
        self.view.row(top)

        self._build_custom()
        self._build_trial()
        self._switch(self.view_var.get())
        room_desc.refresh()
        self.app.after(500, self._tick)

    def _custom_help(self):
        return ("开启后，每一关都会包含修正参数、换弹惊喜和环境，直到关掉。修正参数需要你当房主；换弹惊喜、鬼城只对安装并运行 HellBox 的玩家有效。")

    # ------------------------------------------------------------ HellBox 版
    def _build_custom(self):
        self._build_guest()
        self.c_rows = [self._build_myplays()]
        self.c_cond = [ModeCell("reload_surprise", "换弹惊喜", "每次换弹时枪随机换成另一把", self._pick_c_cond, self._hint_custom)]
        self.c_mod = [ModeCell(k, name, desc, self._pick_c_mod, self._hint_custom) for k, name, desc, _s in pm.CUSTOM_EVENTS]
        c2 = ui.Card(self.view, "EVENT", "修正参数", fill=ui.SKY)
        c2.add(grid(self.c_cond + self.c_mod))
        self._build_drop(c2)
        self.c_env = [ModeCell(k, name, desc, self._pick_env, self._hint_env, big=True, show_desc=True)
                      for k, name, desc, _s in pm.ENVS]
        c3 = ui.Card(self.view, "ENV", "环境", fill=ui.MINT)
        c3.add(grid(self.c_env))
        self.hop = HopRows(self)
        bee = self.hop.steps("drone_light_percent", numbers(10, 100, 10, "%"), needs="drone_light", width=150)
        self.drone_row = self.hop.toggle(c3, "drone_light", "无人机探照灯",
                                         "呼叫无人机时，玩家头顶增加探照灯，照亮周围一圈。",
                                         extras=(bee,))
        beacon = self.hop.steps("beacon_light_percent", numbers(10, 100, 10, "%"), needs="beacon_light", width=150)
        self.beacon_row = self.hop.toggle(c3, "beacon_light", "战备信标更亮",
                                         "战备信标发的光更亮、照得更远；信标用完后几秒内慢慢暗回原样。",
                                         extras=(beacon,))
        self._sync_env_rows()
        self.c_rows += [c3, c2, self._build_loadout()]
        self.c_rows = [self.view.row(c) for c in self.c_rows]
        self._mp_fill()

    # ------------------------------------------------------------ 在别人房间里
    def _build_guest(self):
        card = ui.Card(self.view, "GUEST", "你在别人房间里", fill=ui.YELLOW)
        self.guest_lab = card.add(ui.text(card.body, "", size=10, bold=True))
        self.guest_note = card.add(ui.text(card.body, "", muted=True, size=9), top=4)
        self.guest_row = self.view.row(card)
        self.guest_row.setVisible(False)

    def _is_guest(self):
        return bool(self.app.state.get("running")) and self.status.get("role") == "guest"

    def _follow(self):
        return self.cfg.get("follow") != "0"

    def _host_items(self):
        st = self.status
        state = st.get("host_state") or "err"
        items = []
        if state == "ok":
            h = pm.parse_host(st.get("host"))
            if h and h["custom"]:
                if h["cond"]:
                    items.append(tr(pm.NAMES[h["cond"]]))
                items += [tr(pm.NAMES[e]) for e in h["events"]]
                if h["env"]:
                    items.append(tr(next(n for k, n, _d, _s in pm.ENVS if k == h["env"])))
        rule = (hl.read_status().get("host_rule") or "").strip()
        if rule.startswith("1|"):
            fx, rd = hl.counts(rule.split("|")[1:])
            if fx or rd:
                items.append(T("武装配置（固定 {0} 格、随机 {1} 格）", fx, rd))
        return items, state

    def _guest_text(self):
        items, state = self._host_items()
        if state == "none":
            first = tr("房主没装 HellBox。")
        elif state == "err":
            first = tr("读不到房主的房间数据。")
        elif items:
            first = T("房主开了：{0}", tr("、").join(items))
            if state == "old":
                first += tr("（房主的 HellBox 是旧版，只有武装配置能跟）")
        else:
            first = tr("房主未开启 HellBox 版玩法。") if state == "ok" else tr("房主的 HellBox 是旧版，只有武装配置能跟，房主没定武装配置。")
        if self._follow():
            second = tr("你这页 HellBox 版的设置现在不生效。")
        else:
            second = tr("你选了「照原版」。")
        return first, second

    def _follow_picked(self, value):
        self.cfg["follow"] = "0" if value == "0" else "1"
        self._save(tr("进别人房间时：跟随房主。") if value != "0"
                   else tr("进别人房间时：照原版。"))

    # ------------------------------------------------------------ 我的玩法
    def _build_myplays(self):
        self.mp_list = mp.load()
        card = ui.Card(self.view, "MYPLAYS", "我的玩法", fill=ui.YELLOW)
        seg = dict(font=ui.f_zh(9, True), padx=9, pady=2, shadow=2)
        self.mp_var = ui.Var("")
        self.mp_drop = ui.Dropdown(None, [("", "— 选一个 —")], self.mp_var, command=self._mp_use,
                                   width=14, font=ui.f_zh(9, True), shadow=2)
        self.mp_del_btn = ui.Button(None, "删掉", self._mp_del, **seg)
        card.row("存好的玩法", self.mp_drop, 8, self.mp_del_btn)
        self.mp_name_var = ui.Var("")
        self.mp_name_entry = ui.Entry(None, self.mp_name_var, width=12, font=ui.f_zh(10), pad=(6, 3))
        self.mp_save_btn = ui.Button(None, "存下", self._mp_save, kind="accent", **seg)
        card.row("存成玩法", self.mp_name_entry, 8, self.mp_save_btn)
        return card

    def _mp_now(self):
        p = mp.empty()
        p["slots"] = {k: self.lo[k] for k in hl.SLOTS}
        p["names"] = {k: self.lo.get("name." + k, "") if hl.mode_of(self.lo[k]) == "fixed" else "" for k in hl.SLOTS}
        evs = self._events()
        p["events"] = [e for e in pm.CUSTOM_KEYS if e in evs]
        p["drop"] = list(dict.fromkeys(self._drop_keys()))
        p["env"] = self._env()
        p["surprise"] = self.cfg.get("cond") == "reload_surprise"
        return p

    def _mp_match(self):
        now = mp.key_of(self._mp_now())
        return next((str(i) for i, p in enumerate(self.mp_list) if mp.key_of(p) == now), "")

    def _mp_fill(self):
        self.mp_drop.set_options([("", "— 选一个 —")] + [(str(i), p["name"]) for i, p in enumerate(self.mp_list)])
        self._mp_sync()

    def _mp_sync(self):
        m = self._mp_match()
        if self.mp_var.get() != m:
            self.mp_var.set(m)
        self.mp_del_btn.set_enabled(m != "")

    def _mp_use(self, value):
        if not value:
            return
        p = self.mp_list[int(value)]
        c = self.cfg
        c["custom"] = "1"
        c["cond"] = "reload_surprise" if p["surprise"] else ""
        c["event"] = ",".join(p["events"])
        c["drop"] = ",".join(p["drop"])
        c["env"] = p["env"]
        for slot in hl.SLOTS:
            if hl.mode_of(self.lo[slot]) == "fixed":
                self.lo_last[slot] = self.lo[slot]
            self._lo_set(slot, p["slots"][slot])
            if not self.lo["name." + slot] and hl.mode_of(p["slots"][slot]) == "fixed":
                self.lo["name." + slot] = p["names"].get(slot, "")
        if hl.locked_count(self.lo):
            self.lo["on"] = "1"
        self.mp_name_var.set(p["name"])
        self._lo_fill()
        try:
            hl.save(self.lo)
            pm.save(c)
        except OSError as e:
            self.app.say(T("保存失败：{0}", e), "err")
            return
        self.app.say(T("已用上「{0}」。", p["name"]), "ok")
        self._lo_blocks_fill()
        self._badge()
        self.sync()

    def _mp_save(self):
        name = (self.mp_name_var.get() or "").strip()
        if not name:
            self.app.say(tr("给这个玩法起个名字。"), "err")
            return
        play = self._mp_now()
        play["name"] = name
        same = next((i for i, p in enumerate(self.mp_list) if p["name"] == name), None)
        if same is None and len(self.mp_list) >= mp.MAX:
            self.app.say(T("最多存 {0} 个玩法。", mp.MAX), "err")
            return
        plays = list(self.mp_list)
        if same is None:
            plays.append(play)
        else:
            plays[same] = play
        try:
            mp.save(plays)
        except OSError as e:
            self.app.say(T("保存失败：{0}", e), "err")
            return
        self.mp_list = plays
        self._mp_fill()
        self.app.say(T("已存成玩法「{0}」。", name) if same is None else T("已覆盖玩法「{0}」。", name), "ok")

    def _mp_del(self):
        m = self.mp_var.get()
        if not m:
            return
        name = self.mp_list[int(m)]["name"]
        if not self.app.ask(T("删掉玩法「{0}」？", name)):
            return
        plays = [p for i, p in enumerate(self.mp_list) if str(i) != m]
        try:
            mp.save(plays)
        except OSError as e:
            self.app.say(T("没删掉：{0}", e), "err")
            return
        self.mp_list = plays
        self._mp_fill()
        self.app.say(T("已删掉玩法「{0}」。", name), "ok")

    # ------------------------------------------------------------ 随机掉落
    DROP_ALL = {"red": "全部红色", "blue": "全部蓝色", "green": "全部绿色", "yellow": "全部黄色"}
    DROP_GROUP = {"red": "红色 · 进攻", "blue": "蓝色 · 补给（含载具）", "green": "绿色 · 防御", "yellow": "黄色 · 特殊"}

    def _build_drop(self, parent):
        self.drop_pool = pm.drop_pool()
        self.drop_open = "drop" in self._events()
        self.drop_sum = ui.Label("", font=ui.f_zh(9, True), fg=ui.MUTED, wrap=True)
        self.drop_btn = ui.Button(None, "展开", self._drop_fold, font=ui.f_zh(9, True), padx=9, pady=2, shadow=2)
        head, hl = ui.hbox(spacing=10)
        hl.addWidget(self.drop_sum, 1, Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(self.drop_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        parent.add(head, top=12)
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        self.drop_box = box
        seg = dict(font=ui.f_zh(9, True), padx=8, pady=2, shadow=2)
        btns = []
        for color, _n, _t in pm.DROP_COLORS:
            btns += [ui.Button(None, self.DROP_ALL[color], lambda c=color: self._drop_all(c), **seg), 6]
        btns.append(ui.Button(None, "全不选", self._drop_none, **seg))
        self.drop_count = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        row = ui.HoverRow("一键全选")
        lab = ui.Label("一键全选", font=ui.f_zh(11, True))
        row.lay.addWidget(lab, 0, Qt.AlignmentFlag.AlignVCenter)
        row.lay.addStretch(1)
        for c in btns:
            if isinstance(c, int):
                row.lay.addSpacing(c)
            else:
                row.lay.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
        bl.addWidget(row)
        try:
            from i18n import is_en
            en = is_en()
        except ImportError:
            en = False
        self.drop_vars = {}
        self.drop_cbs = {}
        self.drop_unlocked = pm.read_unlocks()
        chosen = set(pm.split_list(self.cfg.get("drop")))
        for color, rows in self.drop_pool:
            lb = ui.Label(self.DROP_GROUP[color], font=ui.f_zh(9, True), fg=ui.MUTED)
            bl.addSpacing(10)
            bl.addWidget(lb)
            w = QWidget()
            lay = QGridLayout(w)
            lay.setContentsMargins(0, 4, 0, 0)
            lay.setHorizontalSpacing(14)
            lay.setVerticalSpacing(6)
            for i, (key, zh, en_name, _veh) in enumerate(rows):
                name = en_name if en else zh
                v = ui.Var(key in chosen and key not in pm.DROP_BAN)
                cb = ui.CheckBox(None, name, v, command=lambda k=key: self._drop_toggle(k), font=ui.f_zh(9, True))
                if key in pm.DROP_BAN:
                    cb.set_enabled(False)
                else:
                    cb.set_enabled(not self._drop_locked(key))
                self.drop_vars[key] = v
                self.drop_cbs[key] = cb
                lay.addWidget(cb, i // 3, i % 3, alignment=ui.Qt.AlignmentFlag.AlignLeft)
            for col in range(3):
                lay.setColumnStretch(col, 1)
            bl.addWidget(w)
        parent.add(box, top=8)
        self._drop_show()

    def _drop_fold(self):
        self.drop_open = not self.drop_open
        self._drop_show()

    def _drop_show(self):
        self.drop_box.setVisible(self.drop_open)
        self.drop_btn.set_text("收起" if self.drop_open else "展开")

    def _drop_locked(self, key):
        return self.drop_unlocked is not None and key not in self.drop_unlocked

    def _drop_refresh_unlocks(self):
        now = pm.read_unlocks()
        if now == self.drop_unlocked:
            return
        self.drop_unlocked = now
        for key, cb in self.drop_cbs.items():
            if key not in pm.DROP_BAN:
                cb.set_enabled(not self._drop_locked(key))
        if getattr(self, "lo_drops", None):
            self._lo_fill()

    def _drop_summary(self):
        picked = set(self._drop_keys())
        keys = {k for k in picked if not self._drop_locked(k)}
        dead = len(picked) - len(keys)
        tail = T("；{0} 个没解锁，不生效", dead) if dead else ""
        if not keys:
            return T("已选{0}个战备", 0) + tail
        parts = []
        for color, rows in self.drop_pool:
            ok = [r[0] for r in rows if r[0] not in pm.DROP_BAN and not self._drop_locked(r[0])]
            n = sum(1 for k in ok if k in keys)
            if n:
                parts.append(T("{0}{1}个", tr(dict((c, nm) for c, nm, _t in pm.DROP_COLORS)[color]), n))
        return T("已选{0}个战备（{1}）", len(keys), tr("、").join(parts)) + tail

    def _drop_keys(self):
        return [k for k in pm.split_list(self.cfg.get("drop")) if k not in pm.DROP_BAN]

    def _drop_set(self, keys, msg=None):
        self.cfg["drop"] = ",".join(dict.fromkeys(keys))
        self._save(msg)

    def _drop_toggle(self, key):
        keys = self._drop_keys()
        if self.drop_vars[key].get():
            keys.append(key)
        else:
            keys = [k for k in keys if k != key]
        self._drop_set(keys)

    def _drop_all(self, color):
        add = [r[0] for c, rows in self.drop_pool if c == color for r in rows
               if r[0] not in pm.DROP_BAN and not self._drop_locked(r[0])]
        self._drop_set(self._drop_keys() + add, T("{0}的战略配备都勾上了。", tr(dict((c, n) for c, n, _t in pm.DROP_COLORS)[color])))

    def _drop_none(self):
        self._drop_set([], tr("随机掉落的战略配备都取消了。"))

    def _pick_c_cond(self, _key):
        on = self.cfg.get("cond") != "reload_surprise"
        self.cfg["cond"] = "reload_surprise" if on else ""
        self._save("换弹惊喜已" + ("打开" if on else "关闭") + "。")

    # ------------------------------------------------------------ 配装块
    LO_NAMES = (("perk", "天赋"), ("primary", "主武器"), ("s5", "战略配备 1"), ("s6", "战略配备 2"), ("s7", "战略配备 3"), ("s8", "战略配备 4"))
    LO_MODES = [("fixed", "固定"), ("free", "自由"), ("random", "随机")]

    def _build_loadout(self):
        self.lo = hl.load()
        self.lo_items = hl.load_items()
        self.lo_blocks = hl.load_blocks()
        self.lo_last = {}
        self.lo_feed_n = 0
        self.lo_reading = False
        card = ui.Card(self.view, "LOADOUT", "武装配置", fill=ui.TAN)
        self.lo_on = ui.Var(self.lo["on"] == "1")
        self.lo_toggle = ui.Toggle(None, self.lo_on, command=self._lo_toggled)
        self.lo_sub = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        card.row("开启", self.lo_toggle, sub=self.lo_sub)
        seg = dict(font=ui.f_zh(9, True), padx=9, pady=2, shadow=2)
        self.lo_block_var = ui.Var("")
        self.lo_block_drop = ui.Dropdown(None, [("", "— 选一块 —")], self.lo_block_var, command=self._lo_use_block,
                                         width=14, font=ui.f_zh(9, True), shadow=2)
        self.lo_del_btn = ui.Button(None, "删掉", self._lo_del_block, **seg)
        card.row("存好的块", self.lo_block_drop, 8, self.lo_del_btn)
        self.lo_name_var = ui.Var("")
        self.lo_name_entry = ui.Entry(None, self.lo_name_var, width=12, font=ui.f_zh(10), pad=(6, 3))
        self.lo_save_btn = ui.Button(None, "存下", self._lo_save_block, kind="accent", **seg)
        card.row("存成块", self.lo_name_entry, 8, self.lo_save_btn)
        self.lo_mode_vars, self.lo_segs, self.lo_vars, self.lo_drops = {}, {}, {}, {}
        tip = ("固定 = 队友这一格只能用你定的，下拉框里只显示你已解锁的；自由 = 队友照自己的选；"
               "随机 = 游戏自己的随机武装配置办法，选装备界面显示 ???。")
        extra = {"primary": "副武器游戏里不能选。",
                 "s5": "前四个（增援、补给…）游戏固定带，这里是后面四格。战略配备可以重复。"}
        for slot, name in self.LO_NAMES:
            mv = ui.Var(hl.mode_of(self.lo[slot]))
            sg = ui.Segmented(None, self.LO_MODES, mv, command=lambda val, s=slot: self._lo_mode(s, val),
                              font=ui.f_zh(9, True), padx=7, pady=2, shadow=2)
            v = ui.Var("")
            d = ui.Dropdown(None, [("", "—")], v, command=lambda val, s=slot: self._lo_pick(s, val), width=11,
                            font=ui.f_zh(9, True), shadow=2)
            self.lo_mode_vars[slot], self.lo_segs[slot], self.lo_vars[slot], self.lo_drops[slot] = mv, sg, v, d
            card.row(name, sg, 8, d)
        self.lo_copy = ui.Button(None, "抄我现在这套", self._lo_copy, kind="accent", **seg)
        self.lo_clear = ui.Button(None, "全部自由", self._lo_clear, **seg)
        self.lo_rand = ui.Button(None, "全部随机", self._lo_all_random, **seg)
        card.row("快速设置", self.lo_copy, 8, self.lo_clear, 8, self.lo_rand)
        self._lo_fill()
        self._lo_blocks_fill()
        return card

    def _lo_options(self, slot):
        opts = list(self.lo_items.get(hl.kind_of(slot)) or [])
        un = pm.read_unlocks()
        if un is not None:
            opts = [(k, n) for k, n in opts if k in un]
        cur = self.lo[slot] if hl.mode_of(self.lo[slot]) == "fixed" else self.lo_last.get(slot, "")
        if cur and all(k != cur for k, _ in opts):
            opts.append((cur, self.lo.get("name." + slot) or cur))
        if hl.mode_of(self.lo[slot]) != "fixed" and not cur:
            opts = [("", "—")] + opts
        return opts

    def _lo_shown(self, slot):
        v = self.lo[slot]
        return v if hl.mode_of(v) == "fixed" else self.lo_last.get(slot, "")

    def _lo_allowed(self, slot):
        un = pm.read_unlocks()
        if un is None:
            return None
        return {k for k, _n in self._lo_options(slot) if not k or k in un}

    def _lo_locked(self):
        un = pm.read_unlocks()
        if un is None:
            return []
        return [tr(name) for slot, name in self.LO_NAMES
                if hl.mode_of(self.lo[slot]) == "fixed" and self.lo[slot] not in un]

    def _lo_fill(self):
        for slot, _ in self.LO_NAMES:
            self.lo_drops[slot].set_options(self._lo_options(slot), self._lo_allowed(slot))
        self._lo_sync_vars()

    def _lo_sync_vars(self):
        for slot, _ in self.LO_NAMES:
            mode = hl.mode_of(self.lo[slot])
            if self.lo_mode_vars[slot].get() != mode:
                self.lo_mode_vars[slot].set(mode)
            if self.lo_vars[slot].get() != self._lo_shown(slot):
                self.lo_vars[slot].set(self._lo_shown(slot))
            self.lo_drops[slot].set_enabled(mode == "fixed")

    def _lo_name(self, slot, key):
        return next((n for k, n in self.lo_items.get(hl.kind_of(slot)) or [] if k == key), "")

    def _lo_set(self, slot, value):
        self.lo[slot] = value
        self.lo["name." + slot] = self._lo_name(slot, value) if hl.mode_of(value) == "fixed" else ""

    def _lo_save(self, msg=None):
        try:
            hl.save(self.lo)
        except OSError as e:
            self.app.say(T("保存失败：{0}", e), "err")
            return
        if msg:
            self.app.say(msg, "ok")
        self._lo_blocks_fill()
        self._badge()
        self.sync()

    def _lo_toggled(self):
        self.lo["on"] = "1" if self.lo_on.get() else "0"
        if self.lo_on.get() and not hl.locked_count(self.lo):
            self._lo_save(tr("武装配置已打开，但六格都是「自由」。"))
        else:
            self._lo_save(tr("武装配置已打开。") if self.lo_on.get() else tr("武装配置已关闭。"))

    def _lo_current(self, slot):
        cur = self.lo_items.get("loadout")
        i = hl.SLOTS.index(slot)
        return cur[i] if cur and len(cur) > i else ""

    def _lo_mode(self, slot, mode):
        cur = self.lo[slot]
        if mode == hl.mode_of(cur):
            return
        if hl.mode_of(cur) == "fixed":
            self.lo_last[slot] = cur
        if mode == "free":
            value = ""
        elif mode == "random":
            value = hl.RANDOM
        else:
            items = self.lo_items.get(hl.kind_of(slot)) or []
            un = pm.read_unlocks()
            ok = (lambda k: bool(k)) if un is None else (lambda k: bool(k) and k in un)
            value = next((k for k in (self.lo_last.get(slot), self._lo_current(slot)) if ok(k)), "") \
                or next((k for k, _n in items if ok(k)), "")
            if not value:
                self.app.say(tr("还没有物品名单，没法固定。"), "err")
                self._lo_sync_vars()
                return
        self._lo_set(slot, value)
        self._lo_fill()
        self._lo_save()

    def _lo_pick(self, slot, value):
        if not value or hl.mode_of(self.lo[slot]) != "fixed":
            self._lo_sync_vars()
            return
        self._lo_set(slot, value)
        self._lo_save()

    def _lo_copy(self):
        cur = self.lo_items.get("loadout")
        if not (self.app.state.get("running") and cur and len(cur) >= 6):
            self.app.say(tr("读不到你现在的武装配置：需要游戏正在运行，位于主菜单或飞船。"), "err")
            return
        for slot, key in zip(hl.SLOTS, cur):
            self._lo_set(slot, key)
        self._lo_fill()
        self._lo_save(tr("已抄下你现在这套武装配置。"))

    def _lo_clear(self):
        self._lo_all("", tr("六格都改成「自由」了。"))

    def _lo_all_random(self):
        self._lo_all(hl.RANDOM, tr("六格都改成「随机」了。"))

    def _lo_all(self, value, msg):
        for slot in hl.SLOTS:
            if hl.mode_of(self.lo[slot]) == "fixed":
                self.lo_last[slot] = self.lo[slot]
            self._lo_set(slot, value)
        self._lo_fill()
        self._lo_save(msg)

    def _lo_match(self):
        now = {k: self.lo[k] for k in hl.SLOTS}
        return next((str(i) for i, b in enumerate(self.lo_blocks) if b["slots"] == now), "")

    def _lo_blocks_fill(self):
        opts = [("", "— 选一块 —")] + [(str(i), b["name"]) for i, b in enumerate(self.lo_blocks)]
        self.lo_block_drop.set_options(opts)
        m = self._lo_match()
        if self.lo_block_var.get() != m:
            self.lo_block_var.set(m)
        self.lo_del_btn.set_enabled(m != "")

    def _lo_use_block(self, value):
        if not value:
            return
        b = self.lo_blocks[int(value)]
        for slot in hl.SLOTS:
            if hl.mode_of(self.lo[slot]) == "fixed":
                self.lo_last[slot] = self.lo[slot]
            self._lo_set(slot, b["slots"][slot])
            if not self.lo["name." + slot] and hl.mode_of(b["slots"][slot]) == "fixed":
                self.lo["name." + slot] = b["names"].get(slot, "")
        self.lo_name_var.set(b["name"])
        self._lo_fill()
        self._lo_save(T("已用上「{0}」。", b["name"]))

    def _lo_save_block(self):
        name = (self.lo_name_var.get() or "").strip()
        if not name:
            self.app.say(tr("先在左边给这一块起个名字。"), "err")
            return
        block = {"name": name, "slots": {k: self.lo[k] for k in hl.SLOTS},
                 "names": {k: self.lo.get("name." + k, "") for k in hl.SLOTS}}
        same = next((i for i, b in enumerate(self.lo_blocks) if b["name"] == name), None)
        if same is None and len(self.lo_blocks) >= hl.BLOCK_MAX:
            self.app.say(T("最多存 {0} 块，先删掉一块。", hl.BLOCK_MAX), "err")
            return
        blocks = list(self.lo_blocks)
        if same is None:
            blocks.append(block)
        else:
            blocks[same] = block
        try:
            hl.save_blocks(blocks)
        except OSError as e:
            self.app.say(T("保存失败：{0}", e), "err")
            return
        self.lo_blocks = blocks
        self._lo_blocks_fill()
        self.app.say(T("已存成块「{0}」。", name) if same is None else T("已覆盖块「{0}」。", name), "ok")

    def _lo_del_block(self):
        m = self.lo_block_var.get()
        if not m:
            return
        name = self.lo_blocks[int(m)]["name"]
        if not self.app.ask(T("删掉块「{0}」？", name)):
            return
        blocks = [b for i, b in enumerate(self.lo_blocks) if str(i) != m]
        try:
            hl.save_blocks(blocks)
        except OSError as e:
            self.app.say(T("没删掉：{0}", e), "err")
            return
        self.lo_blocks = blocks
        self._lo_blocks_fill()
        self.app.say(T("已删掉块「{0}」。", name), "ok")

    def _lo_feed(self):
        if self.lo_reading or not self.app.state.get("running") or self.app.current is not self:
            return
        self.lo_feed_n -= 1
        if self.lo_feed_n > 0:
            return
        self.lo_feed_n = 5
        self.lo_reading = True
        self.app.bg(profile_feed.read, self._lo_got)

    def _lo_got(self, ok, st):
        self.lo_reading = False
        if not ok or not isinstance(st, dict) or not st.get("ok"):
            return
        items = hl.items_from_feed(st)
        if hl.builtin_items():
            self.lo_items["loadout"] = items["loadout"]
        elif items["perk"] and items["primary"] and items["strat"]:
            changed = any(items[k] != self.lo_items.get(k) for k in ("perk", "primary", "strat"))
            self.lo_items = items
            if changed:
                try:
                    hl.save_items(items)
                except OSError:
                    pass
                self._lo_fill()
        else:
            self.lo_items["loadout"] = items["loadout"]

    def _lo_text(self):
        n = hl.locked_count(self.lo)
        st = hl.read_status() if self.app.state.get("running") else {}
        role, rule = st.get("role"), (st.get("rule") or "").strip()
        if role == "guest" and not self._follow():
            if (st.get("host_rule") or "").strip().startswith("1|"):
                return tr("你在别人的房间：房主已确定武装配置，但你关闭了「跟随房主的玩法」，将使用你自己的武装配置。"), ui.WARN
            return tr("你在别人的房间里：照你自己的武装配置。"), ui.MUTED
        if role == "guest":
            if st.get("api") not in (None, "", "ok"):
                return T("你在别人的房间里，读不到房主的武装配置规则（{0}），照你自己的武装配置。", st.get("api")), ui.WARN
            if rule.startswith("1|"):
                fx, rd = hl.counts(rule.split("|")[1:])
                return T("你在别人的房间里：房主定了固定 {0} 格、随机 {1} 格，按房主的来（你这里的设置这时不管用）。", fx, rd), ui.WARN
            return tr("你在别人的房间里：房主没定武装配置。"), ui.MUTED
        if self.lo["on"] != "1":
            return tr("关着：照自己的武装配置。"), ui.MUTED
        if not n:
            return tr("已开启，但六格都是「自由」。"), ui.MUTED
        locked = self._lo_locked()
        if locked:
            return T("已开启，但这几格固定的是你尚未解锁的，游戏里当「自由」：{0}。换一个已解锁的即可。",
                     tr("、").join(locked)), ui.WARN
        fx, rd = hl.counts(self.lo[k] for k in hl.SLOTS)
        what = T("固定 {0} 格、随机 {1} 格", fx, rd)
        if not self.app.state.get("running"):
            return T("已开启：{0}。启动游戏并当房主后生效。", what), ui.GOOD
        if not st:
            return T("已开启：{0}。正在等待游戏回应。", what), ui.WARN
        return T("已开启：{0}。你当房主时，运行 HellBox 的队友按这套配置。", what), ui.GOOD

    def _custom_support(self, key):
        if key == "reload_surprise":
            return "self"
        for k, _n, _d, s in pm.CUSTOM_EVENTS:
            if k == key:
                return s
        return None

    def _events(self):
        return [e for e in pm.split_list(self.cfg.get("event")) if e in pm.CUSTOM_KEYS]

    def _conflict(self, key):
        other = pm.CONFLICTS.get(key)
        return other if other and other in self._events() and key not in self._events() else None

    FULL = {
        "drop": "以房主时间为准，隔一阵（打击类 15 秒、别的 20 秒）在某个活着的队友身边 4～10 米落一个战略配备，掉哪些在下面的名单里挑。",
        "emp": "电磁脉冲轮着来：开 15 秒，关 40 秒。",
        "get_ammo_from_hits_double_reload_time": "弹匣容量减半（向上取整），每打中敌人一发，弹匣里补回一发子弹。",
        "marksman": "只有打中弱点才有伤害，打中弱点时伤害翻倍。",
        "super_boots": "自带心肺加速器（体力不消耗），但怪物打你的伤害 +50%。",
        "what_goes_around": "你打到队友：队友照样受伤，同样大小的伤害也会打回你自己身上。",
        "reload_surprise": "每次换弹，手里的枪随机换成另一把。",
        "sidearm_saber": "每次出生把手枪换成试炼场「只有近战」里的那把军刀。",
    }

    def _hint_custom(self, cell):
        full = tr(self.FULL.get(cell.key) or cell.desc)
        other = self._conflict(cell.key)
        if other:
            return full + "\n" + T("不能和「{0}」一起开，请先取消「{0}」。", tr(pm.NAMES.get(other, other)))
        if self._custom_support(cell.key) == "team":
            extra = tr("只在虫族、生化人关卡有。") if cell.key == "emp" else ""
            return full + "\n" + tr("你当房主时全队都有；队友无需安装 HellBox。") + extra
        return full + "\n" + tr("只对安装了 HellBox 的玩家有效：你当房主，队友照你的；你在别人房间，照房主的。")

    def _env(self):
        e = self.cfg.get("env") or ""
        return e if e in pm.ENV_KEYS else ""

    def _hint_env(self, cell):
        if cell.key == "ghost_town":
            return tr("只对安装了 HellBox 的玩家有效，房主说了算；没装的人看到正常光照，也能一起玩。")
        return ""

    def _pick_env(self, key):
        self.cfg["env"] = key
        self._sync_env_rows()
        self._save(T("环境：{0}。下一关生效。", tr("鬼城" if key == "ghost_town" else "原版")))

    def _sync_env_rows(self):
        ghost = self._env() == "ghost_town"
        for row in (self.drone_row, self.beacon_row):
            row.setVisible(ghost)
            if row.sep is not None:
                row.sep.setVisible(ghost)

    def _custom_toggled(self):
        self.cfg["custom"] = "1" if self.custom_on.get() else "0"
        self._save("HellBox 版玩法已" + ("打开" if self.custom_on.get() else "关闭") + "。")

    def _pick_c_mod(self, key):
        evs = self._events()
        if key in evs:
            evs.remove(key)
        elif not self._conflict(key):
            evs.append(key)
        self.cfg["event"] = ",".join(e for e in pm.CUSTOM_KEYS if e in evs)
        if key == "drop":
            self.drop_open = "drop" in evs
            self._drop_show()
        self._save()

    # ------------------------------------------------------------ 真训练场
    def _build_trial(self):
        m = ui.Card(self.view, "MAP", "地图", fill=ui.YELLOW)
        self.v_race = ui.Var(self.cfg["race"])
        self.v_tod = ui.Var(self.cfg["tod"])
        self.v_diff = ui.Var(self.cfg["diff"])
        seg = dict(font=ui.f_zh(9, True), padx=9, pady=2, shadow=2)
        self.seg_race = ui.Segmented(None, pm.RACES, self.v_race, command=lambda v: self._set("race", v), **seg)
        self.seg_tod = ui.Segmented(None, pm.TIMES, self.v_tod, command=lambda v: self._set("tod", v), **seg)
        self.seg_diff = ui.Segmented(None, pm.DIFFS, self.v_diff, command=lambda v: self._set("diff", v), **seg)
        m.row("种族", self.seg_race, help="打哪个种族。")
        m.row("时间", self.seg_tod, help="黎明 / 白天 / 黄昏 / 夜晚。")
        m.row("难度", self.seg_diff, help="试炼场只有三档：简单（难度 5）、中等（难度 9）、困难（难度 15）。有的规则在某些难度不能选。")
        self.t_thumb = map_picker.ClickMap(120, self._pick_terrain)
        m.row("地形", self.t_thumb, help="点击地图挑选地形（需游戏正在运行）。")
        self._t_requested = None
        self.t_chal = [ModeCell(k, name, desc, self._pick_t_chal, self._hint_trial)
                       for k, name, desc in pm.CHALLENGES]
        self.t_cond = [ModeCell(k, name, desc, self._pick_t_cond, self._hint_trial) for k, _g, name, desc, _s in pm.CONDITIONS]
        self.t_mod = [ModeCell(k, name, desc, self._pick_t_mod, self._hint_trial) for k, name, desc, _s in pm.MODIFIERS]
        c0 = ui.Card(self.view, "GOAL", "目标", fill=ui.TAN)
        c0.add(grid(self.t_chal))
        c1 = ui.Card(self.view, "RULE", "条件", fill=ui.SALMON)
        c1.add(grid(self.t_cond))
        c2 = ui.Card(self.view, "EVENT", "修正参数", fill=ui.SKY)
        c2.add(grid(self.t_mod))

        go = ui.Card(self.view, "GO", "出发", fill=ui.MINT)
        self.btn_arm = ui.Button(None, "设为下一局", self._arm, kind="primary", font=ui.f_zh(11, True), padx=20, pady=5)
        self.btn_cancel = ui.Button(None, "取消", self._cancel, font=ui.f_zh(10, True), padx=12, pady=4)
        go.add(ui.line(self.btn_arm, 10, self.btn_cancel), align=ui.Qt.AlignmentFlag.AlignLeft)
        self.trial_status = go.add(ui.text(go.body, "", size=10, bold=True), top=10)
        self.t_rows = [self.view.row(c) for c in (m, c0, c1, c2, go)]

    def _hint_trial(self, cell):
        why = self._why_blocked(cell)
        if not why:
            return ""
        item, who = why
        return T("不能开：游戏规定「{0}」不能和「{1}」一起开。", tr(pm.NAMES.get(item, item)), tr(who))

    def _why_blocked(self, cell):
        c = self.cfg
        diff, chal, cond, mod = c["diff"], c["chal"], c["pcond"], c["pmod"]
        if cell in self.t_chal:
            chal = cell.key
        elif cell in self.t_cond:
            cond = cell.key
        else:
            mod = cell.key
        return pm.blocked(diff, chal, cond, mod)

    def _set(self, key, value):
        self.cfg[key] = value
        self._save()

    def _pick_t_chal(self, key):
        self._set("chal", key)

    def _pick_t_cond(self, key):
        self._set("pcond", key)

    def _pick_t_mod(self, key):
        self._set("pmod", key)

    def _trial_key(self, terrain=None):
        c = self.cfg
        t = int(c["terrain"]) // 10000000 if terrain is None else terrain
        return mt.trial_key(c["race"], c["tod"], c["diff"], c["chal"], t)

    def _trial_thumb(self):
        key = self._trial_key()
        if key != self._t_requested:
            self._t_requested = key
            mt.request([key], owner="play")
        self.t_thumb.set_cells(mt.load(key))

    def _pick_terrain(self):
        c = self.cfg
        cands = [self._trial_key(t) for t in range(pm.TERRAINS)]
        names = dict(pm.RACES), dict(pm.TIMES), dict(pm.DIFFS), {k: n for k, n, _d in pm.CHALLENGES}
        title = " · ".join(tr(x) for x in (T("试炼场"), names[0].get(c["race"], ""), names[1].get(c["tod"], ""),
                                           names[2].get(c["diff"], ""), names[3].get(c["chal"], "")) if x)

        def picked(key):
            self._set("terrain", str(cands.index(key) * 10000000))
            self._trial_thumb()

        map_picker.MapPicker(self.view, self._trial_key(), cands, picked,
                             lambda: bool(self.app.state.get("running")), title=title).exec()

    def _arm(self):
        c = self.cfg
        bad = pm.blocked(c["diff"], c["chal"], c["pcond"], c["pmod"])
        if bad:
            item, who = bad
            self.app.warn(T("这个组合游戏不让开：「{0}」不能和「{1}」一起。换一张再设。", tr(pm.NAMES.get(item, item)), tr(who)))
            return
        c["trial"] = pm.new_trial_id()
        self.finished = False
        self._save("已设为下一局：在飞船上当房主照常进出发舱就是这一关。" if self.app.state["running"]
                   else "已设为下一局：开游戏进飞船后自动设好，照常进出发舱就是这一关。")

    def _cancel(self):
        self.cfg["trial"] = ""
        self._save("已取消，下一局照常。")

    # ------------------------------------------------------------ 公共
    def _switch(self, value):
        for r in self.c_rows:
            r.setVisible(value == "custom")
        for r in self.t_rows:
            r.setVisible(value == "trial")
        for w in (self.custom_toggle, self.custom_sub, self.follow_row):
            w.setVisible(value == "custom")
        self.guest_row.setVisible(value == "custom" and self._is_guest())
        self.view_note.config(text=tr(
            "任何关卡都能用；修正参数你当房主全队都有，其余只对安装了 HellBox 的玩家有效，房主说了算。"
            if value == "custom" else
            "开一局真正的试炼场：全队完整生效，队友无需安装 HellBox，外观固定是试炼场。"))
        self.sync()

    def _save(self, msg=None):
        try:
            pm.save(self.cfg)
        except OSError as e:
            self.app.say(T("保存失败：{0}", e), "err")
            return
        if msg:
            self.app.say(msg, "ok")
        self._badge()
        self.sync()

    def _tick(self):
        if self.app.state.get("running"):
            self.status = pm.read_status()
        else:
            self.status = {}
        st = self.status
        if self.cfg["trial"] and st.get("state") == "done" and st.get("trial") == self.cfg["trial"]:
            self.cfg["trial"] = ""
            self.finished = True
            self._save("试炼场这一局打完了，飞船已恢复正常。想再来就再点击「设为下一局」。")
        self._badge()
        room_desc.refresh()
        if self.app.current is self:
            self._lo_feed()
            self.sync()
        self.app.after(POLL_MS, self._tick)

    def _badge(self):
        c, parts = self.cfg, []
        if self._is_guest():
            parts.append(tr("别人房间：玩法照房主") if self._follow() else tr("别人房间：玩法不跟房主"))
        else:
            if c["custom"] == "1" and (c["cond"] or self._events() or self._env()):
                parts.append(tr("HellBox 玩法已开启"))
            if self.lo["on"] == "1" and hl.locked_count(self.lo):
                parts.append(tr("武装配置已开启"))
        if c["trial"] and self.status.get("state") != "done":
            parts.append(tr("下一局：试炼场"))
        footer = getattr(self.app, "footer", None)
        if footer is not None and hasattr(footer, "set_badge"):
            footer.set_badge(" · ".join(parts))

    def on_show(self):
        self.sync()

    def sync(self):
        if hasattr(self, "hop"):
            self.hop.sync(self.app.mod_on() and not self.app.busy)
        c = self.cfg
        on = c["custom"] == "1"
        if self.custom_on.get() != on:
            self.custom_on.set(on)
        if self.follow_var.get() != ("1" if self._follow() else "0"):
            self.follow_var.set("1" if self._follow() else "0")
        guest = self._is_guest()
        self.guest_row.setVisible(guest and self.view_var.get() == "custom")
        if guest:
            first, second = self._guest_text()
            self.guest_lab.config(text=first)
            self.guest_note.config(text=second)
        sub = ""
        evs = self._events()
        if guest:
            sub = tr("在别人房间里，暂时不生效")
        elif on:
            names = [pm.NAMES[k] for k in [c["cond"], *evs, self._env()] if k in pm.NAMES]
            sub = T("已开启：{0}", tr("、").join(tr(n) for n in names)) if names else tr("已开启，但尚未选择玩法")
            if "emp" in evs:
                sub += tr("（电磁干扰只在虫族、生化人关卡有）")
            if "drop" in evs and not [k for k in self._drop_keys() if not self._drop_locked(k)]:
                sub += tr("（随机掉落还没勾战略配备）")
            running = [e for e in pm.split_list(self.status.get("events")) if e in pm.NAMES]
            if running:
                sub += "  " + T("这一关正在跑：{0}", tr("、").join(tr(pm.NAMES[e]) for e in running))
        self.custom_sub.config(text=sub)
        if self.lo_on.get() != (self.lo["on"] == "1"):
            self.lo_on.set(self.lo["on"] == "1")
        self._lo_sync_vars()
        lo_text, lo_color = self._lo_text()
        self.lo_sub.config(text=lo_text, fg=lo_color)
        for cell in self.c_cond + self.c_mod:
            s = self._custom_support(cell.key)
            sel = c["cond"] == "reload_surprise" if cell.key == "reload_surprise" else cell.key in evs
            cell.set_state(sel and s is not None, s is not None and not self._conflict(cell.key), TAG_TEXT[s])
        for cell in self.c_env:
            cell.set_state(cell.key == self._env(), True, TAG_TEXT["self"] if cell.key else "")
        self._sync_env_rows()
        self._drop_refresh_unlocks()
        chosen = set(self._drop_keys())
        for key, v in self.drop_vars.items():
            if v.get() != (key in chosen):
                v.set(key in chosen)
        self.drop_count.config(text=T("勾了 {0} 个", sum(1 for k in chosen if not self._drop_locked(k))))
        self.drop_sum.config(text=self._drop_summary())
        self._mp_sync()
        for var, key in ((self.v_race, "race"), (self.v_tod, "tod"), (self.v_diff, "diff")):
            if var.get() != c[key]:
                var.set(c[key])
        self._trial_thumb()
        for cells, key in ((self.t_chal, "chal"), (self.t_cond, "pcond"), (self.t_mod, "pmod")):
            for cell in cells:
                cell.set_state(cell.key == c[key], self._why_blocked(cell) is None or cell.key == c[key], "")
        bad = pm.blocked(c["diff"], c["chal"], c["pcond"], c["pmod"])
        text, color = self._trial_text(bad)
        self.trial_status.config(text=text, fg=color)
        self.btn_cancel.set_enabled(bool(c["trial"]))

    def _trial_text(self, bad):
        c, st = self.cfg, self.status
        if bad:
            item, who = bad
            return T("这个组合游戏不让开：「{0}」不能和「{1}」一起。", tr(pm.NAMES.get(item, item)), tr(who)), ui.BAD
        if not c["trial"]:
            if self.finished:
                return tr("上一局试炼场打完了，已恢复正常。想再来就再点击「设为下一局」。"), ui.MUTED
            return "", ui.MUTED
        if not self.app.state.get("running"):
            return tr("已设好，等待游戏启动。"), ui.WARN
        if st.get("trial") != c["trial"]:
            return tr("已设好，等游戏回应。"), ui.WARN
        state = st.get("state")
        if state == "armed":
            return tr("游戏里已设好：在飞船上进出发舱就是这一关。"), ui.GOOD
        if state == "used":
            return tr("正在打这一关。打完回飞船自动恢复。"), ui.GOOD
        if state == "done":
            return tr("这一关打完了，已恢复正常。想再来一次就再点击「设为下一局」。"), ui.MUTED
        if state == "not_host":
            return tr("你在别人的房间里，只有房主能设。"), ui.BAD
        if state == "bad":
            return tr("游戏没认这个组合，换一张再设。"), ui.BAD
        if st.get("why") == "busy":
            return tr("飞船正在出发，等这一步结束后自动设上。"), ui.WARN
        return tr("已设好，回到飞船后自动设上。"), ui.WARN
