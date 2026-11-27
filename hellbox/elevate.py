"""以管理员身份重启（High 完整性级别）。

为什么需要：游戏由 Steam 以管理员启动时是 High，HellBox 从资源管理器 / 托盘启动是 Medium。
实测（2026-11-23，Oct0pu5）：Medium 进程连游戏的可写句柄都拿不到（PROCESS_VM_WRITE / PROCESS_VM_OPERATION
都 Errno 5），游戏开着时热改名、潜兵页写设置都要跟游戏同级。

判据不用 TokenElevationType / IsUserAnAdmin：关了 UAC 的机器上两个信号都会说谎
（1.07 那次无限重启就是栽在 IsUserAnAdmin 上）。这里直接试一次游戏的写句柄 —— 被拒绝（错误 5）才提权。

两个时机（2026-11-25 合并 PR #2 时补第二个）：
  - 启动时游戏已经开着：ensure_admin() 直接弹 UAC 重启（app.main）。
  - 先开 HellBox、后开游戏：App._check_admin() 在看到游戏启动时问一次要不要重启。
"""
import ctypes
import os
import sys

from ctypes import wintypes

FLAG = "--as-admin"  # 提权过就带上，防来回重启
ERROR_ACCESS_DENIED = 5
_tried = False


def _frozen():
    return bool(getattr(sys, "frozen", False))


def needs_admin():
    """游戏开着、打开它的写句柄被拒绝（错误 5）-> 需要提权。游戏没开、或别的原因打不开都不算。

    注意：打包后 room_name_live 被 --exclude-module 排在 exe 外，只存在于 <ROOT>/mod，
    而 main() 此刻 sys.path 里还没有 mod —— 所以这里自己补一次。
    """
    try:
        import room_name_live
    except ImportError:
        import paths
        if paths.MOD not in sys.path:
            sys.path.insert(0, paths.MOD)
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
        return ctypes.get_last_error() == ERROR_ACCESS_DENIED
    except (OSError, AttributeError):
        return False


def _command(argv):
    """返回 (exe, 参数列表, 工作目录)。开发版用当前 python 跑同目录的 app.py。"""
    exe = os.path.abspath(sys.executable)
    if _frozen():
        return exe, list(argv), os.path.dirname(exe)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    return exe, [script, *argv], os.path.dirname(script)


def relaunch(argv=None):
    """以管理员身份重新启动 HellBox；用户在 UAC 里点了"否"返回 False。

    调用方在返回 True 后自己退出当前进程。
    """
    global _tried
    argv = [a for a in (sys.argv[1:] if argv is None else argv) if a != FLAG] + [FLAG]
    exe, args, workdir = _command(argv)
    params = " ".join('"%s"' % a if " " in a else a for a in args)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    shell32.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                      wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
    res = shell32.ShellExecuteW(None, "runas", exe, params, workdir, 1)
    _tried = True
    return bool(res) and int(res) > 32


def ensure_admin():
    """启动时：需要提权就重启自己并退出；不需要 / 用户拒绝过就返回。"""
    if sys.platform != "win32" or FLAG in sys.argv or _tried:
        return
    if not needs_admin():
        return
    if relaunch(sys.argv[1:]):
        sys.exit(0)
    try:
        import logbook
        logbook.warn("HellBox", "没有以管理员身份运行：游戏开着时热改名字 / 角色设置会失败。")
    except OSError:
        pass


def may_ask():
    """看到游戏启动时能不能问：已经是提权后的实例、或这次启动时用户已经拒绝过 UAC，就不再问。"""
    return sys.platform == "win32" and FLAG not in sys.argv and not _tried
