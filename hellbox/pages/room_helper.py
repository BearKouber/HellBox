"""权限不够时用的代写：HellBox 是 Medium（托盘 / 资源管理器启动）、游戏是 High（Steam 以管理员运行）时，
OpenProcess 拿写权限必然 ERROR_ACCESS_DENIED —— 高完整级别进程的句柄表不许中级进程打开可写句柄。
这时用 runas /trustlevel:0x20000 起一个中等级别的 helper 进程，它在游戏启动时的条件下能读内存找表、写名字。

    live_set(name, room_name_live.MAGIC)   # 用法同 room_name_live.live_set
"""
import os
import subprocess
import sys
import tempfile

NO_WINDOW = 0x08000000


def _root():
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return here if os.path.isdir(os.path.join(here, "mod")) else os.getcwd()


def _name_of(magic):
    import room_name_live
    for k in sorted(dir(room_name_live)):
        if k.startswith("MAGIC") and getattr(room_name_live, k) == magic:
            return k
    raise RuntimeError("不认识的表")


def _script(text, magic):
    lines = ["import sys", "sys.path.insert(0, %r)" % os.path.join(_root(), "mod"),
             "import room_name_live", "room_name_live.live_set(%r, magic=room_name_live.%s)" % (text, _name_of(magic))]
    fd, path = tempfile.mkstemp(prefix="hb_helper_", suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def live_set(text, magic, timeout=20.0):
    """返回 None 表示已经写进游戏；失败抛 RuntimeError（人话）。"""
    script = _script(text, magic)
    fd, out = tempfile.mkstemp(prefix="hb_helper_", suffix=".log")
    os.close(fd)
    try:
        with open(out, "w", encoding="utf-8") as log:
            subprocess.run(["cmd", "/c", "runas", "/trustlevel:0x20000",
                            '"%s" -I "%s"' % (sys.executable, script)],
                           stdout=log, stderr=subprocess.STDOUT, text=True, timeout=timeout,
                           creationflags=NO_WINDOW)
        log.flush() if False else None
        with open(out, encoding="utf-8", errors="replace") as f:
            result = f.read().strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("改名字超时了，再试一次。")
    finally:
        for path in (script, out):
            try:
                os.unlink(path)
            except OSError:
                pass
    if result:
        raise RuntimeError(result.splitlines()[-1])
    return None
