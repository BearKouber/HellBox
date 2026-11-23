"""
数据页：普通模式改敌人 / 武器 / 战备的全局倍数；开发者模式按块编辑。设置写入 data-live.txt，游戏每秒读取；存档和命令拼法见 pages/data_blocks.py。
"""
import copy

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

import ui
from pages import data_blocks as db
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

POLL_MS = 1500
VC = Qt.AlignmentFlag.AlignVCenter
WHERE_ZH = {"game": "对局中", "menu": "在飞船 / 菜单", "boot": "游戏刚开", "loading": "加载中"}
RACE_ZH = {"bugs": "虫族", "cyborgs": "生化人", "illuminates": "光能者"}
VEH_ORIG_UNIT, VEH_ORIG_COUNT = "characters/cyborg_initiate/cyborg_initiate_elite", 3


def _small(text, command, kind="plain"):
    return ui.Button(None, text, command, kind=kind, font=ui.f_zh(9, True), padx=9, pady=2, shadow=2)


class KindList(ui.Clickable):

    H = 46

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.hover_i = None
        self.setMouseTracking(True)
        self.setFixedHeight(self.H * len(db.SHOWN) + 4)
        self.setMinimumWidth(150)

    def paintEvent(self, _e):
        p = QPainter(self)
        w = self.width()
        for i, (k, name, col, _r) in enumerate(db.SHOWN):
            r = QRect(0, 2 + i * self.H, w, self.H - 4)
            if k == self.page.kind:
                p.fillRect(r, ui.qc(ui.INK))
                p.fillRect(r.adjusted(2, 2, -2, -2), ui.qc(ui.WHITE))
            elif i == self.hover_i:
                p.fillRect(r, ui.qc(ui.PLAIN_HOVER))
            p.fillRect(r.left() + 10, r.top() + 10, 12, 12, ui.qc(ui.INK))
            p.fillRect(r.left() + 12, r.top() + 12, 8, 8, ui.qc(col))
            p.setPen(ui.qc(ui.INK))
            p.setFont(ui.f_zh(10, True))
            p.drawText(QRect(r.left() + 30, r.top() + 3, w - 34, 20), Qt.AlignmentFlag.AlignLeft | VC, tr(name))
            use = self.page.data["live"].get(k)
            cell = self.page.data["blocks"][k][use] if use is not None else None
            p.setFont(ui.f_zh(8))
            p.setPen(ui.qc(ui.GOOD if cell else ui.MUTED))
            label = tr("在用：") + cell["name"] if cell else tr("原版")
            label = p.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, w - 36)
            p.drawText(QRect(r.left() + 30, r.top() + 21, w - 34, 16), Qt.AlignmentFlag.AlignLeft | VC, label)

    def _at(self, e):
        i = int((e.position().y() - 2) // self.H)
        return i if 0 <= i < len(db.SHOWN) else None

    def mouseMoveEvent(self, e):
        i = self._at(e)
        if i != self.hover_i:
            self.hover_i = i
            self.update()

    def leaveEvent(self, e):
        self.hover_i = None
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        i = self._at(e)
        if e.button() == Qt.MouseButton.LeftButton and i is not None:
            self.page.pick(db.SHOWN[i][0])


class DataPage(Page):
    key = "data"
    tab = "数据"

    def build(self):
        self.data = db.load()
        self.editors = {}
        self.editing = None
        self.waiting_since = None
        self.kind = "enemy"
        self.dev = None

        self.btn_reset_all = _small("全部恢复原版", self.reset_simple)
        self.head_lay.addWidget(self.btn_reset_all, 0, VC)

        # ---------------- 编辑时顶上固定的一条：名字 确定 返回 …… 删除
        edit = QWidget()
        el = QVBoxLayout(edit)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(4)
        self.ed_title = ui.Label("", font=ui.f_zh(11, True))
        self.v_name = ui.Var("")
        self.name_entry = ui.Entry(None, self.v_name, width=18, font=ui.f_zh(10), pad=(6, 3))
        self.btn_ok = ui.Button(None, "确定", self.commit, kind="accent", padx=12, pady=2)
        self.btn_cancel = ui.Button(None, "返回", self.close_editor, padx=10, pady=2)
        self.btn_del = ui.Button(None, "删掉这块", self.delete_block, kind="danger", padx=8, pady=2)
        el.addWidget(ui.line(self.ed_title, 14, ui.Label("名字", font=ui.f_zh(10, True), fg=ui.MUTED), 6,
                             self.name_entry, 14, self.btn_ok, 8, self.btn_cancel, "<>", self.btn_del))
        self.edit_bar = edit
        edit.hide()
        self.view.pin_lay.addWidget(edit)

        # ---------------- 普通模式：一页滑条
        self.sliders = {}
        self.simple_rows = []
        veh_after = "spawn" if any(g[0] == "spawn" for g in db.SIMPLE_SHOWN) else "enemy"
        for group, title, color, note, rows in db.SIMPLE_SHOWN:
            card = ui.Card(self.view, "", title, fill=color)
            for row in rows:
                self._slider_row(title, card, row)
            self.simple_rows.append(self.view.row(card))
            if group == veh_after:
                self.simple_rows.append(self.view.row(self._veh_card()))

        # ---------------- 开发者模式：左边分类，右边这一类的块
        left = ui.Card(self.view, "", "分类", fill=ui.INK)
        self.kinds = KindList(self)
        left.add(self.kinds, top=4)
        self.list_card = ui.Card(self.view, "", "", fill=ui.CARD)
        self.list_body, self.list_lay = ui.vbox()
        self.list_card.add(self.list_body)
        self.dev_row = self.view.row(left, self.list_card, weights=(2, 5))

        self.set_dev(self.app.dev)
        self.app.after(500, self._tick)

    def _slider_row(self, card_title, card, row):
        key, name, values, default, _what, help_text = row
        var = ui.Var(self.data["simple"].get(key, default))
        options = [(v, db.simple_label(row, v, " 原版")) for v in values]
        s = ui.StepSlider(None, options, var, width=270, text_width=92, tail=key == "spawn.limit")
        s.changed = var.get() != default
        rs = _small("原版", None)
        sp = rs.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        rs.setSizePolicy(sp)
        rs.setVisible(s.changed)

        def done(val):
            if val == default:
                self.data["simple"].pop(key, None)
            else:
                self.data["simple"][key] = val
            s.changed = val != default
            s.update()
            rs.setVisible(s.changed)
            what = tr(name) if card_title in name or name.startswith("报复关") else T("{0}：{1}", tr(card_title), tr(name))
            self._write(T("{0} {1}", what, dict(options)[val]))

        def reset():
            var.set(default)
            done(default)

        s.command = done
        rs.command = reset
        card.row(name, s, 6, rs, name_w=120)
        self.sliders[key] = (var, default, s, rs)

    # ---------------- 坦克屁股出兵
    def _veh_card(self):
        import drill_spec as ds
        self.veh = db.clean_veh(self.data.get("veh"))
        try:
            ok, _removed = ds.pickable(db.VEH_RACE)
        except Exception:  # noqa: BLE001
            ok = []
        self.veh_units = [("characters/" + m["path"], ds.label(m), m) for m in ok]
        self.veh_orig_unit = VEH_ORIG_UNIT
        orig_name = next((lab for path, lab, _m in self.veh_units if path == VEH_ORIG_UNIT), tr("精英新兵"))
        card = ui.Card(self.view, "", "坦克屁股出兵", fill=db.TYPE_COLOR["spawn"])
        self.v_veh_mode = ui.Var(self.veh["mode"])
        seg = ui.Segmented(None, [("vanilla", "原版"), ("only", "只出选中"), ("none", "不出")], self.v_veh_mode,
                           command=self._veh_mode, font=ui.f_zh(9, True), padx=12, pady=4, shadow=3)
        card.row("方式", seg, name_w=120)
        self.v_veh_count = ui.Var(str(self.veh["count"] or VEH_ORIG_COUNT))
        self.veh_step = ui.Stepper(None, self.v_veh_count, 1, 50, width=3, command=self._veh_count)
        self.veh_count_note = ui.Label("", font=ui.f_zh(9), fg=ui.MUTED)
        self.btn_veh_count = _small("原版", self._veh_count_reset)
        self.row_veh_count = card.row("每次放几只", self.veh_count_note, 10, self.btn_veh_count, 8, self.veh_step, name_w=120)
        self.veh_box, self.veh_lay = ui.vbox(spacing=4)
        card.add(self.veh_box, top=4)
        self._veh_refresh()
        return card

    def _veh_refresh(self):
        v = self.veh
        self.row_veh_count.setVisible(v["mode"] != "none")
        self.v_veh_count.set(str(v["count"] or VEH_ORIG_COUNT))
        self.veh_count_note.config(text=T("原版 {0} 只", VEH_ORIG_COUNT) if not v["count"]
                                   else T("改过（原版 {0}）", VEH_ORIG_COUNT))
        self.btn_veh_count.set_enabled(bool(v["count"]))
        ui.clear_layout(self.veh_lay)
        if v["mode"] != "only":
            return
        if not self.veh_units:
            self.veh_lay.addWidget(ui.text(None, "没读到怪物清单（ai\\drill_monsters.json）。", muted=True, size=9))
            return
        grid_w = QWidget(None)
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(8, 2, 8, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        grid.setColumnMinimumWidth(1, 24)
        grid.setColumnMinimumWidth(3, 24)
        grid.setColumnStretch(6, 1)
        for i, (path, label, m) in enumerate(self.veh_units):
            var = ui.Var(path in v["sel"])
            cb = ui.CheckBox(None, label, var, command=lambda var=var, path=path: self._veh_unit(path, var),
                             note="未实测" if m.get("test") == "untested" else None)
            grid.addWidget(cb, i // 3, (i % 3) * 2, Qt.AlignmentFlag.AlignLeft | VC)
        self.veh_lay.addWidget(grid_w)
        self.veh_lay.addWidget(ui.text(None, "勾了谁，坦克放出来的兵就换成谁（勾多个就轮着放）。一只都没勾 = 原版。",
                                       muted=True, size=9))

    def _veh_save(self, what):
        self.data["veh"] = db.clean_veh(self.veh)
        self._write(T("{0}：{1}", tr("坦克屁股出兵"), what))

    def _veh_mode(self, mode):
        self.veh["mode"] = mode
        if mode == "only" and not self.veh["sel"]:
            self.veh["sel"] = {VEH_ORIG_UNIT: 1}
        self._veh_refresh()
        self._veh_save({"vanilla": tr("原版"), "only": tr("只出选中"), "none": tr("不出")}[mode])

    def _veh_unit(self, path, var):
        if var.get():
            self.veh["sel"][path] = 1
        else:
            self.veh["sel"].pop(path, None)
        self._veh_save(T("勾了 {0} 种", len(self.veh["sel"])))

    def _veh_count(self, *_a):
        n = int(self.veh_step.value())
        self.veh["count"] = 0 if n == VEH_ORIG_COUNT else n
        self._veh_refresh()
        self._veh_save(T("每次放 {0} 只", n))

    def _veh_count_reset(self):
        self.v_veh_count.set(str(VEH_ORIG_COUNT))
        self._veh_count()

    def reset_simple(self):
        if not db.shown_simple(self.data) and not db.simple_veh(self.data):
            self.app.say("已经全是原版了。", "info")
            return
        self.data["simple"] = {k: v for k, v in self.data["simple"].items() if k not in db.SHOWN_ROWS}
        self.veh = db.clean_veh(None)
        self.data["veh"] = dict(self.veh)
        self.v_veh_mode.set("vanilla")
        self._veh_refresh()
        for var, default, s, rs in self.sliders.values():
            var.set(default)
            s.changed = False
            s.update()
            rs.setVisible(False)
        self._write(tr("滑条全部恢复原版"))

    def pick(self, kind):
        self.kind = kind
        self.kinds.update()
        self.refill()

    def refill(self):
        ui.clear_layout(self.list_lay)
        k = self.kind
        self.list_card.title_lab.config(text=tr(db.TYPE_NAME[k]))
        live = self.data["live"].get(k)
        cells = self.data["blocks"][k]
        top, tl = ui.hbox()
        tl.setContentsMargins(8, 2, 8, 8)
        tl.addWidget(ui.Label("现在用的：", font=ui.f_zh(10)), 0, VC)
        tl.addWidget(ui.Label(cells[live]["name"] if live is not None else tr("原版"), font=ui.f_zh(10, True),
                              fg=ui.GOOD if live is not None else ui.MUTED), 0, VC)
        tl.addStretch(1)
        if live is not None:
            tl.addWidget(_small("恢复原版", lambda: self.put(k, None)), 0, VC)
        self.list_lay.addWidget(top)
        filled = [(i, c) for i, c in enumerate(cells) if c]
        if not filled:
            e = ui.text(None, "这一类还没有存好的块。点击下面「＋ 新建一块」创建一个块，完成后点击「使用」。", muted=True, size=9)
            e.setContentsMargins(8, 4, 8, 4)
            self.list_lay.addWidget(e)
        for i, cell in filled:
            sep = QWidget()
            sep.setFixedHeight(1)
            ui.filled(sep, ui.DISABLED)
            self.list_lay.addWidget(sep)
            summ = tr(db.summary(k, cell))
            r = ui.HoverRow(cell["name"])
            on = live == i
            r.lay.addWidget(ui.Square(None, ui.MINT if on else ui.CARD, 10), 0, VC)
            col, cl = ui.vbox()
            cl.addWidget(ui.Label(cell["name"], font=ui.f_zh(11, True)))
            cl.addWidget(ui.ElideLabel(summ, font=ui.f_zh(9), fg=ui.MUTED))
            r.lay.addWidget(col, 1, VC)
            if on:
                r.lay.addWidget(ui.Label("正在用", font=ui.f_zh(9, True), fg=ui.GOOD), 0, VC)
            else:
                r.lay.addWidget(_small("使用", lambda i=i: self.put(k, i), kind="primary"), 0, VC)
            r.lay.addWidget(_small("编辑", lambda i=i: self.open_editor(k, i)), 0, VC)
            self.list_lay.addWidget(r)
        bw, bl = ui.hbox()
        bl.setContentsMargins(8, 12, 8, 2)
        nb = _small("＋ 新建一块", lambda: self.open_editor(k, None))
        nb.set_enabled(len(filled) < db.COUNT)
        bl.addWidget(nb, 0, VC)
        bl.addSpacing(10)
        bl.addWidget(ui.Label(T("{0} / {1} 块", len(filled), db.COUNT), font=ui.f_zh(9), fg=ui.MUTED), 0, VC)
        bl.addStretch(1)
        self.list_lay.addWidget(bw)
        simple = db.simple_summary(self.data)
        if simple:
            note = ui.text(None, T("普通模式的滑条也在生效（乘在块上面）：{0}", simple), muted=True, size=9)
            note.setContentsMargins(8, 10, 8, 0)
            self.list_lay.addWidget(note)
            rb, rl = ui.hbox()
            rl.setContentsMargins(8, 6, 8, 0)
            rl.addWidget(_small("滑条全部恢复原版", self.reset_simple), 0, VC)
            rl.addStretch(1)
            self.list_lay.addWidget(rb)

    def set_dev(self, on):
        on = bool(on)
        if on == self.dev:
            return
        self.dev = on
        if self.editing and not on:
            self.close_editor(ask=False)
        for r in self.simple_rows:
            r.setVisible(not on)
        self.btn_reset_all.setVisible(not on)
        self.dev_row.setVisible(on)
        if on:
            self.refill()

    def put(self, kind, idx):
        if kind not in db.READY or kind not in db.OPEN_KINDS or self.data["live"].get(kind) == idx:
            return
        self.data["live"][kind] = idx
        self._write(T("{0}：{1}", tr(db.TYPE_NAME[kind]),
                      self.data["blocks"][kind][idx]["name"] if idx is not None else tr("回到原版")))

    def _write(self, what):
        try:
            db.write_live(self.data)
        except OSError as e:
            self.app.say(T("写不进数据文件：{0}", e), "err")
            return
        self.waiting_since = self.data["seq"]
        self.refresh()
        running = self.app.state.get("running")
        self.app.say(what + (tr("，游戏内立即生效。") if running else tr("，下次开游戏 / 进地图生效。")), "ok")

    def refresh(self):
        self.kinds.update()
        if self.dev and not self.editing:
            self.refill()
        self._show_status()

    def _editor(self, kind):
        if kind not in self.editors:
            if kind == "player":
                from pages.player_editor import PlayerEditor
                self.editors[kind] = PlayerEditor(self.app, self.view)
            elif kind == "enemy":
                from pages.enemy_editor import EnemyEditor
                self.editors[kind] = EnemyEditor(self.app, self.view)
            elif kind == "weapon":
                from pages.weapon_editor import WeaponEditor
                self.editors[kind] = WeaponEditor(self.app, self.view)
            elif kind.startswith("strat_"):
                from pages.strat_editor import StratEditor
                self.editors[kind] = StratEditor(self.app, self.view, kind[len("strat_"):])
            else:
                from pages.spawn import SpawnEditor
                self.editors[kind] = SpawnEditor(self.app, self.view)
            self.editors[kind].set_visible(False)
        return self.editors[kind]

    def open_editor(self, kind, idx):
        if kind not in db.READY:
            return
        cells = self.data["blocks"][kind]
        if idx is None:
            idx = next((i for i, c in enumerate(cells) if c is None), None)
            if idx is None:
                self.app.say(T("这一类最多 {0} 块，先删掉一块。", db.COUNT), "warn")
                return
        cell = cells[idx]
        new = cell is None
        if new:
            cell = {"name": T("{0} {1}", tr(db.TYPE_NAME[kind]), idx + 1), "data": {}}
        ed = self._editor(kind)
        race = None
        ack = db.read_ack() if self.app.state.get("running") else {}
        if ack.get("race") in RACE_ZH:
            race = ack["race"]
        ed.load(copy.deepcopy(cell.get("data") or {}), race)
        self.editing = (kind, idx, new)
        self.v_name.set(cell["name"])
        self.ed_title.config(text=tr(db.TYPE_NAME[kind]) + (tr("（新建）") if new else ""))
        self.btn_del.set_enabled(not new)
        self.dev_row.hide()
        for k, e in self.editors.items():
            e.set_visible(k == kind)
        self.edit_bar.show()
        self.view.yview_moveto(0)

    def close_editor(self, ask=True):
        if self.editing and ask:
            kind = self.editing[0]
            if self.editors[kind].dirty and not self.app.ask("修改后尚未点击「确定」，放弃这些修改吗？"):
                return
        self.editing = None
        self.edit_bar.hide()
        for e in self.editors.values():
            e.set_visible(False)
        self.dev_row.setVisible(bool(self.dev))
        self.refresh()
        self.view.yview_moveto(0)

    def commit(self):
        if not self.editing:
            return
        kind, idx, _new = self.editing
        name = (self.v_name.get() or "").strip()
        if not name or len(name) > 20:
            self.app.warn("块的名字要 1～20 个字。")
            return
        live = self.data["live"].get(kind) == idx
        if live and not self.app.ask("这块正在使用，确定后游戏里马上换成改好的。继续吗？"):
            return
        self.data["blocks"][kind][idx] = {"name": name, "data": self.editors[kind].dump()}
        self.editors[kind].dirty = False
        if live:
            self.editing = None
            self._write(T("「{0}」已保存并生效", name))
        else:
            try:
                db.save(self.data)
            except OSError as e:
                self.app.say(T("存不进去：{0}", e), "err")
                return
            self.app.say(T("「{0}」已保存。回列表点击「使用」就能用。", name), "ok")
        self.close_editor(ask=False)

    def delete_block(self):
        if not self.editing:
            return
        kind, idx, new = self.editing
        if new:
            return
        name = self.data["blocks"][kind][idx]["name"]
        if not self.app.ask(T("删掉块「{0}」？删了找不回来。", name)):
            return
        live = self.data["live"].get(kind) == idx
        self.data["blocks"][kind][idx] = None
        self.editors[kind].dirty = False
        if live:
            self.data["live"][kind] = None
            self.editing = None
            self._write(T("已删掉块「{0}」，{1}回到原版", name, tr(db.TYPE_NAME[kind])))
        else:
            db.save(self.data)
            self.app.say(T("已删掉块「{0}」。", name), "ok")
        self.close_editor(ask=False)

    def _tick(self):
        if self.app.current is self:
            self._show_status()
        self.app.after(POLL_MS, self._tick)

    def on_show(self):
        self._show_status()

    def _show_status(self):
        if not self.app.state.get("running"):
            self.set_when(tr("游戏运行时也能修改，松开即生效") + "　" + tr("游戏未运行：下次启动游戏 / 进入地图后生效"), ui.DISABLED)
            return
        ack = db.read_ack()
        try:
            seq = int(ack.get("seq") or -1)
        except ValueError:
            seq = -1
        if seq != self.data["seq"]:
            self.set_when(tr("等游戏读取…（一直等不到：可能在加载，或游戏里是旧版 MOD，关游戏后关开一次「核心」）"), ui.YELLOW)
            return
        where = tr(WHERE_ZH.get(ack.get("where"), ack.get("where") or ""))
        race = tr(RACE_ZH.get(ack.get("race"), ""))
        keys = ("player", "params", "spawn", "weapon", "strat.blue", "strat.red", "strat.green", "strat.vehicle", "strat.yellow")
        if not db.FULL:
            keys = ("params", "spawn")
        errs = [ack[k] for k in keys if (ack.get(k) or "").startswith("err")]
        text = tr("游戏已收到") + (f" · {where}" if where else "") + (f" · {race}" if race else "")
        if errs:
            self.set_when(text + "　" + tr("游戏没认的：") + "；".join(errs), ui.SALMON)
        elif ack.get("guest") == "1":
            self.set_when(text + "　" + (tr("你在别人的房间里：这里改的数据都不生效，全部按原版（回到自己的房间再套上）")
                                         if db.FULL else tr("你在别人的房间里：出怪和怪物属性不生效，只有房主的管用")), ui.YELLOW)
        else:
            self.set_when(text + ("" if race else "　" + tr("出怪的改动进了地图才套上")), ui.MINT)

    def sync(self):
        self.kinds.update()
        self._show_status()
