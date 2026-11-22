"""我的名字、房间名、2P / 3P / 4P 名字。游戏开着也能改，几秒内生效。
我的名字和 2P~4P：游戏只存 51 字节（汉字 3、英文数字 1），框里打满就打不进去，别人看到的也是这么长。
房间名：Steam 房间数据最多 8192 字节。"""
import build
import hellbox_options as options
import ui
from pages import room_desc
from pages.base import Page
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)


def _fit(s, limit):
    """按整字切到 limit 字节以内。"""
    while len(s.encode("utf-8")) > limit:
        s = s[:-1]
    return s


class NamesPage(Page):
    key = "names"
    tab = "昵称"
    when = "游戏开着：几秒内生效　没开：下次开游戏生效"

    def build(self):
        lim = build.PLAYER_NAME_BYTES
        self.vars = {}
        self.buttons = []
        # 2026-11-15 新界面：两张卡一行一个名字；原来的「怎么生效」卡拆进顶上那行和每行的说明（鼠标停上去看）
        me = ui.Card(self.view, "ME", "我", fill=ui.MINT)
        self._name_row(me, "我的名字", "me", build.get_self_name(), lim,
                       T("留空 = Steam 昵称。头顶、结算、联机的人看到的都是它；房间名留空时也用它。"
                         "游戏只存 {0} 字节：汉字算 3，最多 17 个汉字或 {0} 个字母。", lim),
                       lambda: self.apply_player(0))
        self._name_row(me, "房间名", "room", build.get_room_name(), None,
                       "留空 = 用你的名字（没设就是 Steam 昵称）。只有你当房主时生效。"
                       "真房间名会自动变成「[HellBox · 玩法] 名字」，所有人都看得到：影响平衡的玩法和数据修改写在方括号里，"
                       "太长时先换简写再截短你的名字（整个房间名最多 200 字节，约 60 个汉字）。", self.apply_room)
        # 2026-11-21 HD1-038 用户要求：[HellBox] 放前面还是名字放前面（写进 room-desc.txt，游戏几秒内跟着改）
        self.room_order = ui.Var(self._order())
        self.seg_order = ui.Segmented(None, list(options.ROOM_ORDERS.items()), self.room_order, command=self.set_order,
                                      font=ui.f_zh(9, True), padx=7, pady=2, shadow=2)
        me.row("房间名顺序", self.seg_order, help="房间名里 [HellBox …] 放前面还是你的名字放前面。只是换个顺序，"
               "方括号里写什么、太长时怎么截都一样。只有你当房主时生效，游戏开着几秒内就换。", name_w=90)
        # 现在的房间名：游戏开着且你是房主 = 游戏里实际的；别的时候 = 预览。方括号里跟「玩法」「数据修改」页的设置走
        self.room_prev = me.add(ui.text(me.body, "", size=10, bold=True), top=8)
        self.room_note = me.add(ui.text(me.body, "", muted=True, size=9), top=2)
        me.add(ui.text(me.body, tr("方括号里的内容跟「玩法」「数据修改」页的设置走，改了几秒内跟着变；太长会自动简写、截短名字。"),
                       muted=True, size=9), top=2)
        self.vars["room"].trace(self._room_preview)
        self._room_preview()
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
        card.row(title, box, 8, btn, help=help_text, sub=count, name_w=90)
        if limit:
            def show():
                used = len((var.get() or "").encode("utf-8"))
                count.config(text=T('{0} / {1} 字节', used, limit), fg=ui.BAD if used >= limit else ui.MUTED)

            def typed(s):
                if len(s.encode("utf-8")) > limit:  # 打满了：多出来的不要，光标留在原处
                    pos = box.edit.cursorPosition()
                    cut = _fit(s, limit)
                    var.set(cut)
                    box.edit.setCursorPosition(min(pos, len(cut)))
                show()

            box.edit.textEdited.connect(typed)
            show()

    def _run(self, save, live_text, magic, live_hint):
        def action():
            save()
            if build.game_running():
                import room_name_live
                room_name_live.live_set(live_text(), magic=getattr(room_name_live, magic))
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
        self.room_note.config(text=tr(room_desc.NOTES[kind]))

    def _tick(self):
        """游戏开着时「现在的房间名」跟着游戏回报走（看着这一页时每秒读一次）。"""
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
