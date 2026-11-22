"""把 HellBox 打包成 bin\\HellBox\\HellBox.exe（文件夹版），根目录放快捷方式 HellBox.lnk。

运行：.venv\\Scripts\\python hellbox\\make_exe.py
     .venv\\Scripts\\python hellbox\\make_exe.py --dist .work\\hb_test   先打一份测试用的（不碰 bin\\、不改快捷方式；
     要放在 Helldivers 下面三层以内，exe 才找得到 mod 文件夹）
     --public 会打独立发行目录，可用 --luajit 指定现有 LuaJIT 工具目录。
     2026-11-21 HD1-037：--public --portable 是另一种打法（Python 官方便携版 + .pyc，make_portable.py）；
     用户同日定发行版还是用 PyInstaller（界面看着舒服），--portable 留着备用。
注意：bin\\HellBox\\HellBox.exe 开着的时候打包会失败（文件被占用），先关掉 HellBox。

为什么不打成单个 exe：单文件版每次启动要先解压到临时目录，实测 2.5～3.8 秒才出窗口；文件夹版约 1 秒。
为什么放 bin\\ 下：ROOT\\HellBox 和源码目录 ROOT\\hellbox 在 Windows 上是同一个文件夹。

exe 里只有界面（hellbox/）、Python 运行时、Qt（只带 QtCore / QtGui / QtWidgets）、字体、图标。
界面是 Qt（PySide6，2026-11-07 从 tkinter 换过来）；打完会删掉用不到的 Qt 插件和翻译，见 PRUNE。
mod 的功能代码（mod\\build.py、cursor_mod.py……、ai\\bridge.py）不打进去，运行时从磁盘读：
改 mod 不用重新打包。所以要把它们会用到的标准库模块列进 HIDDEN，否则 exe 里没有。
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, ".work", "hellbox-build")
DIST = os.path.join(ROOT, "bin")

# mod 代码在磁盘上，不许打进 exe（否则 exe 里的旧副本会盖过磁盘上的新版本）
FROM_DISK = ["build", "bundle", "cursor_mod", "cursor_patch", "texture", "room_name_live", "hellbox_options", "hellbox_hop", "bridge", "drill_spec", "ghost_maps", "patch_files", "obsidian_compat", "camera_stack"]

# mod 代码用到、界面本身没用到的模块
HIDDEN = ["hashlib", "functools", "copy", "random", "re", "shutil", "struct", "subprocess", "zlib", "winreg", "json", "time", "math", "base64",
          "ctypes", "ctypes.wintypes", "dataclasses", "pymem", "pymem.process", "pymem.memory",
          "pymem.exception", "pymem.ressources", "pymem.pattern", "pymem.ptypes", "pymem.thread"]

# 界面只用到 QtCore / QtGui / QtWidgets；别的 Qt 模块、tkinter 都不要
EXCLUDE = ["PIL", "customtkinter", "numpy", "tkinter", "_tkinter",
           "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtSvg", "PySide6.QtOpenGL",
           "PySide6.QtDBus", "PySide6.QtPrintSupport", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtXml",
           "PySide6.QtConcurrent", "PySide6.QtUiTools", "PySide6.QtHelp", "PySide6.QtDesigner"]

# 打完从 _internal\PySide6 里删掉的（相对路径）：用不到的插件、翻译、软件 OpenGL
PRUNE = ["translations", "opengl32sw.dll", "Qt6Network.dll", "Qt6Svg.dll", "plugins/platforms/qdirect2d.dll", "plugins/platforms/qminimal.dll",
         "plugins/platforms/qoffscreen.dll", "plugins/generic", "plugins/networkinformation", "plugins/tls",
         "plugins/platforminputcontexts", "plugins/iconengines", "plugins/imageformats/qgif.dll",
         "plugins/imageformats/qjpeg.dll", "plugins/imageformats/qpdf.dll", "plugins/imageformats/qsvg.dll",
         "plugins/imageformats/qtga.dll", "plugins/imageformats/qtiff.dll", "plugins/imageformats/qwbmp.dll",
         "plugins/imageformats/qwebp.dll", "plugins/imageformats/qicns.dll"]


PUBLIC_MOD_FILES = ("build.py", "bundle.py", "cursor_mod.py", "cursor_patch.py", "texture.py",
                    "room_name_live.py", "hellbox_options.py", "hellbox_hop.py",  # 2026-11-20 HD1-035 收进来的 QoL
                    "ghost_maps.py", "ghost_shading.bin",
                    "patch_files.py", "obsidian_compat.py",  # 2026-11-20 HD1-036 补丁装法、认出 Obsidian
                    "camera_stack.py")  # 2026-11-21 HD1-037 分屏用 Python 叠进启动脚本（不再带分屏 exe）
PUBLIC_DATA = ("drill_spec.py", "drill_monsters.json", "loadout_items.json", "room_words.json", "enemy_settings.json", "enemy_fields.json", "weapon_fields.json", "strat_fields.json", "spawn_tables.json")


def copy_public_support(target, compiler, app=None):
    """说明文件放 target；mod / ai / tools 放 app（发行版是 target\\app，自用 PyInstaller 版就是 target）。"""
    sys.path.insert(0, os.path.join(ROOT, "mod"))
    import build

    app = app or target
    mod = os.path.join(app, "mod")
    os.makedirs(mod, exist_ok=True)
    # 2026-11-21 HD1-037：开源，MIT 授权（含第三方部分说明）
    shutil.copy2(os.path.join(ROOT, "LICENSE"), os.path.join(target, "LICENSE.txt"))
    for name in PUBLIC_MOD_FILES:
        shutil.copy2(os.path.join(ROOT, "mod", name), mod)
    with open(os.path.join(mod, "public_release"), "w", encoding="ascii") as f:
        f.write("HellBox public build\n")
    # HD1-034：发行版也带录制接口（ai_bridge、ai_mech + 前后两个休眠开关），和 build.patches() 的发行版清单一致
    # 原版脚本（vanilla:）不拷：装的时候从玩家自己的游戏里取（build.vanilla_source）
    sources = {file for files in build.PATCHES.values() for file in files
               if not file.startswith(build.VANILLA)
               and (os.path.basename(file) not in build.PRIVATE_SCRIPTS or os.path.basename(file) in build.REC_SCRIPTS)}
    sources |= {build.REC_GATE_PRE, build.REC_GATE_POST}
    for file in sources:
        dst = os.path.join(mod, file)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, "mod", file), dst)
    # 分屏（HalfSugar 的 CameraCTRL，作者同意收进 HellBox）：装 MOD 时把分屏模块（runtime.luac）叠进脚本文件
    shutil.copytree(os.path.join(ROOT, "mod", "camera"), os.path.join(mod, "camera"), dirs_exist_ok=True)
    data = os.path.join(app, "ai")
    os.makedirs(data, exist_ok=True)
    for name in PUBLIC_DATA:
        shutil.copy2(os.path.join(ROOT, "ai", name), data)
    lua = os.path.join(app, "tools", "luajit-2.0")
    src = os.path.join(lua, "src")
    os.makedirs(src, exist_ok=True)
    for name in ("luajit.exe", "lua51.dll"):
        shutil.copy2(os.path.join(compiler, "src", name), src)
    shutil.copytree(os.path.join(compiler, "src", "jit"), os.path.join(src, "jit"), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.obj", "*.o", "*.dll", "*.lib", "*.exp"))
    shutil.copy2(os.path.join(compiler, "COPYRIGHT"), lua)


def compiler_dir():
    if "--luajit" in sys.argv:
        return os.path.abspath(sys.argv[sys.argv.index("--luajit") + 1])
    return os.path.join(ROOT, "tools", "luajit-2.0")


VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '07'),
      StringStruct('FileDescription', 'HellBox - HELLDIVERS (2015) mod tool'),
      StringStruct('FileVersion', '{text}'),
      StringStruct('InternalName', 'HellBox'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 07. MIT License.'),
      StringStruct('OriginalFilename', 'HellBox.exe'),
      StringStruct('ProductName', 'HellBox'),
      StringStruct('ProductVersion', '{text}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def version_file():
    """2026-11-22（GPT 建议，减误报 / 方便核对）：exe 带版本信息（右键属性 → 详细信息），版本号跟 app.py 的 VERSION。"""
    import re
    with open(os.path.join(HERE, "app.py"), encoding="utf-8") as f:
        m = re.search(r'^VERSION = "V(\d+)\.(\d+)"', f.read(), re.M)
    major, minor = int(m.group(1)), int(m.group(2))
    path = os.path.join(WORK, "version_info.txt")
    os.makedirs(WORK, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO.format(nums=(major, minor, 0, 0), text=f"{major}.{m.group(2)}"))
    return path


def main():
    public = "--public" in sys.argv
    dist = os.path.join(ROOT, ".work", "hellbox-public") if public else DIST
    if "--dist" in sys.argv:
        dist = os.path.abspath(sys.argv[sys.argv.index("--dist") + 1])
    subprocess.run([sys.executable, os.path.join(HERE, "make_icon.py")], check=True)
    if public and "--portable" in sys.argv:
        # 2026-11-21 HD1-037：备用打法，Python 官方便携版 + 编译好的代码（见 make_portable.py）；发行版用的是下面的 PyInstaller
        # 本体都在 app\\ 里，根目录只留 HellBox.exe、运行库、说明、runtime\\
        import make_portable
        target = os.path.join(dist, "HellBox")
        app = os.path.join(target, "app")
        if os.path.isdir(target):
            assert os.path.isfile(os.path.join(target, "HellBox.exe")), f"不认识的目录，不删：{target}"
            shutil.rmtree(target)
        make_portable.build_runtime(target, app)
        copy_public_support(target, compiler_dir(), app)
        if "--full" in sys.argv:  # 2026-11-19 用户要自用全数据版：数据页潜兵 / 武器 / 战备全部打开（data_blocks.FULL）
            with open(os.path.join(app, "mod", "data_full"), "w", encoding="ascii") as f:
                f.write("")
        make_portable.compile_app(target, app)
        print(f"发行测试包：{target}" + ("（全数据版）" if "--full" in sys.argv else ""))
        return
    sep = os.pathsep
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
           "--console" if "--console" in sys.argv else "--windowed",
           "--name", "HellBox",
           "--icon", os.path.join(HERE, "icon.ico"),
           "--noupx",
           "--add-data", f"{os.path.join(HERE, 'fonts')}{sep}fonts",
           "--add-data", f"{os.path.join(HERE, 'icon.png')}{sep}.",
           "--add-data", f"{os.path.join(HERE, 'icon.ico')}{sep}.",
           "--add-data", f"{os.path.join(HERE, 'lang_en.json')}{sep}.",  # 英文版界面文字（i18n.py）
           "--paths", HERE,
           "--distpath", dist,
           "--workpath", os.path.join(WORK, "work"),
           "--specpath", WORK]
    for m in EXCLUDE:
        cmd += ["--exclude-module", m]
    hidden = HIDDEN
    if public:
        # 2026-11-22：发布版不带 pymem（发布版读写内存走 mod\room_name_live.py 的 ctypes；用 pymem 的 ai\bridge.py 不进发布版）。
        #   不带 base_library.zip：Python 模块散放在 _internal 里（N 网把「压缩包里套压缩包」当隔离理由）。顶层目录和图标不变。
        hidden = [m for m in HIDDEN if m != "pymem" and not m.startswith("pymem.")]
        cmd += ["--debug", "noarchive", "--version-file", version_file()]
        cmd += ["--exclude-module", "pymem"]
    for m in hidden:
        cmd += ["--hidden-import", m]
    for m in FROM_DISK:
        cmd += ["--exclude-module", m]
    cmd.append(os.path.join(HERE, "app.py"))
    subprocess.run(cmd, check=True)
    exe = os.path.join(dist, "HellBox", "HellBox.exe")
    internal = os.path.join(dist, "HellBox", "_internal")
    prune(os.path.join(internal, "PySide6"))
    # Qt links to the Windows ICU API. PyInstaller can pick up an incompatible
    # ICU from another installed application on PATH.
    for name in os.listdir(internal):
        if name.casefold().startswith(("icuuc", "icudt", "icuin")) and name.lower().endswith(".dll"):
            os.remove(os.path.join(internal, name))
    if public:
        target = os.path.dirname(exe)
        copy_public_support(target, compiler_dir())
        if "--full" in sys.argv:  # 2026-11-19 用户要自用全数据版：数据页潜兵 / 武器 / 战备全部打开（data_blocks.FULL）
            with open(os.path.join(target, "mod", "data_full"), "w", encoding="ascii") as f:
                f.write("")
        print(f"发行测试包：{target}" + ("（全数据版）" if "--full" in sys.argv else ""))
        return
    if dist != DIST:
        print(f"测试版：{exe}（没改 bin 和快捷方式）")
        return
    old = os.path.join(ROOT, "HellBox.exe")  # 以前的单文件版
    if os.path.exists(old):
        os.remove(old)
    link = os.path.join(ROOT, "HellBox.lnk")
    make_shortcut(exe, link)
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(os.path.dirname(exe)) for f in fs)
    print(f"已生成 {exe}（整个文件夹 {size / 1e6:.1f} MB），快捷方式 {link}")


def prune(qt):
    import shutil
    for rel in PRUNE:
        p = os.path.join(qt, *rel.split("/"))
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.isfile(p):
            os.remove(p)


def make_shortcut(target, link):
    ps = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{link}'); "
          f"$s.TargetPath = '{target}'; $s.WorkingDirectory = '{os.path.dirname(target)}'; "
          f"$s.IconLocation = '{target},0'; $s.Description = 'HellBox'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


if __name__ == "__main__":
    main()
