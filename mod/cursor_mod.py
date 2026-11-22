r"""瞄准指针 mod：颜色、不透明度、去掉渐变。界面在 gui_cursor.pyw（根目录「瞄准指针.bat」）。

两部分：
  1. 指针贴图（cursor_patch 只改动到的那几块）：
     局内 14 张（十字 / 不瞄准光斑 / 5 张过渡帧，大小两套），换成所选颜色，
     每张最不透明处统一拉到所选不透明度。"全部用十字"时光斑和过渡帧都换成十字，彻底没有渐变。
     菜单 / 设置界面的箭头（menu、menu_64）保持原版样子，只换色。
     涉及两个 bundle（见 cursor_patch.BUNDLES），各自备份到 backup\、生成到 out\。
  2. 脚本（随 build.py 的脚本 mod 一起装，src/cursor_color.lua）：
     松开瞄准后飘回角色的小十字是脚本画的（原版白色、边飞边变淡），换成同一个颜色、固定不透明度。
     脚本 mod 没装时这一步跳过，小十字保持原版。

2026-11-20 HD1-036（用户定：和 Obsidian 能同时装）：贴图部分不再整份替换游戏文件，改成每个 bundle 旁边一个补丁
  <bundle>.patch_N，只含这几张指针贴图（见 patch_files.py）；游戏原文件保持原版，也不再需要 353MB 的原版备份
  （已经有的备份留着，老装法装过的用户靠它换回原版文件）。

用法：python cursor_mod.py [status|build|install|restore]
"""
import base64
import json
import os
import shutil

import cursor_patch as cp
import texture
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "cursor_settings.json")
ORIG_CACHE = os.path.join(HERE, "backup", "cursor_originals.json")  # 16 张原版指针的小缓存
STATE_FILE = os.path.join(HERE, "backup", "cursor_state.json")      # 上次装 / 还原后游戏文件的大小和修改时间
STATE_VERSION = 3  # 2026-11-14：旧记录可能把别的 HellBox 装的指针记成「原版」，不再信；2026-11-20 v3：记录里加上补丁文件
# 原版贴图文件的指纹（2026-11-14，取自第一次装指针前备份的原版）。没有备份时靠它判断游戏里是不是原版，
# 不再「没备份 = 原版」：别的 HellBox 装过的指针会被当成原版备份下来，以后「恢复原版」就恢复错了。
VANILLA_SHA256 = {
    "750d99512279ecd0": "53af84f0424016ec51fee1cd39f929008d542f135966edcd7768c05fba52581c",
    "95b2365a6369ee36": "3df815b6b005ff4732c3f923de28e193f1e8cf7ff2493b76c6718b8799062649",
}
# 原版备份放在所有 HellBox 共用的地方（和脚本备份同一个文件夹，build.SHARED_BACKUP 旁边）
SHARED_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Arrowhead", "Helldivers", "hellbox", "backup")
_hash_cache = {}

PRESETS = {
    "荧光绿": (60, 255, 60),
    "亮红": (255, 40, 40),
    "品红": (255, 40, 220),
    "青色": (0, 230, 255),
    "亮黄": (255, 235, 0),
    "亮橙": (255, 140, 0),
}

DEFAULTS = {
    "on": False,
    "color": [60, 255, 60],
    "opacity": 100,     # 30~100（%）
    "mode": "keep",     # cross = 全部用瞄准十字（没有渐变）；keep = 保留原来的光斑和过渡帧（发行版固定 keep，界面不给选）
    "outline": False,   # 黑描边（2026-11-14 用户定：默认关）
}

_cache = None  # {资源名: (宽, 高, 头, 像素)}，原版


def backup_path(bundle):
    return os.path.join(SHARED_DIR, bundle)


def _legacy_backup(bundle):
    return os.path.join(HERE, "backup", bundle)  # 2026-11-14 以前每份 HellBox 各存各的


def is_vanilla(path, bundle):
    """这个文件是不是原版（算一次 sha256，353MB 约一两秒；按大小 + 修改时间记住结果）。"""
    try:
        st = os.stat(path)
    except OSError:
        return False
    key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    if key not in _hash_cache:
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                h.update(chunk)
        _hash_cache[key] = h.hexdigest() == VANILLA_SHA256.get(bundle)
    return _hash_cache[key]


def ensure_backup(bundle):
    """保证共用的原版备份在：没有就从旧的本地备份或游戏里拿，但只拿核对过是原版的。返回备份在不在。"""
    import build as script_build
    dst = backup_path(bundle)
    if os.path.exists(dst):
        return True
    for src in (_legacy_backup(bundle), game_bundle_path(bundle)):
        if os.path.exists(src) and is_vanilla(src, bundle):
            os.makedirs(SHARED_DIR, exist_ok=True)
            script_build.safe_copy(src, dst)
            return True
    return False


def has_vanilla_backup():
    try:
        return all(ensure_backup(b) for b in cp.BUNDLES)
    except (OSError, RuntimeError):
        return False


def out_path(bundle):
    """编好的补丁（2026-11-20 起是补丁，不再是整份 bundle）。"""
    return os.path.join(HERE, "out", bundle + ".patch")


def contents_dir():
    import build
    return os.path.join(build.game_dir(), "contents")


def load():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG, encoding="utf-8") as f:
            saved = json.load(f)
        for k in DEFAULTS:
            if k in saved:
                cfg[k] = saved[k]
    except (OSError, ValueError):
        pass
    cfg["color"] = [max(0, min(255, int(x))) for x in cfg["color"]][:3]
    cfg["opacity"] = max(30, min(100, int(cfg["opacity"])))
    cfg["mode"] = "keep"  # 2026-11-13 用户定：去掉「样子」选项，一律保留原来的样子
    cfg["on"] = bool(cfg["on"])
    cfg["outline"] = bool(cfg["outline"])
    return cfg


def save(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump({k: cfg[k] for k in DEFAULTS}, f, ensure_ascii=False, indent=2)


def lua_setting():
    """给 build.py 填进 src/cursor_color.lua：开着 = "r,g,b,a"，关着 = ""（原版白色渐变）。"""
    cfg = load()
    if not cfg["on"]:
        return ""
    r, g, b = cfg["color"]
    return f"{r},{g},{b},{round(cfg['opacity'] * 255 / 100)}"


def game_bundle_path(bundle):
    import build  # 复用现成的游戏目录定位
    return os.path.join(build.game_dir(), "contents", bundle)


def _source_bundle(bundle):
    """原版数据：游戏里的是原版就用它（2026-11-20 补丁装法下一般都是），否则用核对过的备份。"""
    path = game_bundle_path(bundle)
    if not os.path.exists(path):
        raise RuntimeError("没找到游戏的贴图文件，请确认游戏装好且没在更新。")
    if is_vanilla(path, bundle):
        return path
    for p in (backup_path(bundle), _legacy_backup(bundle)):
        if os.path.exists(p) and is_vanilla(p, bundle):
            return p
    raise RuntimeError(NOT_VANILLA)


def _read_original_blobs(bundle, names):
    """从原版 bundle 里抠出这些指针贴图的原始字节。要读整个文件、解压（大 bundle 353MB，内存会冲到 1GB 左右）。"""
    with open(_source_bundle(bundle), "rb") as f:
        data = f.read()
    raw, blocks, _size = cp.decompress_all(data)
    found = cp.find_textures(raw, names)
    del raw
    return {n: cp.read_texture(data, blocks, *found[n]) for n in names}


def _read_originals(bundle, names):
    return {n: texture.parse(b) for n, b in _read_original_blobs(bundle, names).items()}


def _source_key(bundle):
    path = _source_bundle(bundle)
    st = os.stat(path)
    # "v2"：2026-11-14 起只从核对过的原版读（备份，或 2026-11-20 起核对过是原版的游戏文件）
    return ["v2", st.st_size, st.st_mtime_ns]


def load_textures():
    """16 张原版指针读进内存，之后预览全是纯计算。

    第一次要解压整个大 bundle；读完把这 16 张（约 150KB）存进 ORIG_CACHE，
    之后只要原版文件没变就直接读这份小文件，不再碰 353MB 的大文件。
    """
    global _cache
    if _cache is not None:
        return _cache
    key = _source_key(cp.CURSOR_BUNDLE)
    blobs = None
    try:
        with open(ORIG_CACHE, encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("key") == key and set(saved.get("tex", {})) >= set(cp.ALL_NAMES):
            blobs = {n: base64.b64decode(saved["tex"][n]) for n in cp.ALL_NAMES}
    except (OSError, ValueError, KeyError):
        blobs = None
    if blobs is None:
        blobs = _read_original_blobs(cp.CURSOR_BUNDLE, cp.ALL_NAMES)
        try:
            os.makedirs(os.path.dirname(ORIG_CACHE), exist_ok=True)
            with open(ORIG_CACHE, "w", encoding="utf-8") as f:
                json.dump({"key": key, "tex": {n: base64.b64encode(b).decode() for n, b in blobs.items()}}, f)
        except OSError:
            pass
    _cache = {n: texture.parse(b) for n, b in blobs.items()}
    return _cache


def ready():
    """原图是不是已经读进内存了（界面用来判断能不能画预览）。"""
    return _cache is not None


def _shape_source(cfg, name):
    """这张指针用哪张原图的形状。"全部用十字"时，局内的同尺寸都用十字；菜单箭头永远是箭头。"""
    if cfg["mode"] == "cross" and name in cp.CURSOR_NAMES:
        return "hud/cursors/game_64" if name.endswith("_64") else "hud/cursors/game"
    return name


def make_pixels(cfg, name):
    cache = load_textures()
    w, h, _header, px = cache[_shape_source(cfg, name)]
    return w, h, texture.recolor(w, h, px, tuple(cfg["color"]), cfg["opacity"] / 100.0, cfg["outline"])


def make_textures(cfg, bundle):
    """这个 bundle 里要换的贴图 → 新数据。头（尺寸、热点）用该 bundle 里那张自己的。"""
    names = cp.BUNDLES[bundle]
    own = load_textures() if bundle == cp.CURSOR_BUNDLE else _read_originals(bundle, names)
    repl = {}
    for name in names:
        w, h, header, _px = own[name]
        sw, sh, new_px = make_pixels(cfg, name)
        if (sw, sh) != (w, h):
            raise RuntimeError(T('{0} 尺寸对不上', name))
        repl[name] = texture.build(header, new_px)
    return repl


def build():
    """每个 bundle 编一个补丁：原版里这几张贴图的条目（flags、语言照抄），数据换成新颜色的。"""
    import patch_files
    from bundle import murmur64a
    cfg = load()
    outs = []
    for bundle in cp.BUNDLES:
        repl = make_textures(cfg, bundle)
        keys = {(cp.CURSOR_TEX_TYPE, murmur64a(n.encode())): n for n in repl}
        props, ents = patch_files.read_entries(_source_bundle(bundle), want=set(keys))
        if set(ents) != set(keys):
            raise RuntimeError("游戏的指针贴图找不全")
        changed = {}
        for key, (flags, vs) in ents.items():
            if len(vs) != 1 or vs[0][2] or len(vs[0][1]) != len(repl[keys[key]]):
                raise RuntimeError(T('{0} 格式对不上', keys[key]))
            changed[key] = (flags, [(vs[0][0], repl[keys[key]], 0)])
        os.makedirs(os.path.dirname(out_path(bundle)), exist_ok=True)
        with open(out_path(bundle), "wb") as f:
            f.write(patch_files.make_patch(props, changed))
        outs.append(out_path(bundle))
    return outs


NOT_VANILLA = "游戏里的指针文件被改过（不是原版），又没有原版备份。请先点「恢复原版」或用 Steam 验证游戏文件。"


def _bundle_status(bundle):
    """2026-11-20 补丁装法：原文件该是原版；我们的补丁在、读得到、是现在设置编的 → on。"""
    import patch_files
    path = game_bundle_path(bundle)
    if not os.path.exists(path):
        return "unknown"
    if not is_vanilla(path, bundle):
        # 以前整份替换装的：有原版备份就算旧版（装的时候换回原版、改用补丁）；没有就认不出
        return "old" if ensure_backup(bundle) and is_vanilla(backup_path(bundle), bundle) else "unknown"
    contents = contents_dir()
    if not patch_files.installed(contents, bundle):
        return "off"
    if load()["on"] and os.path.exists(out_path(bundle)):
        with open(out_path(bundle), "rb") as f:
            if patch_files.current(contents, bundle, data=f.read()):
                return "on"
    return "old"


def _game_stats():
    """游戏文件和它们的补丁（2026-11-20 起）的大小、修改时间：变了就不信缓存的状态。"""
    import patch_files
    out = {}
    contents = contents_dir()
    for b in cp.BUNDLES:
        p = game_bundle_path(b)
        if not os.path.exists(p):
            return None
        st = os.stat(p)
        out[b] = [st.st_size, st.st_mtime_ns]
        for slot in patch_files.slots(contents, b):
            st = os.stat(patch_files.path_of(contents, b, slot))
            out[f"{b}.patch_{slot}"] = [st.st_size, st.st_mtime_ns]
    return out


def _record(state):
    """记下现在游戏文件的大小和修改时间，下次 status() 对上了就不用逐字节比 353MB 的大文件。"""
    stats = _game_stats()
    if stats is None:
        return
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"v": STATE_VERSION, "state": state, "cfg": load() if state == "on" else None, "files": stats}, f)
    except OSError:
        pass


def status():
    """贴图部分："on" 已装当前设置 / "old" 装的是别的设置 / "off" 原版 / "unknown" 找不到文件或认不出（被别的工具改过、没有原版备份）。

    先看 STATE_FILE：游戏文件大小、修改时间都和上次记的一样，就直接用记下的结果（一眨眼）；
    对不上（游戏更新过、别的工具动过）才逐字节比，比完再记一次。
    """
    stats = _game_stats()
    if stats is None:
        return "unknown"
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        rec = None
    if rec and rec.get("v") == STATE_VERSION and rec.get("files") == stats:
        if rec.get("state") == "on":
            return "on" if rec.get("cfg") == load() else "old"
        return rec.get("state", "unknown")
    st = _slow_status()
    if st in ("on", "off"):
        _record(st)
    return st


def _slow_status():
    sts = {_bundle_status(b) for b in cp.BUNDLES}
    if "unknown" in sts:
        return "unknown"
    if len(sts) == 1:
        return sts.pop()
    return "old"


def script_mod_status():
    import build as script_build
    try:
        return script_build.status()
    except Exception:
        return "unknown"


def _apply_script_part():
    """脚本 mod 开着就重装一遍（把新颜色带进去 / 把颜色拿掉）。返回给用户看的一句话。"""
    import build as script_build
    st = script_mod_status()
    if st in ("on", "old"):
        script_build.install()
        return "飘回角色的小十字也一起改了。" if load()["on"] else "飘回角色的小十字已恢复原版。"
    return "脚本 mod 没装，飘回角色的小十字保持原版白色。"


def game_running():
    import build as script_build
    return script_build.game_running()


def install(script=True):
    """按当前设置装上（会自动打开开关）。返回说明文字。script=False：不重装脚本 mod（调用的人刚装过）。"""
    import build as script_build
    if game_running():
        raise RuntimeError("游戏正在运行，请先关闭游戏。")
    import patch_files
    cfg = load()
    cfg["on"] = True
    save(cfg)
    _back_to_vanilla_files()
    build()
    contents = contents_dir()
    for bundle in cp.BUNDLES:
        with open(out_path(bundle), "rb") as f:
            patch_files.put(contents, bundle, f.read(), "cursor", still_ok=lambda: not script_build.game_running())
    _record("on")
    return "指针和菜单箭头已改好。" + (_apply_script_part() if script else "")


def restore(keep_setting=False, script=True):
    """游戏里的指针换回原版。keep_setting=True：不动存着的设置（关「核心」时用，下次开核心照原来的设置装回去）。"""
    import build as script_build
    if game_running():
        raise RuntimeError("游戏正在运行，请先关闭游戏。")
    if not keep_setting:
        cfg = load()
        cfg["on"] = False
        save(cfg)
    import patch_files
    contents = contents_dir()
    for bundle in cp.BUNDLES:
        patch_files.take_out(contents, bundle, still_ok=lambda: not script_build.game_running())
    _back_to_vanilla_files()
    _record("off")
    return "指针和菜单箭头已恢复原版。" + (_apply_script_part() if script else "")


def _back_to_vanilla_files():
    """以前整份替换装过的贴图文件照原版备份换回去（2026-11-20 起改用补丁，原文件要是原版）。没备份又不是原版 → 报错。"""
    import build as script_build
    for bundle in cp.BUNDLES:
        path = game_bundle_path(bundle)
        if is_vanilla(path, bundle):
            continue
        if not (ensure_backup(bundle) and is_vanilla(backup_path(bundle), bundle)):
            raise RuntimeError(NOT_VANILLA)
        script_build.safe_copy(backup_path(bundle), path, to_game=True)


def apply_saved():
    """打开「核心」时调（2026-11-20 用户定：装核心后默认都是原版，有存过的设置就按存的）。
    以前开核心直接调 install()，它会把「指针改色」强行打开、用默认亮绿色，玩家每次都得自己去指针页恢复原版。
    现在：存的设置是开着才照它装；没存过 / 存的是关着 → 游戏里的指针保持（换回）原版，存的设置不动。
    脚本 mod 由调用的人先装好（build.install 编 cursor_color.lua 时就按存的设置），这里不再重装。"""
    if load()["on"]:
        return install(script=False)
    return restore(keep_setting=True, script=False)


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "build":
        print("已生成", build())
    elif cmd == "install":
        print(install())
    elif cmd == "restore":
        print(restore())
    else:
        print("贴图：", status(), " 脚本 mod：", script_mod_status())
