"""
训练关：通过 Steam 启动一局手动训练任务，并把地图、出怪设置写进游戏。
"""
import os
import subprocess
import time
from pathlib import Path

import build
import drill_spec
from room_name_live import MAGIC_DRILL, MAGIC_SPAWN, find_pid, live_set

LOADOUT_FLAG = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox", "training-loadout.txt")


def mark_loadout():
    os.makedirs(os.path.dirname(LOADOUT_FLAG), exist_ok=True)
    with open(LOADOUT_FLAG, "w", encoding="ascii") as f:
        f.write(str(int(time.time())))


HB_DIR = os.path.dirname(LOADOUT_FLAG)
START_REQ = os.path.join(HB_DIR, "start-training.txt")
START_RES = os.path.join(HB_DIR, "start-training-result.txt")
START_WAIT = 6
PLAY_SETTLE = 1.5
START_RESULTS = {
    "not_ship": "游戏现在不在飞船上（在任务里、结算或主菜单）。进入飞船后再点击，或者退出游戏后点击「开始」。",
    "not_host": "你在别人的房间里，只有房主能开。",
    "teammates": "房间里有联机队友，游戏里的 MOD 是旧版，设不了下一局。请退出游戏后再点击「开始」（会先更新 MOD）。",
    "busy": "飞船正在出发（出发舱倒计时 / 任务简报 / 选装备），等这一步结束或取消后再点。",
    "bad": "地图编号不对，游戏没认。",
    "error": "游戏内进入关卡时出错，可以到「日志」页查看游戏报错。",
}


def start_in_game(cfg, drop_play_trial=None):
    import uuid
    dropped = bool(drop_play_trial and drop_play_trial())
    if dropped:
        time.sleep(PLAY_SETTLE)
    os.makedirs(HB_DIR, exist_ok=True)
    rid = uuid.uuid4().hex[:12]
    try:
        os.remove(START_RES)
    except OSError:
        pass
    mark_loadout()
    tmp = START_REQ + ".tmp"
    with open(tmp, "w", encoding="ascii") as f:
        f.write(f"HBSTART1\nid={rid}\ntime={int(time.time())}\nseed={int(cfg['seed'])}\nmode=auto\n")
    os.replace(tmp, START_REQ)
    end = time.monotonic() + START_WAIT
    result = None
    while time.monotonic() < end:
        try:
            with open(START_RES, encoding="ascii") as f:
                got = dict(line.split("=", 1) for line in f.read().splitlines() if "=" in line)
        except OSError:
            got = {}
        if got.get("id") == rid:
            result = got.get("result")
            break
        time.sleep(0.25)
    if result != "ok":
        for path in (START_REQ, LOADOUT_FLAG):
            try:
                os.remove(path)
            except OSError:
                pass
    if result is None:
        raise RuntimeError("游戏无响应。可能游戏里还是旧版 MOD，或者正卡在加载。退出游戏后再点击「开始」也能进。")
    extra = "（「玩法」页设的试验场下一局已取消。）" if dropped else ""
    if result == "armed":
        return ("已设为下一局：房间里有队友，照常走进出发舱出发就是这张图，队友无需安装 HellBox，大家照常获得经验。打完回飞船，原来的星球自动放回去；想换回原来的任务，在星图上选别的星球就行。" + extra)
    if result != "ok":
        raise RuntimeError(START_RESULTS.get(result, result))
    return "已进关：先选战略配备，再落地。" + extra


def _steam():
    steam = next((Path(root) / "steam.exe" for root in build.steam_roots()
                  if (Path(root) / "steam.exe").is_file()), None)
    if steam is None:
        raise RuntimeError("找不到 Steam。")
    return steam


def launch_online(cfg, drop_play_trial=None):
    """2026-11-22 用户定：游戏关着时点「开始」也要在线。正常开游戏（不带 -autohost，那样游戏会进离线），
    同时写一个带 wait=1 的请求：游戏进到飞船后自己开这张图（mod/src/hellbox_start.lua，10 分钟内有效）。"""
    import uuid
    if drop_play_trial:
        drop_play_trial()
    steam = _steam()
    os.makedirs(HB_DIR, exist_ok=True)
    try:
        os.remove(START_RES)
    except OSError:
        pass
    mark_loadout()
    tmp = START_REQ + ".tmp"
    with open(tmp, "w", encoding="ascii") as f:
        f.write(f"HBSTART1\nid={uuid.uuid4().hex[:12]}\ntime={int(time.time())}\nseed={int(cfg['seed'])}\nmode=auto\nwait=1\n")
    os.replace(tmp, START_REQ)
    subprocess.Popen([str(steam), "-applaunch", build.STEAM_APP_ID],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def launch(cfg, preset=None):
    steam = _steam()
    args = drill_spec.game_args(cfg)
    mark_loadout()
    subprocess.Popen([str(steam), "-applaunch", build.STEAM_APP_ID, *args],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cmd = preset or drill_spec.drill_command(cfg)
    magic = MAGIC_SPAWN if preset else MAGIC_DRILL
    if not cmd:
        return
    end = time.monotonic() + 55
    seen = False
    while time.monotonic() < end:
        pid = find_pid()
        if seen and not pid:
            raise RuntimeError("游戏启动过程中退出了（可能闪退），出怪设置没写进去。可以到「日志」页看游戏报错。")
        seen = seen or bool(pid)
        if pid:
            try:
                live_set(cmd, pid=pid, magic=magic, timeout=1)
                return
            except (OSError, RuntimeError):
                pass
        time.sleep(0.5)
    raise RuntimeError("游戏未确认出怪设置。请退出本局后检查脚本 MOD 是否已更新。")
