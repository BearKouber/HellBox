"""考场（HD1-027 第 2 步，2026-11-11）：勾几个固定场景、每个跑几局，一键连着跑完；跑完算成绩单。

用户："希望可以有每次你测试的多个场景可以直接在hellbox里面选择,省的我一个一个点"。
场景定义、连跑都在 ai\\arena.py（命令行也能跑），成绩单在 ai\\scorecard.py；这一页只是按钮和显示。
进度读 ai\\logs\\runs\\arena\\current.json（arena.py 写）和正在跑那局的 drill_status.json。
「停止」= 在 arena 文件夹和这一局的文件夹各放 STOP：这一局马上收尾，后面的不跑。
方案见开发文档「考场方案」。
"""
import json
import os
import subprocess
import sys

import paths
import ui
from pages.base import Page
from i18n import T, tr
from pages.quick import NO_WINDOW, PYTHON, STATE_TEXT, pid_alive

AI_DIR = os.path.join(paths.ROOT, "ai")
if AI_DIR not in sys.path:
    sys.path.insert(0, AI_DIR)
import arena  # noqa: E402
import scorecard  # noqa: E402

POLL_MS = 1000
MINUTES = {"1": 3.5, "2": 4.5, "3": 5.5, "4": 5.5, "5": 9.5}   # 一局大概几分钟（含开关游戏）


class ArenaPage(Page):
    key = "arena"
    tab = "考场"

    def build(self):
        self.v_scene = {k: ui.Var(k in ("1", "2")) for k in arena.SCENES}
        self.v_n = ui.Var("3")
        self.v_ver = ui.Var("new")
        self.v_report = ui.Var("1")
        self._timer = None
        self._report_busy = False

        # ---- 左：选场景
        card = ui.Card(self.view, "ARENA", "选场景", fill=ui.SALMON, note="同一张图 · 她一个人 · 无人值守")
        for k, (name, main, _req) in arena.SCENES.items():
            card.add(ui.CheckBox(None, f"{k}. {name}", self.v_scene[k], command=self._changed,
                                 note=T("主要看{0}，一局约 {1:g} 分钟", tr(main), MINUTES[k])), top=8 if k != "1" else 0)
        card.add(ui.line(ui.Button(None, "全选", lambda: self._pick(list(arena.SCENES)), padx=8, pady=2),
                         8, ui.Button(None, "只冲锋虫（1、2）", lambda: self._pick(["1", "2"]), padx=8, pady=2),
                         8, ui.Button(None, "全不选", lambda: self._pick([]), padx=8, pady=2)), top=12)
        card.add(ui.Label("每个场景跑几局", font=ui.f_zh(10, True)), top=14)
        self.step_n = ui.Stepper(None, self.v_n, 1, 10, command=self._changed)
        card.add(ui.line(self.step_n, 8, ui.Label("局（说\"变好了\"至少 3 局）", font=ui.f_zh(9), fg=ui.MUTED)), top=4)
        card.add(ui.Label("冲锋虫用哪套打法", font=ui.f_zh(10, True)), top=14)
        card.add(ui.line(ui.Segmented(None, [("new", "打分版（现在用的）"), ("old", "旧剧本（对比用）")], self.v_ver,
                                      command=self._changed, padx=10, pady=4)), top=4)
        self.est = card.add(ui.text(card.body, "", size=10, bold=True), top=14)
        self.btn_start = ui.Button(None, "开始", self.start, kind="primary", padx=26, pady=6, font=ui.f_zh(11, True))
        self.btn_stop = ui.Button(None, "停止", self.stop, kind="danger", padx=26, pady=6, font=ui.f_zh(11, True))
        card.add(ui.line(self.btn_start, 12, self.btn_stop), top=10)
        self.hint = card.add(ui.text(card.body, "", muted=True, size=9), top=8)

        # ---- 右：进度
        st = ui.Card(self.view, "STATUS", "进度", fill=ui.SKY)
        self.sq = ui.Square(color=ui.DISABLED, size=22)
        self.word = ui.Label("未开始", font=ui.f_zh(16, True))
        st.add(ui.line(self.sq, 10, self.word))
        self.now = st.add(ui.text(st.body, "", size=10), top=6)
        self.nums = st.add(ui.Label("", font=ui.f_mono(11, True)), top=6)
        st.add(ui.Label("跑完的局", font=ui.f_zh(10, True), fg=ui.MUTED), top=12)
        self.done = st.add(ui.text(st.body, "（还没有）", size=9))
        self.view.row(card, st, weights=(1, 1))

        # ---- 下：成绩单
        rep = ui.Card(self.view, "REPORT", "成绩单", fill=ui.YELLOW, note="每个版本：中间值 / 最差 + 每局一段")
        opts = [(k, f"{k}. {arena.SCENES[k][0]}") for k in arena.SCENES]
        rep.add(ui.line(ui.Segmented(None, opts, self.v_report, command=self.report, padx=8, pady=3)))
        self.btn_report = ui.Button(None, "算成绩单", self.report, kind="accent", padx=12, pady=3)
        self.btn_folder = ui.Button(None, "打开记录文件夹", self.open_folder, padx=10, pady=3)
        rep.add(ui.line(self.btn_report, 8, self.btn_folder), top=8)
        self.report_text = rep.add(ui.Label("选一个场景，点「算成绩单」。", font=ui.f_mono(9), wrap=True, breakable=True),
                                   top=10)
        self.view.row(rep)
        self._changed()

    # ------------------------------------------------------------ 设置
    def _pick(self, keys):
        for k, v in self.v_scene.items():
            v.set(k in keys)
        self._changed()

    def chosen(self):
        return [k for k in arena.SCENES if self.v_scene[k].get()]

    def _changed(self, *_a):
        ks = self.chosen()
        n = self.step_n.value()
        mins = sum(MINUTES[k] for k in ks) * n
        self.est.config(text=(T("共 {0} 个场景 × {1} 局 = {2} 局，大约 {3:.0f} 分钟，期间别用电脑", len(ks), n, len(ks) * n, mins)
                              if ks else "还没勾场景"))
        self.sync()

    # ------------------------------------------------------------ 开始 / 停止
    def status(self):
        try:
            with open(arena.STATUS, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def running(self):
        s = self.status()
        return bool(s) and not s.get("finished") and pid_alive(s.get("pid") or 0)

    def start(self):
        ks = self.chosen()
        if not ks or self.running():
            return
        if self.app.state.get("script") != "on":
            self.app.warn("脚本 mod 不是最新版（或没开），出怪设置不会生效。\n先打开「关于」页的「核心」开关（要先关游戏）。")
            return
        if self.app.state.get("running") and not self.app.ask("游戏现在开着。开始会先把它关掉（没存的进度会丢）。\n确定吗？"):
            return
        args = [PYTHON, "-B", os.path.join(AI_DIR, "arena.py"), "run", ",".join(ks), "--n", str(self.step_n.value())]
        if self.v_ver.get() == "old":
            args.append("--old-tank")
        os.makedirs(arena.ARENA, exist_ok=True)
        try:
            out = open(os.path.join(arena.ARENA, "arena_stdout.txt"), "w", encoding="utf-8")
            subprocess.Popen(args, cwd=paths.ROOT, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             env=dict(os.environ, PYTHONIOENCODING="utf-8"), creationflags=NO_WINDOW)
        except OSError as e:
            self.app.error(f"启动失败：{e}")
            return
        self.app.say(f"考场开始：场景 {'、'.join(ks)}，每个 {self.step_n.value()} 局。", "info")
        self.word.config(text="准备中")
        self._poll_later(1500)

    def stop(self):
        s = self.status()
        try:
            open(arena.STOP, "w").close()
            if s.get("run_dir") and os.path.isdir(s["run_dir"]):
                open(os.path.join(s["run_dir"], "STOP"), "w").close()
            self.app.say("已请求停止：这一局收尾、关游戏，后面的不跑了。", "info")
        except OSError as e:
            self.app.say(f"停不了：{e}", "err")

    def open_folder(self):
        folder = os.path.join(arena.ARENA, self.v_report.get())
        os.startfile(folder if os.path.isdir(folder) else arena.ARENA if os.path.isdir(arena.ARENA) else AI_DIR)

    # ------------------------------------------------------------ 进度
    def _poll_later(self, ms=POLL_MS):
        ui.cancel(self._timer)
        self._timer = self.app.after(ms, self._poll)

    def _poll(self):
        self._timer = None
        self._show()
        if self.running():
            self._poll_later()
        self.sync()

    def _show(self):
        s = self.status()
        run = self.running()
        live = {}
        if run and s.get("run_dir"):
            try:
                with open(os.path.join(s["run_dir"], "drill_status.json"), encoding="utf-8") as f:
                    live = json.load(f)
            except (OSError, ValueError):
                pass
        if run:
            word, color = STATE_TEXT.get(live.get("state", "starting"), ("进行中", ui.MINT))
            self.word.config(text=word)
            self.sq.set_color(color)
            scenes = s.get("scenes") or []
            total = len(scenes) * (s.get("n") or 1)
            self.now.config(text=(f"场景 {s.get('scene', '?')}「{s.get('scene_name', '')}」第 {s.get('round', '?')}/{s.get('of', '?')} 局"
                                  f"（全部第 {len(s.get('done') or []) + 1}/{total} 局）。{live.get('msg') or ''}"))
            el = live.get("elapsed", 0) or 0
            self.nums.config(text=f"打死 {live.get('kills', 0)}   死了 {live.get('deaths', 0)} 次   "
                                  f"{int(el // 60)}:{int(el % 60):02d}")
        else:
            self.word.config(text="已结束" if s else "未开始")
            self.sq.set_color(ui.SKY if s else ui.DISABLED)
            self.now.config(text=("上一次" + ("被停止" if s.get("stopped") else "跑完了") + f"（{s.get('started', '')} 开始）")
                            if s else "勾好场景，点「开始」。")
            self.nums.config(text="")
        done = s.get("done") or []
        self.done.config(text="\n".join(f"场景 {d['scene']} 第 {d['round']} 局：{d['reason']}，打死 {d.get('kills')}，"
                                        f"死 {d.get('deaths')} 次，{d.get('secs')} 秒" for d in done) or "（还没有）")

    def sync(self):
        run = self.running()
        self.btn_start.set_enabled(bool(self.chosen()) and not run and not self.app.busy)
        self.btn_stop.set_enabled(run)
        if run:
            hint = "正在跑。点「停止」= 这一局收尾、关游戏，后面的不跑。快速开局页这时别用。"
        elif self.app.state.get("script") not in (None, "on"):
            hint = "脚本 mod 不是最新版：先打开「关于」页的「核心」开关。"
        else:
            hint = "点「开始」会先关掉正在运行的游戏。跑完自动关游戏。"
        self.hint.config(text=hint)

    def on_show(self):
        self._show()
        if self.running():
            self._poll_later()
        self.sync()

    # ------------------------------------------------------------ 成绩单
    def report(self, *_a):
        if self._report_busy:
            return
        scene = self.v_report.get()
        folder = os.path.join(arena.ARENA, scene)
        self._report_busy = True
        self.report_text.config(text="算着……")

        def work():
            import glob
            dirs = sorted(d for d in glob.glob(os.path.join(folder, "*")) if os.path.isdir(d))
            return scorecard.report(dirs) if dirs else f"场景 {scene} 还没有记录。"

        def done(ok, result):
            self._report_busy = False
            self.report_text.config(text=result if ok else f"算不出来：{result}")

        self.app.bg(work, done)
