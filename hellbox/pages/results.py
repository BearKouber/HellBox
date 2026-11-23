"""
战绩页：任务结算时由 mod/src/hellbox_results.lua 记一行，这里列出每局并可查看战绩卡片。
"""
import json
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter

import ui
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

FOLDER = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "HellBox"
FILE = FOLDER / "results.json"
FEED = Path(os.getenv("APPDATA") or Path.home()) / "Arrowhead" / "Helldivers" / "hellbox-results-feed.txt"
FIELDS = ("epoch", "seed", "race", "difficulty", "mode", "won", "extracted", "stars", "seconds",
          "done", "total", "kills", "deaths", "samples", "teamkills", "players")
PFIELDS = ("kills", "deaths", "teamkills", "shots", "hits", "samples", "extracted", "me")
RACES = ("虫族", "生化人", "光能者")
MODES = ("普通任务", "原版选图", "自定义选图", "自定义任务")
FILTERS = [(-1, "全部")] + list(enumerate(MODES))
COLS = [("日期", 3), ("阵营", 2), ("难度", 1), ("结果", 3), ("星级", 2), ("用时", 2)]
SHOW_MAX = 60


def parse_line(line):
    parts = line.strip().split("|")
    if len(parts) < 1 + len(FIELDS):
        return None, None
    try:
        values = [int(p) for p in parts[1:1 + len(FIELDS)]]
    except ValueError:
        return None, None
    if not 0 <= values[4] < len(MODES):
        return None, None
    row = dict(zip(FIELDS, values))
    players = []
    for cell in parts[1 + len(FIELDS):]:
        if cell.startswith("#M"):
            row["mods"] = [m for m in cell[2:].split(";") if m]
            continue
        bits = cell.split("\t")
        if len(bits) != 1 + len(PFIELDS):
            continue
        try:
            nums = [int(b) for b in bits[1:]]
        except ValueError:
            continue
        players.append({"name": bits[0].strip() or "?", **dict(zip(PFIELDS, nums))})
    row["list"] = players
    return parts[0], row


def ingest(text):
    FOLDER.mkdir(parents=True, exist_ok=True)
    try:
        saved = json.loads(FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        saved = {}
    current = dict(saved)
    for line in text.splitlines():
        ident, row = parse_line(line)
        if ident and (ident not in current or len(row["list"]) >= len(current[ident].get("list") or [])):
            current[ident] = row
    if current != saved:
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, FILE)
    for row in current.values():
        row.setdefault("list", [])
    return current


def read():
    try:
        text = FEED.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    from room_name_live import MAGIC_RESULTS, live_read
    try:
        _, live = live_read(MAGIC_RESULTS, tries=1)
    except (RuntimeError, OSError):
        live = ""
    return ingest(text + "\n" + live)


# ---------------------------------------------------------------- 这局改了什么
SRC_ZH = {"g": "报复关", "a": "警报", "p": "巡逻"}
SPREAD_ZH = {1: "小", 2: "中", 3: "大"}
ENEMY_ZH = {"health_info.health": "血量", "health_info.armor_max": "装甲", "health_info.armor_min": "装甲",
            "enemy_info.movement_speed": "移动速度", "melee_info.power": "攻击伤害", "weapon_info.power": "攻击伤害"}
STRAT_ZH = {"cooldown_time": "冷却时间", "activation_time": "呼叫时间", "num_uses": "使用次数"}


def _mult(e):
    if "*" in e:
        path, m = e.rsplit("*", 1)
        try:
            return path, "×" + f"{float(m):g}"
        except ValueError:
            return path, tr("改过")
    return e.split("=", 1)[0], tr("改过")


def mods_text(items):
    out = []

    def add(text):
        if text not in out:
            out.append(text)

    player_names, weapon_groups = {}, {}
    try:
        from pages.player_editor import ROWS
        player_names = {p: n.split("（")[0] for _s, rows in ROWS for p, n, *_ in rows}
    except Exception:  # noqa: BLE001
        pass
    try:
        from pages.weapon_editor import fields
        meta = fields()
        labels = {g["key"]: g["label"] for g in meta.get("common") or []}
        for (_unit, path), r in (meta.get("_index") or {}).items():
            if r.get("common") in labels:
                weapon_groups.setdefault(path, labels[r["common"]])
    except Exception:  # noqa: BLE001
        pass
    for item in items or []:
        kind, _, e = item.partition(":")
        if kind == "P":
            if e == "god=heal":
                add(tr("加血无敌"))
            elif e == "god=true":
                add(tr("真无敌"))
            else:
                path, m = _mult(e)
                add(T("绝地潜兵{0} {1}", tr(player_names.get(path, path.rsplit(".", 1)[-1])), m))
        elif kind == "E":
            if e.startswith("set="):
                add(T("单只怪改了 {0} 项", e[4:]))
            else:
                path, m = _mult(e)
                name = ENEMY_ZH.get(path)
                if not name:
                    try:
                        from pages.enemy_zh import describe
                        name = describe(path)[0]
                    except Exception:  # noqa: BLE001
                        name = path.rsplit(".", 1)[-1]
                add(T("敌人{0} {1}", tr(name), m))
        elif kind == "W":
            path, m = _mult(e)
            add(T("武器{0} {1}", tr(weapon_groups.get(path, "单独改")), m if path in weapon_groups else ""))
        elif kind == "T":
            path, m = _mult(e)
            add(T("战略配备{0} {1}", tr(STRAT_ZH.get(path, "单独改")), m if path in STRAT_ZH else ""))
        elif kind == "S":
            key, _, val = e.partition("=")
            if key == "spread":
                add(T("出生散开 {0}", tr(SPREAD_ZH.get(int(val or 0), val))))
            elif key == "vn":
                add(T("战车每次放 {0} 只", val))
            elif key == "cap":
                add(tr("场上上限 破限") if val.strip() == "-1" else T("场上上限 {0}", val))
            elif key == "v":
                add(tr("载具不放兵") if val == "none" else tr("载具放兵换怪"))
            elif key in SRC_ZH:
                src = tr(SRC_ZH[key])
                if val.startswith("mult*"):
                    add(T("{0}数量 ×{1}", src, val[5:]))
                elif val == "only":
                    add(T("{0}只出选中的怪", src))
                elif val == "none":
                    add(T("{0}不出怪", src))
                else:
                    add(T("{0}自己改", src))
        elif kind == "D" and e.startswith("wave="):
            add(T("从第 {0} 波开始", e[5:]))
    return [t.strip() for t in out]


def time_text(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}"


def outcome(row):
    if row["won"] and row["extracted"]:
        return "通关并撤离", ui.GOOD
    if row["won"]:
        return "通关", ui.GOOD
    return "失败", ui.BAD


def cells(row):
    stamp = datetime.fromtimestamp(row["epoch"]).strftime("%m-%d %H:%M")
    race = RACES[row["race"]] if 0 <= row["race"] < len(RACES) else "其他"
    word, color = outcome(row)
    stars = "★" * row["stars"] + "☆" * (3 - row["stars"]) if row["stars"] else "—"
    return [(stamp, ui.INK), (race, ui.INK), (str(row["difficulty"]), ui.INK), (word, color), (stars, ui.INK),
            (time_text(row["seconds"]), ui.INK)]


def _paint_cols(p, rect, texts, font, weights):
    total = sum(weights)
    x = rect.left() + 12
    width = rect.width() - 24
    p.setFont(font)
    for (text, color), wt in zip(texts, weights):
        w = int(width * wt / total)
        p.setPen(ui.qc(color))
        p.drawText(QRect(x, rect.top(), w, rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tr(text))
        x += w


class HeaderRow(ui.QWidget):
    def __init__(self, cols):
        super().__init__()
        self.cols = cols
        self.setFixedHeight(30)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), ui.qc(ui.INK))
        _paint_cols(p, self.rect(), [(c, ui.CARD) for c, _w in self.cols], ui.f_zh(9, True), [w for _c, w in self.cols])


class ResultRow(ui.Clickable):

    def __init__(self, row, stripe, command):
        super().__init__()
        self.row, self.stripe, self.command = row, stripe, command
        self.texts = cells(row)
        self.setFixedHeight(32)

    def paintEvent(self, _e):
        p = QPainter(self)
        bg = ui.MINT_HOVER if self.hovered else (ui.INSET if self.stripe else ui.CARD)
        p.fillRect(self.rect(), ui.qc(bg))
        p.fillRect(0, self.height() - 1, self.width(), 1, ui.qc(ui.DOT))
        _paint_cols(p, self.rect(), self.texts, ui.f_zh(10, True), [w for _c, w in COLS])
        p.setPen(ui.qc(ui.MUTED))
        p.setFont(ui.f_mono(10, True))
        p.drawText(self.rect().adjusted(0, 0, -12, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "›")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.command(self.row)


class Stat(ui.QWidget):

    def __init__(self, title, value, fill=ui.WHITE, font=None):
        super().__init__()
        self.title, self.value, self.fill = title, value, fill
        self.vfont = font or ui.f_mono(15, True)
        self.setFixedHeight(64)
        self.setMinimumWidth(90)

    def paintEvent(self, _e):
        p = QPainter(self)
        r = ui.paint_box(p, self.width(), self.height(), self.fill, 2, 3)
        p.setPen(ui.qc(ui.MUTED))
        p.setFont(ui.f_zh(9, True))
        p.drawText(r.adjusted(10, 4, -6, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, tr(self.title))
        p.setPen(ui.qc(ui.INK))
        p.setFont(self.vfont)
        p.drawText(r.adjusted(10, 0, -6, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, tr(self.value))


class ResultsPage(Page):
    key = "results"
    tab = "战绩"
    when = ""

    def build(self):
        self.rows = {}
        self.reading = False
        self.opened = None

        # ---- 列表
        self.list_card = ui.Card(self.view, "RESULTS", "最近的战斗", fill=ui.MINT)
        self.filter = ui.Var(-1)
        self.seg = ui.Segmented(None, FILTERS, self.filter, command=lambda _v: self.refresh(), padx=9, pady=4, shadow=3)
        self.list_card.add(self.seg, align=ui.LEFT)
        self.summary = self.list_card.add(ui.text(self.list_card.body, "", bold=True, size=10), top=8)
        frame = ui.Box(fill=ui.CARD, border=2, shadow=4)
        frame.lay.addWidget(HeaderRow(COLS))
        self.list_box, self.list_lay = ui.vbox()
        frame.lay.addWidget(self.list_box)
        self.empty = ui.text(None, "还没有记录。打完一局（结算画面出来）就会自动记下来。", muted=True, size=10)
        self.empty.setContentsMargins(12, 14, 12, 14)
        frame.lay.addWidget(self.empty)
        self.list_card.add(frame, top=8)
        self.list_row = self.view.row(self.list_card)

        # ---- 战绩卡片
        self.card = ui.Card(self.view, "REPORT", "战绩卡片", fill=ui.YELLOW)
        self.btn_back = ui.Button(None, "‹ 返回列表", self.close_detail, padx=10, pady=3)
        self.card.add(self.btn_back, align=ui.LEFT)
        self.head = self.card.add(ui.Label("", font=ui.f_zh(15, True)), top=12)
        self.sub = self.card.add(ui.text(self.card.body, "", muted=True, size=10), top=2)
        self.mods = self.card.add(ui.text(self.card.body, "", size=10), top=6)
        self.stats_w, self.stats_lay = ui.hbox(spacing=12)
        self.card.add(self.stats_w, top=12)
        self.players_title = self.card.add(ui.Label("玩家", font=ui.f_zh(11, True)), top=16)
        self.players_frame = ui.Box(fill=ui.CARD, border=2, shadow=4)
        self.players_frame.lay.addWidget(HeaderRow(self.PCOLS))
        self.players_box, self.players_lay = ui.vbox()
        self.players_frame.lay.addWidget(self.players_box)
        self.card.add(self.players_frame, top=6)
        self.players_note = self.card.add(ui.text(self.card.body, "", muted=True, size=9), top=8)
        self.card_row = self.view.row(self.card)
        self.card_row.hide()
        self.app.after(400, self._tick)

    PCOLS = [("玩家", 4), ("杀敌", 1), ("死亡", 1), ("误杀", 1), ("命中率", 2), ("样本", 1), ("撤离", 1)]

    # ------------------------------------------------------------ 读记录
    def _tick(self):
        if not self.reading:
            self.reading = True
            self.app.bg(read, self._got)
        self.app.after(3000, self._tick)

    def _got(self, ok, result):
        self.reading = False
        if ok and result != self.rows:
            self.rows = result
            self.refresh()
        elif not ok and self.app.current is self:
            self.summary.config(text=T('读取战绩失败：{0}', result))

    # ------------------------------------------------------------ 列表
    def refresh(self):
        mode = self.filter.get()
        shown = sorted((r for r in self.rows.values() if mode < 0 or r["mode"] == mode),
                       key=lambda r: r["epoch"], reverse=True)
        ui.clear_layout(self.list_lay)
        for i, row in enumerate(shown[:SHOW_MAX]):
            self.list_lay.addWidget(ResultRow(row, i % 2, self.open_detail))
        self.empty.setVisible(not shown)
        recent = shown[:20]
        wins = sum(r["won"] for r in recent)
        self.summary.config(text=T('共 {0} 局 · 最近 {1} 局通关 {2} 局', len(shown), len(recent), wins) if recent else "")

    # ------------------------------------------------------------ 战绩卡片
    def open_detail(self, row):
        self.opened = row
        race = RACES[row["race"]] if 0 <= row["race"] < len(RACES) else "其他"
        word, color = outcome(row)
        self.head.config(text=T('{0} · 难度 {1} · {2}', race, row['difficulty'], word), fg=color)
        when = datetime.fromtimestamp(row["epoch"]).strftime("%Y-%m-%d %H:%M")
        self.sub.config(text=T('{0}  ·  {1}  ·  地图 {2}  ·  {3} 人', when, MODES[row['mode']], row['seed'], row['players']))
        mods = mods_text(row.get("mods"))
        mods_line = (tr("这局改了：") + tr("、").join(mods) if mods else
                     (tr("这局是旧版 MOD 记的，没记下改了什么。") if row["mode"] in (2, 3) else ""))
        self.mods.config(text=mods_line)
        self.mods.setVisible(bool(mods_line))
        ui.clear_layout(self.stats_lay)
        stars = "★" * row["stars"] + "☆" * (3 - row["stars"]) if row["stars"] else "—"
        fill = ui.MINT if row["won"] else ui.SALMON
        for title, value, f in (("结果", word, fill), ("星级", stars, ui.WHITE), ("用时", time_text(row["seconds"]), ui.WHITE),
                                ("目标", f"{row['done']}/{row['total']}", ui.WHITE),
                                ("全队杀敌", str(sum(p["kills"] for p in row["list"]) or row["kills"]), ui.WHITE)):
            self.stats_lay.addWidget(Stat(title, value, f, ui.f_zh(13, True) if title == "结果" else None), 1)
        ui.clear_layout(self.players_lay)
        players = row["list"] or [{"name": "我", "kills": row["kills"], "deaths": row["deaths"],
                                   "teamkills": row["teamkills"], "shots": 0, "hits": 0,
                                   "samples": row["samples"], "extracted": row["extracted"], "me": 1}]
        for i, pl in enumerate(players):
            acc = f"{pl['hits'] / pl['shots']:.0%}" if pl["shots"] else "—"
            texts = [(pl["name"] + ("（我）" if pl["me"] else ""), ui.INK), (str(pl["kills"]), ui.INK),
                     (str(pl["deaths"]), ui.BAD if pl["deaths"] else ui.INK),
                     (str(pl["teamkills"]), ui.BAD if pl["teamkills"] else ui.INK), (acc, ui.INK),
                     (str(pl["samples"]), ui.INK), ("是" if pl["extracted"] else "否", ui.GOOD if pl["extracted"] else ui.MUTED)]
            self.players_lay.addWidget(PlayerRow(texts, i % 2, bool(pl["me"]), self.PCOLS))
        self.players_note.config(text="" if row["list"] else
                                 "这局是旧版 MOD 记的，只有你自己的数据（新版 MOD 会记下所有玩家）。")
        self.list_row.hide()
        self.card_row.show()
        self.view.yview_moveto(0)

    def close_detail(self):
        self.opened = None
        self.card_row.hide()
        self.list_row.show()


class PlayerRow(ui.QWidget):
    def __init__(self, texts, stripe, me, cols):
        super().__init__()
        self.texts, self.stripe, self.me, self.cols = texts, stripe, me, cols
        self.setFixedHeight(32)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), ui.qc(ui.YELLOW_HOVER if self.me else (ui.INSET if self.stripe else ui.CARD)))
        p.fillRect(0, self.height() - 1, self.width(), 1, ui.qc(ui.DOT))
        _paint_cols(p, self.rect(), self.texts, ui.f_zh(10, True), [w for _c, w in self.cols])
