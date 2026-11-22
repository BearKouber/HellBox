"""日志本（2026-11-14 用户要求：记录 HellBox 和游戏的报错 / 警告，出问题时好查、好发给别人看）。

三个来源，「日志」页合在一起按时间倒序显示：
- HellBox：hellbox/logs/hellbox.log。底部状态栏的报错 / 警告、后台任务失败（带出错位置）、没接住的异常、Qt 的警告。
- 游戏脚本：hellbox/logs/game.log。我们装进游戏的脚本出错时写（mod/src/hb_log.lua 的 HellBoxLog）。
- 游戏崩溃：游戏自己写的 %APPDATA%/Arrowhead/Helldivers/crash/CRASH_*.txt（只读，不动它们）。
- 闪退探针（2026-11-19）：游戏这边一直写 hellbox/logs/game-probe.txt（现在在干什么，mod/src/hb_probe.lua）。
  游戏没在运行、文件里没有正常退出的记号 → 上次多半是闪退（游戏有时闪退不留 CRASH 报告），check_probe 把最后几步写进 HellBox 日志。
每行格式：时间<TAB>级别<TAB>来源<TAB>内容。文件超过 512KB 就把旧的改名 .1 重新开始。
"""
import os
import sys
import threading
import time
import traceback

ROOT = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers")
DIR = os.path.join(ROOT, "hellbox", "logs")
HELLBOX_LOG = os.path.join(DIR, "hellbox.log")
GAME_LOG = os.path.join(DIR, "game.log")
CRASH_DIR = os.path.join(ROOT, "crash")
MAX_BYTES = 512 * 1024
PROBE = os.path.join(DIR, "game-probe.txt")
CLEARED = os.path.join(DIR, "cleared-before.txt")  # 「清空」时记下时间，早于它的崩溃报告不再显示（不删游戏的文件）

_lock = threading.Lock()


def _clean(text):
    return " | ".join(line.strip() for line in str(text).replace("\t", " ").splitlines() if line.strip())


def write(level, source, text):
    """追加一行。写不进去就算了，不能因为记日志把 HellBox 弄崩。"""
    try:
        with _lock:
            os.makedirs(DIR, exist_ok=True)
            if os.path.exists(HELLBOX_LOG) and os.path.getsize(HELLBOX_LOG) > MAX_BYTES:
                os.replace(HELLBOX_LOG, HELLBOX_LOG + ".1")
            with open(HELLBOX_LOG, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{level}\t{source}\t{_clean(text)}\n")
    except OSError:
        pass


def error(source, text):
    write("ERROR", source, text)


def warn(source, text):
    write("WARN", source, text)


def exception(source, exc):
    """异常带上出错位置（最后几层调用），方便定位。"""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)[-4:])
    write("ERROR", source, f"{exc}  ||  {tb}")


def install():
    """接住没人处理的异常和 Qt 警告，都记进日志（原来的处理照旧）。"""
    os.makedirs(DIR, exist_ok=True)
    old_hook = sys.excepthook

    def hook(kind, exc, tb):
        write("ERROR", "HellBox", "".join(traceback.format_exception(kind, exc, tb)[-6:]))
        old_hook(kind, exc, tb)

    sys.excepthook = hook

    def thread_hook(args):
        write("ERROR", "HellBox 后台", "".join(traceback.format_exception(args.exc_type, args.exc_value,
                                                                       args.exc_traceback)[-6:]))

    threading.excepthook = thread_hook
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler

        def qt_handler(kind, _ctx, msg):
            if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                write("WARN" if kind == QtMsgType.QtWarningMsg else "ERROR", "Qt", msg)

        qInstallMessageHandler(qt_handler)
    except ImportError:
        pass


# ------------------------------------------------------------ 读（「日志」页用）
def _read_lines(path, source_default):
    out = []
    for p in (path + ".1", path):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t", 3)
                    if len(parts) == 4:
                        out.append({"time": parts[0], "level": parts[1], "source": parts[2] or source_default,
                                    "text": parts[3], "origin": source_default})
        except OSError:
            pass
    return out


def _cleared_before():
    try:
        with open(CLEARED, encoding="ascii") as f:
            return float(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0.0


def _crashes(limit=20):
    out = []
    since = _cleared_before()
    try:
        names = [n for n in os.listdir(CRASH_DIR) if n.startswith("CRASH_") and n.endswith(".txt")]
    except OSError:
        return out
    paths = sorted((os.path.join(CRASH_DIR, n) for n in names), key=os.path.getmtime, reverse=True)[:limit]
    for p in paths:
        mtime = os.path.getmtime(p)
        if mtime < since:
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                body = f.read(4000)
        except OSError:
            continue
        # 第一行是错误本身，后面 stack traceback 的 [n] 行是出错时在哪（游戏的崩溃报告格式，2026-11-07 那批看过）
        keep = [ln.strip() for ln in body.splitlines() if ln.strip()]
        frames = [ln.split("]", 1)[1].strip() for ln in keep if ln.startswith("[")][:4]
        summary = (keep[0] if keep else "") + ("  ←  " + "  ←  ".join(frames) if frames else "")
        out.append({"time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)), "level": "CRASH",
                    "source": "游戏崩溃", "text": f"{summary}  （{os.path.basename(p)}）", "origin": "crash", "path": p})
    return out


def check_probe():
    """游戏不在运行时调：上次游戏没有正常退出、还没报过 → 写一条 ERROR（最后心跳、当时在干什么、最后几步），
    在探针文件末尾补 reported=1（同一次只报一次），返回一句给底栏的话；没事返回 None。"""
    try:
        with open(PROBE, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    if not text.startswith("HBPROBE1") or "\nexit=clean" in text or "\nreported=1" in text:
        return None
    head, _, tail = text.partition("\nevents:\n")
    kv = dict(line.split("=", 1) for line in head.splitlines()[1:] if "=" in line)
    steps = [ln.replace("\t", " ") for ln in tail.splitlines() if ln.strip() and not ln.startswith("reported=")][-8:]
    write("ERROR", "闪退探针",
          f"上次游戏（{kv.get('started', '?')} 开的）没有正常退出，可能是闪退。最后心跳 {kv.get('beat', '?')}，"
          f"当时：{kv.get('now', '?')}；最后几步：{' → '.join(steps)}")
    try:
        with open(PROBE, "a", encoding="utf-8") as f:
            f.write("reported=1\n")
    except OSError:
        pass
    return "上次游戏没有正常退出（可能闪退了），停在哪一步已记进「日志」页。"


def entries():
    """全部记录，新的在前。"""
    rows = _read_lines(HELLBOX_LOG, "HellBox") + _read_lines(GAME_LOG, "游戏脚本") + _crashes()
    rows.sort(key=lambda r: r["time"], reverse=True)
    return rows


def clear():
    """清空 HellBox 和游戏脚本的日志；游戏崩溃报告不删（是游戏的文件），只是以后不再显示现在这些。"""
    with _lock:
        for p in (HELLBOX_LOG, HELLBOX_LOG + ".1", GAME_LOG, GAME_LOG + ".1"):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.makedirs(DIR, exist_ok=True)
            with open(CLEARED, "w", encoding="ascii") as f:
                f.write(str(time.time()))
        except OSError:
            pass
