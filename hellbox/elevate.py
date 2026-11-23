"""以管理员身份重启（High 完整性级别）。

为什么需要：游戏由 Steam 以管理员启动时是 High，HellBox 从资源管理器 / 托盘启动是 Medium。
实测（2026-11-23）：Medium 进程连游戏的可写句柄都拿不到（PROCESS_VM_WRITE / PROCESS_VM_OPERATION
都 Errno 5），热改名和角色页写设置全都要跟游戏同级。

判据不用 TokenElevationType / IsUserAnAdmin：这台机器关了 UAC，两个信号都会说谎
（1.07 那次无限重启就是栽在 IsUserAnAdmin 上）。这里直接试一次游戏的写句柄 —— 打不开才提权。
"""
import ctypes
import os
import shutil
import sys

from ctypes import wintypes

FLAG = "--as-admin"  # 提权过就带上，防来回重启
_tried = False


def _frozen():
    return bool(getattr(sys, "frozen", False))


def _internal_dir():
    from_dir = getattr(sys, "_MEIPASS", None)
    if from_dir and os.path.isdir(from_dir):
        return from_dir
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    cand = os.path.join(exe_dir, "_internal")
    return cand if _frozen() and os.path.isdir(cand) else None


def _copy_internal():
    """把 _internal 挪一份到 %LOCALAPPDATA%/HellBox：提权后的实例写日志 / 备份不会撞权限。"""
    src = _internal_dir()
    if not src:
        return None
    dst = os.path.join(os.environ.get("LOCALAPPDATA", os.path.dirname(src)), "HellBox", "_internal")
    if os.path.abspath(dst).lower() == os.path.abspath(src).lower():
        return src
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return dst
    except OSError:
        return src


def needs_admin():
    """游戏开着、又打不开它的写句柄 -> 需要提权。游戏没开就不需要。"""
    try:
        import room_name_live
    except ImportError:
        return False
    try:
        pid = room_name_live.find_pid()
        if not pid:
            return False
        h = room_name_live.k32.OpenProcess(
            room_name_live.PROCESS_VM_READ | room_name_live.PROCESS_VM_WRITE
            | room_name_live.PROCESS_VM_OPERATION | room_name_live.PROCESS_QUERY_INFORMATION, False, pid)
        if h:
            room_name_live.k32.CloseHandle(h)
            return False
        return True
    except (OSError, AttributeError):
        return False


def _command(argv):
    """返回 (exe, 参数串, 工作目录)。"""
    if _frozen():
        exe = os.path.abspath(sys.executable)
        args = list(argv)
        return exe, args, os.path.dirname(exe)
    exe = os.path.abspath(sys.executable)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    return exe, [script, *argv], os.path.dirname(script)


def relaunch(argv=None):
    """以管理员身份重启当前程序；用户点了"否"返回 False。

    调用方要在提权成功启动后退出当前进程（这里不退出，方便测试）。
    """
    global _tried
    argv = [a for a in (sys.argv[1:] if argv is None else argv) if a != FLAG] + [FLAG]
    exe, args, workdir = _command(argv)
    params = " ".join('"%s"' % a if " " in a else a for a in args)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    shell32.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                      wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
    env = os.environ
    old = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(p for p in (_copy_internal(), old) if p)
    try:
        res = shell32.ShellExecuteW(None, "runas", exe, params, workdir, 1)
        _tried = True
        return bool(res) and int(res) > 32
    finally:
        if old is None:
            env.pop("PYTHONPATH", None)
        else:
            env["PYTHONPATH"] = old


def ensure_admin():
    """需要提权就重启自己并退出；不需要 / 已被拒绝过返回。"""
    if sys.platform != "win32" or FLAG in sys.argv or _tried:
        return
    if not needs_admin():
        return
    if relaunch(sys.argv[1:]):
        sys.exit(0)
    import logbook
    logbook.warn("HellBox", "没有以管理员身份运行：游戏开着时热改名字 / 角色设置会失败。")
