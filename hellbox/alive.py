"""
HellBox 开着的心跳（2026-11-25 用户定：HellBox 关了，影响平衡的东西马上全部按原版）。

开着时每 BEAT_SECS 秒往 %APPDATA%\\Arrowhead\\Helldivers\\hellbox\\hellbox-alive.txt 写当前时间（秒）；
正常关掉时写 0。游戏那边（mod/src/hellbox_alive.lua）看到 0、没有文件、或者 15 秒没更新（闪退 / 被强关）就当关了。
用单独的线程写，HellBox 界面忙（装 MOD、读存档）时心跳也不停。
"""

import os
import threading
import time

BEAT_SECS = 3.0
PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Arrowhead", "Helldivers", "hellbox",
                    "hellbox-alive.txt")

_stop = threading.Event()
_thread = None
keep_on_exit = False  # 以管理员身份重开自己时设成 True：新的那个马上接着写，中间不算关


def _write(value):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="ascii", newline="\n") as f:
            f.write("%d\n" % value)
        os.replace(tmp, PATH)
    except OSError:
        pass


def _loop():
    while not _stop.is_set():
        _write(int(time.time()))
        _stop.wait(BEAT_SECS)


def start():
    global _thread
    if _thread is not None:
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="hellbox-alive", daemon=True)
    _thread.start()


def stop():
    """正常关掉：停心跳、写 0，游戏下一秒就按原版。"""
    global _thread
    if _thread is None:
        return
    _stop.set()
    _thread.join(timeout=2)
    _thread = None
    if not keep_on_exit:
        _write(0)
