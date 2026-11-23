"""
昵称页：修改自己的名字、房间名和本地多人 2P–4P 的名字；游戏运行时也能修改，几秒内生效。
"""
import build
import hellbox_options as options
import ui
from pages import room_desc
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)


def _fit(s, limit):
    while len(s.encode("utf-8")) > limit:
        s = s[:-1]
    return s


class NamesPage(Page):
    key = "names"
    tab = "昵称"
    when = "游戏运行时可修改"

    def build(self):
        lim = build.PLAYER_NAME_BYTES
        self.vars = {}
        self.buttons = []
        me = ui.Card(self.view, "ME", "我", fill=ui.MINT)
        self._name_row(me, "我的名字", "me", build.get_self_name(), lim,
                       T("留空 = Steam 昵称。头顶、结算、联机的人看到的都是它；房间名留空时也用它。"
                         "联机时每个人改自己的：客机也要装 HellBox 才改得了，改完全队看到的是新名字。"
                         "游戏只存 {0} 字节：汉字算 3，最多 17 个汉字或 {0} 个字母。", lim),
                       lambda: self.apply_player(0))
        self._name_row(me, "房间名", "room", build.get_room_name(), None,
                       "留空 = 用你的名字（没设就是 Steam 昵称）。只有你当房主时生效。"
                       "真房间名会自动带上标记，所有人都看得到：只开了自己用的功能是「[HellBox] 名字」；"
                       "开了玩法、改了数据、带箱子上车或丢支援装备是「[Hex] 名字」，方括号里写鬼城、其他玩法几个（+3），"
                       "敌人改得比原版难再写「炼狱」，比如「[Hex · 鬼城 +3 · 炼狱] 名字」。", self.apply_room)
        self.room_order = ui.Var(self._order())
        orders = [(k, "HellBox 在前" if k == "tag" else "HellBox 在后") for k in options.ROOM_ORDERS]
        self.seg_order = ui.Segmented(None, orders, self.room_order, command=self.set_order,
                                      font=ui.f_zh(9, True), padx=7, pady=2, shadow=2)
        me.row("房间名顺序", self.seg_order, name_w=90)
        self.room_prev = me.add(ui.text(me.body, "", size=10, bold=True), top=8)
        self.vars["room"].trace(self._room_preview)
        self._room_preview()
        room_desc.refresh()
        self.view.row(me)
        local = ui.Card(self.view, "LOCAL", "本地多人（同一台电脑的手柄）", fill=ui.SKY)
        for n in (2, 3, 4):
            self._name_row(local, T('{0}P 名字', n), f"p{n}", build.get_pn_name(n), lim,
                           "留空 = “你的名字 #手柄号”。按副手柄加入的先后排：第一个加入的是 2P。名字不能重复（游戏靠名字认人）。",
                           lambda n=n: self.apply_player(n))
        self.view.row(local)
        self.app.after(1000, self._tick)

    def _name_row(self, card, title, key, value, limit, help_text, command):
        var = ui.Var(_fit(value, limit) if limit else value)
        self.vars[key] = var
        box = ui.Entry(None, var, width=18)
        box.edit.returnPressed.connect(command)
        btn = ui.Button(None, "应用", command, kind="accent", font=ui.f_zh(9, True), padx=10, pady=2, shadow=2)
        self.buttons.append(btn)
        count = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED) if limit else None
        card.row(title, box, 8, btn, sub=count, name_w=90)
        if limit:
            def show():
                used = len((var.get() or "").encode("utf-8"))
                count.config(text=T('{0} / {1} 字节', used, limit), fg=ui.BAD if used >= limit else ui.MUTED)

            def typed(s):
                if len(s.encode("utf-8")) > limit:
                    pos = box.edit.cursorPosition()
                    cut = _fit(s, limit)
                    var.set(cut)
                    box.edit.setCursorPosition(min(pos, len(cut)))
                show()

            box.edit.textEdited.connect(typed)
            show()

    @staticmethod
    def _live_set(value, table):
        """写进游戏内存；HellBox 默认以管理员身份运行（见 hellbox/elevate.py），权限不够时给明确的提示。"""
        import room_name_live
        try:
            room_name_live.live_set(value, magic=table)
        except room_name_live._Helper:
            raise RuntimeError("HellBox 的权限比游戏低（游戏是管理员启动的）。"
                               "关掉 HellBox 用管理员身份重新打开，或者关掉游戏再改，下次开游戏生效。")

    def _run(self, save, live_text, magic, live_hint):
        def action():
            save()
            if build.game_running():
                import room_name_live
                self._live_set(live_text(), getattr(room_name_live, magic))
                self.app.pending_install = True
                return live_hint + "关游戏时 HellBox 别关，会自动记住。"
            build.install()
            return "已保存，下次开游戏生效。"

        self.app.run(action)

    def apply_room(self):
        name = self.vars["room"].get()
        self._run(lambda: build.set_room_name(name), lambda: name.strip(), "MAGIC", "房间名已改好（当房主时生效）。")

    def apply_player(self, n):
        if n == 0:
            name = self.vars["me"].get()
            self._run(lambda: build.set_self_name(name), lambda: name.strip(), "MAGIC_SELF",
                      "名字已改好，头顶马上换。")
        else:
            name = self.vars[f"p{n}"].get()
            self._run(lambda: build.set_pn_name(n, name), build.pn_mail, "MAGIC_P2",
                      T('{0}P 名字已改好，头顶马上换。', n))

    @staticmethod
    def _order():
        v = options.load().get("room_order")
        return v if v in options.ROOM_ORDERS else "tag"

    def set_order(self, value):
        def action():
            options.save({"room_order": value})
            room_desc.refresh()
            return "房间名顺序已改，当房主时几秒内生效。" if build.game_running() else "房间名顺序已改，下次当房主时生效。"

        self.app.run(action)
        self._room_preview()

    def _room_preview(self):
        from pages import play_modes as pm
        trial = pm.read_status().get("state") in ("armed", "used") if self.app.state.get("running") else False
        name, kind = room_desc.current(self.vars["room"].get(), bool(self.app.state.get("running")), trial=trial)
        self.room_prev.config(text=T("现在的房间名：{0}", name))

    def _tick(self):
        if self.app.current is self:
            self._room_preview()
        self.app.after(1000, self._tick)

    def sync(self):
        self._room_preview()
        if not self.app.busy and self.room_order.get() != self._order():
            self.room_order.set(self._order())
        self.seg_order.set_enabled(not self.app.busy)
        for btn in self.buttons:
            btn.set_enabled(not self.app.busy)
