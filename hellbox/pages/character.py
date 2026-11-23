"""
潜兵页：修改等级、研究点、武器、战略配备和披风，只改自己（主手柄）的存档；游戏运行时热改，游戏里由 mod/src/profile_tool.lua 生效。
"""
from PySide6.QtCore import Qt

import ui
from pages import profile_feed
from pages.base import Page
from pages.edit_util import ParamList, small_button
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

POLL_MS = 1500
MAX_LV = 50
VC = Qt.AlignmentFlag.AlignVCenter
UNLOCKABLE = ("lv", "rw", "free")
EMPTY = {"ok": False, "why": "", "capes": [], "weapons": [], "strats": [], "mates": []}
STRAT_KIND = {"supply": "补给", "defensive": "防御", "offensive": "进攻", "special": "特殊"}

FREE_WHY = {
    "ENT015": "社区披风：官方发给社区贡献者的，从来没卖过，不是付费 DLC，所以可以直接解锁。",
    "ENT016": "开发者披风：发给开发组成员的，从来没卖过，不是付费 DLC，所以可以直接解锁。",
}
PG_WHY = ("试炼场披风：官方在「试炼场」(Proving Grounds) 活动里发给排行榜第一名的奖励，游戏按 DLC 的方式发放，"
          "但不是付费 DLC。排行榜第一名常年被作弊占着，正常玩家几乎拿不到，所以可以直接解锁。")


def why(item):
    s, need = item["status"], item["need"]
    if s == "on":
        return tr({"default": "默认就有。", "lv": "升级解锁的。", "dlc": "DLC，已拥有。",
                   "free": "社区 / 开发者 / 试炼场的，已解锁。"}.get(need, "已解锁（奖励拿到的，或在这里解锁的）。"))
    if s == "lv":
        return T("要 {0} 级。可以直接解锁，只是提前拿到，不影响别的。", need)
    if s == "rw":
        return tr("奖励（打下星球、赛季结算这类给的），还没拿到。可以直接解锁。")
    if s == "free":
        return tr(FREE_WHY.get(need, PG_WHY))
    if s == "tut":
        return tr("新兵训练里穿的披风，游戏军械库里永远选不了；这里可以直接穿上。")
    if s == "dlc":
        return T("付费 DLC（Steam 上的扩展包，{0}），你还没买，不能解锁。", need)
    return ""


def short(item):
    s, need = item["status"], item["need"]
    if s == "on":
        return tr({"default": "默认", "lv": "升级解锁", "dlc": "DLC 已拥有", "free": "已解锁"}.get(need, "已解锁"))
    return {"lv": T("要 {0} 级", need), "rw": tr("奖励，没拿到"), "free": tr("免费，可解锁"),
            "tut": tr("新兵训练"), "dlc": tr("付费 DLC，没买")}.get(s, "")


class CharacterPage(Page):
    key = "character"
    tab = "潜兵"
    when = "需要游戏正在运行才能修改，改完立即保存"
    when_color = ui.YELLOW

    def build(self):
        self.st = None
        self.reading = False
        self.sig = None
        self.buttons = []
        self.empty_shown = False

        # ---------------- 潜兵：现在、等级、研究点
        me = ui.Card(self.view, "ME", "绝地潜兵", fill=ui.MINT)
        self.now = ui.Label("…", font=ui.f_zh(10), fg=ui.MUTED)
        me.row("现在", self.now)
        self.v_lv = ui.Var("1")
        self.lv_step = ui.Stepper(None, self.v_lv, 1, MAX_LV, width=3)
        self.btn_lv = small_button("应用", self.apply_level, kind="accent")
        me.row("等级", self.lv_step, 10, self.btn_lv)
        self.rp_var = ui.Var("")
        box = ui.Entry(None, self.rp_var, width=6, pad=(6, 3))
        box.edit.returnPressed.connect(self.apply_rp)
        self.btn_rp = small_button("应用", self.apply_rp, kind="accent")
        self.btn_max = small_button("加满", self.apply_max)
        self.rp_sub = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        me.row("研究点", box, 10, self.btn_rp, 8, self.btn_max, sub=self.rp_sub)

        # ---------------- 武器
        self.w_card = ui.Card(self.view, "GUN", "武器", fill=ui.YELLOW)
        self.btn_all_w = small_button("解锁", lambda: self._send("unlockweapons=all"))
        self.btn_all_w.can = False
        self.w_card.head_lay.addSpacing(10)
        self.w_card.head_lay.addWidget(self.btn_all_w, 0, VC)
        self.w_body, self.w_lay = ui.vbox(spacing=0)
        self.w_card.add(self.w_body, top=4)

        # ---------------- 战略配备
        self.s_card = ui.Card(self.view, "STRAT", "战略配备", fill=ui.SKY)
        self.btn_all_s = small_button("解锁", lambda: self._send("unlockstrats=all"))
        self.btn_all_s.can = False
        self.s_card.head_lay.addSpacing(10)
        self.s_card.head_lay.addWidget(self.btn_all_s, 0, VC)
        self.s_body, self.s_lay = ui.vbox(spacing=0)
        self.s_card.add(self.s_body, top=4)

        # ---------------- 披风
        self.c_card = ui.Card(self.view, "CAPE", "披风", fill=ui.SALMON)
        self.btn_all_c = small_button("解锁", lambda: self._send("unlockcapes=all"))
        self.btn_all_c.can = False
        self.c_card.head_lay.addSpacing(10)
        self.c_card.head_lay.addWidget(self.btn_all_c, 0, VC)
        self.c_body, self.c_lay = ui.vbox(spacing=0)
        self.c_card.add(self.c_body, top=4)

        self.view.row(me)
        self.view.row(self.w_card)
        self.view.row(self.s_card)
        self.view.row(self.c_card)
        self._show_empty()
        self.app.after(300, self._tick)

    # ------------------------------------------------------------ 定时读状态
    def _tick(self):
        if self.app.current is self and self.app.state["running"] and not self.reading:
            self.reading = True
            self.app.bg(profile_feed.read, self._got)
        elif not self.app.state["running"]:
            self._show(dict(EMPTY, why="游戏未运行。"))
        self.app.after(POLL_MS, self._tick)

    def on_show(self):
        if self.app.state["running"] and not self.reading:
            self.reading = True
            self.app.bg(profile_feed.read, self._got)

    def _got(self, ok, st):
        self.reading = False
        self._show(st if ok else dict(EMPTY, why=str(st)))

    def _show(self, st):
        first = not (self.st and self.st.get("ok"))
        self.st = st
        if not st["ok"]:
            self.now.config(text=st.get("why") or "拿不到游戏状态。", fg=ui.MUTED)
            self.rp_sub.config(text="")
            if self.sig is not None or not self.empty_shown:
                self._show_empty()
                self.buttons = []
                self.sig = None
            self.sync()
            return
        per = st["per"] or 10
        cur = next((c for c in st["capes"] if c["index"] == st["cape"]), None)
        if self.app.state.get("script") == "old" or "maxlv" not in st.get("raw_keys", ("maxlv",)):
            self.now.config(text=tr("游戏里还是旧版 MOD，武器、战略配备和部分披风显示不全。关掉游戏后 HellBox 会自动更新。"), fg=ui.WARN)
        else:
            self.now.config(text=T("{0} 级；经验 {1}；穿着「{2}」", st["lv"], st["xp"], cur["name"] if cur else "?"), fg=ui.INK)
        self.rp_sub.config(text=T("现在 {0}（零 {1} 个样本），最多 {2}", st["rp"] // per, st["rp"] % per, st["max"] // per))
        if first or not self.rp_var.get():
            self.rp_var.set(str(st["rp"] // per))
        if first:
            self.v_lv.set(str(max(1, st["lv"])))
        sig = (st["cape"], tuple((c["index"], c["name"], c["status"], c["need"]) for c in st["capes"]),
               tuple((w["index"], w["name"], w["status"], w["need"]) for w in st["weapons"]),
               tuple((w["index"], w["name"], w["status"], w["need"]) for w in st.get("strats", [])))
        if sig != self.sig:
            self.sig = sig
            self._build_lists(st)
        self.sync()

    # ------------------------------------------------------------ 清单
    def _show_empty(self):
        for lay in (self.w_lay, self.s_lay, self.c_lay):
            ui.clear_layout(lay)
        self.empty_shown = True

    def _build_lists(self, st):
        self.empty_shown = False
        self.buttons = []
        for lay in (self.w_lay, self.s_lay, self.c_lay):
            ui.clear_layout(lay)

        self._unlock_list(self.w_lay, ui.YELLOW, st["weapons"], "unlockweapon")
        self.btn_all_w.can = any(w["status"] in UNLOCKABLE for w in st["weapons"])
        strats = st.get("strats", [])
        self._unlock_list(self.s_lay, ui.SKY, strats, "unlockstrat")
        self.btn_all_s.can = any(w["status"] in UNLOCKABLE for w in strats)

        cl = ParamList(self.c_lay, ui.SALMON)
        for title, keep in (("能直接解锁", UNLOCKABLE), ("已解锁", ("on", "tut")), ("付费 DLC，没买", ("dlc",))):
            items = [c for c in st["capes"] if c["status"] in keep]
            if not items:
                continue
            cl.section(T("{0}（{1}）", tr(title), len(items)))
            for c in items:
                if c["status"] in ("on", "tut"):
                    worn = c["index"] == st["cape"]
                    ctl = self._button("穿着" if worn else "穿上", lambda i=c["index"]: self._send(f"wearcape={i}"),
                                       not worn, kind="plain" if worn else "accent")
                elif c["status"] == "dlc":
                    ctl = self._button("要购买", None, False)
                else:
                    ctl = self._button("解锁", lambda i=c["index"]: self._send(f"unlockcape={i}"), True)
                cl.row(c["name"], ctl, short(c))
        self.btn_all_c.can = any(c["status"] in UNLOCKABLE for c in st["capes"])

    def _unlock_list(self, lay, color, items_all, cmd):
        pl = ParamList(lay, color)
        for title, keep in (("能解锁", UNLOCKABLE), ("已解锁", ("on",)), ("付费 DLC，没买", ("dlc",))):
            items = [w for w in items_all if w["status"] in keep]
            if not items:
                continue
            pl.section(T("{0}（{1}）", tr(title), len(items)))
            for w in items:
                ctl = None
                if w["status"] == "dlc":
                    ctl = self._button("要购买", None, False)
                elif w["status"] != "on":
                    ctl = self._button("解锁", lambda i=w["index"]: self._send(f"{cmd}={i}"), True)
                note = short(w)
                if w.get("kind") in STRAT_KIND:
                    note = tr(STRAT_KIND[w["kind"]]) + " · " + note
                pl.row(w["name"], ctl, note)

    def _button(self, text, command, can, kind="plain"):
        b = small_button(text, command, kind=kind)
        b.can = can
        self.buttons.append(b)
        return b

    # ------------------------------------------------------------ 操作
    def _send(self, cmd):
        self.app.run(lambda: profile_feed.send(cmd), working="正在改…")
        self.app.after(400, self.on_show)

    def apply_level(self):
        n = int(self.lv_step.value())
        top = (self.st or {}).get("maxlv") or MAX_LV
        if not 1 <= n <= top:
            self.app.warn(T("等级要在 1 到 {0} 之间。", top))
            return
        self._send(f"level={n}")

    def apply_rp(self):
        try:
            n = int(self.rp_var.get().strip())
        except ValueError:
            self.app.warn("研究点要填一个整数。")
            return
        top = (self.st["max"] // (self.st["per"] or 10)) if self.st and self.st["ok"] else 316
        if not 0 <= n <= top:
            self.app.warn(T('研究点要在 0 到 {0} 之间。', top))
            return
        self._send(f"rp={n}")

    def apply_max(self):
        top = (self.st["max"] // (self.st["per"] or 10)) if self.st and self.st["ok"] else 316
        self.rp_var.set(str(top))
        self._send(f"rp={top}")

    def sync(self):
        live = bool(self.st and self.st["ok"]) and not self.app.busy
        for b in (self.btn_rp, self.btn_max, self.btn_lv):
            b.set_enabled(live)
        self.lv_step.set_enabled(live)
        for b in (self.btn_all_w, self.btn_all_s, self.btn_all_c):
            b.set_enabled(live and b.can)
        for b in self.buttons:
            b.set_enabled(live and b.can)
