"""
录制页（2026-11-26 用户定：只在开发者模式显示；作者在开发潜兵 AI，要真人对局数据；
玩家同意后进任务自动录，录像只存在本机，玩家自己手动发，不做自动上传）。

- 后台就是 ai/recorder.py（和单独的 HD1 录制器同一套：进任务自动录、离开任务自动收、文件格式一样），
  只是不听键盘、不响；游戏里的核心靠 recorder-alive.txt 心跳醒来（mod/src/rec_gate_post.lua）。
- 找游戏进程换成 ctypes：发布版不带 pymem，ai/bridge.py 的 find_pid 用的是 pymem（bridge.py 在冻结名单里，不改它）。
- 录像放「文档\\HellBox Recordings」，换新版 HellBox 文件夹也不会丢。
- 「发给作者」= 打开录像文件夹 + 在浏览器里打开上传表单（UPLOAD_URL，Google 表单，作者填）。
- 第一次打开开发者模式时问一次要不要帮忙录（record_asked.txt 记住问过）。
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

import paths
import ui
from pages.base import Page
try:
    from i18n import T, tr
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

AI_DIR = os.path.join(paths.ROOT, "ai")
CONF = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Arrowhead", "Helldivers", "hellbox")
SETTING = os.path.join(CONF, "record.txt")          # "1" = 开着
ASKED = os.path.join(CONF, "record_asked.txt")      # 问过了
# Google 表单（2026-11-26 用户建好）：玩家登录 Google 后把录像拖进去，文件进作者的 Google 云端硬盘
UPLOAD_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfTbShoWIusLMwF212jy7lJqG-GzW9qCq0IClvBBR8lGilFmA/viewform"
STANDALONE_MUTEX = "HD1Recorder.SingleInstance"     # 单独的 HD1 录制器（ai/recorder_app.py）开着时有这个
POLL_MS = 1000
LIST_ROWS = 8

ASK_TEXT = ("作者在开发潜兵 AI（会自己打的队友），需要真人的对局数据来训练。\n\n"
            "要帮忙录吗？开着时进任务自动录，离开任务自动停。\n"
            "只录游戏里的数字（位置、血量、按键），不录画面、声音、聊天和名字。\n"
            "录像只存在你的电脑上，发不发给作者由你决定。\n\n"
            "以后可以在「录制」页随时关掉。")
WHAT_LINES = [
    "只录游戏里的数字：位置、血量、弹药、按键。不录画面、声音、聊天，也不录名字。",
    "录像只存在你的电脑上，HellBox 不会自己上传。",
    "一局大约几十 MB，长时间不发可以去文件夹里删掉。",
]
RESULT_TEXT = {"extracted": "撤离", "completed": "完成", "left": "未完成", "none": "非任务"}


# ---------------------------------------------------------------- 本机设置

def _read_flag(path):
    try:
        with open(path, encoding="ascii") as f:
            return f.read().strip() == "1"
    except (OSError, ValueError):
        return False


def _write_flag(path, on):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="ascii") as f:
            f.write("1\n" if on else "0\n")
        os.replace(tmp, path)
    except OSError:
        pass


def rec_dir():
    """「文档」文件夹（可能被挪到 D 盘或 OneDrive）里的 HellBox Recordings。"""
    buf = ctypes.create_unicode_buffer(260)
    try:
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:  # 5 = CSIDL_PERSONAL
            return os.path.join(buf.value, "HellBox Recordings")
    except (AttributeError, OSError):
        pass
    return os.path.join(os.path.expanduser("~"), "Documents", "HellBox Recordings")


def standalone_open():
    k32 = ctypes.windll.kernel32
    h = k32.OpenMutexW(0x00100000, False, STANDALONE_MUTEX)  # SYNCHRONIZE
    if h:
        k32.CloseHandle(h)
        return True
    return False


# ---------------------------------------------------------------- 找游戏进程（不用 pymem）

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def find_pid(name):
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return None
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            if e.szExeFile.lower() == name.lower():
                return e.th32ProcessID
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return None


# ---------------------------------------------------------------- 后台录制器（整个 HellBox 只有一个）

_rec = None
_thread = None


def _load():
    if AI_DIR not in sys.path:
        sys.path.insert(0, AI_DIR)
    import recorder
    recorder.find_pid = find_pid
    return recorder


def running():
    return _rec


def start():
    global _rec, _thread
    if _rec is not None:
        return _rec
    import threading
    recorder = _load()
    from blackbox import Keys
    rec = recorder.Recorder(out_dir=rec_dir(), sound=False, auto=True, core_check=lambda: "hellbox")
    rec.keys = Keys(getter=lambda _vk: False, toggle=None, save=None)  # 不听键盘：只自动录
    _rec = rec
    _thread = threading.Thread(target=rec.run, name="hellbox-recorder", daemon=True)
    _thread.start()
    return rec


def shutdown():
    """停掉后台录制器：录着的先收好再走（HellBox 关掉、关掉开关时调）。"""
    global _rec, _thread
    rec, _rec, _thread = _rec, None, None
    if rec is not None:
        rec.shutdown()


def recordings(n=LIST_ROWS):
    recorder = _load()
    return recorder.recordings(rec_dir(), n)


def total_size():
    d = rec_dir()
    try:
        return sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d) if f.endswith(".jsonl.gz"))
    except OSError:
        return 0


def clock(secs):
    secs = int(secs or 0)
    return f"{secs // 60}:{secs % 60:02d}"


def row_text(i):
    g = i.get("game") or {}
    stamp = i["file"][4:17]  # rec_20261126_210300 → 20261126_2103
    when = f"{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}" if len(stamp) >= 13 else i["file"]
    parts = [when, clock(i.get("secs")).rjust(6)]
    if g.get("difficulty") is not None:
        parts.append(T("难度 {0}", g["difficulty"]))  # 任务区里的难度本来就从 1 数（以前多加了 1）
    parts.append(tr(RESULT_TEXT.get(g.get("result"), "未正常结束" if not i.get("ok") else "非任务")))
    if g.get("local_ids"):  # 旧录像（local_slots）多人局会把全队的死算成本机的，不显示
        parts.append(T("死 {0} 次", g.get("local_deaths", 0)))
    sc = i.get("score")  # HD1-040：录完在后台算的评分（本机活着的分钟里，值得多学的有几分钟）
    if sc and "error" not in sc:
        parts.append(T("好教材 {0}/{1} 分钟", sc.get("good_min", 0), sc.get("total_min", 0)))
    elif i.get("ok") and g.get("result") is not None:
        parts.append(tr("评分中"))
    parts.append(f"{i['size'] / 1e6:.1f} MB")
    return "   ".join(parts)


class RecordPage(Page):
    key = "record"
    tab = "录制"
    when = "进任务自动录，离开任务自动停"

    def build(self):
        self.seen_seq = -1
        self.asked_now = False
        self.on = ui.Var(_read_flag(SETTING))

        main = ui.Card(self.view, "REC", "帮作者录对局", fill=ui.SALMON)
        self.toggle = ui.Toggle(None, self.on, command=self.flip)
        w, lay = ui.hbox()
        lay.addWidget(self.toggle, 0, ui.Qt.AlignmentFlag.AlignVCenter)
        lay.addSpacing(14)
        lay.addWidget(ui.text(None, "开着时进任务自动录\n作者在开发潜兵 AI，需要真人对局数据", bold=True), 1)
        main.add(w)
        self.status = main.add(ui.text(main.body, "", size=10, bold=True), top=14)
        self.sub = main.add(ui.text(main.body, "", muted=True, size=9), top=4)

        what = ui.Card(self.view, "INFO", "录了什么", fill=ui.YELLOW)
        for n, line in enumerate(WHAT_LINES):
            what.add(ui.text(what.body, "· " + tr(line), size=9), top=0 if n == 0 else 6)
        self.view.row(main, what)

        files = ui.Card(self.view, "FILES", "录像", fill=ui.SKY)
        w, lay = ui.hbox()
        self.count = ui.text(None, "", muted=True, size=9)
        lay.addWidget(self.count, 1, ui.Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(ui.Button(None, "打开文件夹", self.open_folder, padx=10, pady=3))
        files.add(w)
        self.list = files.add(ui.text(files.body, "", size=9), top=8)
        self.list.setFont(ui.f_mono(9))

        send = ui.Card(self.view, "SEND", "发给作者", fill=ui.MINT)
        send.add(ui.text(send.body, "点下面的按钮，会打开录像文件夹和上传表单，把录像拖进表单就行。"
                                    "表单要登录 Google 账号。", size=9))
        self.send_btn = send.add(ui.Button(None, "打开上传表单", self.send, kind="primary", padx=12, pady=4),
                                 top=12, align=ui.LEFT)
        self.send_hint = send.add(ui.text(send.body, "", muted=True, size=9), top=8)
        self.view.row(files, send)

        if self._should_run():
            self._start()
        self._load_list()
        self.app.after(POLL_MS, self._tick)

    # ---------- 开关 ----------

    def _should_run(self):
        """开关开着、开发者模式开着（关掉开发者模式这页就看不到了，不能在背后录）；界面自检不录。"""
        return bool(self.on.get()) and getattr(self.app, "dev", False) and "--check-ui" not in sys.argv

    def _start(self):
        if standalone_open():
            return False
        try:
            start()
        except Exception as e:
            self.app.say(T("录制没开起来：{0}", e), "err")
            return False
        return True

    def flip(self):
        on = bool(self.on.get())
        if on and not self.app.ask(ASK_TEXT):
            self.on.set(False)
            return
        _write_flag(SETTING, on)
        _write_flag(ASKED, True)
        if on:
            if self._start():
                self.app.say("录制已开启：进任务会自动录。", "ok")
            else:
                self.app.say("录制开关已打开，但现在没在录（看页面上的说明）。", "warn")
        else:
            self.app.bg(shutdown, lambda *_: self._load_list())
            self.app.say("录制已关闭。", "ok")
        self._render_status()

    def set_dev(self, on):
        # 第一次打开开发者模式时问一次（用户定：开发者模式开着就问，确定才录，可以取消）
        if on and not self.asked_now and not _read_flag(ASKED) and "--check-ui" not in sys.argv:
            self.asked_now = True
            self.app.after(600, self._first_ask)
        if not on and running() is not None:
            # 关掉开发者模式就看不到这一页了，别在背后接着录（开关记住，再打开开发者模式接着录）
            self.app.bg(shutdown)

    def _first_ask(self):
        _write_flag(ASKED, True)
        if not getattr(self.app, "dev", False) or self.on.get():
            return
        if self.app.ask(ASK_TEXT):
            self.on.set(True)
            _write_flag(SETTING, True)
            if self._start():
                self.app.say("录制已开启：进任务会自动录。可以在「录制」页关掉。", "ok")
        else:
            self.app.say("没开录制。以后想帮忙，可以在「录制」页打开。", "info")
        self._render_status()

    # ---------- 状态 ----------

    def _tick(self):
        rec = running()
        if rec is None and self._should_run() and not standalone_open():
            self._start()  # 开发者模式重新打开、单独的录制器关掉以后接上
        if self.app.current is self:
            self._render_status()
        if rec is not None and rec.saved_seq != self.seen_seq:
            self.seen_seq = rec.saved_seq
            self._load_list()
        self.app.after(POLL_MS, self._tick)

    def _render_status(self):
        rec = running()
        sub = ""
        if not self.on.get():
            text = "关着：不录。"
        elif rec is None:
            if standalone_open():
                text = "单独的 HD1 录制器开着，HellBox 这里先不录（关掉它以后自动接上）。"
            else:
                text = "开着，但还没开始工作。"
        elif not self.app.mod_on():
            text = "核心没开：要先打开核心才录得到。"
        else:
            take = rec.take
            if take is not None:
                size = take.buf.size / 1e6
                text = T("正在录：{0}，{1:.1f} MB", clock(time.time() - take.t0), size)
                sub = tr("离开任务 15 秒后自动停、存好。")
            else:
                text = {
                    "no_game": "等游戏打开。",
                    "no_table": "游戏开着，等你进任务。",
                    "version": "游戏里的 MOD 和这个 HellBox 版本对不上：关掉游戏，让 HellBox 更新以后再开。",
                    "error": "连游戏出错，几秒后自动重试。",
                    "linked": "已连上游戏，进任务就开始录。",
                }.get(rec.link, "等游戏打开。")
            tpl, args = rec.note
            if tpl and not sub:
                sub = tr("刚才：") + (T(tpl, *args) if args else tr(tpl))
        self.status.config(text=tr(text))
        self.sub.config(text=sub)

    def _load_list(self):
        def done(ok, res):
            if not ok:
                return
            rows, size = res
            if rows:
                self.list.config(text="\n".join(row_text(i) for i in rows))
            else:
                self.list.config(text=tr("还没有录像。"))
            self.count.config(text=T("共 {0:.1f} MB · {1}", size / 1e6, rec_dir()))

        self.app.bg(lambda: (recordings(), total_size()), done)

    def on_show(self):
        self._render_status()
        self._load_list()

    def sync(self):
        self.send_btn.set_enabled(bool(UPLOAD_URL))
        self.send_hint.config(text="" if UPLOAD_URL else tr("作者还没放上传链接，先不用发。"))

    # ---------- 按钮 ----------

    def open_folder(self):
        d = rec_dir()
        os.makedirs(d, exist_ok=True)
        os.startfile(d)

    def send(self):
        if not UPLOAD_URL:
            return
        import webbrowser
        self.open_folder()
        webbrowser.open(UPLOAD_URL)
