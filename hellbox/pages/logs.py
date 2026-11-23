"""
日志页：HellBox 和游戏的报错、警告、崩溃记录，新的在上；数据来自 logbook.py。
"""
import os

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QPlainTextEdit

import logbook
import ui
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

FILTERS = [("all", "全部"), ("error", "只看报错"), ("game", "游戏"), ("hellbox", "HellBox")]
LEVEL_TEXT = {"ERROR": "报错", "WARN": "警告", "CRASH": "崩溃"}
POLL_MS = 3000


def keep(row, mode):
    if mode == "error":
        return row["level"] in ("ERROR", "CRASH")
    if mode == "game":
        return row["origin"] in ("游戏脚本", "crash")
    if mode == "hellbox":
        return row["origin"] == "HellBox"
    return True


def line(row):
    level = tr(LEVEL_TEXT.get(row["level"], row["level"]))
    return f"{row['time']}  [{level}]  {tr(row['source'])}: {row['text']}"


class LogsPage(Page):
    key = "logs"
    tab = "日志"
    when = ""
    when_color = ui.YELLOW

    def build(self):
        self.mode = ui.Var("all")
        self.rows = []
        card = ui.Card(self.view, "LOG", "日志", fill=ui.SALMON)
        w, lay = ui.hbox()
        lay.addWidget(ui.Segmented(None, FILTERS, self.mode, command=lambda _k: self._render(), padx=10, pady=3))
        lay.addStretch(1)
        for text, fn in (("复制", self._copy), ("打开文件夹", self._open), ("清空", self._clear)):
            lay.addSpacing(8)
            lay.addWidget(ui.Button(None, text, fn, padx=10, pady=3))
        card.add(w)
        self.count = card.add(ui.text(card.body, "", muted=True, size=9), top=8)
        self.box = QPlainTextEdit()
        self.box.setReadOnly(True)
        self.box.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.box.setFont(ui.f_mono(9))
        self.box.setMinimumHeight(380)
        self.box.setStyleSheet(f"QPlainTextEdit {{ background: {ui.INSET}; color: {ui.INK}; "
                               f"border: 2px solid {ui.INK}; padding: 6px; }}")
        card.add(self.box, top=6)

        self.view.row(card)
        self.app.after(POLL_MS, self._tick)

    def _tick(self):
        if self.app.current is self:
            self._load()
        self.app.after(POLL_MS, self._tick)

    def _load(self):
        def done(ok, rows):
            if ok and rows != self.rows:
                self.rows = rows
                self._render()

        self.app.bg(logbook.entries, done)

    def _render(self):
        shown = [r for r in self.rows if keep(r, self.mode.get())]
        errors = sum(1 for r in self.rows if r["level"] in ("ERROR", "CRASH"))
        self.count.config(text=T('共 {0} 条，其中报错 / 崩溃 {1} 条。', len(self.rows), errors) if self.rows else "没有记录。")
        text = "\n".join(line(r) for r in shown) or "（这里还没有记录）"
        if self.box.toPlainText() != text:
            self.box.setPlainText(text)

    def _copy(self):
        shown = [r for r in self.rows if keep(r, self.mode.get())]
        QGuiApplication.clipboard().setText("\n".join(line(r) for r in shown))
        self.app.say(T('已复制 {0} 条日志。', len(shown)), "ok")

    def _open(self):
        os.makedirs(logbook.DIR, exist_ok=True)
        os.startfile(logbook.DIR)

    def _clear(self):
        if self.app.ask("清空日志？（游戏崩溃报告不会删除，只是以后不显示现在这些。）"):
            logbook.clear()
            self.rows = []
            self._render()
            self.app.say("日志已清空。", "ok")

    def on_show(self):
        self._load()
