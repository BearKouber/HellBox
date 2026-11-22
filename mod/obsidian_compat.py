r"""认出 Obsidian（Alomare 的 HD1 启动器 / MOD 管理器，github.com/Alomare/ObsidianLauncher）开着哪些 MOD，
HellBox 里重复的功能让出来（2026-11-20 HD1-036，用户定：和 Obsidian 能同时装、互不打架）。

怎么认：
  - Obsidian 装没装进游戏：启动包 9cf71054ea26dddf 旁边有不是我们的补丁，里面有 foundation/lua/build_date_information
    （Obsidian 的加载脚本就放在这个资源里，见它的 core/src/loader.rs）。只看到 settings.txt 不算：清除（Purge）以后它还留着。
  - 开着哪些 MOD、选项是什么：%APPDATA%\Arrowhead\Helldivers\ObsidianLauncher\settings.txt，
    每个开着的、有脚本的 MOD 每个选项一行「option<TAB>MOD id<TAB>选项<TAB>类型<TAB>值」（它的 core/src/settings.rs）。
让出什么（游戏那边看到的开关强制关，界面那一行变灰、写原因；HellBox 存的选择不动，Obsidian 那边关了就恢复）：
  - alomare.betterhud（Better HUD）开着 → HellBox「增强 HUD」（同一份 BetterHUD，开两份会画两套）。
  - alomare.customcrosshair（Custom Crosshair）的 enabled 开着 → HellBox「醒目准星」（两个准星叠在一起）。
只提醒、不替玩家关的（notes）：Eyes of Liberty（第三人称镜头）和 HellBox 分屏都改镜头；两边的补丁改了同一个资源（编号大的赢）。
"""
import os

from bundle import LUA, murmur64a

try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换（提醒是给人看的）
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

SETTINGS = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Arrowhead", "Helldivers",
                        "ObsidianLauncher", "settings.txt")
LOADER_BUNDLE = "9cf71054ea26dddf"
LOADER_RES = (LUA, murmur64a(b"foundation/lua/build_date_information"))

# HellBox 的 hop 开关 -> (Obsidian MOD id, 要看的选项或 None, MOD 名)
YIELDS = {
    # 2026-11-20 用户删了 HellBox 的增强 HUD 和醒目准星，原来让给 Better HUD / Custom Crosshair 的两项没了
}

_cache = {"key": None, "value": None}


def _contents():
    import build
    return os.path.join(build.game_dir(), "contents")


def _loader_files(contents):
    import patch_files
    mine = patch_files.load_record().get(LOADER_BUNDLE, {}).get("slot")
    return [patch_files.path_of(contents, LOADER_BUNDLE, s) for s in patch_files.slots(contents, LOADER_BUNDLE) if s != mine]


def _stamp(paths):
    out = []
    for p in paths:
        try:
            st = os.stat(p)
            out.append((p, st.st_size, st.st_mtime_ns))
        except OSError:
            out.append((p, None, None))
    return tuple(out)


def state(contents=None):
    """{"deployed": Obsidian 的加载脚本在不在游戏里, "mods": {MOD id: {选项: 值}}}。按文件大小 / 时间缓存，很快。"""
    try:
        contents = contents or _contents()
        loaders = _loader_files(contents)
    except Exception:
        return {"deployed": False, "mods": {}}
    key = _stamp(loaders + [SETTINGS])
    if _cache["key"] == key:
        return _cache["value"]
    deployed = False
    import patch_files
    for p in loaders:
        try:
            _props, ents = patch_files.read_entries(p, want={LOADER_RES})
        except Exception:
            continue
        if ents:
            deployed = True
            break
    mods = {}
    if deployed:
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\r\n").split("\t")
                    if len(parts) == 5 and parts[0] == "option":
                        mods.setdefault(parts[1], {})[parts[2]] = parts[4]
        except OSError:
            pass
    value = {"deployed": deployed, "mods": mods}
    _cache["key"], _cache["value"] = key, value
    return value


def _on(text):
    return str(text).strip().lower() not in ("false", "0", "off", "")


def yields(contents=None):
    """{hop 开关: 让出的原因}。"""
    st = state(contents)
    out = {}
    for key, (mod_id, opt, name) in YIELDS.items():
        opts = st["mods"].get(mod_id)
        if opts is None:
            continue
        if opt is None or _on(opts.get(opt, "true")):
            out[key] = name
    return out


def notes(contents=None):
    """给人看的提醒（中文，界面再翻译）：两边功能重叠但没替你关的、补丁改到同一个资源的。"""
    st = state(contents)
    mods = st["mods"]
    out = []
    if not st["deployed"]:
        return out
    # 2026-11-21 HD1-038：HellBox「过场加速」删了（来自 QoL），和 Obsidian Patches 结算加速重叠的提醒一起去掉
    if "alomare.eyesofliberty" in mods:
        out.append(tr("Obsidian 的 Eyes of Liberty（第三人称镜头）和 HellBox 分屏都改镜头，同时用可能打架。"))
    try:
        out += overlap_notes(contents or _contents())
    except Exception:
        pass
    return out


WHAT = {"core": "HellBox 核心脚本", "cursor": "指针颜色", "ghost": "鬼城地图配色"}


_overlap = {"key": None, "value": []}


def overlap_notes(contents):
    """我们的补丁和别人的补丁改了同一个资源：编号大的赢。鬼城那种由游戏那边自己退回夜晚，这里不再提。"""
    import patch_files
    paths = [patch_files.path_of(contents, b, s) for b, r in patch_files.ours().items() if r.get("what") != "ghost"
             for s in patch_files.slots(contents, b)]
    key = _stamp(paths)
    if _overlap["key"] == key:
        return _overlap["value"]
    out = []
    for bundle, r in patch_files.ours().items():
        if r.get("empty") or r.get("what") == "ghost":
            continue
        try:
            _p, mine = patch_files.read_entries(patch_files.path_of(contents, bundle, r["slot"]))
        except Exception:
            continue
        for s in patch_files.foreign(contents, bundle):
            try:
                _p, theirs = patch_files.read_entries(patch_files.path_of(contents, bundle, s))
            except Exception:
                continue
            both = set(mine) & set(theirs)
            if both:
                what = tr(WHAT.get(r.get("what"), bundle))
                if s > r["slot"]:
                    out.append(T("别的工具（比如 Obsidian）的补丁也改了{0}里的 {1} 个资源，排在 HellBox 后面，"
                                 "这几处按它的来，HellBox 对应的功能可能不起作用。", what, len(both)))
                else:
                    out.append(T("别的工具（比如 Obsidian）的补丁也改了{0}里的 {1} 个资源，HellBox 排在后面，这几处按 HellBox 的来。",
                                 what, len(both)))
    _overlap["key"], _overlap["value"] = key, out
    return out
