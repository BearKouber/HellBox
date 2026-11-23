"""
「角色」「队友」两页共用：读取游戏里 profile_tool.lua 每秒写的状态，并发送命令。
"""
import time

import build


def parse(text):
    st = {"ok": False, "why": "", "capes": [], "weapons": [], "strats": [], "perks": [], "loadout": None, "mates": []}
    for line in text.splitlines():
        key, _, rest = line.partition("=")
        if key == "L":
            st["loadout"] = (rest.split("|") + [""] * 6)[:6]
        elif key in ("C", "W", "S", "K"):
            idx, name_key, shown, status, need, kind = (rest.split("|") + [""] * 6)[:6]
            st[{"C": "capes", "W": "weapons", "S": "strats", "K": "perks"}[key]].append(
                {"index": int(idx), "key": name_key, "name": shown or name_key, "status": status, "need": need, "kind": kind})
        else:
            for part in line.split(";"):
                k, _, v = part.partition("=")
                st[k] = v
    st["raw_keys"] = tuple(k for k in ("xp", "maxlv") if k in st)
    st["ok"] = st.get("ok") == "1"
    for k in ("rp", "max", "per", "lv", "cape", "cl", "seq", "xp", "maxlv"):
        try:
            st[k] = int(float(st.get(k, 0)))
        except ValueError:
            st[k] = 0
    return st


def read():
    if not build.game_running():
        return {"ok": False, "why": "游戏未运行。", "capes": [], "weapons": [], "mates": []}
    import room_name_live
    try:
        _, text = room_name_live.live_read(room_name_live.MAGIC_PROFILE)
    except RuntimeError as e:
        return {"ok": False, "why": str(e), "capes": [], "weapons": [], "mates": []}
    st = parse(text)
    if not st["ok"] and st.get("why") == "save":
        st["why"] = "游戏还没读好存档（进到主菜单以后再看）。"
    return st


def send(cmd):
    if not build.game_running():
        raise RuntimeError("需要游戏正在运行才能修改。")
    import room_name_live
    before = read()
    if not before["ok"]:
        raise RuntimeError(before["why"] or "现在拿不到游戏状态。")
    from pages import room_helper
    try:
        room_name_live.live_set(cmd, magic=room_name_live.MAGIC_PROFILE)
    except room_name_live._Helper:
        room_helper.live_set(cmd, room_name_live.MAGIC_PROFILE)
    end = time.monotonic() + 3
    while time.monotonic() < end:
        st = read()
        res = st.get("res", "")
        if st["ok"] and st["seq"] != before["seq"] and res:
            kind, _, msg = res.partition(":")
            if kind == "err":
                raise RuntimeError(msg)
            return msg
        time.sleep(0.1)
    raise RuntimeError("游戏没有回应，稍后再试。")
