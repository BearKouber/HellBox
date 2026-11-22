"""分屏：HalfSugar 写的 CameraCTRL（作者同意收进 HellBox，2026-11-14）。

- 装：分屏模块和我们的脚本 MOD 改同一个游戏文件，build.py 编完我们的脚本后用它的程序叠进去，跟着右上角 MOD 总开关一起装 / 还原。
- 控制：原来要一直开着 CameraCTRL.exe 发信号（5 秒没信号游戏里就自动关分屏）。现在游戏里的 mod/src/camera_link.lua
  每秒自己发，设置从这一页存的 hellbox-split.txt 读，所以不用开着 HellBox；开着时改设置，下一秒游戏里就变。
- 状态：读分屏模块写的 control-status.txt（格式照 CameraCTRL 的 lib.rs）。
- 出怪倍率固定 4，不给选（2026-11-14 用户定）。作者的倍率 x 是"最多几份"的封顶（encounters.lua multipliers）：
  每个分开的区域刷 max(1, x÷4) 份，全场 min(x, 区域数 × 每区份数)。x = 4 时就是"几个人分开就几倍、同屏按原版"，
  HD1 最多 4 人，所以 4 = 不封顶。每个区域的上限 = 出怪设置的怪物上限，全场最多 上限 × 4（64×4）。
"""
import os

import build
import ui
from pages.base import Page
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

DIR = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "camera_ctrl_v1")
SETTINGS = os.path.join(DIR, "hellbox-split.txt")
STATUS = os.path.join(DIR, "control-status.txt")
SPAWN_MULT = 4  # 增援、巡逻都按"分开几个人就几份"，见上面
POLL_MS = 1000
# 个人画面比例（2026-11-19 半糖新版分屏的「个人视口比例」，照作者 view.rs 的 CHOICES，数值 = 宽高比 × 1000，0 = 跟随游戏）。
# 只改自己镜头的可视区域、按比例留黑边，不改队友的公共边界；存进 hellbox-split.txt 第 5 行，camera_link.lua 照作者格式加 VIEW 行。
RATIOS = [("0", "跟随游戏"), ("1778", "16:9"), ("1600", "16:10"), ("1333", "4:3"), ("1250", "5:4")]
RATIO_OK = {int(v) for v, _ in RATIOS}

CAMERA_TEXT = {
    # 2026-11-15 换成作者 2.0 的死后观战：死后镜头停 2 秒，再看活着的队友；键盘 W/A 上一位、S/D 下一位
    "spectator_wait": "你阵亡了，镜头停 2 秒后看队友。",
    "spectator_follow": "正在看队友（W / A 上一位，S / D 下一位）。",
    "spectator_no_teammate": "没有活着的队友，镜头停在原地，等增援。",
    "off": "分屏没开。",
    "menu": "已连上，等进任务。",
    "local_ready_peer_unverified": "分屏已生效。",
    "return_to_team": "要先走回队伍画面里，才能还原。",
    "vehicle_return_to_team": "载具要先开回队伍画面里，才能还原。",
    "vehicle_unlocked": "载具能开出画面（车上的人都开了位置限制）。",
    "vehicle_team_boundary": "载具还在队伍画面里（车上有人没开解除位置限制）。",
    "vehicle_public_passenger": "载具跟着队伍画面（车上有人没开分屏）。",
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
    """(掩码, 增援倍率, 巡逻倍率, 画面比例)。第 5 行画面比例是新版分屏才有的，旧文件没有就按 0。"""
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
    """(是否在线, 中文说明)。游戏 5 秒内写过才算在线。"""
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
    when = "不用开着 HellBox，游戏里自己生效　只支持本机 1 个玩家"

    def build(self):
        mask, _enc, _pat, ratio = load_settings()
        self.v_view = ui.Var(mask & 1 == 1)
        self.v_free = ui.Var(mask & 3 == 3)
        self.v_spawn = ui.Var(mask & 4 == 4)
        self.v_ratio = ui.Var(str(ratio))
        self.controls = []
        # 2026-11-15 新界面：一行一个开关，说明放底栏；鸣谢 HalfSugar 挪进「关于」
        # 2026-11-19 用户要求功能来源标在对应功能下面：分屏整页都是半糖（HalfSugar）的 CameraCTRL
        card = ui.Card(self.view, "SPLIT", "分屏", fill=ui.MINT, note="来自 CameraCTRL")
        self.t_view = self._toggle(card, self.v_view, "解除视角限制", "镜头只跟着自己",
                                   "镜头不再框住全队，只跟着你。队友也装了 HellBox 并开了分屏，才能各自走开。")
        self.t_free = self._toggle(card, self.v_free, "解除位置限制", "能走出队伍画面（要先开上一个）",
                                   "能走出全队的画面范围。要先开「解除视角限制」。在远处关掉分屏，要先走回队伍画面里才会还原。")
        self.t_spawn = self._toggle(card, self.v_spawn, "房主刷怪区域扩展", "走开的人附近各刷一份怪",
                                    "同一个画面里按原版出怪；有人走开，他那边单独刷一份，分开几个人就是几倍。每个人那边的上限照"
                                    "「数据」页的场上上限，设 64、4 个人分开就是最多 64×4 只（测试中，太多可能卡）。只在你当房主时生效。")
        self.seg_ratio = ui.Segmented(None, RATIOS, self.v_ratio, command=lambda _v: self._changed(), padx=8, pady=3)
        self.controls.append(self.seg_ratio)
        card.row("画面比例", self.seg_ratio, sub="只改自己的镜头，多出的地方留黑边",
                 help="开了「解除视角限制」才生效。把自己镜头的画面固定成选的比例，按屏幕大小居中，两边或上下留黑边；"
                      "不改分辨率、不拉伸画面，也不改队友那边的画面范围。「跟随游戏」就是原来的样子。")
        card.row("死后观战", ui.Label("W / A 上一位　S / D 下一位", font=ui.f_zh(9), fg=ui.MUTED),
                 help="阵亡后镜头停 2 秒，再自动看活着的队友；键盘 W / A 换上一位，S / D 换下一位（打字聊天时不换）。"
                      "被增援回来后回到自己。队友不用装分屏。")

        info = ui.Card(self.view, "STATUS", "状态", fill=ui.YELLOW)
        self.status = info.add(ui.text(info.body, "", bold=True, size=10))
        info.add(ui.text(info.body, "别同时开 CameraCTRL.exe，两边会抢。", muted=True, size=9), top=10)
        # 2026-11-19 多了「画面比例」一排五格，分屏卡要整行宽；状态卡挪到下面
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
            self.v_free.set(False)  # 位置解锁要先有独立视角
        mask = (1 if self.v_view.get() else 0) | (2 if self.v_view.get() and self.v_free.get() else 0) \
            | (4 if self.v_spawn.get() else 0)
        try:
            save_settings(mask, SPAWN_MULT, SPAWN_MULT, int(self.v_ratio.get()))
        except OSError as e:
            self.app.say(T('分屏设置没存上：{0}', e), "err")
            return
        self.app.say("分屏设置已保存，游戏里下一秒生效。" if self.app.state["running"] else "分屏设置已保存，下次进游戏生效。", "ok")
        self.sync()

    def _tick(self):
        if self.app.current is self:
            self._show_status()
        self.app.after(POLL_MS, self._tick)

    def _show_status(self):
        if not build.camera_enabled():
            self.status.config(text="这个版本没带分屏模块。", fg=ui.BAD)
            return
        if not self.app.mod_on():
            self.status.config(text="「核心」没开（在「关于」里打开）。", fg=ui.WARN)
            return
        online, text = read_status()
        if not self.app.state["running"]:
            self.status.config(text="游戏没开。", fg=ui.MUTED)
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
