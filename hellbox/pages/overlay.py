"""决策显示（HD1-030，2026-11-11）：游戏画面左边那个半透明框显示哪几行、多透明、放哪。

用户："给你说的设定直接写到hellbox里面吧,可以开关这些显示"。
设置写进 ai\\overlay_settings.json（陪玩程序 ai\\overlay.py 读，开着的局 2 秒内生效），改了马上保存，不用关游戏。
框是 mod（mod\\src\\ai_overlay.lua）画的：mod 要装着（「关于」页的「核心」）；字是陪玩程序写的：她没在跑时框里显示等待提示。
"""
import json
import os

import paths
import ui
from pages.base import Page

SETTINGS = os.path.join(paths.ROOT, "ai", "overlay_settings.json")
DEFAULTS = {"on": 1, "block": 1, "hand": 1, "detail": 0, "history": 0, "goal": 1, "target": 1,
            "alpha": 140, "x": 12, "y": 170}
MARKS = [  # 地上标记（不受"整个框"开关管）
    ("goal", "她要去的点（绿）", "地上一个绿点，从她脚下排一串小绿点过去"),
    ("target", "她要打的那只（橙）", "那只虫中心一个橙点"),
]
LINES = [  # (键, 名字, 例子)
    ("block", "被谁拦了（红字）", "想做的被别的规矩拦下时才出现，例：底线破了：站在冲锋虫正面踩踏圈"),
    ("hand", "手在干什么（青字）", "例：手：开火 11 号 / 手：放下枪（放下枪快走让冲锋）"),
    ("detail", "腿和打分细节（灰字）", "腿怎么走、打分第一第二名和加减分、站位层、局势。行多，查问题时再开"),
    ("history", "最近 3 次变化（灰字）", "例：1.5 秒前：保命 › 躲震地"),
]


def load():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            s.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return s


def save(s):
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({k: s[k] for k in DEFAULTS}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SETTINGS)


class OverlayPage(Page):
    key = "overlay"
    tab = "决策显示"

    def build(self):
        s = load()
        self.v = {k: ui.Var(bool(s[k])) for k in ("on",) + tuple(k for k, _n, _e in LINES + MARKS)}
        self.alpha = ui.Var(int(round(s["alpha"] * 100 / 255)))
        self.x = ui.Var(int(s["x"]))
        self.y = ui.Var(int(s["y"]))
        self._pending = None

        # ---- 左：显示哪几行
        card = ui.Card(self.view, "OVERLAY", "显示哪几行", fill=ui.MINT)
        card.add(self._row("整个框", "关了左边的字就不画（地上标记单独开关），其他设置保留", self.v["on"]))
        card.add(ui.text(card.body, "第一行（她在干什么，例：战斗·冲锋虫 › 引它冲（15 号，7.8 米））总是显示。",
                         muted=True, size=9), top=12)
        for k, name, eg in LINES:
            card.add(self._row(name, eg, self.v[k]), top=10)
        self._label(card, "地上标记")
        for k, name, eg in MARKS:
            card.add(self._row(name, eg, self.v[k]), top=6)

        # ---- 右：样子和位置
        pos = ui.Card(self.view, "STYLE", "样子和位置", fill=ui.YELLOW)
        self.a_text, self.x_text, self.y_text = (ui.Label("", font=ui.f_mono(12, True)) for _ in range(3))
        for lab in (self.a_text, self.x_text, self.y_text):
            lab.setFixedWidth(ui.chars(lab.font(), 5))
        self._label(pos, "底框不透明度")
        pos.add(ui.line(ui.Slider(None, self.alpha, 0, 100, command=lambda final: self.changed(), width=220),
                        8, self.a_text))
        self._label(pos, "离屏幕左边")
        pos.add(ui.line(ui.Slider(None, self.x, 0, 900, command=lambda final: self.changed(), width=220),
                        8, self.x_text))
        self._label(pos, "离屏幕上边")
        pos.add(ui.line(ui.Slider(None, self.y, 0, 650, command=lambda final: self.changed(), width=220),
                        8, self.y_text))
        pos.add(ui.text(pos.body, "位置按 1280×720 的画面算，屏幕再大也按比例放。", muted=True, size=9), top=6)
        self.btn_reset = ui.Button(None, "恢复默认", self.reset)
        pos.add(ui.line(self.btn_reset), top=16)
        self.hint = pos.add(ui.text(pos.body, "", muted=True, size=9), top=10)

        self.view.row(card, pos, weights=(5, 4))
        self.update_labels()

    def _label(self, card, s):
        card.add(ui.Label(s, font=ui.f_zh(10, True)), top=10 if card.blay.count() else 0)
        card.blay.addSpacing(4)

    def _row(self, name, eg, var):
        w, lay = ui.hbox()
        lay.addWidget(ui.Toggle(None, var, command=self.changed), 0, ui.Qt.AlignmentFlag.AlignVCenter)
        lay.addSpacing(12)
        col, cl = ui.vbox()
        cl.addWidget(ui.Label(name, font=ui.f_zh(10, True)))
        cl.addWidget(ui.text(None, eg, muted=True, size=9))
        lay.addWidget(col, 1)
        return w

    def current(self):
        s = {k: int(bool(v.get())) for k, v in self.v.items()}
        s.update(alpha=int(round(int(self.alpha.get()) * 255 / 100)), x=int(self.x.get()), y=int(self.y.get()))
        return s

    def update_labels(self):
        self.a_text.config(text=f"{int(self.alpha.get())}%")
        self.x_text.config(text=str(int(self.x.get())))
        self.y_text.config(text=str(int(self.y.get())))

    def changed(self, *_a):
        self.update_labels()
        ui.cancel(self._pending)
        self._pending = ui.after(200, self._save)

    def _save(self):
        self._pending = None
        try:
            save(self.current())
            self.hint.config(text="已保存。她在打的话 2 秒内生效；没在打下次开局生效。", fg=ui.MUTED)
        except OSError as e:
            self.hint.config(text=f"保存不了：{e}", fg=ui.BAD)

    def reset(self):
        for k, v in self.v.items():
            v.set(bool(DEFAULTS[k]))
        self.alpha.set(int(round(DEFAULTS["alpha"] * 100 / 255)))
        self.x.set(DEFAULTS["x"])
        self.y.set(DEFAULTS["y"])
        self.changed()

    def sync(self):
        st = self.app.state.get("script")
        if st == "off":
            self.hint.config(text="「核心」没开：框画不出来。先到「关于」页打开「核心」。", fg=ui.WARN)
        elif st == "old":
            self.hint.config(text="游戏里是旧版 MOD（可能还没有决策框）：关游戏后在「关于」页关开一次「核心」。", fg=ui.WARN)
        elif self._pending is None:
            self.hint.config(text="改了马上保存。她在打的话 2 秒内生效；没在打下次开局生效。", fg=ui.MUTED)
