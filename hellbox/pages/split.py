"""
分屏页：HalfSugar 的 CameraCTRL 分屏模块，安装与还原跟随核心开关；设置存在 hellbox-split.txt，游戏里由 mod/src/camera_link.lua 读取。
"""
import os

import build
import ui
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

DIR = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "camera_ctrl_v1")
SETTINGS = os.path.join(DIR, "hellbox-split.txt")
STATUS = os.path.join(DIR, "control-status.txt")
SPAWN_MULT = 4
POLL_MS = 1000
RATIOS = [("0", "跟随游戏"), ("1778", "16:9"), ("1600", "16:10"), ("1333", "4:3"), ("1250", "5:4")]
RATIO_OK = {int(v) for v, _ in RATIOS}

CAMERA_TEXT = {
    "spectator_wait": "你阵亡了，镜头停 2 秒后看队友。",
    "spectator_follow": "正在看队友（W / A 上一位，S / D 下一位）。",
    "spectator_no_teammate": "没有活着的队友，镜头停在原地，等增援。",
    "off": "分屏未开启。",
    "menu": "已连上，等进任务。",
    "local_ready_peer_unverified": "分屏已生效。",
    "return_to_team": "要先走回队伍画面里，才能还原。",
    "vehicle_return_to_team": "载具要先开回队伍画面里，才能还原。",
    "vehicle_unlocked": "载具能开出画面（车上的人都开了位置限制）。",
    "vehicle_team_boundary": "载具仍在队伍画面中（车上有人未开启解除位置限制）。",
    "vehicle_public_passenger": "载具跟随队伍画面（车上有人未开启分屏）。",
    "vehicle_passenger": "你是乘客，车往哪开由司机那边决定。",
    "vehicle_waiting_owner": "等载具控制权转过来。",
    "vehicle_waiting_seats": "等载具座位信息。",
    "suspended_character_or_vehicle": "暂停：角色没准备好，或这个座位不支持。",
    "waiting_follow_camera": "暂停：过场中，等镜头恢复。",
    "waiting_camera_replication": "等镜头同步。",
    "waiting_camera_network": "等镜头联机数据。",
    "waiting_own_master": "等自己角色的控制权（刚进关或有队友刚加入，稍等）。",
    "waiting_avatar": "等自己的角色出场。",
    "waiting_players": "等玩家数据。",
}


def load_settings():
    try:
        with open(SETTINGS, encoding="ascii") as f:
            lines = f.read().split()
        if lines[0] == "HBSPLIT1":
            mask, enc, pat = int(lines[1]), int(lines[2]), int(lines[3])
            ratio = int(lines[4]) if len(lines) > 4 else 0
            if ratio not in RATIO_OK:
                ratio = 0
            if mask in (0, 1, 3, 4, 5, 7):
                return mask, max(1, min(4, enc)), max(1, min(4, pat)), ratio
    except (OSError, ValueError, IndexError):
        pass
    return 0, 2, 4, 0


def save_settings(mask, enc, pat, ratio=0):
    os.makedirs(DIR, exist_ok=True)
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="ascii", newline="\n") as f:
        f.write(f"HBSPLIT1\n{mask}\n{enc}\n{pat}\n{ratio}\n")
    os.replace(tmp, SETTINGS)


def read_status():
    import time
    try:
        if time.time() - os.path.getmtime(STATUS) > 5:
            return False, ""
        with open(STATUS, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return False, ""
    if len(lines) < 9 or lines[0] != "CAM2":
        return False, ""
    return True, describe(lines[7])


def describe(detail):
    camera, _, spawn = detail.partition(";spawn=")
    fields = camera.split(";")
    head = fields[0]
    if head.startswith("local_players="):
        out = [T('本机有 {0} 个玩家：分屏只支持 1 个本地玩家。', head.split('=', 1)[1])]
    elif head.startswith("camera_error"):
        out = ["镜头出错，已停下：" + head.split(":", 1)[-1]]
    else:
        out = [CAMERA_TEXT.get(head, head)]
    for f in fields[1:]:
        if f.startswith("escort_transfer=waiting:"):
            out.append("人质控制权接收中，留在交互范围内。")
        elif f.startswith("escort_transfer_error="):
            out.append("人质接管没成功：" + f.split("=", 1)[1])
    s = spawn.split(";")[0] if spawn else "off"
    if s == "host_only":
        out.append("刷怪扩展：你不是房主，不生效。")
    elif s in ("waiting_task", "waiting_managers"):
        out.append("刷怪扩展：等房主任务准备好。")
    elif s == "native_same_screen":
        out.append("刷怪扩展：大家在同一个画面，按一份算。")
    elif s.startswith("expanded:"):
        out.append(T('刷怪扩展：{0} 个走开的玩家各刷一份。', s.split(':', 1)[1]))
    elif s not in ("off", ""):
        out.append("刷怪扩展暂停：" + s)
    return "\n".join(out)


class SplitPage(Page):
    key = "split"
    tab = "分屏"
    when = "不需要运行 HellBox，游戏内自动生效。只支持本机 1 名玩家"
    when_color = ui.YELLOW

    def build(self):
        mask, _enc, _pat, ratio = load_settings()
        self.v_view = ui.Var(mask & 1 == 1)
        self.v_free = ui.Var(mask & 3 == 3)
        self.v_spawn = ui.Var(mask & 4 == 4)
        self.v_ratio = ui.Var(str(ratio))
        self.controls = []
        card = ui.Card(self.view, "SPLIT", "分屏", fill=ui.MINT, note="来自 CameraCTRL")
        self.t_view = self._toggle(card, self.v_view, "解除视角限制", None,
                                   "镜头不再框住全队，只跟着你。队友也装了 HellBox 并开了分屏，才能各自走开。当客机时：房主也装了 HellBox（或开着分屏）才生效，进没装 MOD 的房间不生效。")
        self.t_free = self._toggle(card, self.v_free, "解除位置限制", None,
                                   "能走出全队的画面范围。要先开「解除视角限制」。在远处关掉分屏，要先走回队伍画面里才会还原。")
        self.t_spawn = self._toggle(card, self.v_spawn, "房主刷怪区域扩展", None,
                                    "离开主屏幕的人周围单独刷一份怪，分开几个人就是几倍（测试中，太多可能卡）。只在你当房主时生效。")
        self.seg_ratio = ui.Segmented(None, RATIOS, self.v_ratio, command=lambda _v: self._changed(), padx=8, pady=3)
        self.controls.append(self.seg_ratio)
        card.row("画面比例", self.seg_ratio,
                 help="开了「解除视角限制」才生效。把自己镜头的画面固定成选的比例，按屏幕大小居中，两边或上下留黑边。")
        card.row("死后观战", ui.Label("W / A 上一位；S / D 下一位", font=ui.f_zh(9), fg=ui.MUTED),
                 help="阵亡后镜头停 2 秒，再自动看活着的队友；键盘 W / A 换上一位，S / D 换下一位。"
                      "被增援回来后回到自己。")

        info = ui.Card(self.view, "STATUS", "状态", fill=ui.YELLOW)
        self.status = info.add(ui.text(info.body, "", bold=True, size=10))
        info.add(ui.text(info.body, "请勿同时开启CameraCTRL.exe", muted=True, size=9), top=10)
        self.view.row(card)
        self.view.row(info)
        self.app.after(POLL_MS, self._tick)

    def _toggle(self, card, var, title, sub, help_text):
        t = ui.Toggle(None, var, command=self._changed)
        self.controls.append(t)
        card.row(title, t, sub=sub, help=help_text)
        return t

    def _changed(self):
        if not self.v_view.get() and self.v_free.get():
            self.v_free.set(False)
        mask = (1 if self.v_view.get() else 0) | (2 if self.v_view.get() and self.v_free.get() else 0) \
            | (4 if self.v_spawn.get() else 0)
        try:
            save_settings(mask, SPAWN_MULT, SPAWN_MULT, int(self.v_ratio.get()))
        except OSError as e:
            self.app.say(T("分屏设置保存失败：{0}", e), "err")
            return
        self.app.say("分屏设置已保存，游戏内立即生效。" if self.app.state["running"] else "分屏设置已保存，下次进游戏生效。", "ok")
        self.sync()

    def _tick(self):
        if self.app.current is self:
            self._show_status()
        self.app.after(POLL_MS, self._tick)

    def _show_status(self):
        if not build.camera_enabled():
            self.status.config(text="这个版本未安装分屏模块。", fg=ui.BAD)
            return
        if not self.app.mod_on():
            self.status.config(text="「核心」未开启（请在「关于」页开启）。", fg=ui.WARN)
            return
        online, text = read_status()
        if not self.app.state["running"]:
            self.status.config(text="游戏未运行。", fg=ui.MUTED)
        elif not online:
            self.status.config(text="等游戏里的分屏模块回话……\n（刚装完要重开一次游戏）", fg=ui.WARN)
        else:
            self.status.config(text=text, fg=ui.INK)

    def on_show(self):
        self._show_status()

    def sync(self):
        live = self.app.mod_on() and not self.app.busy and build.camera_enabled()
        for w in self.controls:
            w.set_enabled(live)
        self.t_free.set_enabled(live and bool(self.v_view.get()))
        self.seg_ratio.set_enabled(live and bool(self.v_view.get()))
        self._show_status()
