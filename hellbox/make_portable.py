r"""发行版的 HellBox 程序部分：Python 官方便携版 + 编译好的 HellBox（.pyc），不再用 PyInstaller（2026-11-21 HD1-037）。

为什么：N 网上传要过 VirusTotal，PyInstaller 打的 HellBox.exe 被 2 家杀毒软件误报，它的 _internal\base_library.zip
又算「压缩包套压缩包」，一起被隔离。用户定开源（MIT），源码放 GitHub；发行包里的 Python 代码编成 .pyc
（用户 2026-11-21 要包看着整齐：根目录只留 HellBox.exe、运行库、说明和 app / runtime 两个文件夹）。

做出来的样子（target = 发行目录）：
  HellBox.exe          = Python 官方的 pythonw.exe 改名（改名不影响 Python 软件基金会的数字签名）
  HellBox._pth         Python 读它决定去哪找模块（文件名跟 exe 同名才认），最后一行 import site 会读 runtime\boot\sitecustomize.py
  python314.dll 等      官方便携版的运行库（都有官方签名），要和 exe 放一起
  runtime\lib\         标准库（便携版里的 python314.zip 解出来，不留压缩包）
  runtime\dlls\        标准库的 .pyd 和它们要的 dll
  runtime\site-packages\  PySide6（只留 QtCore / QtGui / QtWidgets）、shiboken6、pymem，从开发环境 .venv 拷
  runtime\boot\sitecustomize.py   双击 HellBox.exe（没带参数）时打开 app\hellbox\app.pyc
  app\                 HellBox 本体：hellbox（界面）、mod（装核心、游戏里的 Lua 脚本）、ai（数据）、tools（LuaJIT）
                       paths.py 按「没打包」的路径找：ROOT = hellbox 的上一层 = app
  app 里的 .py 全部编成同名 .pyc 放在原地（compile_app），.py 不进包；Lua 脚本、数据照原样

便携版的 zip 第一次打包时从 python.org 下载，按固定的 sha256 核对，放在 .work\python-embed\dl\。
"""
import hashlib
import os
import shutil
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PY_VERSION = "3.14.4"  # 和开发环境 .venv 一样
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
EMBED_SHA256 = "cda80a9b1e75c0f1b4f9872ca1b417f0d19bce32facc811aea9180e70fad5fb9"
EMBED_ZIP = os.path.join(ROOT, ".work", "python-embed", "dl", f"python-{PY_VERSION}-embed-amd64.zip")

# 和 exe 放一起的（exe 启动时要直接载入）
TOP_FILES = ("python314.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll")
# 从 .venv 拷的第三方包（含 dist-info 里的授权说明）
PACKAGES = ("PySide6", "shiboken6", "pymem")
DIST_INFO_PREFIX = ("pyside6_essentials-", "shiboken6-", "pymem-")
# PySide6 只留这三个 Qt 模块（界面只用到它们，和以前 PyInstaller 版一样）
QT_KEEP = ("QtCore", "QtGui", "QtWidgets")
# PySide6 里整个删掉的（相对 PySide6 目录）：开发用的、用不到的插件和翻译
QT_DROP_DIRS = ("translations", "qml", "include", "typesystems", "glue", "metatypes", "scripts", "doc", "examples",
                "resources", "plugins/generic", "plugins/networkinformation", "plugins/tls", "plugins/platforminputcontexts",
                "plugins/iconengines", "plugins/qmltooling", "plugins/sqldrivers", "plugins/multimedia", "plugins/designer",
                "plugins/position", "plugins/sensors", "plugins/texttospeech", "plugins/webview", "plugins/virtualkeyboard",
                "plugins/canbus", "plugins/sceneparsers", "plugins/renderers", "plugins/geometryloaders",
                "plugins/printsupport", "plugins/assetimporters", "plugins/qmllint", "plugins/scxmldatamodel",
                "plugins/permissions", "plugins/tracing", "plugins/egldeviceintegrations", "plugins/xcbglintegrations")
QT_DROP_FILES = ("opengl32sw.dll", "plugins/platforms/qdirect2d.dll", "plugins/platforms/qminimal.dll",
                 "plugins/platforms/qoffscreen.dll", "plugins/imageformats/qgif.dll", "plugins/imageformats/qjpeg.dll",
                 "plugins/imageformats/qpdf.dll", "plugins/imageformats/qsvg.dll", "plugins/imageformats/qtga.dll",
                 "plugins/imageformats/qtiff.dll", "plugins/imageformats/qwbmp.dll", "plugins/imageformats/qwebp.dll",
                 "plugins/imageformats/qicns.dll")
# hellbox\ 里不进发行包的（打包工具）
UI_SKIP = ("make_exe.py", "make_portable.py", "make_icon.py")

PTH = "\n".join([
    "runtime\\lib",
    "runtime\\dlls",
    "runtime\\site-packages",
    "runtime\\boot",
    "app\\hellbox",
    "import site",
    "",
])

SITECUSTOMIZE = '''"""双击 HellBox.exe（= Python 官方 pythonw.exe 改名）时打开 HellBox。
带参数运行（比如换语言后重开：HellBox.exe app\\\\hellbox\\\\app.pyc --page xxx）时什么都不做，照 Python 平常的样子跑。
2026-11-21 HD1-037：发行版不再用 PyInstaller，见 hellbox\\\\make_portable.py（源码仓库里）。"""
import os
import sys

if len(getattr(sys, "orig_argv", sys.argv)) <= 1 and os.path.basename(sys.executable).lower() == "hellbox.exe":
    import runpy
    app = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "app", "hellbox", "app.pyc")
    if not os.path.isfile(app):
        app = app[:-1]  # 没编译的（app.py）
    sys.argv = [app]
    code = 0
    try:
        runpy.run_path(app, run_name="__main__")
    except SystemExit as e:  # 界面关掉时 app.py 用 sys.exit 退出
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except BaseException:
        import traceback
        log = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox", "logs", "hellbox-crash.txt")
        try:
            os.makedirs(os.path.dirname(log), exist_ok=True)
            with open(log, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except OSError:
            pass
        code = 1
    # 这里还在 Python 启动阶段（读 sitecustomize），直接 SystemExit 会被当成启动失败；收好尾后直接结束进程
    import atexit
    atexit._run_exitfuncs()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream and stream.flush()
        except Exception:
            pass
    os._exit(code)
'''


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def embed_zip():
    if not os.path.isfile(EMBED_ZIP):
        os.makedirs(os.path.dirname(EMBED_ZIP), exist_ok=True)
        print(f"下载 Python 官方便携版：{EMBED_URL}")
        tmp = EMBED_ZIP + ".part"
        urllib.request.urlretrieve(EMBED_URL, tmp)
        os.replace(tmp, EMBED_ZIP)
    if _sha(EMBED_ZIP) != EMBED_SHA256:
        raise SystemExit(f"Python 便携版的 sha256 对不上，不用它：{EMBED_ZIP}")
    return EMBED_ZIP


def _venv_site_packages():
    import PySide6  # 打包用的就是开发环境的 Python
    return os.path.dirname(os.path.dirname(os.path.abspath(PySide6.__file__)))


def _ignore_cache(_d, names):
    return [n for n in names if n == "__pycache__" or n.endswith(".pyc")]


def _prune_qt(qt):
    for rel in QT_DROP_DIRS:
        p = os.path.join(qt, *rel.split("/"))
        if os.path.isdir(p):
            shutil.rmtree(p)
    for rel in QT_DROP_FILES:
        p = os.path.join(qt, *rel.split("/"))
        if os.path.isfile(p):
            os.remove(p)
    for name in os.listdir(qt):
        full = os.path.join(qt, name)
        if not os.path.isfile(full):
            continue
        low = name.lower()
        # Qt 模块：只留 QtCore / QtGui / QtWidgets 的 .pyd 和 .pyi
        if low.startswith("qt") and low.endswith((".pyd", ".pyi")):
            if name.split(".")[0] not in QT_KEEP:
                os.remove(full)
            continue
        # Qt 动态库：只留三个模块要的（Qt6Core / Qt6Gui / Qt6Widgets），别的 Qt6*.dll 删
        if low.startswith("qt6") and low.endswith(".dll"):
            if name.split(".")[0] not in ("Qt6Core", "Qt6Gui", "Qt6Widgets"):
                os.remove(full)
            continue
        # 设计器、工具程序
        if low.endswith(".exe"):
            os.remove(full)


def build_runtime(target, app):
    """在 target 里放好 HellBox.exe、运行库、runtime\\；界面代码放进 app\\hellbox（还是 .py，最后 compile_app 编译）。"""
    z = zipfile.ZipFile(embed_zip())
    names = set(z.namelist())
    runtime = os.path.join(target, "runtime")
    for d in ("lib", "dlls", "site-packages", "boot"):
        os.makedirs(os.path.join(runtime, d), exist_ok=True)
    with open(os.path.join(target, "HellBox.exe"), "wb") as f:
        f.write(z.read("pythonw.exe"))
    for name in TOP_FILES:
        with open(os.path.join(target, name), "wb") as f:
            f.write(z.read(name))
    with open(os.path.join(runtime, "PYTHON-LICENSE.txt"), "wb") as f:
        f.write(z.read("LICENSE.txt"))
    # PySide6 / Qt 按 LGPL-3.0 用（没改过），附上 LGPL 和它引用的 GPL 原文（tools\licenses，来自 gnu.org）
    shutil.copytree(os.path.join(ROOT, "tools", "licenses"), os.path.join(runtime, "licenses"))
    for name in names:
        low = name.lower()
        if low.endswith(".pyd") or (low.endswith(".dll") and name not in TOP_FILES):
            with open(os.path.join(runtime, "dlls", name), "wb") as f:
                f.write(z.read(name))
    # 标准库：便携版里是 python314.zip（编译好的 .pyc），解开放进 runtime\lib，发行包里不留压缩包
    import io
    with zipfile.ZipFile(io.BytesIO(z.read("python314.zip"))) as stdlib:
        stdlib.extractall(os.path.join(runtime, "lib"))
    with open(os.path.join(target, "HellBox._pth"), "w", encoding="ascii", newline="\r\n") as f:
        f.write(PTH)
    with open(os.path.join(runtime, "boot", "sitecustomize.py"), "w", encoding="utf-8") as f:
        f.write(SITECUSTOMIZE)
    # 第三方包
    sp = _venv_site_packages()
    for pkg in PACKAGES:
        src = os.path.join(sp, pkg)

        def ignore(d, names, src=src):
            skip = _ignore_cache(d, names)
            rel = os.path.relpath(d, src).replace(os.sep, "/")
            for n in names:  # 要删的文件夹拷都不拷（有的路径太长，拷不过去）
                if (n if rel == "." else rel + "/" + n) in QT_DROP_DIRS:
                    skip.append(n)
            return skip
        shutil.copytree(src, os.path.join(runtime, "site-packages", pkg), ignore=ignore if pkg == "PySide6" else _ignore_cache)
    for name in os.listdir(sp):
        if name.lower().startswith(DIST_INFO_PREFIX) and name.endswith(".dist-info"):
            shutil.copytree(os.path.join(sp, name), os.path.join(runtime, "site-packages", name), ignore=_ignore_cache)
    _prune_qt(os.path.join(runtime, "site-packages", "PySide6"))
    # 界面代码
    ui = os.path.join(app, "hellbox")
    shutil.copytree(HERE, ui, ignore=lambda d, names: _ignore_cache(d, names) + [n for n in names if n in UI_SKIP])


def compile_app(target, app):
    """app 里的 .py 全部编成同名 .pyc（放在原地，Python 认「没有源码的 .pyc」），删掉 .py。
    文件名记成 app 里的相对路径（报错时显示 hellbox/app.py 这样，不带打包电脑上的路径）。"""
    import py_compile
    assert sys.version.split()[0] == PY_VERSION, f"要用 Python {PY_VERSION} 编（和发行包里的一样），现在是 {sys.version}"
    n = 0
    for d, dirs, names in os.walk(app):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for name in names:
            if not name.endswith(".py"):
                continue
            src = os.path.join(d, name)
            rel = os.path.relpath(src, app).replace(os.sep, "/")
            py_compile.compile(src, cfile=src + "c", dfile=rel, doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
            os.remove(src)
            n += 1
    left = [os.path.join(d, x) for d, _, names in os.walk(app) for x in names if x.endswith(".py")]
    assert not left, left
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(target) for f in fs)
    print(f"HellBox 程序（官方 Python {PY_VERSION} + 编译好的代码 {n} 个）：{target}（{size / 1e6:.1f} MB）")
